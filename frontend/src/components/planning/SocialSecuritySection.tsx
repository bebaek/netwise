import { useState, type FormEvent } from 'react';
import type {
  Account,
  HouseholdPerson,
  IncomeSource,
  SocialSecurityEstimate,
  SocialSecurityEstimateInput,
} from '../../api';
import { usePlanningPeopleMutations } from '../../queries/planning';
import { formatMoney } from '../../utils/format';

function optionalFormString(form: FormData, key: string): string | undefined {
  const value = String(form.get(key) ?? '').trim();
  return value || undefined;
}

function requiredFormString(form: FormData, key: string): string {
  return String(form.get(key) ?? '').trim();
}

function estimateInput(form: FormData, householdId: string): SocialSecurityEstimateInput {
  const workYears = optionalFormString(form, 'completed_work_years');
  return {
    household_id: householdId,
    person_id: requiredFormString(form, 'social_security_person_id'),
    calculation_mode: requiredFormString(form, 'social_security_mode') as 'manual' | 'ballpark',
    claiming_date: requiredFormString(form, 'claiming_date'),
    current_covered_earnings: optionalFormString(form, 'current_covered_earnings'),
    completed_work_years: workYears ? Number(workYears) : undefined,
    expected_work_end_date: optionalFormString(form, 'expected_work_end_date'),
    earnings_pattern: optionalFormString(form, 'earnings_pattern') as
      | 'lower'
      | 'steady'
      | 'rising'
      | undefined,
    manual_monthly_benefit: optionalFormString(form, 'manual_monthly_benefit'),
    cola_rate: optionalFormString(form, 'cola_rate') ?? '0.025',
    deposit_account_id: optionalFormString(form, 'social_security_deposit_account_id'),
  };
}

function formatRate(value: string): string {
  return `${(Number(value) * 100).toLocaleString(undefined, { maximumFractionDigits: 2 })}%`;
}

export function SocialSecuritySection({
  householdId,
  scenarioId,
  householdPeople,
  incomeSources,
  estimates,
  assetAccounts,
  peopleError,
  estimatesError,
  peoplePending,
  estimatesPending,
}: {
  householdId: string;
  scenarioId: string;
  householdPeople: HouseholdPerson[];
  incomeSources: IncomeSource[];
  estimates: SocialSecurityEstimate[];
  assetAccounts: Account[];
  peopleError: unknown;
  estimatesError: unknown;
  peoplePending: boolean;
  estimatesPending: boolean;
}) {
  const [error, setError] = useState('');
  const [mode, setMode] = useState<'manual' | 'ballpark'>('ballpark');
  const [editId, setEditId] = useState('');
  const mutations = usePlanningPeopleMutations(householdId, scenarioId);
  const editingEstimate = estimates.find((estimate) => estimate.id === editId);
  const editingIncome = incomeSources.find(
    (source) => source.id === editingEstimate?.income_source_id,
  );
  const availablePeople = householdPeople.filter(
    (person) => !estimates.some((estimate) => estimate.person_id === person.id),
  );
  const formPeople = editingEstimate
    ? householdPeople.filter((person) => person.id === editingEstimate.person_id)
    : availablePeople;

  async function onCreatePerson(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const form = new FormData(target);
    setError('');
    try {
      await mutations.createPerson.mutateAsync({
        household_id: householdId,
        name: requiredFormString(form, 'person_name'),
        date_of_birth: requiredFormString(form, 'person_date_of_birth'),
      });
      target.reset();
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  async function onSubmitEstimate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const form = new FormData(target);
    setError('');
    try {
      if (editingEstimate) {
        await mutations.updateSocialSecurity.mutateAsync({
          estimateId: editingEstimate.id,
          payload: estimateInput(form, householdId),
        });
        setEditId('');
      } else {
        await mutations.createSocialSecurity.mutateAsync(estimateInput(form, householdId));
        target.reset();
      }
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  async function onDeleteEstimate(estimate: SocialSecurityEstimate) {
    setError('');
    try {
      await mutations.deleteSocialSecurity.mutateAsync(estimate);
      if (editId === estimate.id) setEditId('');
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  return (
    <>
      {error && <div className="error" role="alert">{error}</div>}
      {peopleError && <div className="error" role="alert">{String(peopleError)}</div>}
      {estimatesError && <div className="error" role="alert">{String(estimatesError)}</div>}
      {(peoplePending || estimatesPending) && (
        <div className="card" role="status">Loading Social Security planning…</div>
      )}
      <section className="grid two-column">
        <div className="card">
          <h2>Social Security estimates</h2>
          <p className="muted">Planning estimates only. Ballpark calculations use a versioned 2025-law baseline and become projection income at the claiming date.</p>
          {estimates.length ? (
            <table tabIndex={0}>
              <thead>
                <tr><th>Person</th><th>Claiming date</th><th>Monthly estimate</th><th>Planning range</th><th>COLA</th><th /></tr>
              </thead>
              <tbody>
                {estimates.map((estimate) => (
                  <tr key={estimate.id}>
                    <td>{householdPeople.find((person) => person.id === estimate.person_id)?.name ?? 'Unknown'}</td>
                    <td>{estimate.claiming_date}</td>
                    <td>{formatMoney(estimate.estimated_monthly_benefit)}</td>
                    <td>{estimate.calculation_mode === 'manual'
                      ? 'Manual entry'
                      : `${formatMoney(estimate.lower_monthly_benefit)}–${formatMoney(estimate.upper_monthly_benefit)}`}</td>
                    <td>{formatRate(estimate.cola_rate)}</td>
                    <td>
                      <button
                        type="button"
                        disabled={mutations.isPending}
                        onClick={() => {
                          setEditId(estimate.id);
                          setMode(estimate.calculation_mode);
                        }}
                      >Edit</button>{' '}
                      <button
                        type="button"
                        className="danger-button"
                        disabled={mutations.isPending}
                        onClick={() => onDeleteEstimate(estimate)}
                      >Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="muted">No Social Security estimates yet.</p>}
        </div>

        <div className="card">
          <h2>{editingEstimate ? 'Edit Social Security estimate' : 'Add Social Security estimate'}</h2>
          {!formPeople.length && <p className="muted">Add a household person, or delete their existing estimate before creating another.</p>}
          <form
            key={editingEstimate?.id ?? 'new'}
            onSubmit={onSubmitEstimate}
            className="stacked-form"
          >
            <label>
              Person
              <select
                name="social_security_person_id"
                defaultValue={editingEstimate?.person_id ?? ''}
                required
                disabled={!formPeople.length}
              >
                <option value="" disabled>Select person</option>
                {formPeople.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}
              </select>
            </label>
            <label>
              Calculation mode
              <select
                name="social_security_mode"
                value={mode}
                onChange={(event) => setMode(event.target.value as 'manual' | 'ballpark')}
              >
                <option value="ballpark">Ballpark from earnings</option>
                <option value="manual">Manual SSA estimate</option>
              </select>
            </label>
            <label>Claiming date<input name="claiming_date" type="date" defaultValue={editingEstimate?.claiming_date ?? ''} required /></label>
            {mode === 'manual' ? (
              <label>Monthly benefit at claiming date<input name="manual_monthly_benefit" inputMode="decimal" defaultValue={editingEstimate?.manual_monthly_benefit ?? ''} required /></label>
            ) : (
              <>
                <label>Current covered annual earnings<input name="current_covered_earnings" inputMode="decimal" defaultValue={editingEstimate?.current_covered_earnings ?? ''} required /></label>
                <label>Completed work years through 2025<input name="completed_work_years" type="number" min="0" max="50" defaultValue={editingEstimate?.completed_work_years ?? ''} required /></label>
                <label>Expected work end date<input name="expected_work_end_date" type="date" defaultValue={editingEstimate?.expected_work_end_date ?? ''} /></label>
                <label>
                  Historical earnings
                  <select name="earnings_pattern" defaultValue={editingEstimate?.earnings_pattern ?? 'steady'} required>
                    <option value="lower">Usually lower than current</option>
                    <option value="steady">Roughly current in real terms</option>
                    <option value="rising">Steadily increasing</option>
                  </select>
                </label>
              </>
            )}
            <label>Annual COLA assumption<input name="cola_rate" inputMode="decimal" defaultValue={editingEstimate?.cola_rate ?? '0.025'} required /></label>
            <label>
              Deposit account
              <select name="social_security_deposit_account_id" defaultValue={editingIncome?.deposit_account_id ?? ''}>
                <option value="">Default deposit account</option>
                {assetAccounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
              </select>
            </label>
            <div className="form-actions">
              <button type="submit" disabled={!formPeople.length || mutations.isPending}>
                {editingEstimate ? 'Save estimate' : 'Create estimate'}
              </button>
              {editingEstimate && (
                <button
                  type="button"
                  onClick={() => {
                    setEditId('');
                    setMode('ballpark');
                  }}
                >Cancel</button>
              )}
            </div>
          </form>
          <hr />
          <h3>Add household person</h3>
          <form onSubmit={onCreatePerson} className="stacked-form">
            <input name="person_name" placeholder="Name" required />
            <label>Date of birth<input name="person_date_of_birth" type="date" required /></label>
            <button type="submit" disabled={mutations.isPending}>Add person</button>
          </form>
        </div>
      </section>
    </>
  );
}
