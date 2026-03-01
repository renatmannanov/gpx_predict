import { useState } from 'react';
import type { RaceResult } from '../../types/races';
import './ResultsTable.css';

const INITIAL_LIMIT = 50;

interface ResultsTableProps {
  results: RaceResult[];
}

export default function ResultsTable({ results }: ResultsTableProps) {
  const [expanded, setExpanded] = useState(false);

  const visible = expanded ? results : results.slice(0, INITIAL_LIMIT);
  const hasMore = results.length > INITIAL_LIMIT;

  return (
    <div className="results-table-wrap">
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
                <span>{r.name}</span>
              </td>
              <td className="col-time">{r.time_formatted}</td>
              <td className="col-cat">{r.category || '—'}</td>
              <td className="col-gender">{r.gender || '—'}</td>
              <td className="col-club">{r.club || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {hasMore && !expanded && (
        <button
          className="btn btn-ghost results-show-all"
          onClick={() => setExpanded(true)}
        >
          Показать всех ({results.length})
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
