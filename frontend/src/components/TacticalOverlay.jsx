import { useEffect, useRef, useState } from 'react'

const BACKEND = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

const ICON_MAP = {
    'High Press': '⬆️',
    'Low Block': '🛡️',
    'Counter Attack': '⚡',
    'Build-Up Play': '🔄',
    'Set Piece': '🎯',
    'Transition': '↔️',
    'Normal Play': '⚽',
    'Attacking Field': '🏏',
    'Defensive Field': '🛡️',
    'Spin Attack': '🌀',
    'Pace Attack': '💨',
}

/* Soccer pitch SVG with dynamic formation dots */
function SoccerPitch({ detection }) {
    return (
        <svg className="pitch-svg" viewBox="0 0 400 280" xmlns="http://www.w3.org/2000/svg">
            {/* Pitch lines */}
            <rect x="10" y="10" width="380" height="260" fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="2" rx="4" />
            {/* Centre circle */}
            <circle cx="200" cy="140" r="40" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="1.5" />
            <line x1="200" y1="10" x2="200" y2="270" stroke="rgba(255,255,255,0.2)" strokeWidth="1.5" />
            <circle cx="200" cy="140" r="3" fill="rgba(255,255,255,0.4)" />
            {/* Penalty areas */}
            <rect x="10" y="80" width="80" height="120" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="1.5" />
            <rect x="310" y="80" width="80" height="120" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="1.5" />
            {/* Goals */}
            <rect x="10" y="110" width="18" height="60" fill="rgba(255,255,255,0.08)" stroke="rgba(255,255,255,0.3)" strokeWidth="1.5" />
            <rect x="372" y="110" width="18" height="60" fill="rgba(255,255,255,0.08)" stroke="rgba(255,255,255,0.3)" strokeWidth="1.5" />

            {/* Formation dots — home team (blue) 4-3-3 */}
            {[
                [50, 140],  // GK
                [100, 50], [100, 110], [100, 170], [100, 230], // DEF x4
                [150, 80], [150, 140], [150, 200],  // MID x3
                [210, 80], [210, 140], [210, 200],  // FWD x3
            ].map(([cx, cy], i) => (
                <circle key={`h${i}`} cx={cx} cy={cy} r="7" fill="rgba(79,156,249,0.85)" stroke="white" strokeWidth="1.5" />
            ))}

            {/* Formation dots — away team (red) 4-2-3-1 */}
            {[
                [350, 140],  // GK
                [300, 50], [300, 110], [300, 170], [300, 230], // DEF x4
                [260, 100], [260, 180], // CDM x2
                [220, 60], [220, 140], [220, 220], // CAM x3
                [180, 140],  // ST x1
            ].map(([cx, cy], i) => (
                <circle key={`a${i}`} cx={cx} cy={cy} r="7" fill="rgba(248,113,113,0.85)" stroke="white" strokeWidth="1.5" />
            ))}

            {/* Ball */}
            <circle cx="200" cy="140" r="5" fill="white" opacity="0.9" />
        </svg>
    )
}

export default function TacticalOverlay({ sport, detection, setDetection }) {
    const [loading, setLoading] = useState(false)
    const [previewUrl, setPreviewUrl] = useState(null)
    const [previewType, setPreviewType] = useState('image')
    const [analysisSource, setAnalysisSource] = useState('frame')
    const [errorMessage, setErrorMessage] = useState('')
    const imageInputRef = useRef()
    const videoInputRef = useRef()
    const objectUrlRef = useRef(null)

    useEffect(() => {
        return () => {
            if (objectUrlRef.current) {
                URL.revokeObjectURL(objectUrlRef.current)
            }
        }
    }, [])

    const resetPreviewUrl = (nextUrl = null, type = 'image', revokeExisting = false) => {
        if (revokeExisting && objectUrlRef.current) {
            URL.revokeObjectURL(objectUrlRef.current)
            objectUrlRef.current = null
        }
        setPreviewType(type)
        setPreviewUrl(nextUrl)
    }

    const analyzeFrameB64 = async (frameB64, timestamp = null) => {
        const res = await fetch(`${BACKEND}/api/v1/frame/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ frame_b64: frameB64, sport, timestamp }),
        })

        const data = await res.json()
        if (data.status !== 'success') {
            throw new Error(data.detail || data.error || 'Frame analysis failed')
        }

        setDetection(data.analysis)
    }

    const handleImageChange = async (e) => {
        const file = e.target.files[0]
        if (!file) return

        setLoading(true)
        setErrorMessage('')
        setAnalysisSource('frame')

        const reader = new FileReader()
        reader.onload = async (ev) => {
            const dataUrl = ev.target.result
            resetPreviewUrl(dataUrl, 'image', true)
            const b64 = dataUrl.split(',')[1]
            try {
                await analyzeFrameB64(b64)
            } catch (err) {
                console.error('Frame analysis failed', err)
                setErrorMessage(err.message || 'Frame analysis failed')
            } finally {
                setLoading(false)
                if (imageInputRef.current) {
                    imageInputRef.current.value = ''
                }
            }
        }
        reader.readAsDataURL(file)
    }

    const extractFrameFromVideo = (file) => new Promise((resolve, reject) => {
        const videoUrl = URL.createObjectURL(file)
        const video = document.createElement('video')
        video.preload = 'metadata'
        video.muted = true
        video.playsInline = true
        video.src = videoUrl

        const fail = (message) => {
            URL.revokeObjectURL(videoUrl)
            reject(new Error(message))
        }

        video.onerror = () => fail('Could not read the selected video')

        video.onloadedmetadata = () => {
            const duration = Number.isFinite(video.duration) && video.duration > 0 ? video.duration : 0
            const captureTime = duration > 0 ? Math.min(Math.max(duration * 0.25, 0.1), Math.max(duration - 0.1, 0.1)) : 0
            video.currentTime = captureTime
        }

        video.onseeked = () => {
            try {
                const canvas = document.createElement('canvas')
                canvas.width = video.videoWidth || 1280
                canvas.height = video.videoHeight || 720
                const context = canvas.getContext('2d')
                if (!context) {
                    fail('Could not create a frame preview from this video')
                    return
                }

                context.drawImage(video, 0, 0, canvas.width, canvas.height)
                const frameDataUrl = canvas.toDataURL('image/jpeg', 0.9)
                resolve({
                    frameDataUrl,
                    videoUrl,
                    timestampMs: Math.round((video.currentTime || 0) * 1000),
                })
            } catch (err) {
                fail(err.message || 'Video frame extraction failed')
            }
        }
    })

    const handleVideoChange = async (e) => {
        const file = e.target.files[0]
        if (!file) return

        setLoading(true)
        setErrorMessage('')
        setAnalysisSource('video')

        try {
            const { frameDataUrl, videoUrl, timestampMs } = await extractFrameFromVideo(file)
            if (objectUrlRef.current) {
                URL.revokeObjectURL(objectUrlRef.current)
            }
            objectUrlRef.current = videoUrl
            resetPreviewUrl(videoUrl, 'video')
            await analyzeFrameB64(frameDataUrl.split(',')[1], timestampMs)
        } catch (err) {
            console.error('Video analysis failed', err)
            setErrorMessage(err.message || 'Video analysis failed')
        } finally {
            setLoading(false)
            if (videoInputRef.current) {
                videoInputRef.current.value = ''
            }
        }
    }

    return (
        <div className="tactical-section" style={{ flexDirection: 'column', alignItems: 'center', width: '100%', gap: '1.5rem' }}>
            <div className="pitch-container" style={{ width: '100%', position: 'relative' }}>
                {previewUrl ? (
                    previewType === 'video' ? (
                        <video
                            src={previewUrl}
                            controls
                            muted
                            playsInline
                            style={{ width: '100%', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.2)', objectFit: 'contain' }}
                        />
                    ) : (
                        <img src={previewUrl} alt="Uploaded Frame" style={{ width: '100%', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.2)', objectFit: 'contain' }} />
                    )
                ) : (
                    <SoccerPitch detection={detection} />
                )}
                {detection && (
                    <div className="tactical-label-badge" style={{ position: 'absolute', top: 16, left: 16, zIndex: 10 }}>
                        {ICON_MAP[detection.tactical_label] || '⚽'} {detection.tactical_label}
                    </div>
                )}
            </div>

            <div className="tactical-controls" style={{ width: '100%' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    <button
                        className="upload-frame-btn"
                        onClick={() => imageInputRef.current.click()}
                        disabled={loading}
                        style={{ width: '100%', padding: '14px', fontSize: '1rem', fontWeight: 600 }}
                    >
                        {loading && analysisSource === 'frame'
                            ? <><span className="spinner" /> Analyzing Frame...</>
                            : <>📸 Upload Frame</>
                        }
                    </button>
                    <button
                        className="upload-frame-btn"
                        onClick={() => videoInputRef.current.click()}
                        disabled={loading}
                        style={{ width: '100%', padding: '14px', fontSize: '1rem', fontWeight: 600 }}
                    >
                        {loading && analysisSource === 'video'
                            ? <><span className="spinner" /> Extracting Video Frame...</>
                            : <>🎬 Upload Short Video</>
                        }
                    </button>
                </div>
                <div style={{ marginTop: 10, color: 'var(--text-secondary)', fontSize: 12 }}>
                    Video uploads extract one representative frame in-browser and send that frame for analysis.
                </div>
                {errorMessage && (
                    <div style={{ marginTop: 10, color: 'var(--accent-red)', fontSize: 12 }}>
                        {errorMessage}
                    </div>
                )}
                <input
                    ref={imageInputRef}
                    type="file"
                    accept="image/*"
                    style={{ display: 'none' }}
                    onChange={handleImageChange}
                />
                <input
                    ref={videoInputRef}
                    type="file"
                    accept="video/*"
                    style={{ display: 'none' }}
                    onChange={handleVideoChange}
                />
            </div>
        </div>
    )
}
