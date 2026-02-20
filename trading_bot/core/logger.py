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
    """Loglama altyapısını bir kez yapılandırır. İkinci çağrıda hiçbir şey yapmaz."""
    global _configured
    if _configured:
        return
    _configured = True

    level = getattr(logging, log_level.upper(), logging.INFO)

    # ── stdlib handler'ları ────────────────────────────────────────────
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        log_path = Path(log_file)
        handlers.append(logging.FileHandler(str(log_path), encoding="utf-8"))

    logging.basicConfig(
        format="%(message)s",
        level=level,
        handlers=handlers,
        force=True,
    )

    # ── structlog yapılandırması ───────────────────────────────────────
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Modül bazlı logger üretir.

    Kullanım:
        from trading_bot.core.logger import get_logger
        logger = get_logger(__name__)
        logger.info("mesaj", extra_key="değer")
    """
    return structlog.get_logger(name)
