import { useMemo, useRef, useState, useCallback, useEffect } from 'react';
import { Link } from 'react-router-dom';
import type { Race } from '../../types/races';
import './SeasonStatsBox.css';

interface SeasonStatsBoxProps {
  races: Race[];
  selectedYear: number;
  availableYears: number[];
  onYearChange: (year: number) => void;
}

export default function SeasonStatsBox({ races, selectedYear, availableYears, onYearChange }: SeasonStatsBoxProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const updateScrollState = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 4);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  }, []);

  useEffect(() => {
    updateScrollState();
  }, [availableYears, updateScrollState]);

  const scrollBy = useCallback((dir: 'left' | 'right') => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollBy({ left: dir === 'left' ? -160 : 160, behavior: 'smooth' });
  }, []);

  const stats = useMemo(() => {
    const racesThisYear = races.filter(r =>
      r.editions.some(e => e.year === selectedYear)
    );
    const distancesThisYear = racesThisYear.reduce(
      (sum, r) => sum + r.distances.length, 0
    );
    const editionsWithResults = racesThisYear.filter(r =>
      r.editions.some(e => e.year === selectedYear && e.has_results)
    ).length;

    return {
      totalRaces: racesThisYear.length,
      totalDistances: distancesThisYear,
      racesWithResults: editionsWithResults,
    };
  }, [races, selectedYear]);

  return (
    <div className="season-box">
      <div className="season-box-head">
        <div className="sbox-title">Сезон {selectedYear}</div>
        <div className="sbox-year">Алматы</div>
      </div>

      {availableYears.length > 1 && (
        <div className="season-years-wrap">
          {canScrollLeft && (
            <button className="syear-arrow" onClick={() => scrollBy('left')} aria-label="Scroll left">
              &larr;
            </button>
          )}
          <div className="season-years" ref={scrollRef} onScroll={updateScrollState}>
            {availableYears.map(year => (
              <button
                key={year}
                className={`season-year-btn${year === selectedYear ? ' active' : ''}`}
                onClick={() => onYearChange(year)}
              >
                {year}
              </button>
            ))}
          </div>
          {canScrollRight && (
            <button className="syear-arrow" onClick={() => scrollBy('right')} aria-label="Scroll right">
              &rarr;
            </button>
          )}
        </div>
      )}

      <div className="season-nums">
        <div className="snum">
          <div className="snum-val accent">{stats.totalRaces}</div>
          <div className="snum-label">гонок</div>
        </div>
        <div className="snum">
          <div className="snum-val">{stats.totalDistances}</div>
          <div className="snum-label">дистанций</div>
        </div>
        <div className="snum">
          <div className="snum-val">{stats.racesWithResults}</div>
          <div className="snum-label">с результатами</div>
        </div>
      </div>
      <div className="season-box-footer">
        <Link to="/races" className="sec-link">
          Смотреть все гонки &rarr;
        </Link>
      </div>
    </div>
  );
}
