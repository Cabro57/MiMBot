"""
trading_bot.models.db_models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
SQLAlchemy ORM modelleri: Signals, Trades, Market_Snapshots.
Backtest ve performans analizi için ilişkisel tablo yapısı.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    """Tüm ORM modellerinin türetileceği temel sınıf."""
    pass


class SignalRecord(Base):
    """
    Üretilen her sinyal kaydı.
    Sembol, yön, giriş fiyatı, TP/SL ve üretilme anı.
    """
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)          # "LONG" | "SHORT"
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    tp_price: Mapped[float] = mapped_column(Float, nullable=False)
    sl_price: Mapped[float] = mapped_column(Float, nullable=False)
    spike_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── İlişkiler ─────────────────────────────────────────────────────
    trade: Mapped[Optional["TradeRecord"]] = relationship(
        back_populates="signal", uselist=False, cascade="all, delete-orphan"
    )
    snapshot: Mapped[Optional["MarketSnapshot"]] = relationship(
        back_populates="signal", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Signal {self.symbol} {self.side} @ {self.entry_price}>"


class TradeRecord(Base):
    """
    Sanal pozisyon kapanış kaydı.
    Sinyalle 1:1 ilişkili — kapanış nedeni, gerçekleşen PnL.
    """
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("signals.id"), nullable=False, unique=True
    )
    close_reason: Mapped[str] = mapped_column(String(16), nullable=False)  # "TP" | "SL" | "TIMEOUT"
    close_price: Mapped[float] = mapped_column(Float, nullable=False)
    pnl_percent: Mapped[float] = mapped_column(Float, nullable=False)      # yüzde bazında kâr/zarar
    closed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── İlişki ────────────────────────────────────────────────────────
    signal: Mapped["SignalRecord"] = relationship(back_populates="trade")

    def __repr__(self) -> str:
        return f"<Trade signal={self.signal_id} {self.close_reason} PnL={self.pnl_percent:.2f}%>"


class MarketSnapshot(Base):
    """
    Sinyal anındaki piyasa kesiti.
    Hesaplanmış indikatör değerleri ve OHLCV verisi (JSON).
    """
    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("signals.id"), nullable=False, unique=True
    )
    ema_fast_value: Mapped[float] = mapped_column(Float, nullable=False)
    ema_slow_value: Mapped[float] = mapped_column(Float, nullable=False)
    current_volume: Mapped[float] = mapped_column(Float, nullable=False)
    avg_volume: Mapped[float] = mapped_column(Float, nullable=False)
    candle_data_json: Mapped[str] = mapped_column(Text, nullable=True)  # Son N mumun JSON hali

    # ── İlişki ────────────────────────────────────────────────────────
    signal: Mapped["SignalRecord"] = relationship(back_populates="snapshot")

    def __repr__(self) -> str:
        return f"<Snapshot signal={self.signal_id} ema_f={self.ema_fast_value:.4f}>"
