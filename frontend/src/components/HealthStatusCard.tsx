import { useHealthQuery } from '../hooks/useHealthQuery';

export function HealthStatusCard() {
  const healthQuery = useHealthQuery();

  return (
    <section className="panel health-card health-card-compact" style={{ borderTop: '1px solid rgba(255, 255, 255, 0.04)' }}>
      <div className="panel__header">
        <div>
          <p className="panel__eyebrow">API Integration</p>
          <h2 className="panel__title">FastAPI Backend Status</h2>
        </div>
        <span className={`status-pill status-pill--${healthQuery.data?.status === 'ok' ? 'success' : 'idle'}`}>
          {healthQuery.data?.status === 'ok' && <span className="pulse-dot" style={{ marginRight: '6px' }} />}
          {healthQuery.isLoading ? 'Checking' : healthQuery.isError ? 'Offline' : healthQuery.data?.status ?? 'Unknown'}
        </span>
      </div>

      <div className="health-card__content">
        {healthQuery.isLoading && <p className="muted">Checking backend availability...</p>}

        {healthQuery.isError && (
          <p className="muted">
            Unable to reach the API. Make sure the backend is running on <strong>http://localhost:8000</strong> using `npm run dev`.
          </p>
        )}

        {healthQuery.data && (
          <dl className="key-values health-grid-compact">
            <div>
              <dt>
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px', verticalAlign: 'middle', opacity: 0.8 }}>
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
                <span>Status</span>
              </dt>
              <dd style={{ color: 'var(--accent)' }}>{healthQuery.data.status}</dd>
            </div>
            <div>
              <dt>
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px', verticalAlign: 'middle', opacity: 0.8 }}>
                  <rect x="4" y="4" width="16" height="16" rx="2" />
                  <rect x="9" y="9" width="6" height="6" />
                  <path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 15h3M1 9h3M1 15h3" />
                </svg>
                <span>Service</span>
              </dt>
              <dd>{healthQuery.data.app_name ?? 'NeuroFin Forecast API'}</dd>
            </div>
            <div>
              <dt>
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px', verticalAlign: 'middle', opacity: 0.8 }}>
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
                <span>Version</span>
              </dt>
              <dd>{healthQuery.data.version ?? '0.1.0'}</dd>
            </div>
            <div>
              <dt>
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px', verticalAlign: 'middle', opacity: 0.8 }}>
                  <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
                </svg>
                <span>Environment</span>
              </dt>
              <dd style={{ color: 'var(--metric-history-color)' }}>{healthQuery.data.environment ?? 'development'}</dd>
            </div>
          </dl>
        )}
      </div>
    </section>
  );
}
