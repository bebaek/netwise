import { useEffect, useState, type FormEvent } from 'react';
import type { ProjectionScenario } from '../../api';
import { useProjectionScenarioMutations } from '../../queries/projectionScenarios';

type EditorMode = 'create' | 'duplicate' | 'edit' | null;

export function ScenarioToolbar({
  householdId,
  scenarios,
  selectedScenario,
  canEdit,
  onSelectScenario,
  onCompare,
}: {
  householdId: string;
  scenarios: ProjectionScenario[];
  selectedScenario: ProjectionScenario;
  canEdit: boolean;
  onSelectScenario: (scenarioId: string, replace?: boolean) => void;
  onCompare: () => void;
}) {
  const [editorMode, setEditorMode] = useState<EditorMode>(null);
  const [error, setError] = useState('');
  const mutations = useProjectionScenarioMutations(householdId);

  useEffect(() => {
    setError('');
    setEditorMode(null);
  }, [selectedScenario.id]);

  function openEditor(mode: Exclude<EditorMode, null>) {
    setError('');
    setEditorMode(mode);
  }

  async function submitEditor(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const name = String(form.get('scenario_name') ?? '').trim();
    const description = String(form.get('scenario_description') ?? '').trim();
    if (!name) return;
    setError('');
    try {
      if (editorMode === 'create') {
        const scenario = await mutations.create.mutateAsync({
          name,
          description: description || undefined,
        });
        onSelectScenario(scenario.id);
      } else if (editorMode === 'duplicate') {
        const scenario = await mutations.duplicate.mutateAsync({
          sourceScenarioId: selectedScenario.id,
          payload: { name, description: description || undefined },
        });
        onSelectScenario(scenario.id);
      } else if (editorMode === 'edit') {
        await mutations.update.mutateAsync({
          scenarioId: selectedScenario.id,
          payload: { name, description: description || null },
        });
      }
      setEditorMode(null);
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  async function removeSelectedScenario() {
    const confirmation = window.prompt(
      `Type "${selectedScenario.name}" to delete this independent scenario.`,
    );
    if (confirmation !== selectedScenario.name) return;
    const baseline = scenarios.find((scenario) => scenario.is_baseline);
    if (!baseline) return;
    setError('');
    try {
      await mutations.remove.mutateAsync(selectedScenario.id);
      onSelectScenario(baseline.id, true);
    } catch (mutationError: unknown) {
      setError(String(mutationError));
    }
  }

  const editorTitle = editorMode === 'create'
    ? 'New scenario'
    : editorMode === 'duplicate'
      ? `Duplicate ${selectedScenario.name}`
      : 'Edit scenario';
  const defaultName = editorMode === 'duplicate'
    ? `${selectedScenario.name} copy`
    : editorMode === 'edit'
      ? selectedScenario.name
      : '';
  const defaultDescription = editorMode === 'edit'
    ? selectedScenario.description ?? ''
    : editorMode === 'duplicate'
      ? selectedScenario.description ?? ''
      : '';

  return (
    <section className="card scenario-toolbar" aria-labelledby="scenario-toolbar-heading">
      <div className="section-header">
        <div>
          <h2 id="scenario-toolbar-heading">Projection scenario</h2>
          <p className="muted">
            Scenario assumptions are independent. Changes here do not alter other scenarios.
          </p>
        </div>
        {selectedScenario.is_baseline && <span className="status-badge">Baseline</span>}
      </div>
      {error && <div className="error" role="alert">{error}</div>}
      <div className="scenario-toolbar-controls">
        <label>
          Current scenario
          <select
            aria-label="Current projection scenario"
            value={selectedScenario.id}
            onChange={(event) => onSelectScenario(event.target.value)}
          >
            {scenarios.map((scenario) => (
              <option key={scenario.id} value={scenario.id}>
                {scenario.name}{scenario.is_baseline ? ' (Baseline)' : ''}
              </option>
            ))}
          </select>
        </label>
        <div className="action-row">
          <button type="button" onClick={() => openEditor('create')} disabled={!canEdit || mutations.isPending}>
            New scenario
          </button>
          <button type="button" className="secondary-button" onClick={() => openEditor('duplicate')} disabled={!canEdit || mutations.isPending}>
            Duplicate
          </button>
          <button type="button" className="secondary-button" onClick={() => openEditor('edit')} disabled={!canEdit || mutations.isPending}>
            Rename
          </button>
          <button
            type="button"
            className="danger-button"
            onClick={removeSelectedScenario}
            disabled={!canEdit || selectedScenario.is_baseline || mutations.isPending}
          >
            Delete
          </button>
          <button
            type="button"
            className="secondary-button"
            disabled={scenarios.length < 2}
            title={scenarios.length < 2 ? 'Create another scenario to compare' : undefined}
            onClick={onCompare}
          >
            Compare
          </button>
        </div>
      </div>
      {selectedScenario.description && <p>{selectedScenario.description}</p>}
      {selectedScenario.created_from_scenario_id && (
        <p className="muted">This is an independent copy. Later source changes are not synchronized.</p>
      )}
      {editorMode && (
        <form className="scenario-editor" onSubmit={submitEditor}>
          <h3>{editorTitle}</h3>
          <label>
            Name
            <input name="scenario_name" defaultValue={defaultName} maxLength={120} required autoFocus />
          </label>
          <label>
            Description
            <textarea name="scenario_description" defaultValue={defaultDescription} maxLength={1000} rows={3} />
          </label>
          {editorMode === 'duplicate' && (
            <p className="muted">Duplication creates a complete independent copy of the selected scenario.</p>
          )}
          <div className="action-row">
            <button type="submit" disabled={mutations.isPending}>Save scenario</button>
            <button type="button" className="secondary-button" onClick={() => setEditorMode(null)}>Cancel</button>
          </div>
        </form>
      )}
    </section>
  );
}
