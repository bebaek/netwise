from __future__ import annotations

import csv
import tomllib
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Account,
    AccountEvent,
    AccountEventType,
    BalanceSnapshot,
    MortgageProfile,
    ProjectionBehavior,
    ProjectionScenarioAccountAssumption,
    ProjectionScenarioPropertyAssumption,
    RealEstateProperty,
    RetirementTaxTreatment,
    SnapshotSource,
)
from app.services.projection_scenarios import get_baseline_scenario

CONDITION_SUFFIX = "-condition.toml"


@dataclass
class FintrackAssetImportResult:
    name: str
    kind: str
    account_id: UUID | None = None
    liability_account_id: UUID | None = None
    accounts_created: int = 0
    accounts_existing: int = 0
    snapshots_created: int = 0
    snapshots_updated: int = 0
    snapshots_existing: int = 0
    events_created: int = 0
    events_existing: int = 0
    real_estate_profiles_created: int = 0
    real_estate_profiles_existing: int = 0
    mortgage_profiles_created: int = 0
    mortgage_profiles_existing: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class FintrackImportResult:
    household_id: UUID
    data_dir: str
    dry_run: bool
    assets: list[FintrackAssetImportResult] = field(default_factory=list)

    @property
    def accounts_created(self) -> int:
        return sum(asset.accounts_created for asset in self.assets)

    @property
    def accounts_existing(self) -> int:
        return sum(asset.accounts_existing for asset in self.assets)

    @property
    def snapshots_created(self) -> int:
        return sum(asset.snapshots_created for asset in self.assets)

    @property
    def snapshots_updated(self) -> int:
        return sum(asset.snapshots_updated for asset in self.assets)

    @property
    def snapshots_existing(self) -> int:
        return sum(asset.snapshots_existing for asset in self.assets)

    @property
    def events_created(self) -> int:
        return sum(asset.events_created for asset in self.assets)

    @property
    def events_existing(self) -> int:
        return sum(asset.events_existing for asset in self.assets)

    @property
    def real_estate_profiles_created(self) -> int:
        return sum(asset.real_estate_profiles_created for asset in self.assets)

    @property
    def real_estate_profiles_existing(self) -> int:
        return sum(asset.real_estate_profiles_existing for asset in self.assets)

    @property
    def mortgage_profiles_created(self) -> int:
        return sum(asset.mortgage_profiles_created for asset in self.assets)

    @property
    def mortgage_profiles_existing(self) -> int:
        return sum(asset.mortgage_profiles_existing for asset in self.assets)


class FintrackImportError(ValueError):
    pass


def import_fintrack_directory(
    db: Session,
    *,
    household_id: UUID,
    data_dir: str | Path,
    currency: str = "USD",
    dry_run: bool = False,
) -> FintrackImportResult:
    root = Path(data_dir).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise FintrackImportError(f"FinTrack data directory does not exist: {root}")

    result = FintrackImportResult(household_id=household_id, data_dir=str(root), dry_run=dry_run)
    condition_paths = sorted(root.glob(f"*{CONDITION_SUFFIX}"))
    if not condition_paths:
        raise FintrackImportError(f"No *{CONDITION_SUFFIX} files found in {root}")

    for condition_path in condition_paths:
        result.assets.append(
            _import_asset(
                db,
                household_id=household_id,
                root=root,
                asset_name=condition_path.name.removesuffix(CONDITION_SUFFIX),
                currency=currency,
            )
        )

    if dry_run:
        db.rollback()
    else:
        db.commit()
    return result


def _import_asset(
    db: Session,
    *,
    household_id: UUID,
    root: Path,
    asset_name: str,
    currency: str,
) -> FintrackAssetImportResult:
    condition = _read_condition(root / f"{asset_name}{CONDITION_SUFFIX}")
    values = _read_value_csv(root / f"{asset_name}-values.csv")
    value_changes = _read_optional_value_csv(root / f"{asset_name}-value-changes.csv")
    is_real_estate = _looks_like_real_estate(condition)

    if is_real_estate:
        return _import_real_estate_asset(
            db,
            household_id=household_id,
            name=asset_name,
            condition=condition,
            values=values,
            value_changes=value_changes,
            currency=currency,
        )
    return _import_liquid_asset(
        db,
        household_id=household_id,
        name=asset_name,
        condition=condition,
        values=values,
        value_changes=value_changes,
        currency=currency,
    )


def _import_liquid_asset(
    db: Session,
    *,
    household_id: UUID,
    name: str,
    condition: dict,
    values: list[tuple[date, Decimal]],
    value_changes: list[tuple[date, Decimal]],
    currency: str,
) -> FintrackAssetImportResult:
    result = FintrackAssetImportResult(name=name, kind="liquid_asset")
    account, created = _get_or_create_account(
        db,
        household_id=household_id,
        name=_display_name(name),
        account_kind="asset",
        category=_infer_liquid_category(name),
        liquidity_class="marketable",
        expected_annual_yield=_condition_yield(condition),
        currency=currency,
    )
    result.account_id = account.id
    if created:
        result.accounts_created += 1
    else:
        result.accounts_existing += 1
    _upsert_snapshots(db, result, account=account, values=values, currency=currency)
    _create_events(db, result, account=account, values=value_changes, currency=currency)
    return result


def _import_real_estate_asset(
    db: Session,
    *,
    household_id: UUID,
    name: str,
    condition: dict,
    values: list[tuple[date, Decimal]],
    value_changes: list[tuple[date, Decimal]],
    currency: str,
) -> FintrackAssetImportResult:
    result = FintrackAssetImportResult(name=name, kind="real_estate")
    property_account, created = _get_or_create_account(
        db,
        household_id=household_id,
        name=_display_name(name),
        account_kind="asset",
        category="real_estate",
        liquidity_class="illiquid",
        expected_annual_yield=None,
        currency=currency,
    )
    result.account_id = property_account.id
    if created:
        result.accounts_created += 1
    else:
        result.accounts_existing += 1
    _upsert_snapshots(db, result, account=property_account, values=values, currency=currency)
    _create_events(db, result, account=property_account, values=value_changes, currency=currency)

    if _get_or_create_real_estate_profile(db, household_id, property_account, condition):
        result.real_estate_profiles_created += 1
    else:
        result.real_estate_profiles_existing += 1

    loan_amount = _decimal_or_none(condition.get("loan"))
    if loan_amount is not None:
        liability_account, liability_created = _get_or_create_account(
            db,
            household_id=household_id,
            name=f"{_display_name(name)} Mortgage",
            account_kind="liability",
            category="mortgage",
            liquidity_class="debt",
            expected_annual_yield=Decimal("0.000000"),
            currency=currency,
        )
        result.liability_account_id = liability_account.id
        if liability_created:
            result.accounts_created += 1
        else:
            result.accounts_existing += 1
        if _get_or_create_mortgage_profile(
            db, household_id, liability_account, property_account, condition, loan_amount
        ):
            result.mortgage_profiles_created += 1
        else:
            result.mortgage_profiles_existing += 1
    else:
        result.warnings.append("No loan amount found; imported property without mortgage profile")

    return result


def _read_condition(path: Path) -> dict:
    with path.open("rb") as file:
        return tomllib.load(file)


def _read_optional_value_csv(path: Path) -> list[tuple[date, Decimal]]:
    if not path.exists():
        return []
    return _read_value_csv(path)


def _read_value_csv(path: Path) -> list[tuple[date, Decimal]]:
    if not path.exists():
        raise FintrackImportError(f"Missing values CSV: {path}")
    values: list[tuple[date, Decimal]] = []
    with path.open(newline="") as file:
        reader = csv.reader(file)
        for row in reader:
            if len(row) < 2:
                continue
            try:
                values.append((date.fromisoformat(row[0].strip()), Decimal(row[1].strip())))
            except (ValueError, InvalidOperation):
                # Header rows are accepted; malformed data rows fail if they look date-like.
                if row[0].strip()[:4].isdigit():
                    raise FintrackImportError(f"Invalid FinTrack CSV row in {path}: {row}")
    return values


def _looks_like_real_estate(condition: dict) -> bool:
    return any(
        key in condition
        for key in ("loan", "start_date", "term", "term_months", "rate", "interest_rate")
    )


def _condition_yield(condition: dict) -> Decimal | None:
    return _decimal_or_none(condition.get("yield"))


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal("0.000001"))


def _display_name(name: str) -> str:
    return name.replace("-", " ").replace("_", " ").title()


def _infer_liquid_category(name: str) -> str:
    lowered = name.lower()
    if any(token in lowered for token in ("401", "403", "ira", "roth", "retirement", "tiaa")):
        return "retirement"
    if any(token in lowered for token in ("checking", "savings", "cash", "bank", "ally")):
        return "cash"
    return "taxable_investment"


def _infer_retirement_tax_treatment(name: str, category: str) -> RetirementTaxTreatment | None:
    if category != "retirement":
        return None
    lowered = name.casefold()
    if "roth" in lowered:
        return RetirementTaxTreatment.roth
    if "after tax" in lowered or "after-tax" in lowered:
        return RetirementTaxTreatment.after_tax
    return RetirementTaxTreatment.traditional


def _get_or_create_account(
    db: Session,
    *,
    household_id: UUID,
    name: str,
    account_kind: str,
    category: str,
    liquidity_class: str,
    expected_annual_yield: Decimal | None,
    currency: str,
) -> tuple[Account, bool]:
    account = db.scalars(
        select(Account).where(Account.household_id == household_id, Account.name == name)
    ).first()
    if account is not None:
        account.account_kind = account_kind
        account.category = category
        account.liquidity_class = liquidity_class
        account.expected_annual_yield = expected_annual_yield
        if category != "retirement":
            account.retirement_tax_treatment = None
        elif account.retirement_tax_treatment is None:
            account.retirement_tax_treatment = _infer_retirement_tax_treatment(name, category)
        account.currency = currency
        _sync_baseline_account_assumption(db, account)
        return account, False

    account = Account(
        household_id=household_id,
        name=name,
        account_kind=account_kind,
        category=category,
        liquidity_class=liquidity_class,
        retirement_tax_treatment=_infer_retirement_tax_treatment(name, category),
        expected_annual_yield=expected_annual_yield,
        currency=currency,
    )
    db.add(account)
    db.flush()
    _sync_baseline_account_assumption(db, account)
    return account, True


def _sync_baseline_account_assumption(db: Session, account: Account) -> None:
    baseline = get_baseline_scenario(db, account.household_id)
    assumption = db.scalar(
        select(ProjectionScenarioAccountAssumption).where(
            ProjectionScenarioAccountAssumption.scenario_id == baseline.id,
            ProjectionScenarioAccountAssumption.account_id == account.id,
        )
    )
    if assumption is None:
        db.add(
            ProjectionScenarioAccountAssumption(
                scenario_id=baseline.id,
                household_id=account.household_id,
                account_id=account.id,
                expected_annual_yield=account.expected_annual_yield,
                liquidation_expense_rate=account.liquidation_expense_rate,
            )
        )
        return
    assumption.expected_annual_yield = account.expected_annual_yield
    assumption.liquidation_expense_rate = account.liquidation_expense_rate


def _upsert_snapshots(
    db: Session,
    result: FintrackAssetImportResult,
    *,
    account: Account,
    values: list[tuple[date, Decimal]],
    currency: str,
) -> None:
    for as_of_date, balance in values:
        snapshot = db.scalars(
            select(BalanceSnapshot).where(
                BalanceSnapshot.account_id == account.id,
                BalanceSnapshot.as_of_date == as_of_date,
            )
        ).first()
        if snapshot is None:
            db.add(
                BalanceSnapshot(
                    household_id=account.household_id,
                    account_id=account.id,
                    as_of_date=as_of_date,
                    balance=balance,
                    currency=currency,
                    source=SnapshotSource.imported_csv,
                    confidence_level="imported",
                )
            )
            result.snapshots_created += 1
        else:
            already_matches = (
                snapshot.balance == balance
                and snapshot.currency == currency
                and snapshot.source == SnapshotSource.imported_csv
                and snapshot.confidence_level == "imported"
            )
            if already_matches:
                result.snapshots_existing += 1
                continue
            snapshot.balance = balance
            snapshot.currency = currency
            snapshot.source = SnapshotSource.imported_csv
            snapshot.confidence_level = "imported"
            result.snapshots_updated += 1


def _create_events(
    db: Session,
    result: FintrackAssetImportResult,
    *,
    account: Account,
    values: list[tuple[date, Decimal]],
    currency: str,
) -> None:
    for event_date, amount in values:
        event_type = AccountEventType.contribution if amount >= 0 else AccountEventType.withdrawal
        description = "Imported from FinTrack value changes"
        existing = db.scalars(
            select(AccountEvent).where(
                AccountEvent.account_id == account.id,
                AccountEvent.event_date == event_date,
                AccountEvent.amount == amount,
                AccountEvent.description == description,
            )
        ).first()
        if existing is not None:
            result.events_existing += 1
            continue
        db.add(
            AccountEvent(
                household_id=account.household_id,
                account_id=account.id,
                event_date=event_date,
                amount=amount,
                currency=currency,
                event_type=event_type,
                description=description,
                projection_behavior=ProjectionBehavior.historical_and_projection,
            )
        )
        result.events_created += 1


def _get_or_create_real_estate_profile(
    db: Session,
    household_id: UUID,
    account: Account,
    condition: dict,
) -> bool:
    existing = db.scalars(
        select(RealEstateProperty).where(RealEstateProperty.account_id == account.id)
    ).first()
    if existing is not None:
        existing.expected_appreciation_rate = _condition_yield(condition)
        _sync_baseline_property_assumption(db, existing)
        return False
    property_record = RealEstateProperty(
        household_id=household_id,
        account_id=account.id,
        property_type="residence",
        expected_appreciation_rate=_condition_yield(condition),
    )
    db.add(property_record)
    db.flush()
    _sync_baseline_property_assumption(db, property_record)
    return True


def _sync_baseline_property_assumption(
    db: Session, property_record: RealEstateProperty
) -> None:
    baseline = get_baseline_scenario(db, property_record.household_id)
    assumption = db.scalar(
        select(ProjectionScenarioPropertyAssumption).where(
            ProjectionScenarioPropertyAssumption.scenario_id == baseline.id,
            ProjectionScenarioPropertyAssumption.property_account_id == property_record.account_id,
        )
    )
    if assumption is None:
        db.add(
            ProjectionScenarioPropertyAssumption(
                scenario_id=baseline.id,
                household_id=property_record.household_id,
                property_account_id=property_record.account_id,
                expected_appreciation_rate=property_record.expected_appreciation_rate,
                rent_growth_rate=property_record.rent_growth_rate,
                vacancy_rate=property_record.vacancy_rate,
            )
        )
        return
    assumption.expected_appreciation_rate = property_record.expected_appreciation_rate
    assumption.rent_growth_rate = property_record.rent_growth_rate
    assumption.vacancy_rate = property_record.vacancy_rate


def _get_or_create_mortgage_profile(
    db: Session,
    household_id: UUID,
    liability_account: Account,
    property_account: Account,
    condition: dict,
    loan_amount: Decimal,
) -> bool:
    start_date_raw = condition.get("start_date")
    if not start_date_raw:
        return False
    start_date = date.fromisoformat(str(start_date_raw))
    interest_rate = _decimal_or_none(condition.get("interest_rate", condition.get("rate")))
    term_months = int(condition.get("term_months", condition.get("term", 360)))
    if interest_rate is None:
        return False

    existing = db.scalars(
        select(MortgageProfile).where(MortgageProfile.liability_account_id == liability_account.id)
    ).first()
    if existing is not None:
        existing.property_account_id = property_account.id
        existing.original_principal = loan_amount
        existing.interest_rate = interest_rate
        existing.term_months = term_months
        existing.start_date = start_date
        return False
    db.add(
        MortgageProfile(
            household_id=household_id,
            liability_account_id=liability_account.id,
            property_account_id=property_account.id,
            original_principal=loan_amount,
            interest_rate=interest_rate,
            term_months=term_months,
            start_date=start_date,
            rate_type="fixed",
        )
    )
    return True
