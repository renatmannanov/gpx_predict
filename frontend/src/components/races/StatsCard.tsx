import type { RaceStats } from '../../types/races';
import './StatsCard.css';

interface StatsCardProps {
  stats: RaceStats;
}

export default function StatsCard({ stats }: StatsCardProps) {
  const hasDnf = (stats.dnf_count ?? 0) > 0;

  return (
    <div className="stats-row">
      <div className="stat-item">
        <div className="stat-n">
          <em>{stats.finishers}</em>
        </div>
        <div className="stat-l">финишеров</div>
      </div>
      <div className="stat-item">
        <div className="stat-n">{stats.best_time}</div>
        <div className="stat-l">лучший</div>
      </div>
      <div className="stat-item">
        <div className="stat-n">{stats.median_time}</div>
        <div className="stat-l">медиана</div>
      </div>
      {hasDnf && (
        <div className="stat-item stat-dnf">
          <div className="stat-n">{stats.dnf_count} DNF</div>
          <div className="stat-l">
            {stats.dnf_rate != null ? `${stats.dnf_rate}%` : ''}
          </div>
        </div>
      )}
    </div>
  );
}
