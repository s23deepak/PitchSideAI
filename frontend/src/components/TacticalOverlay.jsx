import { useEffect, useRef, useState } from 'react'

const BACKEND = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'
const MIN_FALLBACK_VIDEO_SAMPLES = 8
const MAX_FALLBACK_FRAME_DIMENSION = 960
const FALLBACK_FRAME_QUALITY = 0.72
const THUMBNAIL_SIGNATURE_WIDTH = 48
const THUMBNAIL_SIGNATURE_HEIGHT = 27
const ADAPTIVE_PROBE_MIN_INTERVAL_SECONDS = 0.2
const ADAPTIVE_BASELINE_RATIO = 0.6
const ADAPTIVE_MIN_SPACING_RATIO = 0.5
const VIDEO_SAMPLING_PRESETS = {
    balanced: {
        label: 'Balanced',
        intervalSeconds: 0.75,
        maxFrames: 24,
        description: 'Good coverage with moderate upload size.',
    },
    'high-detail': {
        label: 'High Detail',
        intervalSeconds: 0.5,
        maxFrames: 36,
        description: 'Denser local fallback for tactical movement.',
    },
    'max-detail': {
        label: 'Max Detail',
        intervalSeconds: 0.33,
        maxFrames: 48,
        description: 'Most temporal detail, with heavier local uploads.',
    },
}
const VIDEO_SAMPLING_MODES = {
    uniform: {
        label: 'Uniform Coverage',
        description: 'Even spacing across the full clip.',
    },
    adaptive: {
        label: 'Transition Aware',
        description: 'Keeps full-clip coverage and adds more frames around visual changes.',
    },
}
const DEFAULT_VIDEO_SAMPLING_PRESET = VIDEO_SAMPLING_PRESETS[import.meta.env.VITE_FALLBACK_VIDEO_SAMPLING_PRESET]
    ? import.meta.env.VITE_FALLBACK_VIDEO_SAMPLING_PRESET
    : 'high-detail'
const DEFAULT_VIDEO_SAMPLING_MODE = VIDEO_SAMPLING_MODES[import.meta.env.VITE_FALLBACK_VIDEO_SAMPLING_MODE]
    ? import.meta.env.VITE_FALLBACK_VIDEO_SAMPLING_MODE
    : 'adaptive'

function uniqueSortedTimes(times) {
    const sorted = [...times].sort((left, right) => left - right)
    const unique = []

    for (const time of sorted) {
        if (!unique.length || Math.abs(unique[unique.length - 1] - time) > 0.05) {
            unique.push(time)
        }
    }

    return unique
}

function downsampleTimes(times, maxFrames) {
    const unique = uniqueSortedTimes(times)
    if (unique.length <= maxFrames) {
        return unique
    }

    const selected = []
    for (let index = 0; index < maxFrames; index += 1) {
        const position = Math.round((index * (unique.length - 1)) / (maxFrames - 1))
        selected.push(unique[position])
    }

    return uniqueSortedTimes(selected)
}

function buildUniformSampleTimes(duration, intervalSeconds, maxFrames) {
    if (!duration || duration <= 0) {
        return [0]
    }

    const startTime = duration > 0.2 ? 0.1 : 0
    const latestTime = Math.max(duration - 0.1, startTime)
    const times = [startTime]

    for (let time = startTime + intervalSeconds; time < latestTime; time += intervalSeconds) {
        times.push(time)
    }

    if (latestTime > startTime) {
        times.push(latestTime)
    }

    return downsampleTimes(times, Math.max(1, maxFrames))
}

function computeFrameDifference(leftSignature, rightSignature) {
    if (!leftSignature || !rightSignature || leftSignature.length !== rightSignature.length) {
        return 0
    }

    let totalDifference = 0
    for (let index = 0; index < leftSignature.length; index += 4) {
        totalDifference += Math.abs(leftSignature[index] - rightSignature[index])
        totalDifference += Math.abs(leftSignature[index + 1] - rightSignature[index + 1])
        totalDifference += Math.abs(leftSignature[index + 2] - rightSignature[index + 2])
    }

    return totalDifference / (leftSignature.length / 4)
}

function buildAdaptiveSampleTimes(duration, intervalSeconds, maxFrames, probeFrames) {
    const baselineCount = Math.max(
        MIN_FALLBACK_VIDEO_SAMPLES,
        Math.min(maxFrames, Math.ceil(maxFrames * ADAPTIVE_BASELINE_RATIO))
    )
    const baselineTimes = buildUniformSampleTimes(duration, intervalSeconds, baselineCount)
    const minSpacingSeconds = Math.max(ADAPTIVE_PROBE_MIN_INTERVAL_SECONDS, intervalSeconds * ADAPTIVE_MIN_SPACING_RATIO)
    const selectedTimes = [...baselineTimes]

    const scoredCandidates = []
    for (let index = 1; index < probeFrames.length; index += 1) {
        const score = computeFrameDifference(probeFrames[index - 1].signature, probeFrames[index].signature)
        scoredCandidates.push({
            timeSeconds: probeFrames[index].timeSeconds,
            score,
        })
    }

    scoredCandidates.sort((left, right) => right.score - left.score)

    for (const candidate of scoredCandidates) {
        if (selectedTimes.length >= maxFrames) {
            break
        }

        const hasSpacing = selectedTimes.every((time) => Math.abs(time - candidate.timeSeconds) >= minSpacingSeconds)
        if (hasSpacing) {
            selectedTimes.push(candidate.timeSeconds)
        }
    }

    return downsampleTimes(selectedTimes, maxFrames)
}

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

export default function TacticalOverlay({ sport, matchSession, detection, setDetection, sendMatchEvent, sendTacticalDetection }) {
    const [loading, setLoading] = useState(false)
    const [previewUrl, setPreviewUrl] = useState(null)
    const [previewType, setPreviewType] = useState('image')
    const [analysisSource, setAnalysisSource] = useState('frame')
    const [errorMessage, setErrorMessage] = useState('')
    const [videoSamplingPreset, setVideoSamplingPreset] = useState(DEFAULT_VIDEO_SAMPLING_PRESET)
    const [videoSamplingMode, setVideoSamplingMode] = useState(DEFAULT_VIDEO_SAMPLING_MODE)
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
            body: JSON.stringify({ frame_b64: frameB64, sport, timestamp, match_session: matchSession }),
        })

        const data = await res.json()
        if (data.status !== 'success') {
            throw new Error(data.detail || data.error || 'Frame analysis failed')
        }

        const detectionWithTimestamp = {
            ...data.analysis,
            timestamp_ms: data.timestamp ?? timestamp ?? null,
        }

        setDetection(detectionWithTimestamp)

        if (detectionWithTimestamp?.confidence > 0.6) {
            if (sendTacticalDetection) {
                await sendTacticalDetection(detectionWithTimestamp)
            } else if (sendMatchEvent && data.analysis?.actionable_insight) {
                await sendMatchEvent(data.analysis.actionable_insight)
            }
        }
    }

    const analyzeVideoFrames = async (frames) => {
        const readFileAsDataUrl = (file) => new Promise((resolve, reject) => {
            const reader = new FileReader()
            reader.onload = (event) => resolve(event.target?.result)
            reader.onerror = () => reject(new Error('Could not read the selected video file'))
            reader.readAsDataURL(file)
        })

        const fileDataUrl = await readFileAsDataUrl(frames.file)
        const mimeType = frames.file.type || 'video/mp4'
        const inferredFormat = mimeType.split('/')[1]?.replace('3gpp', 'three_gp') || 'mp4'

        const res = await fetch(`${BACKEND}/api/v1/video/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                video_b64: fileDataUrl.split(',')[1],
                video_format: inferredFormat,
                frames_b64: frames.samples.map((frame) => frame.frameDataUrl.split(',')[1]),
                timestamps_ms: frames.samples.map((frame) => frame.timestampMs),
                sport,
                match_session: matchSession,
            }),
        })

        const data = await res.json()
        if (data.status !== 'success') {
            throw new Error(data.detail || data.error || 'Video analysis failed')
        }

        setDetection(data.analysis)

        if (data.analysis?.confidence > 0.6) {
            if (sendTacticalDetection) {
                await sendTacticalDetection(data.analysis)
            } else if (sendMatchEvent && data.analysis?.actionable_insight) {
                await sendMatchEvent(data.analysis.actionable_insight)
            }
        }
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

    const extractFramesFromVideo = (file) => new Promise((resolve, reject) => {
        const videoUrl = URL.createObjectURL(file)
        const video = document.createElement('video')
        video.preload = 'metadata'
        video.muted = true
        video.playsInline = true
        video.src = videoUrl
        const preset = VIDEO_SAMPLING_PRESETS[videoSamplingPreset] || VIDEO_SAMPLING_PRESETS[DEFAULT_VIDEO_SAMPLING_PRESET]
        const mode = VIDEO_SAMPLING_MODES[videoSamplingMode] ? videoSamplingMode : DEFAULT_VIDEO_SAMPLING_MODE

        const fail = (message) => {
            URL.revokeObjectURL(videoUrl)
            reject(new Error(message))
        }

        video.onerror = () => fail('Could not read the selected video')

        const seekAndCapture = (timeSeconds, onCapture) => new Promise((resolveCapture, rejectCapture) => {
            const handleSeeked = () => {
                try {
                    resolveCapture(onCapture())
                } catch (err) {
                    rejectCapture(err)
                }
            }

            video.addEventListener('seeked', handleSeeked, { once: true })
            video.currentTime = timeSeconds
        })

        const captureFrameAt = (timeSeconds) => seekAndCapture(timeSeconds, () => {
                    const sourceWidth = video.videoWidth || 1280
                    const sourceHeight = video.videoHeight || 720
                    const maxDimension = Math.max(sourceWidth, sourceHeight)
                    const scale = maxDimension > MAX_FALLBACK_FRAME_DIMENSION
                        ? MAX_FALLBACK_FRAME_DIMENSION / maxDimension
                        : 1
                    const canvas = document.createElement('canvas')
                    canvas.width = Math.max(1, Math.round(sourceWidth * scale))
                    canvas.height = Math.max(1, Math.round(sourceHeight * scale))
                    const context = canvas.getContext('2d')
                    if (!context) {
                        rejectFrame(new Error('Could not create a frame preview from this video'))
                        return
                    }

                    context.drawImage(video, 0, 0, canvas.width, canvas.height)
                    return {
                        frameDataUrl: canvas.toDataURL('image/jpeg', FALLBACK_FRAME_QUALITY),
                        timestampMs: Math.round((video.currentTime || 0) * 1000),
                    }
        })

        const captureThumbnailAt = (timeSeconds) => seekAndCapture(timeSeconds, () => {
            const canvas = document.createElement('canvas')
            canvas.width = THUMBNAIL_SIGNATURE_WIDTH
            canvas.height = THUMBNAIL_SIGNATURE_HEIGHT
            const context = canvas.getContext('2d', { willReadFrequently: true })
            if (!context) {
                throw new Error('Could not inspect the selected video for transition-aware sampling')
            }

            context.drawImage(video, 0, 0, canvas.width, canvas.height)
            return {
                timeSeconds,
                signature: context.getImageData(0, 0, canvas.width, canvas.height).data,
            }
        })

        video.onloadedmetadata = async () => {
            try {
                const duration = Number.isFinite(video.duration) && video.duration > 0 ? video.duration : 0
                if (!duration) {
                    const firstFrame = await captureFrameAt(0)
                    resolve({
                        file,
                        samples: [firstFrame],
                        videoUrl,
                    })
                    return
                }

                const targetSampleCount = Math.min(
                    preset.maxFrames,
                    Math.max(MIN_FALLBACK_VIDEO_SAMPLES, Math.ceil(duration / preset.intervalSeconds))
                )
                const uniformTimes = buildUniformSampleTimes(duration, preset.intervalSeconds, targetSampleCount)
                let sampleTimes = uniformTimes

                if (mode === 'adaptive' && uniformTimes.length < preset.maxFrames) {
                    const probeIntervalSeconds = Math.max(ADAPTIVE_PROBE_MIN_INTERVAL_SECONDS, preset.intervalSeconds / 2)
                    const probeLimit = Math.min(96, Math.max(targetSampleCount, preset.maxFrames * 2))
                    const probeTimes = buildUniformSampleTimes(duration, probeIntervalSeconds, probeLimit)
                    const probeFrames = []

                    for (const probeTime of probeTimes) {
                        probeFrames.push(await captureThumbnailAt(probeTime))
                    }

                    sampleTimes = buildAdaptiveSampleTimes(duration, preset.intervalSeconds, preset.maxFrames, probeFrames)
                }

                const frames = []
                for (const sampleTime of sampleTimes) {
                    // Sequential seeking preserves temporal order and keeps extraction reliable.
                    frames.push(await captureFrameAt(sampleTime))
                }

                resolve({
                    file,
                    samples: frames,
                    videoUrl,
                })
            } catch (err) {
                fail(err.message || 'Video frame extraction failed')
            }
        }

        video.onseeked = null

        video.onloadeddata = () => {
            try {
                const canvas = document.createElement('canvas')
                canvas.width = 1
                canvas.height = 1
            } catch {
                // no-op; ensures browser decodes initial frame before seeking on some engines
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
            const { file: extractedFile, samples, videoUrl } = await extractFramesFromVideo(file)
            if (objectUrlRef.current) {
                URL.revokeObjectURL(objectUrlRef.current)
            }
            objectUrlRef.current = videoUrl
            resetPreviewUrl(videoUrl, 'video')
            await analyzeVideoFrames({ file: extractedFile, samples })
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

    const activePreset = VIDEO_SAMPLING_PRESETS[videoSamplingPreset] || VIDEO_SAMPLING_PRESETS[DEFAULT_VIDEO_SAMPLING_PRESET]
    const activeMode = VIDEO_SAMPLING_MODES[videoSamplingMode] || VIDEO_SAMPLING_MODES[DEFAULT_VIDEO_SAMPLING_MODE]

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
                            ? <><span className="spinner" /> Sampling Video...</>
                            : <>🎬 Upload Short Video</>
                        }
                    </button>
                </div>
                <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        <span style={{ color: 'var(--text-secondary)', fontSize: 11, fontWeight: 700, letterSpacing: 0.4, textTransform: 'uppercase' }}>
                            Sampling Preset
                        </span>
                        <select
                            value={videoSamplingPreset}
                            onChange={(event) => setVideoSamplingPreset(event.target.value)}
                            disabled={loading}
                            style={{
                                background: 'var(--bg-card)',
                                border: '1px solid var(--border)',
                                borderRadius: 8,
                                color: 'var(--text-primary)',
                                padding: '10px 12px',
                                fontSize: 13,
                                outline: 'none',
                            }}
                        >
                            {Object.entries(VIDEO_SAMPLING_PRESETS).map(([presetKey, preset]) => (
                                <option key={presetKey} value={presetKey}>
                                    {preset.label}
                                </option>
                            ))}
                        </select>
                    </label>
                    <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        <span style={{ color: 'var(--text-secondary)', fontSize: 11, fontWeight: 700, letterSpacing: 0.4, textTransform: 'uppercase' }}>
                            Fallback Mode
                        </span>
                        <select
                            value={videoSamplingMode}
                            onChange={(event) => setVideoSamplingMode(event.target.value)}
                            disabled={loading}
                            style={{
                                background: 'var(--bg-card)',
                                border: '1px solid var(--border)',
                                borderRadius: 8,
                                color: 'var(--text-primary)',
                                padding: '10px 12px',
                                fontSize: 13,
                                outline: 'none',
                            }}
                        >
                            {Object.entries(VIDEO_SAMPLING_MODES).map(([modeKey, modeConfig]) => (
                                <option key={modeKey} value={modeKey}>
                                    {modeConfig.label}
                                </option>
                            ))}
                        </select>
                    </label>
                </div>
                <div style={{ marginTop: 10, color: 'var(--text-secondary)', fontSize: 12 }}>
                    {activePreset.description} {activeMode.description} Current fallback targets roughly one frame every {activePreset.intervalSeconds.toFixed(2)} seconds, capped at {activePreset.maxFrames} frames.
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
