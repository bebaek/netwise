import type { FormEventHandler } from 'react';
import type { Account, MortgageProfile, RealEstateProperty, RetirementTaxTreatment } from '../api';
import { formatMoney } from '../utils/format';

export type AccountEditDraft = {
  id: string;
  name: string;
  institution_name: string;
  account_kind: 'asset' | 'liability';
  category: string;
  liquidity_class: string;
  retirement_tax_treatment: RetirementTaxTreatment | '';
  expected_annual_yield: string;
  liquidation_expense_rate: string;
  currency: string;
  is_active: boolean;
};

export function AssetsPage({
  defaultDate,
  accounts,
  assetAccounts,
  propertyAccounts,
  properties,
  mortgages,
  propertyEditId,
  onPropertyEditId,
  accountNameById,
  latestBalanceByAccountId,
  onUpdateProperty,
  onCreateProperty,
  onCreateMortgage,
  accountEditDraft,
  onAccountEditDraft,
  onSaveAccountEdit,
  onStartEditAccount,
  onCreateAccount,
}: {
  defaultDate: string;
  accounts: Account[];
  assetAccounts: Account[];
  propertyAccounts: Account[];
  properties: RealEstateProperty[];
  mortgages: MortgageProfile[];
  propertyEditId: string;
  onPropertyEditId: (propertyId: string) => void;
  accountNameById: ReadonlyMap<string, string>;
  latestBalanceByAccountId: ReadonlyMap<string, string | null>;
  onUpdateProperty: FormEventHandler<HTMLFormElement>;
  onCreateProperty: FormEventHandler<HTMLFormElement>;
  onCreateMortgage: FormEventHandler<HTMLFormElement>;
  accountEditDraft: AccountEditDraft | null;
  onAccountEditDraft: (draft: AccountEditDraft | null) => void;
  onSaveAccountEdit: FormEventHandler<HTMLFormElement>;
  onStartEditAccount: (account: Account) => void;
  onCreateAccount: FormEventHandler<HTMLFormElement>;
}) {
  return (
    <>
<section className="card">
  <h2>Property details</h2>
  <p className="muted">Classify existing properties and configure rental cash flow assumptions.</p>
  {properties.length ? (
    <>
      <select aria-label="Property to edit" value={propertyEditId} onChange={(event) => onPropertyEditId(event.target.value)}>
        <option value="">Select property to edit</option>
        {properties.map((property) => (
          <option key={property.id} value={property.id}>
            {accountNameById.get(property.account_id) ?? property.account_id}
          </option>
        ))}
      </select>
      {properties.filter((property) => property.id === propertyEditId).map((property) => (
        <form key={property.id} onSubmit={onUpdateProperty} className="projection-form">
          <select name="property_type" aria-label="Property type" defaultValue={property.property_type}>
            <option value="residence">Primary residence</option>
            <option value="rental">Rental</option>
            <option value="land">Land</option>
            <option value="other">Other</option>
          </select>
          <label>Purchase date<input name="purchase_date" type="date" defaultValue={property.purchase_date ?? ''} /></label>
          <label>Purchase price<input name="purchase_price" inputMode="decimal" defaultValue={property.purchase_price ?? ''} /></label>
          <label>Adjusted tax basis<input name="adjusted_tax_basis" inputMode="decimal" defaultValue={property.adjusted_tax_basis ?? ''} /></label>
          <p className="muted">Sale-tax estimates use adjusted basis when provided, otherwise purchase price. Include basis adjustments such as capital improvements and depreciation.</p>
          <label>Down payment<input name="down_payment" inputMode="decimal" defaultValue={property.down_payment ?? ''} /></label>
          <label className="checkbox-label"><input name="is_rental" type="checkbox" defaultChecked={property.is_rental} /> Rental property</label>
          <label>Rental start date<input name="rental_start_date" type="date" defaultValue={property.rental_start_date ?? ''} /></label>
          <input name="monthly_market_rent" inputMode="decimal" placeholder="Monthly market rent" defaultValue={property.monthly_market_rent ?? ''} />
          <input name="other_monthly_income" inputMode="decimal" placeholder="Other monthly income" defaultValue={property.other_monthly_income ?? ''} />
          <input name="rent_growth_rate" inputMode="decimal" placeholder="Annual rent growth, e.g. 0.03" defaultValue={property.rent_growth_rate ?? ''} />
          <input name="vacancy_rate" inputMode="decimal" placeholder="Vacancy rate, e.g. 0.05" defaultValue={property.vacancy_rate ?? ''} />
          <input name="management_fee_rate" inputMode="decimal" placeholder="Management fee rate, e.g. 0.08" defaultValue={property.management_fee_rate ?? ''} />
          <input name="tax_and_insurance_annual" inputMode="decimal" placeholder="Combined annual tax + insurance (overrides separate fields)" defaultValue={property.tax_and_insurance_annual ?? ''} />
          <input name="property_tax_annual" inputMode="decimal" placeholder="Annual property tax (if entered separately)" defaultValue={property.property_tax_annual ?? ''} />
          <input name="insurance_annual" inputMode="decimal" placeholder="Annual insurance (if entered separately)" defaultValue={property.insurance_annual ?? ''} />
          <input name="maintenance_rate" inputMode="decimal" placeholder="Maintenance rate, e.g. 0.01" defaultValue={property.maintenance_rate ?? ''} />
          <input name="hoa_monthly" inputMode="decimal" placeholder="Monthly HOA" defaultValue={property.hoa_monthly ?? ''} />
          <input name="utilities_annual" inputMode="decimal" placeholder="Annual owner-paid utilities" defaultValue={property.utilities_annual ?? ''} />
          <input name="other_operating_expense_annual" inputMode="decimal" placeholder="Other annual operating expenses" defaultValue={property.other_operating_expense_annual ?? ''} />
          <input name="capital_reserve_rate" inputMode="decimal" placeholder="Capital reserve rate, e.g. 0.01" defaultValue={property.capital_reserve_rate ?? ''} />
          <select name="rental_deposit_account_id" aria-label="Rental deposit account" defaultValue={property.rental_deposit_account_id ?? ''}>
            <option value="">Default cash-flow account</option>
            {assetAccounts.filter((account) => account.id !== property.account_id).map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
          </select>
          <button type="submit">Save property details</button>
        </form>
      ))}
    </>
  ) : <p className="muted">No properties configured.</p>}
</section>

<section className="grid two-column">
  <div className="card">
    <h2>Real estate</h2>
    {properties.length ? (
      <table tabIndex={0}>
        <thead>
          <tr>
            <th>Property</th>
            <th>Type</th>
            <th>Purchase price</th>
            <th>Adjusted basis</th>
            <th>Appreciation</th>
          </tr>
        </thead>
        <tbody>
          {properties.map((property) => (
            <tr key={property.id}>
              <td>{accountNameById.get(property.account_id) ?? property.account_id}</td>
              <td>{property.property_type}</td>
              <td>{formatMoney(property.purchase_price)}</td>
              <td>{formatMoney(property.adjusted_tax_basis)}</td>
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
      <table tabIndex={0}>
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
    <form onSubmit={onCreateProperty} className="stacked-form">
      <input name="property_name" placeholder="Primary residence" required />
      <select name="property_type" aria-label="Property type" defaultValue="residence">
        <option value="residence">Residence</option>
        <option value="rental">Rental</option>
        <option value="land">Land</option>
        <option value="other">Other</option>
      </select>
      <label>
        Purchase date
        <input name="purchase_date" type="date" />
      </label>
      <label>Purchase price<input name="purchase_price" inputMode="decimal" /></label>
      <label>Adjusted tax basis<input name="adjusted_tax_basis" inputMode="decimal" /></label>
      <p className="muted">If adjusted basis is blank, sale-tax estimates use purchase price. Basis generally includes qualifying improvements and subtracts depreciation.</p>
      <label>Down payment<input name="down_payment" inputMode="decimal" /></label>
      <input name="expected_appreciation_rate" inputMode="decimal" placeholder="Expected appreciation rate, e.g. 0.03" />
      <input name="tax_and_insurance_annual" inputMode="decimal" placeholder="Combined annual tax + insurance (overrides separate fields)" />
      <input name="property_tax_annual" inputMode="decimal" placeholder="Annual property tax (if entered separately)" />
      <input name="insurance_annual" inputMode="decimal" placeholder="Annual insurance (if entered separately)" />
      <input name="maintenance_rate" inputMode="decimal" placeholder="Maintenance rate, e.g. 0.01" />
      <input name="hoa_monthly" inputMode="decimal" placeholder="Monthly HOA" />
      <label className="checkbox-label">
        <input name="is_rental" type="checkbox" />
        Rental property
      </label>
      <input name="rental_start_date" type="date" placeholder="Rental start date" />
      <input name="monthly_market_rent" inputMode="decimal" placeholder="Monthly market rent" />
      <input name="other_monthly_income" inputMode="decimal" placeholder="Other monthly income" />
      <input name="rent_growth_rate" inputMode="decimal" placeholder="Annual rent growth, e.g. 0.03" />
      <input name="vacancy_rate" inputMode="decimal" placeholder="Vacancy rate, e.g. 0.05" />
      <input name="management_fee_rate" inputMode="decimal" placeholder="Management fee rate, e.g. 0.08" />
      <input name="utilities_annual" inputMode="decimal" placeholder="Annual owner-paid utilities" />
      <input name="other_operating_expense_annual" inputMode="decimal" placeholder="Other annual operating expenses" />
      <input name="capital_reserve_rate" inputMode="decimal" placeholder="Capital reserve rate, e.g. 0.01" />
      <select name="rental_deposit_account_id" aria-label="Rental deposit account" defaultValue="">
        <option value="">Default cash-flow account</option>
        {assetAccounts.map((account) => (
          <option key={account.id} value={account.id}>{account.name}</option>
        ))}
      </select>
      <input name="current_value" inputMode="decimal" placeholder="Current valuation snapshot" />
      <label>
        Valuation date
        <input name="valuation_date" type="date" defaultValue={defaultDate} />
      </label>
      <button type="submit">Add property</button>
    </form>
  </div>

  <div className="card">
    <h2>Add mortgage</h2>
    <p className="muted">Creates a mortgage liability account, mortgage profile, and initial balance snapshot.</p>
    <form onSubmit={onCreateMortgage} className="stacked-form">
      <input name="mortgage_name" placeholder="Primary residence mortgage" required />
      <select name="property_account_id" aria-label="Linked property" defaultValue="">
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
      <select name="rate_type" aria-label="Mortgage rate type" defaultValue="fixed">
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

<section className="card">
  <div className="section-header">
    <div>
      <h2>Accounts</h2>
      <p className="muted">Edit account classifications and projection assumptions without changing balance history.</p>
    </div>
  </div>
  {accountEditDraft && (
    <form onSubmit={onSaveAccountEdit} className="event-editor-card">
      <div className="section-header">
        <div>
          <h3>Edit account</h3>
          <p className="muted">Category and liquidity class affect projection funding and tax estimates.</p>
        </div>
        <button type="button" className="secondary-button" onClick={() => onAccountEditDraft(null)}>
          Cancel
        </button>
      </div>
      <div className="event-editor-grid">
        <label>
          Name
          <input required value={accountEditDraft.name} onChange={(event) => onAccountEditDraft({ ...accountEditDraft, name: event.target.value })} />
        </label>
        <label>
          Institution
          <input value={accountEditDraft.institution_name} onChange={(event) => onAccountEditDraft({ ...accountEditDraft, institution_name: event.target.value })} />
        </label>
        <label>
          Kind
          <select value={accountEditDraft.account_kind} onChange={(event) => onAccountEditDraft({ ...accountEditDraft, account_kind: event.target.value as 'asset' | 'liability' })}>
            <option value="asset">Asset</option>
            <option value="liability">Liability</option>
          </select>
        </label>
        <label>
          Category
          <input
            required
            value={accountEditDraft.category}
            onChange={(event) =>
              onAccountEditDraft({
                ...accountEditDraft,
                category: event.target.value,
                retirement_tax_treatment:
                  event.target.value === 'retirement'
                    ? accountEditDraft.retirement_tax_treatment || 'traditional'
                    : '',
              })
            }
          />
        </label>
        <label>
          Liquidity class
          <input required value={accountEditDraft.liquidity_class} onChange={(event) => onAccountEditDraft({ ...accountEditDraft, liquidity_class: event.target.value })} />
        </label>
        <label>
          Retirement tax treatment
          <select
            disabled={accountEditDraft.category !== 'retirement'}
            value={accountEditDraft.retirement_tax_treatment}
            onChange={(event) =>
              onAccountEditDraft({
                ...accountEditDraft,
                retirement_tax_treatment: event.target.value as RetirementTaxTreatment | '',
              })
            }
          >
            <option value="">Not specified</option>
            <option value="traditional">Traditional / tax-deferred</option>
            <option value="roth">Roth / tax-free</option>
            <option value="after_tax">After-tax</option>
          </select>
        </label>
        <label>
          Expected annual yield
          <input inputMode="decimal" placeholder="0.05" value={accountEditDraft.expected_annual_yield} onChange={(event) => onAccountEditDraft({ ...accountEditDraft, expected_annual_yield: event.target.value })} />
        </label>
        <label>
          Liquidation expense rate
          <input inputMode="decimal" placeholder="0.01" value={accountEditDraft.liquidation_expense_rate} onChange={(event) => onAccountEditDraft({ ...accountEditDraft, liquidation_expense_rate: event.target.value })} />
        </label>
        <label>
          Currency
          <input required maxLength={3} value={accountEditDraft.currency} onChange={(event) => onAccountEditDraft({ ...accountEditDraft, currency: event.target.value })} />
        </label>
        <label className="inline-toggle">
          <input type="checkbox" checked={accountEditDraft.is_active} onChange={(event) => onAccountEditDraft({ ...accountEditDraft, is_active: event.target.checked })} />
          Active account
        </label>
      </div>
      <div className="action-row">
        <button type="submit">Save account</button>
        <button type="button" className="secondary-button" onClick={() => onAccountEditDraft(null)}>Cancel</button>
      </div>
    </form>
  )}
  {accounts.length ? (
    <table tabIndex={0}>
      <thead>
        <tr>
          <th>Name</th>
          <th>Kind</th>
          <th>Category</th>
          <th>Retirement tax treatment</th>
          <th>Yield</th>
          <th>Balance</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {accounts.map((account) => (
          <tr key={account.id}>
            <td>{account.name}{!account.is_active && <span className="muted cell-detail">Inactive</span>}</td>
            <td>{account.account_kind}</td>
            <td>{account.category}</td>
            <td>{account.retirement_tax_treatment ?? 'Not applicable'}</td>
            <td>{account.expected_annual_yield ?? '—'}</td>
            <td>{formatMoney(latestBalanceByAccountId.get(account.id))}</td>
            <td><button type="button" className="secondary-button" onClick={() => onStartEditAccount(account)}>Edit</button></td>
          </tr>
        ))}
      </tbody>
    </table>
  ) : (
    <p className="muted">No accounts yet.</p>
  )}
</section>

<section className="card">
  <h2>Add account</h2>
    <form onSubmit={onCreateAccount} className="stacked-form">
      <input name="name" placeholder="Fidelity 401k" required />
      <select name="account_kind" aria-label="Account kind" defaultValue="asset">
        <option value="asset">Asset</option>
        <option value="liability">Liability</option>
      </select>
      <input name="category" placeholder="retirement / real_estate / mortgage" required />
      <input name="liquidity_class" placeholder="retirement_liquid / real_estate / liability" required />
      <select name="retirement_tax_treatment" aria-label="Retirement tax treatment" defaultValue="">
        <option value="">Not a retirement account</option>
        <option value="traditional">Traditional / tax-deferred</option>
        <option value="roth">Roth / tax-free</option>
        <option value="after_tax">After-tax</option>
      </select>
      <input name="expected_annual_yield" inputMode="decimal" placeholder="Expected annual yield, e.g. 0.05" />
      <button type="submit">Add account</button>
  </form>
</section>
    </>
  );
}
