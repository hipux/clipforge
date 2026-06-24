import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import SessionResume from './components/SessionResume'
import DownloadPage from './pages/DownloadPage'
import MomentsPage from './pages/MomentsPage'
import EffectsPage from './pages/EffectsPage'
import ProcessPage from './pages/ProcessPage'
import PublishPage from './pages/PublishPage'

function App() {
  return (
    <BrowserRouter>
      <SessionResume />
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/download" replace />} />
          <Route path="download" element={<DownloadPage />} />
          <Route path="moments" element={<MomentsPage />} />
          <Route path="effects" element={<EffectsPage />} />
          <Route path="process" element={<ProcessPage />} />
          <Route path="publish" element={<PublishPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App