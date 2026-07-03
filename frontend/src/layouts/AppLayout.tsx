import { Link, Outlet } from 'react-router-dom';
import { AppLogo } from '../components/AppLogo';
import { AppNavigation } from '../components/AppNavigation';

export function AppLayout() {
  return (
    <div className="app-shell">
      <aside className="app-shell__sidebar">
        <AppLogo />
        <p className="app-shell__subtitle">A premium portfolio dashboard for financial forecasting.</p>
        <AppNavigation />
        <div className="app-shell__note">
          <span className="app-shell__note-label">Week 1</span>
          <p>Scaffold, layout, routing, theme tokens and API client.</p>
        </div>
      </aside>

      <main className="app-shell__main">
        <header className="topbar">
          <div>
            <p className="topbar__eyebrow">NeuroFin AI Platform</p>
            <h1 className="topbar__title">Financial Forecasting Dashboard</h1>
          </div>
          <Link className="topbar__cta" to="/forecast">
            Open forecast
          </Link>
        </header>

        <section className="app-shell__content">
          <Outlet />
        </section>
      </main>
    </div>
  );
}
