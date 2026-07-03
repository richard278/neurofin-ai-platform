import { Link, Outlet } from 'react-router-dom';
import { AppLogo } from '../components/AppLogo';
import { AppNavigation } from '../components/AppNavigation';
import { ThemeToggle } from '../components/ThemeToggle';
import { useThemeMode } from '../hooks/useThemeMode';

export function AppLayout() {
  const { theme, toggleTheme } = useThemeMode();

  return (
    <div className="app-shell">
      <aside className="app-shell__sidebar">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--space-2)', width: '100%' }}>
          <AppLogo />
          <ThemeToggle theme={theme} toggleTheme={toggleTheme} />
        </div>
        <p className="app-shell__subtitle" style={{ fontSize: '0.85rem', margin: 'var(--space-2) 0 var(--space-4)', color: 'var(--text-soft)', lineHeight: '1.5' }}>
          Interactive ML time-series forecasting engine with a clean DDD architecture.
        </p>
        <AppNavigation />
        <div className="app-shell__note" style={{ marginTop: 'auto', background: 'var(--bg-elevated)', borderColor: 'var(--border-strong)' }}>
          <span className="app-shell__note-label" style={{ color: 'var(--accent)', fontSize: '0.68rem', fontWeight: 700 }}>PROJECT SANDBOX</span>
          <p style={{ fontSize: '0.78rem', margin: '6px 0 0', lineHeight: '1.4', color: 'var(--text-soft)' }}>
            Developed as a high-fidelity visual proof-of-concept demonstrating React, FastAPI, and financial engineering integrations.
          </p>
        </div>
      </aside>

      <main className="app-shell__main" style={{ display: 'flex', flexDirection: 'column' }}>
        <header className="topbar">
          <div>
            <p className="topbar__eyebrow" style={{ color: 'var(--accent)', margin: 0 }}>NeuroFin AI Sandbox</p>
            <h1 className="topbar__title" style={{ fontSize: '1.45rem', fontWeight: 800, margin: '4px 0 0' }}>Financial Analysis Terminal</h1>
          </div>
          <Link className="topbar__cta" to="/forecast">
            <span>Run Forecast</span>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginLeft: '4px' }}>
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
          </Link>
        </header>

        <section className="app-shell__content" style={{ flex: 1 }}>
          <Outlet />
        </section>
      </main>
    </div>
  );
}
