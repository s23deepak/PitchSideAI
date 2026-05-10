import { useState, useEffect } from 'react'

/* ── FirstVisitOverlay — First-time visitor greeting (Story 4.2, UX-DR14) ───── */
export default function FirstVisitOverlay() {
    const [visible, setVisible] = useState(false)

    useEffect(() => {
        const hasSeen = localStorage.getItem('pitchsideai_first_visit_seen')

        if (!hasSeen) {
            // First visit - show overlay
            setVisible(true)
            localStorage.setItem('pitchsideai_first_visit_seen', 'true')

            // Auto-hide after 4 seconds
            const timer = setTimeout(() => {
                setVisible(false)
            }, 4000)

            return () => clearTimeout(timer)
        }
    }, [])

    // Handle keyboard dismissal
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (visible && e.key === 'Escape') {
                setVisible(false)
            }
        }

        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)
    }, [visible])

    // Patch #4: Focus trap for WCAG 2.1 AA compliance (dialog role requires focus containment)
    useEffect(() => {
        if (!visible) return

        const overlay = document.querySelector('.first-visit-overlay')
        if (!overlay) return

        const focusableElements = overlay.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
        const firstFocusable = focusableElements[0]
        const lastFocusable = focusableElements[focusableElements.length - 1]

        const handleTabKey = (e) => {
            if (e.key !== 'Tab') return
            if (e.shiftKey && document.activeElement === firstFocusable) {
                e.preventDefault()
                lastFocusable.focus()
            } else if (!e.shiftKey && document.activeElement === lastFocusable) {
                e.preventDefault()
                firstFocusable.focus()
            }
        }

        overlay.addEventListener('keydown', handleTabKey)
        firstFocusable?.focus()

        return () => overlay.removeEventListener('keydown', handleTabKey)
    }, [visible])

    if (!visible) return null

    return (
        <div
            className="first-visit-overlay"
            role="dialog"
            aria-modal="true"
            aria-labelledby="overlay-title"
        >
            <div className="first-visit-overlay-content">
                <h2 id="overlay-title" className="first-visit-overlay-title">
                    PitchSideAI — Your AI Broadcast Companion
                </h2>
                <p className="first-visit-overlay-description">
                    Trivia cards explain the action. Hold the mic to ask questions.
                </p>
            </div>
        </div>
    )
}
