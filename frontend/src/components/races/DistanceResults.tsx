import { useState, useCallback, useMemo, useEffect } from 'react';
import type { DistanceResults as DistanceResultsType } from '../../types/races';
import StatsCard from './StatsCard';
import TimeHistogram from './TimeHistogram';
import GenderChart from './GenderChart';
import CategoryBars from './CategoryBars';
import ClubRanking from './ClubRanking';
import ResultsTable from './ResultsTable';
import ComparePanel from './ComparePanel';
import './DistanceResults.css';

interface DistanceResultsProps {
  data: DistanceResultsType;
  raceId?: string;
}

type TabId = 'results' | 'clubs';

export default function DistanceResults({ data, raceId }: DistanceResultsProps) {
  const [activeTab, setActiveTab] = useState<TabId>('results');
  const [filterQuery, setFilterQuery] = useState('');
  const [selectedForCompare, setSelectedForCompare] = useState<Set<number>>(new Set());
  const [showCompare, setShowCompare] = useState(false);

  const subtitle = [
    data.distance_km != null && data.distance_km > 0 && `${data.distance_km} км`,
  ].filter(Boolean).join(' · ');

  const { stats } = data;
  const hasGender = stats.gender_distribution?.length > 0;
  const hasCategory = stats.category_distribution?.length > 0;
  const hasClubs = (stats.club_stats?.length ?? 0) > 0;

  const finisherCount = stats.finishers;
  const clubCount = stats.club_stats?.length ?? 0;

  const handleToggleCompare = useCallback((runnerId: number) => {
    setSelectedForCompare((prev) => {
      const next = new Set(prev);
      if (next.has(runnerId)) {
        next.delete(runnerId);
      } else {
        next.add(runnerId);
      }
      return next;
    });
  }, []);

  const handleRemoveFromCompare = useCallback((runnerId: number) => {
    setSelectedForCompare((prev) => {
      const next = new Set(prev);
      next.delete(runnerId);
      if (next.size < 2) setShowCompare(false);
      return next;
    });
  }, []);

  const handleClearCompare = useCallback(() => {
    setSelectedForCompare(new Set());
    setShowCompare(false);
  }, []);

  // Reset compare when distance changes
  useEffect(() => {
    setSelectedForCompare(new Set());
    setShowCompare(false);
  }, [data.distance_name]);

  // Build name map for selected runners
  const selectedNames = useMemo(() => {
    const map = new Map<number, string>();
    for (const r of data.results) {
      if (r.runner_id && selectedForCompare.has(r.runner_id)) {
        map.set(r.runner_id, r.name);
      }
    }
    return map;
  }, [data.results, selectedForCompare]);

  return (
    <section className="distance-section">
      <h2 className="distance-title">
        {data.distance_name}
        {subtitle && <span className="distance-subtitle"> · {subtitle}</span>}
      </h2>

      <StatsCard stats={stats} />

      <TimeHistogram buckets={stats.time_buckets} />

      {(hasGender || hasCategory) && (
        <div className="insights-grid">
          {hasGender && <GenderChart distribution={stats.gender_distribution} />}
          {hasCategory && <CategoryBars distribution={stats.category_distribution} />}
        </div>
      )}

      <div className="distance-toolbar">
        <nav className="distance-nav">
          <button
            className={`distance-nav-item ${activeTab === 'results' ? 'active' : ''}`}
            onClick={() => setActiveTab('results')}
          >
            Участники<span className="nav-dot">·</span><span className="nav-count">{finisherCount}</span>
          </button>
          {hasClubs && (
            <button
              className={`distance-nav-item ${activeTab === 'clubs' ? 'active' : ''}`}
              onClick={() => setActiveTab('clubs')}
            >
              Клубы<span className="nav-dot">·</span><span className="nav-count">{clubCount}</span>
            </button>
          )}
        </nav>

        <div className="toolbar-filter-wrap">
          <svg
            className="toolbar-filter-icon"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            className="toolbar-filter-input"
            placeholder="Поиск по имени и клубу"
            value={filterQuery}
            onChange={(e) => setFilterQuery(e.target.value)}
          />
          {filterQuery && (
            <button
              className="toolbar-filter-clear"
              onClick={() => setFilterQuery('')}
              title="Очистить"
            >
              &times;
            </button>
          )}
        </div>
      </div>

      {activeTab === 'results' && (
        <ResultsTable
          results={data.results}
          externalFilter={filterQuery}
          selectedForCompare={selectedForCompare}
          onToggleCompare={handleToggleCompare}
        />
      )}
      {activeTab === 'clubs' && hasClubs && (
        <ClubRanking
          clubs={stats.club_stats}
          results={data.results}
          totalFinishers={finisherCount}
          filterQuery={filterQuery}
        />
      )}

      {/* Compare sticky bar */}
      {selectedForCompare.size >= 2 && !showCompare && (
        <div className="compare-bar">
          <span className="compare-bar-text">
            Выбрано <span className="compare-bar-count">{selectedForCompare.size}</span> участника
          </span>
          <button
            className="btn btn-fill"
            onClick={() => setShowCompare(true)}
          >
            Сравнить
          </button>
          <button
            className="btn btn-ghost compare-bar-reset"
            onClick={handleClearCompare}
          >
            Сбросить
          </button>
        </div>
      )}

      {/* Compare panel */}
      {showCompare && raceId && (
        <ComparePanel
          raceId={raceId}
          distanceName={data.distance_name}
          selectedRunnerIds={[...selectedForCompare]}
          selectedNames={selectedNames}
          onClose={() => setShowCompare(false)}
          onRemove={handleRemoveFromCompare}
        />
      )}
    </section>
  );
}
