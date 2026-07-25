from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.social_security import (
    SocialSecurityCalculation,
    age_in_months,
    calculate_ballpark_benefit,
    calculate_manual_benefit,
)
from app.db.models import (
    Account,
    AccountKind,
    AnnualTaxRecord,
    Household,
    HouseholdPerson,
    IncomeFrequency,
    IncomeSource,
    ProjectionSettings,
    ProjectionTransfer,
    SpendingItem,
    SocialSecurityCalculationMode,
    SocialSecurityEstimate,
)
from app.db.session import get_db
from app.schemas.planning import (
    AnnualTaxRecordCreate,
    AnnualTaxRecordRead,
    HouseholdPersonCreate,
    HouseholdPersonRead,
    IncomeSourceCreate,
    IncomeSourceRead,
    ProjectionSettingsRead,
    ProjectionSettingsUpsert,
    ProjectionTransferCreate,
    ProjectionTransferRead,
    SpendingItemCreate,
    SpendingItemRead,
    SpendingItemUpdate,
    SocialSecurityEstimateCreate,
    SocialSecurityEstimateRead,
    SocialSecurityEstimateUpdate,
)
from app.services.projection_scenarios import (
    ProjectionScenarioNotFoundError,
    resolve_scenario,
)

router = APIRouter(tags=["planning"])


def _resolve_scenario_or_404(
    db: Session,
    household_id: UUID,
    scenario_id: UUID | None,
):
    try:
        return resolve_scenario(db, household_id, scenario_id)
    except ProjectionScenarioNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Projection scenario not found",
        ) from exc


def _validate_asset_account(
    db: Session, household_id: UUID, account_id: UUID | None, label: str
) -> None:
    if account_id is None:
        return
    account = db.get(Account, account_id)
    if account is None or account.household_id != household_id or account.account_kind != AccountKind.asset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} must be an asset account in the household",
        )


def _calculate_social_security_estimate(
    person: HouseholdPerson,
    payload: SocialSecurityEstimateCreate | SocialSecurityEstimateUpdate,
) -> SocialSecurityCalculation:
    if age_in_months(person.date_of_birth, payload.claiming_date) < 62 * 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Claiming date must be at or after age 62",
        )
    try:
        if payload.calculation_mode == SocialSecurityCalculationMode.manual:
            if payload.manual_monthly_benefit is None:
                raise ValueError("Manual monthly benefit is required in manual mode")
            return calculate_manual_benefit(
                date_of_birth=person.date_of_birth,
                monthly_benefit=payload.manual_monthly_benefit,
            )
        if (
            payload.current_covered_earnings is None
            or payload.completed_work_years is None
            or payload.earnings_pattern is None
        ):
            raise ValueError(
                "Covered earnings, completed work years, and earnings pattern are required in ballpark mode"
            )
        return calculate_ballpark_benefit(
            date_of_birth=person.date_of_birth,
            claiming_date=payload.claiming_date,
            current_covered_earnings=payload.current_covered_earnings,
            completed_work_years=payload.completed_work_years,
            expected_work_end_date=payload.expected_work_end_date,
            earnings_pattern=payload.earnings_pattern,
            cola_rate=payload.cola_rate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/household-people",
    response_model=HouseholdPersonRead,
    status_code=status.HTTP_201_CREATED,
)
def create_household_person(
    payload: HouseholdPersonCreate,
    db: Session = Depends(get_db),
) -> HouseholdPerson:
    if db.get(Household, payload.household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    person = HouseholdPerson(**payload.model_dump())
    person.name = person.name.strip()
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


@router.get("/household-people", response_model=list[HouseholdPersonRead])
def list_household_people(
    household_id: UUID,
    db: Session = Depends(get_db),
) -> list[HouseholdPerson]:
    return list(
        db.scalars(
            select(HouseholdPerson)
            .where(HouseholdPerson.household_id == household_id)
            .order_by(HouseholdPerson.name)
        ).all()
    )


@router.post(
    "/social-security-estimates",
    response_model=SocialSecurityEstimateRead,
    status_code=status.HTTP_201_CREATED,
)
def create_social_security_estimate(
    payload: SocialSecurityEstimateCreate,
    scenario_id: UUID | None = None,
    db: Session = Depends(get_db),
) -> SocialSecurityEstimate:
    scenario = _resolve_scenario_or_404(db, payload.household_id, scenario_id)
    person = db.get(HouseholdPerson, payload.person_id)
    if person is None or person.household_id != payload.household_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Person must belong to the household",
        )
    _validate_asset_account(db, payload.household_id, payload.deposit_account_id, "Deposit account")
    existing_estimate = db.scalars(
        select(SocialSecurityEstimate).where(
            SocialSecurityEstimate.scenario_id == scenario.id,
            SocialSecurityEstimate.person_id == payload.person_id,
        )
    ).first()
    if existing_estimate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delete the existing estimate for this person before creating another",
        )
    calculation = _calculate_social_security_estimate(person, payload)

    income_source = IncomeSource(
        household_id=payload.household_id,
        scenario_id=scenario.id,
        name=f"{person.name} Social Security",
        income_type="social_security",
        amount=calculation.monthly_benefit,
        currency="USD",
        frequency=IncomeFrequency.monthly,
        start_date=payload.claiming_date,
        growth_rate=payload.cola_rate,
        deposit_account_id=payload.deposit_account_id,
    )
    db.add(income_source)
    db.flush()
    estimate = SocialSecurityEstimate(
        household_id=payload.household_id,
        scenario_id=scenario.id,
        person_id=payload.person_id,
        income_source_id=income_source.id,
        calculation_mode=payload.calculation_mode,
        claiming_date=payload.claiming_date,
        current_covered_earnings=payload.current_covered_earnings,
        completed_work_years=payload.completed_work_years,
        expected_work_end_date=payload.expected_work_end_date,
        earnings_pattern=payload.earnings_pattern,
        manual_monthly_benefit=payload.manual_monthly_benefit,
        cola_rate=payload.cola_rate,
        estimated_monthly_benefit=calculation.monthly_benefit,
        lower_monthly_benefit=calculation.lower_monthly_benefit,
        upper_monthly_benefit=calculation.upper_monthly_benefit,
        full_retirement_age_months=calculation.full_retirement_age_months,
        benefit_at_full_retirement_age=calculation.benefit_at_full_retirement_age,
        calculation_version=calculation.calculation_version,
        law_assumption_year=calculation.law_assumption_year,
    )
    db.add(estimate)
    db.commit()
    db.refresh(estimate)
    return estimate


@router.get("/social-security-estimates", response_model=list[SocialSecurityEstimateRead])
def list_social_security_estimates(
    household_id: UUID,
    scenario_id: UUID | None = None,
    db: Session = Depends(get_db),
) -> list[SocialSecurityEstimate]:
    scenario = _resolve_scenario_or_404(db, household_id, scenario_id)
    return list(
        db.scalars(
            select(SocialSecurityEstimate)
            .where(
                SocialSecurityEstimate.household_id == household_id,
                SocialSecurityEstimate.scenario_id == scenario.id,
            )
            .order_by(SocialSecurityEstimate.claiming_date)
        ).all()
    )


@router.put(
    "/social-security-estimates/{estimate_id}", response_model=SocialSecurityEstimateRead
)
def update_social_security_estimate(
    estimate_id: UUID,
    payload: SocialSecurityEstimateUpdate,
    db: Session = Depends(get_db),
) -> SocialSecurityEstimate:
    estimate = db.get(SocialSecurityEstimate, estimate_id)
    if estimate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estimate not found")
    if payload.household_id != estimate.household_id or payload.person_id != estimate.person_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Estimate household and person cannot be changed",
        )
    person = db.get(HouseholdPerson, estimate.person_id)
    if person is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    _validate_asset_account(db, estimate.household_id, payload.deposit_account_id, "Deposit account")
    calculation = _calculate_social_security_estimate(person, payload)

    income_source = estimate.income_source
    income_source.name = f"{person.name} Social Security"
    income_source.amount = calculation.monthly_benefit
    income_source.start_date = payload.claiming_date
    income_source.growth_rate = payload.cola_rate
    income_source.deposit_account_id = payload.deposit_account_id

    estimate.calculation_mode = payload.calculation_mode
    estimate.claiming_date = payload.claiming_date
    estimate.current_covered_earnings = payload.current_covered_earnings
    estimate.completed_work_years = payload.completed_work_years
    estimate.expected_work_end_date = payload.expected_work_end_date
    estimate.earnings_pattern = payload.earnings_pattern
    estimate.manual_monthly_benefit = payload.manual_monthly_benefit
    estimate.cola_rate = payload.cola_rate
    estimate.estimated_monthly_benefit = calculation.monthly_benefit
    estimate.lower_monthly_benefit = calculation.lower_monthly_benefit
    estimate.upper_monthly_benefit = calculation.upper_monthly_benefit
    estimate.full_retirement_age_months = calculation.full_retirement_age_months
    estimate.benefit_at_full_retirement_age = calculation.benefit_at_full_retirement_age
    estimate.calculation_version = calculation.calculation_version
    estimate.law_assumption_year = calculation.law_assumption_year

    db.commit()
    db.refresh(estimate)
    return estimate


@router.delete("/social-security-estimates/{estimate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_social_security_estimate(
    estimate_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    estimate = db.get(SocialSecurityEstimate, estimate_id)
    if estimate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estimate not found")
    income_source = estimate.income_source
    db.delete(estimate)
    db.flush()
    db.delete(income_source)
    db.commit()


@router.post(
    "/income-sources",
    response_model=IncomeSourceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_income_source(
    payload: IncomeSourceCreate,
    scenario_id: UUID | None = None,
    db: Session = Depends(get_db),
) -> IncomeSource:
    if db.get(Household, payload.household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    scenario = _resolve_scenario_or_404(db, payload.household_id, scenario_id)
    _validate_asset_account(db, payload.household_id, payload.deposit_account_id, "Deposit account")

    income_source = IncomeSource(scenario_id=scenario.id, **payload.model_dump())
    db.add(income_source)
    db.commit()
    db.refresh(income_source)
    return income_source


@router.post(
    "/projection-transfers",
    response_model=ProjectionTransferRead,
    status_code=status.HTTP_201_CREATED,
)
def create_projection_transfer(
    payload: ProjectionTransferCreate,
    scenario_id: UUID | None = None,
    db: Session = Depends(get_db),
) -> ProjectionTransfer:
    if db.get(Household, payload.household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    scenario = _resolve_scenario_or_404(db, payload.household_id, scenario_id)
    _validate_asset_account(db, payload.household_id, payload.from_account_id, "Source account")
    _validate_asset_account(db, payload.household_id, payload.to_account_id, "Destination account")
    if payload.from_account_id == payload.to_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and destination accounts must be different",
        )
    if payload.end_date is not None and payload.end_date < payload.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be on or after start date",
        )

    projection_transfer = ProjectionTransfer(scenario_id=scenario.id, **payload.model_dump())
    db.add(projection_transfer)
    db.commit()
    db.refresh(projection_transfer)
    return projection_transfer


@router.get("/projection-transfers", response_model=list[ProjectionTransferRead])
def list_projection_transfers(
    household_id: UUID,
    scenario_id: UUID | None = None,
    db: Session = Depends(get_db),
) -> list[ProjectionTransfer]:
    scenario = _resolve_scenario_or_404(db, household_id, scenario_id)
    return list(
        db.scalars(
            select(ProjectionTransfer)
            .where(
                ProjectionTransfer.household_id == household_id,
                ProjectionTransfer.scenario_id == scenario.id,
            )
            .order_by(ProjectionTransfer.name, ProjectionTransfer.created_at)
        ).all()
    )


@router.delete(
    "/projection-transfers/{projection_transfer_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_projection_transfer(
    projection_transfer_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    projection_transfer = db.get(ProjectionTransfer, projection_transfer_id)
    if projection_transfer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Projection transfer not found"
        )
    db.delete(projection_transfer)
    db.commit()


@router.post(
    "/spending-items",
    response_model=SpendingItemRead,
    status_code=status.HTTP_201_CREATED,
)
def create_spending_item(
    payload: SpendingItemCreate,
    scenario_id: UUID | None = None,
    db: Session = Depends(get_db),
) -> SpendingItem:
    if db.get(Household, payload.household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    scenario = _resolve_scenario_or_404(db, payload.household_id, scenario_id)
    spending_item = SpendingItem(scenario_id=scenario.id, **payload.model_dump())
    spending_item.name = spending_item.name.strip()
    spending_item.category = spending_item.category.strip().lower()
    if not spending_item.name or not spending_item.category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Spending item name and category are required",
        )
    db.add(spending_item)
    db.commit()
    db.refresh(spending_item)
    return spending_item


@router.get("/spending-items", response_model=list[SpendingItemRead])
def list_spending_items(
    household_id: UUID,
    scenario_id: UUID | None = None,
    db: Session = Depends(get_db),
) -> list[SpendingItem]:
    scenario = _resolve_scenario_or_404(db, household_id, scenario_id)
    return list(
        db.scalars(
            select(SpendingItem)
            .where(
                SpendingItem.household_id == household_id,
                SpendingItem.scenario_id == scenario.id,
            )
            .order_by(SpendingItem.category, SpendingItem.name, SpendingItem.created_at)
        ).all()
    )


@router.patch("/spending-items/{spending_item_id}", response_model=SpendingItemRead)
def update_spending_item(
    spending_item_id: UUID,
    payload: SpendingItemUpdate,
    db: Session = Depends(get_db),
) -> SpendingItem:
    spending_item = db.get(SpendingItem, spending_item_id)
    if spending_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spending item not found")
    values = payload.model_dump(exclude_unset=True)
    if values.get("annual_amount") is None and "annual_amount" in values:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Annual amount cannot be null"
        )
    for field, value in values.items():
        if field == "name" and value is not None:
            value = value.strip()
            if not value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Spending item name is required",
                )
        elif field == "category" and value is not None:
            value = value.strip().lower()
            if not value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Spending item category is required",
                )
        setattr(spending_item, field, value)
    db.commit()
    db.refresh(spending_item)
    return spending_item


@router.delete("/spending-items/{spending_item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_spending_item(
    spending_item_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    spending_item = db.get(SpendingItem, spending_item_id)
    if spending_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spending item not found")
    db.delete(spending_item)
    db.commit()


@router.get("/projection-settings/{household_id}", response_model=ProjectionSettingsRead)
def get_projection_settings(
    household_id: UUID,
    scenario_id: UUID | None = None,
    db: Session = Depends(get_db),
) -> ProjectionSettings:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    scenario = _resolve_scenario_or_404(db, household_id, scenario_id)
    projection_settings = db.scalars(
        select(ProjectionSettings).where(
            ProjectionSettings.household_id == household_id,
            ProjectionSettings.scenario_id == scenario.id,
        )
    ).first()
    if projection_settings is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projection settings not found")
    return projection_settings


@router.put("/projection-settings/{household_id}", response_model=ProjectionSettingsRead)
def upsert_projection_settings(
    household_id: UUID,
    payload: ProjectionSettingsUpsert,
    scenario_id: UUID | None = None,
    db: Session = Depends(get_db),
) -> ProjectionSettings:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    scenario = _resolve_scenario_or_404(db, household_id, scenario_id)

    _validate_asset_account(db, household_id, payload.spending_account_id, "Spending account")
    _validate_asset_account(db, household_id, payload.tax_account_id, "Tax account")

    projection_settings = db.scalars(
        select(ProjectionSettings).where(
            ProjectionSettings.household_id == household_id,
            ProjectionSettings.scenario_id == scenario.id,
        )
    ).first()
    if projection_settings is None:
        projection_settings = ProjectionSettings(
            household_id=household_id,
            scenario_id=scenario.id,
        )
        db.add(projection_settings)

    for field, value in payload.model_dump().items():
        setattr(projection_settings, field, value)

    db.commit()
    db.refresh(projection_settings)
    return projection_settings


@router.get("/income-sources", response_model=list[IncomeSourceRead])
def list_income_sources(
    household_id: UUID,
    scenario_id: UUID | None = None,
    db: Session = Depends(get_db),
) -> list[IncomeSource]:
    scenario = _resolve_scenario_or_404(db, household_id, scenario_id)
    return list(
        db.scalars(
            select(IncomeSource)
            .where(
                IncomeSource.household_id == household_id,
                IncomeSource.scenario_id == scenario.id,
            )
            .order_by(IncomeSource.name)
        ).all()
    )


@router.get("/income-sources/{income_source_id}", response_model=IncomeSourceRead)
def get_income_source(
    income_source_id: UUID,
    db: Session = Depends(get_db),
) -> IncomeSource:
    income_source = db.get(IncomeSource, income_source_id)
    if income_source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Income source not found")
    return income_source


@router.post(
    "/annual-tax-records",
    response_model=AnnualTaxRecordRead,
    status_code=status.HTTP_201_CREATED,
)
def create_annual_tax_record(
    payload: AnnualTaxRecordCreate,
    db: Session = Depends(get_db),
) -> AnnualTaxRecord:
    if db.get(Household, payload.household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")

    tax_record = AnnualTaxRecord(**payload.model_dump())
    db.add(tax_record)
    db.commit()
    db.refresh(tax_record)
    return tax_record


@router.get("/annual-tax-records", response_model=list[AnnualTaxRecordRead])
def list_annual_tax_records(
    household_id: UUID,
    db: Session = Depends(get_db),
) -> list[AnnualTaxRecord]:
    return list(
        db.scalars(
            select(AnnualTaxRecord)
            .where(AnnualTaxRecord.household_id == household_id)
            .order_by(AnnualTaxRecord.tax_year.desc())
        ).all()
    )


@router.get("/annual-tax-records/{tax_record_id}", response_model=AnnualTaxRecordRead)
def get_annual_tax_record(
    tax_record_id: UUID,
    db: Session = Depends(get_db),
) -> AnnualTaxRecord:
    tax_record = db.get(AnnualTaxRecord, tax_record_id)
    if tax_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tax record not found")
    return tax_record
