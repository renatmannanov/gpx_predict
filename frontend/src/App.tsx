import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import PageLayout from './components/layout/PageLayout'
import PredictPage from './pages/PredictPage'

function App() {
  return (
    <BrowserRouter>
      <PageLayout>
        <Routes>
          <Route path="/" element={<Navigate to="/races" replace />} />
          <Route path="/predict" element={<PredictPage />} />
        </Routes>
      </PageLayout>
    </BrowserRouter>
  )
}

export default App
