import type { NetWorthProjection } from '../../api';
import { formatMoney } from '../../utils/format';

function readableLabel(value: string): string {
  return value.split('_').map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(' ');
}

export function ProjectionResults({ projection }: { projection: NetWorthProjection | null }) {
  return projection?.points.length ? (
    <>
      <div className="projection-note">
        <strong>Scenario:</strong> {projection.scenario_name}
      </div>
      {projection.warnings.map((warning) => (
        <div className="projection-note" key={warning}><strong>Projection warning:</strong> {warning}</div>
      ))}
      <div className="projection-note">
        <strong>Spending source:</strong> {projection.spending_mode === 'itemized' ? 'automatic sum of spending items' : 'manual household total'}.
      </div>
      {projection.retirement_date && (
        <div className="projection-note">
          <strong>Retirement phase:</strong> begins {projection.retirement_date}; first retirement-account withdrawal: {projection.first_retirement_withdrawal_date ?? 'none in projection'}; first unfunded period: {projection.first_unfunded_date ?? 'none in projection'}.
        </div>
      )}
      {projection.property_sale_optimization && (
        <div className="projection-note">
          <strong>Optimized March 1 property sales:</strong>{' '}
          {projection.property_sale_optimization.selected_sales
            .map((sale) => `${sale.property_name}: ${sale.sale_date ?? 'never'}`)
            .join(' · ')}
          {' '}({projection.property_sale_optimization.schedules_evaluated.toLocaleString()} schedules evaluated; first retirement withdrawal: {projection.property_sale_optimization.first_retirement_withdrawal_date ?? 'none in projection'})
        </div>
      )}
      <div className="desktop-table table-frame projection-table-frame">
        <table className="spaced-table projection-summary-table compact-table">
          <thead>
            <tr>
              <th>{projection.interval === 'annual' ? 'Year' : 'Period ending'}</th>
              <th>Net worth</th>
              <th>Assets</th>
              <th>Liabilities</th>
              <th>Income</th>
              <th>Taxes</th>
              <th>Total spending</th>
              <th>Property tax &amp; insurance</th>
              <th>Mortgage portion</th>
              <th>Unfunded</th>
              <th>Net cash flow</th>
            </tr>
          </thead>
          <tbody>
            {projection.points.map((point) => (
              <tr key={point.as_of_date}>
                <td>
                  {projection.interval === 'annual' ? point.year : point.as_of_date}
                  {point.retirement_phase ? ' · Retirement' : ''}
                </td>
                <td>{formatMoney(point.net_worth)}</td>
                <td>{formatMoney(point.assets_total)}</td>
                <td>{formatMoney(point.liabilities_total)}</td>
                <td>{formatMoney(point.projected_income)}</td>
                <td>{formatMoney(point.projected_taxes)}</td>
                <td>{formatMoney(point.projected_spending)}</td>
                <td>{formatMoney(point.projected_owner_property_spending)}</td>
                <td>{formatMoney(point.projected_mortgage_spending)}</td>
                <td>{formatMoney(point.projected_unfunded_cash_flow)}</td>
                <td>{formatMoney(point.net_cash_flow)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mobile-card-list projection-year-list">
        {projection.points.map((point) => (
          <article className="projection-year-card" key={point.year}>
            <div className="projection-year-header">
              <div>
                <span className="muted">Year</span>
                <strong>{point.year}</strong>
              </div>
              <div>
                <span className="muted">Net worth</span>
                <strong>{formatMoney(point.net_worth)}</strong>
              </div>
            </div>
            <dl className="projection-metric-list">
              <div>
                <dt>Assets</dt>
                <dd>{formatMoney(point.assets_total)}</dd>
              </div>
              <div>
                <dt>Liabilities</dt>
                <dd>{formatMoney(point.liabilities_total)}</dd>
              </div>
              <div>
                <dt>Income</dt>
                <dd>{formatMoney(point.projected_income)}</dd>
              </div>
              <div>
                <dt>Taxes</dt>
                <dd>{formatMoney(point.projected_taxes)}</dd>
              </div>
              <div>
                <dt>Total spending</dt>
                <dd>{formatMoney(point.projected_spending)}</dd>
              </div>
              <div>
                <dt>Property tax &amp; insurance</dt>
                <dd>{formatMoney(point.projected_owner_property_spending)}</dd>
              </div>
              <div>
                <dt>Mortgage portion</dt>
                <dd>{formatMoney(point.projected_mortgage_spending)}</dd>
              </div>
              <div>
                <dt>Unfunded</dt>
                <dd>{formatMoney(point.projected_unfunded_cash_flow)}</dd>
              </div>
              <div>
                <dt>Net cash flow</dt>
                <dd>{formatMoney(point.net_cash_flow)}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>

      <details className="cash-flow-details">
        <summary>Show projected spending breakdown</summary>
        <div className="table-frame cash-flow-table-frame">
          <table className="spaced-table compact-table" tabIndex={0}>
            <thead>
              <tr><th>Period</th><th>Category</th><th>Item</th><th>Amount</th></tr>
            </thead>
            <tbody>
              {projection.points.flatMap((point) =>
                point.projected_spending_breakdown.map((item, index) => (
                  <tr key={`${point.as_of_date}-${item.category}-${item.name}-${index}`}>
                    <td>{projection.interval === 'annual' ? point.year : point.as_of_date}</td>
                    <td>{readableLabel(item.category)}</td>
                    <td>{item.name}</td>
                    <td>{formatMoney(item.amount)}</td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      </details>

      <details className="cash-flow-details">
        <summary>Show projected account cash flows</summary>
        <div className="desktop-table table-frame cash-flow-table-frame">
          <table className="spaced-table compact-table" tabIndex={0}>
            <thead>
              <tr>
                <th>Year</th>
                <th>Account</th>
                <th>Cash flow</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {projection.points.flatMap((point) =>
                point.cash_flows.map((cashFlow, index) => (
                  <tr key={`${point.year}-${cashFlow.account_id}-${cashFlow.cash_flow_type}-${index}`}>
                    <td>{point.year}</td>
                    <td>{cashFlow.account_name}</td>
                    <td>{readableLabel(cashFlow.cash_flow_type)}</td>
                    <td>{formatMoney(cashFlow.amount)}</td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
        <div className="mobile-card-list cash-flow-card-list">
          {projection.points.flatMap((point) =>
            point.cash_flows.map((cashFlow, index) => (
              <article className="cash-flow-card" key={`${point.year}-${cashFlow.account_id}-${cashFlow.cash_flow_type}-${index}`}>
                <div>
                  <strong>{cashFlow.account_name}</strong>
                  <span>{point.year} · {readableLabel(cashFlow.cash_flow_type)}</span>
                </div>
                <strong>{formatMoney(cashFlow.amount)}</strong>
              </article>
            )),
          )}
        </div>
      </details>
    </>
  ) : (
    <p className="muted">Run a projection to see future net worth points.</p>
  );
}
