"""
trading_bot.strategies.base_strategy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Soyut strateji arayüzü ve sinyal veri yapısı.
Tüm somut stratejiler bu sınıftan türetilir.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config import TradingConfig
    from data.memory_store import MemoryStore


@dataclass(frozen=True)
class Signal:
    """Strateji modülünün ürettiği alım-satım sinyali."""
    symbol: str
    side: str                # "LONG" | "SHORT"
    entry_price: float
    sl_price: float
    tp_price: float
    spike_ratio: float
    ema_fast_value: float
    ema_slow_value: float
    current_volume: float
    avg_volume: float
    timestamp: datetime


class BaseStrategy(ABC):
    """
    Soyut strateji tabanı.

    Her somut strateji:
      1. __init__ içinde config ve store referansını alır.
      2. evaluate() metodunu implemente eder.
      3. Signal | None döndürür.

    MemoryStore'dan NumPy dizisi alıp hesaplama yapar;
    REST API çağrısı YAPMAZ.
    """

    REQUIRED_TIMEFRAMES: list[str] = []

    def __init__(self, config: TradingConfig, store: MemoryStore) -> None:
        self._config = config
        self._store = store

    @abstractmethod
    async def evaluate(self, symbol: str) -> Signal | None:
        """
        Belirtilen sembol için strateji kurallarını değerlendirir.

        Returns:
            Signal nesnesi (sinyal varsa) veya None (sinyal yoksa).
        """
        ...
