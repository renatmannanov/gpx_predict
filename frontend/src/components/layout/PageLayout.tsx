import Navbar from './Navbar';
import Footer from './Footer';

interface PageLayoutProps {
  children: React.ReactNode;
}

export default function PageLayout({ children }: PageLayoutProps) {
  return (
    <div className="site-layout">
      <Navbar />
      <main className="site-main">{children}</main>
      <Footer />
    </div>
  );
}
