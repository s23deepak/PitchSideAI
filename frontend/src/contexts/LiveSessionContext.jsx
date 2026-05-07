import { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react'

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

const LiveSessionContext = createContext(null)

export function LiveSessionProvider({
    children,
    homeTeam: initialHomeTeam = 'Barcelona',
    awayTeam: initialAwayTeam = 'Real Madrid',
    sport: initialSport = 'soccer',
}) {
    // Match info state
    const [homeTeam, setHomeTeam] = useState(initialHomeTeam)
    const [awayTeam, setAwayTeam] = useState(initialAwayTeam)
    const [sport, setSport] = useState(initialSport)
    const [matchSession, setMatchSession] = useState(null)

    // Notes & commentary state
    const [commentaryData, setCommentaryData] = useState(null)
    const [buildingNotes, setBuildingNotes] = useState(false)
    const [buildStatus, setBuildStatus] = useState(null)
    const [buildProgress, setBuildProgress] = useState('')
    const [liveLogs, setLiveLogs] = useState([])

    // Live session state
    const [liveCommentary, setLiveCommentary] = useState([])
    const [detection, setDetection] = useState(null)
    const [isConnected, setIsConnected] = useState(false)
    const [liveSessionReady, setLiveSessionReady] = useState(false)

    // WebSocket ref
    const wsRef = useRef(null)
    const sessionPromiseRef = useRef(null)
    const activeSessionKeyRef = useRef(null)
    const abortControllerRef = useRef(null)

    // Pending settings/language queue (for when WS isn't ready)
    const pendingSettingsRef = useRef(null)
    const pendingLanguageRef = useRef(null)

    // Initialize match session when teams change
    useEffect(() => {
        const key = buildMatchSessionKey(homeTeam, awayTeam, sport)
        setMatchSession(key)
    }, [homeTeam, awayTeam, sport])

    // Ensure live WebSocket session
    const ensureLiveSession = useCallback(async () => {
        if (!homeTeam || !awayTeam) return false

        // Close old WS if matchSession changed
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
                ws.send(JSON.stringify({
                    type: 'init',
                    home_team: homeTeam,
                    away_team: awayTeam,
                    sport: sport,
                }))

                // Send pending settings/language if queued
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
                        setIsConnected(true)
                        if (!settled) {
                            settled = true
                            resolve(true)
                        }
                    } else if (msg.type === 'status') {
                        setLiveSessionReady(false)
                    } else if (msg.type === 'commentary') {
                        setLiveCommentary((prev) => [msg, ...prev].slice(0, 100))
                        // Forward beat highlight
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
                    } else if (msg.type === 'trivia_card') {
                        window.dispatchEvent(new CustomEvent('pitchai:trivia_card', { detail: msg }))
                    } else if (msg.type === 'beat_highlight') {
                        window.dispatchEvent(new CustomEvent('pitchai:beat_highlight', {
                            detail: {
                                beatIndex: msg.beat_index,
                                confidence: msg.confidence,
                                nextIndices: msg.next_indices,
                            }
                        }))
                    } else if (msg.type === 'answer') {
                        window.dispatchEvent(new CustomEvent('pitchai:qa_answer', { detail: msg }))
                    } else if (msg.type === 'error' && !settled) {
                        settled = true
                        reject(new Error(msg.message || 'Live session failed'))
                    }
                } catch {
                    // ignore malformed frames
                }
            }

            ws.onerror = (err) => {
                console.warn('[LiveSession] WS error:', err)
                setIsConnected(false)
                setLiveSessionReady(false)
                if (!settled) {
                    settled = true
                    reject(new Error('Live session connection failed'))
                }
            }

            ws.onclose = () => {
                wsRef.current = null
                sessionPromiseRef.current = null
                setIsConnected(false)
                setLiveSessionReady(false)
            }
        }).finally(() => {
            sessionPromiseRef.current = null
        })

        return sessionPromiseRef.current
    }, [homeTeam, awayTeam, sport, matchSession])

    // Initialize live session when matchSession is ready
    useEffect(() => {
        if (matchSession) {
            ensureLiveSession().catch((err) => console.warn('[LiveSession] Init failed:', err))
        }
    }, [matchSession, ensureLiveSession])

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            // Cancel ongoing requests
            if (abortControllerRef.current) {
                abortControllerRef.current.abort()
            }
            // Close WebSocket
            wsRef.current?.close()
        }
    }, [])

    // Prepare notes via SSE stream
    const prepareNotes = useCallback(async (home, away) => {
        setBuildingNotes(true)
        setBuildStatus('loading')
        setBuildProgress('Starting...')
        setCommentaryData(null)
        setLiveLogs([])

        // Cancel any previous request
        if (abortControllerRef.current) {
            abortControllerRef.current.abort()
        }

        // Create new abort controller
        abortControllerRef.current = new AbortController()

        try {
            const res = await fetch(`${BACKEND}/api/v1/commentary/prepare-notes`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    home_team: home,
                    away_team: away,
                    sport: sport,
                }),
                signal: abortControllerRef.current.signal,
            })

            if (!res.ok) {
                throw new Error(`HTTP ${res.status}: ${res.statusText}`)
            }

            const reader = res.body.getReader()
            const decoder = new TextDecoder()
            let buffer = ''

            // Helper to add log entry
            const addLog = (message, type = 'info') => {
                const now = new Date()
                const time = now.toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
                setLiveLogs(prev => [...prev, { time, message, type }])
            }

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
                            setBuildStatus('ready')
                            setBuildProgress(1.0)
                            addLog('COMPLETE: Commentary notes ready for review.', 'success')
                        } else if (event.phase === 'error') {
                            addLog(`ERROR: ${event.message}`, 'error')
                            throw new Error(event.message)
                        } else {
                            // Use numeric progress if available, otherwise fallback to message
                            setBuildProgress(event.progress !== undefined ? event.progress : (event.message || event.phase))
                            // Stream log entry
                            const phaseLabel = event.phase?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || 'Processing'
                            addLog(`${phaseLabel}: ${event.message || 'Working...'}`, event.done ? 'success' : 'running')
                        }
                    } catch (parseErr) {
                        if (parseErr.message && !parseErr.message.startsWith('Unexpected')) {
                            throw parseErr
                        }
                    }
                }
            }
        } catch (err) {
            if (err.name === 'AbortError') {
                console.log('[LiveSession] Notes preparation cancelled')
                setBuildProgress('Cancelled')
                addLog('Cancelled by user', 'info')
            } else {
                console.error('[LiveSession] Notes generation failed:', err)
                setBuildStatus('error')
                setBuildProgress(err.message || 'Generation failed')
                addLog(`FAILED: ${err.message}`, 'error')
            }
        } finally {
            setBuildingNotes(false)
        }
    }, [sport])

    // Send match event
    const sendMatchEvent = useCallback(async (description) => {
        const ready = await ensureLiveSession()
        if (ready && wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
                type: 'match_event',
                description,
            }))
        }
    }, [ensureLiveSession])

    // Send tactical detection
    const sendTacticalDetection = useCallback(async (analysis) => {
        const ready = await ensureLiveSession()
        if (ready && wsRef.current?.readyState === WebSocket.OPEN && analysis) {
            wsRef.current.send(JSON.stringify({
                type: 'tactical_detection',
                analysis,
            }))
        }
    }, [ensureLiveSession])

    // Send query for Q&A
    const sendQuery = useCallback(async (text, confidence) => {
        const ready = await ensureLiveSession()
        if (ready && wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
                type: 'query',
                text,
                confidence,
            }))
        }
    }, [ensureLiveSession])

    // Update settings
    const updateSettings = useCallback((settings) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
                type: 'settings_update',
                ...settings,
            }))
        } else {
            // Queue for when WS connects
            pendingSettingsRef.current = settings
        }
    }, [])

    // Update language
    const updateLanguage = useCallback((language) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
                type: 'language_switch',
                language,
            }))
        } else {
            // Queue for when WS connects
            pendingLanguageRef.current = language
        }
    }, [])

    // Action: prepend a commentary message to the feed (capped at 100 items)
    const addCommentaryItem = useCallback((msg) => {
        setLiveCommentary((prev) => [msg, ...prev].slice(0, 100))
    }, [])

    // Action: update the current tactical detection result
    const updateDetection = useCallback((data) => {
        setDetection(data)
    }, [])

    const value = {
        // Match info
        homeTeam,
        awayTeam,
        sport,
        matchSession,

        // Notes & commentary
        commentaryData,
        buildingNotes,
        buildStatus,
        buildProgress,
        liveLogs,

        // Live session
        liveCommentary,
        detection,
        isConnected,
        liveSessionReady,

        // Actions
        prepareNotes,
        sendMatchEvent,
        sendTacticalDetection,
        sendQuery,
        updateSettings,
        updateLanguage,
        addCommentaryItem,
        updateDetection,

        // Direct refs for advanced usage
        wsRef,
    }

    return (
        <LiveSessionContext.Provider value={value}>
            {children}
        </LiveSessionContext.Provider>
    )
}

export function useLiveSession() {
    const context = useContext(LiveSessionContext)
    if (!context) {
        throw new Error('useLiveSession must be used within a LiveSessionProvider')
    }
    return context
}

export default LiveSessionContext
