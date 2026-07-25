import type { FormEventHandler } from 'react';
import type {
  Account,
  NetWorthProjection,
} from '../api';
import { IncomeAndTaxSection } from '../components/planning/IncomeAndTaxSection';
import { PlanningEventsSection } from '../components/planning/PlanningEventsSection';
import { ProjectionSection } from '../components/planning/ProjectionSection';
import {
  AutomaticPropertySalesSection,
  PlannedPropertySalesSection,
} from '../components/planning/RealEstatePlanningSections';
import { SocialSecuritySection } from '../components/planning/SocialSecuritySection';
import {
  usePlanningBudgetData,
  usePlanningPeopleData,
} from '../queries/planning';
import { usePlanningRealEstateData } from '../queries/realEstate';
export function PlanningPage({
  householdId,
  defaultDate,
  accounts,
  assetAccounts,
  propertyAccounts,
  accountNameById,
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
  onGetProjection: FormEventHandler<HTMLFormElement>;
  projectionRunning: boolean;
  projection: NetWorthProjection | null;
  onInvalidateProjection: () => void;
}) {
  const planningPeopleData = usePlanningPeopleData(householdId);
  const incomeSources = planningPeopleData.incomeSources.data ?? [];
  const householdPeople = planningPeopleData.householdPeople.data ?? [];
  const socialSecurityEstimates = planningPeopleData.socialSecurityEstimates.data ?? [];
  const planningBudgetData = usePlanningBudgetData(householdId);
  const spendingItems = planningBudgetData.spendingItems.data ?? [];
  const taxRecords = planningBudgetData.taxRecords.data ?? [];
  const planningRealEstateData = usePlanningRealEstateData(householdId);
  const realEstateSales = planningRealEstateData.sales.data ?? [];
  const liquidationStrategies = planningRealEstateData.liquidationStrategies.data ?? [];
  return (
    <>
<AutomaticPropertySalesSection
  householdId={householdId}
  assetAccounts={assetAccounts}
  propertyAccounts={propertyAccounts}
  accountNameById={accountNameById}
  strategies={liquidationStrategies}
  queryError={planningRealEstateData.liquidationStrategies.error}
  queryPending={planningRealEstateData.liquidationStrategies.isPending}
/>

<ProjectionSection
  householdId={householdId}
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
  projection={projection}
  onInvalidateProjection={onInvalidateProjection}
/>

<SocialSecuritySection
  householdId={householdId}
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
  assetAccounts={assetAccounts}
  propertyAccounts={propertyAccounts}
  accountNameById={accountNameById}
  sales={realEstateSales}
  queryError={planningRealEstateData.sales.error}
  queryPending={planningRealEstateData.sales.isPending}
/>

<PlanningEventsSection
  householdId={householdId}
  defaultDate={defaultDate}
  accounts={accounts}
  accountNameById={accountNameById}
/>
    </>
  );
}
