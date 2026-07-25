import { useState, type FormEvent } from 'react';
import type { Account, AnnualTaxRecord, IncomeSource } from '../../api';
import {
  usePlanningBudgetMutations,
  usePlanningPeopleMutations,
} from '../../queries/planning';
import { formatMoney } from '../../utils/format';

function optionalFormString(form: FormData, key: string): string | undefined {
  const value = String(form.get(key) ?? '').trim();
  return value || undefined;
}

function requiredFormString(form: FormData, key: string): string {
  return String(form.get(key) ?? '').trim();
}

export function IncomeAndTaxSection({
  householdId,
  defaultDate,
  assetAccounts,
  accountNameById,
  incomeSources,
  taxRecords,
  incomeQueryError,
  incomeQueryPending,
  taxQueryError,
  taxQueryPending,
}: {
  householdId: string;
  defaultDate: string;
  assetAccounts: Account[];
  accountNameById: ReadonlyMap<string, string>;
  incomeSources: IncomeSource[];
  taxRecords: AnnualTaxRecord[];
  incomeQueryError: unknown;
  incomeQueryPending: boolean;
  taxQueryError: unknown;
  taxQueryPending: boolean;
}) {
  const [incomeError, setIncomeError] = useState('');
  const [taxRecordError, setTaxRecordError] = useState('');
  const peopleMutations = usePlanningPeopleMutations(householdId);
  const budgetMutations = usePlanningBudgetMutations(householdId);

  async function onCreateIncomeSource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const form = new FormData(target);
    setIncomeError('');
    try {
      await peopleMutations.createIncome.mutateAsync({
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
      await budgetMutations.createTaxRecord.mutateAsync({
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

  return (
    <>
      {incomeError && <div className="error" role="alert">{incomeError}</div>}
      {incomeQueryError && <div className="error" role="alert">{String(incomeQueryError)}</div>}
      {incomeQueryPending && <div className="card" role="status">Loading income sources…</div>}
      {taxRecordError && <div className="error" role="alert">{taxRecordError}</div>}
      {taxQueryError && <div className="error" role="alert">{String(taxQueryError)}</div>}
      {taxQueryPending && <div className="card" role="status">Loading tax records…</div>}

      <section className="grid two-column">
        <div className="card">
          <h2>Income sources</h2>
          {incomeSources.length ? (
            <table tabIndex={0}>
              <thead>
                <tr><th>Name</th><th>Type</th><th>Amount</th><th>Frequency</th><th>Deposit account</th></tr>
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
          ) : <p className="muted">No income sources yet.</p>}
        </div>

        <div className="card">
          <h2>Annual tax records</h2>
          {taxRecords.length ? (
            <table tabIndex={0}>
              <thead>
                <tr><th>Year</th><th>Gross income</th><th>Taxes paid</th><th>Effective rate</th></tr>
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
          ) : <p className="muted">No tax records yet.</p>}
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
            <label>Start date<input name="start_date" type="date" defaultValue={defaultDate} required /></label>
            <label>End date<input name="end_date" type="date" /></label>
            <input name="growth_rate" inputMode="decimal" placeholder="Growth rate, e.g. 0.03" />
            <select name="deposit_account_id" aria-label="Income deposit account" defaultValue="">
              <option value="">Default deposit account</option>
              {assetAccounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
            </select>
            <button type="submit" disabled={peopleMutations.isPending}>Add income source</button>
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
            <button type="submit" disabled={budgetMutations.isPending}>Add tax record</button>
          </form>
        </div>
      </section>
    </>
  );
}
