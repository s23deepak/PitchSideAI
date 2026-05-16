import { useState, useRef, useEffect, useCallback } from 'react'
import { backendWsUrl } from '@/lib/backend-url'

/**
 * StreamingCommentary — Hackathon Track 3 component.
 *
 * Connects to /ws/video/streaming (StreamingVisionBridge backend)
 * for real-time continuous video understanding with KV-cache management.
 *
 * Supports two modes:
 * - "upload": Upload a video file, frames auto-captured and streamed
 * - "live": Connect to live camera feed (coming soon)
 */
export default function StreamingCommentary({
    matchSession = 'demo_match',
    homeTeam = 'Home',
    awayTeam = 'Away',
    onCommentary,
    onStats,
}) {
    const [isStreaming, setIsStreaming] = useState(false)
    const [isPaused, setIsPaused] = useState(false)
    const [videoFile, setVideoFile] = useState(null)
    const [currentTime, setCurrentTime] = useState(0)
    const [duration, setDuration] = useState(0)
    const [framesSent, setFramesSent] = useState(0)
    const [videoReady, setVideoReady] = useState(false)
    const [wsReady, setWsReady] = useState(false)
    const [backend, setBackend] = useState('vllm')
    const [chunkInterval, setChunkInterval] = useState(5) // seconds
    const [targetFps, setTargetFps] = useState(8)
    const [commentaryCount, setCommentaryCount] = useState(0)
    const [stats, setStats] = useState(null)

    const wsRef = useRef(null)
    const videoRef = useRef(null)
    const canvasRef = useRef(null)
    const captureInterval = useRef(null)

    // Connect to StreamingVisionBridge WebSocket
    const connectWebSocket = useCallback(() => {
        const wsUrl = backendWsUrl('/ws/video/streaming')
        const ws = new WebSocket(wsUrl)
        wsRef.current = ws

        ws.onopen = () => {
            ws.send(JSON.stringify({
                type: 'init',
                home_team: homeTeam,
                away_team: awayTeam,
                match_session: matchSession,
                sport: 'football',
                config: {
                    backend: backend,
                    chunk_interval_seconds: chunkInterval,
                    max_chunk_frames: Math.round(targetFps * chunkInterval),
                    target_fps: targetFps,
                }
            }))
        }

        ws.onmessage = (e) => {
            if (typeof e.data !== 'string') return
            try {
                const msg = JSON.parse(e.data)

                switch (msg.type) {
                    case 'ready':
                        setWsReady(true)
                        break

                    case 'commentary':
                        setCommentaryCount(c => c + 1)
                        onCommentary?.(msg)
                        break

                    case 'stats_update':
                        setStats(msg.stats)
                        onStats?.(msg.stats)
                        break

                    case 'error':
                        console.error('Streaming error:', msg.message)
                        break

                    case 'ping':
                        // Heartbeat — ignore
                        break
                }
            } catch (err) {
                console.warn('WS parse error:', err)
            }
        }

        ws.onerror = (err) => {
            console.error('WebSocket error:', err)
            setIsStreaming(false)
            setWsReady(false)
        }

        ws.onclose = () => {
            wsRef.current = null
            setWsReady(false)
        }
    }, [homeTeam, awayTeam, matchSession, backend, chunkInterval, targetFps, onCommentary, onStats])

    // Frame capture at target FPS
    const captureLoop = useCallback(() => {
        if (!videoRef.current || !canvasRef.current || isPaused || !videoReady) return

        const video = videoRef.current
        const canvas = canvasRef.current
        const ctx = canvas.getContext('2d')

        if (!video.videoWidth || !video.videoHeight) return

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
                    keyframe: framesSent % Math.round(targetFps) === 0,
                }))
                setFramesSent(f => f + 1)
            }
        } catch (err) {
            console.error('Frame capture error:', err)
        }
    }, [isPaused, videoReady, targetFps, framesSent])

    const handleVideoSelect = (e) => {
        const file = e.target.files?.[0]
        if (!file) return
        setVideoFile(file)
        setVideoReady(false)

        const url = URL.createObjectURL(file)
        if (videoRef.current) {
            videoRef.current.src = url
            videoRef.current.load()
        }
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

        if (captureInterval.current) {
            clearInterval(captureInterval.current)
            captureInterval.current = null
        }
        if (videoRef.current) videoRef.current.pause()
        wsRef.current?.close()
        wsRef.current = null
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
        return () => {
            if (captureInterval.current) clearInterval(captureInterval.current)
            if (videoRef.current?.src) URL.revokeObjectURL(videoRef.current.src)
            wsRef.current?.close()
        }
    }, [])

    const formatTime = (seconds) => {
        const mins = Math.floor(seconds / 60)
        const secs = Math.floor(seconds % 60)
        return `${mins}:${secs.toString().padStart(2, '0')}`
    }

    return (
        <div className="streaming-commentary" style={{
            background: 'var(--surface)',
            borderRadius: 12,
            padding: 16,
            border: '1px solid var(--border-color)',
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <div>
                    <h3 style={{ margin: 0, fontSize: 16 }}>Streaming Vision Commentary</h3>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        StreamingVLM-powered real-time analysis
                    </span>
                </div>
                {commentaryCount > 0 && (
                    <span style={{
                        background: 'var(--accent)',
                        color: '#fff',
                        padding: '2px 10px',
                        borderRadius: 12,
                        fontSize: 12,
                    }}>
                        {commentaryCount} commentaries
                    </span>
                )}
            </div>

            {/* Config */}
            {!isStreaming && (
                <div style={{ display: 'flex', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
                    <div>
                        <label style={{ fontSize: 11, color: 'var(--text-muted)' }}>Backend</label>
                        <select value={backend} onChange={e => setBackend(e.target.value)}
                            style={{ display: 'block', padding: '4px 8px', borderRadius: 6, border: '1px solid var(--border-color)', background: 'var(--bg)' }}>
                            <option value="vllm">vLLM (RTX 5060)</option>
                            <option value="streaming_vlm">StreamingVLM (MI300X)</option>
                        </select>
                    </div>
                    <div>
                        <label style={{ fontSize: 11, color: 'var(--text-muted)' }}>Chunk (s)</label>
                        <input type="number" value={chunkInterval} onChange={e => setChunkInterval(Number(e.target.value))}
                            min={1} max={30} style={{ width: 60, padding: '4px 8px', borderRadius: 6, border: '1px solid var(--border-color)', background: 'var(--bg)' }} />
                    </div>
                    <div>
                        <label style={{ fontSize: 11, color: 'var(--text-muted)' }}>Target FPS</label>
                        <input type="number" value={targetFps} onChange={e => setTargetFps(Number(e.target.value))}
                            min={1} max={30} style={{ width: 60, padding: '4px 8px', borderRadius: 6, border: '1px solid var(--border-color)', background: 'var(--bg)' }} />
                    </div>
                </div>
            )}

            {/* Hidden video + canvas */}
            <video ref={videoRef}
                onTimeUpdate={() => videoRef.current && setCurrentTime(videoRef.current.currentTime)}
                onEnded={stopStreaming}
                onLoadedData={() => { setVideoReady(true); if (videoRef.current) setDuration(videoRef.current.duration || 0) }}
                style={{ display: 'none' }} />
            <canvas ref={canvasRef} style={{ display: 'none' }} />

            {!isStreaming ? (
                <div>
                    <label style={{
                        display: 'block', border: '2px dashed var(--border-color)',
                        borderRadius: 10, padding: 24, textAlign: 'center', cursor: 'pointer',
                    }}>
                        <input type="file" accept="video/*" onChange={handleVideoSelect}
                            style={{ display: 'none' }} />
                        <span style={{ fontSize: 32 }}>📹</span>
                        <div style={{ marginTop: 8 }}>
                            {videoFile ? videoFile.name : 'Upload football footage'}
                        </div>
                    </label>
                    {videoFile && (
                        <button className="btn btn-primary"
                            onClick={startStreaming}
                            disabled={!videoReady}
                            style={{ marginTop: 12, width: '100%', padding: '10px 0' }}>
                            {videoReady ? 'Start Streaming Commentary' : 'Loading video...'}
                        </button>
                    )}
                </div>
            ) : (
                <div>
                    {/* Controls */}
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
                        <button className="btn btn-secondary btn-sm" onClick={togglePause}>
                            {isPaused ? '▶️' : '⏸️'}
                        </button>
                        <div style={{ flex: 1, height: 4, background: 'var(--border-color)', borderRadius: 2, overflow: 'hidden' }}>
                            <div style={{
                                height: '100%', width: `${duration ? (currentTime / duration) * 100 : 0}%`,
                                background: 'var(--accent)', transition: 'width 0.1s linear',
                            }} />
                        </div>
                        <span style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
                            {formatTime(currentTime)} / {formatTime(duration)}
                        </span>
                        <button className="btn btn-danger btn-sm" onClick={stopStreaming}>⏹️</button>
                    </div>

                    {/* Status bar */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, color: 'var(--text-muted)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <div style={{
                                width: 8, height: 8, borderRadius: '50%',
                                background: isStreaming && wsReady ? '#22c55e' : '#ef4444',
                                animation: isStreaming && wsReady ? 'pulse 1.5s infinite' : 'none',
                            }} />
                            {isPaused ? 'Paused' : wsReady ? 'LIVE' : 'Connecting...'}
                        </div>
                        <span>{framesSent} frames sent</span>
                        {stats?.backend && (
                            <span>via {stats.backend?.backend || backend}</span>
                        )}
                    </div>
                </div>
            )}
        </div>
    )
}
