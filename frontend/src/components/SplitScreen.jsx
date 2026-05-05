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
const AUTO_DISMISS_TIMEOUT = 5000 // 5-8 seconds per AC4

export default function SplitScreen({
    answer,
    isActive,
    onDismiss,
    children,
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

    // Handle activation
    useEffect(() => {
        if (isActive && answer) {
            // Start content timeout
            contentTimeoutRef.current = setTimeout(() => {
                setLoadingSkeleton(true)
            }, CONTENT_TIMEOUT)

            // Check if content is ready (frozen frame loaded)
            if (answer.timestamp_ms || answer.temporal_context === 'limited') {
                setContentReady(true)
                clearTimeout(contentTimeoutRef.current)
            }

            // Start auto-dismiss timer
            autoDismissRef.current = setTimeout(() => {
                handleDismiss()
            }, AUTO_DISMISS_TIMEOUT)

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
            if (autoDismissRef.current) clearTimeout(autoDismissRef.current)
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
            {/* Left Panel - Live Match (60%) */}
            <div className="split-screen-left">
                {children}
            </div>

            {/* Divider - 2px Slate 800 */}
            <div className="split-screen-divider" />

            {/* Right Panel - Frozen Frame (40%) */}
            <div
                className="split-screen-right"
                style={{ width: getPanelWidth() }}
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
                {loadingSkeleton && !contentReady ? (
                    <div className="loading-skeleton">
                        <div className="skeleton-frame" />
                        <div className="skeleton-text" />
                    </div>
                ) : isLimitedContext ? (
                    <div className="limited-context-panel">
                        <div className="limited-context-indicator">
                            Based on available footage
                        </div>
                        <div className="answer-text">
                            {answer?.text}
                        </div>
                    </div>
                ) : (
                    <FrozenFrameWithSVG
                        timestamp_ms={answer?.timestamp_ms}
                        overlay={answer?.overlay_coordinates}
                        answerText={answer?.text}
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
                    position: relative;
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
                    background-color: rgb(2, 6, 23); /* Slate 950 */
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
