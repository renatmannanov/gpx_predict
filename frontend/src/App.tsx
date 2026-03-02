import { BrowserRouter, Routes, Route } from 'react-router-dom'
import PageLayout from './components/layout/PageLayout'
import ErrorBoundary from './components/ErrorBoundary'
import DashboardPage from './pages/DashboardPage'
// import PredictPage from './pages/PredictPage'
import RacesPage from './pages/RacesPage'
import RaceDetailPage from './pages/RaceDetailPage'
import RunnerProfilePage from './pages/RunnerProfilePage'
import NotFoundPage from './pages/NotFoundPage'

function App() {
  return (
    <BrowserRouter>
      <PageLayout>
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/races" element={<RacesPage />} />
            <Route path="/races/:raceId" element={<RaceDetailPage />} />
            <Route path="/runners/:runnerId" element={<RunnerProfilePage />} />
            {/* <Route path="/predict" element={<PredictPage />} /> */}
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </ErrorBoundary>
      </PageLayout>
    </BrowserRouter>
  )
}

export default App
