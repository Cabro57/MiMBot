"""
trading_bot.strategies.rsi_macd_strategy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
RSI Aşırı Alım/Satım + MACD Kesişim Stratejisi
Pandas kullanılmadan, %100 NumPy vektörel operasyonları ile yazılmıştır.
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
    """NumPy ile Exponential Moving Average hesaplar."""
    alpha = 2.0 / (span + 1)
    ema = np.empty_like(data)
    ema[0] = data[0]
    for i in range(1, len(data)):
        ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
    return ema


def _macd_numpy(data: np.ndarray, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> tuple[np.ndarray, np.ndarray]:
    """NumPy ile MACD Line ve Signal Line hesaplar."""
    ema_fast = _ema_numpy(data, fast_period)
    ema_slow = _ema_numpy(data, slow_period)
    macd_line = ema_fast - ema_slow
    signal_line = _ema_numpy(macd_line, signal_period)
    return macd_line, signal_line


def _rsi_numpy(data: np.ndarray, period: int = 14) -> np.ndarray:
    """NumPy ile RSI hesaplar (Wilder's Smoothing)."""
    deltas = np.diff(data)
    seed = deltas[:period]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down != 0 else 0
    
    rsi = np.zeros_like(data)
    rsi[:period] = 100.0 - 100.0 / (1.0 + rs)

    for i in range(period, len(data)):
        delta = deltas[i - 1]
        if delta > 0:
            upval = delta
            downval = 0.0
        else:
            upval = 0.0
            downval = -delta

        up = (up * (period - 1) + upval) / period
        down = (down * (period - 1) + downval) / period
        rs = up / down if down != 0 else 0
        rsi[i] = 100.0 - 100.0 / (1.0 + rs)
        
    return rsi


class RsiMacdStrategy(BaseStrategy):
    """
    RSI ve MACD kesişimini kullanan Dinamik Zaman Dilimli Ticaret Stratejisi.
    Sinyal koşulları:
      LONG  → RSI(14) < 30 AND MACD, Sinyal çizgisini yukarı keserse
      SHORT → RSI(14) > 70 AND MACD, Sinyal çizgisini aşağı keserse
    """

    # Sadece 15 dakikalık zaman dilimi gerektirir
    REQUIRED_TIMEFRAMES: list[str] = ["15m"]

    def __init__(
        self, 
        config: TradingConfig, 
        store: MemoryStore,
        rsi_period: int = 14,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        rr_ratio: float = 2.0
    ) -> None:
        super().__init__(config, store)
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.rr_ratio = rr_ratio

    async def evaluate(self, symbol: str) -> Signal | None:
        """
        Belirtilen sembol için strateji kurallarını değerlendirir ve 
        varsa Signal nesnesi döndürür.
        """
        # ── Veri Çekme ────────────────────────────────────────────────
        candles_15m = await self._store.get_candles(symbol, "15m")

        # Yeterli veri kontrolü (En yavaş indikatör MACD Slow Period)
        min_length = max(self.macd_slow, self.rsi_period) + 10
        if len(candles_15m) < min_length:
            return None

        close_15m = candles_15m[:, CLOSE]
        high_15m = candles_15m[:, HIGH]
        low_15m = candles_15m[:, LOW]
        volume_15m = candles_15m[:, VOLUME]

        # ── İndikatör Hesaplamaları ───────────────────────────────────
        rsi = _rsi_numpy(close_15m, self.rsi_period)
        macd_line, signal_line = _macd_numpy(
            close_15m, self.macd_fast, self.macd_slow, self.macd_signal
        )

        last_rsi = float(rsi[-1])
        
        # Kesişim kontrolü için son iki mumun MACD ve Sinyal değerleri
        prev_macd = float(macd_line[-2])
        prev_signal = float(signal_line[-2])
        curr_macd = float(macd_line[-1])
        curr_signal = float(signal_line[-1])

        # ── Yön Belirleme ─────────────────────────────────────────────
        side: str | None = None
        
        # LONG: RSI 30 altı VE MACD sinyali yukarı kesti
        if last_rsi < self.rsi_oversold and prev_macd < prev_signal and curr_macd > curr_signal:
            side = "LONG"
            
        # SHORT: RSI 70 üstü VE MACD sinyali aşağı kesti
        elif last_rsi > self.rsi_overbought and prev_macd > prev_signal and curr_macd < curr_signal:
            side = "SHORT"

        if side is None:
            return None

        # ── Canlı Fiyat ve Risk Yönetimi ──────────────────────────────
        live_price = await self._store.get_price(symbol)
        entry_price = float(live_price) if live_price is not None else float(close_15m[-1])

        # Son mumun High / Low değerlerine göre Stop Loss belirleme
        if side == "LONG":
            sl = float(low_15m[-1])
            # Güvenlik önlemi: Eğer anlık fiyat çok düştüyse SL entry'den büyük olamaz
            if sl >= entry_price:
                sl = entry_price * 0.998  
            risk = entry_price - sl
            tp = entry_price + (risk * self.rr_ratio)
        else:
            sl = float(high_15m[-1])
            if sl <= entry_price:
                sl = entry_price * 1.002
            risk = sl - entry_price
            tp = entry_price - (risk * self.rr_ratio)

        # ── Sinyal Üretimi (Base Signal Yapısına Uygun) ───────────────
        current_vol = float(volume_15m[-1])
        avg_vol_10 = float(np.mean(volume_15m[-11:-1])) if len(volume_15m) >= 11 else 0.0
        spike_ratio = current_vol / avg_vol_10 if avg_vol_10 > 0 else 0.0

        signal = Signal(
            symbol=symbol,
            side=side,
            entry_price=round(entry_price, 6),
            sl_price=round(sl, 6),
            tp_price=round(tp, 6),
            spike_ratio=round(spike_ratio, 4),
            ema_fast_value=round(curr_macd, 6),    # Referans modeli korumak için MACD map edildi
            ema_slow_value=round(curr_signal, 6),  # Referans modeli korumak için Signal map edildi
            current_volume=round(current_vol, 2),
            avg_volume=round(avg_vol_10, 2),
            timestamp=datetime.now(timezone.utc),
        )

        logger.info(
            "rsi_macd_signal_generated",
            symbol=symbol,
            side=side,
            entry=signal.entry_price,
            rsi=round(last_rsi, 2)
        )
        return signal