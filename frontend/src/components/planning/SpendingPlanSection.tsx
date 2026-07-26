import { useState, type FormEvent } from 'react';
import type { SpendingItem } from '../../api';
import { usePlanningBudgetMutations } from '../../queries/planning';
import { formatMoney } from '../../utils/format';

const SPENDING_CATEGORY_OPTIONS = [
  ['housing', 'Housing'],
  ['food', 'Food'],
  ['healthcare', 'Healthcare'],
  ['transportation', 'Transportation'],
  ['utilities', 'Utilities'],
  ['insurance', 'Insurance'],
  ['travel', 'Travel'],
  ['entertainment', 'Entertainment'],
  ['personal', 'Personal'],
  ['giving', 'Giving'],
  ['other', 'Other'],
] as const;

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

export function SpendingPlanSection({
  householdId,
  scenarioId,
  spendingItems,
  queryError,
  queryPending,
  spendingMode,
  workingSpendingTotal,
  retirementSpendingTotal,
  manualWorkingSpending,
  manualRetirementSpending,
  onInvalidateProjection,
}: {
  householdId: string;
  scenarioId: string;
  spendingItems: SpendingItem[];
  queryError: unknown;
  queryPending: boolean;
  spendingMode: 'manual' | 'itemized';
  workingSpendingTotal: number;
  retirementSpendingTotal: number;
  manualWorkingSpending: number;
  manualRetirementSpending: number;
  onInvalidateProjection: () => void;
}) {
  const [error, setError] = useState('');
  const [editId, setEditId] = useState('');
  const mutations = usePlanningBudgetMutations(householdId, scenarioId);

  async function onCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const form = new FormData(target);
    setError('');
    try {
      await mutations.createSpending.mutateAsync({
        household_id: householdId,
        name: requiredFormString(form, 'spending_item_name'),
        category: requiredFormString(form, 'spending_item_category'),
        annual_amount: requiredFormString(form, 'spending_item_annual_amount'),
        retirement_annual_amount: optionalFormString(form, 'spending_item_retirement_annual_amount'),
        growth_rate: optionalFormString(form, 'spending_item_growth_rate'),
      });
      target.reset();
      onInvalidateProjection();
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  async function onUpdate(event: FormEvent<HTMLFormElement>, spendingItem: SpendingItem) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError('');
    try {
      await mutations.updateSpending.mutateAsync({
        spendingItemId: spendingItem.id,
        payload: {
          name: requiredFormString(form, 'spending_item_edit_name'),
          category: requiredFormString(form, 'spending_item_edit_category'),
          annual_amount: requiredFormString(form, 'spending_item_edit_annual_amount'),
          retirement_annual_amount:
            optionalFormString(form, 'spending_item_edit_retirement_annual_amount') ?? null,
          growth_rate: optionalFormString(form, 'spending_item_edit_growth_rate') ?? null,
        },
      });
      onInvalidateProjection();
    } catch (mutationError: unknown) {
      setError(String(mutationError));
      throw mutationError;
    }
  }

  async function onDelete(spendingItem: SpendingItem) {
    if (!window.confirm(`Delete spending item ${spendingItem.name}?`)) return;
    setError('');
    try {
      await mutations.deleteSpending.mutateAsync(spendingItem);
      onInvalidateProjection();
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  return (
    <>
      {error && <div className="error" role="alert">{error}</div>}
      {queryError && <div className="error" role="alert">{String(queryError)}</div>}
      {queryPending && <div className="card" role="status">Loading spending plan…</div>}
      <section className="grid two-column">
        <div className="card">
          <h2>Spending plan</h2>
          <p className="muted">Break non-mortgage spending into categories with separate working and retirement amounts. Choose whether projections use the automatically calculated item total or the manually entered household total.</p>
          {spendingItems.length ? (
            <>
              <div className="projection-note">
                <strong>Automatic item sum:</strong> {formatMoney(String(workingSpendingTotal))} while working · {formatMoney(String(retirementSpendingTotal))} in retirement<br />
                <strong>Manual total:</strong> {formatMoney(String(manualWorkingSpending))} while working · {formatMoney(String(manualRetirementSpending))} in retirement<br />
                <strong>Projection source:</strong> {spendingMode === 'itemized' ? 'Automatic item sum' : 'Manual total'}
              </div>
              <div className="table-frame">
                <table className="spaced-table compact-table">
                  <thead>
                    <tr><th>Item</th><th>Category</th><th>Annual</th><th>Monthly</th><th>Retirement</th><th>Growth</th><th /></tr>
                  </thead>
                  <tbody>
                    {spendingItems.map((item) => {
                      const editFormId = `spending-item-edit-${item.id}`;
                      if (editId === item.id) {
                        return (
                          <tr key={item.id}>
                            <td><input form={editFormId} name="spending_item_edit_name" aria-label="Spending item name" defaultValue={item.name} required /></td>
                            <td>
                              <select form={editFormId} name="spending_item_edit_category" aria-label="Spending item category" defaultValue={item.category} required>
                                {SPENDING_CATEGORY_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                              </select>
                            </td>
                            <td><input form={editFormId} name="spending_item_edit_annual_amount" aria-label="Current annual amount" inputMode="decimal" defaultValue={item.annual_amount} required /></td>
                            <td>{formatMoney(String(Number(item.annual_amount) / 12))}</td>
                            <td><input form={editFormId} name="spending_item_edit_retirement_annual_amount" aria-label="Retirement annual amount" inputMode="decimal" placeholder="Same as current" defaultValue={item.retirement_annual_amount ?? ''} /></td>
                            <td><input form={editFormId} name="spending_item_edit_growth_rate" aria-label="Annual growth rate" inputMode="decimal" placeholder="Default inflation" defaultValue={item.growth_rate ?? ''} /></td>
                            <td>
                              <form
                                id={editFormId}
                                className="form-row"
                                onSubmit={async (event) => {
                                  try {
                                    await onUpdate(event, item);
                                    setEditId('');
                                  } catch {
                                    // Keep the row editable while the local error is displayed.
                                  }
                                }}
                              >
                                <button type="submit" disabled={mutations.isPending}>Save</button>
                                <button type="button" className="secondary-button" onClick={() => setEditId('')}>Cancel</button>
                              </form>
                            </td>
                          </tr>
                        );
                      }
                      return (
                        <tr key={item.id}>
                          <td>{item.name}</td>
                          <td>{readableLabel(item.category)}</td>
                          <td>{formatMoney(item.annual_amount)}</td>
                          <td>{formatMoney(String(Number(item.annual_amount) / 12))}</td>
                          <td>{formatMoney(item.retirement_annual_amount ?? item.annual_amount)}</td>
                          <td>{item.growth_rate == null ? 'Default inflation' : formatRate(item.growth_rate)}</td>
                          <td className="form-row">
                            <button type="button" disabled={mutations.isPending} onClick={() => setEditId(item.id)}>Edit</button>
                            <button type="button" className="danger-button" disabled={mutations.isPending} onClick={() => onDelete(item)}>Delete</button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className="muted">No itemized spending yet. Automatic item sum currently produces $0.00; manual mode uses the household total below.</p>
          )}
        </div>

        <div className="card">
          <h2>Add spending item</h2>
          <form onSubmit={onCreate} className="stacked-form">
            <label>Name<input name="spending_item_name" placeholder="Groceries" required /></label>
            <label>
              Category
              <select name="spending_item_category" defaultValue="food" required>
                {SPENDING_CATEGORY_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label>Current annual amount<input name="spending_item_annual_amount" inputMode="decimal" placeholder="9000" required /></label>
            <label>Retirement annual amount<input name="spending_item_retirement_annual_amount" inputMode="decimal" placeholder="Same as current" /></label>
            <label>Annual growth rate<input name="spending_item_growth_rate" inputMode="decimal" placeholder="Use default inflation" /></label>
            <p className="muted">Use a retirement amount of 0 for costs that end at retirement. Leave it blank to keep the current amount. A custom growth rate lets healthcare or travel differ from general inflation.</p>
            <button type="submit" disabled={mutations.isPending}>Add spending item</button>
          </form>
        </div>
      </section>
    </>
  );
}
