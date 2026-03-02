import type { RaceStats } from '../../types/races';
import './DistStatsBlock.css';

interface DistStatsBlockProps {
  distanceName: string;
  distanceKm: number | null;
  elevationGain: number | null;
  stats: RaceStats;
}

export default function DistStatsBlock({
  distanceName,
  distanceKm,
  elevationGain,
  stats,
}: DistStatsBlockProps) {
  const hasDnf = (stats.dnf_count ?? 0) > 0;
  const hasDns = (stats.dns_count ?? 0) > 0;

  // Build meta string: "42 км ↑ 1200 м"
  const metaParts: string[] = [];
  if (distanceKm != null && distanceKm > 0) metaParts.push(`${distanceKm} км`);
  if (elevationGain != null && elevationGain > 0) metaParts.push(`↑ ${elevationGain} м`);
  const metaStr = metaParts.join(' · ');

  return (
    <div className="dist-stats">
      <div className="ds-top">
        <div className="ds-name">
          {distanceName}
          {metaStr && <span className="ds-name-meta">{metaStr}</span>}
        </div>
        <div className="ds-main">{stats.finishers} финишёров</div>
      </div>
      <div className="ds-strip">
        <div className="ds-left">
          <div className="dm">
            <div className="dm-n">{stats.best_time}</div>
            <div className="dm-l">лучший</div>
          </div>
          <div className="dm">
            <div className="dm-n">{stats.median_time}</div>
            <div className="dm-l">медиана</div>
          </div>
          <div className="dm">
            <div className="dm-n">{stats.worst_time}</div>
            <div className="dm-l">последний</div>
          </div>
        </div>
        {(hasDnf || hasDns) && (
          <div className="ds-right">
            {hasDnf && (
              <div className="dm-r">
                <div className="dm-n warn">{stats.dnf_count}</div>
                <div className="dm-l">DNF</div>
              </div>
            )}
            {hasDns && (
              <div className="dm-r">
                <div className="dm-n">{stats.dns_count}</div>
                <div className="dm-l">DNS</div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
