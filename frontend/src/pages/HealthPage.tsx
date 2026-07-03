import { HealthStatusCard } from '../components/HealthStatusCard';

export function HealthPage() {
  return (
    <div className="health-page-container">
      <section className="panel health-hero-panel" style={{ borderTop: '1px solid rgba(255, 255, 255, 0.04)' }}>
        <div className="panel__header">
          <div>
            <p className="panel__eyebrow" style={{ color: 'var(--accent)', margin: 0 }}>System Diagnostics</p>
            <h2 className="panel__title">API Health & Setup</h2>
          </div>
        </div>
        <p className="muted" style={{ color: 'var(--text-soft)', margin: 0 }}>
          This view validates the secure connection to the FastAPI backend. Use this status grid to review active runtime variables, versions, and deployment environments.
        </p>
      </section>

      <HealthStatusCard />
    </div>
  );
}
