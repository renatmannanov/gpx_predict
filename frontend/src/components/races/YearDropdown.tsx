import { useState, useRef, useEffect, useCallback } from 'react';
import './YearDropdown.css';

interface YearDropdownProps {
  years: number[];
  selected: number;
  onChange: (year: number) => void;
}

export default function YearDropdown({ years, selected, onChange }: YearDropdownProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const sorted = [...years].sort((a, b) => b - a);
  const latestYear = sorted[0];

  const toggle = useCallback(() => setOpen((v) => !v), []);

  // Close on click outside
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
    <div className="year-dd" ref={ref}>
      <button className={`year-btn${open ? ' open' : ''}`} onClick={toggle}>
        <span>{selected}</span>
        <span className="year-chevron">▾</span>
      </button>
      <div className={`year-menu${open ? ' open' : ''}`}>
        {sorted.map((year) => (
          <button
            key={year}
            className={`year-opt${year === selected ? ' on' : ''}`}
            onClick={() => {
              onChange(year);
              setOpen(false);
            }}
          >
            {year}
            {year === latestYear && <span className="year-opt-tag">сейчас</span>}
          </button>
        ))}
      </div>
    </div>
  );
}
