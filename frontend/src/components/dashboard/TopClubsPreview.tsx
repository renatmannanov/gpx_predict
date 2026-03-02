import type { SeasonTopClub } from '../../types/races';
import './TopClubsPreview.css';

interface TopClubsPreviewProps {
  clubs: SeasonTopClub[];
  year: number;
}

export default function TopClubsPreview({ clubs, year }: TopClubsPreviewProps) {
  if (clubs.length === 0) return null;

  return (
    <>
      <div className="sec-head">
        <div className="sec-title">Клубы {year}</div>
      </div>
      <div className="clubs-list">
        {clubs.map((club, i) => (
          <div key={club.club} className="club-row card">
            <span className="club-rank">#{i + 1}</span>
            <span className="club-name">{club.club}</span>
            <span className="club-count">
              {club.runners_count} {pluralize(club.runners_count, 'бегун', 'бегуна', 'бегунов')}
            </span>
          </div>
        ))}
      </div>
    </>
  );
}

function pluralize(n: number, one: string, few: string, many: string): string {
  const abs = Math.abs(n) % 100;
  const last = abs % 10;
  if (abs > 10 && abs < 20) return many;
  if (last > 1 && last < 5) return few;
  if (last === 1) return one;
  return many;
}
