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
                const msg = JSON.parse(e.data)
                if (msg.type === 'ready') {
                    console.log('Video streaming ready')
                } else if (msg.type === 'chunk_analyzed') {
                    onChunkAnalyzed?.(msg.result)
                } else if (msg.type === 'commentary') {
                    onCommentary?.(msg)
                } else if (msg.type === 'error') {
                    console.error('Streaming error:', msg.message)
                }
            }
        }

        ws.onerror = (err) => {
            console.error('WebSocket error:', err)
            setIsStreaming(false)
        }

        ws.onclose = () => {
            console.log('WebSocket closed')
            wsRef.current = null
        }
    }, [matchSession, chunkInterval, onChunkAnalyzed, onCommentary])

    // Handle video file selection
    const handleVideoSelect = (e) => {
        const file = e.target.files?.[0]
        if (!file) return

        setVideoFile(file)
        const url = URL.createObjectURL(file)
        if (videoRef.current) {
            videoRef.current.src = url
            videoRef.current.load()
        }
    }

    // Start streaming
    const startStreaming = () => {
        if (!videoRef.current || !videoFile) return

        connectWebSocket()
        setIsStreaming(true)
        setIsPaused(false)
        videoRef.current.play()

        // Start frame capture
        frameCaptureInterval.current = setInterval(captureFrame, 1000 / 3) // 30 FPS capture
    }

    // Stop streaming
    const stopStreaming = () => {
        setIsStreaming(false)
        setIsPaused(false)

        if (frameCaptureInterval.current) {
            clearInterval(frameCaptureInterval.current)
            frameCaptureInterval.current = null
        }

        if (videoRef.current) {
            videoRef.current.pause()
        }

        wsRef.current?.close()
        wsRef.current = null
    }

    // Capture frame from video
    const captureFrame = () => {
        if (!videoRef.current || !canvasRef.current || isPaused) return

        const video = videoRef.current
        const canvas = canvasRef.current
        const ctx = canvas.getContext('2d')

        // Set canvas size to match video
        canvas.width = video.videoWidth || 640
        canvas.height = video.videoHeight || 360

        // Draw current frame
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

        // Convert to base64
        const frame_b64 = canvas.toDataURL('image/jpeg', 0.7).split(',')[1]
        const timestamp_ms = Math.floor(video.currentTime * 1000)

        // Add to chunk buffer
        chunkBuffer.current.push({ frame_b64, timestamp_ms })
        setFramesSent(prev => prev + 1)

        // Send chunk when buffer is full (every ~10 seconds at 3fps = 30 frames)
        // But we'll send smaller chunks more frequently
        if (chunkBuffer.current.length >= 12) {
            sendChunk()
        }

        // Update current time
        setCurrentTime(video.currentTime)
    }

    // Send chunk to server
    const sendChunk = () => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
        if (chunkBuffer.current.length === 0) return

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

    // Handle video end
    const handleVideoEnded = () => {
        // Send final chunk
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
                        >
                            <span>🔴</span>
                            Start Live Commentary
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
                        <div className={`status-indicator ${isStreaming ? 'streaming' : ''}`}>
                            <div className="pulse-dot" />
                        </div>
                        <span className="status-text">
                            {isPaused ? 'Paused' : 'Live'} • {framesSent} frames sent
                        </span>
                        <span className="chunk-info">
                            Chunk size: {chunkBuffer.current.length}/12 frames
                        </span>
                    </div>
                </>
            )}
        </div>
    )
}
