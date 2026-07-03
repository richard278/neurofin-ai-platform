import { useHealthQuery } from '../hooks/useHealthQuery';

export function HealthStatusCard() {
  const healthQuery = useHealthQuery();

  return (
    <section className="panel health-card">
      <div className="panel__header">
        <div>
          <p className="panel__eyebrow">Backend status</p>
          <h2 className="panel__title">Live connection to FastAPI</h2>
        </div>
        <span className={`status-pill status-pill--${healthQuery.data?.status === 'ok' ? 'success' : 'idle'}`}>
          {healthQuery.isLoading ? 'Checking' : healthQuery.isError ? 'Offline' : healthQuery.data?.status ?? 'Unknown'}
        </span>
      </div>

      <div className="health-card__content">
        {healthQuery.isLoading && <p className="muted">Checking backend availability...</p>}

        {healthQuery.isError && (
          <p className="muted">
            Unable to reach the API yet. Make sure the backend is running on <strong>http://localhost:8000</strong>.
          </p>
        )}

        {healthQuery.data && (
          <dl className="key-values">
            <div>
              <dt>Status</dt>
              <dd>{healthQuery.data.status}</dd>
            </div>
            <div>
              <dt>App</dt>
              <dd>{healthQuery.data.app_name ?? 'NeuroFin Forecast API'}</dd>
            </div>
            <div>
              <dt>Version</dt>
              <dd>{healthQuery.data.version ?? '0.1.0'}</dd>
            </div>
            <div>
              <dt>Environment</dt>
              <dd>{healthQuery.data.environment ?? 'development'}</dd>
            </div>
          </dl>
        )}
      </div>
    </section>
  );
}
