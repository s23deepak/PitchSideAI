import { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react'
import { backendUrl, backendWsUrl } from '@/lib/backend-url'

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
    const [connectionState, setConnectionState] = useState('idle')
    const [connectionError, setConnectionError] = useState(null)

    // WebSocket ref
    const wsRef = useRef(null)
    const sessionPromiseRef = useRef(null)
    const activeSessionKeyRef = useRef(null)
    const abortControllerRef = useRef(null)
    const reconnectTimerRef = useRef(null)
    const shouldReconnectRef = useRef(true)

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
            shouldReconnectRef.current = false
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

        const wsUrl = backendWsUrl('/ws/live')
        const ws = new WebSocket(wsUrl)
        wsRef.current = ws
        activeSessionKeyRef.current = matchSession
        shouldReconnectRef.current = true
        setConnectionState('connecting')
        setConnectionError(null)

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
                        setConnectionState('ready')
                        setConnectionError(null)
                        if (!settled) {
                            settled = true
                            resolve(true)
                        }
                    } else if (msg.type === 'status') {
                        setConnectionState((current) => current === 'ready' ? 'ready' : 'initializing')
                    } else if (msg.type === 'commentary') {
                        setLiveCommentary((prev) => [msg, ...prev].slice(0, 100))
                        // Forward beat highlight
                        if (msg.beat_indices && msg.beat_indices.length > 0) {
                            const bestBeatIdx = msg.beat_indices[0]
                            const bestConfidence = msg.confidence || 0.8
                            window.dispatchEvent(new CustomEvent('pitchsideai:beat_highlight', {
                                detail: {
                                    beatIndex: bestBeatIdx,
                                    confidence: bestConfidence,
                                    nextIndices: msg.beat_indices.slice(0, 3),
                                }
                            }))
                        }
                    } else if (msg.type === 'trivia_card') {
                        window.dispatchEvent(new CustomEvent('pitchsideai:trivia_card', { detail: msg }))
                    } else if (msg.type === 'beat_highlight') {
                        window.dispatchEvent(new CustomEvent('pitchsideai:beat_highlight', {
                            detail: {
                                beatIndex: msg.beat_index,
                                confidence: msg.confidence,
                                nextIndices: msg.next_indices,
                            }
                        }))
                    } else if (msg.type === 'answer') {
                        window.dispatchEvent(new CustomEvent('pitchsideai:qa_answer', { detail: msg }))
                    } else if (msg.type === 'error') {
                        const message = msg.message || 'Live session failed'
                        setConnectionState('error')
                        setConnectionError(message)
                        if (!settled) {
                            settled = true
                            reject(new Error(message))
                        }
                    }
                } catch {
                    // ignore malformed frames
                }
            }

            ws.onerror = (err) => {
                if (wsRef.current !== ws) return
                console.warn('[LiveSession] WS error:', err)
                setIsConnected(false)
                setLiveSessionReady(false)
                setConnectionState('error')
                setConnectionError('Live session connection failed')
                if (!settled) {
                    settled = true
                    reject(new Error('Live session connection failed'))
                }
            }

            ws.onclose = () => {
                if (wsRef.current !== ws) return
                wsRef.current = null
                sessionPromiseRef.current = null
                setIsConnected(false)
                setLiveSessionReady(false)
                setConnectionState(shouldReconnectRef.current ? 'reconnecting' : 'idle')
                // Schedule reconnect so the mic/AI-ready state recovers automatically
                if (shouldReconnectRef.current && reconnectTimerRef.current === null) {
                    reconnectTimerRef.current = setTimeout(() => {
                        reconnectTimerRef.current = null
                        ensureLiveSession().catch(() => {})
                    }, 5000)
                }
            }
        }).finally(() => {
            sessionPromiseRef.current = null
        })

        return sessionPromiseRef.current
    }, [homeTeam, awayTeam, sport, matchSession])

    // Initialize live session when matchSession is ready, with auto-reconnect on failure
    useEffect(() => {
        if (!matchSession) return

        let cancelled = false

        const connect = () => {
            if (cancelled) return
            ensureLiveSession().catch((err) => {
                console.warn('[LiveSession] Init failed:', err)
                // Retry after 5 s if not already connected and not cancelled
                if (!cancelled) {
                    reconnectTimerRef.current = setTimeout(() => {
                        if (!cancelled) connect()
                    }, 5000)
                }
            })
        }

        connect()

        return () => {
            cancelled = true
            shouldReconnectRef.current = false
            if (reconnectTimerRef.current) {
                clearTimeout(reconnectTimerRef.current)
                reconnectTimerRef.current = null
            }
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
            shouldReconnectRef.current = false
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

        const addLog = (message, type = 'info') => {
            const now = new Date()
            const time = now.toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
            setLiveLogs(prev => [...prev, { time, message, type }])
        }

        try {
            const res = await fetch(backendUrl('/api/v1/commentary/prepare-notes'), {
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

            const job = await res.json()
            addLog(`QUEUED: Notes job ${job.job_id}`, job.created ? 'success' : 'info')

            await new Promise((resolve, reject) => {
                const eventsUrl = job.events_url?.startsWith('http')
                    ? job.events_url
                    : backendUrl(job.events_url)
                const es = new EventSource(eventsUrl)

                abortControllerRef.current.signal.addEventListener('abort', () => {
                    es.close()
                    reject(new DOMException('Notes preparation cancelled', 'AbortError'))
                }, { once: true })

                es.onmessage = (message) => {
                    try {
                        const event = JSON.parse(message.data)
                        if (event.phase === 'complete' && event.result) {
                            const data = event.result
                            setCommentaryData(data)
                            setBuildStatus('ready')
                            setBuildProgress(1.0)
                            addLog('COMPLETE: Commentary notes ready for review.', 'success')
                            es.close()
                            resolve()
                        } else if (event.phase === 'error') {
                            addLog(`ERROR: ${event.message}`, 'error')
                            es.close()
                            reject(new Error(event.message))
                        } else {
                            setBuildProgress(event.progress !== undefined ? event.progress : (event.message || event.phase))
                            const phaseLabel = event.phase?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || 'Processing'
                            addLog(`${phaseLabel}: ${event.message || 'Working...'}`, event.done ? 'success' : 'running')
                        }
                    } catch (parseErr) {
                        es.close()
                        reject(parseErr)
                    }
                }

                es.onerror = () => {
                    es.close()
                    reject(new Error('Lost notes job event stream'))
                }
            })
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
        connectionState,
        connectionError,

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
