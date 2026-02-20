"""
trading_bot.execution.position_watcher
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Sanal pozisyon takip modülü (Paper Trading).
Gerçek borsada işlem AÇMAZ — sadece sinyalleri bellekte izler
ve TP/SL/Timeout durumlarını tespit eder.

Fiyat verisini MemoryStore'daki mark price cache'inden alır
(WebSocket public stream tarafından sürekli güncellenir).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict

from core.database import get_session
from core.logger import get_logger
from models.db_models import TradeRecord

if TYPE_CHECKING:
    from core.config import TradingConfig
    from data.memory_store import MemoryStore
    from strategies.base_strategy import Signal

logger = get_logger(__name__)


@dataclass
class VirtualPosition:
    """Bellekte tutulan sanal pozisyon."""
    signal_id: int
    symbol: str
    side: str              # "LONG" | "SHORT"
    entry_price: float
    tp_price: float
    sl_price: float
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PositionWatcher:
    """
    Sanal TP/SL/Timeout takipçisi.

    WebSocket mark price stream'i MemoryStore'a fiyatları yazar;
    bu modül periyodik olarak fiyatları kontrol ederek sanal
    pozisyonları kapatır ve sonuçları DB + Telegram'a yazar.

    Kullanım:
        watcher = PositionWatcher(config, store, telegram_callback)
        await watcher.track(signal, signal_id)
        await watcher.run()  # asyncio.gather içinde
    """

    def __init__(
        self,
        config: TradingConfig,
        store: MemoryStore,
        on_close_callback=None,
    ) -> None:
        self._config = config
        self._store = store
        self._on_close = on_close_callback  # async func(text: str) — Telegram bildirimi
        self._positions: Dict[str, VirtualPosition] = {}
        self._running = False

    # ── Public API ────────────────────────────────────────────────────

    async def track(self, signal: Signal, signal_id: int) -> None:
        """Yeni sanal pozisyon açar."""
        pos = VirtualPosition(
            signal_id=signal_id,
            symbol=signal.symbol,
            side=signal.side,
            entry_price=signal.entry_price,
            tp_price=signal.tp_price,
            sl_price=signal.sl_price,
        )
        self._positions[signal.symbol] = pos
        logger.info(
            "virtual_position_opened",
            symbol=signal.symbol,
            side=signal.side,
            entry=signal.entry_price,
        )

    async def run(self) -> None:
        """
        Ana kontrol döngüsü.
        config.trade_control_seconds aralığıyla tüm pozisyonları kontrol eder.
        """
        self._running = True
        logger.info("position_watcher_started")

        while self._running:
            try:
                await self._check_all_positions()
            except Exception as e:
                logger.error(
                    "position_check_error",
                    error=str(e),
                    error_type=type(e).__name__,
                )
            await asyncio.sleep(self._config.trade_control_seconds)

    async def stop(self) -> None:
        """Döngüyü durdurur."""
        self._running = False
        logger.info("position_watcher_stopped", open_positions=len(self._positions))

    @property
    def tracked_symbols(self) -> set[str]:
        """Şu an takip edilen sembollerin kümesi."""
        return set(self._positions.keys())

    # ── Kontrol Mantığı ───────────────────────────────────────────────

    async def _check_all_positions(self) -> None:
        """Tüm sanal pozisyonları mevcut fiyatla karşılaştırır."""
        if not self._positions:
            return

        for symbol in list(self._positions.keys()):
            pos = self._positions.get(symbol)
            if pos is None:
                continue

            price = await self._store.get_price(symbol)
            if price is None:
                continue

            close_reason: str | None = None

            # ── TP Kontrolü ───────────────────────────────────────────
            if pos.side == "LONG" and price >= pos.tp_price:
                close_reason = "TP"
            elif pos.side == "SHORT" and price <= pos.tp_price:
                close_reason = "TP"

            # ── SL Kontrolü ───────────────────────────────────────────
            elif pos.side == "LONG" and price <= pos.sl_price:
                close_reason = "SL"
            elif pos.side == "SHORT" and price >= pos.sl_price:
                close_reason = "SL"

            # ── Zaman Stopu ───────────────────────────────────────────
            else:
                elapsed_hours = (
                    datetime.now(timezone.utc) - pos.opened_at
                ).total_seconds() / 3600
                if elapsed_hours >= self._config.time_stop_hours:
                    close_reason = "TIMEOUT"

            if close_reason:
                await self._close_position(pos, price, close_reason)

    async def _close_position(
        self, pos: VirtualPosition, close_price: float, reason: str
    ) -> None:
        """Sanal pozisyonu kapatır → DB + Telegram."""
        # PnL hesaplama (yüzde)
        if pos.side == "LONG":
            pnl_pct = ((close_price - pos.entry_price) / pos.entry_price) * 100
        else:
            pnl_pct = ((pos.entry_price - close_price) / pos.entry_price) * 100

        # Pozisyonu sil
        self._positions.pop(pos.symbol, None)

        # DB'ye kaydet
        try:
            async with get_session() as session:
                trade = TradeRecord(
                    signal_id=pos.signal_id,
                    close_reason=reason,
                    close_price=close_price,
                    pnl_percent=round(pnl_pct, 4),
                )
                session.add(trade)
                await session.commit()
        except Exception as e:
            logger.error("trade_save_failed", error=str(e), symbol=pos.symbol)

        # Telegram bildirimi
        icon = {"TP": "✅ TP", "SL": "❌ SL", "TIMEOUT": "⏱ TIMEOUT"}.get(reason, reason)
        pnl_icon = "🟢" if pnl_pct >= 0 else "🔴"
        msg = (
            f"{icon} | <b>{pos.symbol}</b> Kapatıldı\n"
            f"📍 Giriş: {pos.entry_price} → Çıkış: {close_price}\n"
            f"{pnl_icon} PnL: {pnl_pct:+.2f}%"
        )

        if self._on_close:
            try:
                await self._on_close(msg)
            except Exception as e:
                logger.error("close_notification_failed", error=str(e))

        logger.info(
            "virtual_position_closed",
            symbol=pos.symbol,
            reason=reason,
            pnl_percent=round(pnl_pct, 4),
        )
