import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import PageLayout from './components/layout/PageLayout'
import ErrorBoundary from './components/ErrorBoundary'
import PredictPage from './pages/PredictPage'
import RacesPage from './pages/RacesPage'
import NotFoundPage from './pages/NotFoundPage'

function App() {
  return (
    <BrowserRouter>
      <PageLayout>
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<Navigate to="/races" replace />} />
            <Route path="/races" element={<RacesPage />} />
            <Route path="/predict" element={<PredictPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </ErrorBoundary>
      </PageLayout>
    </BrowserRouter>
  )
}

export default App
