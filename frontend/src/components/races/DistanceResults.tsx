import type { DistanceResults as DistanceResultsType } from '../../types/races';
import StatsCard from './StatsCard';
import ResultsTable from './ResultsTable';
import './DistanceResults.css';

interface DistanceResultsProps {
  data: DistanceResultsType;
}

export default function DistanceResults({ data }: DistanceResultsProps) {
  const subtitle = [
    data.distance_km && `${data.distance_km} км`,
  ].filter(Boolean).join(' · ');

  return (
    <section className="distance-section">
      <h2 className="distance-title">
        {data.distance_name}
        {subtitle && <span className="distance-subtitle"> · {subtitle}</span>}
      </h2>

      <StatsCard stats={data.stats} />

      {/* TimeHistogram will be added here in a future iteration */}

      <ResultsTable results={data.results} />
    </section>
  );
}
