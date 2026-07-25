import { useState, type FormEvent, type FormEventHandler } from 'react';
import type {
  Account,
  NetWorthProjection,
  ProjectionTransfer,
  RealEstateLiquidationStrategy,
  RealEstateSale,
} from '../api';
import { PlanningEventsSection } from '../components/planning/PlanningEventsSection';
import { SocialSecuritySection } from '../components/planning/SocialSecuritySection';
import { SpendingPlanSection } from '../components/planning/SpendingPlanSection';
import {
  usePlanningBudgetData,
  usePlanningBudgetMutations,
  usePlanningPeopleData,
  usePlanningPeopleMutations,
  usePlanningProjectionData,
  usePlanningProjectionMutations,
} from '../queries/planning';
import { usePlanningRealEstateData, usePlanningRealEstateMutations } from '../queries/realEstate';
import { formatMoney } from '../utils/format';

function optionalFormString(form: FormData, key: string): string | undefined {
  const value = String(form.get(key) ?? '').trim();
  return value || undefined;
}

function requiredFormString(form: FormData, key: string): string {
  return String(form.get(key) ?? '').trim();
}

function readableLabel(value: string): string {
  return value.split('_').map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(' ');
}

function formatRate(value: string): string {
  return `${(Number(value) * 100).toLocaleString(undefined, { maximumFractionDigits: 2 })}%`;
}

export function PlanningPage({
  householdId,
  defaultDate,
  accounts,
  assetAccounts,
  propertyAccounts,
  accountNameById,
  onGetProjection,
  projectionRunning,
  projection,
  onInvalidateProjection,
}: {
  householdId: string;
  defaultDate: string;
  accounts: Account[];
  assetAccounts: Account[];
  propertyAccounts: Account[];
  accountNameById: ReadonlyMap<string, string>;
  onGetProjection: FormEventHandler<HTMLFormElement>;
  projectionRunning: boolean;
  projection: NetWorthProjection | null;
  onInvalidateProjection: () => void;
}) {
  const [projectionConfigError, setProjectionConfigError] = useState('');
  const planningProjectionData = usePlanningProjectionData(householdId);
  const planningProjectionMutations = usePlanningProjectionMutations(householdId);
  const projectionSettings = planningProjectionData.projectionSettings.data ?? null;
  const projectionTransfers = planningProjectionData.projectionTransfers.data ?? [];
  const [incomeError, setIncomeError] = useState('');
  const planningPeopleData = usePlanningPeopleData(householdId);
  const planningPeopleMutations = usePlanningPeopleMutations(householdId);
  const incomeSources = planningPeopleData.incomeSources.data ?? [];
  const householdPeople = planningPeopleData.householdPeople.data ?? [];
  const socialSecurityEstimates = planningPeopleData.socialSecurityEstimates.data ?? [];
  const [taxRecordError, setTaxRecordError] = useState('');
  const planningBudgetData = usePlanningBudgetData(householdId);
  const planningBudgetMutations = usePlanningBudgetMutations(householdId);
  const spendingItems = planningBudgetData.spendingItems.data ?? [];
  const taxRecords = planningBudgetData.taxRecords.data ?? [];
  const [realEstateError, setRealEstateError] = useState('');
  const planningRealEstateData = usePlanningRealEstateData(householdId);
  const planningRealEstateMutations = usePlanningRealEstateMutations(householdId);
  const realEstateSales = planningRealEstateData.sales.data ?? [];
  const liquidationStrategies = planningRealEstateData.liquidationStrategies.data ?? [];
  const workingSpendingTotal = spendingItems.reduce(
    (total, item) => total + Number(item.annual_amount),
    0,
  );
  const retirementSpendingTotal = spendingItems.reduce(
    (total, item) => total + Number(item.retirement_annual_amount ?? item.annual_amount),
    0,
  );
  const spendingMode = projectionSettings?.spending_mode
    ?? (projectionSettings?.annual_spending == null ? 'itemized' : 'manual');
  const manualWorkingSpending = Number(projectionSettings?.annual_spending ?? 0);
  const manualRetirementSpending = Number(
    projectionSettings?.retirement_annual_spending ?? projectionSettings?.annual_spending ?? 0,
  );
  const defaultProjectionEndYear = householdPeople.length
    ? Math.max(...householdPeople.map((person) => Number(person.date_of_birth.slice(0, 4)) + 100))
    : new Date().getFullYear() + 20;

  async function onCreateProjectionTransfer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const form = new FormData(target);
    setProjectionConfigError('');
    try {
      await planningProjectionMutations.createTransfer.mutateAsync({
        household_id: householdId,
        name: requiredFormString(form, 'transfer_name'),
        from_account_id: requiredFormString(form, 'transfer_from_account_id'),
        to_account_id: requiredFormString(form, 'transfer_to_account_id'),
        annual_amount: requiredFormString(form, 'transfer_annual_amount'),
        start_date: requiredFormString(form, 'transfer_start_date'),
        end_date: optionalFormString(form, 'transfer_end_date'),
        growth_rate: optionalFormString(form, 'transfer_growth_rate'),
      });
      target.reset();
      onInvalidateProjection();
    } catch (mutationError: unknown) {
      setProjectionConfigError(String(mutationError));
    }
  }

  async function onDeleteProjectionTransfer(transfer: ProjectionTransfer) {
    if (!window.confirm(`Delete recurring transfer ${transfer.name}?`)) return;
    setProjectionConfigError('');
    try {
      await planningProjectionMutations.deleteTransfer.mutateAsync(transfer);
      onInvalidateProjection();
    } catch (mutationError: unknown) {
      setProjectionConfigError(String(mutationError));
    }
  }

  async function onSpendingModeChange(mode: 'manual' | 'itemized') {
    setProjectionConfigError('');
    try {
      await planningProjectionMutations.saveSettings.mutateAsync({
        annual_spending: projectionSettings?.annual_spending ?? undefined,
        spending_mode: mode,
        spending_inflation_rate: projectionSettings?.spending_inflation_rate ?? undefined,
        retirement_date: projectionSettings?.retirement_date ?? undefined,
        retirement_annual_spending: projectionSettings?.retirement_annual_spending ?? undefined,
        spending_account_id: projectionSettings?.spending_account_id ?? undefined,
        tax_account_id: projectionSettings?.tax_account_id ?? undefined,
      });
      onInvalidateProjection();
    } catch (mutationError: unknown) {
      setProjectionConfigError(String(mutationError));
    }
  }

  async function onSaveProjectionSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setProjectionConfigError('');
    try {
      await planningProjectionMutations.saveSettings.mutateAsync({
        annual_spending: optionalFormString(form, 'settings_annual_spending'),
        spending_mode: requiredFormString(form, 'settings_spending_mode') as 'manual' | 'itemized',
        spending_inflation_rate: optionalFormString(form, 'settings_spending_inflation_rate'),
        retirement_date: optionalFormString(form, 'settings_retirement_date'),
        retirement_annual_spending: optionalFormString(
          form,
          'settings_retirement_annual_spending',
        ),
        spending_account_id: optionalFormString(form, 'settings_spending_account_id'),
        tax_account_id: optionalFormString(form, 'settings_tax_account_id'),
      });
      onInvalidateProjection();
    } catch (mutationError: unknown) {
      setProjectionConfigError(String(mutationError));
    }
  }

  async function onCreateIncomeSource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const form = new FormData(target);
    setIncomeError('');
    try {
      await planningPeopleMutations.createIncome.mutateAsync({
        household_id: householdId,
        name: requiredFormString(form, 'income_name'),
        income_type: optionalFormString(form, 'income_type') ?? 'other',
        amount: requiredFormString(form, 'amount'),
        currency: 'USD',
        frequency: requiredFormString(form, 'frequency'),
        start_date: requiredFormString(form, 'start_date'),
        end_date: optionalFormString(form, 'end_date'),
        growth_rate: optionalFormString(form, 'growth_rate'),
        deposit_account_id: optionalFormString(form, 'deposit_account_id'),
      });
      target.reset();
    } catch (mutationError: unknown) {
      setIncomeError(String(mutationError));
    }
  }

  async function onCreateTaxRecord(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const form = new FormData(target);
    setTaxRecordError('');
    try {
      await planningBudgetMutations.createTaxRecord.mutateAsync({
        household_id: householdId,
        tax_year: Number(requiredFormString(form, 'tax_year')),
        gross_income: optionalFormString(form, 'gross_income'),
        total_taxes_paid: requiredFormString(form, 'total_taxes_paid'),
        refund_or_amount_due: optionalFormString(form, 'refund_or_amount_due'),
        notes: optionalFormString(form, 'notes'),
      });
      target.reset();
    } catch (mutationError: unknown) {
      setTaxRecordError(String(mutationError));
    }
  }

  async function onUpsertLiquidationStrategy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const form = new FormData(target);
    const propertyAccountId = requiredFormString(form, 'automatic_property_account_id');
    setRealEstateError('');
    try {
      await planningRealEstateMutations.upsertLiquidationStrategy.mutateAsync({
        propertyAccountId,
        payload: {
          enabled: form.get('automatic_enabled') === 'on',
          optimization_mode: requiredFormString(
            form,
            'automatic_optimization_mode',
          ) as 'liquidity_shortfall' | 'maximize_liquid_runway',
          priority: Number(requiredFormString(form, 'automatic_priority')),
          earliest_sale_date: optionalFormString(form, 'automatic_earliest_sale_date'),
          proceeds_account_id: optionalFormString(form, 'automatic_proceeds_account_id'),
          selling_expense_rate: optionalFormString(form, 'automatic_selling_expense_rate'),
          estimated_tax_rate: requiredFormString(form, 'automatic_estimated_tax_rate'),
        },
      });
      target.reset();
    } catch (mutationError: unknown) {
      setRealEstateError(String(mutationError));
    }
  }

  async function onDeleteLiquidationStrategy(strategy: RealEstateLiquidationStrategy) {
    if (!window.confirm('Delete this automatic property sale strategy?')) return;
    setRealEstateError('');
    try {
      await planningRealEstateMutations.deleteLiquidationStrategy.mutateAsync(strategy);
    } catch (mutationError: unknown) {
      setRealEstateError(String(mutationError));
    }
  }

  async function onCreateRealEstateSale(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const form = new FormData(target);
    setRealEstateError('');
    try {
      await planningRealEstateMutations.createSale.mutateAsync({
        property_account_id: requiredFormString(form, 'property_account_id'),
        sale_date: requiredFormString(form, 'sale_date'),
        gross_sale_price: requiredFormString(form, 'gross_sale_price'),
        proceeds_account_id: optionalFormString(form, 'proceeds_account_id'),
        selling_expense_rate: optionalFormString(form, 'selling_expense_rate'),
        estimated_tax_rate: requiredFormString(form, 'estimated_tax_rate'),
      });
      target.reset();
    } catch (mutationError: unknown) {
      setRealEstateError(String(mutationError));
    }
  }

  async function onDeleteRealEstateSale(sale: RealEstateSale) {
    if (!window.confirm(`Delete the planned sale on ${sale.sale_date}?`)) return;
    setRealEstateError('');
    try {
      await planningRealEstateMutations.deleteSale.mutateAsync(sale);
    } catch (mutationError: unknown) {
      setRealEstateError(String(mutationError));
    }
  }

  return (
    <>
      {projectionConfigError && (
        <div className="error" role="alert">{projectionConfigError}</div>
      )}
      {planningProjectionData.projectionTransfers.error && (
        <div className="error" role="alert">
          {String(planningProjectionData.projectionTransfers.error)}
        </div>
      )}
      {planningProjectionData.projectionSettings.error && (
        <div className="error" role="alert">
          {String(planningProjectionData.projectionSettings.error)}
        </div>
      )}
      {(planningProjectionData.projectionTransfers.isPending
        || planningProjectionData.projectionSettings.isPending) && (
        <div className="card" role="status">Loading projection configuration…</div>
      )}
      {incomeError && <div className="error" role="alert">{incomeError}</div>}
      {planningPeopleData.incomeSources.error && (
        <div className="error" role="alert">{String(planningPeopleData.incomeSources.error)}</div>
      )}
      {planningPeopleData.incomeSources.isPending && (
        <div className="card" role="status">Loading income sources…</div>
      )}
      {taxRecordError && <div className="error" role="alert">{taxRecordError}</div>}
      {planningBudgetData.taxRecords.error && (
        <div className="error" role="alert">{String(planningBudgetData.taxRecords.error)}</div>
      )}
      {planningBudgetData.taxRecords.isPending && (
        <div className="card" role="status">Loading tax records…</div>
      )}
      {realEstateError && <div className="error" role="alert">{realEstateError}</div>}
      {planningRealEstateData.sales.error && (
        <div className="error" role="alert">{String(planningRealEstateData.sales.error)}</div>
      )}
      {planningRealEstateData.liquidationStrategies.error && (
        <div className="error" role="alert">
          {String(planningRealEstateData.liquidationStrategies.error)}
        </div>
      )}
      {(planningRealEstateData.sales.isPending
        || planningRealEstateData.liquidationStrategies.isPending) && (
        <div className="card" role="status">Loading real estate plans…</div>
      )}
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
              <td><button type="button" className="danger-button" disabled={planningRealEstateMutations.isPending} onClick={() => onDeleteLiquidationStrategy(strategy)}>Delete</button></td>
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
      <button type="submit" disabled={!propertyAccounts.length || planningRealEstateMutations.isPending}>Save strategy</button>
    </form>
  </div>
  </section>
</details>

<SpendingPlanSection
  householdId={householdId}
  spendingItems={spendingItems}
  queryError={planningBudgetData.spendingItems.error}
  queryPending={planningBudgetData.spendingItems.isPending}
  spendingMode={spendingMode}
  workingSpendingTotal={workingSpendingTotal}
  retirementSpendingTotal={retirementSpendingTotal}
  manualWorkingSpending={manualWorkingSpending}
  manualRetirementSpending={manualRetirementSpending}
  onInvalidateProjection={onInvalidateProjection}
/>

<section className="card">
  <h2>Projection</h2>
  <p className="muted">Project net worth from current balances, account yields, mortgages, estimated spending, projected income, taxes, and future projection events.</p>

  <div className="projection-panels">
    <form
      key={projectionSettings?.updated_at ?? 'new'}
      onSubmit={onSaveProjectionSettings}
      className="projection-form"
      aria-busy={planningProjectionMutations.saveSettings.isPending}
    >
      <div>
        <h3>Projection assumptions</h3>
        <p className="muted">Saved defaults used when a projection run does not provide overrides.</p>
      </div>
      <label>
        Spending calculation
        <select
          name="settings_spending_mode"
          value={spendingMode}
          disabled={planningProjectionData.projectionSettings.isPending
            || planningProjectionMutations.saveSettings.isPending}
          onChange={(event) => onSpendingModeChange(event.target.value as 'manual' | 'itemized')}
        >
          <option value="manual">Use manual household total</option>
          <option value="itemized">Automatically sum spending items</option>
        </select>
      </label>
      <label>
        Manual annual non-mortgage spending
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
        Manual annual retirement non-mortgage spending
        <input
          name="settings_retirement_annual_spending"
          inputMode="decimal"
          placeholder="Use regular annual spending"
          defaultValue={projectionSettings?.retirement_annual_spending ?? ''}
        />
      </label>
      <p className="muted">The spending calculation selection saves immediately. The manual total is the default when provided. Select automatic item sum to derive spending from the granular plan. Owner-occupied mortgage payments are always projected separately, remain fixed, and stop after the final scheduled payment.</p>
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
      <button type="submit" disabled={planningProjectionData.projectionSettings.isPending
        || planningProjectionMutations.saveSettings.isPending}>Save settings</button>
    </form>

    <form
      onSubmit={onGetProjection}
      className="projection-form"
      aria-busy={projectionRunning}
    >
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
          key={defaultProjectionEndYear}
          name="projection_end_year"
          inputMode="numeric"
          placeholder={String(defaultProjectionEndYear)}
          defaultValue={defaultProjectionEndYear}
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
      <button type="submit" className="projection-run-button" disabled={projectionRunning}>
        {projectionRunning && <span className="loading-spinner" aria-hidden="true" />}
        {projectionRunning ? 'Running projection…' : 'Run projection'}
      </button>
      {projectionRunning && (
        <p className="projection-run-status" role="status" aria-live="polite">
          Calculating your projection. Longer date ranges and optimization strategies may take some time.
        </p>
      )}
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
      <div className="projection-note">
        <strong>Spending source:</strong> {projection.spending_mode === 'itemized' ? 'automatic sum of spending items' : 'manual household total'}.
      </div>
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
              <th>Property tax &amp; insurance</th>
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
                <td>{formatMoney(point.projected_owner_property_spending)}</td>
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
                <dt>Property tax &amp; insurance</dt>
                <dd>{formatMoney(point.projected_owner_property_spending)}</dd>
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
        <summary>Show projected spending breakdown</summary>
        <div className="table-frame cash-flow-table-frame">
          <table className="spaced-table compact-table" tabIndex={0}>
            <thead>
              <tr><th>Period</th><th>Category</th><th>Item</th><th>Amount</th></tr>
            </thead>
            <tbody>
              {projection.points.flatMap((point) =>
                point.projected_spending_breakdown.map((item, index) => (
                  <tr key={`${point.as_of_date}-${item.category}-${item.name}-${index}`}>
                    <td>{projection.interval === 'annual' ? point.year : point.as_of_date}</td>
                    <td>{readableLabel(item.category)}</td>
                    <td>{item.name}</td>
                    <td>{formatMoney(item.amount)}</td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      </details>

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
              <td><button
                type="button"
                className="danger-button"
                disabled={planningProjectionMutations.isPending}
                onClick={() => onDeleteProjectionTransfer(transfer)}
              >Delete</button></td>
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
      <button
        type="submit"
        disabled={assetAccounts.length < 2 || planningProjectionMutations.isPending}
      >Add transfer</button>
    </form>
  </div>
</section>

<SocialSecuritySection
  householdId={householdId}
  householdPeople={householdPeople}
  incomeSources={incomeSources}
  estimates={socialSecurityEstimates}
  assetAccounts={assetAccounts}
  peopleError={planningPeopleData.householdPeople.error}
  estimatesError={planningPeopleData.socialSecurityEstimates.error}
  peoplePending={planningPeopleData.householdPeople.isPending}
  estimatesPending={planningPeopleData.socialSecurityEstimates.isPending}
/>

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
      <button type="submit" disabled={planningPeopleMutations.isPending}>Add income source</button>
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
      <button type="submit" disabled={planningBudgetMutations.isPending}>Add tax record</button>
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
              <td><button type="button" className="danger-button" disabled={planningRealEstateMutations.isPending} onClick={() => onDeleteRealEstateSale(sale)}>Delete</button></td>
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
      <button type="submit" disabled={!propertyAccounts.length || planningRealEstateMutations.isPending}>Plan sale</button>
    </form>
  </div>
</section>

<PlanningEventsSection
  householdId={householdId}
  defaultDate={defaultDate}
  accounts={accounts}
  accountNameById={accountNameById}
/>
    </>
  );
}
