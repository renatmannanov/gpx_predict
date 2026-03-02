import { Link } from 'react-router-dom';
import './PredictCTA.css';

export default function PredictCTA() {
  return (
    <div className="predict-cta">
      <div>
        <div className="pc-tag">GPX Predict</div>
        <div className="pc-title">За какое время ты пробежишь этот маршрут?</div>
        <p className="pc-sub">
          Подключи Strava — предскажем твоё финишное время
          на любом трейле Алматы на основе твоих реальных данных.
        </p>
      </div>
      <Link to="/predict" className="btn btn-fill pc-btn">
        Предсказать моё время
      </Link>
    </div>
  );
}
