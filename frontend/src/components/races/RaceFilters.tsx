type FilterValue = 'all' | 'athletex' | 'am';

interface RaceFiltersProps {
  selected: FilterValue;
  counts: { all: number; athletex: number; am: number };
  onChange: (filter: FilterValue) => void;
}

const filters: { value: FilterValue; label: string }[] = [
  { value: 'all', label: 'Все' },
  { value: 'athletex', label: 'Athletex' },
  { value: 'am', label: 'Алматы Марафон' },
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
