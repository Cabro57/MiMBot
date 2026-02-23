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

class VolatilityEmaStrategy(BaseStrategy):
    """
    EMA Kesişimi ve Hacim Patlaması Stratejisi.
    file.py'deki 'analyze_symbol_async' mantığını temel alır.
    """
    
    # Yeni mimari gereği dinamik zaman dilimleri
    REQUIRED_TIMEFRAMES = ["15m"]

    def __init__(self, config: TradingConfig, store: MemoryStore) -> None:
        super().__init__(config, store)
        # Varsayılan Parametreler (Plug & Play için)
        self.ema_fast_len = getattr(config, 'ema_fast', 9)
        self.ema_slow_len = getattr(config, 'ema_slow', 21)
        self.volume_ma_len = getattr(config, 'volume_ma', 20)
        self.volume_threshold = getattr(config, 'volume_threshold', 2.5)
        self.rr_ratio = getattr(config, 'rr_ratio', 1.5)
        self.max_stop_percent = getattr(config, 'max_stop_percent', 0.02)
        self.stop_offset = getattr(config, 'stop_offset', 0.001)

    async def evaluate(self, symbol: str) -> Optional[Signal]:
        """
        Sembol için strateji kurallarını değerlendirir.
        """
        try:
            # 1. Veri Çekme (Dinamik Zaman Dilimi)
            candles = await self._store.get_candles(symbol, "15m")
            if len(candles) < max(self.ema_slow_len, self.volume_ma_len) + 2:
                return None

            # Sütunları ayır
            close = candles[:, CLOSE]
            high = candles[:, HIGH]
            low = candles[:, LOW]
            volume = candles[:, VOLUME]

            # 2. İndikatör Hesaplamaları (Sadece NumPy)
            ema_f = _ema_numpy(close, self.ema_fast_len)
            ema_s = _ema_numpy(close, self.ema_slow_len)
            
            # Hacim Ortalaması ve Spike Oranı
            avg_vol = np.mean(volume[-self.volume_ma_len-1:-1])
            current_vol = volume[-1]
            spike_ratio = current_vol / avg_vol if avg_vol > 0 else 0

            # 3. Sinyal Koşulları (file.py mantığı)
            side = None
            
            # LONG Koşulu: Fast > Slow ve Hacim Patlaması
            if ema_f[-1] > ema_s[-1] and ema_f[-2] <= ema_s[-2]:
                if spike_ratio >= self.volume_threshold:
                    side = "LONG"
            
            # SHORT Koşulu: Fast < Slow ve Hacim Patlaması
            elif ema_f[-1] < ema_s[-1] and ema_f[-2] >= ema_s[-2]:
                if spike_ratio >= self.volume_threshold:
                    side = "SHORT"

            if not side:
                return None

            # 4. Giriş Fiyatı ve Risk Yönetimi (Live Price)
            live_price = await self._store.get_price(symbol)
            entry_price = float(live_price) if live_price is not None else float(close[-1])

            # TP/SL Hesaplama (Referans: ema_volume_strategy.py)
            r_high = np.max(high[-3:])
            r_low = np.min(low[-3:])

            if side == "LONG":
                # Stop loss: Son 3 mumun en düşüğü veya max_stop_percent
                sl = max(
                    r_low * (1 - self.stop_offset),
                    entry_price * (1 - self.max_stop_percent)
                )
                risk = entry_price - sl
                tp = entry_price + (risk * self.rr_ratio)
            else:
                # Stop loss: Son 3 mumun en yükseği veya max_stop_percent
                sl = min(
                    r_high * (1 + self.stop_offset),
                    entry_price * (1 + self.max_stop_percent)
                )
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