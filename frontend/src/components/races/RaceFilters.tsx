type FilterValue = 'all' | 'trail' | 'road';

interface RaceFiltersProps {
  selected: FilterValue;
  counts: { all: number; trail: number; road: number };
  onChange: (filter: FilterValue) => void;
}

const filters: { value: FilterValue; label: string }[] = [
  { value: 'all', label: 'Все' },
  { value: 'trail', label: 'Трейл' },
  { value: 'road', label: 'Шоссе' },
];

export default function RaceFilters({ selected, counts, onChange }: RaceFiltersProps) {
  return (
    <div className="filter-bar">
      {filters.map((f) => (
        <button
          key={f.value}
          className={`filter-btn${selected === f.value ? ' active' : ''}`}
          onClick={() => onChange(f.value)}
        >
          {f.label} {counts[f.value]}
        </button>
      ))}
    </div>
  );
}
