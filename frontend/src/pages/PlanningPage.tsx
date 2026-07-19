import type { FormEventHandler } from 'react';
import type {
  Account,
  AccountEvent,
  AnnualTaxRecord,
  IncomeSource,
  NetWorthProjection,
  ProjectionSettings,
  ProjectionTransfer,
  RealEstateLiquidationStrategy,
  RealEstateSale,
} from '../api';
import { formatMoney } from '../utils/format';

export type AccountEventDraft = {
  id?: string;
  original_account_id?: string;
  account_id: string;
  event_date: string;
  amount: string;
  currency: string;
  event_type: string;
  description: string;
  projection_behavior: string;
};

const ACCOUNT_EVENT_TYPE_OPTIONS = [
  ['contribution', 'Contribution'],
  ['withdrawal', 'Withdrawal'],
  ['transfer', 'Transfer'],
  ['large_purchase', 'Large purchase'],
  ['asset_sale', 'Asset sale'],
  ['gift', 'Gift'],
  ['inheritance', 'Inheritance'],
  ['tax_payment', 'Tax payment'],
  ['account_added', 'Account added'],
  ['account_removed', 'Account removed'],
  ['manual_projection_adjustment', 'Manual projection adjustment'],
] as const;

const PROJECTION_BEHAVIOR_OPTIONS = [
  ['projection_only', 'Projection only'],
  ['historical_and_projection', 'Historical and projection'],
  ['historical_only', 'Historical only'],
] as const;

function eventTypeLabel(value: string): string {
  return ACCOUNT_EVENT_TYPE_OPTIONS.find(([optionValue]) => optionValue === value)?.[1] ?? value;
}

function projectionBehaviorLabel(value: string): string {
  return PROJECTION_BEHAVIOR_OPTIONS.find(([optionValue]) => optionValue === value)?.[1] ?? value;
}

function readableLabel(value: string): string {
  return value.split('_').map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(' ');
}

function formatRate(value: string): string {
  return `${(Number(value) * 100).toLocaleString(undefined, { maximumFractionDigits: 2 })}%`;
}

export function PlanningPage({
  defaultDate,
  accounts,
  assetAccounts,
  propertyAccounts,
  accountNameById,
  liquidationStrategies,
  onDeleteLiquidationStrategy,
  onUpsertLiquidationStrategy,
  projectionSettings,
  onSaveProjectionSettings,
  onGetProjection,
  incomeSources,
  projectionTransfers,
  taxRecords,
  projection,
  onCreateIncomeSource,
  onCreateProjectionTransfer,
  onDeleteProjectionTransfer,
  onCreateTaxRecord,
  realEstateSales,
  onDeleteRealEstateSale,
  onCreateRealEstateSale,
  accountEvents,
  accountEventDraft,
  onAccountEventDraft,
  onStartNewAccountEvent,
  onStartEditAccountEvent,
  onSaveAccountEvent,
  onDeleteAccountEvent,
}: {
  defaultDate: string;
  accounts: Account[];
  assetAccounts: Account[];
  propertyAccounts: Account[];
  accountNameById: ReadonlyMap<string, string>;
  liquidationStrategies: RealEstateLiquidationStrategy[];
  onDeleteLiquidationStrategy: (strategy: RealEstateLiquidationStrategy) => void | Promise<void>;
  onUpsertLiquidationStrategy: FormEventHandler<HTMLFormElement>;
  projectionSettings: ProjectionSettings | null;
  onSaveProjectionSettings: FormEventHandler<HTMLFormElement>;
  onGetProjection: FormEventHandler<HTMLFormElement>;
  incomeSources: IncomeSource[];
  projectionTransfers: ProjectionTransfer[];
  taxRecords: AnnualTaxRecord[];
  projection: NetWorthProjection | null;
  onCreateIncomeSource: FormEventHandler<HTMLFormElement>;
  onCreateProjectionTransfer: FormEventHandler<HTMLFormElement>;
  onDeleteProjectionTransfer: (transfer: ProjectionTransfer) => void | Promise<void>;
  onCreateTaxRecord: FormEventHandler<HTMLFormElement>;
  realEstateSales: RealEstateSale[];
  onDeleteRealEstateSale: (sale: RealEstateSale) => void | Promise<void>;
  onCreateRealEstateSale: FormEventHandler<HTMLFormElement>;
  accountEvents: AccountEvent[];
  accountEventDraft: AccountEventDraft | null;
  onAccountEventDraft: (draft: AccountEventDraft | null) => void;
  onStartNewAccountEvent: () => void;
  onStartEditAccountEvent: (event: AccountEvent) => void;
  onSaveAccountEvent: FormEventHandler<HTMLFormElement>;
  onDeleteAccountEvent: (event: AccountEvent) => void | Promise<void>;
}) {
  return (
    <>
<details className="advanced-planning">
  <summary>Advanced property sale automation</summary>
  <p className="muted">Configure automatic sales for liquidity shortfalls or runway optimization.</p>
  <section className="grid two-column">
  <div className="card">
    <h2>Automatic property sale strategies</h2>
    <p className="muted">Strategies either sell at a liquid-funding shortfall or jointly test annual March 1 sale schedules to delay retirement withdrawals as long as possible. Fixed-date sales take precedence.</p>
    {liquidationStrategies.length ? (
      <table tabIndex={0}>
        <thead>
          <tr><th>Property</th><th>Mode</th><th>Priority</th><th>Earliest date</th><th>Tax reserve</th><th>Status</th><th /></tr>
        </thead>
        <tbody>
          {liquidationStrategies.map((strategy) => (
            <tr key={strategy.id}>
              <td>{accountNameById.get(strategy.property_account_id) ?? strategy.property_account_id}</td>
              <td>{strategy.optimization_mode === 'maximize_liquid_runway' ? 'Maximize liquid runway' : 'Liquidity shortfall'}</td>
              <td>{strategy.priority}</td>
              <td>{strategy.earliest_sale_date ?? 'Any date'}</td>
              <td>{formatRate(strategy.estimated_tax_rate)}</td>
              <td>{strategy.enabled ? 'Enabled' : 'Disabled'}</td>
              <td><button type="button" className="danger-button" onClick={() => onDeleteLiquidationStrategy(strategy)}>Delete</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    ) : <p className="muted">No automatic property sales configured.</p>}
  </div>

  <div className="card">
    <h2>Configure automatic sale</h2>
    <form onSubmit={onUpsertLiquidationStrategy} className="stacked-form">
      <label>
        Property
        <select name="automatic_property_account_id" defaultValue="" required>
          <option value="" disabled>Select property</option>
          {propertyAccounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
        </select>
      </label>
      <label>
        Trigger mode
        <select name="automatic_optimization_mode" defaultValue="liquidity_shortfall" required>
          <option value="liquidity_shortfall">Sell only at a liquid-funding shortfall</option>
          <option value="maximize_liquid_runway">Optimize annual March 1 sales for liquid runway</option>
        </select>
      </label>
      <label>Priority<input name="automatic_priority" type="number" min="0" defaultValue="100" required /></label>
      <label>Earliest sale date<input name="automatic_earliest_sale_date" type="date" /></label>
      <label>
        Proceeds account
        <select name="automatic_proceeds_account_id" defaultValue="">
          <option value="">Default non-retirement liquid account</option>
          {assetAccounts.filter((account) => account.category !== 'real_estate' && account.category !== 'retirement').map((account) => (
            <option key={account.id} value={account.id}>{account.name}</option>
          ))}
        </select>
      </label>
      <label>
        Selling expense rate
        <input name="automatic_selling_expense_rate" inputMode="decimal" placeholder="Default 0.06" />
      </label>
      <label>Estimated sale-tax reserve rate<input name="automatic_estimated_tax_rate" inputMode="decimal" defaultValue="0.15" required /></label>
      <label><input name="automatic_enabled" type="checkbox" defaultChecked /> Enabled</label>
      <p className="muted">Primary residences are never enrolled automatically. Runway optimization jointly evaluates enabled optimized properties in priority order and reports its selected schedule with the projection.</p>
      <button type="submit" disabled={!propertyAccounts.length}>Save strategy</button>
    </form>
  </div>
  </section>
</details>

<section className="card">
  <h2>Projection</h2>
  <p className="muted">Project net worth from current balances, account yields, mortgages, estimated spending, projected income, taxes, and future projection events.</p>

  <div className="projection-panels">
    <form onSubmit={onSaveProjectionSettings} className="projection-form">
      <div>
        <h3>Projection assumptions</h3>
        <p className="muted">Saved defaults used when a projection run does not provide overrides.</p>
      </div>
      <label>
        Annual non-mortgage spending
        <input
          name="settings_annual_spending"
          inputMode="decimal"
          placeholder="70000"
          defaultValue={projectionSettings?.annual_spending ?? ''}
        />
      </label>
      <label>
        Spending inflation rate
        <input
          name="settings_spending_inflation_rate"
          inputMode="decimal"
          placeholder="0.03"
          defaultValue={projectionSettings?.spending_inflation_rate ?? ''}
        />
      </label>
      <label>
        Retirement date
        <input
          name="settings_retirement_date"
          type="date"
          defaultValue={projectionSettings?.retirement_date ?? ''}
        />
      </label>
      <label>
        Annual retirement non-mortgage spending
        <input
          name="settings_retirement_annual_spending"
          inputMode="decimal"
          placeholder="Use regular annual spending"
          defaultValue={projectionSettings?.retirement_annual_spending ?? ''}
        />
      </label>
      <p className="muted">Owner-occupied mortgage payments are projected separately from household spending, remain fixed, and stop after the final scheduled payment. The retirement date changes the non-mortgage spending phase. Use income-source dates for salary, pension, and Social Security timing. Retirement withdrawal penalties are only applied when configured as an account liquidation expense.</p>
      <label>
        Spending account
        <select name="settings_spending_account_id" defaultValue={projectionSettings?.spending_account_id ?? ''}>
          <option value="">Default funding order</option>
          {assetAccounts.map((account) => (
            <option key={account.id} value={account.id}>
              {account.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Tax payment account
        <select name="settings_tax_account_id" defaultValue={projectionSettings?.tax_account_id ?? ''}>
          <option value="">Default funding order</option>
          {assetAccounts.map((account) => (
            <option key={account.id} value={account.id}>
              {account.name}
            </option>
          ))}
        </select>
      </label>
      <button type="submit">Save settings</button>
    </form>

    <form onSubmit={onGetProjection} className="projection-form">
      <div>
        <h3>Run projection</h3>
        <p className="muted">Optional overrides apply only to this run.</p>
      </div>
      <label>
        Start year
        <input
          name="projection_start_year"
          inputMode="numeric"
          placeholder="2026"
          defaultValue={new Date().getFullYear()}
          required
        />
      </label>
      <label>
        End year
        <input
          name="projection_end_year"
          inputMode="numeric"
          placeholder="2036"
          defaultValue={new Date().getFullYear() + 10}
          required
        />
      </label>
      <label>
        Projection interval
        <select name="projection_interval" defaultValue="quarterly">
          <option value="annual">Annual</option>
          <option value="quarterly">Quarterly</option>
          <option value="monthly">Monthly</option>
        </select>
      </label>
      <label>
        Annual non-mortgage spending override
        <input
          name="projection_annual_spending"
          inputMode="decimal"
          placeholder="Use saved/default"
        />
      </label>
      <label>
        Inflation override
        <input
          name="projection_spending_inflation_rate"
          inputMode="decimal"
          placeholder="Use saved/default"
        />
      </label>
      <label>
        Spending account override
        <select name="projection_spending_account_id" defaultValue="">
          <option value="">Use saved/default</option>
          {assetAccounts.map((account) => (
            <option key={account.id} value={account.id}>
              {account.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Tax account override
        <select name="projection_tax_account_id" defaultValue="">
          <option value="">Use saved/default</option>
          {assetAccounts.map((account) => (
            <option key={account.id} value={account.id}>
              {account.name}
            </option>
          ))}
        </select>
      </label>
      <button type="submit">Run projection</button>
    </form>
  </div>

  {incomeSources.length === 0 && (
    <p className="projection-note">No active income sources are configured, so projected income and taxes are $0.00.</p>
  )}
  <p className="projection-note">Spending and taxes draw from their configured account first. If that account cannot cover the amount, the projection uses the default asset funding order.</p>

  {projection?.points.length ? (
    <>
      {projection.warnings.map((warning) => (
        <div className="projection-note" key={warning}><strong>Projection warning:</strong> {warning}</div>
      ))}
      {projection.retirement_date && (
        <div className="projection-note">
          <strong>Retirement phase:</strong> begins {projection.retirement_date}; first retirement-account withdrawal: {projection.first_retirement_withdrawal_date ?? 'none in projection'}; first unfunded period: {projection.first_unfunded_date ?? 'none in projection'}.
        </div>
      )}
      {projection.property_sale_optimization && (
        <div className="projection-note">
          <strong>Optimized March 1 property sales:</strong>{' '}
          {projection.property_sale_optimization.selected_sales
            .map((sale) => `${sale.property_name}: ${sale.sale_date ?? 'never'}`)
            .join(' · ')}
          {' '}({projection.property_sale_optimization.schedules_evaluated.toLocaleString()} schedules evaluated; first retirement withdrawal: {projection.property_sale_optimization.first_retirement_withdrawal_date ?? 'none in projection'})
        </div>
      )}
      <div className="desktop-table table-frame projection-table-frame">
        <table className="spaced-table projection-summary-table compact-table">
          <thead>
            <tr>
              <th>{projection.interval === 'annual' ? 'Year' : 'Period ending'}</th>
              <th>Net worth</th>
              <th>Assets</th>
              <th>Liabilities</th>
              <th>Income</th>
              <th>Taxes</th>
              <th>Total spending</th>
              <th>Mortgage portion</th>
              <th>Unfunded</th>
              <th>Net cash flow</th>
            </tr>
          </thead>
          <tbody>
            {projection.points.map((point) => (
              <tr key={point.as_of_date}>
                <td>
                  {projection.interval === 'annual' ? point.year : point.as_of_date}
                  {point.retirement_phase ? ' · Retirement' : ''}
                </td>
                <td>{formatMoney(point.net_worth)}</td>
                <td>{formatMoney(point.assets_total)}</td>
                <td>{formatMoney(point.liabilities_total)}</td>
                <td>{formatMoney(point.projected_income)}</td>
                <td>{formatMoney(point.projected_taxes)}</td>
                <td>{formatMoney(point.projected_spending)}</td>
                <td>{formatMoney(point.projected_mortgage_spending)}</td>
                <td>{formatMoney(point.projected_unfunded_cash_flow)}</td>
                <td>{formatMoney(point.net_cash_flow)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mobile-card-list projection-year-list">
        {projection.points.map((point) => (
          <article className="projection-year-card" key={point.year}>
            <div className="projection-year-header">
              <div>
                <span className="muted">Year</span>
                <strong>{point.year}</strong>
              </div>
              <div>
                <span className="muted">Net worth</span>
                <strong>{formatMoney(point.net_worth)}</strong>
              </div>
            </div>
            <dl className="projection-metric-list">
              <div>
                <dt>Assets</dt>
                <dd>{formatMoney(point.assets_total)}</dd>
              </div>
              <div>
                <dt>Liabilities</dt>
                <dd>{formatMoney(point.liabilities_total)}</dd>
              </div>
              <div>
                <dt>Income</dt>
                <dd>{formatMoney(point.projected_income)}</dd>
              </div>
              <div>
                <dt>Taxes</dt>
                <dd>{formatMoney(point.projected_taxes)}</dd>
              </div>
              <div>
                <dt>Total spending</dt>
                <dd>{formatMoney(point.projected_spending)}</dd>
              </div>
              <div>
                <dt>Mortgage portion</dt>
                <dd>{formatMoney(point.projected_mortgage_spending)}</dd>
              </div>
              <div>
                <dt>Unfunded</dt>
                <dd>{formatMoney(point.projected_unfunded_cash_flow)}</dd>
              </div>
              <div>
                <dt>Net cash flow</dt>
                <dd>{formatMoney(point.net_cash_flow)}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>

      <details className="cash-flow-details">
        <summary>Show projected account cash flows</summary>
        <div className="desktop-table table-frame cash-flow-table-frame">
          <table className="spaced-table compact-table" tabIndex={0}>
            <thead>
              <tr>
                <th>Year</th>
                <th>Account</th>
                <th>Cash flow</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {projection.points.flatMap((point) =>
                point.cash_flows.map((cashFlow, index) => (
                  <tr key={`${point.year}-${cashFlow.account_id}-${cashFlow.cash_flow_type}-${index}`}>
                    <td>{point.year}</td>
                    <td>{cashFlow.account_name}</td>
                    <td>{readableLabel(cashFlow.cash_flow_type)}</td>
                    <td>{formatMoney(cashFlow.amount)}</td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
        <div className="mobile-card-list cash-flow-card-list">
          {projection.points.flatMap((point) =>
            point.cash_flows.map((cashFlow, index) => (
              <article className="cash-flow-card" key={`${point.year}-${cashFlow.account_id}-${cashFlow.cash_flow_type}-${index}`}>
                <div>
                  <strong>{cashFlow.account_name}</strong>
                  <span>{point.year} · {readableLabel(cashFlow.cash_flow_type)}</span>
                </div>
                <strong>{formatMoney(cashFlow.amount)}</strong>
              </article>
            )),
          )}
        </div>
      </details>
    </>
  ) : (
    <p className="muted">Run a projection to see future net worth points.</p>
  )}
</section>

<section className="grid two-column">
  <div className="card">
    <h2>Recurring projection transfers</h2>
    <p className="muted">Move available cash between accounts after projected spending and taxes. Transfers do not count as income or spending and do not model tax effects.</p>
    {projectionTransfers.length ? (
      <table tabIndex={0}>
        <thead>
          <tr><th>Name</th><th>From</th><th>To</th><th>Annual amount</th><th>Dates</th><th /></tr>
        </thead>
        <tbody>
          {projectionTransfers.map((transfer) => (
            <tr key={transfer.id}>
              <td>{transfer.name}</td>
              <td>{accountNameById.get(transfer.from_account_id) ?? transfer.from_account_id}</td>
              <td>{accountNameById.get(transfer.to_account_id) ?? transfer.to_account_id}</td>
              <td>{formatMoney(transfer.annual_amount)}</td>
              <td>{transfer.start_date} – {transfer.end_date ?? 'ongoing'}</td>
              <td><button type="button" className="danger-button" onClick={() => onDeleteProjectionTransfer(transfer)}>Delete</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    ) : <p className="muted">No recurring transfers configured.</p>}
  </div>

  <div className="card">
    <h2>Add recurring transfer</h2>
    <form onSubmit={onCreateProjectionTransfer} className="stacked-form">
      <input name="transfer_name" placeholder="401k contribution" required />
      <label>
        From account
        <select name="transfer_from_account_id" defaultValue="" required>
          <option value="" disabled>Select source</option>
          {assetAccounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
        </select>
      </label>
      <label>
        To account
        <select name="transfer_to_account_id" defaultValue="" required>
          <option value="" disabled>Select destination</option>
          {assetAccounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
        </select>
      </label>
      <label>Annual amount<input name="transfer_annual_amount" inputMode="decimal" required /></label>
      <label>Start date<input name="transfer_start_date" type="date" defaultValue={defaultDate} required /></label>
      <label>End date<input name="transfer_end_date" type="date" /></label>
      <label>Annual growth rate<input name="transfer_growth_rate" inputMode="decimal" placeholder="0.00" /></label>
      <button type="submit" disabled={assetAccounts.length < 2}>Add transfer</button>
    </form>
  </div>
</section>

<section className="grid two-column">
  <div className="card">
    <h2>Income sources</h2>
    {incomeSources.length ? (
      <table tabIndex={0}>
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Amount</th>
            <th>Frequency</th>
            <th>Deposit account</th>
          </tr>
        </thead>
        <tbody>
          {incomeSources.map((source) => (
            <tr key={source.id}>
              <td>{source.name}</td>
              <td>{source.income_type}</td>
              <td>{formatMoney(source.amount)}</td>
              <td>{source.frequency}</td>
              <td>{source.deposit_account_id ? accountNameById.get(source.deposit_account_id) ?? source.deposit_account_id : 'Default'}</td>
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
      <table tabIndex={0}>
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
    <form onSubmit={onCreateIncomeSource} className="stacked-form">
      <input name="income_name" placeholder="Salary" required />
      <input name="income_type" placeholder="salary / bonus / other" />
      <input name="amount" inputMode="decimal" placeholder="Amount per pay period" required />
      <select name="frequency" aria-label="Income frequency" defaultValue="monthly" required>
        <option value="weekly">Weekly</option>
        <option value="biweekly">Biweekly</option>
        <option value="semimonthly">Semimonthly</option>
        <option value="monthly">Monthly</option>
        <option value="quarterly">Quarterly</option>
        <option value="annually">Annually</option>
      </select>
      <label>
        Start date
        <input name="start_date" type="date" defaultValue={defaultDate} required />
      </label>
      <label>
        End date
        <input name="end_date" type="date" />
      </label>
      <input name="growth_rate" inputMode="decimal" placeholder="Growth rate, e.g. 0.03" />
      <select name="deposit_account_id" aria-label="Income deposit account" defaultValue="">
        <option value="">Default deposit account</option>
        {assetAccounts.map((account) => (
          <option key={account.id} value={account.id}>
            {account.name}
          </option>
        ))}
      </select>
      <button type="submit">Add income source</button>
    </form>
  </div>

  <div className="card">
    <h2>Add tax record</h2>
    <form onSubmit={onCreateTaxRecord} className="stacked-form">
      <input name="tax_year" inputMode="numeric" placeholder="Tax year" required />
      <input name="gross_income" inputMode="decimal" placeholder="Gross income" />
      <input name="total_taxes_paid" inputMode="decimal" placeholder="Total taxes paid" required />
      <input name="refund_or_amount_due" inputMode="decimal" placeholder="Refund or amount due" />
      <input name="notes" placeholder="Notes" />
      <button type="submit">Add tax record</button>
    </form>
  </div>
</section>

<section className="grid two-column">
  <div className="card">
    <h2>Planned property sales</h2>
    <p className="muted">A sale pays off its linked mortgage, deducts selling costs and an estimated tax reserve, and transfers net proceeds to the selected account.</p>
    {realEstateSales.length ? (
      <table tabIndex={0}>
        <thead>
          <tr><th>Property</th><th>Date</th><th>Price</th><th>Tax reserve</th><th>Proceeds account</th><th /></tr>
        </thead>
        <tbody>
          {realEstateSales.map((sale) => (
            <tr key={sale.id}>
              <td>{accountNameById.get(sale.property_account_id) ?? sale.property_account_id}</td>
              <td>{sale.sale_date}</td>
              <td>{formatMoney(sale.gross_sale_price)}</td>
              <td>{formatRate(sale.estimated_tax_rate)}</td>
              <td>{accountNameById.get(sale.proceeds_account_id) ?? sale.proceeds_account_id}</td>
              <td><button type="button" className="danger-button" onClick={() => onDeleteRealEstateSale(sale)}>Delete</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    ) : <p className="muted">No property sales planned.</p>}
  </div>

  <div className="card">
    <h2>Plan property sale</h2>
    <form onSubmit={onCreateRealEstateSale} className="stacked-form">
      <select name="property_account_id" aria-label="Property to sell" defaultValue="" required>
        <option value="" disabled>Select property</option>
        {propertyAccounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
      </select>
      <label>Sale date<input name="sale_date" type="date" required /></label>
      <input name="gross_sale_price" inputMode="decimal" placeholder="Gross sale price" required />
      <label>
        Proceeds account
        <select name="proceeds_account_id" defaultValue="">
          <option value="">Default non-retirement liquid account</option>
          {assetAccounts.filter((account) => account.category !== 'real_estate').map((account) => (
            <option key={account.id} value={account.id}>{account.name}</option>
          ))}
        </select>
      </label>
      <input name="selling_expense_rate" inputMode="decimal" placeholder="Selling expense rate, e.g. 0.06" />
      <label>
        Estimated sale-tax reserve rate
        <input name="estimated_tax_rate" inputMode="decimal" defaultValue="0.15" required />
      </label>
      <p className="muted">Defaults to 15% of gross sale price when tax basis and depreciation details are unavailable.</p>
      <button type="submit" disabled={!propertyAccounts.length}>Plan sale</button>
    </form>
  </div>
</section>

<section className="card projection-events-card">
  <div className="section-header">
    <div>
      <h2>Projection events</h2>
      <p className="muted">Capture planned future contributions, withdrawals, purchases, sales, and adjustments.</p>
    </div>
    <button type="button" onClick={onStartNewAccountEvent} disabled={!accounts.length}>
      Add event
    </button>
  </div>

  {accountEventDraft && (
    <form onSubmit={onSaveAccountEvent} className="event-editor-card">
      <div className="section-header">
        <div>
          <h3>{accountEventDraft.id ? 'Edit projection event' : 'Add projection event'}</h3>
          <p className="muted">Use positive amounts; outflow event types are applied as withdrawals in projections.</p>
        </div>
        <button type="button" className="secondary-button" onClick={() => onAccountEventDraft(null)}>
          Cancel
        </button>
      </div>
      <div className="event-editor-grid">
        <label>
          Account
          <select
            required
            value={accountEventDraft.account_id}
            onChange={(changeEvent) =>
              onAccountEventDraft({ ...accountEventDraft, account_id: changeEvent.target.value })
            }
          >
            {!accountEventDraft.account_id && <option value="">Select account</option>}
            {accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Event date
          <input
            required
            type="date"
            value={accountEventDraft.event_date}
            onChange={(changeEvent) =>
              onAccountEventDraft({ ...accountEventDraft, event_date: changeEvent.target.value })
            }
          />
        </label>
        <label>
          Amount
          <input
            required
            inputMode="decimal"
            placeholder="2500.00"
            value={accountEventDraft.amount}
            onChange={(changeEvent) =>
              onAccountEventDraft({ ...accountEventDraft, amount: changeEvent.target.value })
            }
          />
        </label>
        <label>
          Type
          <select
            required
            value={accountEventDraft.event_type}
            onChange={(changeEvent) =>
              onAccountEventDraft({ ...accountEventDraft, event_type: changeEvent.target.value })
            }
          >
            {ACCOUNT_EVENT_TYPE_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Projection behavior
          <select
            required
            value={accountEventDraft.projection_behavior}
            onChange={(changeEvent) =>
              onAccountEventDraft({ ...accountEventDraft, projection_behavior: changeEvent.target.value })
            }
          >
            {PROJECTION_BEHAVIOR_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Description
          <input
            placeholder="Optional note"
            value={accountEventDraft.description}
            onChange={(changeEvent) =>
              onAccountEventDraft({ ...accountEventDraft, description: changeEvent.target.value })
            }
          />
        </label>
      </div>
      <div className="action-row">
        <button type="submit" disabled={!accountEventDraft.account_id}>Save event</button>
        <button type="button" className="secondary-button" onClick={() => onAccountEventDraft(null)}>
          Cancel
        </button>
      </div>
    </form>
  )}

  {accountEvents.length ? (
    <>
      <div className="desktop-table table-frame sticky-actions">
        <table className="editable-table compact-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Account</th>
              <th>Type</th>
              <th>Amount</th>
              <th>Behavior</th>
              <th>Description</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {accountEvents.map((event) => (
              <tr key={event.id}>
                <td>{event.event_date}</td>
                <td>{accountNameById.get(event.account_id) ?? event.account_id}</td>
                <td>{eventTypeLabel(event.event_type)}</td>
                <td>{formatMoney(event.amount)}</td>
                <td>{projectionBehaviorLabel(event.projection_behavior)}</td>
                <td>{event.description || '—'}</td>
                <td>
                  <div className="action-row">
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => onStartEditAccountEvent(event)}
                    >
                      Edit
                    </button>
                    <button type="button" className="danger-button" onClick={() => onDeleteAccountEvent(event)}>
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mobile-card-list">
        {accountEvents.map((event) => (
          <article className="event-card" key={event.id}>
            <div className="event-card-header">
              <div>
                <strong className="event-card-title">{eventTypeLabel(event.event_type)}</strong>
                <span>{event.event_date}</span>
              </div>
              <strong className="event-card-amount">{formatMoney(event.amount)}</strong>
            </div>
            <dl className="event-card-meta">
              <div>
                <dt>Account</dt>
                <dd>{accountNameById.get(event.account_id) ?? event.account_id}</dd>
              </div>
              <div>
                <dt>Behavior</dt>
                <dd>{projectionBehaviorLabel(event.projection_behavior)}</dd>
              </div>
              {event.description && (
                <div>
                  <dt>Description</dt>
                  <dd>{event.description}</dd>
                </div>
              )}
            </dl>
            <div className="event-card-actions">
              <button type="button" className="secondary-button" onClick={() => onStartEditAccountEvent(event)}>
                Edit
              </button>
              <button type="button" className="danger-button" onClick={() => onDeleteAccountEvent(event)}>
                Delete
              </button>
            </div>
          </article>
        ))}
      </div>
    </>
  ) : (
    <p className="muted">No projection events yet.</p>
  )}
</section>
    </>
  );
}
