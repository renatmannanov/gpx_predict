import { useState, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchRaces } from '../api/races';
import RaceFilters from '../components/races/RaceFilters';
import RaceCard from '../components/races/RaceCard';
import './RacesPage.css';

type FilterValue = 'all' | 'athletex' | 'am';

export default function RacesPage() {
  const { data: races, isLoading, error } = useQuery({
    queryKey: ['races'],
    queryFn: fetchRaces,
  });

  const [filter, setFilter] = useState<FilterValue>('all');

  useEffect(() => {
    document.title = 'Гонки — ayda.run';
  }, []);

  const counts = useMemo(() => {
    if (!races) return { all: 0, athletex: 0, am: 0 };
    return {
      all: races.length,
      athletex: races.filter((r) => r.source === 'athletex').length,
      am: races.filter((r) => r.source === 'am').length,
    };
  }, [races]);

  const sortedAndFiltered = useMemo(() => {
    if (!races) return [];

    const filtered = filter === 'all'
      ? races
      : races.filter((r) => r.source === filter);

    return [...filtered].sort((a, b) => {
      const latestA = getLatestEditionDate(a.editions);
      const latestB = getLatestEditionDate(b.editions);
      return latestB.localeCompare(latestA);
    });
  }, [races, filter]);

  if (isLoading) {
    return (
      <div className="page">
        <div className="loading-text">Загрузка...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page">
        <div className="error-text">
          Не удалось загрузить гонки. Попробуйте обновить страницу.
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-eyebrow">
        <a href="https://athletex.kz/" target="_blank" rel="noopener noreferrer">Athletex</a>
        {' · '}
        <a href="https://almaty-marathon.kz/ru/" target="_blank" rel="noopener noreferrer" className="eyebrow-road">Алматы Марафон</a>
      </div>
      <h1>Гонки</h1>
      <p className="page-sub">
        Беговые гонки Алматы — результаты, статистика, аналитика
      </p>

      <div className="races-toolbar">
        <RaceFilters selected={filter} counts={counts} onChange={setFilter} />
      </div>

      <div className="races-grid">
        {sortedAndFiltered.map((race) => (
          <RaceCard key={race.id} race={race} />
        ))}
      </div>

      {sortedAndFiltered.length === 0 && (
        <div className="loading-text">Нет гонок в этой категории</div>
      )}
    </div>
  );
}

function getLatestEditionDate(editions: { year: number; date: string | null }[]): string {
  if (editions.length === 0) return '0000';
  const sorted = [...editions].sort((a, b) => b.year - a.year);
  return sorted[0].date || String(sorted[0].year);
}
