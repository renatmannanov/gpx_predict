import type { PercentileBucket } from '../../types/races';
import './TimeHistogram.css';
import './PercentileHistogram.css';

interface PercentileHistogramProps {
  buckets: PercentileBucket[];
}

const FILL_COLORS: Record<string, string> = {
  elite: 'rgba(60, 199, 122, 0.35)',
  good: 'rgba(74, 222, 200, 0.25)',
  mid: 'rgba(214, 188, 72, 0.25)',
  below: 'rgba(232, 98, 42, 0.25)',
  low: 'rgba(122, 131, 148, 0.20)',
};

const LABEL_COLORS: Record<string, string> = {
  elite: '#3CC77A',
  good: '#4adec8',
  mid: '#d6bc48',
  below: '#E8622A',
  low: '#7A8394',
};

export default function PercentileHistogram({ buckets }: PercentileHistogramProps) {
  if (!buckets.length) return null;

  const maxCount = Math.max(...buckets.map((b) => b.count));

  return (
    <div className="pct-histogram">
      <h3 className="histogram-title">
        Распределение участников{' '}
        <span className="histogram-subtitle">по персентилям</span>
      </h3>
      <div className="histogram-bars">
        {buckets.map((b) => (
          <div key={b.level} className="histogram-row">
            <span
              className="histogram-label"
              style={{ color: LABEL_COLORS[b.level] }}
            >
              {b.label}
            </span>
            <div className="histogram-track">
              <div
                className="histogram-fill"
                style={{
                  width: `${maxCount > 0 ? (b.count / maxCount) * 100 : 0}%`,
                  background: FILL_COLORS[b.level],
                }}
              />
            </div>
            <span className="histogram-value">
              <strong>{b.count}</strong>{' '}
              <span className="histogram-pct">({b.percent}%)</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
