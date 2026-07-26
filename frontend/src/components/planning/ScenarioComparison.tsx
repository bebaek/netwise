import { useId, useState, type FormEvent } from 'react';
import type { ProjectionComparisonScenario, ProjectionScenario } from '../../api';
import { useProjectionComparison } from '../../queries/planning';
import { formatMoney } from '../../utils/format';

const SERIES_STYLES = [
  { color: '#2563eb', dash: '', label: 'solid' },
  { color: '#d97706', dash: '10 5', label: 'long dash' },
  { color: '#059669', dash: '3 4', label: 'short dash' },
  { color: '#c026d3', dash: '12 4 3 4', label: 'dash dot' },
] as const;

const LIQUIDITY_CLASSES = new Set(['cash', 'liquid', 'marketable', 'retirement_liquid']);

function liquidAssetsTotal(
  point: ProjectionComparisonScenario['points'][number],
): number {
  return point.accounts.reduce((total, account) => (
    account.account_kind === 'asset' && LIQUIDITY_CLASSES.has(account.liquidity_class)
      ? total + Number(account.projected_balance)
      : total
  ), 0);
}

function ComparisonChart({
  title,
  scenarios,
  valueForPoint,
}: {
  title: string;
  scenarios: ProjectionComparisonScenario[];
  valueForPoint: (point: ProjectionComparisonScenario['points'][number]) => number;
}) {
  const titleId = useId();
  const width = 760;
  const height = 280;
  const padding = { top: 24, right: 24, bottom: 40, left: 104 };
  const allValues = scenarios.flatMap((scenario) => scenario.points.map(valueForPoint));
  const rawMinimum = Math.min(...allValues);
  const rawMaximum = Math.max(...allValues);
  const valuePadding = Math.max((rawMaximum - rawMinimum) * 0.08, 1);
  const minimum = rawMinimum - valuePadding;
  const maximum = rawMaximum + valuePadding;
  const pointCount = Math.max(...scenarios.map((scenario) => scenario.points.length));
  const x = (index: number) => padding.left
    + (index / Math.max(pointCount - 1, 1)) * (width - padding.left - padding.right);
  const y = (value: number) => padding.top
    + (height - padding.top - padding.bottom)
    - ((value - minimum) / Math.max(maximum - minimum, 1))
      * (height - padding.top - padding.bottom);
  const firstDate = scenarios[0]?.points[0]?.as_of_date ?? '';
  const lastDate = scenarios[0]?.points.at(-1)?.as_of_date ?? '';

  return (
    <div className="comparison-chart">
      <h3 id={titleId}>{title}</h3>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby={titleId}>
        <line x1={padding.left} y1={height - padding.bottom} x2={width - padding.right} y2={height - padding.bottom} className="axis" />
        <line x1={padding.left} y1={padding.top} x2={padding.left} y2={height - padding.bottom} className="axis" />
        <text x={padding.left - 10} y={padding.top + 4} textAnchor="end" className="axis-label">{formatMoney(String(maximum))}</text>
        <text x={padding.left - 10} y={height - padding.bottom + 4} textAnchor="end" className="axis-label">{formatMoney(String(minimum))}</text>
        {scenarios.map((scenario, scenarioIndex) => (
          <polyline
            key={scenario.scenario_id}
            points={scenario.points.map((point, pointIndex) => (
              `${x(pointIndex)},${y(valueForPoint(point))}`
            )).join(' ')}
            fill="none"
            stroke={SERIES_STYLES[scenarioIndex].color}
            strokeDasharray={SERIES_STYLES[scenarioIndex].dash || undefined}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="3"
          >
            <title>{scenario.scenario_name}</title>
          </polyline>
        ))}
        <text x={padding.left} y={height - 12} className="axis-label">{firstDate}</text>
        <text x={width - padding.right} y={height - 12} textAnchor="end" className="axis-label">{lastDate}</text>
      </svg>
      <div className="comparison-legend" aria-label={`${title} line styles`}>
        {scenarios.map((scenario, index) => (
          <span key={scenario.scenario_id}>
            <i
              aria-hidden="true"
              style={{
                borderTopColor: SERIES_STYLES[index].color,
                borderTopStyle: index === 0 ? 'solid' : 'dashed',
              }}
            />
            {scenario.scenario_name} ({SERIES_STYLES[index].label})
          </span>
        ))}
      </div>
    </div>
  );
}

export function ScenarioComparison({
  householdId,
  scenarios,
  currentScenarioId,
  onClose,
}: {
  householdId: string;
  scenarios: ProjectionScenario[];
  currentScenarioId: string;
  onClose: () => void;
}) {
  const firstOtherScenario = scenarios.find((scenario) => scenario.id !== currentScenarioId);
  const [selectedScenarioIds, setSelectedScenarioIds] = useState<string[]>([
    currentScenarioId,
    ...(firstOtherScenario ? [firstOtherScenario.id] : []),
  ]);
  const [startYear, setStartYear] = useState(new Date().getFullYear());
  const [endYear, setEndYear] = useState(new Date().getFullYear() + 20);
  const [comparisonRequest, setComparisonRequest] = useState<{
    scenarioIds: string[];
    startYear: number;
    endYear: number;
  } | null>(null);
  const comparison = useProjectionComparison(householdId, comparisonRequest);

  function toggleScenario(scenarioId: string) {
    setComparisonRequest(null);
    setSelectedScenarioIds((current) => current.includes(scenarioId)
      ? current.filter((id) => id !== scenarioId)
      : [...current, scenarioId]);
  }

  function runComparison(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedScenarioIds.length < 2 || selectedScenarioIds.length > 4) return;
    const nextRequest = {
      scenarioIds: selectedScenarioIds,
      startYear,
      endYear,
    };
    if (
      comparisonRequest
      && comparisonRequest.startYear === nextRequest.startYear
      && comparisonRequest.endYear === nextRequest.endYear
      && comparisonRequest.scenarioIds.join(',') === nextRequest.scenarioIds.join(',')
    ) {
      comparison.refetch();
      return;
    }
    setComparisonRequest(nextRequest);
  }

  const results = comparison.data?.scenarios ?? [];
  const periodCount = results[0]?.points.length ?? 0;

  return (
    <section className="card scenario-comparison" aria-labelledby="scenario-comparison-heading">
      <div className="section-header">
        <div>
          <h2 id="scenario-comparison-heading">Compare projection scenarios</h2>
          <p className="muted">Compare two to four deterministic annual projections over the same date range. No scenario is ranked or recommended.</p>
        </div>
        <button type="button" className="secondary-button" onClick={onClose}>Back to planning</button>
      </div>

      <form className="scenario-comparison-form" onSubmit={runComparison}>
        <fieldset>
          <legend>Scenarios</legend>
          <div className="comparison-scenario-options">
            {scenarios.map((scenario) => {
              const selected = selectedScenarioIds.includes(scenario.id);
              return (
                <label key={scenario.id}>
                  <input
                    type="checkbox"
                    checked={selected}
                    disabled={!selected && selectedScenarioIds.length >= 4}
                    onChange={() => toggleScenario(scenario.id)}
                  />
                  {scenario.name}{scenario.is_baseline ? ' (Baseline)' : ''}
                </label>
              );
            })}
          </div>
        </fieldset>
        <label>
          Start year
          <input
            type="number"
            value={startYear}
            onChange={(event) => {
              setStartYear(Number(event.target.value));
              setComparisonRequest(null);
            }}
            required
          />
        </label>
        <label>
          End year
          <input
            type="number"
            value={endYear}
            onChange={(event) => {
              setEndYear(Number(event.target.value));
              setComparisonRequest(null);
            }}
            required
          />
        </label>
        <button
          type="submit"
          disabled={selectedScenarioIds.length < 2
            || selectedScenarioIds.length > 4
            || endYear < startYear
            || comparison.isFetching}
        >
          {comparison.isFetching ? 'Comparing…' : 'Run comparison'}
        </button>
        {selectedScenarioIds.length < 2 && <p className="error" role="alert">Select at least two scenarios.</p>}
      </form>

      {comparison.error && <div className="error" role="alert">{String(comparison.error)}</div>}
      {comparison.isFetching && <div role="status">Calculating scenario comparison…</div>}

      {results.length > 0 && (
        <div className="comparison-results">
          <div className="comparison-summary-grid">
            {results.map((scenario, index) => (
              <article className="comparison-summary-card" key={scenario.scenario_id}>
                <h3>
                  <i
                    className="comparison-series-marker"
                    aria-hidden="true"
                    style={{ borderColor: SERIES_STYLES[index].color }}
                  />
                  {scenario.scenario_name}
                </h3>
                <dl>
                  <div><dt>Ending net worth</dt><dd>{formatMoney(scenario.ending_net_worth)}</dd></div>
                  <div><dt>Lowest net worth</dt><dd>{formatMoney(scenario.lowest_net_worth)}</dd></div>
                  <div><dt>Lowest liquid assets</dt><dd>{formatMoney(scenario.lowest_liquid_assets_total)}</dd></div>
                  <div><dt>First retirement withdrawal</dt><dd>{scenario.first_retirement_withdrawal_date ?? 'None'}</dd></div>
                  <div><dt>First unfunded period</dt><dd>{scenario.first_unfunded_date ?? 'None'}</dd></div>
                  <div><dt>Cumulative income</dt><dd>{formatMoney(scenario.cumulative_projected_income)}</dd></div>
                  <div><dt>Cumulative taxes</dt><dd>{formatMoney(scenario.cumulative_projected_taxes)}</dd></div>
                  <div><dt>Cumulative spending</dt><dd>{formatMoney(scenario.cumulative_projected_spending)}</dd></div>
                </dl>
                {scenario.warnings.length > 0 ? (
                  <div className="comparison-warnings">
                    <strong>Warnings</strong>
                    <ul>{scenario.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
                  </div>
                ) : <p className="muted">No projection warnings.</p>}
              </article>
            ))}
          </div>

          <div className="comparison-chart-grid">
            <ComparisonChart
              title="Net worth by scenario"
              scenarios={results}
              valueForPoint={(point) => Number(point.net_worth)}
            />
            <ComparisonChart
              title="Liquid assets by scenario"
              scenarios={results}
              valueForPoint={liquidAssetsTotal}
            />
          </div>

          <div className="table-scroll" tabIndex={0} role="region" aria-label="Annual scenario comparison values">
            <table className="spaced-table comparison-table" tabIndex={0}>
              <caption>Annual net worth and liquid assets for each scenario</caption>
              <thead>
                <tr>
                  <th rowSpan={2}>Period ending</th>
                  {results.map((scenario) => (
                    <th key={scenario.scenario_id} colSpan={2} scope="colgroup">{scenario.scenario_name}</th>
                  ))}
                </tr>
                <tr>
                  {results.flatMap((scenario) => [
                    <th key={`${scenario.scenario_id}-net-worth`}>Net worth</th>,
                    <th key={`${scenario.scenario_id}-liquid`}>Liquid assets</th>,
                  ])}
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: periodCount }, (_, pointIndex) => (
                  <tr key={results[0].points[pointIndex].as_of_date}>
                    <td>{results[0].points[pointIndex].as_of_date}</td>
                    {results.flatMap((scenario) => {
                      const point = scenario.points[pointIndex];
                      return [
                        <td key={`${scenario.scenario_id}-${pointIndex}-net-worth`}>{formatMoney(point.net_worth)}</td>,
                        <td key={`${scenario.scenario_id}-${pointIndex}-liquid`}>{formatMoney(String(liquidAssetsTotal(point)))}</td>,
                      ];
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
