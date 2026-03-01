interface YearTabsProps {
  years: number[];
  selected: number;
  onChange: (year: number) => void;
}

export default function YearTabs({ years, selected, onChange }: YearTabsProps) {
  const sorted = [...years].sort((a, b) => b - a);

  return (
    <div className="filter-bar">
      {sorted.map((year) => (
        <button
          key={year}
          className={`filter-btn${year === selected ? ' active' : ''}`}
          onClick={() => onChange(year)}
        >
          {year}
        </button>
      ))}
    </div>
  );
}
