"""
trading_bot.strategies.loader
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Dinamik strateji yükleyici.
Config'de belirtilen strateji sınıfını importlib ile yükler.
Yeni strateji eklendiğinde main.py'de değişiklik yapmaya gerek kalmaz.
"""
from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from core.logger import get_logger
from strategies.base_strategy import BaseStrategy

if TYPE_CHECKING:
    from core.config import TradingConfig
    from data.memory_store import MemoryStore

logger = get_logger(__name__)


def load_strategy(config: 'TradingConfig', store: 'MemoryStore') -> BaseStrategy:
    """
    config.active_strategy değerini ayrıştırarak strateji sınıfını dinamik yükler.

    Format: "module_name.ClassName"
    Örnek: "ema_volume_strategy.EmaVolumeStrategy"
           → strategies.ema_volume_strategy modülünden EmaVolumeStrategy sınıfı

    Returns:
        Başlatılmış strateji nesnesi (BaseStrategy alt sınıfı).

    Raises:
        ValueError: Format hatalıysa.
        ImportError: Modül bulunamazsa.
        AttributeError: Sınıf bulunamazsa.
    """
    raw = config.active_strategy.strip()

    if "." not in raw:
        raise ValueError(
            f"active_strategy formatı hatalı: '{raw}'. "
            "Beklenen format: 'module_name.ClassName' (örn: 'ema_volume_strategy.EmaVolumeStrategy')"
        )

    module_name, class_name = raw.rsplit(".", 1)
    full_module = f"strategies.{module_name}"

    logger.info("strategy_loading", module=full_module, cls=class_name)

    module = importlib.import_module(full_module)
    strategy_cls = getattr(module, class_name)

    if not issubclass(strategy_cls, BaseStrategy):
        raise TypeError(
            f"{class_name} sınıfı BaseStrategy'den türetilmemiş."
        )

    instance = strategy_cls(config, store)

    logger.info(
        "strategy_loaded",
        name=class_name,
        timeframes=instance.REQUIRED_TIMEFRAMES,
    )
    return instance
