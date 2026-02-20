"""
trading_bot.data.websocket_client
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Binance Futures public WebSocket istemcisi.
API Key gerektirmez — sadece halka açık Kline ve Mark Price yayınlarını dinler.

Görevleri:
  1. Kline (mum) verilerini MemoryStore'a yazmak
  2. Mark Price verilerini MemoryStore'a yazmak (position_watcher için)
  3. Bağlantı koptuğunda otomatik yeniden bağlanmak
"""
from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

import websockets
from websockets.exceptions import ConnectionClosed

from core.logger import get_logger

if TYPE_CHECKING:
    from core.config import TradingConfig
    from data.memory_store import MemoryStore

logger = get_logger(__name__)

# Binance Futures public WS base URL
_WS_BASE = "wss://fstream.binance.com"


class BinanceWebSocketClient:
    """
    Binance Futures halka açık WebSocket istemcisi.

    İki bağımsız stream yönetir:
      • Kline stream  — strateji modülü için OHLCV mumları
      • Mark Price stream — position_watcher için anlık fiyatlar

    Kullanım:
        client = BinanceWebSocketClient(config, store, symbols)
        await client.start()   # asyncio.gather içinde çağrılır
        await client.stop()    # graceful shutdown
    """

    def __init__(
        self,
        config: TradingConfig,
        store: MemoryStore,
        symbols: list[str],
    ) -> None:
        self._config = config
        self._store = store
        self._symbols = [s.replace("/", "").lower() for s in symbols]
        self._running = False
        self._tasks: list[asyncio.Task] = []

    # ── Public API ────────────────────────────────────────────────────

    async def start(self) -> None:
        """Kline ve Mark Price stream'lerini başlatır."""
        self._running = True
        self._tasks = [
            asyncio.create_task(self._run_kline_stream(), name="ws_kline"),
            asyncio.create_task(self._run_mark_price_stream(), name="ws_mark_price"),
        ]
        logger.info("websocket_started", symbol_count=len(self._symbols))
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def stop(self) -> None:
        """Tüm WebSocket bağlantılarını kapatır."""
        self._running = False
        for t in self._tasks:
            t.cancel()
        logger.info("websocket_stopped")

    def update_symbols(self, symbols: list[str]) -> None:
        """Sembol listesini günceller (yeniden bağlanma gerektirir)."""
        self._symbols = [s.replace("/", "").lower() for s in symbols]
        logger.info("symbols_updated", count=len(self._symbols))

    # ── Kline Stream ──────────────────────────────────────────────────

    async def _run_kline_stream(self) -> None:
        """Kline combined stream — otomatik reconnect ile."""
        while self._running:
            try:
                url = self._build_kline_url()
                logger.info("kline_connecting", url=url[:120])

                async with websockets.connect(url, ping_interval=20) as ws:
                    logger.info("kline_connected")
                    async for raw in ws:
                        if not self._running:
                            break
                        await self._handle_kline_msg(raw)

            except ConnectionClosed as e:
                logger.warning("kline_disconnected", code=e.code, reason=str(e.reason))
            except Exception as e:
                logger.error("kline_error", error=str(e), error_type=type(e).__name__)

            if self._running:
                delay = self._config.ws_reconnect_delay
                logger.info("kline_reconnecting", delay_sec=delay)
                await asyncio.sleep(delay)

    def _build_kline_url(self) -> str:
        """Çoklu sembol + çoklu timeframe combined stream URL'si oluşturur."""
        streams: list[str] = []
        for sym in self._symbols:
            for tf in self._config.ws_kline_timeframes:
                streams.append(f"{sym}@kline_{tf}")
        # Binance 200 stream limiti var; gerekirse chunk'lanabilir
        return f"{_WS_BASE}/stream?streams={'/'.join(streams[:200])}"

    async def _handle_kline_msg(self, raw: str) -> None:
        """Gelen Kline mesajını parse edip MemoryStore'a yazar."""
        try:
            msg = json.loads(raw)
            data = msg.get("data", {})
            kline = data.get("k")
            if kline is None:
                return

            symbol = kline["s"]        # "BTCUSDT"
            timeframe = kline["i"]     # "1m"
            is_closed = kline["x"]     # bool — mum kapandı mı?

            candle = [
                float(kline["t"]),     # timestamp (ms)
                float(kline["o"]),     # open
                float(kline["h"]),     # high
                float(kline["l"]),     # low
                float(kline["c"]),     # close
                float(kline["v"]),     # volume
            ]

            await self._store.update_candle(symbol, timeframe, candle, is_closed=is_closed)

            # Mark price cache'i close fiyatıyla da güncelle (ek kaynak)
            await self._store.update_price(symbol, candle[4])

        except (KeyError, ValueError, TypeError) as e:
            logger.debug("kline_parse_skip", error=str(e))

    # ── Mark Price Stream ─────────────────────────────────────────────

    async def _run_mark_price_stream(self) -> None:
        """
        Tüm sembollerin mark price'ını 1s aralıkla yayınlayan genel stream.
        position_watcher sanal TP/SL kontrolü için bu fiyatları kullanır.
        """
        url = f"{_WS_BASE}/ws/!markPrice@arr@1s"

        while self._running:
            try:
                logger.info("markprice_connecting")
                async with websockets.connect(url, ping_interval=20) as ws:
                    logger.info("markprice_connected")
                    async for raw in ws:
                        if not self._running:
                            break
                        await self._handle_mark_price_msg(raw)

            except ConnectionClosed as e:
                logger.warning("markprice_disconnected", code=e.code, reason=str(e.reason))
            except Exception as e:
                logger.error("markprice_error", error=str(e), error_type=type(e).__name__)

            if self._running:
                delay = self._config.ws_reconnect_delay
                logger.info("markprice_reconnecting", delay_sec=delay)
                await asyncio.sleep(delay)

    async def _handle_mark_price_msg(self, raw: str) -> None:
        """
        Mark Price dizisini parse edip MemoryStore'daki fiyat cache'ini günceller.
        Sadece takip edilen sembolleri günceller (performans için).
        """
        try:
            items = json.loads(raw)
            if not isinstance(items, list):
                return

            tracked = set(self._symbols)
            for item in items:
                sym = item.get("s", "").lower()
                if sym in tracked:
                    price = float(item["p"])  # mark price
                    await self._store.update_price(item["s"], price)

        except (KeyError, ValueError, TypeError) as e:
            logger.debug("markprice_parse_skip", error=str(e))
