import type { GenderDistribution } from '../../types/races';
import './GenderChart.css';

interface GenderChartProps {
  distribution: GenderDistribution[];
}

const GENDER_COLORS: Record<string, string> = {
  M: 'var(--accent-road)',
  F: 'var(--accent)',
};

const GENDER_LABELS: Record<string, string> = {
  M: 'Мужчины',
  F: 'Женщины',
};

export default function GenderChart({ distribution }: GenderChartProps) {
  if (!distribution.length) return null;

  const total = distribution.reduce((s, d) => s + d.count, 0);

  // Build conic-gradient segments
  let cumPercent = 0;
  const segments = distribution.map((d) => {
    const start = cumPercent;
    cumPercent += d.percent;
    const color = GENDER_COLORS[d.gender] || 'var(--dim)';
    return `${color} ${start}% ${cumPercent}%`;
  });
  const gradient = `conic-gradient(${segments.join(', ')})`;

  return (
    <div className="gender-chart">
      <h3 className="gender-chart-title">Пол</h3>
      <div className="gender-chart-body">
        <div className="gender-donut" style={{ background: gradient }}>
          <div className="gender-donut-hole">
            <span className="gender-donut-total">{total}</span>
          </div>
        </div>
        <div className="gender-legend">
          {distribution.map((d) => (
            <div key={d.gender} className="gender-legend-item">
              <span
                className="gender-legend-dot"
                style={{ background: GENDER_COLORS[d.gender] || 'var(--dim)' }}
              />
              <span className="gender-legend-label">
                {GENDER_LABELS[d.gender] || d.gender}
              </span>
              <span className="gender-legend-value">
                {d.count} ({d.percent}%)
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
