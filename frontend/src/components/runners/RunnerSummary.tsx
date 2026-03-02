import type { RunnerProfile } from '../../types/races';
import { getPercentileClass } from '../shared/PercentileBadge';
import './RunnerSummary.css';

interface RunnerSummaryProps {
  profile: RunnerProfile;
  totalRaces: number;
  medianPercentile: number | null;
  yearsActive: number;
  racesThisYear: number;
  currentYear: number;
  bestPlace: number | null;
}

export default function RunnerSummary({
  profile,
  totalRaces,
  medianPercentile,
  yearsActive,
  racesThisYear,
  currentYear,
  bestPlace,
}: RunnerSummaryProps) {
  const pctLabel = medianPercentile != null
    ? `top-${Math.round(medianPercentile)}%`
    : '—';
  const pctColorClass = medianPercentile != null
    ? getPercentileClass(medianPercentile)
    : '';

  // Build inline meta items for mobile
  const leftItems: string[] = [];
  if (profile.club) leftItems.push(profile.club);
  if (profile.category) leftItems.push(profile.category);
  leftItems.push(`${yearsActive} ${pluralYears(yearsActive, true)}`);

  const rightItems: string[] = [];
  rightItems.push(`${totalRaces} гонок`);
  rightItems.push(`${racesThisYear} в ${currentYear}`);
  if (bestPlace != null) rightItems.push(`#${bestPlace} лучшее`);

  return (
    <div className="runner-head">
      <div className="rh-top">
        <div className="rh-name">{profile.name}</div>
        <div className={`rh-pct ${pctColorClass}`}>{pctLabel}</div>
      </div>

      {/* Desktop: two-row grid with labels */}
      <div className="rh-strip rh-desktop">
        <div className="rh-left-meta">
          {profile.club && (
            <div className="rm">
              <div className="rm-n">{profile.club}</div>
              <div className="rm-l">клуб</div>
            </div>
          )}
          {profile.category && (
            <div className="rm">
              <div className="rm-n">{profile.category}</div>
              <div className="rm-l">категория</div>
            </div>
          )}
          <div className="rm">
            <div className="rm-n">{yearsActive}</div>
            <div className="rm-l">{pluralYears(yearsActive)}</div>
          </div>
        </div>
        <div className="rh-right-meta">
          <div className="rm-r">
            <div className="rm-n">{totalRaces}</div>
            <div className="rm-l">гонок всего</div>
          </div>
          <div className="rm-r">
            <div className="rm-n">{racesThisYear}</div>
            <div className="rm-l">в {currentYear}</div>
          </div>
          {bestPlace != null && (
            <div className="rm-r">
              <div className="rm-n acc">#{bestPlace}</div>
              <div className="rm-l">лучшее место</div>
            </div>
          )}
        </div>
      </div>

      {/* Mobile: compact dot-separated lines */}
      <div className="rh-strip rh-mobile">
        <div className="rh-inline">{leftItems.join(' · ')}</div>
        <div className="rh-inline dim">{rightItems.join(' · ')}</div>
      </div>
    </div>
  );
}

function pluralYears(n: number, short = false): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  const suffix = short ? '' : ' на сцене';
  if (mod100 >= 11 && mod100 <= 14) return 'лет' + suffix;
  if (mod10 === 1) return 'год' + suffix;
  if (mod10 >= 2 && mod10 <= 4) return 'года' + suffix;
  return 'лет' + suffix;
}
