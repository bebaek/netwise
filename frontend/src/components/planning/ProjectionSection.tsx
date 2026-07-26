import { useState, type FormEvent, type FormEventHandler } from 'react';
import type {
  Account,
  HouseholdPerson,
  NetWorthProjection,
  ProjectionTransfer,
  SpendingItem,
} from '../../api';
import {
  usePlanningProjectionData,
  usePlanningProjectionMutations,
} from '../../queries/planning';
import { formatMoney } from '../../utils/format';
import { ProjectionResults } from './ProjectionResults';
import { SpendingPlanSection } from './SpendingPlanSection';

function optionalFormString(form: FormData, key: string): string | undefined {
  const value = String(form.get(key) ?? '').trim();
  return value || undefined;
}

function requiredFormString(form: FormData, key: string): string {
  return String(form.get(key) ?? '').trim();
}

export function ProjectionSection({
  householdId,
  scenarioId,
  defaultDate,
  assetAccounts,
  accountNameById,
  spendingItems,
  spendingQueryError,
  spendingQueryPending,
  householdPeople,
  hasIncomeSources,
  onGetProjection,
  projectionRunning,
  projection,
  onInvalidateProjection,
}: {
  householdId: string;
  scenarioId: string;
  defaultDate: string;
  assetAccounts: Account[];
  accountNameById: ReadonlyMap<string, string>;
  spendingItems: SpendingItem[];
  spendingQueryError: unknown;
  spendingQueryPending: boolean;
  householdPeople: HouseholdPerson[];
  hasIncomeSources: boolean;
  onGetProjection: FormEventHandler<HTMLFormElement>;
  projectionRunning: boolean;
  projection: NetWorthProjection | null;
  onInvalidateProjection: () => void;
}) {
  const [projectionConfigError, setProjectionConfigError] = useState('');
  const planningProjectionData = usePlanningProjectionData(householdId, scenarioId);
  const planningProjectionMutations = usePlanningProjectionMutations(householdId, scenarioId);
  const projectionSettings = planningProjectionData.projectionSettings.data ?? null;
  const projectionTransfers = planningProjectionData.projectionTransfers.data ?? [];
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
<SpendingPlanSection
  householdId={householdId}
  scenarioId={scenarioId}
  spendingItems={spendingItems}
  queryError={spendingQueryError}
  queryPending={spendingQueryPending}
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
      <input type="hidden" name="scenario_id" value={scenarioId} />
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
      <input type="hidden" name="scenario_id" value={scenarioId} />
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

  {!hasIncomeSources && (
    <p className="projection-note">No active income sources are configured, so projected income and taxes are $0.00.</p>
  )}
  <p className="projection-note">Spending and taxes draw from their configured account first. If that account cannot cover the amount, the projection uses the default asset funding order.</p>

  <ProjectionResults projection={projection} />
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
    </>
  );
}
