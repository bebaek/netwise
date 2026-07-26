import { useEffect, useState, type FormEventHandler } from 'react';
import { useSearchParams } from 'react-router';
import type { Account, NetWorthProjection } from '../api';
import { IncomeAndTaxSection } from '../components/planning/IncomeAndTaxSection';
import { PlanningEventsSection } from '../components/planning/PlanningEventsSection';
import { ProjectionSection } from '../components/planning/ProjectionSection';
import {
  AutomaticPropertySalesSection,
  PlannedPropertySalesSection,
} from '../components/planning/RealEstatePlanningSections';
import { ScenarioAssumptionsSection } from '../components/planning/ScenarioAssumptionsSection';
import { ScenarioComparison } from '../components/planning/ScenarioComparison';
import { ScenarioToolbar } from '../components/planning/ScenarioToolbar';
import { SocialSecuritySection } from '../components/planning/SocialSecuritySection';
import { usePlanningBudgetData, usePlanningPeopleData } from '../queries/planning';
import { useProjectionScenarios } from '../queries/projectionScenarios';
import { usePlanningRealEstateData } from '../queries/realEstate';

export function PlanningPage({
  householdId,
  defaultDate,
  accounts,
  assetAccounts,
  propertyAccounts,
  accountNameById,
  canEdit,
  onGetProjection,
  projectionRunning,
  projection,
  onInvalidateProjection,
}: {
  householdId: string;
  defaultDate: string;
  accounts: Account[];
  assetAccounts: Account[];
  propertyAccounts: Account[];
  accountNameById: ReadonlyMap<string, string>;
  canEdit: boolean;
  onGetProjection: FormEventHandler<HTMLFormElement>;
  projectionRunning: boolean;
  projection: NetWorthProjection | null;
  onInvalidateProjection: () => void;
}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [comparing, setComparing] = useState(false);
  const scenariosQuery = useProjectionScenarios(householdId);
  const scenarios = scenariosQuery.data ?? [];
  const requestedScenarioId = searchParams.get('scenario');
  const baseline = scenarios.find((scenario) => scenario.is_baseline);
  const selectedScenario = scenarios.find((scenario) => scenario.id === requestedScenarioId)
    ?? baseline;
  const scenarioId = selectedScenario?.id ?? '';

  const planningPeopleData = usePlanningPeopleData(householdId, scenarioId);
  const incomeSources = planningPeopleData.incomeSources.data ?? [];
  const householdPeople = planningPeopleData.householdPeople.data ?? [];
  const socialSecurityEstimates = planningPeopleData.socialSecurityEstimates.data ?? [];
  const planningBudgetData = usePlanningBudgetData(householdId, scenarioId);
  const spendingItems = planningBudgetData.spendingItems.data ?? [];
  const taxRecords = planningBudgetData.taxRecords.data ?? [];
  const planningRealEstateData = usePlanningRealEstateData(householdId, scenarioId);
  const realEstateSales = planningRealEstateData.sales.data ?? [];
  const liquidationStrategies = planningRealEstateData.liquidationStrategies.data ?? [];

  function selectScenario(nextScenarioId: string, replace = false) {
    setComparing(false);
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set('scenario', nextScenarioId);
      return next;
    }, { replace });
  }

  useEffect(() => {
    if (selectedScenario && requestedScenarioId !== selectedScenario.id) {
      selectScenario(selectedScenario.id, true);
    }
  }, [requestedScenarioId, selectedScenario?.id]);

  useEffect(() => {
    if (scenarioId) onInvalidateProjection();
  }, [scenarioId, onInvalidateProjection]);

  if (scenariosQuery.isPending) {
    return <div className="card" role="status">Loading projection scenarios…</div>;
  }
  if (scenariosQuery.error) {
    return <div className="error" role="alert">{String(scenariosQuery.error)}</div>;
  }
  if (!selectedScenario) {
    return <div className="error" role="alert">No baseline projection scenario is available.</div>;
  }

  return (
    <>
      <ScenarioToolbar
        householdId={householdId}
        scenarios={scenarios}
        selectedScenario={selectedScenario}
        canEdit={canEdit}
        onSelectScenario={selectScenario}
        onCompare={() => setComparing(true)}
      />

      {comparing ? (
        <ScenarioComparison
          householdId={householdId}
          scenarios={scenarios}
          currentScenarioId={scenarioId}
          onClose={() => setComparing(false)}
        />
      ) : (
      <div key={selectedScenario.id} className="scenario-planning-content">
        <ScenarioAssumptionsSection
          householdId={householdId}
          scenarioId={scenarioId}
          accounts={accounts}
          propertyAccounts={propertyAccounts}
          canEdit={canEdit}
        />

        <AutomaticPropertySalesSection
          householdId={householdId}
          scenarioId={scenarioId}
          assetAccounts={assetAccounts}
          propertyAccounts={propertyAccounts}
          accountNameById={accountNameById}
          strategies={liquidationStrategies}
          queryError={planningRealEstateData.liquidationStrategies.error}
          queryPending={planningRealEstateData.liquidationStrategies.isPending}
        />

        <ProjectionSection
          householdId={householdId}
          scenarioId={scenarioId}
          defaultDate={defaultDate}
          assetAccounts={assetAccounts}
          accountNameById={accountNameById}
          spendingItems={spendingItems}
          spendingQueryError={planningBudgetData.spendingItems.error}
          spendingQueryPending={planningBudgetData.spendingItems.isPending}
          householdPeople={householdPeople}
          hasIncomeSources={incomeSources.length > 0}
          onGetProjection={onGetProjection}
          projectionRunning={projectionRunning}
          projection={projection?.scenario_id === scenarioId ? projection : null}
          onInvalidateProjection={onInvalidateProjection}
        />

        <SocialSecuritySection
          householdId={householdId}
          scenarioId={scenarioId}
          householdPeople={householdPeople}
          incomeSources={incomeSources}
          estimates={socialSecurityEstimates}
          assetAccounts={assetAccounts}
          peopleError={planningPeopleData.householdPeople.error}
          estimatesError={planningPeopleData.socialSecurityEstimates.error}
          peoplePending={planningPeopleData.householdPeople.isPending}
          estimatesPending={planningPeopleData.socialSecurityEstimates.isPending}
        />

        <IncomeAndTaxSection
          householdId={householdId}
          scenarioId={scenarioId}
          defaultDate={defaultDate}
          assetAccounts={assetAccounts}
          accountNameById={accountNameById}
          incomeSources={incomeSources}
          taxRecords={taxRecords}
          incomeQueryError={planningPeopleData.incomeSources.error}
          incomeQueryPending={planningPeopleData.incomeSources.isPending}
          taxQueryError={planningBudgetData.taxRecords.error}
          taxQueryPending={planningBudgetData.taxRecords.isPending}
        />

        <PlannedPropertySalesSection
          householdId={householdId}
          scenarioId={scenarioId}
          assetAccounts={assetAccounts}
          propertyAccounts={propertyAccounts}
          accountNameById={accountNameById}
          sales={realEstateSales}
          queryError={planningRealEstateData.sales.error}
          queryPending={planningRealEstateData.sales.isPending}
        />

        <PlanningEventsSection
          householdId={householdId}
          scenarioId={scenarioId}
          defaultDate={defaultDate}
          accounts={accounts}
          accountNameById={accountNameById}
        />
      </div>
      )}
    </>
  );
}
