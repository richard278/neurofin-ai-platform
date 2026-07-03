import { HealthStatusCard } from '../components/HealthStatusCard';
import { MetricCard } from '../components/MetricCard';

export function DashboardPage() {
  return (
    <div className="page-stack" style={{ gap: 'var(--space-8)' }}>
      <section className="hero-section" style={{ padding: 'var(--space-2) 0', display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
        <p className="panel__eyebrow" style={{ color: 'var(--accent)', margin: 0 }}>Fintech Portfolio Showcase</p>
        <h2 className="hero__title" style={{ background: 'linear-gradient(135deg, var(--text) 45%, var(--accent) 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', margin: 0, fontSize: 'clamp(2rem, 3.5vw, 2.75rem)', lineHeight: '1.25' }}>
          Turn Predictive Signals into Intelligible Financial Projections
        </h2>
        <p className="hero__text" style={{ color: 'var(--text-soft)', fontSize: '1.02rem', lineHeight: '1.6', maxWidth: '48rem', margin: 0 }}>
          An interactive dashboard built with React, Vite, and TypeScript. It queries a domain-driven FastAPI service in the backend to project financial parameters, asset defaults, and microfinance delinquency ratios.
        </p>
      </section>

      <div className="hero__grid" style={{ gap: 'var(--space-5)' }}>
        <MetricCard
          label="Product Focus"
          value="Forecast Engine"
          description="Shortest path from complex backend econometric models to readable charting insights."
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <circle cx="12" cy="12" r="6" />
              <circle cx="12" cy="12" r="2" />
            </svg>
          }
        />
        <MetricCard
          label="Core Stack"
          value="React & FastAPI"
          description="Blazing fast hot-module reload with Vite frontend paired with high-performance Python services."
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="12 2 2 7 12 12 22 7 12 2" />
              <polyline points="2 17 12 22 22 17" />
              <polyline points="2 12 12 17 22 12" />
            </svg>
          }
        />
        <MetricCard
          label="Architecture"
          value="Clean & Typed"
          description="Domain-Driven Design (DDD) on the backend; fully typed schemas and React-Query state on the frontend."
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
            </svg>
          }
        />
      </div>

      <div className="two-column-grid" style={{ gap: 'var(--space-5)' }}>
        <HealthStatusCard />

        <section className="panel" style={{ borderTop: '1px solid rgba(255, 255, 255, 0.04)' }}>
          <div className="panel__header">
            <div>
              <p className="panel__eyebrow">Sandbox Milestone</p>
              <h2 className="panel__title">Architecture Checklist</h2>
            </div>
          </div>

          <ul className="timeline">
            <li><strong>Frontend Scaffold:</strong> React 18 + Vite + TypeScript compiling cleanly for production.</li>
            <li><strong>Design System:</strong> CSS Custom Properties carrying exact Prussian Blue & Emerald Green branding.</li>
            <li><strong>State & API Client:</strong> Fully typed fetch client managed through TanStack React Query cache lifecycle.</li>
            <li><strong>Backend Service:</strong> RESTful FastAPI server implementing a simple moving average baseline model.</li>
          </ul>
        </section>
      </div>
    </div>
  );
}
