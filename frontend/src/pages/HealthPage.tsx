import { HealthStatusCard } from '../components/HealthStatusCard';

export function HealthPage() {
  return (
    <div className="page-stack">
      <section className="panel">
        <div className="panel__header">
          <div>
            <p className="panel__eyebrow">System view</p>
            <h2 className="panel__title">API health and environment details</h2>
          </div>
        </div>
        <p className="muted">Use this view to validate the connection to the FastAPI backend while developing the UI.</p>
      </section>

      <HealthStatusCard />
    </div>
  );
}
