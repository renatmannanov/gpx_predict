import { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchRace, fetchResults } from '../api/races';
import { getRaceCategory, getRaceCategoryLabel } from '../types/races';
import YearDropdown from '../components/races/YearDropdown';
import DistancePills from '../components/races/DistancePills';
import DistanceResults from '../components/races/DistanceResults';
import './RaceDetailPage.css';

export default function RaceDetailPage() {
  const { raceId } = useParams<{ raceId: string }>();
  const [searchParams] = useSearchParams();
  const distanceFromUrl = searchParams.get('distance');

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

  // Sort distances: longest first
  const sortedResults = useMemo(() => {
    if (!results) return null;
    return [...results].sort((a, b) => (b.distance_km ?? 0) - (a.distance_km ?? 0));
  }, [results]);

  // Auto-select distance: prefer URL param, then first
  useEffect(() => {
    if (sortedResults && sortedResults.length > 0) {
      if (distanceFromUrl) {
        const match = sortedResults.find((r) => r.distance_name === distanceFromUrl);
        if (match) {
          setSelectedDistance(match.distance_name);
          return;
        }
      }
      setSelectedDistance(sortedResults[0].distance_name);
    } else {
      setSelectedDistance(null);
    }
  }, [sortedResults, distanceFromUrl]);

  const handleYearChange = useCallback((year: number) => {
    if (year === selectedYear) return;
    setSelectedYear(year);
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

  const activeResult = sortedResults?.find((r) => r.distance_name === selectedDistance);
  const activeDistMeta = race?.distances.find((d) => d.name === selectedDistance);

  return (
    <div className="page">
      <Link to="/races" className="back-link">&larr; Все гонки</Link>

      {/* Title row: name + year dropdown + badge */}
      <div className="race-title-row">
        <h1 className="race-title">{race.name}</h1>
        {years.length > 0 && selectedYear !== null && (
          <YearDropdown
            years={years}
            selected={selectedYear}
            onChange={handleYearChange}
          />
        )}
        <span className={badgeClass}>{badgeText}</span>
      </div>

      {/* Distance pills */}
      {sortedResults && sortedResults.length > 1 && (
        <DistancePills
          distances={sortedResults}
          selected={selectedDistance}
          onSelect={setSelectedDistance}
        />
      )}

      {/* Results for selected distance */}
      {resultsLoading && (
        <div className="loading-text">Загрузка результатов...</div>
      )}

      {activeResult && (
        <DistanceResults
          data={activeResult}
          raceId={raceId}
          elevationGain={activeDistMeta?.elevation_gain_m}
        />
      )}

      {sortedResults && sortedResults.length === 0 && (
        <div className="loading-text">Нет результатов за {selectedYear} год</div>
      )}
    </div>
  );
}
