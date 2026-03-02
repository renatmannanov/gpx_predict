import type { TimeBucket } from '../../types/races';
import './TimeHistogram.css';

interface TimeHistogramProps {
  buckets: TimeBucket[];
  isBackyard?: boolean;
}

function humanizeLabel(label: string, index: number, total: number, isBackyard: boolean): string {
  if (index === 0 && label.startsWith('>')) {
    // Backyard: first bucket is ">" (longest times = best)
    return 'больше ' + label.slice(2);
  }
  if (index === 0 && label.startsWith('<')) {
    // Standard: "< 57:30" → "быстрее 57:30"
    return 'быстрее ' + label.slice(2);
  }
  if (index === total - 1 && label.startsWith('<') && isBackyard) {
    // Backyard: last bucket is "<" (shortest times = worst)
    return 'меньше ' + label.slice(2);
  }
  if (index === total - 1 && label.startsWith('>')) {
    // Standard: "> 1:54:13" → "медленнее 1:54:13"
    return 'медленнее ' + label.slice(2);
  }
  return label;
}

export default function TimeHistogram({ buckets, isBackyard = false }: TimeHistogramProps) {
  if (!buckets.length) return null;

  const maxCount = Math.max(...buckets.map((b) => b.count));

  return (
    <div className="time-histogram">
      <h3 className="histogram-title">
        {isBackyard ? 'Продолжительность' : 'Время финиша'}
        {' '}<span className="histogram-subtitle">— сколько участников финишировали в каждом диапазоне</span>
      </h3>
      <div className="histogram-bars">
        {buckets.map((b, i) => (
          <div key={i} className="histogram-row">
            <span className="histogram-label">
              {humanizeLabel(b.label, i, buckets.length, isBackyard)}
            </span>
            <div className="histogram-track">
              <div
                className="histogram-fill"
                style={{ width: `${maxCount > 0 ? (b.count / maxCount) * 100 : 0}%` }}
              />
            </div>
            <span className="histogram-value">
              {b.count} <span className="histogram-pct">({b.percent}%)</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
