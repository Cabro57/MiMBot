"""
trading_bot.core.logger
~~~~~~~~~~~~~~~~~~~~~~~~
structlog tabanlı yapılandırılmış (structured) loglama sistemi.
JSON formatında konsol + dosya çıktısı üretir.
Tüm modüller bu fabrika fonksiyonunu kullanır.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog


_configured = False


def setup_logging(log_level: str = "INFO", log_file: str | None = "trading_bot.log") -> None:
    """Loglama altyapısını yapılandırır: Konsol (Renkli/Okunabilir), Dosya (JSON)."""
    global _configured
    if _configured:
        return
    _configured = True

    level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # ── ProcessorFormatter ile farklı çıktı formatları ───────────────────
    
    # 1. Konsol için renklendirilmiş çıktı
    console_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(colors=True),
        ],
    )

    # 2. Dosya için JSON çıktı
    file_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
    )

    # ── Handler Yapılandırması ──────────────────────────────────────────
    handlers: list[logging.Handler] = []

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    handlers.append(console_handler)

    if log_file:
        file_handler = logging.FileHandler(str(Path(log_file)), encoding="utf-8")
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)

    # Root logger yapılandırması
    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True,
    )

    # ── Structlog'u stdlib ile konuştur ────────────────────────────────
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Diğer kütüphanelerin loglarını sessize al (isteğe bağlı)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Modül bazlı logger üretir."""
    return structlog.get_logger(name)
