import { useState } from 'react'
import './index.css'
import PushToTalk from './components/PushToTalk'
import TacticalOverlay from './components/TacticalOverlay'
import MatchNotes from './components/MatchNotes'
import EventFeed from './components/EventFeed'
import CommentaryNotesViewer from './components/CommentaryNotesViewer'

const BACKEND = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

export default function App() {
    const [homeTeam, setHomeTeam] = useState('Manchester United')
    const [awayTeam, setAwayTeam] = useState('Liverpool')
    const [sport, setSport] = useState('soccer')
    const [matchDateTime, setMatchDateTime] = useState(new Date().toISOString().slice(0, 16))
    const [venue, setVenue] = useState('Old Trafford')
    const [venueLat, setVenueLat] = useState(53.4631)
    const [venueLon, setVenueLon] = useState(-2.2913)

    const [matchReady, setMatchReady] = useState(false)
    const [buildingNotes, setBuildingNotes] = useState(false)
    const [commentaryData, setCommentaryData] = useState(null)
    const [buildStatus, setBuildStatus] = useState(null) // null | 'loading' | 'ready' | 'error'
    const [preparationTime, setPreparationTime] = useState(0)

    const buildCommentaryNotes = async () => {
        setBuildingNotes(true)
        setBuildStatus('loading')
        setCommentaryData(null)
        setPreparationTime(0)

        try {
            // Convert datetime to ISO format
            const isoDateTime = new Date(matchDateTime).toISOString()

            const res = await fetch(`${BACKEND}/api/v1/commentary/prepare-notes`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    home_team: homeTeam,
                    away_team: awayTeam,
                    sport,
                    match_datetime: isoDateTime,
                    venue,
                    venue_lat: parseFloat(venueLat),
                    venue_lon: parseFloat(venueLon),
                    include_embedded_json: true,
                }),
            })

            if (!res.ok) {
                throw new Error(`HTTP ${res.status}: ${res.statusText}`)
            }

            const data = await res.json()

            if (data.status === 'success') {
                setCommentaryData(data)
                setPreparationTime(data.preparation_time_ms)
                setMatchReady(true)
                setBuildStatus('ready')
            } else {
                throw new Error(data.error || 'Failed to generate notes')
            }
        } catch (err) {
            console.error('Commentary notes failed', err)
            setBuildStatus('error')
        } finally {
            setBuildingNotes(false)
        }
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
                    style={{ width: 140 }}
                    id="home-team-input"
                />
                <span style={{ color: 'var(--text-muted)', fontWeight: 700 }}>vs</span>
                <input
                    type="text"
                    placeholder="Away Team"
                    value={awayTeam}
                    onChange={e => setAwayTeam(e.target.value)}
                    style={{ width: 140 }}
                    id="away-team-input"
                />
                <select value={sport} onChange={e => setSport(e.target.value)} id="sport-select">
                    <option value="soccer">⚽ Soccer</option>
                    <option value="cricket">🏏 Cricket</option>
                    <option value="basketball">🏀 Basketball</option>
                    <option value="rugby">🏉 Rugby</option>
                    <option value="tennis">🎾 Tennis</option>
                    <option value="hockey">🏒 Hockey</option>
                </select>

                <input
                    type="datetime-local"
                    value={matchDateTime}
                    onChange={e => setMatchDateTime(e.target.value)}
                    style={{ width: 180 }}
                    id="match-datetime-input"
                />

                <input
                    type="text"
                    placeholder="Venue"
                    value={venue}
                    onChange={e => setVenue(e.target.value)}
                    style={{ width: 140 }}
                    id="venue-input"
                />

                <button
                    className="btn btn-primary"
                    onClick={buildCommentaryNotes}
                    disabled={buildingNotes || !homeTeam || !awayTeam || !venue}
                    id="build-commentary-btn"
                >
                    {buildingNotes
                        ? <><span className="spinner" /> Generating Notes...</>
                        : '📝 Generate Commentary Notes'
                    }
                </button>

                {buildStatus && (
                    <span className={`status-pill ${buildStatus}`}>
                        {buildStatus === 'loading' && '⏳ Researching all agents...'}
                        {buildStatus === 'ready' && `✅ Complete (${preparationTime.toFixed(0)}ms)`}
                        {buildStatus === 'error' && '⚠️ Generation failed'}
                    </span>
                )}
            </div>

            {/* Main Dashboard */}
            <div className="dashboard">

                {/* Left — main area */}
                <div className="dashboard-main">
                    {commentaryData && <CommentaryNotesViewer data={commentaryData} />}
                    {!commentaryData && (
                        <>
                            {/* Push-to-Talk */}
                            <PushToTalk
                                matchReady={matchReady}
                                homeTeam={homeTeam}
                                awayTeam={awayTeam}
                                sport={sport}
                            />

                            {/* Tactical Overlay */}
                            <TacticalOverlay sport={sport} />
                        </>
                    )}
                </div>

                {/* Right — sidebar */}
                <div className="dashboard-sidebar">
                    {/* Match Notes (top half) */}
                    {!commentaryData && (
                        <>
                            <MatchNotes notes={[]} loading={buildingNotes} />

                            {/* Event Feed (bottom half) */}
                            <EventFeed />
                        </>
                    )}
                </div>
            </div>
        </div>
    )
}
