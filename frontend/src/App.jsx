import { useState } from 'react'
import './index.css'
import PushToTalk from './components/PushToTalk'
import TacticalOverlay from './components/TacticalOverlay'
import MatchNotes from './components/MatchNotes'
import EventFeed from './components/EventFeed'

const BACKEND = import.meta.env.VITE_BACKEND_URL || ''

export default function App() {
    const [homeTeam, setHomeTeam] = useState('Manchester City')
    const [awayTeam, setAwayTeam] = useState('Arsenal')
    const [sport, setSport] = useState('soccer')
    const [matchReady, setMatchReady] = useState(false)
    const [buildingNotes, setBuildingNotes] = useState(false)
    const [notes, setNotes] = useState([])
    const [buildStatus, setBuildStatus] = useState(null) // null | 'loading' | 'ready' | 'error'

    const buildMatchNotes = async () => {
        setBuildingNotes(true)
        setBuildStatus('loading')
        setNotes([])
        try {
            const res = await fetch(`${BACKEND}/api/research`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ home_team: homeTeam, away_team: awayTeam, sport }),
            })
            const data = await res.json()

            // Parse the brief text into note cards
            const parsed = parseBrief(data.brief)
            setNotes(parsed)
            setMatchReady(true)
            setBuildStatus('ready')
        } catch (err) {
            console.error('Research failed', err)
            setBuildStatus('error')
        } finally {
            setBuildingNotes(false)
        }
    }

    // Parse raw brief text into structured note cards
    const parseBrief = (text) => {
        if (!text) return []
        const lines = text.split('\n').filter(l => l.trim().length > 20)
        const categories = ['form', 'stats', 'h2h', 'tactics', 'stats', 'form']
        return lines.slice(0, 10).map((line, i) => ({
            text: line.replace(/^#+\s*/, '').trim(),
            category: categories[i % categories.length],
        }))
    }

    return (
        <div className="app-wrapper">
            {/* Header */}
            <header className="header">
                <div className="header-brand">
                    <div className="header-logo">🏟️ PitchSide AI</div>
                    <div className="header-badge">Live Agents 🗣️</div>
                </div>
                <div className="header-match">
                    {matchReady
                        ? <><strong>{homeTeam}</strong> vs <strong>{awayTeam}</strong> — {sport}</>
                        : 'Configure a match to begin'}
                </div>
                <div className="header-live">
                    <div className="live-dot" />
                    Live
                </div>
            </header>

            {/* Match Setup Banner */}
            <div className="setup-banner">
                <input
                    type="text"
                    placeholder="Home Team"
                    value={homeTeam}
                    onChange={e => setHomeTeam(e.target.value)}
                    style={{ width: 180 }}
                    id="home-team-input"
                />
                <span style={{ color: 'var(--text-muted)', fontWeight: 700 }}>vs</span>
                <input
                    type="text"
                    placeholder="Away Team"
                    value={awayTeam}
                    onChange={e => setAwayTeam(e.target.value)}
                    style={{ width: 180 }}
                    id="away-team-input"
                />
                <select value={sport} onChange={e => setSport(e.target.value)} id="sport-select">
                    <option value="soccer">⚽ Soccer</option>
                    <option value="cricket">🏏 Cricket</option>
                </select>

                <button
                    className="btn btn-primary"
                    onClick={buildMatchNotes}
                    disabled={buildingNotes || !homeTeam || !awayTeam}
                    id="build-notes-btn"
                >
                    {buildingNotes
                        ? <><span className="spinner" /> Researching...</>
                        : '🔬 Build Match Notes'
                    }
                </button>

                {buildStatus && (
                    <span className={`status-pill ${buildStatus}`}>
                        {buildStatus === 'loading' && '⏳ Building brief...'}
                        {buildStatus === 'ready' && '✅ Research complete'}
                        {buildStatus === 'error' && '⚠️ Research failed'}
                    </span>
                )}
            </div>

            {/* Main Dashboard */}
            <div className="dashboard">

                {/* Left — main area */}
                <div className="dashboard-main">
                    {/* Push-to-Talk */}
                    <PushToTalk
                        matchReady={matchReady}
                        homeTeam={homeTeam}
                        awayTeam={awayTeam}
                        sport={sport}
                    />

                    {/* Tactical Overlay */}
                    <TacticalOverlay sport={sport} />
                </div>

                {/* Right — sidebar */}
                <div className="dashboard-sidebar">
                    {/* Match Notes (top half) */}
                    <MatchNotes notes={notes} loading={buildingNotes} />

                    {/* Event Feed (bottom half) */}
                    <EventFeed />
                </div>
            </div>
        </div>
    )
}
