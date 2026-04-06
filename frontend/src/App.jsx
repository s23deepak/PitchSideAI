import { useState, useRef, useEffect } from 'react'
import './index.css'
import PushToTalk from './components/PushToTalk'
import TacticalOverlay from './components/TacticalOverlay'
import MatchNotes from './components/MatchNotes'
import EventFeed from './components/EventFeed'
import CommentaryNotesViewer from './components/CommentaryNotesViewer'
import CommentaryFeed from './components/CommentaryFeed'

const BACKEND = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

function buildMatchSessionKey(homeTeam, awayTeam, sport) {
    const slugify = (value) =>
        (value || '')
            .trim()
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-+|-+$/g, '') || 'unknown'

    return `${slugify(sport)}#${slugify(homeTeam)}#vs#${slugify(awayTeam)}`
}

export default function App() {
    const [homeTeam, setHomeTeam] = useState('Manchester United')
    const [awayTeam, setAwayTeam] = useState('Liverpool')
    const [sport, setSport] = useState('soccer')

    const [matchReady, setMatchReady] = useState(false)
    const [buildingNotes, setBuildingNotes] = useState(false)
    const [commentaryData, setCommentaryData] = useState(null)
    const [buildStatus, setBuildStatus] = useState(null) // null | 'loading' | 'ready' | 'error'
    const [buildProgress, setBuildProgress] = useState('') // current phase message
    const [preparationTime, setPreparationTime] = useState(0)
    const [detection, setDetection] = useState(null)
    const [liveCommentary, setLiveCommentary] = useState([])
    const [liveSessionReady, setLiveSessionReady] = useState(false)
    const wsRef = useRef(null)
    const sessionPromiseRef = useRef(null)
    const activeSessionKeyRef = useRef(null)
    const matchSession = buildMatchSessionKey(homeTeam, awayTeam, sport)

    useEffect(() => {
        if (wsRef.current) {
            wsRef.current.close()
            wsRef.current = null
        }
        sessionPromiseRef.current = null
        activeSessionKeyRef.current = null
        setLiveSessionReady(false)
        setLiveCommentary([])
    }, [matchSession])

    useEffect(() => () => wsRef.current?.close(), [])

    const ensureLiveSession = async () => {
        if (!homeTeam || !awayTeam) {
            return false
        }

        if (
            wsRef.current?.readyState === WebSocket.OPEN &&
            activeSessionKeyRef.current === matchSession &&
            liveSessionReady
        ) {
            return true
        }

        if (sessionPromiseRef.current) {
            return sessionPromiseRef.current
        }

        const wsUrl = BACKEND.replace(/^http/, 'ws') + '/ws/live'
        const ws = new WebSocket(wsUrl)
        wsRef.current = ws
        activeSessionKeyRef.current = matchSession

        sessionPromiseRef.current = new Promise((resolve, reject) => {
            let settled = false

            ws.onopen = () => {
                ws.send(JSON.stringify({ type: 'init', home_team: homeTeam, away_team: awayTeam, sport }))
            }

            ws.onmessage = (e) => {
                try {
                    const msg = JSON.parse(e.data)
                    if (msg.type === 'ready') {
                        setLiveSessionReady(true)
                        if (!settled) {
                            settled = true
                            resolve(true)
                        }
                    } else if (msg.type === 'status') {
                        setLiveSessionReady(false)
                    } else if (msg.type === 'commentary') {
                        setLiveCommentary((prev) => [msg, ...prev].slice(0, 100))
                    } else if (msg.type === 'error' && !settled) {
                        settled = true
                        reject(new Error(msg.message || 'Live session failed'))
                    }
                } catch {
                    /* ignore malformed frames */
                }
            }

            ws.onerror = (err) => {
                console.warn('WS error', err)
                setLiveSessionReady(false)
                if (!settled) {
                    settled = true
                    reject(new Error('Live session connection failed'))
                }
            }

            ws.onclose = () => {
                wsRef.current = null
                sessionPromiseRef.current = null
                setLiveSessionReady(false)
            }
        }).finally(() => {
            sessionPromiseRef.current = null
        })

        return sessionPromiseRef.current
    }

    useEffect(() => {
        if (matchReady) {
            ensureLiveSession().catch((err) => console.warn('Live session init failed', err))
        }
    }, [matchReady]) // eslint-disable-line react-hooks/exhaustive-deps

    const sendMatchEvent = async (description) => {
        const ready = await ensureLiveSession()
        if (ready && wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'match_event', description }))
        }
    }

    const sendTacticalDetection = async (analysis) => {
        const ready = await ensureLiveSession()
        if (ready && wsRef.current?.readyState === WebSocket.OPEN && analysis) {
            wsRef.current.send(JSON.stringify({ type: 'tactical_detection', analysis }))
        }
    }

    const buildCommentaryNotes = async () => {
        setBuildingNotes(true)
        setBuildStatus('loading')
        setBuildProgress('Starting...')
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

            const reader = res.body.getReader()
            const decoder = new TextDecoder()
            let buffer = ''

            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                buffer += decoder.decode(value, { stream: true })
                const lines = buffer.split('\n')
                buffer = lines.pop() // keep incomplete line in buffer

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue
                    try {
                        const event = JSON.parse(line.slice(6))
                        if (event.phase === 'complete' && event.result) {
                            const data = event.result
                            setCommentaryData(data)
                            setPreparationTime(data.preparation_time_ms)
                            setMatchReady(true)
                            setBuildStatus('ready')
                            setBuildProgress('')
                        } else if (event.phase === 'error') {
                            throw new Error(event.message)
                        } else {
                            setBuildProgress(event.message || event.phase)
                        }
                    } catch (parseErr) {
                        if (parseErr.message && !parseErr.message.startsWith('Unexpected'))
                            throw parseErr
                    }
                }
            }
        } catch (err) {
            console.error('Commentary notes failed', err)
            setBuildStatus('error')
            setBuildProgress(err.message || 'Generation failed')
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
                    {(matchReady || liveSessionReady)
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
                        {buildStatus === 'loading' && `⏳ ${buildProgress || 'Starting...'}`}
                        {buildStatus === 'ready' && `✅ Complete (${(preparationTime / 1000).toFixed(1)}s)`}
                        {buildStatus === 'error' && `⚠️ ${buildProgress || 'Generation failed'}`}
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

                    {/* TacticalOverlay always visible — upload frame / video at any time */}
                    <TacticalOverlay
                        sport={sport}
                        matchSession={matchSession}
                        detection={detection}
                        setDetection={setDetection}
                        sendMatchEvent={sendMatchEvent}
                        sendTacticalDetection={sendTacticalDetection}
                    />

                    {/* Commentary notes appear below the pitch once generated */}
                    {commentaryData && <CommentaryNotesViewer data={commentaryData} liveDetection={detection} />}
                </div>

                {/* Right — sidebar */}
                <div className="dashboard-sidebar">
                    {/* Live Commentary Feed — once match is ready */}
                    {(matchReady || liveSessionReady || liveCommentary.length > 0) && (
                        <CommentaryFeed messages={liveCommentary} sendMatchEvent={sendMatchEvent} />
                    )}

                    {/* Tactical detection card */}
                    {detection && (
                        <div className="tactical-info" style={{ width: '100%', minWidth: 300 }}>
                            <div className="detection-card">
                                <div className="detection-label">Tactical Label</div>
                                <div className="detection-value">{detection.tactical_label}</div>
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
                    )}

                    {!detection && !matchReady && (
                        <MatchNotes notes={[]} loading={buildingNotes} />
                    )}

                    {/* Event Feed always visible */}
                    <EventFeed matchSession={matchSession} />
                </div>
            </div>
        </div>
    )
}
