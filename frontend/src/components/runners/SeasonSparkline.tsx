import { useRef, useEffect, useCallback, useState, useMemo } from 'react';
import type { RunnerRaceResult, SeasonSummary } from '../../types/races';
import './SeasonSparkline.css';

interface SeasonSparklineProps {
  results: RunnerRaceResult[];
  seasons: SeasonSummary[];
}

interface RacePoint {
  race: RunnerRaceResult;
  /** position on 0..1 time axis */
  t: number;
}

interface Dot {
  x: number;
  y: number;
  point: RacePoint;
}

const FINISHED = new Set(['finished', 'over_time_limit']);

export default function SeasonSparkline({ results, seasons }: SeasonSparklineProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [dots, setDots] = useState<Dot[]>([]);
  const [tipDot, setTipDot] = useState<Dot | null>(null);

  // Filter to finished results, sort chronologically
  const points = useMemo(() => {
    const finished = results
      .filter(r => FINISHED.has(r.status))
      .sort((a, b) => {
        // sort by date if available, then by year
        const da = a.race_date || `${a.year}-06-01`;
        const db = b.race_date || `${b.year}-06-01`;
        return da.localeCompare(db);
      });

    if (finished.length === 0) return [];

    // Map to 0..1 time axis
    const firstDate = parseDate(finished[0]);
    const lastDate = parseDate(finished[finished.length - 1]);
    const span = lastDate - firstDate || 1;

    return finished.map(r => ({
      race: r,
      t: (parseDate(r) - firstDate) / span,
    }));
  }, [results]);

  // Progress badge from seasons
  const progressLabel = getProgressLabel(seasons);

  // Year tick positions for X axis
  const yearTicks = useMemo(() => {
    if (points.length < 2) return [];
    const first = parseDate(points[0].race);
    const last = parseDate(points[points.length - 1].race);
    const span = last - first || 1;

    const years = new Set(points.map(p => p.race.year));
    return [...years].sort().map(y => ({
      year: y,
      t: (new Date(y, 0, 1).getTime() - first) / span,
    })).filter(yt => yt.t >= -0.02 && yt.t <= 1.02);
  }, [points]);

  const render = useCallback(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap || points.length < 1) return;

    const dpr = window.devicePixelRatio || 1;
    const W = wrap.getBoundingClientRect().width;
    const H = 80;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    canvas.style.width = W + 'px';
    canvas.style.height = H + 'px';

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.scale(dpr, dpr);

    const P = { t: 8, r: 16, b: 6, l: 16 };
    const cW = W - P.l - P.r;
    const cH = H - P.t - P.b;

    // Performance = 100 - percentile (higher = better)
    const perfs = points.map(p => 100 - p.race.percentile);
    const minP = Math.min(...perfs);
    const maxP = Math.max(...perfs);
    const range = maxP - minP || 1;
    const pad = range * 0.2;
    const lo = minP - pad;
    const hi = maxP + pad;

    const toX = (t: number) => P.l + t * cW;
    const toY = (perf: number) => P.t + cH - ((perf - lo) / (hi - lo)) * cH;

    // Grid lines
    ctx.strokeStyle = 'rgba(255,255,255,0.04)';
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 5]);
    for (let i = 1; i <= 3; i++) {
      const gy = P.t + (cH * i) / 4;
      ctx.beginPath();
      ctx.moveTo(P.l, gy);
      ctx.lineTo(P.l + cW, gy);
      ctx.stroke();
    }
    ctx.setLineDash([]);

    // Area fill
    const grad = ctx.createLinearGradient(0, P.t, 0, P.t + cH);
    grad.addColorStop(0, 'rgba(232,98,42,0.18)');
    grad.addColorStop(1, 'rgba(232,98,42,0)');
    ctx.beginPath();
    points.forEach((p, i) => {
      const x = toX(p.t);
      const y = toY(perfs[i]);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.lineTo(toX(points[points.length - 1].t), P.t + cH);
    ctx.lineTo(toX(points[0].t), P.t + cH);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // Line
    ctx.beginPath();
    ctx.strokeStyle = 'rgba(232,98,42,0.85)';
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    points.forEach((p, i) => {
      const x = toX(p.t);
      const y = toY(perfs[i]);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Dots
    const bestPerf = Math.max(...perfs);
    const newDots: Dot[] = [];
    points.forEach((p, i) => {
      const x = toX(p.t);
      const y = toY(perfs[i]);

      // Halo on best result
      if (perfs[i] === bestPerf) {
        ctx.beginPath();
        ctx.arc(x, y, 7, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(232,98,42,0.15)';
        ctx.fill();
      }

      ctx.beginPath();
      ctx.arc(x, y, 3.5, 0, Math.PI * 2);
      ctx.fillStyle = '#E8622A';
      ctx.fill();

      ctx.beginPath();
      ctx.arc(x, y, 1.5, 0, Math.PI * 2);
      ctx.fillStyle = '#fff';
      ctx.fill();

      newDots.push({ x, y, point: p });
    });

    setDots(newDots);
  }, [points]);

  useEffect(() => {
    render();
    window.addEventListener('resize', render);
    return () => window.removeEventListener('resize', render);
  }, [render]);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    let found: Dot | null = null;
    let bestDist = 20;
    for (const d of dots) {
      const dist = Math.sqrt((mx - d.x) ** 2 + (my - d.y) ** 2);
      if (dist < bestDist) {
        bestDist = dist;
        found = d;
      }
    }
    setTipDot(found);
  }, [dots]);

  const handleMouseLeave = useCallback(() => setTipDot(null), []);

  if (points.length < 1) return null;

  return (
    <div className="section">
      <div className="sh">
        <div className="sh-title">Прогресс</div>
        {progressLabel && (
          <div className={`sh-badge ${progressLabel.up ? 'sh-badge-up' : 'sh-badge-dn'}`}>
            {progressLabel.text}
          </div>
        )}
      </div>
      <div className="spark-card">
        <div className="spark-wrap" ref={wrapRef}>
          <canvas
            ref={canvasRef}
            style={{ width: '100%', height: 80 }}
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
          />
          {tipDot && (
            <div
              className="spark-tip"
              style={{
                left: Math.min(tipDot.x + 12, (wrapRef.current?.clientWidth || 300) - 220),
                top: tipDot.y < 50 ? tipDot.y + 16 : tipDot.y - 52,
              }}
            >
              <b>
                {tipDot.point.race.race_name} · top-{Math.round(tipDot.point.race.percentile)}%
              </b>
              <br />
              <span>
                {tipDot.point.race.time_formatted} · #{tipDot.point.race.place} из {tipDot.point.race.total_finishers}
              </span>
            </div>
          )}
        </div>
        <div className="spark-years">
          {yearTicks.map(yt => {
            const pct = Math.max(0, Math.min(100, yt.t * 100));
            return (
              <span
                key={yt.year}
                className="spark-year"
                style={{ left: `${pct}%` }}
              >
                {yt.year}
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function parseDate(r: RunnerRaceResult): number {
  if (r.race_date) return new Date(r.race_date).getTime();
  return new Date(r.year, 5, 1).getTime(); // fallback: June 1
}

function getProgressLabel(seasons: SeasonSummary[]): { text: string; up: boolean } | null {
  if (seasons.length < 2) return null;
  const first = seasons[0];
  const last = seasons[seasons.length - 1];
  const diff = Math.round(first.median_percentile - last.median_percentile);
  const years = last.year - first.year;
  if (diff === 0 || years === 0) return null;
  if (diff > 0) {
    return { text: `↑ +${diff}% за ${years} лет`, up: true };
  }
  return { text: `↓ ${diff}% за ${years} лет`, up: false };
}
