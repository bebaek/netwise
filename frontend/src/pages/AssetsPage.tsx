import { type FormEvent, useState } from 'react';
import type {
  Account,
  RealEstateAnalytics,
  RetirementTaxTreatment,
} from '../api';
import { useAccountMutations } from '../queries/household';
import { useRealEstateAssetData, useRealEstateAssetMutations } from '../queries/realEstate';
import { formatMoney } from '../utils/format';

function optionalFormString(form: FormData, key: string): string | undefined {
  const value = String(form.get(key) ?? '').trim();
  return value || undefined;
}

function requiredFormString(form: FormData, key: string): string {
  return String(form.get(key) ?? '').trim();
}

function formatPercent(value: string | null): string {
  if (value == null) return '—';
  return Number(value).toLocaleString(undefined, {
    style: 'percent',
    minimumFractionDigits: 1,
    maximumFractionDigits: 2,
  });
}

function dateMs(value: string): number {
  return new Date(`${value}T00:00:00Z`).getTime();
}

function PropertyAppreciationChart({ analytics }: { analytics: RealEstateAnalytics }) {
  const valuations = [...analytics.valuation_history].sort((left, right) =>
    left.as_of_date.localeCompare(right.as_of_date),
  );
  const purchasePoint = analytics.purchase_date && analytics.purchase_price
    ? { as_of_date: analytics.purchase_date, value: analytics.purchase_price }
    : null;
  const observedPoints = [...(purchasePoint ? [purchasePoint] : []), ...valuations]
    .sort((left, right) => left.as_of_date.localeCompare(right.as_of_date));
  const chartPoints = observedPoints;
  if (chartPoints.length < 2) return null;

  const dates = chartPoints.map((point) => dateMs(point.as_of_date));
  const values = chartPoints.map((point) => Number(point.value));
  const minDate = Math.min(...dates);
  const maxDate = Math.max(...dates);
  if (minDate === maxDate) return null;
  const rawMinValue = Math.min(...values);
  const rawMaxValue = Math.max(...values);
  const valuePadding = Math.max((rawMaxValue - rawMinValue) * 0.08, rawMaxValue * 0.02, 1);
  const minValue = Math.max(0, rawMinValue - valuePadding);
  const maxValue = rawMaxValue + valuePadding;
  const width = 720;
  const height = 220;
  const topPadding = 24;
  const bottomPadding = 28;
  const leftPadding = 96;
  const rightPadding = 28;
  const xForDate = (value: string) => leftPadding
    + ((dateMs(value) - minDate) / (maxDate - minDate)) * (width - leftPadding - rightPadding);
  const yForValue = (value: string) => topPadding
    + (height - topPadding - bottomPadding)
    - ((Number(value) - minValue) / (maxValue - minValue)) * (height - topPadding - bottomPadding);
  const valuationPolyline = observedPoints
    .map((point) => `${xForDate(point.as_of_date)},${yForValue(point.value)}`)
    .join(' ');

  return (
    <div className="trend-chart property-appreciation-chart" aria-label={`${analytics.property_name} appreciation trend chart`}>
      <svg viewBox={`0 0 ${width} ${height}`} role="img">
        <title>{analytics.property_name} recorded valuation trend</title>
        <line x1={leftPadding} y1={height - bottomPadding} x2={width - rightPadding} y2={height - bottomPadding} className="axis" />
        <line x1={leftPadding} y1={topPadding} x2={leftPadding} y2={height - bottomPadding} className="axis" />
        <text x={leftPadding - 10} y={topPadding + 4} textAnchor="end" className="axis-label">{formatMoney(String(maxValue))}</text>
        <text x={leftPadding - 10} y={height - bottomPadding + 4} textAnchor="end" className="axis-label">{formatMoney(String(minValue))}</text>
        {observedPoints.length > 1 && <polyline points={valuationPolyline} className="trend-line history" />}
        {purchasePoint && (
          <circle cx={xForDate(purchasePoint.as_of_date)} cy={yForValue(purchasePoint.value)} r={5} className="trend-dot purchase">
            <title>Purchase: {formatMoney(purchasePoint.value)} on {purchasePoint.as_of_date}</title>
          </circle>
        )}
        {valuations.map((point) => (
          <circle key={point.as_of_date} cx={xForDate(point.as_of_date)} cy={yForValue(point.value)} r={5} className="trend-dot snapshot">
            <title>Recorded valuation: {formatMoney(point.value)} on {point.as_of_date}</title>
          </circle>
        ))}
      </svg>
      <div className="chart-labels"><span>{new Date(minDate).toISOString().slice(0, 10)}</span><span>{new Date(maxDate).toISOString().slice(0, 10)}</span></div>
      <div className="chart-legend">
        <span><i className="legend-dot purchase" />Purchase price</span>
        <span><i className="legend-dot snapshot" />Recorded valuation</span>
      </div>
    </div>
  );
}

type AccountEditDraft = {
  id: string;
  name: string;
  institution_name: string;
  account_kind: 'asset' | 'liability';
  category: string;
  liquidity_class: string;
  retirement_tax_treatment: RetirementTaxTreatment | '';
  cost_basis: string;
  currency: string;
  is_active: boolean;
};

export function AssetsPage({
  householdId,
  defaultDate,
  accounts,
  assetAccounts,
  propertyAccounts,
  accountNameById,
  latestBalanceByAccountId,
}: {
  householdId: string;
  defaultDate: string;
  accounts: Account[];
  assetAccounts: Account[];
  propertyAccounts: Account[];
  accountNameById: ReadonlyMap<string, string>;
  latestBalanceByAccountId: ReadonlyMap<string, string | null>;
}) {
  const [propertyEditId, setPropertyEditId] = useState('');
  const [realEstateError, setRealEstateError] = useState('');
  const realEstateData = useRealEstateAssetData(householdId);
  const realEstateMutations = useRealEstateAssetMutations(householdId);
  const properties = realEstateData.properties.data ?? [];
  const realEstateAnalytics = realEstateData.analytics.data ?? [];
  const mortgages = realEstateData.mortgages.data ?? [];
  const [accountEditDraft, setAccountEditDraft] = useState<AccountEditDraft | null>(null);
  const [accountError, setAccountError] = useState('');
  const accountMutations = useAccountMutations(householdId);

  function startEditAccount(account: Account) {
    setAccountEditDraft({
      id: account.id,
      name: account.name,
      institution_name: account.institution_name ?? '',
      account_kind: account.account_kind,
      category: account.category,
      liquidity_class: account.liquidity_class,
      retirement_tax_treatment: account.retirement_tax_treatment ?? '',
      cost_basis: account.cost_basis ?? '',
      currency: account.currency,
      is_active: account.is_active,
    });
  }

  async function handleSaveAccountEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!accountEditDraft) return;
    setAccountError('');
    try {
      await accountMutations.update.mutateAsync({
        accountId: accountEditDraft.id,
        payload: {
          name: accountEditDraft.name.trim(),
          institution_name: accountEditDraft.institution_name.trim() || null,
          account_kind: accountEditDraft.account_kind,
          category: accountEditDraft.category.trim(),
          liquidity_class: accountEditDraft.liquidity_class.trim(),
          retirement_tax_treatment: accountEditDraft.retirement_tax_treatment || null,
          cost_basis: accountEditDraft.cost_basis.trim() || null,
          currency: accountEditDraft.currency.trim().toUpperCase(),
          is_active: accountEditDraft.is_active,
        },
      });
      await realEstateMutations.refreshAnalytics();
      setAccountEditDraft(null);
    } catch (mutationError: unknown) {
      setAccountError(String(mutationError));
    }
  }

  async function handleCreateAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const form = new FormData(target);
    const retirementTaxTreatment = String(form.get('retirement_tax_treatment') ?? '').trim();
    setAccountError('');
    try {
      await accountMutations.create.mutateAsync({
        household_id: householdId,
        name: String(form.get('name') ?? ''),
        account_kind: String(form.get('account_kind')) as 'asset' | 'liability',
        category: String(form.get('category') ?? ''),
        liquidity_class: String(form.get('liquidity_class') ?? ''),
        retirement_tax_treatment: retirementTaxTreatment
          ? retirementTaxTreatment as RetirementTaxTreatment
          : undefined,
        currency: 'USD',
      });
      target.reset();
    } catch (mutationError: unknown) {
      setAccountError(String(mutationError));
    }
  }

  async function handleUpdateProperty(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!propertyEditId) return;
    const form = new FormData(event.currentTarget);
    setRealEstateError('');
    try {
      await realEstateMutations.updateProperty.mutateAsync({
        propertyId: propertyEditId,
        payload: {
          property_type: requiredFormString(form, 'property_type'),
          purchase_date: optionalFormString(form, 'purchase_date') ?? null,
          purchase_price: optionalFormString(form, 'purchase_price') ?? null,
          adjusted_tax_basis: optionalFormString(form, 'adjusted_tax_basis') ?? null,
          down_payment: optionalFormString(form, 'down_payment') ?? null,
          is_rental: form.get('is_rental') === 'on',
          rental_start_date: optionalFormString(form, 'rental_start_date') ?? null,
          monthly_market_rent: optionalFormString(form, 'monthly_market_rent') ?? null,
          other_monthly_income: optionalFormString(form, 'other_monthly_income') ?? null,
          management_fee_rate: optionalFormString(form, 'management_fee_rate') ?? null,
          property_tax_annual: optionalFormString(form, 'property_tax_annual') ?? null,
          insurance_annual: optionalFormString(form, 'insurance_annual') ?? null,
          tax_and_insurance_annual: optionalFormString(form, 'tax_and_insurance_annual') ?? null,
          maintenance_rate: optionalFormString(form, 'maintenance_rate') ?? null,
          hoa_monthly: optionalFormString(form, 'hoa_monthly') ?? null,
          utilities_annual: optionalFormString(form, 'utilities_annual') ?? null,
          other_operating_expense_annual:
            optionalFormString(form, 'other_operating_expense_annual') ?? null,
          capital_reserve_rate: optionalFormString(form, 'capital_reserve_rate') ?? null,
          rental_deposit_account_id:
            optionalFormString(form, 'rental_deposit_account_id') ?? null,
        },
      });
    } catch (mutationError: unknown) {
      setRealEstateError(String(mutationError));
    }
  }

  async function handleCreateProperty(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const form = new FormData(target);
    const currentValue = optionalFormString(form, 'current_value');
    setRealEstateError('');
    try {
      await realEstateMutations.createProperty.mutateAsync({
        account: {
          household_id: householdId,
          name: requiredFormString(form, 'property_name'),
          account_kind: 'asset',
          category: 'real_estate',
          liquidity_class: 'illiquid',
          currency: 'USD',
        },
        property: {
          property_type: optionalFormString(form, 'property_type') ?? 'residence',
          purchase_date: optionalFormString(form, 'purchase_date'),
          purchase_price: optionalFormString(form, 'purchase_price'),
          adjusted_tax_basis: optionalFormString(form, 'adjusted_tax_basis'),
          down_payment: optionalFormString(form, 'down_payment'),
          property_tax_annual: optionalFormString(form, 'property_tax_annual'),
          insurance_annual: optionalFormString(form, 'insurance_annual'),
          tax_and_insurance_annual: optionalFormString(form, 'tax_and_insurance_annual'),
          maintenance_rate: optionalFormString(form, 'maintenance_rate'),
          hoa_monthly: optionalFormString(form, 'hoa_monthly'),
          is_rental: form.get('is_rental') === 'on',
          rental_start_date: optionalFormString(form, 'rental_start_date'),
          monthly_market_rent: optionalFormString(form, 'monthly_market_rent'),
          other_monthly_income: optionalFormString(form, 'other_monthly_income'),
          management_fee_rate: optionalFormString(form, 'management_fee_rate'),
          utilities_annual: optionalFormString(form, 'utilities_annual'),
          other_operating_expense_annual:
            optionalFormString(form, 'other_operating_expense_annual'),
          capital_reserve_rate: optionalFormString(form, 'capital_reserve_rate'),
          rental_deposit_account_id: optionalFormString(form, 'rental_deposit_account_id'),
        },
        snapshot: currentValue ? {
          as_of_date: optionalFormString(form, 'valuation_date') ?? defaultDate,
          balance: currentValue,
          currency: 'USD',
        } : undefined,
      });
      target.reset();
    } catch (mutationError: unknown) {
      setRealEstateError(String(mutationError));
    }
  }

  async function handleCreateMortgage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const form = new FormData(target);
    const originalPrincipal = requiredFormString(form, 'original_principal');
    const startDate = requiredFormString(form, 'start_date');
    const currentBalance = optionalFormString(form, 'current_balance') ?? originalPrincipal;
    setRealEstateError('');
    try {
      await realEstateMutations.createMortgage.mutateAsync({
        account: {
          household_id: householdId,
          name: requiredFormString(form, 'mortgage_name'),
          account_kind: 'liability',
          category: 'mortgage',
          liquidity_class: 'debt',
          expected_annual_yield: '0.000000',
          currency: 'USD',
        },
        mortgage: {
          property_account_id: optionalFormString(form, 'property_account_id'),
          original_principal: originalPrincipal,
          interest_rate: requiredFormString(form, 'interest_rate'),
          term_months: Number(requiredFormString(form, 'term_months')),
          start_date: startDate,
          monthly_payment: optionalFormString(form, 'monthly_payment'),
          rate_type: optionalFormString(form, 'rate_type') ?? 'fixed',
        },
        snapshot: {
          as_of_date: optionalFormString(form, 'balance_date') ?? startDate,
          balance: currentBalance,
          currency: 'USD',
        },
      });
      target.reset();
    } catch (mutationError: unknown) {
      setRealEstateError(String(mutationError));
    }
  }

  const realEstateQueryError = [
    realEstateData.properties,
    realEstateData.analytics,
    realEstateData.mortgages,
  ].find((query) => query.error)?.error;
  const realEstateLoading = [
    realEstateData.properties,
    realEstateData.analytics,
    realEstateData.mortgages,
  ].some((query) => query.isPending);

  return (
    <>
      {accountError && <div className="error" role="alert">{accountError}</div>}
      {realEstateError && <div className="error" role="alert">{realEstateError}</div>}
      {realEstateQueryError && <div className="error" role="alert">{String(realEstateQueryError)}</div>}
      {realEstateLoading && <div className="card" role="status">Loading real estate data…</div>}
<section className="card">
  <h2>Property details</h2>
  <p className="muted">Classify existing properties and configure rental cash flow assumptions.</p>
  {properties.length ? (
    <>
      <select aria-label="Property to edit" value={propertyEditId} onChange={(event) => setPropertyEditId(event.target.value)}>
        <option value="">Select property to edit</option>
        {properties.map((property) => (
          <option key={property.id} value={property.id}>
            {accountNameById.get(property.account_id) ?? property.account_id}
          </option>
        ))}
      </select>
      {properties.filter((property) => property.id === propertyEditId).map((property) => (
        <form key={property.id} onSubmit={handleUpdateProperty} className="projection-form">
          <select name="property_type" aria-label="Property type" defaultValue={property.property_type}>
            <option value="residence">Primary residence</option>
            <option value="rental">Rental</option>
            <option value="land">Land</option>
            <option value="other">Other</option>
          </select>
          <label>Purchase date<input name="purchase_date" type="date" defaultValue={property.purchase_date ?? ''} /></label>
          <label>Purchase price<input name="purchase_price" inputMode="decimal" defaultValue={property.purchase_price ?? ''} /></label>
          <label>Adjusted tax basis<input name="adjusted_tax_basis" inputMode="decimal" defaultValue={property.adjusted_tax_basis ?? ''} /></label>
          <p className="muted">Sale-tax estimates use adjusted basis when provided, otherwise purchase price. Include basis adjustments such as capital improvements and depreciation.</p>
          <label>Down payment<input name="down_payment" inputMode="decimal" defaultValue={property.down_payment ?? ''} /></label>
          <p className="muted">Projection appreciation, rent growth, and vacancy are managed per scenario on the Planning page.</p>
          <label className="checkbox-label"><input name="is_rental" type="checkbox" defaultChecked={property.is_rental} /> Rental property</label>
          <label>Rental start date<input name="rental_start_date" type="date" defaultValue={property.rental_start_date ?? ''} /></label>
          <input name="monthly_market_rent" inputMode="decimal" placeholder="Monthly market rent" defaultValue={property.monthly_market_rent ?? ''} />
          <input name="other_monthly_income" inputMode="decimal" placeholder="Other monthly income" defaultValue={property.other_monthly_income ?? ''} />
          <input name="management_fee_rate" inputMode="decimal" placeholder="Management fee rate, e.g. 0.08" defaultValue={property.management_fee_rate ?? ''} />
          <input name="tax_and_insurance_annual" inputMode="decimal" placeholder="Combined annual tax + insurance (overrides separate fields)" defaultValue={property.tax_and_insurance_annual ?? ''} />
          <input name="property_tax_annual" inputMode="decimal" placeholder="Annual property tax (if entered separately)" defaultValue={property.property_tax_annual ?? ''} />
          <input name="insurance_annual" inputMode="decimal" placeholder="Annual insurance (if entered separately)" defaultValue={property.insurance_annual ?? ''} />
          <input name="maintenance_rate" inputMode="decimal" placeholder="Maintenance rate, e.g. 0.01" defaultValue={property.maintenance_rate ?? ''} />
          <input name="hoa_monthly" inputMode="decimal" placeholder="Monthly HOA" defaultValue={property.hoa_monthly ?? ''} />
          <input name="utilities_annual" inputMode="decimal" placeholder="Annual owner-paid utilities" defaultValue={property.utilities_annual ?? ''} />
          <input name="other_operating_expense_annual" inputMode="decimal" placeholder="Other annual operating expenses" defaultValue={property.other_operating_expense_annual ?? ''} />
          <input name="capital_reserve_rate" inputMode="decimal" placeholder="Capital reserve rate, e.g. 0.01" defaultValue={property.capital_reserve_rate ?? ''} />
          <select name="rental_deposit_account_id" aria-label="Rental deposit account" defaultValue={property.rental_deposit_account_id ?? ''}>
            <option value="">Default cash-flow account</option>
            {assetAccounts.filter((account) => account.id !== property.account_id).map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
          </select>
          <button type="submit" disabled={realEstateMutations.isPending}>Save property details</button>
        </form>
      ))}
    </>
  ) : <p className="muted">No properties configured.</p>}
</section>

<section className="card">
  <div className="section-header">
    <div>
      <h2>Property performance</h2>
      <p className="muted">Appreciation and equity use recorded valuations. Rental returns are estimates based on current assumptions.</p>
    </div>
  </div>
  {realEstateAnalytics.length ? (
    <div className="table-scroll" tabIndex={0} role="region" aria-label="Real estate performance analytics">
      <table className="spaced-table">
        <thead>
          <tr>
            <th>Property</th>
            <th>Current value</th>
            <th>Historical appreciation</th>
            <th>Annualized</th>
            <th>Equity</th>
            <th>Gross yield</th>
            <th>Cap rate</th>
            <th>Cash-on-cash</th>
          </tr>
        </thead>
        <tbody>
          {realEstateAnalytics.map((analytics) => (
            <tr key={analytics.property_id}>
              <td>
                {analytics.property_name}
                <span className="muted cell-detail">
                  {analytics.valuation_date ? `As of ${analytics.valuation_date}` : 'No valuation'}
                </span>
              </td>
              <td>{formatMoney(analytics.current_value)}</td>
              <td>
                {formatMoney(analytics.appreciation_amount)}
                <span className="muted cell-detail">{formatPercent(analytics.appreciation_rate)}</span>
              </td>
              <td>{formatPercent(analytics.annualized_appreciation_rate)}</td>
              <td>
                {formatMoney(analytics.equity)}
                {analytics.mortgage_balance_estimated && <span className="muted cell-detail">Estimated mortgage</span>}
              </td>
              <td>{formatPercent(analytics.gross_rental_yield)}</td>
              <td>{formatPercent(analytics.cap_rate)}</td>
              <td>{formatPercent(analytics.cash_on_cash_return)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {realEstateAnalytics.map((analytics) => (
        <details key={`${analytics.property_id}-history`} className="analytics-details">
          <summary>{analytics.property_name} valuation history ({analytics.valuation_history.length})</summary>
          <PropertyAppreciationChart analytics={analytics} />
          {analytics.valuation_history.length ? (
            <table className="spaced-table compact-table">
              <thead><tr><th>Date</th><th>Recorded value</th></tr></thead>
              <tbody>
                {analytics.valuation_history.map((point) => (
                  <tr key={point.as_of_date}><td>{point.as_of_date}</td><td>{formatMoney(point.value)}</td></tr>
                ))}
              </tbody>
            </table>
          ) : <p className="muted">Add a valuation snapshot to begin performance history.</p>}
          {analytics.estimated_noi != null && (
            <p className="muted">
              Estimated annual rent {formatMoney(analytics.estimated_annual_rental_income)}, NOI {formatMoney(analytics.estimated_noi)}, and cash flow {formatMoney(analytics.estimated_annual_cash_flow)}.
            </p>
          )}
          {analytics.limitations.map((limitation) => <p key={limitation} className="muted">{limitation}</p>)}
        </details>
      ))}
    </div>
  ) : <p className="muted">Add a property to see historical performance.</p>}
</section>

<section className="grid two-column">
  <div className="card">
    <h2>Real estate</h2>
    {properties.length ? (
      <table tabIndex={0}>
        <thead>
          <tr>
            <th>Property</th>
            <th>Type</th>
            <th>Purchase price</th>
            <th>Adjusted basis</th>
            <th>Projection assumptions</th>
          </tr>
        </thead>
        <tbody>
          {properties.map((property) => (
            <tr key={property.id}>
              <td>{accountNameById.get(property.account_id) ?? property.account_id}</td>
              <td>{property.property_type}</td>
              <td>{formatMoney(property.purchase_price)}</td>
              <td>{formatMoney(property.adjusted_tax_basis)}</td>
              <td>Managed in Planning</td>
            </tr>
          ))}
        </tbody>
      </table>
    ) : (
      <p className="muted">No property profiles yet.</p>
    )}
  </div>

  <div className="card">
    <h2>Mortgages</h2>
    {mortgages.length ? (
      <table tabIndex={0}>
        <thead>
          <tr>
            <th>Mortgage</th>
            <th>Property</th>
            <th>Principal</th>
            <th>Rate</th>
          </tr>
        </thead>
        <tbody>
          {mortgages.map((mortgage) => (
            <tr key={mortgage.id}>
              <td>{accountNameById.get(mortgage.liability_account_id) ?? mortgage.liability_account_id}</td>
              <td>
                {mortgage.property_account_id
                  ? accountNameById.get(mortgage.property_account_id) ?? mortgage.property_account_id
                  : '—'}
              </td>
              <td>{formatMoney(mortgage.original_principal)}</td>
              <td>{mortgage.interest_rate}</td>
            </tr>
          ))}
        </tbody>
      </table>
    ) : (
      <p className="muted">No mortgage profiles yet.</p>
    )}
  </div>
</section>

<section className="grid two-column">
  <div className="card">
    <h2>Add property</h2>
    <p className="muted">Creates a real estate asset account, property profile, and optional valuation snapshot.</p>
    <form onSubmit={handleCreateProperty} className="stacked-form">
      <input name="property_name" placeholder="Primary residence" required />
      <select name="property_type" aria-label="Property type" defaultValue="residence">
        <option value="residence">Residence</option>
        <option value="rental">Rental</option>
        <option value="land">Land</option>
        <option value="other">Other</option>
      </select>
      <label>
        Purchase date
        <input name="purchase_date" type="date" />
      </label>
      <label>Purchase price<input name="purchase_price" inputMode="decimal" /></label>
      <label>Adjusted tax basis<input name="adjusted_tax_basis" inputMode="decimal" /></label>
      <p className="muted">If adjusted basis is blank, sale-tax estimates use purchase price. Basis generally includes qualifying improvements and subtracts depreciation.</p>
      <label>Down payment<input name="down_payment" inputMode="decimal" /></label>
      <p className="muted">Set appreciation, rent growth, and vacancy after creation in the selected Planning scenario.</p>
      <input name="tax_and_insurance_annual" inputMode="decimal" placeholder="Combined annual tax + insurance (overrides separate fields)" />
      <input name="property_tax_annual" inputMode="decimal" placeholder="Annual property tax (if entered separately)" />
      <input name="insurance_annual" inputMode="decimal" placeholder="Annual insurance (if entered separately)" />
      <input name="maintenance_rate" inputMode="decimal" placeholder="Maintenance rate, e.g. 0.01" />
      <input name="hoa_monthly" inputMode="decimal" placeholder="Monthly HOA" />
      <label className="checkbox-label">
        <input name="is_rental" type="checkbox" />
        Rental property
      </label>
      <input name="rental_start_date" type="date" placeholder="Rental start date" />
      <input name="monthly_market_rent" inputMode="decimal" placeholder="Monthly market rent" />
      <input name="other_monthly_income" inputMode="decimal" placeholder="Other monthly income" />
      <input name="management_fee_rate" inputMode="decimal" placeholder="Management fee rate, e.g. 0.08" />
      <input name="utilities_annual" inputMode="decimal" placeholder="Annual owner-paid utilities" />
      <input name="other_operating_expense_annual" inputMode="decimal" placeholder="Other annual operating expenses" />
      <input name="capital_reserve_rate" inputMode="decimal" placeholder="Capital reserve rate, e.g. 0.01" />
      <select name="rental_deposit_account_id" aria-label="Rental deposit account" defaultValue="">
        <option value="">Default cash-flow account</option>
        {assetAccounts.map((account) => (
          <option key={account.id} value={account.id}>{account.name}</option>
        ))}
      </select>
      <input name="current_value" inputMode="decimal" placeholder="Current valuation snapshot" />
      <label>
        Valuation date
        <input name="valuation_date" type="date" defaultValue={defaultDate} />
      </label>
      <button type="submit" disabled={realEstateMutations.isPending}>Add property</button>
    </form>
  </div>

  <div className="card">
    <h2>Add mortgage</h2>
    <p className="muted">Creates a mortgage liability account, mortgage profile, and initial balance snapshot.</p>
    <form onSubmit={handleCreateMortgage} className="stacked-form">
      <input name="mortgage_name" placeholder="Primary residence mortgage" required />
      <select name="property_account_id" aria-label="Linked property" defaultValue="">
        <option value="">No linked property</option>
        {propertyAccounts.map((account) => (
          <option key={account.id} value={account.id}>
            {account.name}
          </option>
        ))}
      </select>
      <input name="original_principal" inputMode="decimal" placeholder="Original principal" required />
      <input name="interest_rate" inputMode="decimal" placeholder="Interest rate, e.g. 0.065" required />
      <input name="term_months" inputMode="numeric" placeholder="Term months, e.g. 360" required />
      <label>
        Start date
        <input name="start_date" type="date" required />
      </label>
      <input name="monthly_payment" inputMode="decimal" placeholder="Monthly payment" />
      <select name="rate_type" aria-label="Mortgage rate type" defaultValue="fixed">
        <option value="fixed">Fixed</option>
        <option value="adjustable">Adjustable</option>
      </select>
      <input name="current_balance" inputMode="decimal" placeholder="Current balance; defaults to original principal" />
      <label>
        Balance date
        <input name="balance_date" type="date" />
      </label>
      <button type="submit" disabled={realEstateMutations.isPending}>Add mortgage</button>
    </form>
  </div>
</section>

<section className="card">
  <div className="section-header">
    <div>
      <h2>Accounts</h2>
      <p className="muted">Edit shared account identity and classifications. Projection rates are managed per scenario on Planning.</p>
    </div>
  </div>
  {accountEditDraft && (
    <form onSubmit={handleSaveAccountEdit} className="event-editor-card">
      <div className="section-header">
        <div>
          <h3>Edit account</h3>
          <p className="muted">Category and liquidity class affect projection funding and tax estimates.</p>
        </div>
        <button type="button" className="secondary-button" onClick={() => setAccountEditDraft(null)}>
          Cancel
        </button>
      </div>
      <div className="event-editor-grid">
        <label>
          Name
          <input required value={accountEditDraft.name} onChange={(event) => setAccountEditDraft({ ...accountEditDraft, name: event.target.value })} />
        </label>
        <label>
          Institution
          <input value={accountEditDraft.institution_name} onChange={(event) => setAccountEditDraft({ ...accountEditDraft, institution_name: event.target.value })} />
        </label>
        <label>
          Kind
          <select value={accountEditDraft.account_kind} onChange={(event) => setAccountEditDraft({ ...accountEditDraft, account_kind: event.target.value as 'asset' | 'liability' })}>
            <option value="asset">Asset</option>
            <option value="liability">Liability</option>
          </select>
        </label>
        <label>
          Category
          <input
            required
            value={accountEditDraft.category}
            onChange={(event) =>
              setAccountEditDraft({
                ...accountEditDraft,
                category: event.target.value,
                retirement_tax_treatment:
                  event.target.value === 'retirement'
                    ? accountEditDraft.retirement_tax_treatment || 'traditional'
                    : '',
              })
            }
          />
        </label>
        <label>
          Liquidity class
          <input required value={accountEditDraft.liquidity_class} onChange={(event) => setAccountEditDraft({ ...accountEditDraft, liquidity_class: event.target.value })} />
        </label>
        <label>
          Retirement tax treatment
          <select
            disabled={accountEditDraft.category !== 'retirement'}
            value={accountEditDraft.retirement_tax_treatment}
            onChange={(event) =>
              setAccountEditDraft({
                ...accountEditDraft,
                retirement_tax_treatment: event.target.value as RetirementTaxTreatment | '',
              })
            }
          >
            <option value="">Not specified</option>
            <option value="traditional">Traditional / tax-deferred</option>
            <option value="roth">Roth / tax-free</option>
            <option value="after_tax">After-tax</option>
          </select>
        </label>
        <p className="muted">Expected yield and liquidation expense are managed per scenario on the Planning page.</p>
        <label>
          Cost basis
          <input inputMode="decimal" placeholder="Taxable accounts only" value={accountEditDraft.cost_basis} onChange={(event) => setAccountEditDraft({ ...accountEditDraft, cost_basis: event.target.value })} />
        </label>
        <p className="muted">
          Cost basis applies to taxable investment accounts; capital gains taxes use it instead of taxing the full withdrawal. Leave blank to estimate basis from the oldest balance snapshot.
        </p>
        <label>
          Currency
          <input required maxLength={3} value={accountEditDraft.currency} onChange={(event) => setAccountEditDraft({ ...accountEditDraft, currency: event.target.value })} />
        </label>
        <label className="inline-toggle">
          <input type="checkbox" checked={accountEditDraft.is_active} onChange={(event) => setAccountEditDraft({ ...accountEditDraft, is_active: event.target.checked })} />
          Active account
        </label>
      </div>
      <div className="action-row">
        <button type="submit" disabled={accountMutations.isPending}>Save account</button>
        <button type="button" className="secondary-button" onClick={() => setAccountEditDraft(null)}>Cancel</button>
      </div>
    </form>
  )}
  {accounts.length ? (
    <table tabIndex={0}>
      <thead>
        <tr>
          <th>Name</th>
          <th>Kind</th>
          <th>Category</th>
          <th>Retirement tax treatment</th>
          <th>Projection assumptions</th>
          <th>Balance</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {accounts.map((account) => (
          <tr key={account.id}>
            <td>{account.name}{!account.is_active && <span className="muted cell-detail">Inactive</span>}</td>
            <td>{account.account_kind}</td>
            <td>{account.category}</td>
            <td>{account.retirement_tax_treatment ?? 'Not applicable'}</td>
            <td>Managed in Planning</td>
            <td>{formatMoney(latestBalanceByAccountId.get(account.id))}</td>
            <td><button type="button" className="secondary-button" onClick={() => startEditAccount(account)}>Edit</button></td>
          </tr>
        ))}
      </tbody>
    </table>
  ) : (
    <p className="muted">No accounts yet.</p>
  )}
</section>

<section className="card">
  <h2>Add account</h2>
    <form onSubmit={handleCreateAccount} className="stacked-form">
      <input name="name" placeholder="Fidelity 401k" required />
      <select name="account_kind" aria-label="Account kind" defaultValue="asset">
        <option value="asset">Asset</option>
        <option value="liability">Liability</option>
      </select>
      <input name="category" placeholder="retirement / real_estate / mortgage" required />
      <input name="liquidity_class" placeholder="retirement_liquid / real_estate / liability" required />
      <select name="retirement_tax_treatment" aria-label="Retirement tax treatment" defaultValue="">
        <option value="">Not a retirement account</option>
        <option value="traditional">Traditional / tax-deferred</option>
        <option value="roth">Roth / tax-free</option>
        <option value="after_tax">After-tax</option>
      </select>
      <p className="muted">Configure expected yield and liquidation expense in the selected Planning scenario.</p>
      <button type="submit" disabled={accountMutations.isPending}>Add account</button>
  </form>
</section>
    </>
  );
}
