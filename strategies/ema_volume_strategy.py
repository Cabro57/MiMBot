"""
trading_bot.strategies.ema_volume_strategy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
EMA crossover + hacim patlaması stratejisi.
Mevcut file.py'deki analyze_symbol_async mantığının
NumPy vektörel operasyonlarla yeniden yazılmış hali.

Pandas kullaNILMAZ — tüm hesaplamalar NumPy ile yapılır.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import numpy as np

from core.logger import get_logger
from strategies.base_strategy import BaseStrategy, Signal

if TYPE_CHECKING:
    from core.config import TradingConfig
    from data.memory_store import MemoryStore

logger = get_logger(__name__)

# MemoryStore NumPy sütun indeksleri
TS, OPEN, HIGH, LOW, CLOSE, VOLUME = 0, 1, 2, 3, 4, 5


def _ema_numpy(data: np.ndarray, span: int) -> np.ndarray:
    """
    NumPy ile Exponential Moving Average hesaplama.
    Pandas ewm(span=N, adjust=False) ile aynı sonucu verir.

    Args:
        data: 1-D float64 dizisi (close fiyatları).
        span: EMA periyodu.

    Returns:
        Aynı uzunlukta EMA dizisi.
    """
    alpha = 2.0 / (span + 1)
    ema = np.empty_like(data)
    ema[0] = data[0]
    for i in range(1, len(data)):
        ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
    return ema


class EmaVolumeStrategy(BaseStrategy):
    """
    EMA + Hacim Kırılım Stratejisi.

    Sinyal koşulları (mevcut file.py mantığı korunmuştur):
      LONG  → close > r_high  AND  ema_fast > ema_slow  AND  spike_ratio filtre içinde
      SHORT → close < r_low   AND  ema_fast < ema_slow  AND  spike_ratio filtre içinde

    Tüm parametreler TradingConfig'den dinamik olarak okunur.
    """

    def __init__(self, config: TradingConfig, store: MemoryStore) -> None:
        super().__init__(config, store)

    async def evaluate(self, symbol: str) -> Signal | None:
        """
        1m ve 5m mumlarını MemoryStore'dan çeker,
        NumPy ile EMA ve hacim hesaplamalarını yapar,
        sinyal koşullarını değerlendirir.
        """
        cfg = self._config

        # ── Veri çekme ────────────────────────────────────────────────
        candles_1m = await self._store.get_candles(symbol, "1m")
        candles_5m = await self._store.get_candles(symbol, "5m")

        # Yeterli veri kontrolü
        min_1m = max(cfg.ema_slow + 10, 50)
        min_5m = cfg.breakout_range_period + 1

        if len(candles_1m) < min_1m or len(candles_5m) < min_5m:
            return None

        # ── 1m verisinden EMA hesaplama ───────────────────────────────
        close_1m = candles_1m[:, CLOSE]
        volume_1m = candles_1m[:, VOLUME]

        ema_fast = _ema_numpy(close_1m, cfg.ema_fast)
        ema_slow = _ema_numpy(close_1m, cfg.ema_slow)

        last_close = close_1m[-1]
        last_ema_f = ema_fast[-1]
        last_ema_s = ema_slow[-1]

        # ── 5m verisinden kırılım aralığı (range) ────────────────────
        # Son N mumun (kapanmış olanlar, son mum hariç) yüksek/düşüğü
        period = cfg.breakout_range_period
        range_slice = candles_5m[-(period + 1):-1]  # son N kapanmış 5m mum
        r_high = float(np.max(range_slice[:, HIGH]))
        r_low = float(np.min(range_slice[:, LOW]))

        # ── Hacim spike kontrolü ──────────────────────────────────────
        current_vol = float(volume_1m[-1])
        avg_vol_10 = float(np.mean(volume_1m[-11:-1])) if len(volume_1m) >= 11 else 0.0

        if avg_vol_10 <= 0:
            return None

        spike_ratio = current_vol / avg_vol_10

        if not (cfg.volume_spike_min <= spike_ratio <= cfg.volume_spike_max):
            return None

        # ── Yön belirleme ─────────────────────────────────────────────
        side: str | None = None
        if last_close > r_high and last_ema_f > last_ema_s:
            side = "LONG"
        elif last_close < r_low and last_ema_f < last_ema_s:
            side = "SHORT"

        if side is None:
            return None

        # ── TP / SL hesaplama ─────────────────────────────────────────
        if side == "LONG":
            sl = max(
                r_low * (1 - cfg.stop_offset),
                last_close * (1 - cfg.max_stop_percent),
            )
            tp = last_close + (last_close - sl) * cfg.rr_ratio
        else:
            sl = min(
                r_high * (1 + cfg.stop_offset),
                last_close * (1 + cfg.max_stop_percent),
            )
            tp = last_close - (sl - last_close) * cfg.rr_ratio

        # ── Sinyal üret ───────────────────────────────────────────────
        signal = Signal(
            symbol=symbol,
            side=side,
            entry_price=round(last_close, 6),
            sl_price=round(sl, 6),
            tp_price=round(tp, 6),
            spike_ratio=round(spike_ratio, 4),
            ema_fast_value=round(float(last_ema_f), 6),
            ema_slow_value=round(float(last_ema_s), 6),
            current_volume=round(current_vol, 2),
            avg_volume=round(avg_vol_10, 2),
            timestamp=datetime.now(timezone.utc),
        )

        logger.info(
            "signal_generated",
            symbol=symbol,
            side=side,
            entry=signal.entry_price,
            spike=signal.spike_ratio,
        )
        return signal
