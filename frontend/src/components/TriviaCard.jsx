import { useState, useEffect, useRef } from 'react'

/* ── TriviaCard — Contextual trivia display (Story 4.2) ─────────────────────── */
export default function TriviaCard({ card, onDismiss }) {
    const [visible, setVisible] = useState(false)
    const [isExiting, setIsExiting] = useState(false)
    // Patch #6: Ref to prevent double-dismiss race condition
    const isDismissingRef = useRef(false)

    // Fade in on mount
    useEffect(() => {
        setVisible(true)
    }, [])

    // Auto-dismiss after delay (Patch #6: prevent race with parent dismiss)
    useEffect(() => {
        if (!card || isDismissingRef.current) return

        isDismissingRef.current = true
        const timer = setTimeout(() => {
            setIsExiting(true)
            setTimeout(() => {
                onDismiss?.()
            }, 300) // Wait for exit animation
        }, 8000)

        return () => {
            clearTimeout(timer)
            isDismissingRef.current = false
        }
    }, [card, onDismiss])

    if (!card) return null

    const getEventTagColor = (tag) => {
        switch (tag) {
            case 'goal':
                return { bg: 'var(--success-muted)', border: 'var(--success)', text: 'var(--success)' }
            case 'yellow_card':
                return { bg: 'var(--warning-muted)', border: 'var(--warning)', text: 'var(--warning)' }
            case 'red_card':
                return { bg: 'var(--danger-muted)', border: 'var(--danger)', text: 'var(--danger)' }
            case 'substitution':
                return { bg: 'var(--accent-interactive-focus)', border: 'var(--accent-interactive)', text: 'var(--accent-interactive)' }
            default:
                return { bg: 'var(--accent-narrative-muted)', border: 'var(--accent-narrative)', text: 'var(--accent-narrative)' }
        }
    }

    const tagColors = getEventTagColor(card.eventTag)

    return (
        <div
            className={`trivia-card ${visible && !isExiting ? 'visible' : 'exiting'}`}
            role="alert"
            aria-live="polite"
        >
            <div className="trivia-card-header">
                <span
                    className="trivia-card-tag"
                    style={{
                        background: tagColors.bg,
                        border: `1px solid ${tagColors.border}`,
                        color: tagColors.text,
                    }}
                >
                    {card.eventTag.replace('_', ' ').toUpperCase()}
                </span>
                <span className="trivia-card-source">{card.source}</span>
            </div>
            <p className="trivia-card-text">{card.text}</p>
            <button
                className="trivia-card-dismiss"
                onClick={onDismiss}
                aria-label="Dismiss trivia card"
            >
                Dismiss
            </button>
        </div>
    )
}
