import { useEffect } from 'react';
import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  useEffect(() => {
    document.title = 'Страница не найдена — ayda.run';
  }, []);

  return (
    <div className="page" style={{ textAlign: 'center' }}>
      <h1>404</h1>
      <p className="page-sub">Страница не найдена</p>
      <Link to="/" className="btn btn-ghost">
        &larr; На главную
      </Link>
    </div>
  );
}
