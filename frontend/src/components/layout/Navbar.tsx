import { Link, useLocation } from 'react-router-dom';
import './Navbar.css';

const navLinks = [
  { to: '/races', label: 'Гонки' },
  { to: '/predict', label: 'Предсказать время' },
];

export default function Navbar() {
  const location = useLocation();

  return (
    <nav className="navbar">
      <Link to="/" className="logo">
        ayda<em>.run</em>
      </Link>

      <div className="nav-links">
        {navLinks.map((link) => (
          <Link
            key={link.to}
            to={link.to}
            className={location.pathname.startsWith(link.to) ? 'on' : ''}
          >
            {link.label}
          </Link>
        ))}
      </div>

      <div className="nav-right">
        <button className="btn-nav" disabled>
          Войти
        </button>
      </div>
    </nav>
  );
}
