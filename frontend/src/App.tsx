import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  Account,
  Household,
  NetWorth,
  NetWorthHistory,
  createAccount,
  createHousehold,
  createSnapshot,
  getNetWorth,
  getNetWorthHistory,
  listAccounts,
  listHouseholds,
} from './api';
import './styles.css';

function formatMoney(value: string | null | undefined): string {
  if (value == null) return '—';
  return Number(value).toLocaleString(undefined, { style: 'currency', currency: 'USD' });
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function App() {
  const [households, setHouseholds] = useState<Household[]>([]);
  const [selectedHouseholdId, setSelectedHouseholdId] = useState<string>('');
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [netWorth, setNetWorth] = useState<NetWorth | null>(null);
  const [history, setHistory] = useState<NetWorthHistory | null>(null);
  const [error, setError] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);

  const selectedHousehold = useMemo(
    () => households.find((household) => household.id === selectedHouseholdId),
    [households, selectedHouseholdId],
  );

  async function refreshHouseholds() {
    const householdList = await listHouseholds();
    setHouseholds(householdList);
    if (!selectedHouseholdId && householdList.length > 0) {
      setSelectedHouseholdId(householdList[0].id);
    }
  }

  async function refreshDashboard(householdId: string) {
    const [accountList, netWorthResult, historyResult] = await Promise.all([
      listAccounts(householdId),
      getNetWorth(householdId),
      getNetWorthHistory(householdId),
    ]);
    setAccounts(accountList);
    setNetWorth(netWorthResult);
    setHistory(historyResult);
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
