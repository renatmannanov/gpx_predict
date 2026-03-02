import type { CategoryDistribution } from '../../types/races';
import './CategoryBars.css';

interface CategoryBarsProps {
  distribution: CategoryDistribution[];
}

const MAX_CATEGORIES = 8;

export default function CategoryBars({ distribution }: CategoryBarsProps) {
  if (!distribution.length) return null;

  // Trim to max categories, group rest into "Другие"
  let items = distribution;
  if (items.length > MAX_CATEGORIES) {
    const shown = items.slice(0, MAX_CATEGORIES);
    const rest = items.slice(MAX_CATEGORIES);
    const restCount = rest.reduce((s, c) => s + c.count, 0);
    const restPercent = rest.reduce((s, c) => s + c.percent, 0);
    items = [
      ...shown,
      { category: 'Другие', count: restCount, percent: Math.round(restPercent * 10) / 10 },
    ];
  }

  const maxCount = Math.max(...items.map((c) => c.count));

  return (
    <div className="category-bars">
      <h3 className="category-bars-title">Категории</h3>
      <div className="category-bars-list">
        {items.map((c) => (
          <div key={c.category} className="category-bar-row">
            <span className="category-bar-label">{c.category}</span>
            <div className="category-bar-track">
              <div
                className={`category-bar-fill ${c.category.startsWith('F') ? 'fill-f' : 'fill-m'}`}
                style={{ width: `${maxCount > 0 ? (c.count / maxCount) * 100 : 0}%` }}
              />
            </div>
            <span className="category-bar-value">
              {c.count} <span className="category-bar-pct">({c.percent}%)</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
