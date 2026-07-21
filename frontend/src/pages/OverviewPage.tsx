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

function compactMoney(value: number): string {
  const absolute = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (absolute >= 1_000_000) {
    return `${sign}$${(absolute / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 1 })}M`;
  }
  if (absolute >= 1_000) {
    return `${sign}$${(absolute / 1_000).toLocaleString(undefined, { maximumFractionDigits: 0 })}K`;
  }
  return `${sign}$${absolute.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function niceStep(value: number): number {
  const magnitude = 10 ** Math.floor(Math.log10(value || 1));
  const normalized = value / magnitude;
  const factor = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return factor * magnitude;
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
  const rawMinValue = Math.min(0, ...values);
  const rawMaxValue = Math.max(0, ...values);
  const valueStep = niceStep((rawMaxValue - rawMinValue || 1) / 5);
  const minValue = Math.floor(rawMinValue / valueStep) * valueStep;
  const maxValue = Math.ceil(rawMaxValue / valueStep) * valueStep || valueStep;
  const minDate = Math.min(...dates);
  const maxDate = Math.max(...dates);
  const valueRange = maxValue - minValue || 1;
  const dateRange = maxDate - minDate || 1;
  const width = 900;
  const height = 320;
  const topPadding = 28;
  const rightPadding = 24;
  const bottomPadding = 48;
  const leftPadding = 82;
  const plotWidth = width - leftPadding - rightPadding;
  const plotHeight = height - topPadding - bottomPadding;
  const plotBottom = height - bottomPadding;
  const xForMs = (value: number) => leftPadding + ((value - minDate) / dateRange) * plotWidth;
  const xForDate = (value: string) => xForMs(dateMs(value));
  const yForValue = (value: number) => topPadding + plotHeight - ((value - minValue) / valueRange) * plotHeight;
  const polylineFor = (items: Array<{ as_of_date: string; net_worth: string }>) =>
    items.map((point) => `${xForDate(point.as_of_date)},${yForValue(Number(point.net_worth))}`).join(' ');
  const projectionPolyline = lastHistoryPoint
    ? polylineFor([lastHistoryPoint, ...visibleProjectionPoints])
    : polylineFor(visibleProjectionPoints);
  const yTicks = Array.from(
    { length: Math.round((maxValue - minValue) / valueStep) + 1 },
    (_, index) => minValue + index * valueStep,
  );
  const minYear = new Date(minDate).getFullYear();
  const maxYear = new Date(maxDate).getFullYear();
  const yearSpan = Math.max(maxYear - minYear, 1);
  const yearStep = yearSpan > 40 ? 10 : yearSpan > 20 ? 5 : yearSpan > 8 ? 2 : 1;
  const xTickYears = [
    minYear,
    ...Array.from(
      { length: Math.max(Math.floor((maxYear - Math.ceil(minYear / yearStep) * yearStep) / yearStep) + 1, 0) },
      (_, index) => Math.ceil(minYear / yearStep) * yearStep + index * yearStep,
    ),
    maxYear,
  ].filter((year, index, years) => year >= minYear && year <= maxYear && years.indexOf(year) === index);
  const todayMs = Date.now();
  const showToday = todayMs > minDate && todayMs < maxDate;
  const finalProjectionPoint = visibleProjectionPoints[visibleProjectionPoints.length - 1];

  return (
    <div className="trend-chart" aria-label="Financial trajectory chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img">
        <title>Financial trajectory</title>
        <desc>Historical net-worth snapshots and future projection over time.</desc>
        {yTicks.map((tick) => (
          <g key={`y-${tick}`}>
            <line
              x1={leftPadding}
              y1={yForValue(tick)}
              x2={width - rightPadding}
              y2={yForValue(tick)}
              className="chart-grid-line"
            />
            <text x={leftPadding - 12} y={yForValue(tick) + 4} textAnchor="end" className="axis-label">
              {compactMoney(tick)}
            </text>
          </g>
        ))}
        {xTickYears.map((year) => {
          const tickMs = new Date(`${year}-01-01T00:00:00`).getTime();
          const x = xForMs(Math.min(Math.max(tickMs, minDate), maxDate));
          return (
            <g key={`x-${year}`}>
              <line x1={x} y1={topPadding} x2={x} y2={plotBottom} className="chart-grid-line vertical" />
              <text x={x} y={height - 19} textAnchor="middle" className="axis-label">{year}</text>
            </g>
          );
        })}
        <line x1={leftPadding} y1={plotBottom} x2={width - rightPadding} y2={plotBottom} className="axis" />
        <line x1={leftPadding} y1={topPadding} x2={leftPadding} y2={plotBottom} className="axis" />
        <text transform={`translate(20 ${height / 2}) rotate(-90)`} textAnchor="middle" className="axis-title">
          Net worth
        </text>
        {sortedHistory.slice(1).map((point, index) => {
          const previous = sortedHistory[index];
          const estimated = previous.estimated || point.estimated;
          return (
            <line
              key={`history-segment-${previous.as_of_date}-${point.as_of_date}`}
              x1={xForDate(previous.as_of_date)}
              y1={yForValue(Number(previous.net_worth))}
              x2={xForDate(point.as_of_date)}
              y2={yForValue(Number(point.net_worth))}
              className={estimated ? 'trend-line estimate' : 'trend-line history'}
            />
          );
        })}
        {visibleProjectionPoints.length > 0 && <polyline points={projectionPolyline} className="trend-line projection" />}
        {showToday && (
          <g className="today-marker">
            <line x1={xForMs(todayMs)} y1={topPadding} x2={xForMs(todayMs)} y2={plotBottom} />
            <text x={xForMs(todayMs) + 6} y={topPadding + 14}>Today</text>
          </g>
        )}
        {sortedHistory.map((point) => (
          <circle
            key={`${point.as_of_date}-${point.estimated ? 'estimate' : 'snapshot'}`}
            cx={xForDate(point.as_of_date)}
            cy={yForValue(Number(point.net_worth))}
            r={point.estimated ? 2 : 3.5}
            className={point.estimated ? 'trend-dot estimate' : 'trend-dot snapshot'}
          >
            <title>{`${point.as_of_date}: ${formatMoney(point.net_worth)}${point.estimated ? ' (estimate)' : ''}`}</title>
          </circle>
        ))}
        {visibleProjectionPoints.map((point) => (
          <circle
            key={`${point.as_of_date}-projection-hit`}
            cx={xForDate(point.as_of_date)}
            cy={yForValue(Number(point.net_worth))}
            r={7}
            className="trend-hit-target"
          >
            <title>{`${point.as_of_date}: ${formatMoney(point.net_worth)} (projection)`}</title>
          </circle>
        ))}
        {finalProjectionPoint && (
          <circle
            cx={xForDate(finalProjectionPoint.as_of_date)}
            cy={yForValue(Number(finalProjectionPoint.net_worth))}
            r={4}
            className="trend-dot projection endpoint"
          />
        )}
      </svg>
      <div className="chart-legend">
        <span><i className="legend-line history" />Historical snapshots</span>
        <span><i className="legend-line estimate" />Interpolated estimate</span>
        {visibleProjectionPoints.length > 0 && <span><i className="legend-line projection" />Projection</span>}
      </div>
    </div>
  );
}

export function OverviewPage({
  netWorth,
  history,
  projection,
  breakdownHistory,
  showInterpolatedHistory,
  onShowInterpolatedHistory,
  showProjectionOnTrajectory,
  onShowProjectionOnTrajectory,
}: {
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

      <section className="card">
        <div className="section-header trajectory-header">
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
            <table className="spaced-table" tabIndex={0} aria-label="Net worth history">
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

      <section className="card">
        <h2>What changed?</h2>
        <p className="muted">Break down each snapshot date by asset and liability category.</p>
        {breakdownHistory?.points.length ? (
          <div className="table-scroll" tabIndex={0} role="region" aria-label="Net worth breakdown history">
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
