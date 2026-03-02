import { useRef, useEffect, useCallback } from 'react';
import type { DistanceResults } from '../../types/races';
import './DistancePills.css';

interface DistancePillsProps {
  distances: DistanceResults[];
  selected: string | null;
  onSelect: (name: string) => void;
}

export default function DistancePills({ distances, selected, onSelect }: DistancePillsProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const checkScroll = useCallback(() => {
    const el = scrollRef.current;
    const wrap = wrapRef.current;
    if (!el || !wrap) return;
    const atStart = el.scrollLeft <= 4;
    const atEnd = el.scrollLeft >= el.scrollWidth - el.clientWidth - 4;
    wrap.classList.toggle('can-scroll-left', !atStart);
    wrap.classList.toggle('can-scroll-right', !atEnd);
  }, []);

  const scrollBy = useCallback((dir: number) => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollBy({ left: dir * 180, behavior: 'smooth' });
    setTimeout(checkScroll, 300);
  }, [checkScroll]);

  useEffect(() => {
    checkScroll();
    window.addEventListener('resize', checkScroll);
    return () => window.removeEventListener('resize', checkScroll);
  }, [checkScroll, distances]);

  return (
    <div className="dist-wrap" ref={wrapRef}>
      <button className="dist-arrow left" onClick={() => scrollBy(-1)}>‹</button>
      <button className="dist-arrow right" onClick={() => scrollBy(1)}>›</button>
      <div className="dist-scroll" ref={scrollRef} onScroll={checkScroll}>
        <div className="dist-pills">
          {distances.map((d) => {
            const label = d.distance_km != null && d.distance_km > 0
              ? `${d.distance_name} · ${d.distance_km}км`
              : d.distance_name;
            return (
              <button
                key={d.distance_name}
                className={`dp${d.distance_name === selected ? ' on' : ''}`}
                onClick={() => onSelect(d.distance_name)}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
