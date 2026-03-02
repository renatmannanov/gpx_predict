import { useState, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchRaces } from '../api/races';
import HeroSection from '../components/dashboard/HeroSection';
import RacesPreview from '../components/dashboard/RacesPreview';
// import PredictCTA from '../components/dashboard/PredictCTA';

export default function DashboardPage() {
  useEffect(() => {
    document.title = 'ayda.run — беговой портал Алматы';
  }, []);

  const { data: races, isLoading } = useQuery({
    queryKey: ['races'],
    queryFn: fetchRaces,
  });

  const availableYears = useMemo(() => {
    if (!races) return [];
    const years = new Set(races.flatMap(r => r.editions.map(e => e.year)));
    return [...years].sort((a, b) => b - a);
  }, [races]);

  const [selectedYear, setSelectedYear] = useState<number | null>(null);

  // Set default year when data loads
  useEffect(() => {
    if (availableYears.length > 0 && selectedYear === null) {
      setSelectedYear(availableYears[0]);
    }
  }, [availableYears, selectedYear]);

  if (isLoading) {
    return <div className="loading-text">Загрузка...</div>;
  }

  return (
    <div>
      <HeroSection
        races={races || []}
        selectedYear={selectedYear ?? new Date().getFullYear()}
        availableYears={availableYears}
        onYearChange={setSelectedYear}
      />
      <RacesPreview
        races={races || []}
        selectedYear={selectedYear ?? new Date().getFullYear()}
      />
      {/* <PredictCTA /> */}
    </div>
  );
}
