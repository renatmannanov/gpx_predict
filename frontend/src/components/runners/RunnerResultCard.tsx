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
  const pct = Math.round(result.percentile);
  const highlight = isFinished && pct <= 1;

  return (
    <Link
      to={`/races/${result.race_id}?distance=${encodeURIComponent(result.distance_name)}`}
      className={`result-row${highlight ? ' hi' : ''}`}
    >
      {/* col 1: race + distance */}
      <div>
        <div className="rr-race">{result.race_name}</div>
        <div className="rr-dist">{result.distance_name}</div>
      </div>

      {/* col 2: trend (left-aligned, before time) */}
      {diff ? (
        <div className={`rr-trend ${diff.improved ? 'tup' : 'tdn'}`}>
          {diff.improved ? '▲' : '▼'} {diff.label} vs {diff.vsYear}
        </div>
      ) : (
        <div />
      )}

      {/* col 3: time + place */}
      {isFinished ? (
        <div>
          <div className="rr-time">{result.time_formatted}</div>
          <div className="rr-place">#{result.place} из {result.total_finishers}</div>
        </div>
      ) : (
        <div>
          <div className="rr-time rr-dnf">{getStatusLabel(result.status)}</div>
        </div>
      )}

      {/* col 4: percentile badge */}
      {isFinished ? (
        <PercentileBadge percentile={result.percentile} />
      ) : (
        <div />
      )}
    </Link>
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
