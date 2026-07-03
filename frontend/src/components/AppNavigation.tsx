import { NavLink } from 'react-router-dom';

const navigation = [
  { to: '/', label: 'Dashboard' },
  { to: '/forecast', label: 'Forecast' },
  { to: '/health', label: 'System' },
];

export function AppNavigation() {
  return (
    <nav className="app-nav" aria-label="Primary">
      {navigation.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/'}
          className={({ isActive }) => `app-nav__link${isActive ? ' app-nav__link--active' : ''}`}
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}
