import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useDebounce } from '../../hooks/useDebounce';
import { searchRunners } from '../../api/races';
import './GlobalSearch.css';

export default function GlobalSearch() {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const debouncedQuery = useDebounce(query, 300);
  const wrapRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const { data: results, isLoading } = useQuery({
    queryKey: ['runner-search', debouncedQuery],
    queryFn: () => searchRunners(debouncedQuery),
    enabled: debouncedQuery.length >= 2,
  });

  const showDropdown = isOpen && debouncedQuery.length >= 2;

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setIsOpen(false);
      inputRef.current?.blur();
    }
  }, []);

  function handleSelect(runnerId: number) {
    setIsOpen(false);
    setQuery('');
    navigate(`/runners/${runnerId}`);
  }

  return (
    <div className="global-search" ref={wrapRef}>
      <div className="global-search-input-wrap">
        <svg
          className="global-search-icon"
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
          ref={inputRef}
          type="text"
          className="global-search-input"
          placeholder="Найди себя..."
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
        />

        {showDropdown && (
          <div className="global-search-dropdown">
            {isLoading && (
              <div className="global-search-loading">Поиск...</div>
            )}

            {!isLoading && results && results.length === 0 && (
              <div className="global-search-empty">Никого не найдено</div>
            )}

            {!isLoading && results && results.length > 0 && (
              <div className="global-search-results">
                {results.map((r) => (
                  <button
                    key={r.id}
                    className="global-search-result"
                    onClick={() => handleSelect(r.id)}
                  >
                    <span className="avatar">{getInitials(r.name)}</span>
                    <div className="global-search-result-info">
                      <span className="global-search-result-name">{r.name}</span>
                      <span className="global-search-result-meta">
                        {[
                          r.club,
                          `${r.races_count} ${pluralRaces(r.races_count)}`,
                          r.last_race && r.last_year && `${r.last_race} ${r.last_year}`,
                        ].filter(Boolean).join(' · ')}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function getInitials(name: string): string {
  const parts = name.split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0][0].toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function pluralRaces(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 14) return 'гонок';
  if (mod10 === 1) return 'гонка';
  if (mod10 >= 2 && mod10 <= 4) return 'гонки';
  return 'гонок';
}
