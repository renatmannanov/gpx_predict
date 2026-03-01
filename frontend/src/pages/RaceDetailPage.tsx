import { useState, useEffect, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchRace, fetchResults } from '../api/races';
import { getRaceCategory, getRaceCategoryLabel } from '../types/races';
import YearTabs from '../components/races/YearTabs';
import DistanceResults from '../components/races/DistanceResults';
import './RaceDetailPage.css';

export default function RaceDetailPage() {
  const { raceId } = useParams<{ raceId: string }>();

  const {
    data: race,
    isLoading: raceLoading,
    error: raceError,
  } = useQuery({
    queryKey: ['race', raceId],
    queryFn: () => fetchRace(raceId!),
    enabled: !!raceId,
  });

  const years = useMemo(() => {
    if (!race) return [];
    return race.editions
      .filter((e) => e.has_results)
      .map((e) => e.year)
      .sort((a, b) => b - a);
  }, [race]);

  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [selectedDistance, setSelectedDistance] = useState<string | null>(null);

  // Set default year when race loads
  useEffect(() => {
    if (years.length > 0 && selectedYear === null) {
      setSelectedYear(years[0]);
    }
  }, [years, selectedYear]);

  const {
    data: results,
    isLoading: resultsLoading,
  } = useQuery({
    queryKey: ['results', raceId, selectedYear],
    queryFn: () => fetchResults(raceId!, selectedYear!),
    enabled: !!raceId && selectedYear !== null,
  });

  // Set default distance when results load
  useEffect(() => {
    if (results && results.length > 0 && !selectedDistance) {
      setSelectedDistance(results[0].distance_name);
    }
  }, [results, selectedDistance]);

  // Reset selected distance when year changes
  useEffect(() => {
    setSelectedDistance(null);
  }, [selectedYear]);

  // Document title
  useEffect(() => {
    if (race) {
      document.title = `${race.name} — ayda.run`;
    }
    return () => {
      document.title = 'ayda.run — беговой портал Алматы';
    };
  }, [race]);

  if (raceLoading) {
    return (
      <div className="page">
        <div className="loading-text">Загрузка...</div>
      </div>
    );
  }

  if (raceError || !race) {
    return (
      <div className="page">
        <Link to="/races" className="back-link">&larr; Все гонки</Link>
        <div className="error-text">
          Гонка не найдена
        </div>
      </div>
    );
  }

  const category = getRaceCategory(race.type, race.id);
  const badgeClass = category === 'road' ? 'badge badge-road' : 'badge badge-trail';
  const badgeText = race.type
    ? race.type.replace(/_/g, ' ')
    : getRaceCategoryLabel(category);

  const activeResult = results?.find((r) => r.distance_name === selectedDistance);

  return (
    <div className="page">
      <Link to="/races" className="back-link">&larr; Все гонки</Link>

      <div className="race-header">
        <span className={badgeClass}>{badgeText}</span>
        <h1>{race.name}</h1>
        {race.location && (
          <p className="race-location">{race.location}</p>
        )}
      </div>

      {/* Year tabs */}
      {years.length > 0 && selectedYear !== null && (
        <div className="year-tabs-wrap">
          <YearTabs
            years={years}
            selected={selectedYear}
            onChange={setSelectedYear}
          />
        </div>
      )}

      {/* Distance tabs */}
      {results && results.length > 1 && (
        <div className="distance-tabs">
          {results.map((dr) => (
            <button
              key={dr.distance_name}
              className={`distance-tab${dr.distance_name === selectedDistance ? ' active' : ''}`}
              onClick={() => setSelectedDistance(dr.distance_name)}
            >
              <span className="distance-tab-name">{dr.distance_name}</span>
              {dr.distance_km != null && dr.distance_km > 0 && (
                <span className="distance-tab-info">{dr.distance_km} км</span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Results for selected distance */}
      {resultsLoading && (
        <div className="loading-text">Загрузка результатов...</div>
      )}

      {activeResult && (
        <DistanceResults data={activeResult} />
      )}

      {results && results.length === 0 && (
        <div className="loading-text">Нет результатов за {selectedYear} год</div>
      )}
    </div>
  );
}
