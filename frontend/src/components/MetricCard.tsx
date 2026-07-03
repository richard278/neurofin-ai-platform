interface MetricCardProps {
  label: string;
  value: string;
  description: string;
  icon?: React.ReactNode;
  trend?: 'up' | 'down' | 'neutral';
}

export function MetricCard({ label, value, description, icon, trend }: MetricCardProps) {
  return (
    <article className="metric-card">
      <div className="metric-card__header">
        <p className="metric-card__label">{label}</p>
        {icon && <span className="metric-card__icon">{icon}</span>}
      </div>
      <div className="metric-card__body">
        <p className={`metric-card__value ${trend ? `metric-card__value--${trend}` : ''}`}>
          {value}
        </p>
        <p className="metric-card__description">{description}</p>
      </div>
    </article>
  );
}
