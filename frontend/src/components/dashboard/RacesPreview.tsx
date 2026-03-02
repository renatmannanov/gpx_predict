import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import type { Race } from '../../types/races';
import { fetchSeasonStats } from '../../api/races';
import RaceCard from '../races/RaceCard';
import TopClubsPreview from './TopClubsPreview';
import './RacesPreview.css';

interface RacesPreviewProps {
  races: Race[];
  selectedYear: number;
}

export default function RacesPreview({ races, selectedYear }: RacesPreviewProps) {
  const { data: seasonStats } = useQuery({
    queryKey: ['seasonStats', selectedYear],
    queryFn: () => fetchSeasonStats(selectedYear),
    staleTime: 5 * 60 * 1000,
  });

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

  // const hasClubs = (seasonStats?.top_clubs?.length ?? 0) > 0;

  return (
    <div className="section races-preview">
      <div className="rp-layout">
        <div className="rp-main">
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

        {/* TODO: clubs sidebar — temporarily hidden
        {hasClubs && (
          <div className="rp-clubs">
            <TopClubsPreview clubs={seasonStats!.top_clubs} year={selectedYear} />
          </div>
        )}
        */}
      </div>
    </div>
  );
}

function getEditionDate(race: Race, year: number): Date {
  const edition = race.editions.find(e => e.year === year);
  if (edition?.date) return new Date(edition.date);
  return new Date(0);
}
