import type { RunnerProfile } from '../../types/races';
import './RunnerSummary.css';

interface RunnerSummaryProps {
  profile: RunnerProfile;
  totalRaces: number;
  medianPercentile: number | null;
  yearsActive: number;
}

export default function RunnerSummary({
  profile,
  totalRaces,
  medianPercentile,
  yearsActive,
}: RunnerSummaryProps) {
  const subtitle = [profile.club, profile.category].filter(Boolean).join(' · ');

  return (
    <div className="runner-header">
      <h1>{profile.name}</h1>
      {subtitle && <p className="runner-subtitle">{subtitle}</p>}

      <div className="stats-row runner-stats">
        <div className="stat-item">
          <div className="stat-n"><em>{totalRaces}</em></div>
          <div className="stat-l">{pluralRaces(totalRaces)}</div>
        </div>
        <div className="stat-item">
          <div className="stat-n">
            {medianPercentile != null ? `top-${Math.round(medianPercentile)}%` : '—'}
          </div>
          <div className="stat-l">средний</div>
        </div>
        <div className="stat-item">
          <div className="stat-n">{yearsActive}</div>
          <div className="stat-l">{pluralYears(yearsActive)}</div>
        </div>
      </div>
    </div>
  );
}

function pluralRaces(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 14) return 'гонок';
  if (mod10 === 1) return 'гонка';
  if (mod10 >= 2 && mod10 <= 4) return 'гонки';
  return 'гонок';
}

function pluralYears(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 14) return 'лет на сцене';
  if (mod10 === 1) return 'год на сцене';
  if (mod10 >= 2 && mod10 <= 4) return 'года на сцене';
  return 'лет на сцене';
}
