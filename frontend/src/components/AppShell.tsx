import { useEffect, useRef } from 'react';
import { Link, NavLink } from 'react-router-dom';
import type { Household, User } from '../api';

export type AppView = 'overview' | 'update' | 'plan' | 'assets' | 'settings';

type ViewDetails = {
  id: AppView;
  label: string;
  description: string;
};

export const APP_VIEWS: ViewDetails[] = [
  { id: 'overview', label: 'Overview', description: 'Your current position, history, and financial trajectory.' },
  { id: 'update', label: 'Update', description: 'Capture balances and maintain snapshot history.' },
  { id: 'plan', label: 'Plan', description: 'Model projections, income, events, and property sales.' },
  { id: 'assets', label: 'Assets', description: 'Manage accounts, properties, mortgages, and assumptions.' },
  { id: 'settings', label: 'Settings', description: 'Manage household access, imports, and exports.' },
];

export function appViewPath(view: AppView): string {
  return `/${view}`;
}

export function AppHeader({
  users,
  selectedUser,
  selectedUserId,
  onSelectUser,
  households,
  selectedHousehold,
  selectedHouseholdId,
  onSelectHousehold,
}: {
  users: User[];
  selectedUser?: User;
  selectedUserId: string;
  onSelectUser: (userId: string) => void;
  households: Household[];
  selectedHousehold?: Household;
  selectedHouseholdId: string;
  onSelectHousehold: (householdId: string) => void;
}) {
  return (
    <header className="app-header">
      <div className="brand-block">
        <p className="eyebrow">Netwise</p>
        <h1>{selectedHousehold?.name ?? 'Financial planning'}</h1>
        <p className="muted">Balance-snapshot planning without transaction tracking.</p>
      </div>
      <div className="selector-stack">
        {selectedUser && (
          <select
            value={selectedUserId}
            onChange={(event) => onSelectUser(event.target.value)}
            aria-label="Selected user"
          >
            {users.map((user) => (
              <option key={user.id} value={user.id}>
                {user.display_name}
              </option>
            ))}
          </select>
        )}
        {selectedHousehold && (
          <select
            value={selectedHouseholdId}
            onChange={(event) => onSelectHousehold(event.target.value)}
            aria-label="Selected household"
          >
            {households.map((household) => (
              <option key={household.id} value={household.id}>
                {household.name}
              </option>
            ))}
          </select>
        )}
      </div>
    </header>
  );
}

export function AppNavigation() {
  return (
    <nav className="app-nav" aria-label="Primary navigation">
      {APP_VIEWS.map((view) => (
        <NavLink
          key={view.id}
          to={appViewPath(view.id)}
          className={({ isActive }) => `app-nav-button${isActive ? ' active' : ''}`}
        >
          {view.label}
        </NavLink>
      ))}
    </nav>
  );
}

export function ViewHeading({
  activeView,
  householdName,
}: {
  activeView: AppView;
  householdName: string;
}) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const details = APP_VIEWS.find((view) => view.id === activeView) ?? APP_VIEWS[0];

  useEffect(() => {
    headingRef.current?.focus();
  }, [activeView]);

  useEffect(() => {
    const title = `${details.label} · ${householdName} · Netwise`;
    document.title = title;
    return () => {
      if (document.title === title) document.title = 'Netwise';
    };
  }, [details.label, householdName]);

  return (
    <section className="page-heading">
      <div>
        <p className="eyebrow">{details.label}</p>
        <h2 ref={headingRef} tabIndex={-1}>{details.label}</h2>
        <p className="muted">{details.description}</p>
      </div>
      {activeView === 'overview' && (
        <Link className="button-link" to={appViewPath('update')}>Update balances</Link>
      )}
    </section>
  );
}
