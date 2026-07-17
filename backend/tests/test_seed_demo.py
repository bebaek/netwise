from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Account,
    AccountEvent,
    AnnualTaxRecord,
    BalanceSnapshot,
    Household,
    IncomeSource,
    MortgageProfile,
    RealEstateProperty,
)
from app.seed_demo import DEMO_HOUSEHOLD_NAME, seed_demo_data


def test_seed_demo_data_creates_realistic_household(db_session: Session) -> None:
    summary = seed_demo_data(db_session)

    household = db_session.get(Household, UUID(summary.household_id))
    assert household is not None
    assert household.name == DEMO_HOUSEHOLD_NAME
    assert summary.accounts_created == 6
    assert summary.snapshots_created == 30
    assert summary.events_created == 4
    assert summary.properties_created == 1
    assert summary.mortgages_created == 1
    assert summary.income_sources_created == 2
    assert summary.tax_records_created == 2

    assert db_session.scalar(select(func.count()).select_from(Account)) == 6
    assert db_session.scalar(select(func.count()).select_from(BalanceSnapshot)) == 30
    assert db_session.scalar(select(func.count()).select_from(AccountEvent)) == 4
    assert db_session.scalar(select(func.count()).select_from(RealEstateProperty)) == 1
    assert db_session.scalar(select(func.count()).select_from(MortgageProfile)) == 1
    assert db_session.scalar(select(func.count()).select_from(IncomeSource)) == 2
    assert db_session.scalar(select(func.count()).select_from(AnnualTaxRecord)) == 2


def test_seed_demo_data_is_idempotent_by_default(db_session: Session) -> None:
    first_summary = seed_demo_data(db_session)
    second_summary = seed_demo_data(db_session)

    assert second_summary.household_id == first_summary.household_id
    assert second_summary.accounts_created == 0
    assert second_summary.snapshots_created == 0
    assert second_summary.events_created == 0
    assert second_summary.properties_created == 0
    assert second_summary.mortgages_created == 0
    assert second_summary.income_sources_created == 0
    assert second_summary.tax_records_created == 0

    assert db_session.scalar(select(func.count()).select_from(Household)) == 1
    assert db_session.scalar(select(func.count()).select_from(Account)) == 6
    assert db_session.scalar(select(func.count()).select_from(BalanceSnapshot)) == 30
    assert db_session.scalar(select(func.count()).select_from(AccountEvent)) == 4


def test_seed_demo_data_reset_recreates_household(db_session: Session) -> None:
    first_summary = seed_demo_data(db_session)
    reset_summary = seed_demo_data(db_session, reset=True)

    assert reset_summary.reset is True
    assert reset_summary.household_id != first_summary.household_id
    assert reset_summary.accounts_created == 6
    assert reset_summary.snapshots_created == 30
    assert db_session.scalar(select(func.count()).select_from(Household)) == 1
    assert db_session.scalar(select(func.count()).select_from(Account)) == 6
    assert db_session.scalar(select(func.count()).select_from(BalanceSnapshot)) == 30
