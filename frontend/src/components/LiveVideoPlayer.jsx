import { useState, useRef, useEffect, useCallback } from 'react'

const BACKEND = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

/* ── LiveVideoPlayer — Chunked Video Streaming ─────────────────────────────── */
export default function LiveVideoPlayer({ matchSession, onChunkAnalyzed, onCommentary }) {
    const [isStreaming, setIsStreaming] = useState(false)
    const [isPaused, setIsPaused] = useState(false)
    const [videoFile, setVideoFile] = useState(null)
    const [currentTime, setCurrentTime] = useState(0)
    const [duration, setDuration] = useState(0)
    const [framesSent, setFramesSent] = useState(0)
    const [videoReady, setVideoReady] = useState(false)
    const [wsReady, setWsReady] = useState(false)
    const [chunkInterval] = useState(10) // seconds
    const wsRef = useRef(null)
    const videoRef = useRef(null)
    const canvasRef = useRef(null)
    const frameCaptureInterval = useRef(null)
    const chunkBuffer = useRef([])

    // Connect to WebSocket for chunked streaming
    const connectWebSocket = useCallback(() => {
        const wsUrl = BACKEND.replace(/^http/, 'ws') + '/ws/video/stream'
        const ws = new WebSocket(wsUrl)
        wsRef.current = ws

        ws.onopen = () => {
            console.log('WebSocket connected')
            // Send init message
            ws.send(JSON.stringify({
                type: 'init',
                match_session: matchSession,
                config: {
                    chunk_interval_seconds: chunkInterval,
                    max_chunk_frames: 12,
                    quality: 'medium'
                }
            }))
        }

        ws.onmessage = (e) => {
            if (typeof e.data === 'string') {
                try {
                    const msg = JSON.parse(e.data)
                    console.log('WS message:', msg.type)
                    if (msg.type === 'ready') {
                        setWsReady(true)
                        console.log('Video streaming ready')
                    } else if (msg.type === 'chunk_analyzed') {
                        onChunkAnalyzed?.(msg.result)
                    } else if (msg.type === 'commentary') {
                        onCommentary?.(msg)
                    } else if (msg.type === 'error') {
                        console.error('Streaming error:', msg.message)
                    }
                } catch (err) {
                    console.warn('Failed to parse WS message:', err)
                }
            }
        }

        ws.onerror = (err) => {
            console.error('WebSocket error:', err)
            setIsStreaming(false)
            setWsReady(false)
        }

        ws.onclose = () => {
            console.log('WebSocket closed')
            wsRef.current = null
            setWsReady(false)
        }
    }, [matchSession, chunkInterval, onChunkAnalyzed, onCommentary])

    // Handle video file selection
    const handleVideoSelect = (e) => {
        const file = e.target.files?.[0]
        if (!file) return

        console.log('Video selected:', file.name)
        setVideoFile(file)
        setVideoReady(false)

        const url = URL.createObjectURL(file)
        if (videoRef.current) {
            videoRef.current.src = url
            videoRef.current.load()
        }
    }

    // Start streaming
    const startStreaming = () => {
        if (!videoRef.current || !videoFile) {
            console.error('No video ready')
            return
        }

        console.log('Starting streaming...')
        connectWebSocket()
        setIsStreaming(true)
        setIsPaused(false)

        // Wait for video to be ready and playing
        videoRef.current.play().then(() => {
            console.log('Video started playing')
        }).catch(err => {
            console.error('Video play error:', err)
        })

        // Start frame capture at 1 FPS (1 frame per second for 10-second chunks)
        frameCaptureInterval.current = setInterval(captureFrame, 1000)
    }

    // Stop streaming
    const stopStreaming = () => {
        console.log('Stopping streaming...')
        setIsStreaming(false)
        setIsPaused(false)
        setWsReady(false)
        setVideoReady(false)

        if (frameCaptureInterval.current) {
            clearInterval(frameCaptureInterval.current)
            frameCaptureInterval.current = null
        }

        if (videoRef.current) {
            videoRef.current.pause()
        }

        wsRef.current?.close()
        wsRef.current = null
        chunkBuffer.current = []
    }

    // Capture frame from video
    const captureFrame = () => {
        if (!videoRef.current || !canvasRef.current || isPaused || !videoReady) {
            return
        }

        const video = videoRef.current
        const canvas = canvasRef.current
        const ctx = canvas.getContext('2d')

        // Check if video has valid dimensions
        if (!video.videoWidth || !video.videoHeight) {
            console.warn('Video dimensions not ready')
            return
        }

        // Set canvas size to match video (scaled down for performance)
        const scale = 0.5 // Scale down to 50%
        canvas.width = Math.floor(video.videoWidth * scale)
        canvas.height = Math.floor(video.videoHeight * scale)

        try {
            // Draw current frame
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

            // Convert to base64
            const frame_b64 = canvas.toDataURL('image/jpeg', 0.7).split(',')[1]
            const timestamp_ms = Math.floor(video.currentTime * 1000)

            // Add to chunk buffer
            chunkBuffer.current.push({ frame_b64, timestamp_ms })
            setFramesSent(prev => prev + 1)

            // Send chunk when buffer is full (12 frames = ~12 seconds at 1fps)
            if (chunkBuffer.current.length >= 12) {
                sendChunk()
            }

            // Update current time
            setCurrentTime(video.currentTime)
        } catch (err) {
            console.error('Frame capture error:', err)
        }
    }

    // Send chunk to server
    const sendChunk = () => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            console.warn('WebSocket not ready, clearing buffer')
            chunkBuffer.current = []
            return
        }
        if (chunkBuffer.current.length === 0) return

        console.log('Sending chunk:', chunkBuffer.current.length, 'frames')

        const frames = chunkBuffer.current.map(item => item.frame_b64)
        const timestamps = chunkBuffer.current.map(item => item.timestamp_ms)

        wsRef.current.send(JSON.stringify({
            type: 'chunk',
            frames_b64: frames,
            timestamps_ms: timestamps
        }))

        chunkBuffer.current = []
    }

    // Handle video time update
    const handleTimeUpdate = () => {
        if (videoRef.current) {
            setCurrentTime(videoRef.current.currentTime)
            setDuration(videoRef.current.duration || 0)
        }
    }

    // Handle video loaded
    const handleVideoLoaded = () => {
        console.log('Video loaded:', videoRef.current?.videoWidth, 'x', videoRef.current?.videoHeight)
        setVideoReady(true)
    }

    // Handle video end
    const handleVideoEnded = () => {
        console.log('Video ended, sending final chunk')
        sendChunk()
        stopStreaming()
    }

    // Toggle pause
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

    // Seek video
    const handleSeek = (e) => {
        const time = parseFloat(e.target.value)
        if (videoRef.current) {
            videoRef.current.currentTime = time
            setCurrentTime(time)
        }
    }

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            stopStreaming()
            if (videoRef.current?.src) {
                URL.revokeObjectURL(videoRef.current.src)
            }
        }
    }, [])

    // Format time display
    const formatTime = (seconds) => {
        const mins = Math.floor(seconds / 60)
        const secs = Math.floor(seconds % 60)
        return `${mins}:${secs.toString().padStart(2, '0')}`
    }

    return (
        <div className="live-video-player">
            {/* Hidden video element for processing */}
            <video
                ref={videoRef}
                onTimeUpdate={handleTimeUpdate}
                onEnded={handleVideoEnded}
                onLoadedData={handleVideoLoaded}
                style={{ display: 'none' }}
            />

            {/* Hidden canvas for frame capture */}
            <canvas ref={canvasRef} style={{ display: 'none' }} />

            {/* Video File Input */}
            {!isStreaming && (
                <div className="video-upload-section">
                    <label className="video-upload-label">
                        <input
                            type="file"
                            accept="video/*"
                            onChange={handleVideoSelect}
                            className="video-upload-input"
                        />
                        <div className="video-upload-placeholder">
                            <span className="upload-icon">📹</span>
                            <span className="upload-text">
                                {videoFile ? videoFile.name : 'Upload match video to start live commentary'}
                            </span>
                        </div>
                    </label>

                    {videoFile && (
                        <button
                            className="btn btn-primary start-streaming-btn"
                            onClick={startStreaming}
                            disabled={!videoReady}
                        >
                            <span>🔴</span>
                            {videoReady ? 'Start Live Commentary' : 'Loading video...'}
                        </button>
                    )}
                </div>
            )}

            {/* Streaming Controls */}
            {isStreaming && (
                <>
                    <div className="video-controls">
                        <button
                            className="btn btn-secondary btn-sm"
                            onClick={togglePause}
                        >
                            {isPaused ? '▶️ Play' : '⏸️ Pause'}
                        </button>

                        <div className="time-display">
                            <span>{formatTime(currentTime)}</span>
                            <span>/</span>
                            <span>{formatTime(duration)}</span>
                        </div>

                        <button
                            className="btn btn-danger btn-sm"
                            onClick={stopStreaming}
                        >
                            ⏹️ Stop
                        </button>
                    </div>

                    {/* Progress Bar */}
                    <div className="video-progress">
                        <input
                            type="range"
                            min="0"
                            max={duration || 100}
                            value={currentTime}
                            onChange={handleSeek}
                            className="progress-slider"
                        />
                    </div>

                    {/* Streaming Status */}
                    <div className="streaming-status">
                        <div className={`status-indicator ${isStreaming && wsReady ? 'streaming' : ''}`}>
                            <div className="pulse-dot" />
                        </div>
                        <span className="status-text">
                            {isPaused ? 'Paused' : wsReady ? 'Live' : 'Connecting...'} • {framesSent} frames sent
                        </span>
                        <span className="chunk-info">
                            Buffer: {chunkBuffer.current.length}/12 frames
                        </span>
                    </div>
                </>
            )}
        </div>
    )
}
