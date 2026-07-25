from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.real_estate import calculate_real_estate_analytics
from app.db.models import (
    Account,
    AccountKind,
    MortgageProfile,
    ProjectionScenarioPropertyAssumption,
    RealEstateLiquidationStrategy,
    RealEstateProperty,
    RealEstateSale,
)
from app.db.session import get_db
from app.schemas.real_estate import (
    MortgageProfileCreate,
    MortgageProfileRead,
    RealEstateAnalyticsRead,
    RealEstateLiquidationStrategyRead,
    RealEstateLiquidationStrategyUpsert,
    RealEstatePropertyCreate,
    RealEstatePropertyRead,
    RealEstatePropertyUpdate,
    RealEstateSaleCreate,
    RealEstateSaleRead,
)
from app.services.projection_scenarios import (
    ProjectionScenarioNotFoundError,
    ensure_property_assumptions_for_all_scenarios,
    get_baseline_scenario,
    resolve_scenario,
)

router = APIRouter(tags=["real-estate"])


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

BANK_CATEGORIES = {"cash", "checking", "savings"}
LIQUIDITY_CLASSES = {"cash", "liquid", "marketable", "retirement_liquid"}


def _default_sale_proceeds_account(db: Session, household_id: UUID) -> Account | None:
    accounts = db.scalars(
        select(Account)
        .where(Account.household_id == household_id, Account.is_active.is_(True))
        .order_by(Account.name)
    ).all()
    return next(
        (
            account
            for account in accounts
            if account.account_kind == AccountKind.asset
            and account.category not in BANK_CATEGORIES | {"retirement", "real_estate"}
            and account.liquidity_class in LIQUIDITY_CLASSES
        ),
        None,
    )


def _validate_sale_proceeds_account(
    db: Session, household_id: UUID, property_account_id: UUID, proceeds_account_id: UUID
) -> Account:
    account = db.get(Account, proceeds_account_id)
    if (
        account is None
        or account.household_id != household_id
        or not account.is_active
        or account.account_kind != AccountKind.asset
        or account.id == property_account_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sale proceeds account must be a different active asset account in the household",
        )
    return account


def _validate_automatic_sale_proceeds_account(
    db: Session,
    household_id: UUID,
    property_account_id: UUID,
    proceeds_account_id: UUID,
) -> Account:
    account = _validate_sale_proceeds_account(
        db, household_id, property_account_id, proceeds_account_id
    )
    if (
        account.category in {"retirement", "real_estate"}
        or account.liquidity_class not in LIQUIDITY_CLASSES
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Automatic sale proceeds account must be a non-retirement liquid asset",
        )
    return account


@router.post(
    "/real-estate/sales",
    response_model=RealEstateSaleRead,
    status_code=status.HTTP_201_CREATED,
)
def create_real_estate_sale(
    payload: RealEstateSaleCreate,
    scenario_id: UUID | None = None,
    db: Session = Depends(get_db),
) -> RealEstateSale:
    property_account = db.get(Account, payload.property_account_id)
    if property_account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Property account not found"
        )
    if (
        property_account.account_kind != AccountKind.asset
        or property_account.category != "real_estate"
        or not property_account.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Property sale must be linked to an active real estate asset account",
        )
    scenario = _resolve_scenario_or_404(db, property_account.household_id, scenario_id)
    if (
        db.scalars(
            select(RealEstateSale).where(
                RealEstateSale.scenario_id == scenario.id,
                RealEstateSale.property_account_id == property_account.id,
            )
        ).first()
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A sale is already planned for this property account",
        )

    proceeds_account_id = payload.proceeds_account_id
    if proceeds_account_id is None:
        proceeds_account = _default_sale_proceeds_account(db, property_account.household_id)
        if proceeds_account is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Select a sale proceeds account; no non-retirement liquid account is available",
            )
        proceeds_account_id = proceeds_account.id

    _validate_sale_proceeds_account(
        db, property_account.household_id, property_account.id, proceeds_account_id
    )
    sale = RealEstateSale(
        household_id=property_account.household_id,
        scenario_id=scenario.id,
        property_account_id=property_account.id,
        sale_date=payload.sale_date,
        gross_sale_price=payload.gross_sale_price,
        proceeds_account_id=proceeds_account_id,
        selling_expense_rate=payload.selling_expense_rate,
        estimated_tax_rate=payload.estimated_tax_rate,
    )
    db.add(sale)
    db.commit()
    db.refresh(sale)
    return sale


@router.get("/real-estate/sales", response_model=list[RealEstateSaleRead])
def list_real_estate_sales(
    household_id: UUID,
    scenario_id: UUID | None = None,
    db: Session = Depends(get_db),
) -> list[RealEstateSale]:
    scenario = _resolve_scenario_or_404(db, household_id, scenario_id)
    return list(
        db.scalars(
            select(RealEstateSale)
            .where(
                RealEstateSale.household_id == household_id,
                RealEstateSale.scenario_id == scenario.id,
            )
            .order_by(RealEstateSale.sale_date)
        ).all()
    )


@router.delete("/real-estate/sales/{sale_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_real_estate_sale(sale_id: UUID, db: Session = Depends(get_db)) -> Response:
    sale = db.get(RealEstateSale, sale_id)
    if sale is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property sale not found")
    db.delete(sale)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/real-estate/liquidation-strategies",
    response_model=list[RealEstateLiquidationStrategyRead],
)
def list_real_estate_liquidation_strategies(
    household_id: UUID,
    scenario_id: UUID | None = None,
    db: Session = Depends(get_db),
) -> list[RealEstateLiquidationStrategy]:
    scenario = _resolve_scenario_or_404(db, household_id, scenario_id)
    return list(
        db.scalars(
            select(RealEstateLiquidationStrategy)
            .where(
                RealEstateLiquidationStrategy.household_id == household_id,
                RealEstateLiquidationStrategy.scenario_id == scenario.id,
            )
            .order_by(
                RealEstateLiquidationStrategy.priority,
                RealEstateLiquidationStrategy.created_at,
            )
        ).all()
    )


@router.put(
    "/real-estate/liquidation-strategies/{property_account_id}",
    response_model=RealEstateLiquidationStrategyRead,
)
def upsert_real_estate_liquidation_strategy(
    property_account_id: UUID,
    payload: RealEstateLiquidationStrategyUpsert,
    scenario_id: UUID | None = None,
    db: Session = Depends(get_db),
) -> RealEstateLiquidationStrategy:
    property_account = db.get(Account, property_account_id)
    if (
        property_account is None
        or property_account.account_kind != AccountKind.asset
        or property_account.category != "real_estate"
        or not property_account.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Automatic sale strategy requires an active real estate asset account",
        )

    scenario = _resolve_scenario_or_404(db, property_account.household_id, scenario_id)
    proceeds_account_id = payload.proceeds_account_id
    if proceeds_account_id is None:
        proceeds_account = _default_sale_proceeds_account(db, property_account.household_id)
        if proceeds_account is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Select a proceeds account; no non-retirement liquid account is available",
            )
        proceeds_account_id = proceeds_account.id
    _validate_automatic_sale_proceeds_account(
        db, property_account.household_id, property_account.id, proceeds_account_id
    )

    strategy = db.scalars(
        select(RealEstateLiquidationStrategy).where(
            RealEstateLiquidationStrategy.scenario_id == scenario.id,
            RealEstateLiquidationStrategy.property_account_id == property_account.id,
        )
    ).first()
    if strategy is None:
        strategy = RealEstateLiquidationStrategy(
            household_id=property_account.household_id,
            scenario_id=scenario.id,
            property_account_id=property_account.id,
            proceeds_account_id=proceeds_account_id,
        )
        db.add(strategy)

    strategy.enabled = payload.enabled
    strategy.optimization_mode = payload.optimization_mode
    strategy.priority = payload.priority
    strategy.earliest_sale_date = payload.earliest_sale_date
    strategy.proceeds_account_id = proceeds_account_id
    strategy.selling_expense_rate = payload.selling_expense_rate
    strategy.estimated_tax_rate = payload.estimated_tax_rate
    db.commit()
    db.refresh(strategy)
    return strategy


@router.delete(
    "/real-estate/liquidation-strategies/{property_account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_real_estate_liquidation_strategy(
    property_account_id: UUID,
    scenario_id: UUID | None = None,
    db: Session = Depends(get_db),
) -> Response:
    property_account = db.get(Account, property_account_id)
    if property_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    scenario = _resolve_scenario_or_404(db, property_account.household_id, scenario_id)
    strategy = db.scalars(
        select(RealEstateLiquidationStrategy).where(
            RealEstateLiquidationStrategy.scenario_id == scenario.id,
            RealEstateLiquidationStrategy.property_account_id == property_account_id,
        )
    ).first()
    if strategy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automatic property sale strategy not found",
        )
    db.delete(strategy)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/real-estate/properties",
    response_model=RealEstatePropertyRead,
    status_code=status.HTTP_201_CREATED,
)
def create_real_estate_property(
    payload: RealEstatePropertyCreate,
    db: Session = Depends(get_db),
) -> RealEstateProperty:
    account = db.get(Account, payload.account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    if account.account_kind != AccountKind.asset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Real estate property must be linked to an asset account",
        )
    if payload.rental_deposit_account_id is not None:
        deposit_account = db.get(Account, payload.rental_deposit_account_id)
        if (
            deposit_account is None
            or deposit_account.household_id != account.household_id
            or not deposit_account.is_active
            or deposit_account.account_kind != AccountKind.asset
            or deposit_account.id == account.id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rental deposit account must be a different active asset in the same household",
            )

    real_estate_property = RealEstateProperty(
        household_id=account.household_id,
        **payload.model_dump(),
    )
    db.add(real_estate_property)
    db.flush()
    ensure_property_assumptions_for_all_scenarios(db, real_estate_property)
    db.commit()
    db.refresh(real_estate_property)
    return real_estate_property


@router.patch("/real-estate/properties/{property_id}", response_model=RealEstatePropertyRead)
def update_real_estate_property(
    property_id: UUID,
    payload: RealEstatePropertyUpdate,
    db: Session = Depends(get_db),
) -> RealEstateProperty:
    property_record = db.get(RealEstateProperty, property_id)
    if property_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    changes = payload.model_dump(exclude_unset=True)
    if "rental_deposit_account_id" in changes and changes["rental_deposit_account_id"] is not None:
        deposit_account = db.get(Account, changes["rental_deposit_account_id"])
        if (
            deposit_account is None
            or deposit_account.household_id != property_record.household_id
            or not deposit_account.is_active
            or deposit_account.account_kind != AccountKind.asset
            or deposit_account.id == property_record.account_id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rental deposit account must be a different active asset in the same household",
            )
    for field, value in changes.items():
        setattr(property_record, field, value)
    planning_fields = {"expected_appreciation_rate", "rent_growth_rate", "vacancy_rate"}
    if planning_fields & changes.keys():
        baseline = get_baseline_scenario(db, property_record.household_id)
        assumption = db.scalar(
            select(ProjectionScenarioPropertyAssumption).where(
                ProjectionScenarioPropertyAssumption.scenario_id == baseline.id,
                ProjectionScenarioPropertyAssumption.property_account_id
                == property_record.account_id,
            )
        )
        if assumption is None:
            ensure_property_assumptions_for_all_scenarios(db, property_record)
            db.flush()
            assumption = db.scalar(
                select(ProjectionScenarioPropertyAssumption).where(
                    ProjectionScenarioPropertyAssumption.scenario_id == baseline.id,
                    ProjectionScenarioPropertyAssumption.property_account_id
                    == property_record.account_id,
                )
            )
        if assumption is not None:
            for field in planning_fields & changes.keys():
                setattr(assumption, field, changes[field])
    db.commit()
    db.refresh(property_record)
    return property_record


@router.get(
    "/real-estate/analytics",
    response_model=list[RealEstateAnalyticsRead],
)
def get_real_estate_analytics(
    household_id: UUID,
    db: Session = Depends(get_db),
) -> list[dict]:
    return calculate_real_estate_analytics(db, household_id)


@router.get(
    "/real-estate/properties",
    response_model=list[RealEstatePropertyRead],
)
def list_real_estate_properties(
    household_id: UUID,
    db: Session = Depends(get_db),
) -> list[RealEstateProperty]:
    return list(
        db.scalars(
            select(RealEstateProperty)
            .where(RealEstateProperty.household_id == household_id)
            .order_by(RealEstateProperty.created_at)
        ).all()
    )


@router.get(
    "/real-estate/properties/{property_id}",
    response_model=RealEstatePropertyRead,
)
def get_real_estate_property(
    property_id: UUID,
    db: Session = Depends(get_db),
) -> RealEstateProperty:
    real_estate_property = db.get(RealEstateProperty, property_id)
    if real_estate_property is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    return real_estate_property


@router.post(
    "/mortgages",
    response_model=MortgageProfileRead,
    status_code=status.HTTP_201_CREATED,
)
def create_mortgage_profile(
    payload: MortgageProfileCreate,
    db: Session = Depends(get_db),
) -> MortgageProfile:
    liability_account = db.get(Account, payload.liability_account_id)
    if liability_account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Liability account not found"
        )
    if liability_account.account_kind != AccountKind.liability:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mortgage profile must be linked to a liability account",
        )

    if payload.property_account_id is not None:
        property_account = db.get(Account, payload.property_account_id)
        if property_account is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Property account not found"
            )
        if property_account.household_id != liability_account.household_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Property account must belong to the same household",
            )
        if property_account.account_kind != AccountKind.asset:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Property account must be an asset account",
            )

    mortgage_profile = MortgageProfile(
        household_id=liability_account.household_id,
        **payload.model_dump(),
    )
    db.add(mortgage_profile)
    db.commit()
    db.refresh(mortgage_profile)
    return mortgage_profile


@router.get("/mortgages", response_model=list[MortgageProfileRead])
def list_mortgage_profiles(
    household_id: UUID,
    db: Session = Depends(get_db),
) -> list[MortgageProfile]:
    return list(
        db.scalars(
            select(MortgageProfile)
            .where(MortgageProfile.household_id == household_id)
            .order_by(MortgageProfile.created_at)
        ).all()
    )


@router.get("/mortgages/{mortgage_id}", response_model=MortgageProfileRead)
def get_mortgage_profile(
    mortgage_id: UUID,
    db: Session = Depends(get_db),
) -> MortgageProfile:
    mortgage_profile = db.get(MortgageProfile, mortgage_id)
    if mortgage_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mortgage profile not found"
        )
    return mortgage_profile
