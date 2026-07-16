from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AccountKind(StrEnum):
    asset = "asset"
    liability = "liability"


class SnapshotSource(StrEnum):
    manual = "manual"
    guided_manual = "guided_manual"
    imported_csv = "imported_csv"
    plugin_api = "plugin_api"
    plugin_browser_automation = "plugin_browser_automation"


def now_utc() -> datetime:
    return datetime.now(UTC)


class Household(Base):
    __tablename__ = "households"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )

    accounts: Mapped[list["Account"]] = relationship(back_populates="household")


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    institution_name: Mapped[str | None] = mapped_column(String(200))
    account_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    liquidity_class: Mapped[str] = mapped_column(String(80), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )

    household: Mapped[Household] = relationship(back_populates="accounts")
    snapshots: Mapped[list["BalanceSnapshot"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_accounts_household_id", "household_id"),)


class BalanceSnapshot(Base):
    __tablename__ = "balance_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    source: Mapped[str] = mapped_column(String(64), nullable=False, default=SnapshotSource.manual)
    confidence_level: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    account: Mapped[Account] = relationship(back_populates="snapshots")

    __table_args__ = (
        UniqueConstraint("account_id", "as_of_date", name="uq_balance_snapshots_account_date"),
        Index("ix_balance_snapshots_household_date", "household_id", "as_of_date"),
        Index("ix_balance_snapshots_account_date", "account_id", "as_of_date"),
    )
