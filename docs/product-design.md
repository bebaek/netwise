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

Real estate should be modeled as an asset with optional linked mortgage liability.

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
