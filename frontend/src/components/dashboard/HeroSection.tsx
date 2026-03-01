import { Link } from 'react-router-dom';
import type { Race } from '../../types/races';
import SeasonStatsBox from './SeasonStatsBox';
import './HeroSection.css';

interface HeroSectionProps {
  races: Race[];
  selectedYear: number;
  availableYears: number[];
  onYearChange: (year: number) => void;
}

export default function HeroSection({ races, selectedYear, availableYears, onYearChange }: HeroSectionProps) {
  return (
    <div className="hero">
      <div className="hero-top">
        <div>
          <div className="hero-label">Беговой портал Алматы</div>
          <h1>
            Сквозная аналитика
            <br />
            беговых
            {' '}
            <em>гонок Алматы</em>
          </h1>
          <p className="hero-sub">
            Результаты всех беговых гонок Алматы в одном месте.
            Плюс GPX маршруты и предсказание твоего финишного времени.
          </p>
          <div className="hero-btns">
            <Link to="/races" className="btn btn-fill">Все гонки</Link>
            <Link to="/predict" className="btn btn-ghost">Предсказать моё время &rarr;</Link>
          </div>
        </div>

        <SeasonStatsBox
          races={races}
          selectedYear={selectedYear}
          availableYears={availableYears}
          onYearChange={onYearChange}
        />
      </div>
    </div>
  );
}
