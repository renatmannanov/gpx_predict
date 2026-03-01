import { useState, useMemo } from 'react';
import type { ClubStatsData, RaceResult } from '../../types/races';
import './DataTable.css';
import './ClubRanking.css';

const FINISHED_STATUSES = ['finished', 'over_time_limit'];

interface ClubRankingProps {
  clubs: ClubStatsData[];
  results: RaceResult[];
  totalFinishers: number;
  filterQuery: string;
}

export default function ClubRanking({ clubs, results, totalFinishers, filterQuery }: ClubRankingProps) {
  const [expandedClub, setExpandedClub] = useState<string | null>(null);

  const queryLower = filterQuery.toLowerCase().trim();

  // Group finished results by club, sorted by place
  const resultsByClub = useMemo(() => {
    const map: Record<string, RaceResult[]> = {};
    for (const r of results) {
      if (r.club && FINISHED_STATUSES.includes(r.status)) {
        if (!map[r.club]) map[r.club] = [];
        map[r.club].push(r);
      }
    }
    for (const key of Object.keys(map)) {
      map[key].sort((a, b) => a.place - b.place);
    }
    return map;
  }, [results]);

  // Filter clubs by query
  const filteredClubs = useMemo(() => {
    if (!queryLower) return clubs;
    return clubs.filter((c) => c.club.toLowerCase().includes(queryLower));
  }, [clubs, queryLower]);

  if (!filteredClubs.length && queryLower) {
    return <div className="data-table-empty">Не найдено</div>;
  }

  if (!filteredClubs.length) return null;

  const toggleClub = (club: string) => {
    setExpandedClub((prev) => (prev === club ? null : club));
  };

  return (
    <div className="data-table-wrap">
      <table className="data-table club-table">
        <thead>
          <tr>
            <th className="dt-col-rank">#</th>
            <th>Клуб</th>
            <th className="ct-col-count">Бегунов</th>
            <th className="ct-col-best">Лучший</th>
            <th className="ct-col-pct">Ср. перс.</th>
          </tr>
        </thead>
        <tbody>
          {filteredClubs.map((c, i) => {
            const isExpanded = expandedClub === c.club;
            const members = resultsByClub[c.club] || [];

            return (
              <ClubRow
                key={c.club}
                club={c}
                rank={i + 1}
                isTop={i < 3}
                isExpanded={isExpanded}
                members={members}
                totalFinishers={totalFinishers}
                onToggle={() => toggleClub(c.club)}
              />
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

interface ClubRowProps {
  club: ClubStatsData;
  rank: number;
  isTop: boolean;
  isExpanded: boolean;
  members: RaceResult[];
  totalFinishers: number;
  onToggle: () => void;
}

function ClubRow({ club, rank, isTop, isExpanded, members, totalFinishers, onToggle }: ClubRowProps) {
  return (
    <>
      <tr
        className={`club-row ${isTop ? 'club-top' : ''} ${isExpanded ? 'club-expanded' : ''}`}
        onClick={onToggle}
        title="Нажмите чтобы раскрыть"
      >
        <td className={`dt-col-rank ${isTop ? 'rank-accent' : ''}`}>{rank}</td>
        <td className="dt-col-name">
          <div className="dt-col-name-inner">
            <span className={`club-expand-icon ${isExpanded ? 'expanded' : ''}`}>›</span>
            {club.club}
          </div>
        </td>
        <td className="dt-col-num">{club.count}</td>
        <td className="dt-col-num">{club.best_time}</td>
        <td className={`dt-col-num ${getPercentileClass(club.avg_percentile)}`}>
          top-{Math.round(club.avg_percentile)}%
        </td>
      </tr>
      {isExpanded && members.length > 0 && (
        members.map((r, j) => {
          const pct = totalFinishers > 1
            ? Math.round(((r.place - 1) / (totalFinishers - 1)) * 100)
            : 0;
          return (
            <tr key={`${club.club}-${j}`} className="club-member-row">
              <td className="dt-col-rank"></td>
              <td className="club-member-name">{r.name}</td>
              <td className="dt-col-num club-member-dim">#{r.place}</td>
              <td className="dt-col-num club-member-dim">{r.time_formatted}</td>
              <td className={`dt-col-num ${getPercentileClass(pct)}`}>
                top-{pct}%
              </td>
            </tr>
          );
        })
      )}
    </>
  );
}

function getPercentileClass(pct: number): string {
  if (pct < 25) return 'pct-green';
  if (pct < 50) return 'pct-yellow';
  return 'pct-dim';
}
