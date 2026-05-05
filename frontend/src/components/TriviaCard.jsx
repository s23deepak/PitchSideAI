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
                return { bg: 'rgba(16, 185, 129, 0.15)', border: '#10B981', text: '#10B981' }
            case 'yellow_card':
                return { bg: 'rgba(245, 158, 11, 0.15)', border: '#F59E0B', text: '#F59E0B' }
            case 'red_card':
                return { bg: 'rgba(239, 68, 68, 0.15)', border: '#EF4444', text: '#EF4444' }
            case 'substitution':
                return { bg: 'rgba(59, 130, 246, 0.15)', border: '#3B82F6', text: '#3B82F6' }
            default:
                return { bg: 'rgba(167, 139, 250, 0.15)', border: '#A78BFA', text: '#A78BFA' }
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
