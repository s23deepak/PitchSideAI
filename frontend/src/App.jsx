import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import './index.css'
import HomeScreen from './components/HomeScreen'
import LandingPage from './pages/LandingPage'
import VideoPage from './pages/VideoPage'
import TabbedLivePage from './pages/TabbedLivePage'

function LegacyDashboardEntry() {
    const navigate = useNavigate()

    const handleStartMatch = (home, away) => {
        const params = new URLSearchParams({
            tab: 'fan-lens',
            home,
            away,
            sport: 'soccer',
        })
        navigate(`/live?${params.toString()}`, { replace: true })
    }

    return <HomeScreen onStartMatch={handleStartMatch} />
}

export default function App() {
    return (
        <BrowserRouter>
            <Routes>
                <Route path="/" element={<LandingPage />} />
                <Route path="/watch" element={<VideoPage />} />
                <Route path="/dashboard" element={<LegacyDashboardEntry />} />
                <Route path="/live" element={<TabbedLivePage />} />
                <Route path="/fan-lens" element={<Navigate to="/live?tab=fan-lens" replace />} />
                <Route path="/commentator" element={<Navigate to="/live?tab=commentator" replace />} />
                <Route path="/notes" element={<Navigate to="/live?tab=notes" replace />} />
            </Routes>
        </BrowserRouter>
    )
}
