import { useState } from 'react'
import PushToTalk from './PushToTalk'
import CommentaryFeed from './CommentaryFeed'
import EventFeed from './EventFeed'
import CommentaryNotesViewer from './CommentaryNotesViewer'
import LiveVideoPlayer from './LiveVideoPlayer'

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

    const handleSendMatchEvent = async (description) => {
        onSendMatchEvent?.(description)
    }

    const handleSendTacticalDetection = async (analysis) => {
        onSendTacticalDetection?.(analysis)
    }

    return (
        <div className="match-dashboard">
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

                    {/* Live Video Player - Primary, Full Width */}
                    <LiveVideoPlayer
                        matchSession={matchSession}
                        onChunkAnalyzed={setDetection}
                        onCommentary={(msg) => {
                            if (msg.type === 'commentary') {
                                setLiveCommentary((prev) => [msg, ...prev].slice(0, 100))
                            }
                        }}
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

                {/* Bottom Row - Commentary + Events (side by side) */}
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
