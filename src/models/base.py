"""SQLAlchemy declarative base and shared mixins."""

# stdlib
import logging
from datetime import datetime

# third-party
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


class TimestampMixin:
    """Mixin that adds created_at and updated_at columns to a model."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
