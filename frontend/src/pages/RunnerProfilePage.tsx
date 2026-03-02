import { useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchRunnerProfile } from '../api/races';
import type { RunnerRaceResult } from '../types/races';
import RunnerSummary from '../components/runners/RunnerSummary';
import RunnerResultCard from '../components/runners/RunnerResultCard';
import './RunnerProfilePage.css';

export default function RunnerProfilePage() {
  const { runnerId } = useParams<{ runnerId: string }>();
  const navigate = useNavigate();
  const id = Number(runnerId);

  // Fix 1: scroll to top on navigation
  useEffect(() => {
    window.scrollTo(0, 0);
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

  // Group results by year (DESC) and build previous-result map
  const { yearGroups, previousMap } = useMemo(() => {
    if (!data) return { yearGroups: [] as [number, RunnerRaceResult[]][], previousMap: new Map() };

    const byYear = new Map<number, RunnerRaceResult[]>();
    for (const r of data.results) {
      const arr = byYear.get(r.year) || [];
      arr.push(r);
      byYear.set(r.year, arr);
    }
    const groups = [...byYear.entries()].sort((a, b) => b[0] - a[0]);

    // Build previous result map: key = "race_id|distance_name|year" → result from previous year
    const prevMap = new Map<string, RunnerRaceResult>();
    const byRaceDist = new Map<string, RunnerRaceResult[]>();
    for (const r of data.results) {
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
  }, [data]);

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

  return (
    <div className="page runner-page">
      <button onClick={() => navigate(-1)} className="back-link">&larr; Назад</button>

      <RunnerSummary
        profile={profileWithLatestCategory}
        totalRaces={data.total_races}
        medianPercentile={data.median_percentile}
        yearsActive={data.years_active}
      />

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
