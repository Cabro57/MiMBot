"""
trading_bot.core.config
~~~~~~~~~~~~~~~~~~~~~~~~
.env tabanlı dinamik yapılandırma modülü.
Tüm strateji ve sistem parametreleri burada merkezi olarak tanımlanır.
API Key gerektirmez — sadece Telegram bilgileri .env'den okunur.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

# Proje kök dizinindeki .env dosyasını yükle
_env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_env_path, override=False)


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int = 0) -> int:
    return int(os.environ.get(key, default))


def _env_float(key: str, default: float = 0.0) -> float:
    return float(os.environ.get(key, default))


@dataclass(frozen=True)
class TradingConfig:
    """Tüm bot parametrelerini tek noktadan yöneten immutable yapılandırma."""

    # ── Telegram ──────────────────────────────────────────────────────
    telegram_bot_token: str = field(default_factory=lambda: _env("TELEGRAM_BOT_TOKEN"))
    telegram_chat_id: str = field(default_factory=lambda: _env("TELEGRAM_CHAT_ID"))

    # ── Market Tarama ─────────────────────────────────────────────────
    top_volume_limit: int = field(default_factory=lambda: _env_int("TOP_VOLUME_LIMIT", 100))
    market_refresh_hours: int = field(default_factory=lambda: _env_int("MARKET_REFRESH_HOURS", 1))

    # ── Zamanlama ─────────────────────────────────────────────────────
    scan_interval_seconds: int = field(default_factory=lambda: _env_int("SCAN_INTERVAL_SECONDS", 300))
    trade_control_seconds: int = field(default_factory=lambda: _env_int("TRADE_CONTROL_SECONDS", 10))

    # ── EMA Strateji Parametreleri ────────────────────────────────────
    ema_fast: int = field(default_factory=lambda: _env_int("EMA_FAST", 9))
    ema_slow: int = field(default_factory=lambda: _env_int("EMA_SLOW", 21))

    # ── Hacim Filtresi ────────────────────────────────────────────────
    volume_spike_min: float = field(default_factory=lambda: _env_float("VOLUME_SPIKE_MIN", 2.5))
    volume_spike_max: float = field(default_factory=lambda: _env_float("VOLUME_SPIKE_MAX", 6.0))
    breakout_range_period: int = field(default_factory=lambda: _env_int("BREAKOUT_RANGE_PERIOD", 5))

    # ── Risk Yönetimi (Sanal TP/SL) ───────────────────────────────────
    rr_ratio: float = field(default_factory=lambda: _env_float("RR_RATIO", 1.4))
    max_stop_percent: float = field(default_factory=lambda: _env_float("MAX_STOP_PERCENT", 0.025))
    stop_offset: float = field(default_factory=lambda: _env_float("STOP_OFFSET", 0.0005))
    time_stop_hours: int = field(default_factory=lambda: _env_int("TIME_STOP_HOURS", 4))
    cooldown_minutes: int = field(default_factory=lambda: _env_int("COOLDOWN_MINUTES", 30))

    # ── Sistem ────────────────────────────────────────────────────────
    active_strategy: str = field(default_factory=lambda: _env("ACTIVE_STRATEGY", "ema_volume_strategy.EmaVolumeStrategy"))
    max_parallel_tasks: int = field(default_factory=lambda: _env_int("MAX_PARALLEL_TASKS", 15))
    db_url: str = field(default_factory=lambda: _env("DB_URL", "sqlite+aiosqlite:///trading_bot.db"))
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO"))
    max_tracked_signals: int = field(default_factory=lambda: _env_int("MAX_TRACKED_SIGNALS", 3))

    # ── WebSocket ─────────────────────────────────────────────────────
    ws_kline_timeframes: list[str] = field(default_factory=lambda: ["1m", "5m"])
    ws_reconnect_delay: int = field(default_factory=lambda: _env_int("WS_RECONNECT_DELAY", 5))
