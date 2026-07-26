import { useState, type FormEvent } from 'react';
import type { Account, RealEstateLiquidationStrategy, RealEstateSale } from '../../api';
import { usePlanningRealEstateMutations } from '../../queries/realEstate';
import { formatMoney } from '../../utils/format';

function optionalFormString(form: FormData, key: string): string | undefined {
  const value = String(form.get(key) ?? '').trim();
  return value || undefined;
}

function requiredFormString(form: FormData, key: string): string {
  return String(form.get(key) ?? '').trim();
}

function formatRate(value: string): string {
  return `${(Number(value) * 100).toLocaleString(undefined, { maximumFractionDigits: 2 })}%`;
}

type SharedProps = {
  householdId: string;
  scenarioId: string;
  assetAccounts: Account[];
  propertyAccounts: Account[];
  accountNameById: ReadonlyMap<string, string>;
};

export function AutomaticPropertySalesSection({
  householdId,
  scenarioId,
  assetAccounts,
  propertyAccounts,
  accountNameById,
  strategies,
  queryError,
  queryPending,
}: SharedProps & {
  strategies: RealEstateLiquidationStrategy[];
  queryError: unknown;
  queryPending: boolean;
}) {
  const [error, setError] = useState('');
  const mutations = usePlanningRealEstateMutations(householdId, scenarioId);

  async function onUpsert(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const form = new FormData(target);
    const propertyAccountId = requiredFormString(form, 'automatic_property_account_id');
    setError('');
    try {
      await mutations.upsertLiquidationStrategy.mutateAsync({
        propertyAccountId,
        payload: {
          enabled: form.get('automatic_enabled') === 'on',
          optimization_mode: requiredFormString(form, 'automatic_optimization_mode') as
            | 'liquidity_shortfall'
            | 'maximize_liquid_runway',
          priority: Number(requiredFormString(form, 'automatic_priority')),
          earliest_sale_date: optionalFormString(form, 'automatic_earliest_sale_date'),
          proceeds_account_id: optionalFormString(form, 'automatic_proceeds_account_id'),
          selling_expense_rate: optionalFormString(form, 'automatic_selling_expense_rate'),
          estimated_tax_rate: requiredFormString(form, 'automatic_estimated_tax_rate'),
        },
      });
      target.reset();
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  async function onDelete(strategy: RealEstateLiquidationStrategy) {
    if (!window.confirm('Delete this automatic property sale strategy?')) return;
    setError('');
    try {
      await mutations.deleteLiquidationStrategy.mutateAsync(strategy);
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  return (
    <>
      {error && <div className="error" role="alert">{error}</div>}
      {queryError && <div className="error" role="alert">{String(queryError)}</div>}
      {queryPending && <div className="card" role="status">Loading automatic property sales…</div>}
      <details className="advanced-planning">
        <summary>Advanced property sale automation</summary>
        <p className="muted">Configure automatic sales for liquidity shortfalls or runway optimization.</p>
        <section className="grid two-column">
          <div className="card">
            <h2>Automatic property sale strategies</h2>
            <p className="muted">Strategies either sell at a liquid-funding shortfall or jointly test annual March 1 sale schedules to delay retirement withdrawals as long as possible. Fixed-date sales take precedence.</p>
            {strategies.length ? (
              <table tabIndex={0}>
                <thead>
                  <tr><th>Property</th><th>Mode</th><th>Priority</th><th>Earliest date</th><th>Tax reserve</th><th>Status</th><th /></tr>
                </thead>
                <tbody>
                  {strategies.map((strategy) => (
                    <tr key={strategy.id}>
                      <td>{accountNameById.get(strategy.property_account_id) ?? strategy.property_account_id}</td>
                      <td>{strategy.optimization_mode === 'maximize_liquid_runway' ? 'Maximize liquid runway' : 'Liquidity shortfall'}</td>
                      <td>{strategy.priority}</td>
                      <td>{strategy.earliest_sale_date ?? 'Any date'}</td>
                      <td>{formatRate(strategy.estimated_tax_rate)}</td>
                      <td>{strategy.enabled ? 'Enabled' : 'Disabled'}</td>
                      <td><button type="button" className="danger-button" disabled={mutations.isPending} onClick={() => onDelete(strategy)}>Delete</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <p className="muted">No automatic property sales configured.</p>}
          </div>

          <div className="card">
            <h2>Configure automatic sale</h2>
            <form onSubmit={onUpsert} className="stacked-form">
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
              <label>Selling expense rate<input name="automatic_selling_expense_rate" inputMode="decimal" placeholder="Default 0.06" /></label>
              <label>Estimated sale-tax reserve rate<input name="automatic_estimated_tax_rate" inputMode="decimal" defaultValue="0.15" required /></label>
              <label><input name="automatic_enabled" type="checkbox" defaultChecked /> Enabled</label>
              <p className="muted">Primary residences are never enrolled automatically. Runway optimization jointly evaluates enabled optimized properties in priority order and reports its selected schedule with the projection.</p>
              <button type="submit" disabled={!propertyAccounts.length || mutations.isPending}>Save strategy</button>
            </form>
          </div>
        </section>
      </details>
    </>
  );
}

export function PlannedPropertySalesSection({
  householdId,
  scenarioId,
  assetAccounts,
  propertyAccounts,
  accountNameById,
  sales,
  queryError,
  queryPending,
}: SharedProps & {
  sales: RealEstateSale[];
  queryError: unknown;
  queryPending: boolean;
}) {
  const [error, setError] = useState('');
  const mutations = usePlanningRealEstateMutations(householdId, scenarioId);

  async function onCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const form = new FormData(target);
    setError('');
    try {
      await mutations.createSale.mutateAsync({
        property_account_id: requiredFormString(form, 'property_account_id'),
        sale_date: requiredFormString(form, 'sale_date'),
        gross_sale_price: requiredFormString(form, 'gross_sale_price'),
        proceeds_account_id: optionalFormString(form, 'proceeds_account_id'),
        selling_expense_rate: optionalFormString(form, 'selling_expense_rate'),
        estimated_tax_rate: requiredFormString(form, 'estimated_tax_rate'),
      });
      target.reset();
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  async function onDelete(sale: RealEstateSale) {
    if (!window.confirm(`Delete the planned sale on ${sale.sale_date}?`)) return;
    setError('');
    try {
      await mutations.deleteSale.mutateAsync(sale);
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  return (
    <>
      {error && <div className="error" role="alert">{error}</div>}
      {queryError && <div className="error" role="alert">{String(queryError)}</div>}
      {queryPending && <div className="card" role="status">Loading planned property sales…</div>}
      <section className="grid two-column">
        <div className="card">
          <h2>Planned property sales</h2>
          <p className="muted">A sale pays off its linked mortgage, deducts selling costs and an estimated tax reserve, and transfers net proceeds to the selected account.</p>
          {sales.length ? (
            <table tabIndex={0}>
              <thead>
                <tr><th>Property</th><th>Date</th><th>Price</th><th>Tax reserve</th><th>Proceeds account</th><th /></tr>
              </thead>
              <tbody>
                {sales.map((sale) => (
                  <tr key={sale.id}>
                    <td>{accountNameById.get(sale.property_account_id) ?? sale.property_account_id}</td>
                    <td>{sale.sale_date}</td>
                    <td>{formatMoney(sale.gross_sale_price)}</td>
                    <td>{formatRate(sale.estimated_tax_rate)}</td>
                    <td>{accountNameById.get(sale.proceeds_account_id) ?? sale.proceeds_account_id}</td>
                    <td><button type="button" className="danger-button" disabled={mutations.isPending} onClick={() => onDelete(sale)}>Delete</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="muted">No property sales planned.</p>}
        </div>

        <div className="card">
          <h2>Plan property sale</h2>
          <form onSubmit={onCreate} className="stacked-form">
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
            <label>Estimated sale-tax reserve rate<input name="estimated_tax_rate" inputMode="decimal" defaultValue="0.15" required /></label>
            <p className="muted">Defaults to 15% of gross sale price when tax basis and depreciation details are unavailable.</p>
            <button type="submit" disabled={!propertyAccounts.length || mutations.isPending}>Plan sale</button>
          </form>
        </div>
      </section>
    </>
  );
}
