# Product Design

## Positioning

Netwise is a no-transaction financial planning app. It turns periodic account balance snapshots into financial status, estimated expenses, and future projections.

It is not primarily a budgeting app, transaction categorizer, or tax filing product.

## Target users

- Individuals who track net worth manually today.
- Couples or households who want a shared financial dashboard.
- Privacy-conscious users who do not want to link bank credentials.
- FIRE and long-term planning users who want useful projections without maintaining transaction categories.
- Users with fragmented institutions where automation is unreliable.

## Core workflow

1. Create a household.
2. Invite household members if needed.
3. Add asset and liability accounts.
4. Categorize accounts by financial planning purpose.
5. Enter current balances.
6. Add income sources.
7. Add annual tax summaries when available.
8. Configure simple projection assumptions.
9. Review current status, historical changes, estimated expenses, and future scenarios.
10. Update balances monthly or quarterly.

## Account categories

Suggested asset categories:

- Cash
- Taxable investment
- Retirement
- HSA
- Real estate
- Fixed-income asset
- Crypto
- Business equity
- Vehicle
- Collectible
- Other asset

Suggested liability categories:

- Mortgage
- Credit card
- Student loan
- Auto loan
- Personal loan
- Other liability

## Liquidity classes

Planning should separate categories by accessibility:

- Cash
- Non-retirement liquid
- Retirement liquid
- Real estate
- Illiquid
- Liability

## Balance snapshots

A balance snapshot records account value at a point in time.

Required fields:

- Household
- Account
- As-of date
- Balance
- Currency
- Source

Snapshot sources:

- Manual
- Guided manual
- Imported CSV
- Plugin API
- Plugin browser automation

The first product version should focus on manual and guided manual snapshots.

## Guided manual extraction

Netwise can store institution guides that help users find the correct balance manually.

Example guide:

1. Open the institution website.
2. Sign in.
3. Navigate to the account summary page.
4. Locate total account value.
5. Enter the displayed balance and date.

These guides should not store user credentials.

## Real estate modeling

Real estate should be modeled as a property asset with an optional linked mortgage liability.

Current net worth should compute real estate equity from current valuation and debt:

```text
real estate equity = latest property valuation - latest or computed mortgage balance
```

Property value should be stored as dated valuation snapshots. Valuation snapshots should include source and confidence because real estate value is approximate.

Valuation sources:

- Manual estimate
- Purchase price
- Appraisal
- Tax assessment
- Comparable sales
- Plugin estimate
- Model estimate

Property assumptions:

- Purchase date
- Purchase price
- Down payment
- Current estimated value
- Expected appreciation rate
- Property tax estimate
- Insurance estimate
- Maintenance estimate
- HOA estimate

Mortgage assumptions:

- Original principal
- Current balance
- Interest rate
- Term
- Start date
- Monthly payment

For current status, use the latest mortgage balance snapshot when available. If no recent mortgage balance snapshot exists, compute an estimated balance from the mortgage amortization profile.

Projection should compute future property value, mortgage balance, and equity separately.

## Liquid asset modeling

Liquid assets use yield strategies for projection.

Initial strategies:

- Static annual rate
- Category default rate

Future strategies:

- Historical average
- Moving average
- Portfolio-allocation based
- Time-series forecast
- Manual yield curve

## Income modeling

Income sources represent predictable inflows.

Examples:

- Salary
- Bonus
- Rental income
- Pension
- Social Security estimate
- Annuity
- Business income
- Other income

Each income source can include amount, frequency, start date, end date, and growth assumption.

## Retirement-phase modeling

The initial retirement model is household-level and deterministic. Projection settings can define a
retirement date and annual retirement non-mortgage spending. The projection uses regular annual
non-mortgage spending before that date, retirement non-mortgage spending afterward, and prorates a
period that contains the transition date. An itemized spending plan defines granular categories. Each
item has a current annual amount, an optional retirement annual amount, and an optional
category-specific growth rate; otherwise it inherits general spending inflation. Projection settings
select either the manual household total or the automatic sum of spending items. Manual mode is the
default when a household total is present, while itemized mode derives both working and retirement
spending from the category entries. A one-run spending override uses manual mode. The projection
returns its effective mode and per-period item breakdown so total spending remains auditable.
Owner-occupied mortgage payments are calculated separately from linked
mortgage profiles, remain fixed rather than inflating with household spending, and stop after the
final scheduled payment or a property sale. Owner-occupied property tax and homeowners insurance
are also projected automatically from the property profile, inherit general spending inflation,
and stop after a sale; users should not duplicate those costs in itemized spending. Projected total
spending reports the itemized/manual, property-cost, and mortgage components separately.

Income timing remains explicit: salary, pension, Social Security, and similar cash flows are modeled
as income sources with their own start and end dates. The retirement date does not automatically
stop salary or calculate retirement benefits. Recurring projection transfers can model contributions
from one asset account to another; they run after spending and taxes, are capped by available source
cash, and do not count as household income or spending.

Projection results identify retirement-phase periods, the first retirement-account withdrawal, and
the first unfunded period. Retirement accounts do not receive a default early-withdrawal penalty;
users can model one with an account liquidation-expense rate.

### Social Security planning estimates

Social Security can be entered manually from an SSA statement or estimated with a deliberately
approximate, versioned calculator. Estimates belong to a household person rather than a login and
become monthly projection income on the selected claiming date. Ballpark mode uses current covered
earnings, completed and expected future work years, a broad historical earnings pattern, claiming-age
adjustments, and a separate COLA assumption. It returns a low/base/high range and records the law year
and calculator version used. It is not an SSA benefit determination and does not model detailed annual
earnings histories, eligibility credits, spousal or survivor benefits, disability benefits, or
Social Security-specific tax rules. The general projection tax approximation currently treats the
resulting income like other household income.

The initial retirement model does not derive age eligibility, required minimum distributions,
Medicare costs, or detailed tax rules.

## Annual tax summaries

Tax can be entered once per year to improve after-tax income, estimated expense, and future projections.

MVP fields:

- Tax year
- Gross income
- Total taxes paid
- Refund or additional payment
- Notes

The app should calculate effective tax rate when gross income is available.

Netwise should not attempt tax filing or detailed tax optimization in early versions.

## Expense estimation

Expense can be estimated from income, taxes, asset growth, net worth change, and known adjustments.

Simplified yearly formula:

```text
Estimated living expense = gross income - taxes paid + estimated investment growth + other inflows - net worth increase - known adjustments
```

Tax should be shown separately from living expense.

Users should be able to add adjustment entries for unusual events such as home purchase, car purchase, inheritance, gifts, account additions, account removals, or major one-time spending.

## Account events and adjustments

The precursor CLI uses dated `value_changes` to alter projected asset values. Netwise should model this explicitly as account events.

Account events are separate from balance snapshots:

- A balance snapshot says what an account was worth on a date.
- An account event explains or plans a change to an account.

Event examples:

- Contribution
- Withdrawal
- Transfer
- Large purchase
- Asset sale
- Gift
- Inheritance
- Tax payment
- Account added
- Account removed
- Manual projection adjustment

Historical events improve expense estimation by explaining net worth changes. Future events improve projection scenarios by representing planned contributions, withdrawals, sales, or purchases.

## Projection scenarios

A scenario contains assumptions for future projection.

Examples:

- Base case
- Conservative return
- Optimistic return
- Buy property
- Retire early
- Reduced income
- Higher expenses

Projection outputs:

- Net worth
- Liquid assets
- Retirement assets
- Real estate equity
- Liabilities
- Estimated expenses
- Savings rate
- Target-date progress

## Non-goals for early versions

- Transaction import and categorization
- Tax filing
- Detailed tax bracket modeling
- Investment advice
- Banking or money movement
- Unreviewed plugin execution
