import { useState } from 'react'
import PushToTalk from './PushToTalk'
import CommentaryFeed from './CommentaryFeed'
import EventFeed from './EventFeed'
import CommentaryNotesViewer from './CommentaryNotesViewer'
import LiveVideoPlayer from './LiveVideoPlayer'
import VideoCanvas from './VideoCanvas'
import MatchInsight from './MatchInsight'
import MicButton from './MicButton'
import SplitScreen from './SplitScreen'

/* ── MatchDashboard — Live Match View ───────────────────────────────────────── */
export default function MatchDashboard({
    homeTeam,
    awayTeam,
    sport,
    matchSession,
    commentaryData,
    detection,
    setDetection,
    liveCommentary,
    onSendMatchEvent,
    onSendTacticalDetection,
    onGoBack,
    onPrepareNotes,
    buildingNotes,
    buildStatus,
    buildProgress,
}) {
    const [showNotes, setShowNotes] = useState(true)
    const [isSplitScreenActive, setIsSplitScreenActive] = useState(false)
    const [currentAnswer, setCurrentAnswer] = useState(null)
    const [isAiReady, setIsAiReady] = useState(true) // False while vision model warming up

    const handleSendMatchEvent = async (description) => {
        onSendMatchEvent?.(description)
    }

    const handleSendTacticalDetection = async (analysis) => {
        onSendTacticalDetection?.(analysis)
    }

    // Handle Q&A answer received (Story 2.2 + 2.3 + 2.4)
    const handleAnswerReceived = (answer) => {
        console.log('[MatchDashboard] Answer received:', answer)
        setCurrentAnswer(answer)
        setIsSplitScreenActive(true)

        // Auto-hide split screen after animation completes
        setTimeout(() => {
            setIsSplitScreenActive(false)
            setCurrentAnswer(null)
        }, 8000) // 8 seconds total (500ms timeout + 5-8s display)
    }

    // Handle Q&A question submission from MicButton
    const handleQuestionSubmit = async ({ text, confidence }) => {
        console.log('[MatchDashboard] Question submitted:', { text, confidence })
        // TODO: Wire up WebSocket query handler for Story 2.2
        // The answer will be received via WebSocket and trigger handleAnswerReceived
    }

    // Handle split screen dismissal
    const handleSplitScreenDismiss = () => {
        setIsSplitScreenActive(false)
        setCurrentAnswer(null)
    }

    return (
        <div className="match-dashboard">
            {/* SplitScreen - Story 2.3: Temporal Navigation */}
            {isSplitScreenActive && currentAnswer && (
                <SplitScreen
                    answer={currentAnswer}
                    isActive={isSplitScreenActive}
                    onDismiss={handleSplitScreenDismiss}
                >
                    <VideoCanvas
                        matchSession={matchSession}
                        homeTeam={homeTeam}
                        awayTeam={awayTeam}
                        sport={sport}
                        isLive={true}
                    />
                </SplitScreen>
            )}

            {/* Dashboard Header */}
            <header className="dashboard-header">
                <div className="dashboard-match-info">
                    <button className="btn btn-secondary btn-sm" onClick={onGoBack}>
                        ← Back
                    </button>
                    <span className="team-name home">{homeTeam}</span>
                    <span className="vs-text">vs</span>
                    <span className="team-name away">{awayTeam}</span>
                </div>
                <div className="dashboard-actions">
                    <button
                        className={`btn btn-primary btn-sm${buildingNotes ? ' loading' : ''}`}
                        onClick={onPrepareNotes}
                        disabled={buildingNotes}
                        title={buildProgress || ''}
                    >
                        {buildingNotes ? `📋 ${buildProgress || 'Preparing...'}` : commentaryData ? '📋 Refresh Notes' : '📋 Prepare Notes'}
                    </button>
                    <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => setShowNotes(!showNotes)}
                        disabled={!commentaryData}
                    >
                        {showNotes ? '📝 Hide Notes' : '📝 Show Notes'}
                    </button>
                </div>
            </header>

            {/* Main Dashboard - Full Width Content */}
            <div className="dashboard-full-width">
                {/* Top Row - Push to Talk + Video Player */}
                <div className="dashboard-row">
                    <div className="compact-ptt">
                        <PushToTalk
                            matchReady={true}
                            homeTeam={homeTeam}
                            awayTeam={awayTeam}
                            sport={sport}
                        />
                    </div>

                    {/* VideoCanvas - Fan Lens with tactical overlays */}
                    <VideoCanvas
                        matchSession={matchSession}
                        homeTeam={homeTeam}
                        awayTeam={awayTeam}
                        sport={sport}
                        onTacticalDetection={(analysis) => {
                            setDetection(analysis)
                            handleSendTacticalDetection(analysis)
                        }}
                        onCommentary={(msg) => {
                            if (msg.type === 'commentary') {
                                setLiveCommentary((prev) => [msg, ...prev].slice(0, 100))
                            }
                        }}
                    />

                    {/* MicButton - Voice Q&A input (Story 2.1) */}
                    <MicButton
                        onQuestionSubmit={handleQuestionSubmit}
                        isAiReady={isAiReady}
                        isSplitScreenActive={isSplitScreenActive}
                    />

                    {/* Tactical Detection Card (when available) */}
                    {detection && (
                        <div className="tactical-detection-card full-width">
                            <div className="detection-header">
                                <span className="detection-label">Latest Analysis</span>
                                <span className="detection-confidence">
                                    {Math.round(detection.confidence * 100)}% confidence
                                </span>
                            </div>
                            <div className="detection-value">{detection.tactical_label}</div>
                            {detection.key_observation && (
                                <div className="detection-observation">{detection.key_observation}</div>
                            )}
                        </div>
                    )}
                </div>

                {/* Bottom Row - Commentary + Events + MatchInsight (side by side) */}
                <div className="dashboard-bottom-row">
                    {/* Live Commentary Feed */}
                    <div className="bottom-panel">
                        <CommentaryFeed
                            messages={liveCommentary}
                            sendMatchEvent={handleSendMatchEvent}
                        />
                    </div>

                    {/* Event Feed */}
                    <div className="bottom-panel">
                        <EventFeed matchSession={matchSession} />
                    </div>

                    {/* MatchInsight - Trivia cards + Q&A */}
                    <div className="bottom-panel">
                        <MatchInsight
                            matchSession={matchSession}
                            homeTeam={homeTeam}
                            awayTeam={awayTeam}
                            sport={sport}
                            initialTrivia={commentaryData?.notes?.beats || []}
                        />
                    </div>
                </div>

                {/* Commentary Notes (collapsible, full width) */}
                {showNotes && commentaryData && (
                    <div className="notes-container full-width">
                        <CommentaryNotesViewer
                            data={commentaryData}
                            liveDetection={detection}
                        />
                    </div>
                )}
            </div>
        </div>
    )
}
