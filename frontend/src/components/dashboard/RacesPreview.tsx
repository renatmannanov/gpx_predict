import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import type { Race } from '../../types/races';
import RaceCard from '../races/RaceCard';
import './RacesPreview.css';

interface RacesPreviewProps {
  races: Race[];
  selectedYear: number;
}

export default function RacesPreview({ races, selectedYear }: RacesPreviewProps) {
  const topRaces = useMemo(() => {
    const racesThisYear = races.filter(r =>
      r.editions.some(e => e.year === selectedYear)
    );

    return racesThisYear
      .sort((a, b) => {
        const dateA = getEditionDate(a, selectedYear);
        const dateB = getEditionDate(b, selectedYear);
        return dateB.getTime() - dateA.getTime();
      })
      .slice(0, 6);
  }, [races, selectedYear]);

  return (
    <div className="section races-preview">
      <div className="sec-head">
        <div className="sec-title">Гонки {selectedYear}</div>
        <Link to="/races" className="sec-link">Все гонки &rarr;</Link>
      </div>
      <div className="races-preview-grid">
        {topRaces.map(race => (
          <RaceCard key={race.id} race={race} />
        ))}
      </div>
    </div>
  );
}

function getEditionDate(race: Race, year: number): Date {
  const edition = race.editions.find(e => e.year === year);
  if (edition?.date) return new Date(edition.date);
  return new Date(0);
}
