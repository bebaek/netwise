import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  Account,
  Household,
  MortgageProfile,
  NetWorth,
  NetWorthHistory,
  RealEstateProperty,
  createAccount,
  createHousehold,
  createMortgageProfile,
  createRealEstateProperty,
  createSnapshot,
  getNetWorth,
  getNetWorthHistory,
  listAccounts,
  listHouseholds,
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

function App() {
  const [households, setHouseholds] = useState<Household[]>([]);
  const [selectedHouseholdId, setSelectedHouseholdId] = useState<string>('');
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [netWorth, setNetWorth] = useState<NetWorth | null>(null);
  const [history, setHistory] = useState<NetWorthHistory | null>(null);
  const [properties, setProperties] = useState<RealEstateProperty[]>([]);
  const [mortgages, setMortgages] = useState<MortgageProfile[]>([]);
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
    const [accountList, netWorthResult, historyResult, propertyList, mortgageList] = await Promise.all([
      listAccounts(householdId),
      getNetWorth(householdId),
      getNetWorthHistory(householdId),
      listRealEstateProperties(householdId),
      listMortgageProfiles(householdId),
    ]);
    setAccounts(accountList);
    setNetWorth(netWorthResult);
    setHistory(historyResult);
    setProperties(propertyList);
    setMortgages(mortgageList);
  }

  useEffect(() => {
    refreshHouseholds()
      .catch((err: unknown) => setError(String(err)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedHouseholdId) return;
    refreshDashboard(selectedHouseholdId).catch((err: unknown) => setError(String(err)));
  }, [selectedHouseholdId]);

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

          <section className="grid two-column">
            <div className="card">
              <h2>Accounts</h2>
              {netWorth?.accounts.length ? (
                <table>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Kind</th>
                      <th>Category</th>
                      <th>Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {netWorth.accounts.map((account) => (
                      <tr key={account.account_id}>
                        <td>{account.name}</td>
                        <td>{account.account_kind}</td>
                        <td>{account.category}</td>
                        <td>{formatMoney(account.balance)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted">No accounts yet.</p>
              )}
            </div>

            <div className="card">
              <h2>History</h2>
              {history?.points.length ? (
                <table>
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Net worth</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.points.map((point) => (
                      <tr key={point.as_of_date}>
                        <td>{point.as_of_date}</td>
                        <td>{formatMoney(point.net_worth)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted">Add snapshots to see history.</p>
              )}
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
