import './PercentileBadge.css';

interface PercentileBadgeProps {
  percentile: number; // 0-100, lower = better
  compact?: boolean;  // true = "15%", false = "top-15%"
}

export function getPercentileClass(p: number): string {
  if (p <= 10) return 'pct-elite';
  if (p <= 25) return 'pct-good';
  if (p <= 50) return 'pct-mid';
  if (p <= 75) return 'pct-below';
  return 'pct-low';
}

export default function PercentileBadge({ percentile, compact }: PercentileBadgeProps) {
  const rounded = Math.round(percentile);
  const label = compact ? `${rounded}%` : `top-${rounded}%`;
  return (
    <span className={`pct-badge ${getPercentileClass(percentile)}`}>
      {label}
    </span>
  );
}
