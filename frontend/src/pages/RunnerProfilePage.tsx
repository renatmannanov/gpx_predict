import { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchRunnerProfile } from '../api/races';
import type { RunnerRaceResult } from '../types/races';
import RunnerSummary from '../components/runners/RunnerSummary';
import SeasonSparkline from '../components/runners/SeasonSparkline';
import RunnerResultCard from '../components/runners/RunnerResultCard';
import './RunnerProfilePage.css';

export interface RaceDistOption {
  key: string;
  label: string;
}

export default function RunnerProfilePage() {
  const { runnerId } = useParams<{ runnerId: string }>();
  const navigate = useNavigate();
  const id = Number(runnerId);
  const [raceDistFilter, setRaceDistFilter] = useState<string | null>(null);

  // Scroll to top + reset filter on navigation
  useEffect(() => {
    window.scrollTo(0, 0);
    setRaceDistFilter(null);
  }, [id]);

  const { data, isLoading, error } = useQuery({
    queryKey: ['runner', id],
    queryFn: () => fetchRunnerProfile(id),
    enabled: !isNaN(id) && id > 0,
  });

  useEffect(() => {
    if (data) {
      document.title = `${data.profile.name} — ayda.run`;
    }
    return () => {
      document.title = 'ayda.run — беговой портал Алматы';
    };
  }, [data]);

  // Derive category from freshest result instead of profile
  const latestCategory = useMemo(() => {
    if (!data || data.results.length === 0) return data?.profile.category ?? null;
    const sorted = [...data.results].sort((a, b) => b.year - a.year);
    return sorted[0].category;
  }, [data]);

  // Unique race+distance options for filter dropdown
  const raceDistOptions = useMemo((): RaceDistOption[] => {
    if (!data) return [];
    const seen = new Map<string, { raceName: string; distanceName: string }>();
    for (const r of data.results) {
      const key = `${r.race_id}|${r.distance_name}`;
      if (!seen.has(key)) {
        seen.set(key, { raceName: r.race_name, distanceName: r.distance_name });
      }
    }
    return [...seen.entries()].map(([key, { raceName, distanceName }]) => ({
      key,
      label: `${raceName} · ${distanceName}`,
    }));
  }, [data]);

  // Filtered results by race+distance
  const filteredResults = useMemo(() => {
    if (!data || !raceDistFilter) return data?.results ?? [];
    return data.results.filter((r) => `${r.race_id}|${r.distance_name}` === raceDistFilter);
  }, [data, raceDistFilter]);

  // Group results by year (DESC) and build previous-result map
  const { yearGroups, previousMap } = useMemo(() => {
    if (!data) return { yearGroups: [] as [number, RunnerRaceResult[]][], previousMap: new Map() };

    const source = filteredResults;

    const byYear = new Map<number, RunnerRaceResult[]>();
    for (const r of source) {
      const arr = byYear.get(r.year) || [];
      arr.push(r);
      byYear.set(r.year, arr);
    }
    const groups = [...byYear.entries()].sort((a, b) => b[0] - a[0]);

    // Build previous result map: key = "race_id|distance_name|year" → result from previous year
    const prevMap = new Map<string, RunnerRaceResult>();
    const byRaceDist = new Map<string, RunnerRaceResult[]>();
    for (const r of source) {
      const key = `${r.race_id}|${r.distance_name}`;
      const arr = byRaceDist.get(key) || [];
      arr.push(r);
      byRaceDist.set(key, arr);
    }
    for (const [, results] of byRaceDist) {
      const sorted = [...results].sort((a, b) => a.year - b.year);
      for (let i = 1; i < sorted.length; i++) {
        const mapKey = `${sorted[i].race_id}|${sorted[i].distance_name}|${sorted[i].year}`;
        prevMap.set(mapKey, sorted[i - 1]);
      }
    }

    return { yearGroups: groups, previousMap: prevMap };
  }, [data, filteredResults]);

  if (isLoading) {
    return (
      <div className="page">
        <div className="loading-text">Загрузка...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="page">
        <button onClick={() => navigate(-1)} className="back-link">&larr; Назад</button>
        <div className="error-text">Бегун не найден</div>
      </div>
    );
  }

  // Override profile category with the freshest one
  const profileWithLatestCategory = { ...data.profile, category: latestCategory };

  // Compute extra stats for header
  const currentYear = new Date().getFullYear();
  const finishedResults = data.results.filter((r) => r.status === 'finished' || r.status === 'over_time_limit');
  const racesThisYear = finishedResults.filter((r) => r.year === currentYear).length;
  const bestPlace = finishedResults.length > 0 ? Math.min(...finishedResults.map((r) => r.place)) : null;

  return (
    <div className="page runner-page">
      <button onClick={() => navigate(-1)} className="back-link">&larr; Назад</button>

      <RunnerSummary
        profile={profileWithLatestCategory}
        totalRaces={data.total_races}
        medianPercentile={data.median_percentile}
        yearsActive={data.years_active}
        racesThisYear={racesThisYear}
        currentYear={currentYear}
        bestPlace={bestPlace}
      />

      {data.results.length >= 2 && (
        <SeasonSparkline
          results={filteredResults}
          seasons={data.seasons}
          raceDistFilter={raceDistFilter}
          raceDistOptions={raceDistOptions}
          onRaceDistFilterChange={setRaceDistFilter}
        />
      )}

      <div className="runner-results">
        {yearGroups.map(([year, results]) => (
          <div key={year} className="runner-year-group">
            <div className="runner-year-label">{year}</div>
            <div className="runner-year-cards">
              {results.map((r, i) => {
                const prevKey = `${r.race_id}|${r.distance_name}|${r.year}`;
                return (
                  <RunnerResultCard
                    key={i}
                    result={r}
                    previousResult={previousMap.get(prevKey)}
                  />
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
