export function AppLogo() {
  return (
    <div className="app-logo" aria-label="NeuroFin AI Platform">
      <div className="app-logo__mark" style={{ background: 'linear-gradient(135deg, var(--prussian-blue) 0%, #15427a 50%, var(--emerald-green) 100%)', boxShadow: '0 8px 22px rgba(15, 164, 122, 0.22), inset 0 1px 1px rgba(255, 255, 255, 0.15)', border: '1px solid rgba(15, 164, 122, 0.35)', borderRadius: '12px', width: '2.85rem', height: '2.85rem', display: 'grid', placeItems: 'center', transition: 'transform 0.2s cubic-bezier(0.16, 1, 0.3, 1)' }}>
        <svg viewBox="0 0 24 24" width="23" height="23" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M4 18h16M4 13h16M4 8h16" stroke="rgba(255, 255, 255, 0.12)" strokeWidth="1" />
          <path d="M4 16l5-5 4 4 7-8" stroke="url(#logo-grad)" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
          <circle cx="4" cy="16" r="2.5" fill="#ffffff" stroke="var(--prussian-blue)" strokeWidth="1.2" />
          <circle cx="9" cy="11" r="2.5" fill="var(--emerald-green)" stroke="#ffffff" strokeWidth="1.2" />
          <circle cx="13" cy="15" r="2.5" fill="var(--emerald-green)" stroke="#ffffff" strokeWidth="1.2" />
          <circle cx="20" cy="7" r="3.2" fill="#ffffff" stroke="var(--emerald-green)" strokeWidth="1.5" />
          <defs>
            <linearGradient id="logo-grad" x1="4" y1="16" x2="20" y2="7" gradientUnits="userSpaceOnUse">
              <stop stopColor="#60a5fa" />
              <stop offset="0.5" stopColor="#3b82f6" />
              <stop offset="100%" stopColor="var(--emerald-green)" />
            </linearGradient>
          </defs>
        </svg>
      </div>
      <div>
        <p className="app-logo__eyebrow" style={{ fontFamily: 'var(--font-heading)', fontWeight: 800, color: 'var(--text)', fontSize: '0.98rem', letterSpacing: '-0.02em', textTransform: 'none', margin: 0 }}>
          NeuroFin <span style={{ color: 'var(--accent)', fontWeight: 600 }}>AI</span>
        </p>
        <p className="app-logo__name" style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, margin: '2px 0 0 0' }}>
          Portfolio Sandbox
        </p>
      </div>
    </div>
  );
}
