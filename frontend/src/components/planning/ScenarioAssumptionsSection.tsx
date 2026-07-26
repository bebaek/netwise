import { useState, type FormEvent } from 'react';
import type { Account } from '../../api';
import {
  useProjectionScenarioAssumptionMutations,
  useProjectionScenarioAssumptions,
} from '../../queries/projectionScenarios';

function nullableValue(form: FormData, key: string): string | null {
  const value = String(form.get(key) ?? '').trim();
  return value || null;
}

export function ScenarioAssumptionsSection({
  householdId,
  scenarioId,
  accounts,
  propertyAccounts,
  canEdit,
}: {
  householdId: string;
  scenarioId: string;
  accounts: Account[];
  propertyAccounts: Account[];
  canEdit: boolean;
}) {
  const [error, setError] = useState('');
  const assumptions = useProjectionScenarioAssumptions(householdId, scenarioId);
  const mutations = useProjectionScenarioAssumptionMutations(householdId, scenarioId);
  const accountAssumptionById = new Map(
    (assumptions.accountAssumptions.data ?? []).map((assumption) => [assumption.account_id, assumption]),
  );
  const propertyAssumptionById = new Map(
    (assumptions.propertyAssumptions.data ?? []).map((assumption) => [
      assumption.property_account_id,
      assumption,
    ]),
  );

  async function saveAccount(event: FormEvent<HTMLFormElement>, accountId: string) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError('');
    try {
      await mutations.updateAccount.mutateAsync({
        accountId,
        payload: {
          expected_annual_yield: nullableValue(form, 'expected_annual_yield'),
          liquidation_expense_rate: nullableValue(form, 'liquidation_expense_rate'),
        },
      });
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  async function saveProperty(event: FormEvent<HTMLFormElement>, propertyAccountId: string) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError('');
    try {
      await mutations.updateProperty.mutateAsync({
        propertyAccountId,
        payload: {
          expected_appreciation_rate: nullableValue(form, 'expected_appreciation_rate'),
          rent_growth_rate: nullableValue(form, 'rent_growth_rate'),
          vacancy_rate: nullableValue(form, 'vacancy_rate'),
        },
      });
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  const loading = assumptions.accountAssumptions.isPending
    || assumptions.propertyAssumptions.isPending;
  const queryError = assumptions.accountAssumptions.error ?? assumptions.propertyAssumptions.error;

  return (
    <section className="card">
      <h2>Scenario return assumptions</h2>
      <p className="muted">
        These rates affect only the selected scenario. Balances, account identity, and recorded history remain shared.
      </p>
      {error && <div className="error" role="alert">{error}</div>}
      {queryError && <div className="error" role="alert">{String(queryError)}</div>}
      {loading && <div role="status">Loading scenario assumptions…</div>}
      {!loading && (
        <>
          <h3>Accounts</h3>
          <div className="assumption-grid">
            {accounts.map((account) => {
              const assumption = accountAssumptionById.get(account.id);
              return (
                <form key={account.id} className="assumption-card" onSubmit={(event) => saveAccount(event, account.id)}>
                  <strong>{account.name}</strong>
                  <span className="muted">{account.category}</span>
                  {account.category !== 'real_estate' && (
                    <label>
                      Expected annual yield
                      <input
                        name="expected_annual_yield"
                        inputMode="decimal"
                        defaultValue={assumption?.expected_annual_yield ?? ''}
                        placeholder="0.05"
                        disabled={!canEdit}
                      />
                    </label>
                  )}
                  <label>
                    Liquidation expense rate
                    <input
                      name="liquidation_expense_rate"
                      inputMode="decimal"
                      defaultValue={assumption?.liquidation_expense_rate ?? ''}
                      placeholder="0.01"
                      disabled={!canEdit}
                    />
                  </label>
                  <button type="submit" disabled={!canEdit || mutations.isPending}>Save account assumption</button>
                </form>
              );
            })}
          </div>

          {propertyAccounts.length > 0 && (
            <>
              <h3>Properties</h3>
              <div className="assumption-grid">
                {propertyAccounts.map((account) => {
                  const assumption = propertyAssumptionById.get(account.id);
                  return (
                    <form key={account.id} className="assumption-card" onSubmit={(event) => saveProperty(event, account.id)}>
                      <strong>{account.name}</strong>
                      <label>
                        Expected annual appreciation
                        <input
                          name="expected_appreciation_rate"
                          inputMode="decimal"
                          defaultValue={assumption?.expected_appreciation_rate ?? ''}
                          placeholder="0.03"
                          disabled={!canEdit}
                        />
                      </label>
                      <label>
                        Annual rent growth
                        <input
                          name="rent_growth_rate"
                          inputMode="decimal"
                          defaultValue={assumption?.rent_growth_rate ?? ''}
                          placeholder="0.03"
                          disabled={!canEdit}
                        />
                      </label>
                      <label>
                        Vacancy rate
                        <input
                          name="vacancy_rate"
                          inputMode="decimal"
                          defaultValue={assumption?.vacancy_rate ?? ''}
                          placeholder="0.05"
                          disabled={!canEdit}
                        />
                      </label>
                      <button type="submit" disabled={!canEdit || mutations.isPending}>Save property assumption</button>
                    </form>
                  );
                })}
              </div>
            </>
          )}
        </>
      )}
    </section>
  );
}
