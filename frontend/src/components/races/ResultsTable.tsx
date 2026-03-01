import { useState, useMemo } from 'react';
import type { RaceResult } from '../../types/races';
import './ResultsTable.css';

const INITIAL_LIMIT = 50;

interface ResultsTableProps {
  results: RaceResult[];
}

export default function ResultsTable({ results }: ResultsTableProps) {
  const [expanded, setExpanded] = useState(false);
  const [filterQuery, setFilterQuery] = useState('');

  const queryLower = filterQuery.toLowerCase().trim();

  const filtered = useMemo(() => {
    if (!queryLower) return results;
    return results.filter(
      (r) =>
        r.name.toLowerCase().includes(queryLower) ||
        (r.club && r.club.toLowerCase().includes(queryLower))
    );
  }, [results, queryLower]);

  const visible = expanded ? filtered : filtered.slice(0, INITIAL_LIMIT);
  const hasMore = filtered.length > INITIAL_LIMIT;

  return (
    <div className="results-table-wrap">
      <div className="table-filter-wrap">
        <svg
          className="table-filter-icon"
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
          className="table-filter-input"
          placeholder="Фильтр по имени или клубу..."
          value={filterQuery}
          onChange={(e) => {
            setFilterQuery(e.target.value);
            setExpanded(false);
          }}
        />
        {filterQuery && (
          <button
            className="table-filter-clear"
            onClick={() => setFilterQuery('')}
            title="Очистить"
          >
            &times;
          </button>
        )}
      </div>

      <table className="results-table">
        <thead>
          <tr>
            <th className="col-place">#</th>
            <th className="col-name">Имя</th>
            <th className="col-time">Время</th>
            <th className="col-cat">Кат.</th>
            <th className="col-gender">Пол</th>
            <th className="col-club">Клуб</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((r, i) => (
            <tr key={i} className="result-row">
              <td className={`col-place ${getMedalClass(r.place)}`}>
                {r.place}
              </td>
              <td className="col-name">
                <span className="avatar">{getInitials(r.name)}</span>
                <span>{highlightMatch(r.name, queryLower)}</span>
              </td>
              <td className="col-time">{r.time_formatted}</td>
              <td className="col-cat">{r.category || '—'}</td>
              <td className="col-gender">{r.gender || '—'}</td>
              <td className="col-club">
                {r.club ? highlightMatch(r.club, queryLower) : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {queryLower && filtered.length === 0 && (
        <div className="table-filter-empty">
          Не найдено
        </div>
      )}

      {hasMore && !expanded && (
        <button
          className="btn btn-ghost results-show-all"
          onClick={() => setExpanded(true)}
        >
          Показать всех ({filtered.length})
        </button>
      )}
    </div>
  );
}

function getMedalClass(place: number): string {
  if (place === 1) return 'medal-gold';
  if (place === 2) return 'medal-silver';
  if (place === 3) return 'medal-bronze';
  return '';
}

function getInitials(name: string): string {
  const parts = name.split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0][0].toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function highlightMatch(text: string, query: string): React.ReactNode {
  if (!query) return text;
  const idx = text.toLowerCase().indexOf(query);
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="filter-highlight">{text.slice(idx, idx + query.length)}</mark>
      {text.slice(idx + query.length)}
    </>
  );
}
