import type { RaceStats } from '../../types/races';
import './StatsCard.css';

interface StatsCardProps {
  stats: RaceStats;
}

export default function StatsCard({ stats }: StatsCardProps) {
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
    </div>
  );
}
