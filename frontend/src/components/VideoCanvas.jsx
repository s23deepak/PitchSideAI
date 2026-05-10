import { useState, useRef, useEffect, useCallback } from 'react'

const BACKEND = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'
const FAN_LENS_BACKENDS = new Set(['vllm', 'sglang', 'streaming_vlm', 'auto'])
const DEFAULT_FAN_LENS_BACKEND = FAN_LENS_BACKENDS.has(import.meta.env.VITE_FAN_LENS_BACKEND)
    ? import.meta.env.VITE_FAN_LENS_BACKEND
    : 'vllm'

/**
 * VideoCanvas — Fan Lens video player with tactical overlays.
 *
 * Renders video from camera or file with SVG overlays for:
 * - Player position dots (home=blue, away=red)
 * - Ball position marker
 * - Tactical label badge
 * - Connection state indicator
 * - Trivia card animations
 *
 * Streams frames to /ws/video/streaming for live video Q&A.
 */
export default function VideoCanvas({
    matchSession,
    homeTeam = 'Home',
    awayTeam = 'Away',
    sport = 'soccer',
    startLabel = 'Start Video Analysis',
    onTacticalDetection,
    onCommentary,
    onVideoReady, // (objectUrl: string | null) => void — notifies parent when video loads/clears
    onStreamingStatus,
}) {
    // Streaming state
    const [isStreaming, setIsStreaming] = useState(false)
    const [isPaused, setIsPaused] = useState(false)
    const [videoFile, setVideoFile] = useState(null)
    const [currentTime, setCurrentTime] = useState(0)
    const [duration, setDuration] = useState(0)
    const [framesSent, setFramesSent] = useState(0)
    const [videoReady, setVideoReady] = useState(false)
    const [wsReady, setWsReady] = useState(false)
    const [connectionState, setConnectionState] = useState('disconnected') // 'connected' | 'reconnecting' | 'disconnected'

    // Detection/overlay state
    const [currentDetection, setCurrentDetection] = useState(null)
    const [overlayVisible, setOverlayVisible] = useState(true)
    const [triviaCard, setTriviaCard] = useState(null)

    // Backend config
    const [backend, setBackend] = useState(DEFAULT_FAN_LENS_BACKEND)
    const [chunkInterval, setChunkInterval] = useState(5) // seconds
    const [targetFps, setTargetFps] = useState(8)

    const wsRef = useRef(null)
    const videoRef = useRef(null)
    const canvasRef = useRef(null)
    const captureInterval = useRef(null)
    const overlayTimeout = useRef(null)
    const pendingQueryRef = useRef(null)
    const framesSentRef = useRef(0)

    // Connect to video streaming WebSocket (separate from LiveSession /ws/live)
    const connectWebSocket = useCallback(() => {
        const wsUrl = BACKEND.replace(/^http/, 'ws') + '/ws/video/streaming'
        const ws = new WebSocket(wsUrl)
        wsRef.current = ws

        setConnectionState('reconnecting')

        ws.onopen = () => {
            ws.send(JSON.stringify({
                type: 'init',
                home_team: homeTeam,
                away_team: awayTeam,
                sport: sport,
                config: {
                    backend: backend,
                    chunk_interval_seconds: chunkInterval,
                    max_chunk_frames: Math.round(targetFps * chunkInterval),
                    target_fps: targetFps,
                    sport: sport,
                },
            }))
            setConnectionState('connected')
            setWsReady(true)
        }

        ws.onmessage = (e) => {
            if (typeof e.data !== 'string') return
            try {
                const msg = JSON.parse(e.data)

                switch (msg.type) {
                    case 'ready':
                        setWsReady(true)
                        setConnectionState('connected')
                        break

                    case 'status':
                        // Stats/status messages, not an error
                        break

                    case 'commentary':
                        // Tactical analysis coming from streaming video endpoint
                        if (msg.tactical_label) {
                            const detection = {
                                tactical_label: msg.tactical_label,
                                confidence: msg.confidence || 0,
                            }
                            setCurrentDetection(detection)
                            setOverlayVisible(true)
                            if (overlayTimeout.current) clearTimeout(overlayTimeout.current)
                            overlayTimeout.current = setTimeout(() => {
                                setOverlayVisible(false)
                            }, 3000)
                            if (onTacticalDetection && msg.confidence > 0.6) {
                                onTacticalDetection(detection)
                            }
                        }
                        onCommentary?.(msg)
                        break

                    case 'answer':
                        window.dispatchEvent(new CustomEvent('pitchai:qa_answer', { detail: msg }))
                        break

                    case 'trivia_card':
                        const displayDuration = msg.confidence >= 0.8 ? 5000 : 3000
                        setTriviaCard({
                            text: msg.text,
                            source: msg.source,
                            confidence: msg.confidence,
                            fadeInMs: msg.fade_in_ms || 400,
                            fadeOutMs: msg.fade_out_ms || 400,
                        })
                        setTimeout(() => {
                            setTriviaCard(null)
                        }, displayDuration)
                        break

                    case 'chunk_analyzed':
                        // Full chunk analysis result
                        if (msg.result?.tactical_label) {
                            const detection = {
                                tactical_label: msg.result.tactical_label,
                                confidence: msg.result.confidence || 0,
                                key_observation: msg.result.key_observation,
                            }
                            setCurrentDetection(detection)
                            setOverlayVisible(true)
                            if (overlayTimeout.current) clearTimeout(overlayTimeout.current)
                            overlayTimeout.current = setTimeout(() => {
                                setOverlayVisible(false)
                            }, 5000)
                            if (onTacticalDetection && msg.result.confidence > 0.6) {
                                onTacticalDetection(detection)
                            }
                        }
                        break

                    case 'error':
                        console.error('VideoCanvas error:', msg.message)
                        setConnectionState('disconnected')
                        break

                    case 'ping':
                        break
                }
            } catch (err) {
                console.warn('WS parse error:', err)
            }
        }

        ws.onerror = (err) => {
            console.error('WebSocket error:', err)
            setConnectionState('disconnected')
            setIsStreaming(false)
            setWsReady(false)
        }

        ws.onclose = () => {
            wsRef.current = null
            setWsReady(false)
            setConnectionState('disconnected')
        }
    }, [homeTeam, awayTeam, sport, backend, chunkInterval, targetFps, onTacticalDetection, onCommentary])

    useEffect(() => {
        onStreamingStatus?.({
            isStreaming,
            wsReady,
            connectionState,
            framesSent,
            videoReady,
            hasVideo: Boolean(videoFile),
            currentTime,
        })
    }, [isStreaming, wsReady, connectionState, framesSent, videoReady, videoFile, currentTime, onStreamingStatus])

    // Frame capture at target FPS
    const captureLoop = useCallback(() => {
        if (!videoRef.current || !canvasRef.current || isPaused || !videoReady) return

        const video = videoRef.current
        const canvas = canvasRef.current
        const ctx = canvas.getContext('2d')

        if (!video.videoWidth || !video.videoHeight) return

        // Scale down for performance
        const scale = 0.5
        canvas.width = Math.floor(video.videoWidth * scale)
        canvas.height = Math.floor(video.videoHeight * scale)

        try {
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
            const frame_b64 = canvas.toDataURL('image/jpeg', 0.7).split(',')[1]
            const timestamp_ms = Math.floor(video.currentTime * 1000)

            if (wsRef.current?.readyState === WebSocket.OPEN) {
                wsRef.current.send(JSON.stringify({
                    type: 'frame',
                    frame_b64,
                    timestamp_ms,
                    keyframe: framesSentRef.current % Math.round(targetFps) === 0,
                }))
                const nextFramesSent = framesSentRef.current + 1
                framesSentRef.current = nextFramesSent
                setFramesSent(nextFramesSent)
                if (pendingQueryRef.current && nextFramesSent >= 2) {
                    wsRef.current.send(JSON.stringify({ type: 'query', text: pendingQueryRef.current }))
                    pendingQueryRef.current = null
                }
            }
        } catch (err) {
            console.error('Frame capture error:', err)
        }
    }, [isPaused, videoReady, targetFps])

    const handleVideoSelect = (e) => {
        const file = e.target.files?.[0]
        if (!file) return
        setVideoFile(file)
        setVideoReady(false)
        setFramesSent(0)
        framesSentRef.current = 0
        pendingQueryRef.current = null

        const url = URL.createObjectURL(file)
        if (videoRef.current) {
            videoRef.current.src = url
            videoRef.current.load()
        }
        onVideoReady?.(url) // notify parent so SplitScreen can mirror the video
    }

    const startStreaming = () => {
        if (!videoRef.current || !videoFile) return

        connectWebSocket()
        setIsStreaming(true)
        setIsPaused(false)

        videoRef.current.play().catch(err => console.error('Play error:', err))

        const intervalMs = Math.round(1000 / targetFps)
        captureInterval.current = setInterval(captureLoop, intervalMs)
    }

    const stopStreaming = () => {
        setIsStreaming(false)
        setIsPaused(false)
        setWsReady(false)
        setVideoReady(false)
        setVideoFile(null)
        setConnectionState('disconnected')
        setFramesSent(0)
        framesSentRef.current = 0
        pendingQueryRef.current = null

        if (captureInterval.current) {
            clearInterval(captureInterval.current)
            captureInterval.current = null
        }
        if (overlayTimeout.current) clearTimeout(overlayTimeout.current)
        if (videoRef.current) {
            videoRef.current.pause()
            videoRef.current.src = ''
        }
        wsRef.current?.close()
        wsRef.current = null
        onVideoReady?.(null) // notify parent video was cleared
    }

    const togglePause = () => {
        if (!videoRef.current) return
        if (isPaused) {
            videoRef.current.play()
            setIsPaused(false)
        } else {
            videoRef.current.pause()
            setIsPaused(true)
        }
    }

    useEffect(() => {
        const handleStreamingQuery = (event) => {
            const text = event.detail?.text?.trim()
            if (!text) return
            pendingQueryRef.current = text
            if (wsRef.current?.readyState === WebSocket.OPEN && framesSentRef.current >= 2) {
                wsRef.current.send(JSON.stringify({ type: 'query', text }))
                pendingQueryRef.current = null
                return
            }
            if (!isStreaming && videoRef.current && videoFile && videoReady) {
                startStreaming()
                return
            }
            if (!videoFile || !videoReady) {
                window.dispatchEvent(new CustomEvent('pitchai:qa_answer', {
                    detail: {
                        type: 'answer',
                        text: 'Upload match footage first, then ask me about what is happening in the video.',
                        source: 'system',
                    },
                }))
            }
        }

        window.addEventListener('pitchai:streaming_query', handleStreamingQuery)
        return () => window.removeEventListener('pitchai:streaming_query', handleStreamingQuery)
    }, [isStreaming, videoFile, videoReady, startStreaming])

    useEffect(() => {
        return () => {
            if (captureInterval.current) clearInterval(captureInterval.current)
            if (overlayTimeout.current) clearTimeout(overlayTimeout.current)
            if (videoRef.current?.src) URL.revokeObjectURL(videoRef.current.src)
            wsRef.current?.close()
        }
    }, [])

    const formatTime = (seconds) => {
        const mins = Math.floor(seconds / 60)
        const secs = Math.floor(seconds % 60)
        return `${mins}:${secs.toString().padStart(2, '0')}`
    }

    // Render SVG overlays
    const renderOverlays = () => {
        if (!currentDetection || !overlayVisible) return null

        const { tactical_label, confidence, players = [], ball = null } = currentDetection
        const opacity = overlayVisible ? 1 : 0

        // Icon mapping for tactical labels
        const ICON_MAP = {
            'Goal': '⚽',
            'High Press': '⬆️',
            'Low Block': '🛡️',
            'Counter Attack': '⚡',
            'Build-Up Play': '🔄',
            'Set Piece': '🎯',
            'Transition': '↔️',
            'Normal Play': '⚽',
        }

        return (
            <svg
                className="overlay-svg"
                viewBox="0 0 100 100"
                style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: '100%',
                    pointerEvents: 'none',
                    opacity,
                    transition: 'opacity 200ms ease-in-out',
                }}
            >
                {/* Tactical label badge */}
                <g transform="translate(5, 5)">
                    <rect
                        x="0"
                        y="0"
                        width="25"
                        height="8"
                        rx="2"
                        fill="var(--bg-surface-container)"
                        stroke="var(--border-dim)"
                        strokeWidth="0.5"
                    />
                    <text
                        x="2"
                        y="5.5"
                        fontSize="4"
                        fill="var(--text-primary)"
                        fontFamily="Inter, sans-serif"
                        fontWeight="600"
                    >
                        {ICON_MAP[tactical_label] || '⚽'} {tactical_label}
                    </text>
                </g>

                {/* Player dots - home team */}
                {players.filter(p => p.team === 'home').map((player, i) => (
                    <circle
                        key={`home-${i}`}
                        cx={player.x * 100}
                        cy={player.y * 100}
                        r="2"
                        fill="var(--accent-interactive)"
                        stroke="white"
                        strokeWidth="0.5"
                    />
                ))}

                {/* Player dots - away team */}
                {players.filter(p => p.team === 'away').map((player, i) => (
                    <circle
                        key={`away-${i}`}
                        cx={player.x * 100}
                        cy={player.y * 100}
                        r="2"
                        fill="var(--danger)"
                        stroke="white"
                        strokeWidth="0.5"
                    />
                ))}

                {/* Ball position */}
                {ball && (
                    <circle
                        cx={ball.x * 100}
                        cy={ball.y * 100}
                        r="1.5"
                        fill="white"
                        opacity="0.9"
                    />
                )}
            </svg>
        )
    }

    // Connection state indicator
    const renderConnectionIndicator = () => {
        if (!videoFile || !isStreaming) return null

        const stateConfig = {
            connected: { color: 'var(--success)', label: 'Live', pulse: true },
            reconnecting: { color: 'var(--warning)', label: 'Reconnecting...', pulse: true },
            disconnected: { color: 'var(--danger)', label: 'Analysis stopped', pulse: false },
        }

        const config = stateConfig[connectionState] || stateConfig.disconnected

        return (
            <div
                className="connection-indicator"
                style={{
                    position: 'absolute',
                    top: 12,
                    right: 12,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '6px 10px',
                    background: 'var(--bg-surface-container)',
                    borderRadius: 20,
                    fontSize: 11,
                    color: 'var(--text-primary)',
                    zIndex: 20,
                    cursor: 'default',
                }}
                title={`${config.label} • ${backend.toUpperCase()}`}
            >
                <div
                    style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: config.color,
                        animation: config.pulse ? 'pulse 1.5s infinite' : 'none',
                    }}
                />
                <span style={{ fontWeight: 500 }}>{config.label}</span>
            </div>
        )
    }

    return (
        <div className="video-canvas" style={{
            position: 'relative',
            width: '100%',
            height: '100%',
            background: 'var(--bg-secondary)',
            borderRadius: 12,
            overflow: 'hidden',
            border: '1px solid var(--border)',
        }}>
            {/* Header */}
            <div style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                padding: '10px 16px',
                background: 'linear-gradient(180deg, var(--bg-secondary) 0%, transparent 100%)',
                zIndex: 10,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
            }}>
                <div>
                    <h3 style={{ margin: 0, fontSize: 14, color: 'var(--text-primary)' }}>
                        {homeTeam} vs {awayTeam}
                    </h3>
                    <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                        Fan Lens • {sport}
                    </span>
                </div>
                {framesSent > 0 && (
                    <span style={{
                        background: 'var(--accent-interactive-focus)',
                        color: 'var(--accent-interactive)',
                        padding: '2px 8px',
                        borderRadius: 12,
                        fontSize: 10,
                    }}>
                        {framesSent} frames
                    </span>
                )}
            </div>

            {/* Connection indicator */}
            {renderConnectionIndicator()}

            {/* Video + Canvas layer — fills full canvas height */}
            <div style={{ position: 'absolute', inset: 0, background: 'var(--bg-primary)' }}>
                <video
                    ref={videoRef}
                    onTimeUpdate={() => videoRef.current && setCurrentTime(videoRef.current.currentTime)}
                    onEnded={stopStreaming}
                    onLoadedData={() => {
                        setVideoReady(true)
                        if (videoRef.current) setDuration(videoRef.current.duration || 0)
                        // Auto-play as soon as video data is ready
                        videoRef.current?.play().catch(() => {})
                    }}
                    style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width: '100%',
                        height: '100%',
                        objectFit: 'contain',
                    }}
                />
                <canvas
                    ref={canvasRef}
                    style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width: '100%',
                        height: '100%',
                        opacity: isStreaming ? 1 : 0,
                        transition: 'opacity 300ms',
                    }}
                />
                {/* SVG Overlays */}
                {renderOverlays()}
            </div>

            {/* Trivia Card */}
            {triviaCard && (
                <div
                    className="trivia-card"
                    style={{
                        position: 'absolute',
                        bottom: 80,
                        left: '50%',
                        transform: 'translateX(-50%)',
                        width: 'min(90%, 400px)',
                        background: 'var(--bg-surface-container)',
                        borderRadius: 12,
                        padding: 16,
                        border: '1px solid var(--border-dim)',
                        boxShadow: '0 10px 40px rgba(0,0,0,0.4)',
                        zIndex: 30,
                        animation: `slideUp ${triviaCard.fadeInMs}ms ease-out`,
                    }}
                >
                    <div style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5 }}>
                        {triviaCard.text}
                    </div>
                    {triviaCard.source && (
                        <div style={{
                            marginTop: 8,
                            fontSize: 10,
                            color: 'var(--text-secondary)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 4,
                        }}>
                            <span style={{
                                background: 'var(--accent-interactive-focus)',
                                padding: '1px 6px',
                                borderRadius: 4,
                                color: 'var(--accent-interactive)',
                            }}>
                                {triviaCard.source}
                            </span>
                            {triviaCard.confidence >= 0.8 && (
                                <span>• High confidence</span>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* Controls */}
            {!videoFile ? (
                /* No video loaded — show centred drop zone */
                <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 5 }}>
                    <label style={{
                        border: '2px dashed var(--border)',
                        borderRadius: 10,
                        padding: '32px 48px',
                        textAlign: 'center',
                        cursor: 'pointer',
                        transition: 'border-color 200ms',
                        background: 'rgba(0,0,0,0.6)',
                    }}
                    onMouseOver={(e) => e.currentTarget.style.borderColor = 'var(--accent-interactive)'}
                    onMouseOut={(e) => e.currentTarget.style.borderColor = 'var(--border)'}
                    >
                        <input
                            type="file"
                            accept="video/*"
                            onChange={handleVideoSelect}
                            style={{ display: 'none' }}
                        />
                        <span style={{ fontSize: 40 }}>📹</span>
                        <div style={{ marginTop: 8, color: 'var(--text-muted)', fontSize: 14 }}>Upload match footage</div>
                    </label>
                </div>
            ) : videoReady && !isStreaming ? (
                /* Video ready — compact overlay away from the Ask AI tray */
                <div style={{
                    position: 'absolute', top: 16, left: 16, zIndex: 5,
                    maxWidth: 'min(520px, calc(100% - 32px))',
                    padding: '10px 12px',
                    borderRadius: 12,
                    background: 'rgba(0,0,0,0.68)',
                    backdropFilter: 'blur(14px)',
                    WebkitBackdropFilter: 'blur(14px)',
                    border: '1px solid rgba(255,255,255,0.12)',
                    display: 'flex', alignItems: 'center', gap: 8,
                }}>
                    <span style={{ flex: 1, fontSize: 12, color: 'rgba(255,255,255,0.7)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {videoFile?.name}
                    </span>
                    <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => {
                            setVideoFile(null)
                            setVideoReady(false)
                            if (videoRef.current) videoRef.current.src = ''
                            onVideoReady?.(null)
                        }}
                        style={{ padding: '4px 10px', fontSize: 12 }}
                    >
                        Change
                    </button>
                    <button
                        className="btn btn-primary btn-sm"
                        onClick={startStreaming}
                        style={{ padding: '4px 10px', fontSize: 12 }}
                    >
                        {startLabel}
                    </button>
                </div>
            ) : isStreaming ? (
                /* Streaming — keep playback controls away from the Ask AI tray */
                <div style={{
                    position: 'absolute', top: 16, left: 16, right: 16, zIndex: 5,
                    padding: '10px 12px',
                    borderRadius: 12,
                    background: 'rgba(0,0,0,0.68)',
                    backdropFilter: 'blur(14px)',
                    WebkitBackdropFilter: 'blur(14px)',
                    border: '1px solid rgba(255,255,255,0.12)',
                }}>
                    {/* Progress bar */}
                    <div style={{
                        display: 'flex',
                        gap: 8,
                        alignItems: 'center',
                        marginBottom: 8,
                    }}>
                        <button
                            className="btn btn-secondary btn-sm"
                            onClick={togglePause}
                            style={{ padding: '4px 8px', fontSize: 12 }}
                        >
                            {isPaused ? '▶️' : '⏸️'}
                        </button>
                        <div style={{
                            flex: 1,
                            height: 4,
                            background: 'var(--border-color, #334155)',
                            borderRadius: 2,
                            overflow: 'hidden',
                        }}>
                            <div style={{
                                height: '100%',
                                width: `${duration ? (currentTime / duration) * 100 : 0}%`,
                                background: 'var(--accent, #3b82f6)',
                                transition: 'width 0.1s linear',
                            }}
                            />
                        </div>
                        <span style={{ fontSize: 11, color: 'var(--text-muted, #94a3b8)' }}>
                            {formatTime(currentTime)} / {formatTime(duration)}
                        </span>
                        <button
                            className="btn btn-danger btn-sm"
                            onClick={stopStreaming}
                            style={{ padding: '4px 8px', fontSize: 12 }}
                        >
                            ⏹️
                        </button>
                    </div>
                </div>
            ) : null}

            {/* Backend config (only when not streaming) */}
            {!isStreaming && (
                <div style={{
                    padding: '0 16px 16px',
                    display: 'flex',
                    gap: 12,
                    flexWrap: 'wrap',
                }}>
                    <div>
                        <label style={{ fontSize: 10, color: 'var(--text-muted)' }}>Backend</label>
                        <select
                            value={backend}
                            onChange={e => setBackend(e.target.value)}
                            style={{
                                display: 'block',
                                padding: '4px 8px',
                                borderRadius: 6,
                                border: '1px solid var(--border)',
                                background: 'var(--bg-primary)',
                                color: 'var(--text-primary)',
                                fontSize: 11,
                            }}
                        >
                            <option value="vllm">vLLM</option>
                            <option value="streaming_vlm">StreamingVLM</option>
                        </select>
                    </div>
                    <div>
                        <label style={{ fontSize: 10, color: 'var(--text-muted)' }}>Chunk (s)</label>
                        <input
                            type="number"
                            value={chunkInterval}
                            onChange={e => setChunkInterval(Number(e.target.value))}
                            min={1}
                            max={30}
                            style={{
                                width: 60,
                                padding: '4px 8px',
                                borderRadius: 6,
                                border: '1px solid var(--border)',
                                background: 'var(--bg-primary)',
                                color: 'var(--text-primary)',
                                fontSize: 11,
                            }}
                        />
                    </div>
                    <div>
                        <label style={{ fontSize: 10, color: 'var(--text-muted)' }}>FPS</label>
                        <input
                            type="number"
                            value={targetFps}
                            onChange={e => setTargetFps(Number(e.target.value))}
                            min={1}
                            max={30}
                            style={{
                                width: 60,
                                padding: '4px 8px',
                                borderRadius: 6,
                                border: '1px solid var(--border)',
                                background: 'var(--bg-primary)',
                                color: 'var(--text-primary)',
                                fontSize: 11,
                            }}
                        />
                    </div>
                </div>
            )}

            {/* CSS Animations */}
            <style>{`
                @keyframes pulse {
                    0%, 100% { opacity: 1; transform: scale(1); }
                    50% { opacity: 0.5; transform: scale(1.1); }
                }
                @keyframes slideUp {
                    from { opacity: 0; transform: translate(-50%, 20px); }
                    to { opacity: 1; transform: translate(-50%, 0); }
                }
            `}</style>
        </div>
    )
}
