"""
trading_bot.data.memory_store
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Bellek içi OHLCV ring buffer.
WebSocket'ten gelen mumları sembol+timeframe bazında depolar.
Strateji modülü veriyi buradan NumPy dizisi olarak okur.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, Tuple

import numpy as np

from trading_bot.core.logger import get_logger

logger = get_logger(__name__)

# OHLCV sütun indeksleri (NumPy dizisinde)
TS, OPEN, HIGH, LOW, CLOSE, VOLUME = 0, 1, 2, 3, 4, 5
_COLUMNS = 6


@dataclass
class CandleBuffer:
    """Tek bir sembol+timeframe için sabit uzunluklu mum tamponu."""
    maxlen: int = 200
    _deque: deque = field(default_factory=lambda: deque(maxlen=200))

    def __post_init__(self) -> None:
        self._deque = deque(maxlen=self.maxlen)

    def append(self, candle: list[float]) -> None:
        """[timestamp, open, high, low, close, volume] formatında mum ekler."""
        self._deque.append(candle)

    def update_last(self, candle: list[float]) -> None:
        """Açık (henüz kapanmamış) mumu günceller — aynı timestamp ise üzerine yazar."""
        if self._deque and self._deque[-1][TS] == candle[TS]:
            self._deque[-1] = candle
        else:
            self._deque.append(candle)

    def to_numpy(self) -> np.ndarray:
        """Tamponu shape=(N, 6) NumPy dizisine çevirir."""
        if not self._deque:
            return np.empty((0, _COLUMNS), dtype=np.float64)
        return np.array(list(self._deque), dtype=np.float64)

    def __len__(self) -> int:
        return len(self._deque)


class MemoryStore:
    """
    Thread-safe bellek içi mum deposu.

    Kullanım:
        store = MemoryStore()
        store.update_candle("BTCUSDT", "1m", candle_list)
        arr = await store.get_candles("BTCUSDT", "1m")  # np.ndarray
    """

    def __init__(self, maxlen: int = 200) -> None:
        self._maxlen = maxlen
        self._lock = asyncio.Lock()
        # {("BTCUSDT","1m"): CandleBuffer, ...}
        self._buffers: Dict[Tuple[str, str], CandleBuffer] = defaultdict(
            lambda: CandleBuffer(maxlen=self._maxlen)
        )
        # Son mark/ticker fiyatları — position_watcher tarafından kullanılır
        self._last_prices: Dict[str, float] = {}

    # ── Mum Operasyonları ─────────────────────────────────────────────

    async def update_candle(
        self, symbol: str, timeframe: str, candle: list[float], *, is_closed: bool
    ) -> None:
        """
        WebSocket'ten gelen mumu depoya yazar.
        is_closed=True ise yeni mum olarak eklenir, False ise son mum güncellenir.
        """
        async with self._lock:
            buf = self._buffers[(symbol, timeframe)]
            if is_closed:
                buf.append(candle)
            else:
                buf.update_last(candle)

    async def get_candles(self, symbol: str, timeframe: str) -> np.ndarray:
        """Belirtilen sembol+timeframe için NumPy dizisi döndürür."""
        async with self._lock:
            return self._buffers[(symbol, timeframe)].to_numpy()

    async def get_candle_count(self, symbol: str, timeframe: str) -> int:
        """Depodaki mum sayısını döndürür."""
        async with self._lock:
            return len(self._buffers[(symbol, timeframe)])

    # ── Fiyat Operasyonları (Position Watcher İçin) ───────────────────

    async def update_price(self, symbol: str, price: float) -> None:
        """Mark price / ticker fiyatını günceller."""
        async with self._lock:
            self._last_prices[symbol] = price

    async def get_price(self, symbol: str) -> float | None:
        """Son bilinen fiyatı döndürür."""
        async with self._lock:
            return self._last_prices.get(symbol)

    async def get_all_prices(self) -> Dict[str, float]:
        """Tüm fiyatları döndürür."""
        async with self._lock:
            return dict(self._last_prices)

    # ── Yardımcılar ──────────────────────────────────────────────────

    async def get_available_symbols(self) -> list[str]:
        """En az 1 mumu olan sembolleri döndürür."""
        async with self._lock:
            symbols = set()
            for (sym, _tf), buf in self._buffers.items():
                if len(buf) > 0:
                    symbols.add(sym)
            return sorted(symbols)
