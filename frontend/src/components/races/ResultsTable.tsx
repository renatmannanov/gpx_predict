import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import type { RaceResult } from '../../types/races';
import './DataTable.css';
import './ResultsTable.css';

const INITIAL_LIMIT = 50;
const FINISHED_STATUSES = ['finished', 'over_time_limit'];

interface ResultsTableProps {
  results: RaceResult[];
  externalFilter?: string;
}

function isDnfDns(r: RaceResult): boolean {
  return !FINISHED_STATUSES.includes(r.status);
}

function getStatusLabel(status: string): string {
  switch (status) {
    case 'dnf': return 'DNF';
    case 'dns': return 'DNS';
    case 'dsq': return 'DSQ';
    default: return status.toUpperCase();
  }
}

export default function ResultsTable({ results, externalFilter }: ResultsTableProps) {
  const [expanded, setExpanded] = useState(false);

  const queryLower = (externalFilter || '').toLowerCase().trim();

  // Split finishers and DNF/DNS
  const { finishers, dnfDns } = useMemo(() => {
    const fin: RaceResult[] = [];
    const dd: RaceResult[] = [];
    for (const r of results) {
      if (isDnfDns(r)) dd.push(r);
      else fin.push(r);
    }
    return { finishers: fin, dnfDns: dd };
  }, [results]);

  const filteredFinishers = useMemo(() => {
    if (!queryLower) return finishers;
    return finishers.filter(
      (r) =>
        r.name.toLowerCase().includes(queryLower) ||
        (r.club && r.club.toLowerCase().includes(queryLower))
    );
  }, [finishers, queryLower]);

  const filteredDnf = useMemo(() => {
    if (!queryLower) return dnfDns;
    return dnfDns.filter(
      (r) =>
        r.name.toLowerCase().includes(queryLower) ||
        (r.club && r.club.toLowerCase().includes(queryLower))
    );
  }, [dnfDns, queryLower]);

  const visibleFinishers = expanded
    ? filteredFinishers
    : filteredFinishers.slice(0, INITIAL_LIMIT);
  const hasMore = filteredFinishers.length > INITIAL_LIMIT;
  const totalFiltered = filteredFinishers.length + filteredDnf.length;

  return (
    <div className="data-table-wrap">
      <table className="data-table results-table">
        <thead>
          <tr>
            <th className="dt-col-rank">#</th>
            <th>Имя</th>
            <th className="rt-col-time">Время</th>
            <th className="rt-col-cat">Кат.</th>
            <th className="rt-col-gender">Пол</th>
            <th className="rt-col-club">Клуб</th>
          </tr>
        </thead>
        <tbody>
          {visibleFinishers.map((r, i) => (
            <tr key={i}>
              <td className={`dt-col-rank ${getMedalClass(r.place)}`}>
                {r.place}
              </td>
              <td className="dt-col-name">
                <div className="dt-col-name-inner">
                  <span className="avatar">{getInitials(r.name)}</span>
                  {r.runner_id ? (
                    <Link to={`/runners/${r.runner_id}`} className="rt-name-link">
                      {highlightMatch(r.name, queryLower)}
                    </Link>
                  ) : (
                    <span>{highlightMatch(r.name, queryLower)}</span>
                  )}
                </div>
              </td>
              <td className="dt-col-num">{r.time_formatted}</td>
              <td className="dt-col-dim">{r.category || '—'}</td>
              <td className="dt-col-dim">{r.gender || '—'}</td>
              <td className="dt-col-dim">
                {r.club ? highlightMatch(r.club, queryLower) : '—'}
              </td>
            </tr>
          ))}

          {/* DNF/DNS section */}
          {filteredDnf.length > 0 && (expanded || !hasMore) && (
            <>
              <tr className="dnf-separator-row">
                <td colSpan={6} className="dnf-separator">
                  DNF / DNS ({filteredDnf.length})
                </td>
              </tr>
              {filteredDnf.map((r, i) => (
                <tr key={`dnf-${i}`} className="row-dnf">
                  <td className="dt-col-rank">—</td>
                  <td className="dt-col-name">
                    <span className="avatar">{getInitials(r.name)}</span>
                    {r.runner_id ? (
                      <Link to={`/runners/${r.runner_id}`} className="rt-name-link">
                        {highlightMatch(r.name, queryLower)}
                      </Link>
                    ) : (
                      <span>{highlightMatch(r.name, queryLower)}</span>
                    )}
                  </td>
                  <td className="dt-col-num rt-col-status">{getStatusLabel(r.status)}</td>
                  <td className="dt-col-dim">{r.category || '—'}</td>
                  <td className="dt-col-dim">{r.gender || '—'}</td>
                  <td className="dt-col-dim">
                    {r.club ? highlightMatch(r.club, queryLower) : '—'}
                  </td>
                </tr>
              ))}
            </>
          )}
        </tbody>
      </table>

      {queryLower && totalFiltered === 0 && (
        <div className="data-table-empty">
          Не найдено
        </div>
      )}

      {hasMore && !expanded && (
        <button
          className="btn btn-ghost results-show-all"
          onClick={() => setExpanded(true)}
        >
          Показать всех ({filteredFinishers.length}{filteredDnf.length > 0 ? ` + ${filteredDnf.length} DNF` : ''})
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
