import { useState, useRef, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import './index.css'
import HomeScreen from './components/HomeScreen'
import MatchDashboard from './components/MatchDashboard'
import PushToTalk from './components/PushToTalk'
import EventFeed from './components/EventFeed'
import CommentaryNotesViewer from './components/CommentaryNotesViewer'
import CommentaryFeed from './components/CommentaryFeed'
import LiveVideoPlayer from './components/LiveVideoPlayer'
import LandingPage from './pages/LandingPage'
import VideoPage from './pages/VideoPage'
import FanLensBroadcast from './pages/FanLensBroadcast'
import CommentatorDashboard from './pages/CommentatorDashboard'
import NotesGenerationHub from './pages/NotesGenerationHub'
import TabbedLivePage from './pages/TabbedLivePage'
import { LiveSessionProvider } from './contexts/LiveSessionContext'

const BACKEND = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

function buildMatchSessionKey(homeTeam, awayTeam, sport = 'soccer') {
    const slugify = (value) =>
        (value || '')
            .trim()
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-+|-+$/g, '') || 'unknown'

    return `${slugify(sport)}#${slugify(homeTeam)}#vs#${slugify(awayTeam)}`
}

// Inner app component that has access to router hooks
function AppContent() {
    const navigate = useNavigate()
    // Screen state
    const [currentScreen, setCurrentScreen] = useState('home') // 'home' | 'dashboard'

    // Match state
    const [homeTeam, setHomeTeam] = useState('')
    const [awayTeam, setAwayTeam] = useState('')
    const [sport] = useState('soccer')
    const [matchSession, setMatchSession] = useState(null)

    // Dashboard state
    const [matchReady, setMatchReady] = useState(false)
    const [buildingNotes, setBuildingNotes] = useState(false)
    const [commentaryData, setCommentaryData] = useState(null)
    const [buildStatus, setBuildStatus] = useState(null)
    const [buildProgress, setBuildProgress] = useState('')
    const [preparationTime, setPreparationTime] = useState(0)
    const [detection, setDetection] = useState(null)
    const [liveCommentary, setLiveCommentary] = useState([])
    const [liveSessionReady, setLiveSessionReady] = useState(false)

    const wsRef = useRef(null)
    const sessionPromiseRef = useRef(null)
    const activeSessionKeyRef = useRef(null)
    const abortControllerRef = useRef(null)

    // Handle starting a new match — only transitions to dashboard, does NOT auto-trigger notes
    const handleStartMatch = (home, away) => {
        setHomeTeam(home)
        setAwayTeam(away)
        setMatchSession(buildMatchSessionKey(home, away))
        setCurrentScreen('dashboard')
        navigate('/dashboard')
    }

    // Build commentary notes
    const buildCommentaryNotes = async (home, away) => {
        setBuildingNotes(true)
        setBuildStatus('loading')
        setBuildProgress('Starting...')
        setCommentaryData(null)
        setPreparationTime(0)

        // Cancel any previous request
        if (abortControllerRef.current) {
            abortControllerRef.current.abort()
        }

        // Create new abort controller for this request
        abortControllerRef.current = new AbortController()

        try {
            const res = await fetch(`${BACKEND}/api/v1/commentary/prepare-notes`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    home_team: home,
                    away_team: away,
                    sport: 'soccer'
                }),
                signal: abortControllerRef.current.signal
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
                buffer = lines.pop()

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
            // Don't show error if request was aborted (user cancelled)
            if (err.name === 'AbortError') {
                console.log('Commentary preparation cancelled')
                setBuildProgress('Cancelled')
            } else {
                console.error('Commentary notes failed', err)
                setBuildStatus('error')
                setBuildProgress(err.message || 'Generation failed')
            }
        } finally {
            setBuildingNotes(false)
        }
    }

    // Ensure live WebSocket session
    const ensureLiveSession = async () => {
        if (!homeTeam || !awayTeam) return false

        // Fix #13: Close old WS if matchSession changed (race condition fix)
        if (activeSessionKeyRef.current && activeSessionKeyRef.current !== matchSession) {
            wsRef.current?.close()
            wsRef.current = null
            setLiveSessionReady(false)
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

                // Fix #12: Send any pending settings/language when WS connects
                if (pendingSettingsRef.current) {
                    ws.send(JSON.stringify({
                        type: 'settings_update',
                        ...pendingSettingsRef.current,
                    }))
                    pendingSettingsRef.current = null
                }
                if (pendingLanguageRef.current) {
                    ws.send(JSON.stringify({
                        type: 'language_switch',
                        language: pendingLanguageRef.current,
                    }))
                    pendingLanguageRef.current = null
                }
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
                        // Story 3.2: Forward beat highlight to Teleprompter
                        if (msg.beat_indices && msg.beat_indices.length > 0) {
                            const bestBeatIdx = msg.beat_indices[0]
                            const bestConfidence = msg.confidence || 0.8
                            window.dispatchEvent(new CustomEvent('pitchai:beat_highlight', {
                                detail: {
                                    beatIndex: bestBeatIdx,
                                    confidence: bestConfidence,
                                    nextIndices: msg.beat_indices.slice(0, 3),
                                }
                            }))
                        }
                    } else if (msg.type === 'beat_highlight') {
                        // Story 3.2: Direct beat highlight message
                        window.dispatchEvent(new CustomEvent('pitchai:beat_highlight', {
                            detail: {
                                beatIndex: msg.beat_index,
                                confidence: msg.confidence,
                                nextIndices: msg.next_indices,
                            }
                        }))
                    } else if (msg.type === 'error' && !settled) {
                        settled = true
                        reject(new Error(msg.message || 'Live session failed'))
                    }
                } catch {
                    // ignore malformed frames
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

    // Initialize live session when match is ready
    useEffect(() => {
        if (matchReady && matchSession) {
            ensureLiveSession().catch((err) => console.warn('Live session init failed', err))
        }
    }, [matchReady, matchSession])

    // Fix #12: Queue for settings/language when WS not ready
    const pendingSettingsRef = useRef(null)
    const pendingLanguageRef = useRef(null)

    // Handle settings and language changes via custom events
    useEffect(() => {
        const handleSettingsUpdate = (e) => {
            const settings = e.detail
            if (wsRef.current?.readyState === WebSocket.OPEN) {
                wsRef.current.send(JSON.stringify({
                    type: 'settings_update',
                    ...settings,
                }))
            } else {
                // Queue settings for when WS connects (fix #12)
                pendingSettingsRef.current = settings
            }
        }

        const handleLanguageSwitch = (e) => {
            const { language } = e.detail
            if (wsRef.current?.readyState === WebSocket.OPEN) {
                wsRef.current.send(JSON.stringify({
                    type: 'language_switch',
                    language,
                }))
            } else {
                // Queue language for when WS connects (fix #12)
                pendingLanguageRef.current = language
            }
        }

        window.addEventListener('pitchai:settings', handleSettingsUpdate)
        window.addEventListener('pitchai:language', handleLanguageSwitch)

        return () => {
            window.removeEventListener('pitchai:settings', handleSettingsUpdate)
            window.removeEventListener('pitchai:language', handleLanguageSwitch)
        }
    }, [])

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            // Cancel ongoing research request on unmount/refresh
            if (abortControllerRef.current) {
                abortControllerRef.current.abort()
            }
            wsRef.current?.close()
        }
    }, [])

    // Send match event
    const sendMatchEvent = async (description) => {
        const ready = await ensureLiveSession()
        if (ready && wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'match_event', description }))
        }
    }

    // Send tactical detection
    const sendTacticalDetection = async (analysis) => {
        const ready = await ensureLiveSession()
        if (ready && wsRef.current?.readyState === WebSocket.OPEN && analysis) {
            wsRef.current.send(JSON.stringify({ type: 'tactical_detection', analysis }))
        }
    }

    // Handle chunk analyzed from live video
    const handleChunkAnalyzed = (result) => {
        setDetection(result)
        // Auto-send as tactical detection
        sendTacticalDetection(result)
    }

    // Handle commentary from live video
    const handleVideoCommentary = (msg) => {
        if (msg.type === 'commentary') {
            setLiveCommentary((prev) => [msg, ...prev].slice(0, 100))
        }
    }

    // Render current screen
    if (currentScreen === 'home') {
        return <HomeScreen onStartMatch={handleStartMatch} />
    }

    // Handle go back to home
    const handleGoBack = () => {
        // Cancel ongoing research request
        if (abortControllerRef.current) {
            abortControllerRef.current.abort()
        }
        // Cleanup WebSocket
        wsRef.current?.close()
        wsRef.current = null
        // Reset state
        setCurrentScreen('home')
        setMatchReady(false)
        setLiveSessionReady(false)
        setLiveCommentary([])
        setDetection(null)
        setCommentaryData(null)
        setHomeTeam('')
        setAwayTeam('')
        setMatchSession(null)
    }

    // Dashboard screen
    return (
        <div className="match-dashboard">
            <MatchDashboard
                homeTeam={homeTeam}
                awayTeam={awayTeam}
                sport={sport}
                matchSession={matchSession}
                commentaryData={commentaryData}
                detection={detection}
                setDetection={setDetection}
                liveCommentary={liveCommentary}
                onSendMatchEvent={sendMatchEvent}
                onSendTacticalDetection={sendTacticalDetection}
                onGoBack={handleGoBack}
                onPrepareNotes={() => buildCommentaryNotes(homeTeam, awayTeam)}
                buildingNotes={buildingNotes}
                buildStatus={buildStatus}
                buildProgress={buildProgress}
            />
        </div>
    )
}

// Main App component with routing
export default function App() {
    return (
        <BrowserRouter>
            <Routes>
                <Route path="/" element={<LandingPage />} />
                <Route path="/watch" element={<VideoPage />} />
                <Route path="/dashboard" element={<AppContent />} />
                <Route path="/live" element={<TabbedLivePage />} />
                <Route path="/fan-lens" element={<Navigate to="/live?tab=fan-lens" replace />} />
                <Route path="/commentator" element={<Navigate to="/live?tab=commentator" replace />} />
                <Route path="/notes" element={<Navigate to="/live?tab=notes" replace />} />
            </Routes>
        </BrowserRouter>
    )
}
