"""
trading_bot.strategies.volatility_ema_strategy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
file.py içerisindeki strateji mantığının, yüksek performanslı NumPy ve 
yeni dinamik mimari (Plug & Play) ile yeniden yazılmış versiyonu.
"""

from __future__ import annotations
import numpy as np
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from strategies.base_strategy import BaseStrategy, Signal
from core.logger import get_logger

if TYPE_CHECKING:
    from core.config import TradingConfig
    from data.memory_store import MemoryStore

logger = get_logger(__name__)

# MemoryStore NumPy sütun indeksleri
TS, OPEN, HIGH, LOW, CLOSE, VOLUME = 0, 1, 2, 3, 4, 5

def _ema_numpy(data: np.ndarray, span: int) -> np.ndarray:
    """
    NumPy tabanlı Üssel Hareketli Ortalama (EMA) hesaplama.
    Pandas ewm(span=N, adjust=False) ile tam uyumludur.
    """
    alpha = 2.0 / (span + 1)
    ema = np.zeros_like(data)
    ema[0] = data[0]
    for i in range(1, len(data)):
        ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
    return ema

def _atr_numpy(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """
    NumPy tabanlı Average True Range (ATR) hesaplama.
    Wilder's Smoothing Method kullanılır.
    """
    tr = np.zeros_like(close)
    tr[0] = high[0] - low[0]
    tr[1:] = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1])
        )
    )
    
    atr = np.zeros_like(close)
    if len(tr) >= period:
        atr[period-1] = np.mean(tr[:period])
        for i in range(period, len(close)):
            atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
    return atr

class VolatilityEmaStrategy(BaseStrategy):
    """
    EMA Kesişimi ve Hacim Patlaması Stratejisi.
    Geliştirilmiş ATR tabanlı Risk Yönetimi ve Hacim Filtresi.
    """
    
    REQUIRED_TIMEFRAMES = ["15m"]

    def __init__(self, config: TradingConfig, store: MemoryStore) -> None:
        super().__init__(config, store)
        # Varsayılan Parametreler (Dinamik Konfigürasyon)
        self.ema_fast_len = getattr(config, 'ema_fast', 9)
        self.ema_slow_len = getattr(config, 'ema_slow', 21)
        self.volume_ma_len = getattr(config, 'volume_ma', 20)
        self.min_spike = getattr(config, 'min_spike', 4.0)
        self.max_spike = getattr(config, 'max_spike', 12.0)
        self.rr_ratio = getattr(config, 'rr_ratio', 1.5)

    async def evaluate(self, symbol: str) -> Optional[Signal]:
        """
        Sembol için strateji kurallarını değerlendirir.
        Giriş: 15m Grafik
        Filtre: 4.0 <= Spike <= 12.0
        Stop-Loss: 1.5 * ATR
        """
        try:
            # 1. Veri Çekme
            candles = await self._store.get_candles(symbol, "15m")
            if len(candles) < max(self.ema_slow_len, self.volume_ma_len, 15) + 2:
                return None

            # Sütunları ayır
            close = candles[:, CLOSE]
            high = candles[:, HIGH]
            low = candles[:, LOW]
            volume = candles[:, VOLUME]

            # 2. İndikatör Hesaplamaları
            ema_f = _ema_numpy(close, self.ema_fast_len)
            ema_s = _ema_numpy(close, self.ema_slow_len)
            atr = _atr_numpy(high, low, close, 14)
            
            # Hacim Ortalaması ve Spike Oranı
            avg_vol = np.mean(volume[-self.volume_ma_len-1:-1])
            current_vol = volume[-1]
            spike_ratio = current_vol / avg_vol if avg_vol > 0 else 0

            # 3. Sinyal Koşulları
            side = None
            
            # Yeni Hacim Filtresi: Sweet Spot (4.0 - 12.0)
            if self.min_spike <= spike_ratio <= self.max_spike:
                # LONG Koşulu: Fast > Slow Kesişimi
                if ema_f[-1] > ema_s[-1] and ema_f[-2] <= ema_s[-2]:
                    side = "LONG"
                
                # SHORT Koşulu: Fast < Slow Kesişimi
                elif ema_f[-1] < ema_s[-1] and ema_f[-2] >= ema_s[-2]:
                    side = "SHORT"

            if not side:
                return None

            # 4. Giriş Fiyatı ve ATR Tabanlı Risk Yönetimi
            live_price = await self._store.get_price(symbol)
            entry_price = float(live_price) if live_price is not None else float(close[-1])
            
            atr_value = atr[-1]
            if atr_value <= 0:
                return None

            if side == "LONG":
                # Stop loss: Entry - 1.5 * ATR
                sl = entry_price - (1.5 * atr_value)
                risk = entry_price - sl
                tp = entry_price + (risk * self.rr_ratio)
            else:
                # Stop loss: Entry + 1.5 * ATR
                sl = entry_price + (1.5 * atr_value)
                risk = sl - entry_price
                tp = entry_price - (risk * self.rr_ratio)

            # 5. Sinyal Objesini Döndür
            return Signal(
                symbol=symbol,
                side=side,
                entry_price=round(entry_price, 6),
                sl_price=round(sl, 6),
                tp_price=round(tp, 6),
                spike_ratio=round(float(spike_ratio), 4),
                ema_fast_value=round(float(ema_f[-1]), 6),
                ema_slow_value=round(float(ema_s[-1]), 6),
                current_volume=round(float(current_vol), 2),
                avg_volume=round(float(avg_vol), 2),
                timestamp=datetime.now(timezone.utc)
            )

        except Exception as e:
            logger.error(f"⚠️ {symbol} Strateji hatası: {str(e)}")
            return None
