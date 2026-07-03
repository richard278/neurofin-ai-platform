import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <section className="panel not-found">
      <p className="panel__eyebrow">404</p>
      <h2 className="panel__title">Page not found</h2>
      <p className="muted">The requested route does not exist yet. Return to the dashboard to continue.</p>
      <Link className="topbar__cta" to="/">
        Go home
      </Link>
    </section>
  );
}
