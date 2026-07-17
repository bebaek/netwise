import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  Account,
  AccountEvent,
  AnnualExpenseEstimate,
  AnnualTaxRecord,
  Household,
  IncomeSource,
  MortgageProfile,
  NetWorth,
  NetWorthHistory,
  NetWorthProjection,
  RealEstateProperty,
  createAccount,
  createAccountEvent,
  createAnnualTaxRecord,
  createHousehold,
  createIncomeSource,
  createMortgageProfile,
  createRealEstateProperty,
  createSnapshot,
  getAnnualExpenseEstimate,
  getHistoricalTrend,
  getNetWorth,
  getNetWorthProjection,
  listAccounts,
  listAccountEvents,
  listAnnualTaxRecords,
  listHouseholds,
  listIncomeSources,
  listMortgageProfiles,
  listRealEstateProperties,
} from './api';
import './styles.css';

function formatMoney(value: string | null | undefined): string {
  if (value == null) return '—';
  return Number(value).toLocaleString(undefined, { style: 'currency', currency: 'USD' });
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function optionalString(form: FormData, key: string): string | undefined {
  const value = String(form.get(key) ?? '').trim();
  return value ? value : undefined;
}

function requiredString(form: FormData, key: string): string {
  return String(form.get(key) ?? '').trim();
}

type TrajectoryProjectionPoint = Pick<NetWorthProjection['points'][number], 'as_of_date' | 'net_worth'>;

function dateMs(value: string): number {
  return new Date(`${value}T00:00:00`).getTime();
}

function HistoryChart({
  points,
  projectionPoints = [],
}: {
  points: NetWorthHistory['points'];
  projectionPoints?: TrajectoryProjectionPoint[];
}) {
  const sortedHistory = [...points].sort((left, right) => left.as_of_date.localeCompare(right.as_of_date));
  const lastHistoryPoint = sortedHistory[sortedHistory.length - 1];
  const visibleProjectionPoints = [...projectionPoints]
    .filter((point) => !lastHistoryPoint || point.as_of_date > lastHistoryPoint.as_of_date)
    .sort((left, right) => left.as_of_date.localeCompare(right.as_of_date));
  const chartPoints = [...sortedHistory, ...visibleProjectionPoints];
  if (chartPoints.length < 2) return null;

  const values = chartPoints.map((point) => Number(point.net_worth));
  const dates = chartPoints.map((point) => dateMs(point.as_of_date));
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const minDate = Math.min(...dates);
  const maxDate = Math.max(...dates);
  const valueRange = maxValue - minValue || 1;
  const dateRange = maxDate - minDate || 1;
  const width = 720;
  const height = 240;
  const padding = 28;
  const plotWidth = width - padding * 2;
  const plotHeight = height - padding * 2;
  const xForDate = (value: string) => padding + ((dateMs(value) - minDate) / dateRange) * plotWidth;
  const yForValue = (value: number) => padding + plotHeight - ((value - minValue) / valueRange) * plotHeight;
  const polylineFor = (items: Array<{ as_of_date: string; net_worth: string }>) =>
    items.map((point) => `${xForDate(point.as_of_date)},${yForValue(Number(point.net_worth))}`).join(' ');
  const historyPolyline = polylineFor(sortedHistory);
  const projectionPolyline = lastHistoryPoint
    ? polylineFor([lastHistoryPoint, ...visibleProjectionPoints])
    : polylineFor(visibleProjectionPoints);

  return (
    <div className="trend-chart" aria-label="Financial trajectory chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img">
        <title>Financial trajectory</title>
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} className="axis" />
        <line x1={padding} y1={padding} x2={padding} y2={height - padding} className="axis" />
        <polyline points={historyPolyline} className="trend-line history" />
        {visibleProjectionPoints.length > 0 && <polyline points={projectionPolyline} className="trend-line projection" />}
        {sortedHistory.map((point) => (
          <circle
            key={`${point.as_of_date}-${point.estimated ? 'estimate' : 'snapshot'}`}
            cx={xForDate(point.as_of_date)}
            cy={yForValue(Number(point.net_worth))}
            r={point.estimated ? 3 : 5}
            className={point.estimated ? 'trend-dot estimate' : 'trend-dot snapshot'}
          />
        ))}
        {visibleProjectionPoints.map((point) => (
          <circle
            key={`${point.as_of_date}-projection`}
            cx={xForDate(point.as_of_date)}
            cy={yForValue(Number(point.net_worth))}
            r={4}
            className="trend-dot projection"
          />
        ))}
      </svg>
      <div className="chart-labels">
        <span>{chartPoints[0]?.as_of_date}</span>
        <span>{chartPoints[chartPoints.length - 1]?.as_of_date}</span>
      </div>
      <div className="chart-legend">
        <span><i className="legend-dot snapshot" />Snapshot</span>
        <span><i className="legend-dot estimate" />Estimate</span>
        {visibleProjectionPoints.length > 0 && <span><i className="legend-dot projection" />Projection</span>}
      </div>
    </div>
  );
}

function App() {
  const [households, setHouseholds] = useState<Household[]>([]);
  const [selectedHouseholdId, setSelectedHouseholdId] = useState<string>('');
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accountEvents, setAccountEvents] = useState<AccountEvent[]>([]);
  const [netWorth, setNetWorth] = useState<NetWorth | null>(null);
  const [history, setHistory] = useState<NetWorthHistory | null>(null);
  const [properties, setProperties] = useState<RealEstateProperty[]>([]);
  const [mortgages, setMortgages] = useState<MortgageProfile[]>([]);
  const [incomeSources, setIncomeSources] = useState<IncomeSource[]>([]);
  const [taxRecords, setTaxRecords] = useState<AnnualTaxRecord[]>([]);
  const [expenseEstimate, setExpenseEstimate] = useState<AnnualExpenseEstimate | null>(null);
  const [projection, setProjection] = useState<NetWorthProjection | null>(null);
  const [showInterpolatedHistory, setShowInterpolatedHistory] = useState<boolean>(false);
  const [showProjectionOnTrajectory, setShowProjectionOnTrajectory] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);

  const selectedHousehold = useMemo(
    () => households.find((household) => household.id === selectedHouseholdId),
    [households, selectedHouseholdId],
  );

  const accountNameById = useMemo(
    () => new Map(accounts.map((account) => [account.id, account.name])),
    [accounts],
  );

  const propertyAccounts = accounts.filter(
    (account) => account.account_kind === 'asset' && account.category === 'real_estate',
  );

  async function refreshHouseholds() {
    const householdList = await listHouseholds();
    setHouseholds(householdList);
    if (!selectedHouseholdId && householdList.length > 0) {
      setSelectedHouseholdId(householdList[0].id);
    }
  }

  async function refreshDashboard(householdId: string) {
    const [
      accountList,
      netWorthResult,
      historyResult,
      propertyList,
      mortgageList,
      incomeSourceList,
      taxRecordList,
    ] = await Promise.all([
      listAccounts(householdId),
      getNetWorth(householdId),
      getHistoricalTrend(householdId, showInterpolatedHistory),
      listRealEstateProperties(householdId),
      listMortgageProfiles(householdId),
      listIncomeSources(householdId),
      listAnnualTaxRecords(householdId),
    ]);
    const accountEventList = (await Promise.all(accountList.map((account) => listAccountEvents(account.id))))
      .flat()
      .sort((left, right) => right.event_date.localeCompare(left.event_date));
    setAccounts(accountList);
    setAccountEvents(accountEventList);
    setNetWorth(netWorthResult);
    setHistory(historyResult);
    setProperties(propertyList);
    setMortgages(mortgageList);
    setIncomeSources(incomeSourceList);
    setTaxRecords(taxRecordList);
  }

  useEffect(() => {
    refreshHouseholds()
      .catch((err: unknown) => setError(String(err)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedHouseholdId) return;
    setExpenseEstimate(null);
    setProjection(null);
  }, [selectedHouseholdId]);

  useEffect(() => {
    if (!selectedHouseholdId) return;
    refreshDashboard(selectedHouseholdId).catch((err: unknown) => setError(String(err)));
  }, [selectedHouseholdId, showInterpolatedHistory]);

  async function handleCreateHousehold(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    setError('');
    const form = new FormData(target);
    const name = String(form.get('name') ?? '').trim();
    if (!name) return;
    try {
      const household = await createHousehold(name);
      target.reset();
      await refreshHouseholds();
      setSelectedHouseholdId(household.id);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleCreateAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    if (!selectedHouseholdId) return;
    setError('');
    const form = new FormData(target);
    try {
      await createAccount({
        household_id: selectedHouseholdId,
        name: String(form.get('name') ?? ''),
        account_kind: String(form.get('account_kind')) as 'asset' | 'liability',
        category: String(form.get('category') ?? ''),
        liquidity_class: String(form.get('liquidity_class') ?? ''),
        expected_annual_yield: optionalString(form, 'expected_annual_yield'),
        currency: 'USD',
      });
      target.reset();
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleCreateSnapshot(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    if (!selectedHouseholdId) return;
    setError('');
    const form = new FormData(target);
    try {
      await createSnapshot(String(form.get('account_id')), {
        as_of_date: String(form.get('as_of_date')),
        balance: String(form.get('balance')),
        currency: 'USD',
      });
      target.reset();
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleCreateAccountEvent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    if (!selectedHouseholdId) return;
    setError('');
    const form = new FormData(target);
    try {
      await createAccountEvent(requiredString(form, 'account_id'), {
        event_date: requiredString(form, 'event_date'),
        amount: requiredString(form, 'amount'),
        currency: 'USD',
        event_type: requiredString(form, 'event_type'),
        description: optionalString(form, 'description'),
        projection_behavior: requiredString(form, 'projection_behavior'),
      });
      target.reset();
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleCreateProperty(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    if (!selectedHouseholdId) return;
    setError('');
    const form = new FormData(target);
    try {
      const propertyName = requiredString(form, 'property_name');
      const currentValue = optionalString(form, 'current_value');
      const valuationDate = optionalString(form, 'valuation_date') ?? today();
      const propertyAccount = await createAccount({
        household_id: selectedHouseholdId,
        name: propertyName,
        account_kind: 'asset',
        category: 'real_estate',
        liquidity_class: 'illiquid',
        expected_annual_yield: optionalString(form, 'expected_appreciation_rate'),
        currency: 'USD',
      });
      await createRealEstateProperty({
        account_id: propertyAccount.id,
        property_type: optionalString(form, 'property_type') ?? 'residence',
        purchase_date: optionalString(form, 'purchase_date'),
        purchase_price: optionalString(form, 'purchase_price'),
        down_payment: optionalString(form, 'down_payment'),
        expected_appreciation_rate: optionalString(form, 'expected_appreciation_rate'),
        property_tax_annual: optionalString(form, 'property_tax_annual'),
        insurance_annual: optionalString(form, 'insurance_annual'),
        maintenance_rate: optionalString(form, 'maintenance_rate'),
        hoa_monthly: optionalString(form, 'hoa_monthly'),
      });
      if (currentValue) {
        await createSnapshot(propertyAccount.id, {
          as_of_date: valuationDate,
          balance: currentValue,
          currency: 'USD',
        });
      }
      target.reset();
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleCreateMortgage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    if (!selectedHouseholdId) return;
    setError('');
    const form = new FormData(target);
    try {
      const originalPrincipal = requiredString(form, 'original_principal');
      const startDate = requiredString(form, 'start_date');
      const currentBalance = optionalString(form, 'current_balance') ?? originalPrincipal;
      const balanceDate = optionalString(form, 'balance_date') ?? startDate;
      const propertyAccountId = optionalString(form, 'property_account_id');
      const liabilityAccount = await createAccount({
        household_id: selectedHouseholdId,
        name: requiredString(form, 'mortgage_name'),
        account_kind: 'liability',
        category: 'mortgage',
        liquidity_class: 'debt',
        expected_annual_yield: '0.000000',
        currency: 'USD',
      });
      await createMortgageProfile({
        liability_account_id: liabilityAccount.id,
        property_account_id: propertyAccountId,
        original_principal: originalPrincipal,
        interest_rate: requiredString(form, 'interest_rate'),
        term_months: Number(requiredString(form, 'term_months')),
        start_date: startDate,
        monthly_payment: optionalString(form, 'monthly_payment'),
        rate_type: optionalString(form, 'rate_type') ?? 'fixed',
      });
      if (currentBalance) {
        await createSnapshot(liabilityAccount.id, {
          as_of_date: balanceDate,
          balance: currentBalance,
          currency: 'USD',
        });
      }
      target.reset();
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleCreateIncomeSource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    if (!selectedHouseholdId) return;
    setError('');
    const form = new FormData(target);
    try {
      await createIncomeSource({
        household_id: selectedHouseholdId,
        name: requiredString(form, 'income_name'),
        income_type: optionalString(form, 'income_type') ?? 'other',
        amount: requiredString(form, 'amount'),
        currency: 'USD',
        frequency: requiredString(form, 'frequency'),
        start_date: requiredString(form, 'start_date'),
        end_date: optionalString(form, 'end_date'),
        growth_rate: optionalString(form, 'growth_rate'),
      });
      target.reset();
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleCreateTaxRecord(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    if (!selectedHouseholdId) return;
    setError('');
    const form = new FormData(target);
    try {
      await createAnnualTaxRecord({
        household_id: selectedHouseholdId,
        tax_year: Number(requiredString(form, 'tax_year')),
        gross_income: optionalString(form, 'gross_income'),
        total_taxes_paid: requiredString(form, 'total_taxes_paid'),
        refund_or_amount_due: optionalString(form, 'refund_or_amount_due'),
        notes: optionalString(form, 'notes'),
      });
      target.reset();
      await refreshDashboard(selectedHouseholdId);
    } catch (err: unknown) {
      setError(String(err));
    }
  }

  async function handleGetExpenseEstimate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedHouseholdId) return;
    setError('');
    const form = new FormData(event.currentTarget);
    try {
      const result = await getAnnualExpenseEstimate(
        selectedHouseholdId,
        Number(requiredString(form, 'tax_year')),
      );
      setExpenseEstimate(result);
    } catch (err: unknown) {
      setExpenseEstimate(null);
      setError(String(err));
    }
  }

  async function handleGetProjection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedHouseholdId) return;
    setError('');
    const form = new FormData(event.currentTarget);
    try {
      const result = await getNetWorthProjection(
        selectedHouseholdId,
        Number(requiredString(form, 'start_year')),
        Number(requiredString(form, 'end_year')),
      );
      setProjection(result);
    } catch (err: unknown) {
      setProjection(null);
      setError(String(err));
    }
  }

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Netwise</p>
          <h1>Financial status from balance snapshots</h1>
          <p className="muted">Track household net worth without transaction categorization.</p>
        </div>
        {selectedHousehold && (
          <select
            value={selectedHouseholdId}
            onChange={(event) => setSelectedHouseholdId(event.target.value)}
            aria-label="Selected household"
          >
            {households.map((household) => (
              <option key={household.id} value={household.id}>
                {household.name}
              </option>
            ))}
          </select>
        )}
      </header>

      {error && <div className="error">{error}</div>}
      {loading && <div className="card">Loading…</div>}

      {!loading && households.length === 0 && (
        <section className="card narrow">
          <h2>Create your household</h2>
          <form onSubmit={handleCreateHousehold} className="form-row">
            <input name="name" placeholder="Home" required />
            <button type="submit">Create</button>
          </form>
        </section>
      )}

      {selectedHousehold && (
        <>
          <section className="summary-grid">
            <div className="metric-card">
              <span>Net worth</span>
              <strong>{formatMoney(netWorth?.net_worth)}</strong>
            </div>
            <div className="metric-card">
              <span>Assets</span>
              <strong>{formatMoney(netWorth?.assets_total)}</strong>
            </div>
            <div className="metric-card">
              <span>Liabilities</span>
              <strong>{formatMoney(netWorth?.liabilities_total)}</strong>
            </div>
          </section>

          <section className="card">
            <div className="section-header">
              <div>
                <h2>Financial trajectory</h2>
                <p className="muted">Known historical snapshots, optional interpolated estimates, and projected future net worth in one view.</p>
              </div>
              <div className="toggle-group">
                <label className="inline-toggle">
                  <input
                    type="checkbox"
                    checked={showInterpolatedHistory}
                    onChange={(event) => setShowInterpolatedHistory(event.target.checked)}
                  />
                  Show interpolated estimates
                </label>
                <label className="inline-toggle">
                  <input
                    type="checkbox"
                    checked={showProjectionOnTrajectory}
                    onChange={(event) => setShowProjectionOnTrajectory(event.target.checked)}
                  />
                  Show projection after run
                </label>
              </div>
            </div>
            {history?.points.length ? (
              <>
                <HistoryChart
                  points={history.points}
                  projectionPoints={showProjectionOnTrajectory ? projection?.points ?? [] : []}
                />
                <table className="spaced-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Net worth</th>
                      <th>Assets</th>
                      <th>Liabilities</th>
                      <th>Type</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.points.map((point) => (
                      <tr key={`${point.as_of_date}-${point.estimated ? 'estimate' : 'snapshot'}`} className={point.estimated ? 'estimated-row' : undefined}>
                        <td>{point.as_of_date}</td>
                        <td>{formatMoney(point.net_worth)}</td>
                        <td>{formatMoney(point.assets_total)}</td>
                        <td>{formatMoney(point.liabilities_total)}</td>
                        <td>{point.estimated ? 'Estimate' : 'Snapshot'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            ) : (
              <p className="muted">Add snapshots to see historical trend.</p>
            )}
          </section>

          <section className="card">
            <h2>Projection</h2>
            <p className="muted">Project net worth from current balances, account yields, mortgages, and future projection events.</p>
            <form onSubmit={handleGetProjection} className="form-row">
              <input
                name="start_year"
                inputMode="numeric"
                placeholder="Start year"
                defaultValue={new Date().getFullYear()}
                required
              />
              <input
                name="end_year"
                inputMode="numeric"
                placeholder="End year"
                defaultValue={new Date().getFullYear() + 10}
                required
              />
              <button type="submit">Run projection</button>
            </form>
            {projection?.points.length ? (
              <table className="spaced-table">
                <thead>
                  <tr>
                    <th>Year</th>
                    <th>Net worth</th>
                    <th>Assets</th>
                    <th>Liabilities</th>
                  </tr>
                </thead>
                <tbody>
                  {projection.points.map((point) => (
                    <tr key={point.year}>
                      <td>{point.year}</td>
                      <td>{formatMoney(point.net_worth)}</td>
                      <td>{formatMoney(point.assets_total)}</td>
                      <td>{formatMoney(point.liabilities_total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="muted">Run a projection to see future net worth points.</p>
            )}
          </section>

          <section className="grid two-column">
            <div className="card">
              <h2>Income sources</h2>
              {incomeSources.length ? (
                <table>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Type</th>
                      <th>Amount</th>
                      <th>Frequency</th>
                    </tr>
                  </thead>
                  <tbody>
                    {incomeSources.map((source) => (
                      <tr key={source.id}>
                        <td>{source.name}</td>
                        <td>{source.income_type}</td>
                        <td>{formatMoney(source.amount)}</td>
                        <td>{source.frequency}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted">No income sources yet.</p>
              )}
            </div>

            <div className="card">
              <h2>Annual tax records</h2>
              {taxRecords.length ? (
                <table>
                  <thead>
                    <tr>
                      <th>Year</th>
                      <th>Gross income</th>
                      <th>Taxes paid</th>
                      <th>Effective rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {taxRecords.map((record) => (
                      <tr key={record.id}>
                        <td>{record.tax_year}</td>
                        <td>{formatMoney(record.gross_income)}</td>
                        <td>{formatMoney(record.total_taxes_paid)}</td>
                        <td>{record.effective_tax_rate ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted">No tax records yet.</p>
              )}
            </div>
          </section>

          <section className="grid two-column">
            <div className="card">
              <h2>Add income source</h2>
              <form onSubmit={handleCreateIncomeSource} className="stacked-form">
                <input name="income_name" placeholder="Salary" required />
                <input name="income_type" placeholder="salary / bonus / other" />
                <input name="amount" inputMode="decimal" placeholder="Amount per pay period" required />
                <select name="frequency" defaultValue="monthly" required>
                  <option value="weekly">Weekly</option>
                  <option value="biweekly">Biweekly</option>
                  <option value="semimonthly">Semimonthly</option>
                  <option value="monthly">Monthly</option>
                  <option value="quarterly">Quarterly</option>
                  <option value="annually">Annually</option>
                </select>
                <label>
                  Start date
                  <input name="start_date" type="date" defaultValue={today()} required />
                </label>
                <label>
                  End date
                  <input name="end_date" type="date" />
                </label>
                <input name="growth_rate" inputMode="decimal" placeholder="Growth rate, e.g. 0.03" />
                <button type="submit">Add income source</button>
              </form>
            </div>

            <div className="card">
              <h2>Add tax record</h2>
              <form onSubmit={handleCreateTaxRecord} className="stacked-form">
                <input name="tax_year" inputMode="numeric" placeholder="Tax year" required />
                <input name="gross_income" inputMode="decimal" placeholder="Gross income" />
                <input name="total_taxes_paid" inputMode="decimal" placeholder="Total taxes paid" required />
                <input name="refund_or_amount_due" inputMode="decimal" placeholder="Refund or amount due" />
                <input name="notes" placeholder="Notes" />
                <button type="submit">Add tax record</button>
              </form>
            </div>
          </section>

          <section className="card">
            <h2>Expense estimate</h2>
            <p className="muted">Estimate annual living expense from gross income, taxes, and net worth change.</p>
            <form onSubmit={handleGetExpenseEstimate} className="form-row">
              <input
                name="tax_year"
                inputMode="numeric"
                placeholder="Tax year"
                defaultValue={taxRecords[0]?.tax_year ?? new Date().getFullYear() - 1}
                required
              />
              <button type="submit">Estimate expenses</button>
            </form>
            {expenseEstimate && (
              <section className="summary-grid compact-summary">
                <div className="metric-card">
                  <span>Estimated expense</span>
                  <strong>{formatMoney(expenseEstimate.estimated_living_expense)}</strong>
                </div>
                <div className="metric-card">
                  <span>Net worth change</span>
                  <strong>{formatMoney(expenseEstimate.net_worth_change)}</strong>
                </div>
                <div className="metric-card">
                  <span>Adjustments</span>
                  <strong>{formatMoney(expenseEstimate.adjustment_total)}</strong>
                </div>
              </section>
            )}
          </section>

          <section className="grid two-column">
            <div className="card">
              <h2>Real estate</h2>
              {properties.length ? (
                <table>
                  <thead>
                    <tr>
                      <th>Property</th>
                      <th>Type</th>
                      <th>Purchase price</th>
                      <th>Appreciation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {properties.map((property) => (
                      <tr key={property.id}>
                        <td>{accountNameById.get(property.account_id) ?? property.account_id}</td>
                        <td>{property.property_type}</td>
                        <td>{formatMoney(property.purchase_price)}</td>
                        <td>{property.expected_appreciation_rate ?? '—'}</td>
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
                <table>
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
                <select name="property_type" defaultValue="residence">
                  <option value="residence">Residence</option>
                  <option value="rental">Rental</option>
                  <option value="land">Land</option>
                  <option value="other">Other</option>
                </select>
                <label>
                  Purchase date
                  <input name="purchase_date" type="date" />
                </label>
                <input name="purchase_price" inputMode="decimal" placeholder="Purchase price" />
                <input name="down_payment" inputMode="decimal" placeholder="Down payment" />
                <input name="expected_appreciation_rate" inputMode="decimal" placeholder="Expected appreciation rate, e.g. 0.03" />
                <input name="property_tax_annual" inputMode="decimal" placeholder="Annual property tax" />
                <input name="insurance_annual" inputMode="decimal" placeholder="Annual insurance" />
                <input name="maintenance_rate" inputMode="decimal" placeholder="Maintenance rate, e.g. 0.01" />
                <input name="hoa_monthly" inputMode="decimal" placeholder="Monthly HOA" />
                <input name="current_value" inputMode="decimal" placeholder="Current valuation snapshot" />
                <label>
                  Valuation date
                  <input name="valuation_date" type="date" defaultValue={today()} />
                </label>
                <button type="submit">Add property</button>
              </form>
            </div>

            <div className="card">
              <h2>Add mortgage</h2>
              <p className="muted">Creates a mortgage liability account, mortgage profile, and initial balance snapshot.</p>
              <form onSubmit={handleCreateMortgage} className="stacked-form">
                <input name="mortgage_name" placeholder="Primary residence mortgage" required />
                <select name="property_account_id" defaultValue="">
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
                <select name="rate_type" defaultValue="fixed">
                  <option value="fixed">Fixed</option>
                  <option value="adjustable">Adjustable</option>
                </select>
                <input name="current_balance" inputMode="decimal" placeholder="Current balance; defaults to original principal" />
                <label>
                  Balance date
                  <input name="balance_date" type="date" />
                </label>
                <button type="submit">Add mortgage</button>
              </form>
            </div>
          </section>

          <section className="card">
            <h2>Accounts</h2>
            {netWorth?.accounts.length ? (
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Kind</th>
                    <th>Category</th>
                    <th>Yield</th>
                    <th>Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {netWorth.accounts.map((account) => (
                    <tr key={account.account_id}>
                      <td>{account.name}</td>
                      <td>{account.account_kind}</td>
                      <td>{account.category}</td>
                      <td>{accounts.find((item) => item.id === account.account_id)?.expected_annual_yield ?? '—'}</td>
                      <td>{formatMoney(account.balance)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="muted">No accounts yet.</p>
            )}
          </section>

          <section className="grid two-column">
            <div className="card">
              <h2>Projection events</h2>
              {accountEvents.length ? (
                <table>
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Account</th>
                      <th>Type</th>
                      <th>Amount</th>
                      <th>Behavior</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accountEvents.map((event) => (
                      <tr key={event.id}>
                        <td>{event.event_date}</td>
                        <td>{accountNameById.get(event.account_id) ?? event.account_id}</td>
                        <td>{event.event_type}</td>
                        <td>{formatMoney(event.amount)}</td>
                        <td>{event.projection_behavior}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted">No projection events yet.</p>
              )}
            </div>

            <div className="card">
              <h2>Add projection event</h2>
              <p className="muted">Capture planned future contributions, withdrawals, purchases, sales, and adjustments.</p>
              <form onSubmit={handleCreateAccountEvent} className="stacked-form">
                <select name="account_id" required defaultValue="">
                  <option value="" disabled>
                    Select account
                  </option>
                  {accounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.name}
                    </option>
                  ))}
                </select>
                <label>
                  Event date
                  <input name="event_date" type="date" defaultValue={today()} required />
                </label>
                <input name="amount" inputMode="decimal" placeholder="Amount" required />
                <select name="event_type" defaultValue="manual_projection_adjustment" required>
                  <option value="contribution">Contribution</option>
                  <option value="withdrawal">Withdrawal</option>
                  <option value="transfer">Transfer</option>
                  <option value="large_purchase">Large purchase</option>
                  <option value="asset_sale">Asset sale</option>
                  <option value="gift">Gift</option>
                  <option value="inheritance">Inheritance</option>
                  <option value="tax_payment">Tax payment</option>
                  <option value="account_added">Account added</option>
                  <option value="account_removed">Account removed</option>
                  <option value="manual_projection_adjustment">Manual projection adjustment</option>
                </select>
                <select name="projection_behavior" defaultValue="projection_only" required>
                  <option value="projection_only">Projection only</option>
                  <option value="historical_and_projection">Historical and projection</option>
                  <option value="historical_only">Historical only</option>
                </select>
                <input name="description" placeholder="Description" />
                <button type="submit">Add projection event</button>
              </form>
            </div>
          </section>

          <section className="grid two-column">
            <div className="card">
              <h2>Add account</h2>
              <form onSubmit={handleCreateAccount} className="stacked-form">
                <input name="name" placeholder="Fidelity 401k" required />
                <select name="account_kind" defaultValue="asset">
                  <option value="asset">Asset</option>
                  <option value="liability">Liability</option>
                </select>
                <input name="category" placeholder="retirement / real_estate / mortgage" required />
                <input name="liquidity_class" placeholder="retirement_liquid / real_estate / liability" required />
                <input name="expected_annual_yield" inputMode="decimal" placeholder="Expected annual yield, e.g. 0.05" />
                <button type="submit">Add account</button>
              </form>
            </div>

            <div className="card">
              <h2>Add snapshot</h2>
              <form onSubmit={handleCreateSnapshot} className="stacked-form">
                <select name="account_id" required defaultValue="">
                  <option value="" disabled>
                    Select account
                  </option>
                  {accounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.name}
                    </option>
                  ))}
                </select>
                <input name="as_of_date" type="date" defaultValue={today()} required />
                <input name="balance" placeholder="100000.00" required />
                <button type="submit">Add snapshot</button>
              </form>
            </div>
          </section>
        </>
      )}
    </main>
  );
}

export default App;
