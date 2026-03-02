import { Link } from 'react-router-dom';
import type { Race } from '../../types/races';
import { getRaceCategory, getRaceCategoryLabel } from '../../types/races';
import './RaceCard.css';

interface RaceCardProps {
  race: Race;
}

export default function RaceCard({ race }: RaceCardProps) {
  const category = getRaceCategory(race.type, race.id);
  const badgeClass = category === 'road' ? 'badge badge-road' : 'badge badge-trail';

  const editionCount = race.editions.length;
  const distanceCount = race.distances.length;

  // Badge text: from API type, or fallback to category label
  const badgeText = race.type
    ? race.type.replace(/_/g, ' ')
    : getRaceCategoryLabel(category);

  return (
    <Link to={`/races/${race.id}`} className="card race-card">
      <span className={badgeClass}>
        {badgeText}
      </span>
      <h3 className="race-card-name">{race.name}</h3>
      {race.location && (
        <span className="race-card-location">{race.location}</span>
      )}
      <div className="race-card-footer">
        <span>
          {race.total_finishers != null && race.total_finishers > 0 && (
            <>{race.total_finishers} {pluralize(race.total_finishers, 'финишёр', 'финишёра', 'финишёров')} · </>
          )}
          {distanceCount} {pluralize(distanceCount, 'дистанция', 'дистанции', 'дистанций')}
          {' · '}
          {editionCount} {pluralize(editionCount, 'год', 'года', 'лет')}
        </span>
        <span className="race-card-arrow">&rarr;</span>
      </div>
    </Link>
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
