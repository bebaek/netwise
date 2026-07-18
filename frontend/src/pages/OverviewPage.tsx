import { useMemo } from 'react';
import type { NetWorth, NetWorthBreakdownHistory, NetWorthHistory, NetWorthProjection } from '../api';
import { formatMoney } from '../utils/format';

type TrajectoryProjectionPoint = Pick<NetWorthProjection['points'][number], 'as_of_date' | 'net_worth'>;

function categoryBalance(
  categories: Array<{ category: string; balance: string }>,
  category: string,
): string | null {
  return categories.find((item) => item.category === category)?.balance ?? null;
}

function dateMs(value: string): number {
  return new Date(`${value}T00:00:00`).getTime();
}

function HistoryChart({
  points,
  projectionPoints = [],
}: {
  points: NetWorthHistory['points'];
  projectionPoints?: TrajectoryProjectionPoint[];
}) {
  const sortedHistory = [...points].sort((left, right) => left.as_of_date.localeCompare(right.as_of_date));
  const lastHistoryPoint = sortedHistory[sortedHistory.length - 1];
  const visibleProjectionPoints = [...projectionPoints]
    .filter((point) => !lastHistoryPoint || point.as_of_date > lastHistoryPoint.as_of_date)
    .sort((left, right) => left.as_of_date.localeCompare(right.as_of_date));
  const chartPoints = [...sortedHistory, ...visibleProjectionPoints];
  if (chartPoints.length < 2) return null;

  const values = chartPoints.map((point) => Number(point.net_worth));
  const dates = chartPoints.map((point) => dateMs(point.as_of_date));
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const minDate = Math.min(...dates);
  const maxDate = Math.max(...dates);
  const valueRange = maxValue - minValue || 1;
  const dateRange = maxDate - minDate || 1;
  const width = 720;
  const height = 240;
  const padding = 28;
  const leftPadding = 96;
  const plotWidth = width - leftPadding - padding;
  const plotHeight = height - padding * 2;
  const xForDate = (value: string) => leftPadding + ((dateMs(value) - minDate) / dateRange) * plotWidth;
  const yForValue = (value: number) => padding + plotHeight - ((value - minValue) / valueRange) * plotHeight;
  const polylineFor = (items: Array<{ as_of_date: string; net_worth: string }>) =>
    items.map((point) => `${xForDate(point.as_of_date)},${yForValue(Number(point.net_worth))}`).join(' ');
  const historyPolyline = polylineFor(sortedHistory);
  const projectionPolyline = lastHistoryPoint
    ? polylineFor([lastHistoryPoint, ...visibleProjectionPoints])
    : polylineFor(visibleProjectionPoints);

  return (
    <div className="trend-chart" aria-label="Financial trajectory chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img">
        <title>Financial trajectory</title>
        <line x1={leftPadding} y1={height - padding} x2={width - padding} y2={height - padding} className="axis" />
        <line x1={leftPadding} y1={padding} x2={leftPadding} y2={height - padding} className="axis" />
        <text x={leftPadding - 10} y={padding + 4} textAnchor="end" className="axis-label">
          {formatMoney(String(maxValue))}
        </text>
        <text x={leftPadding - 10} y={height - padding + 4} textAnchor="end" className="axis-label">
          {formatMoney(String(minValue))}
        </text>
        <text transform={`translate(18 ${height / 2}) rotate(-90)`} textAnchor="middle" className="axis-title">
          Net worth
        </text>
        <polyline points={historyPolyline} className="trend-line history" />
        {visibleProjectionPoints.length > 0 && <polyline points={projectionPolyline} className="trend-line projection" />}
        {sortedHistory.map((point) => (
          <circle
            key={`${point.as_of_date}-${point.estimated ? 'estimate' : 'snapshot'}`}
            cx={xForDate(point.as_of_date)}
            cy={yForValue(Number(point.net_worth))}
            r={point.estimated ? 3 : 5}
            className={point.estimated ? 'trend-dot estimate' : 'trend-dot snapshot'}
          />
        ))}
        {visibleProjectionPoints.map((point) => (
          <circle
            key={`${point.as_of_date}-projection`}
            cx={xForDate(point.as_of_date)}
            cy={yForValue(Number(point.net_worth))}
            r={4}
            className="trend-dot projection"
          />
        ))}
      </svg>
      <div className="chart-labels">
        <span>{chartPoints[0]?.as_of_date}</span>
        <span>{chartPoints[chartPoints.length - 1]?.as_of_date}</span>
      </div>
      <div className="chart-legend">
        <span><i className="legend-dot snapshot" />Snapshot</span>
        <span><i className="legend-dot estimate" />Estimate</span>
        {visibleProjectionPoints.length > 0 && <span><i className="legend-dot projection" />Projection</span>}
      </div>
    </div>
  );
}

export function OverviewPage({
  active,
  netWorth,
  history,
  projection,
  breakdownHistory,
  showInterpolatedHistory,
  onShowInterpolatedHistory,
  showProjectionOnTrajectory,
  onShowProjectionOnTrajectory,
}: {
  active: boolean;
  netWorth: NetWorth | null;
  history: NetWorthHistory | null;
  projection: NetWorthProjection | null;
  breakdownHistory: NetWorthBreakdownHistory | null;
  showInterpolatedHistory: boolean;
  onShowInterpolatedHistory: (show: boolean) => void;
  showProjectionOnTrajectory: boolean;
  onShowProjectionOnTrajectory: (show: boolean) => void;
}) {
  const breakdownCategories = useMemo(() => {
    const assetCategories = new Set<string>();
    const liabilityCategories = new Set<string>();
    for (const point of breakdownHistory?.points ?? []) {
      point.asset_categories.forEach((item) => assetCategories.add(item.category));
      point.liability_categories.forEach((item) => liabilityCategories.add(item.category));
    }
    return {
      assetCategories: [...assetCategories].sort(),
      liabilityCategories: [...liabilityCategories].sort(),
    };
  }, [breakdownHistory]);

  return (
    <>
      <section className="summary-grid" hidden={!active}>
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

      <section className="card" hidden={!active}>
        <div className="section-header">
          <div>
            <h2>Financial trajectory</h2>
            <p className="muted">Known historical snapshots, optional interpolated estimates, and projected future net worth in one view.</p>
          </div>
          <div className="toggle-group">
            <label className="inline-toggle">
              <input
                type="checkbox"
                checked={showInterpolatedHistory}
                onChange={(event) => onShowInterpolatedHistory(event.target.checked)}
              />
              Show interpolated estimates
            </label>
            <label className="inline-toggle">
              <input
                type="checkbox"
                checked={showProjectionOnTrajectory}
                onChange={(event) => onShowProjectionOnTrajectory(event.target.checked)}
              />
              Show projection after run
            </label>
          </div>
        </div>
        {history?.points.length ? (
          <>
            <HistoryChart
              points={history.points}
              projectionPoints={showProjectionOnTrajectory ? projection?.points ?? [] : []}
            />
            <table className="spaced-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Net worth</th>
                  <th>Assets</th>
                  <th>Liabilities</th>
                  <th>Type</th>
                </tr>
              </thead>
              <tbody>
                {history.points.map((point) => (
                  <tr key={`${point.as_of_date}-${point.estimated ? 'estimate' : 'snapshot'}`} className={point.estimated ? 'estimated-row' : undefined}>
                    <td>{point.as_of_date}</td>
                    <td>{formatMoney(point.net_worth)}</td>
                    <td>{formatMoney(point.assets_total)}</td>
                    <td>{formatMoney(point.liabilities_total)}</td>
                    <td>{point.estimated ? 'Estimate' : 'Snapshot'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : (
          <p className="muted">Add snapshots to see historical trend.</p>
        )}
      </section>

      <section className="card" hidden={!active}>
        <h2>What changed?</h2>
        <p className="muted">Break down each snapshot date by asset and liability category.</p>
        {breakdownHistory?.points.length ? (
          <div className="table-scroll">
            <table className="spaced-table breakdown-table">
              <thead>
                <tr>
                  <th>Date</th>
                  {breakdownCategories.assetCategories.map((category) => (
                    <th key={`asset-${category}`}>{category}</th>
                  ))}
                  {breakdownCategories.liabilityCategories.map((category) => (
                    <th key={`liability-${category}`}>{category} debt</th>
                  ))}
                  <th>Net worth</th>
                </tr>
              </thead>
              <tbody>
                {breakdownHistory.points.map((point) => (
                  <tr key={point.as_of_date}>
                    <td>{point.as_of_date}</td>
                    {breakdownCategories.assetCategories.map((category) => (
                      <td key={`${point.as_of_date}-asset-${category}`}>
                        {formatMoney(categoryBalance(point.asset_categories, category))}
                      </td>
                    ))}
                    {breakdownCategories.liabilityCategories.map((category) => (
                      <td key={`${point.as_of_date}-liability-${category}`}>
                        {formatMoney(categoryBalance(point.liability_categories, category))}
                      </td>
                    ))}
                    <td>{formatMoney(point.net_worth)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">Add snapshots to see category changes over time.</p>
        )}
      </section>
    </>
  );
}
