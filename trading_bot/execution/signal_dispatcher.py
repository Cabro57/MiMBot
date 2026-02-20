"""
trading_bot.execution.signal_dispatcher
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Sinyal iletim ve kayıt modülü.
Gerçek emir GÖNDERMEZ — sadece:
  1. Telegram'a sinyal bildirimi gönderir
  2. Sinyali veritabanına (SignalRecord + MarketSnapshot) kaydeder
  3. Sinyali PositionWatcher'a sanal takip için aktarır
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from telegram import Bot
from telegram.constants import ParseMode

from trading_bot.core.database import get_session
from trading_bot.core.logger import get_logger
from trading_bot.models.db_models import MarketSnapshot, SignalRecord

if TYPE_CHECKING:
    from trading_bot.core.config import TradingConfig
    from trading_bot.execution.position_watcher import PositionWatcher
    from trading_bot.strategies.base_strategy import Signal

logger = get_logger(__name__)


class SignalDispatcher:
    """
    Üretilen sinyalleri yönlendirir:
      Strateji → Telegram + DB + PositionWatcher

    Gerçek borsaya emir göndermez.
    """

    def __init__(
        self,
        config: TradingConfig,
        position_watcher: PositionWatcher,
    ) -> None:
        self._config = config
        self._watcher = position_watcher
        self._telegram = Bot(token=config.telegram_bot_token)

    # ── Ana Dağıtım Metodu ────────────────────────────────────────────

    async def dispatch(self, signal: Signal) -> None:
        """
        Tek bir sinyali işler:
          1. DB'ye yaz (SignalRecord + MarketSnapshot)
          2. Telegram'a gönder
          3. PositionWatcher'a aktar (sanal takip)
        """
        try:
            # 1. Veritabanına kaydet
            signal_id = await self._save_to_db(signal)

            # 2. Telegram bildirimi
            await self._send_telegram(signal)

            # 3. Sanal pozisyon takibine ekle
            await self._watcher.track(signal, signal_id)

            logger.info(
                "signal_dispatched",
                symbol=signal.symbol,
                side=signal.side,
                signal_id=signal_id,
            )

        except Exception as e:
            logger.error(
                "dispatch_failed",
                symbol=signal.symbol,
                error=str(e),
                error_type=type(e).__name__,
            )

    # ── Telegram ──────────────────────────────────────────────────────

    async def _send_telegram(self, signal: Signal) -> None:
        """HTML formatında sinyal mesajı gönderir."""
        try:
            msg = (
                f"🔔 <b>#{signal.symbol} {signal.side}</b>\n"
                f"📈 Giriş: {signal.entry_price}\n"
                f"🎯 TP: {signal.tp_price}\n"
                f"🛡️ SL: {signal.sl_price}\n"
                f"📊 Hacim Gücü: {signal.spike_ratio}x\n"
                f"⏱ {signal.timestamp.strftime('%H:%M:%S UTC')}"
            )
            await self._telegram.send_message(
                chat_id=self._config.telegram_chat_id,
                text=msg,
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.error("telegram_send_failed", error=str(e))

    async def send_notification(self, text: str) -> None:
        """Genel amaçlı Telegram bildirimi (başlangıç, kapanış vb.)."""
        try:
            await self._telegram.send_message(
                chat_id=self._config.telegram_chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.error("telegram_notification_failed", error=str(e))

    # ── Veritabanı ────────────────────────────────────────────────────

    async def _save_to_db(self, signal: Signal) -> int:
        """Sinyali ve piyasa anlık görüntüsünü veritabanına yazar."""
        async with get_session() as session:
            record = SignalRecord(
                symbol=signal.symbol,
                side=signal.side,
                entry_price=signal.entry_price,
                tp_price=signal.tp_price,
                sl_price=signal.sl_price,
                spike_ratio=signal.spike_ratio,
                created_at=signal.timestamp,
            )
            session.add(record)
            await session.flush()  # ID ataması için

            snapshot = MarketSnapshot(
                signal_id=record.id,
                ema_fast_value=signal.ema_fast_value,
                ema_slow_value=signal.ema_slow_value,
                current_volume=signal.current_volume,
                avg_volume=signal.avg_volume,
                candle_data_json=None,  # İsteğe bağlı — ileride eklenebilir
            )
            session.add(snapshot)
            await session.commit()

            logger.info("signal_saved", signal_id=record.id, symbol=signal.symbol)
            return record.id
