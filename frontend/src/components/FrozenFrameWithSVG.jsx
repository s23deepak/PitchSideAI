/**
 * FrozenFrameWithSVG Component — Story 2.3: Split-Screen Temporal Navigation
 *
 * Displays a frozen video frame with SVG overlays for player identification
 * and tactical annotations.
 *
 * Features:
 * - SVG overlay rendering with stroke-dasharray draw-on animation (200ms per element)
 * - Confidence-based overlay types (circle for high, zone for medium)
 * - White 90% opacity strokes with dropshadow filter (UX-DR27)
 * - Sequential element drawing: circle → arrow → line → label
 * - Click/tap to dismiss
 */

import { useState, useEffect, useRef } from 'react'

/**
 * Overlay confidence tiers
 */
const CONFIDENCE_HIGH = 0.9
const CONFIDENCE_MEDIUM = 0.7

/**
 * Animation duration for draw-on effect (ms)
 */
const DRAW_ON_DURATION = 200

export default function FrozenFrameWithSVG({
    timestamp_ms,
    overlay,
    answerText,
    onDismiss,
}) {
    const [frameLoaded, setFrameLoaded] = useState(false)
    const [drawAnimation, setDrawAnimation] = useState(false)
    const [visibleElements, setVisibleElements] = useState({
        circle: false,
        arrow: false,
        line: false,
        label: false,
    })
    const videoRef = useRef(null)

    // Handle frame loading
    useEffect(() => {
        if (timestamp_ms && videoRef.current) {
            const video = videoRef.current

            const handleLoadedData = () => {
                setFrameLoaded(true)
                startDrawAnimation()
            }

            video.addEventListener('loadeddata', handleLoadedData)

            // Seek to timestamp
            const timestampSec = (timestamp_ms || 0) / 1000
            video.currentTime = timestampSec

            return () => {
                video.removeEventListener('loadeddata', handleLoadedData)
            }
        } else {
            // No timestamp, show placeholder
            setFrameLoaded(true)
            startDrawAnimation()
        }
    }, [timestamp_ms])

    // Start draw-on animation sequence
    const startDrawAnimation = () => {
        setDrawAnimation(true)

        // Sequential element visibility
        const sequence = []

        if (overlay) {
            // Circle first (if high confidence)
            if (overlay.confidence > CONFIDENCE_HIGH) {
                sequence.push(
                    setTimeout(() => {
                        setVisibleElements((prev) => ({ ...prev, circle: true }))
                    }, 0)
                )
            }

            // Zone highlight (if medium confidence)
            if (overlay.confidence >= CONFIDENCE_MEDIUM && overlay.confidence <= CONFIDENCE_HIGH) {
                sequence.push(
                    setTimeout(() => {
                        setVisibleElements((prev) => ({ ...prev, circle: true }))
                    }, 0)
                )
            }

            // Arrow (if present)
            if (overlay.type === 'arrow') {
                sequence.push(
                    setTimeout(() => {
                        setVisibleElements((prev) => ({ ...prev, arrow: true }))
                    }, DRAW_ON_DURATION)
                )
            }

            // Line (if present, e.g., offside line)
            if (overlay.type === 'line') {
                sequence.push(
                    setTimeout(() => {
                        setVisibleElements((prev) => ({ ...prev, line: true }))
                    }, DRAW_ON_DURATION)
                )
            }

            // Label always last
            if (overlay.label) {
                sequence.push(
                    setTimeout(() => {
                        setVisibleElements((prev) => ({ ...prev, label: true }))
                    }, DRAW_ON_DURATION * 2)
                )
            }
        }

        return () => {
            sequence.forEach((timeout) => clearTimeout(timeout))
        }
    }

    // Handle click to dismiss
    const handleClick = () => {
        onDismiss?.()
    }

    // Render overlay based on type and confidence
    const renderOverlay = () => {
        if (!overlay || !frameLoaded) {
            return null
        }

        const {
            type = 'circle',
            cx,
            cy,
            r,
            rx,
            ry,
            label,
            confidence = 0.5,
            stroke = 'rgb(255, 255, 255)',
            stroke_width = 2,
        } = overlay

        const isHighConfidence = confidence > CONFIDENCE_HIGH
        const isMediumConfidence = confidence >= CONFIDENCE_MEDIUM && confidence <= CONFIDENCE_HIGH

        return (
            <svg
                className="overlay-svg"
                viewBox="0 0 100 100"
                preserveAspectRatio="xMidYMid meet"
                onClick={handleClick}
            >
                {/* Dropshadow filter (UX-DR27: 1px blur, 50% black) */}
                <defs>
                    <filter id="overlay-dropshadow" x="-50%" y="-50%" width="200%" height="200%">
                        <feDropShadow dx="0" dy="0" stdDeviation="1" floodOpacity="0.5" />
                    </filter>
                </defs>

                {/* Circle overlay (high confidence - precise) */}
                {type === 'circle' && isHighConfidence && visibleElements.circle && (
                    <circle
                        cx={cx}
                        cy={cy}
                        r={r || 8}
                        stroke={stroke}
                        strokeWidth={stroke_width || 3}
                        fill="none"
                        opacity="0.9"
                        filter="url(#overlay-dropshadow)"
                        className="overlay-circle"
                        style={{
                            strokeDasharray: '1000',
                            strokeDashoffset: drawAnimation ? '1000' : '0',
                            transition: `stroke-dashoffset ${DRAW_ON_DURATION}ms ease-out`,
                        }}
                    />
                )}

                {/* Zone overlay (medium confidence - wider highlight) */}
                {(type === 'zone' || (type === 'circle' && isMediumConfidence)) && visibleElements.circle && (
                    <>
                        <ellipse
                            cx={cx}
                            cy={cy}
                            rx={rx || 15}
                            ry={ry || 12}
                            stroke={stroke}
                            strokeWidth={stroke_width || 2}
                            fill="rgba(255, 255, 255, 0.2)"
                            opacity="0.9"
                            filter="url(#overlay-dropshadow)"
                            className="overlay-zone"
                            style={{
                                strokeDasharray: '1000',
                                strokeDashoffset: drawAnimation ? '1000' : '0',
                                transition: `stroke-dashoffset ${DRAW_ON_DURATION}ms ease-out`,
                            }}
                        />
                    </>
                )}

                {/* Arrow overlay (e.g., movement direction) */}
                {type === 'arrow' && visibleElements.arrow && (
                    <g
                        className="overlay-arrow"
                        filter="url(#overlay-dropshadow)"
                        opacity="0.9"
                    >
                        <line
                            x1={overlay.x1 || 20}
                            y1={overlay.y1 || 50}
                            x2={overlay.x2 || 80}
                            y2={overlay.y2 || 50}
                            stroke={stroke}
                            strokeWidth={stroke_width || 3}
                            strokeDasharray="5,5"
                            style={{
                                strokeDashoffset: drawAnimation ? '10' : '0',
                                transition: `stroke-dashoffset ${DRAW_ON_DURATION}ms ease-out`,
                            }}
                        />
                        {/* Arrowhead */}
                        <polygon
                            points={`${overlay.x2 || 80},${overlay.y2 || 50} ${overlay.x2 - 5 || 75},${overlay.y2 - 5 || 45} ${overlay.x2 - 5 || 75},${overlay.y2 + 5 || 55}`}
                            fill={stroke}
                            opacity="0.9"
                        />
                    </g>
                )}

                {/* Line overlay (e.g., offside line) */}
                {type === 'line' && visibleElements.line && (
                    <line
                        x1={overlay.x1 || 0}
                        y1={overlay.y1 || 50}
                        x2={overlay.x2 || 100}
                        y2={overlay.y2 || 50}
                        stroke={stroke}
                        strokeWidth={stroke_width || 2}
                        strokeDasharray="5,5"
                        opacity="0.9"
                        filter="url(#overlay-dropshadow)"
                        className="overlay-line"
                        style={{
                            strokeDashoffset: drawAnimation ? '10' : '0',
                            transition: `stroke-dashoffset ${DRAW_ON_DURATION}ms ease-out`,
                        }}
                    />
                )}

                {/* Label text */}
                {label && visibleElements.label && (
                    <text
                        x={overlay.labelX || cx || 50}
                        y={overlay.labelY || (cy || 50) - 15}
                        fill={stroke}
                        fontSize="14"
                        fontWeight="bold"
                        textAnchor="middle"
                        opacity="0.9"
                        filter="url(#overlay-dropshadow)"
                        className="overlay-label"
                        style={{
                            opacity: drawAnimation ? 0 : 0.9,
                            transition: `opacity ${DRAW_ON_DURATION}ms ease-out`,
                        }}
                    >
                        {label}
                    </text>
                )}
            </svg>
        )
    }

    return (
        <div className="frozen-frame-container" onClick={handleClick}>
            {/* Video element for frozen frame */}
            <video
                ref={videoRef}
                className="frozen-frame-video"
                muted
                playsInline
                preload="metadata"
            >
                {/* Source will be set by parent component via context or prop */}
                {/* For now, using a placeholder */}
                <source src="" type="video/mp4" />
            </video>

            {/* Placeholder when no video source */}
            {!timestamp_ms && (
                <div className="frozen-frame-placeholder">
                    <div className="placeholder-icon">🎬</div>
                    <div className="placeholder-text">
                        Frame at {timestamp_ms ? `${(timestamp_ms / 1000).toFixed(1)}s` : 'N/A'}
                    </div>
                </div>
            )}

            {/* SVG Overlay layer */}
            {frameLoaded && renderOverlay()}

            {/* Answer text overlay (optional) */}
            {answerText && (
                <div className="answer-text-overlay">
                    {answerText}
                </div>
            )}

            {/* Dismiss hint */}
            <div className="dismiss-hint">
                Click or press Escape to dismiss
            </div>

            {/* Inline styles */}
            <style>{`
                .frozen-frame-container {
                    position: relative;
                    width: 100%;
                    height: 100%;
                    background-color: rgb(2, 6, 23); /* Slate 950 */
                    cursor: pointer;
                }

                .frozen-frame-video {
                    width: 100%;
                    height: 100%;
                    object-fit: cover;
                }

                .frozen-frame-placeholder {
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    background-color: rgb(15, 23, 42); /* Slate 800 */
                }

                .placeholder-icon {
                    font-size: 3rem;
                    margin-bottom: 1rem;
                }

                .placeholder-text {
                    color: rgb(148, 163, 184); /* Slate 400 */
                    font-size: 0.875rem;
                }

                .overlay-svg {
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    pointer-events: none;
                }

                .answer-text-overlay {
                    position: absolute;
                    bottom: 0;
                    left: 0;
                    right: 0;
                    padding: 1rem;
                    background: linear-gradient(
                        to top,
                        rgba(0, 0, 0, 0.8) 0%,
                        rgba(0, 0, 0, 0) 100%
                    );
                    color: rgb(255, 255, 255);
                    font-size: 0.875rem;
                    line-height: 1.5;
                }

                .dismiss-hint {
                    position: absolute;
                    top: 1rem;
                    right: 1rem;
                    padding: 0.5rem 1rem;
                    background-color: rgba(0, 0, 0, 0.7);
                    color: rgb(203, 213, 225); /* Slate 300 */
                    font-size: 0.75rem;
                    border-radius: 4px;
                    opacity: 0.8;
                }
            `}</style>
        </div>
    )
}
