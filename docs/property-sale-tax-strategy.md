# Property sale tax strategy

## Current behavior

Netwise treats taxes on a planned rental or investment property sale as a planning reserve, not as a tax-return calculation.

Each `RealEstateSale` has an `estimated_tax_rate`. The default is `0.150000`. When a property has an adjusted tax basis, the projection applies this rate to estimated gain after selling expenses. If adjusted basis is absent, purchase price is used as a coarse basis. If both are absent, the projection retains the conservative gross-price fallback and emits a warning.

```text
basis = adjusted tax basis, otherwise purchase price
amount realized = gross sale price - selling expenses
estimated taxable gain = max(amount realized - basis, 0)
estimated sale tax = estimated taxable gain × estimated tax rate

net proceeds = gross sale price
             - selling expenses
             - mortgage payoff
             - estimated sale tax
```

The mortgage payoff reduces cash proceeds but does not reduce estimated taxable gain. A user can override the rate when creating a sale, including setting it to zero when tax is expected to be deferred or otherwise inapplicable.

The projection reports the reserve as:

- a `property_sale_tax` cash flow;
- part of the projection point's `projected_taxes`; and
- a reduction in the amount deposited into the sale proceeds account.

The 15% rate remains a coarse planning assumption rather than an IRS tax rate, tax advice, or a guarantee of eventual liability. Purchase price is only a fallback for adjusted basis. Users should enter adjusted basis when improvements, depreciation, or other basis adjustments are material. Depreciation recapture, primary-residence exclusions, and detailed federal, state, and local tax treatment remain outside the initial estimate.

## Conditional liquidation before retirement

Netwise also supports opt-in automatic property liquidation strategies. When a projected outflow cannot be fully funded from eligible non-retirement liquid accounts, the engine:

1. exhausts eligible non-retirement liquid funding;
2. selects the enabled property with the lowest priority number whose earliest-sale date has arrived;
3. sells it at its projected account value for that period;
4. deducts selling expenses, the configured sale-tax reserve, and the linked mortgage payoff;
5. deposits net proceeds into the configured non-retirement liquid account;
6. retries the original cash-flow need; and
7. uses retirement accounts only if no eligible strategy remains or sale proceeds are insufficient.

Automatic sales are projection-generated operations and are not persisted as fixed-date sales or account events. Their cash flows use the `automatic_property_sale_*` prefix. A fixed-date `RealEstateSale` for a property takes precedence and prevents that property from being conditionally sold.

No property is enrolled automatically. In particular, a primary residence is eligible only when the user explicitly creates and enables a strategy for it. Strategies support priority, earliest-sale date, proceeds account, selling-expense rate, and estimated-tax rate.

Projection points expose `projected_unfunded_cash_flow`. This is the amount of planned outflow that remained unfunded after non-retirement assets, eligible automatic property sales, and retirement assets were exhausted.

## Liquid-runway sale optimization

A liquidation strategy can use `maximize_liquid_runway` instead of the default `liquidity_shortfall` mode. Enabled optimized properties are evaluated jointly in priority order. The optimizer:

1. treats March 1 of each eligible projection year, plus “never,” as the candidate sale dates;
2. simulates ordered combinations without invoking the optimizer recursively;
3. scores each schedule first by the date of the first retirement-account withdrawal;
4. breaks ties by the first unfunded cash flow, the non-retirement liquid balance immediately before retirement use, and ending net worth; and
5. returns the winning schedule in `property_sale_optimization` without persisting fixed-date sale records.

The search begins with the all-“never” schedule and expands its candidate-year window whenever a better schedule postpones retirement use. Dates after the current liquid-runway boundary are initially collapsed because they cannot affect earlier cash flows. This keeps a three-property, multi-decade optimization practical while preserving deterministic results.

Optimized properties do not also participate in shortfall-triggered sales during a candidate simulation; each candidate must respect its proposed schedule. Existing fixed-date sales continue to take precedence. The projection response reports the selected property names and dates, number of schedules evaluated, and first retirement-withdrawal date for auditability.

## Why the gross-price fallback remains

Actual taxable gain generally depends on amount realized, adjusted tax basis, depreciation, holding period, taxpayer income, jurisdiction, and transaction structure. A flat gross-price reserve can overstate tax on a recently purchased property and understate tax on a highly appreciated or heavily depreciated property.

Selling expenses and mortgage payoff have different tax effects. Selling expenses generally affect amount realized; mortgage payoff affects cash proceeds but does not by itself reduce taxable gain.

## Calculation hierarchy

The implementation selects the best available method in this order:

1. **Adjusted tax basis** — apply the configured rate to estimated gain after selling expenses.
2. **Purchase-price basis** — use purchase price as a coarse basis and emit a warning that adjustments are missing.
3. **Gross-price reserve** — retain 15% of gross price as a conservative fallback and emit a missing-basis warning.

Future versions can add a sale-specific manual tax amount and detailed depreciation-recapture calculations ahead of these methods.

## Data needed for detailed estimates

Property-level data:

- original purchase price and purchase date;
- acquisition costs included in basis;
- land and depreciable-building allocation;
- capital improvements and other basis adjustments;
- depreciation allowed or allowable;
- prior casualty, insurance, or partial-disposition adjustments;
- suspended passive activity losses;
- residence versus investment use history; and
- planned exchange or installment-sale treatment.

Household/scenario data:

- filing status and projected taxable income in the sale year;
- federal long-term capital-gains assumptions;
- unrecaptured Section 1250 gain assumptions;
- Net Investment Income Tax applicability;
- state and local tax assumptions; and
- capital-loss carryforwards or other offsets.

## Future detailed calculation

A future basis-aware strategy should separate cash proceeds from taxable gain:

```text
adjusted basis = original basis
               + capital improvements
               + eligible basis additions
               - depreciation allowed or allowable
               - other basis reductions

amount realized = gross sale price - eligible selling expenses

total gain = max(amount realized - adjusted basis, 0)

estimated tax = depreciation-related tax
              + remaining long-term capital-gains tax
              + applicable NIIT
              + state and local tax
              - modeled offsets

cash deposited = gross sale price
               - selling expenses
               - mortgage payoff
               - estimated tax
```

Losses, mixed personal/rental use, primary-residence exclusions, Section 1031 exchanges, installment sales, and passive-loss releases require dedicated strategies rather than additions to the fallback formula.

## Product and audit requirements

- Always label fallback results as estimated reserves.
- Permit explicit rate or amount overrides.
- Preserve the assumptions used for reproducibility.
- Include sale taxes in projection cash-flow details and aggregate projected taxes.
- Never infer adjusted basis from current market value or mortgage balance.
- Add scenario comparison for low, default, and conservative sale-tax assumptions.
- Retain deterministic calculations so projected proceeds can be audited from stored inputs.
