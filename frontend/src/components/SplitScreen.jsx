/**
 * SplitScreen Component — Story 2.3: Split-Screen Temporal Navigation
 *
 * Displays a split view with live match (60%) and frozen frame with SVG overlays (40%)
 * when Q&A answers are received with temporal context.
 *
 * Features:
 * - 300ms slide animation (instant with prefers-reduced-motion)
 * - 60/40 split with 2px Slate 800 divider
 * - SVG overlay rendering with stroke-dasharray draw-on animation
 * - Keyboard dismissal (Escape) and click dismissal
 * - Screen reader accessibility (role="region", aria-label)
 * - Content timeout with loading skeleton
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import FrozenFrameWithSVG from './FrozenFrameWithSVG'

/**
 * SplitScreen states
 */
const SplitScreenState = {
    HIDDEN: 'hidden',
    SLIDING_IN: 'sliding_in',
    ACTIVE: 'active',
    SLIDING_OUT: 'sliding_out',
}

/**
 * Animation durations (ms)
 */
const ANIMATION_DURATION = 300
const CONTENT_TIMEOUT = 500
const AUTO_DISMISS_TIMEOUT = 5000      // 5s for voice Q&A
const VIDEO_AUTO_DISMISS_TIMEOUT = 15000 // 15s for video clip Q&A

function cleanAnswerText(text) {
    if (!text) return ''
    let cleaned = String(text).trim()

    try {
        const parsed = JSON.parse(cleaned)
        if (parsed && typeof parsed === 'object') {
            cleaned = parsed.answer || parsed.commentary || parsed.key_observation || parsed.analysis || parsed.text || cleaned
        }
    } catch {
        const match = cleaned.match(/"(?:answer|commentary|key_observation|analysis|text)"\s*:\s*"([^"]+)/s)
        if (match) cleaned = match[1]
    }

    return cleaned
        .replace(/\\n/g, ' ')
        .replace(/\\"/g, '"')
        .replace(/^\s*(?:answer|commentary|analysis|text)\s*:\s*/i, '')
        .replace(/",?\s*\d+\s*:\s*.*$/s, '')
        .replace(/^[\s{}[\],'"]+|[\s{}[\],'"]+$/g, '')
        .replace(/\s+/g, ' ')
        .trim()
}

export default function SplitScreen({
    answer,
    isActive,
    onDismiss,
    children,
    videoPreview = null,   // Object URL for uploaded video clip (from useVideoQA)
    liveVideoUrl = null,   // Object URL of the video currently playing in VideoCanvas
    isAnalyzing = false,   // True while video Q&A backend is processing
    clipQuestion = '',     // The question the user typed before uploading
}) {
    const [state, setState] = useState(SplitScreenState.HIDDEN)
    const [contentReady, setContentReady] = useState(false)
    const [loadingSkeleton, setLoadingSkeleton] = useState(false)
    const contentTimeoutRef = useRef(null)
    const autoDismissRef = useRef(null)
    const prefersReducedMotion = useRef(false)

    // Detect prefers-reduced-motion on mount
    useEffect(() => {
        const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
        prefersReducedMotion.current = mediaQuery.matches

        const handleChange = (e) => {
            prefersReducedMotion.current = e.matches
        }

        mediaQuery.addEventListener('change', handleChange)
        return () => mediaQuery.removeEventListener('change', handleChange)
    }, [])

    // Handle activation — slide in and mark content ready. No auto-dismiss here.
    useEffect(() => {
        if (isActive && answer) {
            // Start content timeout
            contentTimeoutRef.current = setTimeout(() => {
                setLoadingSkeleton(true)
            }, CONTENT_TIMEOUT)

            // Check if content is ready
            const isVideoQA = answer.source === 'video_qa'
            if (isVideoQA || answer.timestamp_ms || answer.temporal_context === 'limited') {
                setContentReady(true)
                clearTimeout(contentTimeoutRef.current)
            }

            // Start slide-in animation
            setState(SplitScreenState.SLIDING_IN)

            // Transition to active after animation
            const duration = prefersReducedMotion.current ? 0 : ANIMATION_DURATION
            setTimeout(() => {
                setState(SplitScreenState.ACTIVE)
            }, duration)
        }

        return () => {
            if (contentTimeoutRef.current) clearTimeout(contentTimeoutRef.current)
        }
    }, [isActive, answer])

    // Handle dismissal
    const handleDismiss = useCallback(() => {
        setState(SplitScreenState.SLIDING_OUT)

        const duration = prefersReducedMotion.current ? 0 : ANIMATION_DURATION
        setTimeout(() => {
            setState(SplitScreenState.HIDDEN)
            setContentReady(false)
            setLoadingSkeleton(false)
            onDismiss?.()
        }, duration)

        // Clear auto-dismiss timer
        if (autoDismissRef.current) {
            clearTimeout(autoDismissRef.current)
            autoDismissRef.current = null
        }
    }, [onDismiss])

    // Auto-dismiss — only starts AFTER model finishes (isAnalyzing → false)
    useEffect(() => {
        if (autoDismissRef.current) {
            clearTimeout(autoDismissRef.current)
            autoDismissRef.current = null
        }
        if (!isActive || isAnalyzing) return   // wait until done
        const isVideoQA = answer?.source === 'video_qa'
        const timeout = isVideoQA ? VIDEO_AUTO_DISMISS_TIMEOUT : AUTO_DISMISS_TIMEOUT
        autoDismissRef.current = setTimeout(() => {
            handleDismiss()
        }, timeout)
        return () => {
            if (autoDismissRef.current) clearTimeout(autoDismissRef.current)
        }
    }, [isActive, isAnalyzing, handleDismiss])

    // Keyboard dismissal (Escape key)
    useEffect(() => {
        if (state !== SplitScreenState.ACTIVE && state !== SplitScreenState.SLIDING_IN) {
            return
        }

        const handleKeyDown = (e) => {
            if (e.key === 'Escape') {
                e.preventDefault()
                handleDismiss()
            }
        }

        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)
    }, [state, handleDismiss])

    // Click/tap dismissal on right panel
    const handleRightPanelClick = useCallback((e) => {
        // Only dismiss if clicking directly on the panel (not on overlay elements)
        if (e.target === e.currentTarget) {
            handleDismiss()
        }
    }, [handleDismiss])

    // Don't render if hidden
    if (state === SplitScreenState.HIDDEN) {
        return null
    }

    // Determine if we're in limited temporal context mode
    const isLimitedContext = answer?.temporal_context === 'limited'
    const answerText = cleanAnswerText(answer?.text)

    // Animation class based on state
    const getAnimationClass = () => {
        if (prefersReducedMotion.current) {
            return ''
        }

        switch (state) {
            case SplitScreenState.SLIDING_IN:
                return 'animate-slide-in'
            case SplitScreenState.SLIDING_OUT:
                return 'animate-slide-out'
            default:
                return ''
        }
    }

    // Panel width based on state
    const getPanelWidth = () => {
        if (state === SplitScreenState.HIDDEN) return '0%'
        if (state === SplitScreenState.SLIDING_OUT) return '0%'
        return '40%'
    }

    return (
        <div
            className={`split-screen ${getAnimationClass()}`}
            role="region"
            aria-label="Question answer: showing the relevant match moment"
            aria-live="polite"
        >
            {/* Left Panel - Live Match Video (60%) */}
            <div className="split-screen-left">
                {liveVideoUrl ? (
                    <video
                        src={liveVideoUrl}
                        autoPlay
                        loop
                        muted
                        playsInline
                        style={{ width: '100%', height: '100%', objectFit: 'contain', background: '#000' }}
                    />
                ) : children}
            </div>

            {/* Divider - 2px Slate 800 */}
            <div className="split-screen-divider" />

            {/* Right Panel - Frozen Frame (40%) */}
            <div
                className="split-screen-right"
                style={{ width: getPanelWidth(), background: '#0E0E0E', borderLeft: '2px solid #1a1a1a' }}
                onClick={handleRightPanelClick}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        handleDismiss()
                    }
                }}
                aria-label="Click or press Enter to dismiss"
            >
                {/* Dismiss X button — always visible when active */}
                <button
                    onClick={(e) => { e.stopPropagation(); handleDismiss() }}
                    aria-label="Dismiss Q&A panel"
                    style={{
                        position: 'absolute', top: '12px', right: '12px', zIndex: 10,
                        width: '28px', height: '28px', borderRadius: '50%',
                        background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.12)',
                        color: '#c3c9ae', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: '16px', lineHeight: 1, fontFamily: 'system-ui',
                    }}
                >×</button>

                {answer?.source === 'video_qa' ? (
                    /* ── Video Q&A panel ── */
                    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '16px 14px 14px' }}>
                        {/* Video preview */}
                        {videoPreview && (
                            <div style={{ borderRadius: '8px', overflow: 'hidden', flexShrink: 0, marginBottom: '12px', border: '1px solid rgba(255,255,255,0.08)' }}>
                                <video
                                    src={videoPreview}
                                    style={{ width: '100%', display: 'block', maxHeight: '180px', objectFit: 'cover' }}
                                    muted autoPlay loop playsInline
                                />
                            </div>
                        )}

                        {/* Header */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px' }}>
                            <span className="material-symbols-outlined" style={{ fontSize: '16px', color: '#c3f400' }}>smart_toy</span>
                            <span style={{ fontFamily: "'Space Grotesk', monospace", fontSize: '11px', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#c3c9ae' }}>AI CLIP ANALYSIS</span>
                        </div>
                        {clipQuestion && (
                            <div style={{ marginBottom: '10px', padding: '7px 10px', borderRadius: '6px', background: 'rgba(195,244,0,0.06)', border: '1px solid rgba(195,244,0,0.15)' }}>
                                <span style={{ color: '#c3f400', fontFamily: "'Space Grotesk', monospace", fontSize: '11px', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', display: 'block', marginBottom: '2px' }}>Q</span>
                                <span style={{ color: '#e5e2e1', fontFamily: "'Inter', sans-serif", fontSize: '13px', lineHeight: 1.5 }}>{clipQuestion}</span>
                            </div>
                        )}

                        {/* Streaming answer text */}
                        <div style={{ flex: 1, overflow: 'auto', paddingRight: '4px' }}>
                            {isAnalyzing && !answer?.text ? (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                    {[100, 85, 70].map((w, i) => (
                                        <div key={i} style={{
                                            height: '12px', borderRadius: '4px', width: `${w}%`,
                                            background: 'linear-gradient(90deg, #1e2a1e 0%, #2a3a1a 50%, #1e2a1e 100%)',
                                            backgroundSize: '200% 100%', animation: 'shimmer 1.5s infinite',
                                        }} />
                                    ))}
                                    <span style={{ color: '#c3c9ae', fontFamily: "'Inter', sans-serif", fontSize: '12px', marginTop: '4px' }}>Analyzing clip…</span>
                                </div>
                            ) : (
                                <p style={{
                                    color: '#e5e2e1', fontFamily: "'Inter', sans-serif",
                                    fontSize: '14px', lineHeight: '1.6', margin: 0,
                                }}>
                                    {answerText}
                                    {isAnalyzing && <span style={{ color: '#c3f400', animation: 'pulse 1s infinite' }}>▌</span>}
                                </p>
                            )}
                        </div>
                    </div>
                ) : loadingSkeleton && !contentReady ? (
                    <div className="loading-skeleton">
                        <div className="skeleton-frame" />
                        <div className="skeleton-text" />
                    </div>
                ) : isLimitedContext ? (
                    <div className="limited-context-panel">
                        <div className="limited-context-indicator">Based on available footage</div>
                        <div className="answer-text">{answerText}</div>
                    </div>
                ) : (
                    <FrozenFrameWithSVG
                        timestamp_ms={answer?.timestamp_ms}
                        overlay={answer?.overlay_coordinates}
                        answerText={answerText}
                        onDismiss={handleDismiss}
                    />
                )}
            </div>

            {/* Inline styles for animations */}
            <style>{`
                .split-screen {
                    display: flex;
                    width: 100%;
                    height: 100%;
                    position: absolute;
                    top: 0;
                    left: 0;
                    z-index: 50;
                    overflow: hidden;
                }

                .split-screen-left {
                    flex: 0 0 60%;
                    width: 60%;
                    height: 100%;
                }

                .split-screen-divider {
                    flex: 0 0 2px;
                    width: 2px;
                    background-color: rgb(15, 23, 42); /* Slate 800 */
                    height: 100%;
                }

                .split-screen-right {
                    flex: 0 0 40%;
                    height: 100%;
                    position: relative;
                    background-color: #0E0E0E; /* Midnight Stadium surface-container-lowest */
                    overflow: hidden;
                    transition: width ${ANIMATION_DURATION}ms ease-in-out;
                }

                @keyframes slideIn {
                    from {
                        width: 0%;
                        opacity: 0;
                    }
                    to {
                        width: 40%;
                        opacity: 1;
                    }
                }

                @keyframes slideOut {
                    from {
                        width: 40%;
                        opacity: 1;
                    }
                    to {
                        width: 0%;
                        opacity: 0;
                    }
                }

                .animate-slide-in {
                    animation: slideIn ${ANIMATION_DURATION}ms ease-out forwards;
                }

                .animate-slide-out {
                    animation: slideOut ${ANIMATION_DURATION}ms ease-in forwards;
                }

                .loading-skeleton {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100%;
                    padding: 2rem;
                }

                .skeleton-frame {
                    width: 100%;
                    height: 60%;
                    background: linear-gradient(
                        90deg,
                        rgb(30, 41, 59) 0%,
                        rgb(51, 65, 85) 50%,
                        rgb(30, 41, 59) 100%
                    );
                    background-size: 200% 100%;
                    animation: shimmer 1.5s infinite;
                    border-radius: 8px;
                    margin-bottom: 1rem;
                }

                .skeleton-text {
                    width: 80%;
                    height: 20px;
                    background: linear-gradient(
                        90deg,
                        rgb(30, 41, 59) 0%,
                        rgb(51, 65, 85) 50%,
                        rgb(30, 41, 59) 100%
                    );
                    background-size: 200% 100%;
                    animation: shimmer 1.5s infinite;
                    border-radius: 4px;
                }

                @keyframes shimmer {
                    0% {
                        background-position: -200% 0;
                    }
                    100% {
                        background-position: 200% 0;
                    }
                }

                .limited-context-panel {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100%;
                    padding: 2rem;
                    text-align: center;
                }

                .limited-context-indicator {
                    color: rgb(148, 163, 184); /* Slate 400 */
                    font-size: 0.875rem;
                    margin-bottom: 1rem;
                    font-style: italic;
                }

                .answer-text {
                    color: rgb(255, 255, 255);
                    font-size: 1rem;
                    line-height: 1.6;
                }
            `}</style>
        </div>
    )
}
