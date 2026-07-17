from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    Account,
    AccountEvent,
    AccountEventType,
    AnnualTaxRecord,
    BalanceSnapshot,
    Household,
    IncomeFrequency,
    IncomeSource,
    MortgageProfile,
    ProjectionBehavior,
    RealEstateProperty,
    SnapshotSource,
)
from app.db.session import SessionLocal

DEMO_HOUSEHOLD_NAME = "Demo Household"


@dataclass
class DemoSeedSummary:
    household_id: str
    accounts_created: int = 0
    snapshots_created: int = 0
    events_created: int = 0
    properties_created: int = 0
    mortgages_created: int = 0
    income_sources_created: int = 0
    tax_records_created: int = 0
    reset: bool = False


def seed_demo_data(db: Session, *, reset: bool = False) -> DemoSeedSummary:
    if reset:
        _delete_demo_households(db)
        db.flush()

    household = _get_or_create_household(db, DEMO_HOUSEHOLD_NAME)
    summary = DemoSeedSummary(household_id=str(household.id), reset=reset)
    if household.created_at == household.updated_at:
        # This is only a hint for summary accounting. Existing rows are counted by the
        # specific helpers below, where idempotency matters most.
        pass

    accounts = {
        "checking": _get_or_create_account(
            db,
            summary,
            household_id=household.id,
            name="Checking",
            account_kind="asset",
            category="cash",
            liquidity_class="liquid",
            expected_annual_yield=Decimal("0.010000"),
            institution_name="Demo Bank",
        ),
        "brokerage": _get_or_create_account(
            db,
            summary,
            household_id=household.id,
            name="Brokerage",
            account_kind="asset",
            category="taxable_investment",
            liquidity_class="marketable",
            expected_annual_yield=Decimal("0.060000"),
            institution_name="Demo Brokerage",
        ),
        "retirement": _get_or_create_account(
            db,
            summary,
            household_id=household.id,
            name="401k",
            account_kind="asset",
            category="retirement",
            liquidity_class="retirement",
            expected_annual_yield=Decimal("0.065000"),
            institution_name="Demo 401k Provider",
        ),
        "home": _get_or_create_account(
            db,
            summary,
            household_id=household.id,
            name="Primary Residence",
            account_kind="asset",
            category="real_estate",
            liquidity_class="illiquid",
            expected_annual_yield=Decimal("0.035000"),
        ),
        "mortgage": _get_or_create_account(
            db,
            summary,
            household_id=household.id,
            name="Primary Residence Mortgage",
            account_kind="liability",
            category="mortgage",
            liquidity_class="debt",
            expected_annual_yield=Decimal("0.000000"),
            institution_name="Demo Mortgage Co",
        ),
        "credit_card": _get_or_create_account(
            db,
            summary,
            household_id=household.id,
            name="Credit Card",
            account_kind="liability",
            category="credit_card",
            liquidity_class="debt",
            expected_annual_yield=Decimal("0.000000"),
            institution_name="Demo Card",
        ),
    }

    _seed_snapshots(db, summary, household.id, accounts)
    _seed_real_estate(db, summary, household.id, accounts["home"])
    _seed_mortgage(db, summary, household.id, accounts["mortgage"], accounts["home"])
    _seed_income_sources(db, summary, household.id)
    _seed_tax_records(db, summary, household.id)
    _seed_events(db, summary, household.id, accounts)

    db.commit()
    return summary


def _delete_demo_households(db: Session) -> None:
    household_ids = list(
        db.scalars(select(Household.id).where(Household.name == DEMO_HOUSEHOLD_NAME)).all()
    )
    for household_id in household_ids:
        db.execute(delete(AccountEvent).where(AccountEvent.household_id == household_id))
        db.execute(delete(BalanceSnapshot).where(BalanceSnapshot.household_id == household_id))
        db.execute(delete(MortgageProfile).where(MortgageProfile.household_id == household_id))
        db.execute(delete(RealEstateProperty).where(RealEstateProperty.household_id == household_id))
        db.execute(delete(IncomeSource).where(IncomeSource.household_id == household_id))
        db.execute(delete(AnnualTaxRecord).where(AnnualTaxRecord.household_id == household_id))
        db.execute(delete(Account).where(Account.household_id == household_id))
        db.execute(delete(Household).where(Household.id == household_id))


def _get_or_create_household(db: Session, name: str) -> Household:
    household = db.scalars(select(Household).where(Household.name == name)).first()
    if household is not None:
        return household
    household = Household(name=name)
    db.add(household)
    db.flush()
    return household


def _get_or_create_account(
    db: Session,
    summary: DemoSeedSummary,
    *,
    household_id: UUID,
    name: str,
    account_kind: str,
    category: str,
    liquidity_class: str,
    expected_annual_yield: Decimal | None = None,
    institution_name: str | None = None,
) -> Account:
    account = db.scalars(
        select(Account).where(
            Account.household_id == household_id,
            Account.name == name,
            Account.account_kind == account_kind,
        )
    ).first()
    if account is not None:
        return account
    account = Account(
        household_id=household_id,
        name=name,
        institution_name=institution_name,
        account_kind=account_kind,
        category=category,
        liquidity_class=liquidity_class,
        expected_annual_yield=expected_annual_yield,
        currency="USD",
    )
    db.add(account)
    db.flush()
    summary.accounts_created += 1
    return account


def _seed_snapshots(
    db: Session,
    summary: DemoSeedSummary,
    household_id: UUID,
    accounts: dict[str, Account],
) -> None:
    rows = [
        ("checking", date(2024, 1, 1), "18500.00"),
        ("checking", date(2024, 12, 31), "23500.00"),
        ("checking", date(2025, 1, 1), "23500.00"),
        ("checking", date(2025, 12, 31), "28200.00"),
        ("checking", date(2026, 1, 31), "30100.00"),
        ("brokerage", date(2024, 1, 1), "142000.00"),
        ("brokerage", date(2024, 12, 31), "171500.00"),
        ("brokerage", date(2025, 1, 1), "171500.00"),
        ("brokerage", date(2025, 12, 31), "214000.00"),
        ("brokerage", date(2026, 1, 31), "219250.00"),
        ("retirement", date(2024, 1, 1), "310000.00"),
        ("retirement", date(2024, 12, 31), "356000.00"),
        ("retirement", date(2025, 1, 1), "356000.00"),
        ("retirement", date(2025, 12, 31), "413000.00"),
        ("retirement", date(2026, 1, 31), "421500.00"),
        ("home", date(2024, 1, 1), "705000.00"),
        ("home", date(2024, 12, 31), "731000.00"),
        ("home", date(2025, 1, 1), "731000.00"),
        ("home", date(2025, 12, 31), "760000.00"),
        ("home", date(2026, 1, 31), "762000.00"),
        ("mortgage", date(2024, 1, 1), "481000.00"),
        ("mortgage", date(2024, 12, 31), "468500.00"),
        ("mortgage", date(2025, 1, 1), "468500.00"),
        ("mortgage", date(2025, 12, 31), "454900.00"),
        ("mortgage", date(2026, 1, 31), "453700.00"),
        ("credit_card", date(2024, 1, 1), "4200.00"),
        ("credit_card", date(2024, 12, 31), "3100.00"),
        ("credit_card", date(2025, 1, 1), "3100.00"),
        ("credit_card", date(2025, 12, 31), "2400.00"),
        ("credit_card", date(2026, 1, 31), "1800.00"),
    ]
    for account_key, as_of_date, balance in rows:
        _create_snapshot_if_missing(
            db,
            summary,
            household_id=household_id,
            account=accounts[account_key],
            as_of_date=as_of_date,
            balance=Decimal(balance),
        )


def _create_snapshot_if_missing(
    db: Session,
    summary: DemoSeedSummary,
    *,
    household_id: UUID,
    account: Account,
    as_of_date: date,
    balance: Decimal,
) -> None:
    exists = db.scalars(
        select(BalanceSnapshot.id).where(
            BalanceSnapshot.account_id == account.id,
            BalanceSnapshot.as_of_date == as_of_date,
        )
    ).first()
    if exists is not None:
        return
    db.add(
        BalanceSnapshot(
            household_id=household_id,
            account_id=account.id,
            as_of_date=as_of_date,
            balance=balance,
            currency="USD",
            source=SnapshotSource.guided_manual,
            confidence_level="demo",
        )
    )
    summary.snapshots_created += 1


def _seed_real_estate(
    db: Session,
    summary: DemoSeedSummary,
    household_id: UUID,
    home_account: Account,
) -> None:
    exists = db.scalars(
        select(RealEstateProperty.id).where(RealEstateProperty.account_id == home_account.id)
    ).first()
    if exists is not None:
        return
    db.add(
        RealEstateProperty(
            household_id=household_id,
            account_id=home_account.id,
            property_type="residence",
            purchase_date=date(2020, 6, 15),
            purchase_price=Decimal("650000.00"),
            down_payment=Decimal("130000.00"),
            expected_appreciation_rate=Decimal("0.035000"),
            property_tax_annual=Decimal("7800.00"),
            insurance_annual=Decimal("1800.00"),
            maintenance_rate=Decimal("0.010000"),
            hoa_monthly=Decimal("0.00"),
        )
    )
    summary.properties_created += 1


def _seed_mortgage(
    db: Session,
    summary: DemoSeedSummary,
    household_id: UUID,
    mortgage_account: Account,
    home_account: Account,
) -> None:
    exists = db.scalars(
        select(MortgageProfile.id).where(MortgageProfile.liability_account_id == mortgage_account.id)
    ).first()
    if exists is not None:
        return
    db.add(
        MortgageProfile(
            household_id=household_id,
            liability_account_id=mortgage_account.id,
            property_account_id=home_account.id,
            original_principal=Decimal("520000.00"),
            interest_rate=Decimal("0.032500"),
            term_months=360,
            start_date=date(2020, 6, 15),
            monthly_payment=Decimal("2262.00"),
            rate_type="fixed",
        )
    )
    summary.mortgages_created += 1


def _seed_income_sources(db: Session, summary: DemoSeedSummary, household_id: UUID) -> None:
    rows = [
        {
            "name": "Salary",
            "income_type": "salary",
            "amount": Decimal("15500.00"),
            "frequency": IncomeFrequency.monthly,
            "start_date": date(2023, 1, 1),
            "growth_rate": Decimal("0.035000"),
        },
        {
            "name": "Annual Bonus",
            "income_type": "bonus",
            "amount": Decimal("25000.00"),
            "frequency": IncomeFrequency.annually,
            "start_date": date(2024, 3, 15),
            "growth_rate": Decimal("0.000000"),
        },
    ]
    for row in rows:
        exists = db.scalars(
            select(IncomeSource.id).where(
                IncomeSource.household_id == household_id,
                IncomeSource.name == row["name"],
            )
        ).first()
        if exists is not None:
            continue
        db.add(IncomeSource(household_id=household_id, currency="USD", **row))
        summary.income_sources_created += 1


def _seed_tax_records(db: Session, summary: DemoSeedSummary, household_id: UUID) -> None:
    rows = [
        (2024, "210000.00", "52000.00", "-1800.00", "Demo tax record for expense estimation."),
        (2025, "222000.00", "56500.00", "2400.00", "Demo tax record for expense estimation."),
    ]
    for tax_year, gross_income, total_taxes_paid, refund_or_amount_due, notes in rows:
        exists = db.scalars(
            select(AnnualTaxRecord.id).where(
                AnnualTaxRecord.household_id == household_id,
                AnnualTaxRecord.tax_year == tax_year,
            )
        ).first()
        if exists is not None:
            continue
        db.add(
            AnnualTaxRecord(
                household_id=household_id,
                tax_year=tax_year,
                gross_income=Decimal(gross_income),
                total_taxes_paid=Decimal(total_taxes_paid),
                refund_or_amount_due=Decimal(refund_or_amount_due),
                notes=notes,
            )
        )
        summary.tax_records_created += 1


def _seed_events(
    db: Session,
    summary: DemoSeedSummary,
    household_id: UUID,
    accounts: dict[str, Account],
) -> None:
    rows = [
        (
            accounts["brokerage"],
            date(2026, 6, 1),
            Decimal("12000.00"),
            AccountEventType.contribution,
            "Planned taxable brokerage contribution.",
            ProjectionBehavior.projection_only,
        ),
        (
            accounts["retirement"],
            date(2027, 1, 15),
            Decimal("23500.00"),
            AccountEventType.contribution,
            "Planned annual retirement contribution.",
            ProjectionBehavior.projection_only,
        ),
        (
            accounts["checking"],
            date(2028, 5, 1),
            Decimal("-18000.00"),
            AccountEventType.large_purchase,
            "Planned vehicle replacement.",
            ProjectionBehavior.projection_only,
        ),
        (
            accounts["home"],
            date(2030, 6, 15),
            Decimal("-35000.00"),
            AccountEventType.manual_projection_adjustment,
            "Planned major home renovation adjustment.",
            ProjectionBehavior.projection_only,
        ),
    ]
    for account, event_date, amount, event_type, description, projection_behavior in rows:
        exists = db.scalars(
            select(AccountEvent.id).where(
                AccountEvent.account_id == account.id,
                AccountEvent.event_date == event_date,
                AccountEvent.amount == amount,
                AccountEvent.event_type == event_type,
                AccountEvent.description == description,
            )
        ).first()
        if exists is not None:
            continue
        db.add(
            AccountEvent(
                household_id=household_id,
                account_id=account.id,
                event_date=event_date,
                amount=amount,
                currency="USD",
                event_type=event_type,
                description=description,
                projection_behavior=projection_behavior,
            )
        )
        summary.events_created += 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a realistic Netwise demo household.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing Demo Household data before recreating it.",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        summary = seed_demo_data(db, reset=args.reset)

    print("Seeded Netwise demo data:")
    for key, value in asdict(summary).items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
