import { HealthStatusCard } from '../components/HealthStatusCard';
import { MetricCard } from '../components/MetricCard';

export function DashboardPage() {
  return (
    <div className="page-stack">
      <section className="hero panel">
        <div className="hero__content">
          <p className="panel__eyebrow">Portfolio-ready frontend</p>
          <h2 className="hero__title">Turn backend signals into a polished financial experience.</h2>
          <p className="hero__text">
            This first frontend milestone focuses on clarity, visual hierarchy and a clean entry point for the
            forecasting workflow.
          </p>
        </div>

        <div className="hero__grid">
          <MetricCard label="Focus" value="Forecast first" description="Build the shortest path from API to insight." />
          <MetricCard label="Stack" value="React + Vite" description="Fast iteration with a modern TypeScript base." />
          <MetricCard label="Goal" value="Demo ready" description="Designed to impress recruiters and stakeholders." />
        </div>
      </section>

      <div className="two-column-grid">
        <HealthStatusCard />

        <section className="panel">
          <div className="panel__header">
            <div>
              <p className="panel__eyebrow">Week 1 deliverable</p>
              <h2 className="panel__title">Foundation in place</h2>
            </div>
          </div>

          <ul className="timeline">
            <li>Scaffold React + Vite + TypeScript.</li>
            <li>Set up routing, theme tokens and layout.</li>
            <li>Add a typed API client for backend integration.</li>
            <li>Connect the health endpoint and validate the flow.</li>
          </ul>
        </section>
      </div>
    </div>
  );
}
