import { Link } from 'react-router-dom';
import type { RunnerRaceResult } from '../../types/races';
import PercentileBadge from '../shared/PercentileBadge';
import './RunnerResultCard.css';

interface RunnerResultCardProps {
  result: RunnerRaceResult;
  previousResult?: RunnerRaceResult; // same race+distance, previous year
}

const FINISHED_STATUSES = ['finished', 'over_time_limit'];

export default function RunnerResultCard({ result, previousResult }: RunnerResultCardProps) {
  const isFinished = FINISHED_STATUSES.includes(result.status);
  const diff = getDiff(result, previousResult);

  return (
    <div className="rrc">
      <div className="rrc-top">
        <Link
          to={`/races/${result.race_id}?distance=${encodeURIComponent(result.distance_name)}`}
          className="rrc-race"
        >
          {result.race_name}
          <span className="rrc-dist"> · {result.distance_name}</span>
        </Link>
      </div>

      <div className="rrc-mid">
        {isFinished ? (
          <>
            <span className="rrc-time">{result.time_formatted}</span>
            <span className="rrc-sep">·</span>
            <span className="rrc-place">#{result.place} из {result.total_finishers}</span>
            <span className="rrc-sep">·</span>
            <PercentileBadge percentile={result.percentile} />
          </>
        ) : (
          <span className="rrc-dnf">{getStatusLabel(result.status)}</span>
        )}
      </div>

      {diff && (
        <div className={`rrc-diff ${diff.improved ? 'rrc-diff-up' : 'rrc-diff-down'}`}>
          {diff.improved ? '▲' : '▼'} {diff.label} vs {diff.vsYear}
        </div>
      )}
    </div>
  );
}

function getStatusLabel(status: string): string {
  switch (status) {
    case 'dnf': return 'DNF';
    case 'dns': return 'DNS';
    case 'dsq': return 'DSQ';
    default: return status.toUpperCase();
  }
}

interface DiffInfo {
  improved: boolean;
  label: string;
  vsYear: number;
}

function getDiff(
  current: RunnerRaceResult,
  previous?: RunnerRaceResult,
): DiffInfo | null {
  if (!previous) return null;
  if (!FINISHED_STATUSES.includes(current.status)) return null;
  if (!FINISHED_STATUSES.includes(previous.status)) return null;
  if (!current.time_s || !previous.time_s) return null;

  const diffS = current.time_s - previous.time_s;
  const improved = diffS < 0;
  const abs = Math.abs(diffS);
  const h = Math.floor(abs / 3600);
  const m = Math.floor((abs % 3600) / 60);
  const s = abs % 60;

  const sign = improved ? '-' : '+';
  const label = `${sign}${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;

  return { improved, label, vsYear: previous.year };
}
