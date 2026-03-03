import { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import type { DistanceResults as DistanceResultsType } from '../../types/races';
import DistStatsBlock from './DistStatsBlock';
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
  elevationGain?: number | null;
}

type TabId = 'results' | 'clubs';

const FINISHED_STATUSES = ['finished', 'over_time_limit'];

export default function DistanceResults({ data, raceId, elevationGain }: DistanceResultsProps) {
  const [activeTab, setActiveTab] = useState<TabId>('results');
  const [filterQuery, setFilterQuery] = useState('');
  const [genderFilter, setGenderFilter] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [selectedForCompare, setSelectedForCompare] = useState<Set<number>>(new Set());
  const [showCompare, setShowCompare] = useState(false);

  const { stats } = data;
  const hasGender = stats.gender_distribution?.length > 0;
  const hasCategory = stats.category_distribution?.length > 0;
  const hasClubs = (stats.club_stats?.length ?? 0) > 0;

  const finisherCount = stats.finishers;
  const clubCount = stats.club_stats?.length ?? 0;

  // Unique genders from results
  const genders = useMemo(() => {
    const set = new Set<string>();
    for (const r of data.results) {
      if (r.gender) set.add(r.gender);
    }
    return [...set].sort();
  }, [data.results]);

  // Unique categories from results
  const categories = useMemo(() => {
    const set = new Set<string>();
    for (const r of data.results) {
      if (r.category) set.add(r.category);
    }
    return [...set].sort();
  }, [data.results]);

  // Filtered results for "Участники" tab only
  const filteredResults = useMemo(() => {
    let res = data.results;
    if (genderFilter) {
      res = res.filter((r) => r.gender === genderFilter);
    }
    if (categoryFilter) {
      res = res.filter((r) => r.category === categoryFilter);
    }
    return res;
  }, [data.results, genderFilter, categoryFilter]);

  const isFiltered = !!(genderFilter || categoryFilter);
  const filteredFinisherCount = isFiltered
    ? filteredResults.filter((r) => FINISHED_STATUSES.includes(r.status)).length
    : finisherCount;

  const hasFilters = genders.length > 1 || categories.length > 0;

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

  // Reset filters & compare when distance changes
  useEffect(() => {
    setSelectedForCompare(new Set());
    setShowCompare(false);
    setGenderFilter(null);
    setCategoryFilter(null);
    setFilterQuery('');
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
      <DistStatsBlock
        distanceName={data.distance_name}
        distanceKm={data.distance_km}
        elevationGain={elevationGain ?? null}
        stats={stats}
      />

      <TimeHistogram buckets={stats.time_buckets} isBackyard={raceId === 'backyard_ultra_kz'} />

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
            Участники<span className="nav-dot">·</span>
            <span className="nav-count">{activeTab === 'results' ? filteredFinisherCount : finisherCount}</span>
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

        <div className="toolbar-controls">
          {hasFilters && activeTab === 'results' && (
            <>
              {genders.length > 1 && (
                <div className="gender-chips">
                  <button
                    className={`filter-btn${genderFilter === null ? ' active' : ''}`}
                    onClick={() => setGenderFilter(null)}
                  >
                    Все
                  </button>
                  {genders.map((g) => (
                    <button
                      key={g}
                      className={`filter-btn${genderFilter === g ? ' active' : ''}`}
                      onClick={() => setGenderFilter(genderFilter === g ? null : g)}
                    >
                      {g === 'M' ? 'М' : g === 'F' ? 'Ж' : g}
                    </button>
                  ))}
                </div>
              )}

              {categories.length > 0 && (
                <CategoryDropdown
                  categories={categories}
                  selected={categoryFilter}
                  onChange={setCategoryFilter}
                />
              )}
            </>
          )}

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
      </div>

      {activeTab === 'results' && (
        <ResultsTable
          results={filteredResults}
          externalFilter={filterQuery}
          totalFinishers={finisherCount}
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

/* ── Category dropdown ── */

function CategoryDropdown({
  categories,
  selected,
  onChange,
}: {
  categories: string[];
  selected: string | null;
  onChange: (value: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('click', handler, true);
    return () => document.removeEventListener('click', handler, true);
  }, [open]);

  return (
    <div className="cat-dd" ref={ref}>
      <button
        className={`cat-btn${open ? ' open' : ''}${selected ? ' has-value' : ''}`}
        onClick={() => setOpen((v) => !v)}
      >
        <span>Кат: {selected || 'Все'}</span>
        <span className="cat-chevron">&#9662;</span>
      </button>
      {open && (
        <div className="cat-menu">
          <button
            className={`cat-opt${selected === null ? ' on' : ''}`}
            onClick={() => { onChange(null); setOpen(false); }}
          >
            Все
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              className={`cat-opt${selected === cat ? ' on' : ''}`}
              onClick={() => { onChange(cat); setOpen(false); }}
            >
              {cat}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
