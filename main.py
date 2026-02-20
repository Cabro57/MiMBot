"""
trading_bot.main
~~~~~~~~~~~~~~~~~
Asenkron orkestratör — tüm modülleri başlatır ve koordine eder.

Akış:
  1. Config yükle & loglama başlat
  2. Veritabanını başlat
  3. Aktif sembol listesini çek (public REST, API Key gerektirmez)
  4. WebSocket istemcisini başlat (Kline + Mark Price)
  5. Strateji tarama döngüsünü başlat
  6. Position Watcher'ı başlat
  7. Graceful shutdown

Kullanım:
  python -m trading_bot.main
"""
from __future__ import annotations

import asyncio
import platform
import signal as os_signal
import sys
from datetime import datetime, timezone

import aiohttp

from core.config import TradingConfig
from core.database import close_db, init_db
from core.logger import get_logger, setup_logging
from data.memory_store import MemoryStore
from data.websocket_client import BinanceWebSocketClient
from execution.position_watcher import PositionWatcher
from execution.signal_dispatcher import SignalDispatcher
from strategies.ema_volume_strategy import EmaVolumeStrategy

logger = get_logger(__name__)


# ── Sembol Listesi Çekme (Public REST) ────────────────────────────────

async def fetch_active_symbols(limit: int = 100) -> list[str]:
    """
    Binance Futures'tan halka açık endpoint ile aktif USDT
    perpetual sembollerini çeker. API Key gerektirmez.
    """
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()

        symbols = [
            s["symbol"]
            for s in data.get("symbols", [])
            if s.get("status") == "TRADING"
            and s.get("contractType") == "PERPETUAL"
            and s.get("quoteAsset") == "USDT"
        ]
        logger.info("symbols_fetched", count=len(symbols))
        return symbols[:limit]

    except Exception as e:
        logger.error("symbol_fetch_failed", error=str(e))
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT"]  # fallback


# ── Strateji Tarama Döngüsü ──────────────────────────────────────────

async def strategy_scan_loop(
    config: TradingConfig,
    strategy: EmaVolumeStrategy,
    dispatcher: SignalDispatcher,
    watcher: PositionWatcher,
    store: MemoryStore,
    symbols: list[str],
) -> None:
    """
    Periyodik olarak tüm sembolleri strateji ile değerlendirir.
    Sinyal bulunursa dispatcher aracılığıyla Telegram + DB + Watcher'a gönderir.
    """
    logger.info("scan_loop_started", interval_sec=config.scan_interval_seconds)

    # İlk taramadan önce WebSocket'in veri toplamasını bekle
    warmup_seconds = 90
    logger.info("warmup_waiting", seconds=warmup_seconds)
    await asyncio.sleep(warmup_seconds)

    while True:
        try:
            scan_start = datetime.now(timezone.utc)
            tracked = watcher.tracked_symbols

            # Takip edilmeyen sembolleri tara
            candidates = [s for s in symbols if s not in tracked]
            logger.info("scan_cycle_start", total=len(candidates), tracked=len(tracked))

            # Paralel değerlendirme (semaphore ile sınırlandırılmış)
            semaphore = asyncio.Semaphore(config.max_parallel_tasks)

            async def _eval(sym: str):
                async with semaphore:
                    return await strategy.evaluate(sym)

            tasks = [_eval(s) for s in candidates]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Hatalı sonuçları filtrele, sinyalleri topla
            signals = []
            for res in results:
                if isinstance(res, Exception):
                    logger.debug("eval_exception", error=str(res))
                elif res is not None:
                    signals.append(res)

            logger.info(
                "scan_cycle_complete",
                scanned=len(candidates),
                signals_found=len(signals),
                elapsed_ms=int((datetime.now(timezone.utc) - scan_start).total_seconds() * 1000),
            )

            if signals:
                # En güçlü hacim spike'ına göre sırala, en fazla N sinyal gönder
                signals.sort(key=lambda s: s.spike_ratio, reverse=True)
                top_signals = signals[: config.max_tracked_signals]

                for sig in top_signals:
                    await dispatcher.dispatch(sig)

            await asyncio.sleep(config.scan_interval_seconds)

        except asyncio.CancelledError:
            logger.info("scan_loop_cancelled")
            break
        except Exception as e:
            logger.error("scan_loop_error", error=str(e), error_type=type(e).__name__)
            await asyncio.sleep(60)


# ── Sembol Listesi Yenileme Döngüsü ──────────────────────────────────

async def symbol_refresh_loop(
    config: TradingConfig,
    ws_client: BinanceWebSocketClient,
    symbols_ref: list,
) -> None:
    """Market listesini periyodik olarak günceller."""
    refresh_interval = config.market_refresh_hours * 3600

    while True:
        await asyncio.sleep(refresh_interval)
        try:
            new_symbols = await fetch_active_symbols(config.top_volume_limit)
            symbols_ref.clear()
            symbols_ref.extend(new_symbols)
            ws_client.update_symbols(new_symbols)
            logger.info("symbols_refreshed", count=len(new_symbols))
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("symbol_refresh_error", error=str(e))


# ── Ana Orkestratör ──────────────────────────────────────────────────

async def main() -> None:
    """Tüm modülleri oluşturur, bağlar ve paralel çalıştırır."""

    # 1. Config & Logging
    config = TradingConfig()
    setup_logging(config.log_level)
    logger.info("bot_starting", version="5.0", mode="scanner_paper_trading")

    # 2. Veritabanı
    await init_db(config.db_url)

    # 3. Sembol listesi (public REST)
    symbols = await fetch_active_symbols(config.top_volume_limit)

    # 4. Bellek deposu
    store = MemoryStore(maxlen=200)

    # 5. Position Watcher (sanal TP/SL takibi)
    watcher = PositionWatcher(config, store)

    # 6. Signal Dispatcher (Telegram + DB)
    dispatcher = SignalDispatcher(config, watcher)

    # Telegram callback'i watcher'a bağla
    watcher._on_close = dispatcher.send_notification

    # 7. WebSocket istemcisi (public Kline + Mark Price)
    ws_client = BinanceWebSocketClient(config, store, symbols)

    # 8. Strateji
    strategy = EmaVolumeStrategy(config, store)

    # Başlangıç bildirimi
    await dispatcher.send_notification(
        f"🚀 <b>AstarBot v5.0 Aktif</b>\n"
        f"📡 Mod: Scanner & Paper Trading\n"
        f"📊 {len(symbols)} sembol takipte\n"
        f"⚡ WebSocket Kline + Mark Price"
    )

    # ── Paralel görevleri başlat ──────────────────────────────────────
    tasks = [
        asyncio.create_task(ws_client.start(), name="websocket"),
        asyncio.create_task(watcher.run(), name="position_watcher"),
        asyncio.create_task(
            strategy_scan_loop(config, strategy, dispatcher, watcher, store, symbols),
            name="scan_loop",
        ),
        asyncio.create_task(
            symbol_refresh_loop(config, ws_client, symbols),
            name="symbol_refresh",
        ),
    ]

    # ── Graceful Shutdown ─────────────────────────────────────────────
    shutdown_event = asyncio.Event()

    def _shutdown_handler():
        logger.info("shutdown_signal_received")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    # Windows'ta SIGTERM yok; sadece KeyboardInterrupt ile kapanır
    if platform.system() != "Windows":
        for sig in (os_signal.SIGINT, os_signal.SIGTERM):
            loop.add_signal_handler(sig, _shutdown_handler)

    try:
        # shutdown_event set olana kadar veya bir task çökene kadar bekle
        done, pending = await asyncio.wait(
            [asyncio.create_task(shutdown_event.wait()), *tasks],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Temizlik
        for t in pending:
            t.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    except KeyboardInterrupt:
        logger.info("keyboard_interrupt")
    finally:
        await ws_client.stop()
        await watcher.stop()
        await dispatcher.send_notification("🔴 <b>AstarBot kapatıldı.</b>")
        await close_db()
        logger.info("bot_shutdown_complete")


# ── Entry Point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
