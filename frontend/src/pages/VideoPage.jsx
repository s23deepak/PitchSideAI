import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { DemoModeProvider, useDemoMode } from '../components/DemoModeProvider'
import FirstVisitOverlay from '../components/FirstVisitOverlay'
import VideoCanvas from '../components/VideoCanvas'
import ControlsTray from '../components/ControlsTray'
import Teleprompter from '../components/Teleprompter'
import CommentaryNotesViewer from '../components/CommentaryNotesViewer'
import TriviaCard from '../components/TriviaCard'
import { DEMO_FIXTURE } from '../lib/demo-seed'

/* ── VideoPage — Self-Guided Demo Mode (Story 4.2) ──────────────────────────── */

// Patch #7: Simple inline error boundary component
function VideoErrorBoundary({ children }) {
    const [hasError, setHasError] = useState(false)

    // Error boundary using error event listener
    useEffect(() => {
        const handleError = (event) => {
            event.preventDefault()
            setHasError(true)
        }

        window.addEventListener('error', handleError)
        return () => window.removeEventListener('error', handleError)
    }, [])

    if (hasError) {
        return (
            <div className="video-error" role="alert">
                <h2>Video player unavailable</h2>
                <p>The video player encountered an error.</p>
                <button onClick={() => window.location.reload()}>
                    Retry
                </button>
            </div>
        )
    }

    return children
}

function VideoPageContent() {
    const navigate = useNavigate()
    const { fixture, getNextTriviaCard, suggestedQuestions, markFeatureTried } = useDemoMode()

    // Patch #3: Null guard for fixture
    if (!fixture) {
        return (
            <div className="video-page-loading">
                <div className="loading-spinner" role="status" aria-label="Loading demo mode">
                    <div className="spinner" />
                </div>
                <p>Loading demo mode...</p>
            </div>
        )
    }

    const [videoTime, setVideoTime] = useState(0)
    const [currentTriviaCard, setCurrentTriviaCard] = useState(null)
    const [showControls, setShowControls] = useState(true)
    const [showTeleprompter, setShowTeleprompter] = useState(false)
    const [showNotes, setShowNotes] = useState(true)

    // Handle video time update
    const handleTimeUpdate = useCallback((time) => {
        setVideoTime(time * 1000) // Convert to ms

        // Check for trivia card at this time
        const card = getNextTriviaCard(time * 1000)
        if (card) {
            setCurrentTriviaCard(card)
        }
    }, [getNextTriviaCard])

    // Auto-dismiss trivia card after 8 seconds
    useEffect(() => {
        if (currentTriviaCard) {
            const timer = setTimeout(() => {
                setCurrentTriviaCard(null)
            }, 8000)
            return () => clearTimeout(timer)
        }
    }, [currentTriviaCard])

    // Mark feature as tried when controls are interacted with
    const handleControlInteraction = useCallback((feature) => {
        markFeatureTried(feature)
    }, [markFeatureTried])

    return (
        <div className="video-page">
            {/* First-visit overlay (auto-dismisses after 4s) */}
            <FirstVisitOverlay />

            {/* Demo match info header */}
            <div className="video-page-header">
                <div className="demo-match-info">
                    <h1 className="demo-match-title">
                        {fixture.homeTeam} vs {fixture.awayTeam}
                    </h1>
                    <p className="demo-match-competition">{fixture.competition}</p>
                    <span className="demo-badge">Demo Mode</span>
                </div>
                <button
                    className="back-to-home-btn"
                    onClick={() => navigate('/')}
                    aria-label="Back to home"
                >
                    ← Back
                </button>
            </div>

            {/* Main video player - Patch #7: Wrapped in error boundary */}
            <div className="video-page-content">
                <VideoErrorBoundary>
                    <VideoCanvas
                        matchSession={`${fixture.homeTeam.toLowerCase()}-vs-${fixture.awayTeam.toLowerCase()}`}
                        homeTeam={fixture.homeTeam}
                        awayTeam={fixture.awayTeam}
                        sport="soccer"
                        onTacticalDetection={(detection) => console.log('[VideoPage] Tactical:', detection)}
                        onCommentary={(commentary) => console.log('[VideoPage] Commentary:', commentary)}
                    />
                </VideoErrorBoundary>

                {/* Trivia card overlay */}
                {currentTriviaCard && (
                    <TriviaCard
                        card={currentTriviaCard}
                        onDismiss={() => setCurrentTriviaCard(null)}
                    />
                )}
            </div>

            {/* Controls tray - always visible in demo mode */}
            {showControls && (
                <ControlsTray
                    visible={true}
                    isDemoMode={true}
                    suggestedQuestions={suggestedQuestions}
                    onFeatureTry={handleControlInteraction}
                    onViewChange={(view) => {
                        if (view === 'commentator') {
                            setShowTeleprompter(true)
                        } else {
                            setShowTeleprompter(false)
                        }
                    }}
                    onNotesToggle={(enabled) => setShowNotes(enabled)}
                />
            )}

            {/* Teleprompter panel (commentator view) */}
            {showTeleprompter && (
                <div className="teleprompter-panel">
                    <Teleprompter
                        notes={fixture.commentaryNotes}
                        isGenerating={false}
                    />
                </div>
            )}

            {/* Commentary notes viewer */}
            {showNotes && (
                <div className="notes-panel">
                    <CommentaryNotesViewer
                        commentaryData={{ raw_markdown: fixture.commentaryNotes }}
                        buildingNotes={false}
                    />
                </div>
            )}
        </div>
    )
}

/* ── VideoPage with Demo Mode Provider ─────────────────────────────────────── */
export default function VideoPage() {
    return (
        <DemoModeProvider>
            <VideoPageContent />
        </DemoModeProvider>
    )
}
