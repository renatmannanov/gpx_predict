import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useQueries } from '@tanstack/react-query';
import { searchParticipant } from '../../api/races';
import type { SearchResult } from '../../types/races';
import './ComparePanel.css';

interface ComparePanelProps {
  raceId: string;
  distanceName: string;
  selectedRunnerIds: number[];
  selectedNames: Map<number, string>;
  onClose: () => void;
  onRemove: (runnerId: number) => void;
}

interface RunnerColumn {
  runnerId: number;
  name: string;
  results: SearchResult[];
  isLoading: boolean;
}

function formatTimeDiff(diffS: number): string {
  const abs = Math.abs(diffS);
  const h = Math.floor(abs / 3600);
  const m = Math.floor((abs % 3600) / 60);
  const s = abs % 60;
  const sign = diffS < 0 ? '-' : '+';
  return `${sign}${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export default function ComparePanel({
  raceId,
  distanceName,
  selectedRunnerIds,
  selectedNames,
  onClose,
  onRemove,
}: ComparePanelProps) {
  // Parallel queries for each selected runner
  const queries = useQueries({
    queries: selectedRunnerIds.map((runnerId) => {
      const name = selectedNames.get(runnerId) || '';
      return {
        queryKey: ['compare', raceId, name],
        queryFn: () => searchParticipant(raceId, name),
        enabled: !!name,
        staleTime: 5 * 60 * 1000,
      };
    }),
  });

  // Build columns
  const columns: RunnerColumn[] = useMemo(() => {
    return selectedRunnerIds.map((runnerId, i) => {
      const q = queries[i];
      const allResults = q.data ?? [];
      // Filter to only the matching distance and runner
      const name = selectedNames.get(runnerId) || '';
      const results = allResults.filter(
        (sr) => sr.result && sr.result.name === name
      );
      return {
        runnerId,
        name,
        results,
        isLoading: q.isLoading,
      };
    });
  }, [selectedRunnerIds, selectedNames, queries]);

  // Collect all years across all runners, sorted DESC
  const allYears = useMemo(() => {
    const yearSet = new Set<number>();
    for (const col of columns) {
      for (const sr of col.results) {
        yearSet.add(sr.year);
      }
    }
    return [...yearSet].sort((a, b) => b - a);
  }, [columns]);

  // Compute summary for each column
  const summaries = useMemo(() => {
    return columns.map((col) => {
      const finishedResults = col.results.filter(
        (sr) => sr.result && sr.result.time_s > 0
      );
      if (finishedResults.length === 0) {
        return { bestTime: null, bestYear: null, progress: null, club: null };
      }
      // Best time
      let bestSr = finishedResults[0];
      for (const sr of finishedResults) {
        if (sr.result!.time_s < bestSr.result!.time_s) bestSr = sr;
      }

      // Progress: first year vs last year (sorted by year ASC)
      const sorted = [...finishedResults].sort((a, b) => a.year - b.year);
      let progress: number | null = null;
      if (sorted.length >= 2) {
        progress = sorted[sorted.length - 1].result!.time_s - sorted[0].result!.time_s;
      }

      const latestClub = finishedResults
        .sort((a, b) => b.year - a.year)[0]?.result?.club ?? null;

      return {
        bestTime: bestSr.result!.time_formatted,
        bestYear: bestSr.year,
        progress,
        club: latestClub,
      };
    });
  }, [columns]);

  const isLoading = queries.some((q) => q.isLoading);

  return (
    <div className="compare-overlay" onClick={onClose}>
      <div className="compare-panel" onClick={(e) => e.stopPropagation()}>
        <div className="compare-header">
          <h3 className="compare-title">Сравнение — {distanceName}</h3>
          <button className="compare-close" onClick={onClose} title="Закрыть">
            &times;
          </button>
        </div>

        {isLoading ? (
          <div className="compare-loading">Загрузка...</div>
        ) : (
          <div className="compare-scroll">
            <table className="compare-table">
              <thead>
                <tr>
                  <th className="compare-label-col" />
                  {columns.map((col) => (
                    <th key={col.runnerId} className="compare-runner-col">
                      <div className="compare-runner-header">
                        <Link
                          to={`/runners/${col.runnerId}`}
                          className="compare-runner-name"
                        >
                          {col.name}
                        </Link>
                        <button
                          className="compare-remove"
                          onClick={() => onRemove(col.runnerId)}
                          title="Убрать"
                        >
                          &times;
                        </button>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {/* Year rows */}
                {allYears.map((year) => (
                  <tr key={year}>
                    <td className="compare-label">{year}</td>
                    {columns.map((col) => {
                      const sr = col.results.find((r) => r.year === year);
                      if (!sr || !sr.result) {
                        return (
                          <td key={col.runnerId} className="compare-cell compare-empty">
                            —
                          </td>
                        );
                      }
                      const r = sr.result;
                      const isDnf = r.status !== 'finished' && r.status !== 'over_time_limit';
                      return (
                        <td key={col.runnerId} className={`compare-cell${isDnf ? ' compare-dnf' : ''}`}>
                          {isDnf ? (
                            <span className="compare-status">{r.status.toUpperCase()}</span>
                          ) : (
                            <>
                              <span className="compare-time">{r.time_formatted}</span>
                              <span className="compare-place">#{r.place}</span>
                            </>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}

                {/* Summary rows */}
                {allYears.length > 0 && (
                  <>
                    <tr className="compare-summary-separator">
                      <td colSpan={columns.length + 1} />
                    </tr>
                    <tr className="compare-summary-row">
                      <td className="compare-label">Лучшее</td>
                      {summaries.map((s, i) => (
                        <td key={columns[i].runnerId} className="compare-cell">
                          {s.bestTime ? (
                            <>
                              <span className="compare-time">{s.bestTime}</span>
                              <span className="compare-place">({s.bestYear})</span>
                            </>
                          ) : '—'}
                        </td>
                      ))}
                    </tr>
                    <tr className="compare-summary-row">
                      <td className="compare-label">Прогресс</td>
                      {summaries.map((s, i) => (
                        <td key={columns[i].runnerId} className="compare-cell">
                          {s.progress != null ? (
                            <span className={s.progress < 0 ? 'compare-improved' : 'compare-degraded'}>
                              {s.progress < 0 ? '▲' : '▼'} {formatTimeDiff(s.progress)}
                            </span>
                          ) : (
                            <span className="compare-dim">—</span>
                          )}
                        </td>
                      ))}
                    </tr>
                    <tr className="compare-summary-row">
                      <td className="compare-label">Клуб</td>
                      {summaries.map((s, i) => (
                        <td key={columns[i].runnerId} className="compare-cell compare-dim">
                          {s.club || '—'}
                        </td>
                      ))}
                    </tr>
                  </>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
