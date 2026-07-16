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


class AccountEventType(StrEnum):
    contribution = "contribution"
    withdrawal = "withdrawal"
    transfer = "transfer"
    large_purchase = "large_purchase"
    asset_sale = "asset_sale"
    gift = "gift"
    inheritance = "inheritance"
    tax_payment = "tax_payment"
    account_added = "account_added"
    account_removed = "account_removed"
    manual_projection_adjustment = "manual_projection_adjustment"


class ProjectionBehavior(StrEnum):
    historical_only = "historical_only"
    projection_only = "projection_only"
    historical_and_projection = "historical_and_projection"


class IncomeFrequency(StrEnum):
    weekly = "weekly"
    biweekly = "biweekly"
    semimonthly = "semimonthly"
    monthly = "monthly"
    quarterly = "quarterly"
    annually = "annually"


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
    income_sources: Mapped[list["IncomeSource"]] = relationship(
        back_populates="household", cascade="all, delete-orphan"
    )
    annual_tax_records: Mapped[list["AnnualTaxRecord"]] = relationship(
        back_populates="household", cascade="all, delete-orphan"
    )


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
    events: Mapped[list["AccountEvent"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    real_estate_property: Mapped["RealEstateProperty | None"] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    mortgage_profile: Mapped["MortgageProfile | None"] = relationship(
        back_populates="liability_account",
        cascade="all, delete-orphan",
        foreign_keys="MortgageProfile.liability_account_id",
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


class AccountEvent(Base):
    __tablename__ = "account_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    projection_behavior: Mapped[str] = mapped_column(
        String(64), nullable=False, default=ProjectionBehavior.historical_only
    )
    scenario_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )

    account: Mapped[Account] = relationship(back_populates="events")

    __table_args__ = (
        Index("ix_account_events_household_date", "household_id", "event_date"),
        Index("ix_account_events_account_date", "account_id", "event_date"),
    )


class RealEstateProperty(Base):
    __tablename__ = "real_estate_properties"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    property_type: Mapped[str] = mapped_column(String(64), nullable=False, default="residence")
    purchase_date: Mapped[date | None] = mapped_column(Date)
    purchase_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    down_payment: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    expected_appreciation_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    property_tax_annual: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    insurance_annual: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    maintenance_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    hoa_monthly: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )

    account: Mapped[Account] = relationship(back_populates="real_estate_property")

    __table_args__ = (
        UniqueConstraint("account_id", name="uq_real_estate_properties_account"),
        Index("ix_real_estate_properties_household_id", "household_id"),
    )


class MortgageProfile(Base):
    __tablename__ = "mortgage_profiles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    liability_account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    property_account_id: Mapped[UUID | None] = mapped_column(ForeignKey("accounts.id"))
    original_principal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    term_months: Mapped[int] = mapped_column(nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    monthly_payment: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    rate_type: Mapped[str] = mapped_column(String(32), nullable=False, default="fixed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )

    liability_account: Mapped[Account] = relationship(
        back_populates="mortgage_profile", foreign_keys=[liability_account_id]
    )
    property_account: Mapped[Account | None] = relationship(foreign_keys=[property_account_id])

    __table_args__ = (
        UniqueConstraint("liability_account_id", name="uq_mortgage_profiles_liability_account"),
        Index("ix_mortgage_profiles_household_id", "household_id"),
        Index("ix_mortgage_profiles_property_account_id", "property_account_id"),
    )


class IncomeSource(Base):
    __tablename__ = "income_sources"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    income_type: Mapped[str] = mapped_column(String(80), nullable=False, default="other")
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    frequency: Mapped[str] = mapped_column(String(32), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    growth_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )

    household: Mapped[Household] = relationship(back_populates="income_sources")

    __table_args__ = (Index("ix_income_sources_household_id", "household_id"),)


class AnnualTaxRecord(Base):
    __tablename__ = "annual_tax_records"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    tax_year: Mapped[int] = mapped_column(nullable=False)
    gross_income: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    total_taxes_paid: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    refund_or_amount_due: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    notes: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )

    household: Mapped[Household] = relationship(back_populates="annual_tax_records")

    @property
    def effective_tax_rate(self) -> Decimal | None:
        if self.gross_income is None or self.gross_income == Decimal("0.00"):
            return None
        return self.total_taxes_paid / self.gross_income

    __table_args__ = (
        UniqueConstraint("household_id", "tax_year", name="uq_annual_tax_records_household_year"),
        Index("ix_annual_tax_records_household_id", "household_id"),
    )
