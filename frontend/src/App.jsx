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

    const [matchReady, setMatchReady] = useState(false)
    const [buildingNotes, setBuildingNotes] = useState(false)
    const [commentaryData, setCommentaryData] = useState(null)
    const [buildStatus, setBuildStatus] = useState(null) // null | 'loading' | 'ready' | 'error'
    const [preparationTime, setPreparationTime] = useState(0)
    const [detection, setDetection] = useState(null)

    const buildCommentaryNotes = async () => {
        setBuildingNotes(true)
        setBuildStatus('loading')
        setCommentaryData(null)
        setPreparationTime(0)

        try {
            const res = await fetch(`${BACKEND}/api/v1/commentary/prepare-notes`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    home_team: homeTeam,
                    away_team: awayTeam,
                    sport
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

                <button
                    className="btn btn-primary"
                    onClick={buildCommentaryNotes}
                    disabled={buildingNotes || !homeTeam || !awayTeam}
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
                    {/* Push-to-Talk always visible */}
                    <PushToTalk
                        matchReady={matchReady}
                        homeTeam={homeTeam}
                        awayTeam={awayTeam}
                        sport={sport}
                    />

                    {commentaryData && <CommentaryNotesViewer data={commentaryData} />}
                    {!commentaryData && <TacticalOverlay sport={sport} detection={detection} setDetection={setDetection} />}
                </div>

                {/* Right — sidebar */}
                <div className="dashboard-sidebar">
                    {/* Match Notes OR Tactical Detection */}
                    {!commentaryData && (
                        <>
                            {detection ? (
                                <div className="tactical-info" style={{ width: '100%', minWidth: 300 }}>
                                    <div className="detection-card">
                                        <div className="detection-label">Tactical Label</div>
                                        <div className="detection-value">
                                            {detection.tactical_label}
                                        </div>
                                        {detection.key_observation && (
                                            <div className="detection-sub">{detection.key_observation}</div>
                                        )}
                                        {detection.confidence != null && (
                                            <>
                                                <div className="confidence-bar">
                                                    <div className="confidence-fill" style={{ width: `${detection.confidence * 100}%` }} />
                                                </div>
                                                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                                                    {Math.round(detection.confidence * 100)}% confidence
                                                </div>
                                            </>
                                        )}
                                    </div>

                                    <div className="detection-card">
                                        <div className="detection-label">Formation (Home)</div>
                                        <div className="detection-value">{detection.formation_home || '4-3-3'}</div>
                                    </div>

                                    <div className="detection-card">
                                        <div className="detection-label">Formation (Away)</div>
                                        <div className="detection-value">{detection.formation_away || '4-2-3-1'}</div>
                                    </div>
                                </div>
                            ) : (
                                <MatchNotes notes={[]} loading={buildingNotes} />
                            )}

                            {/* Event Feed (bottom half) */}
                            <EventFeed />
                        </>
                    )}
                </div>
            </div>
        </div>
    )
}
