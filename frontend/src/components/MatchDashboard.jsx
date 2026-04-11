import { useState, useRef } from 'react'
import PushToTalk from './PushToTalk'
import TacticalOverlay from './TacticalOverlay'
import CommentaryFeed from './CommentaryFeed'
import EventFeed from './EventFeed'
import CommentaryNotesViewer from './CommentaryNotesViewer'

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
                    <span className="team-name home">{homeTeam}</span>
                    <span className="vs-text">vs</span>
                    <span className="team-name away">{awayTeam}</span>
                </div>
                <div className="dashboard-actions">
                    <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => setShowNotes(!showNotes)}
                    >
                        {showNotes ? '📝 Hide Notes' : '📝 Show Notes'}
                    </button>
                </div>
            </header>

            {/* Main Dashboard Grid */}
            <div className="dashboard-grid">
                {/* Left Column - Video & Pitch */}
                <div className="dashboard-column main">
                    {/* Push-to-Talk */}
                    <PushToTalk
                        matchReady={true}
                        homeTeam={homeTeam}
                        awayTeam={awayTeam}
                        sport={sport}
                    />

                    {/* Tactical Overlay / Video Player */}
                    <TacticalOverlay
                        sport={sport}
                        matchSession={matchSession}
                        detection={detection}
                        setDetection={setDetection}
                        sendMatchEvent={handleSendMatchEvent}
                        sendTacticalDetection={handleSendTacticalDetection}
                    />

                    {/* Commentary Notes (collapsible) */}
                    {showNotes && commentaryData && (
                        <CommentaryNotesViewer
                            data={commentaryData}
                            liveDetection={detection}
                        />
                    )}
                </div>

                {/* Right Column - Sidebar */}
                <div className="dashboard-column sidebar">
                    {/* Live Commentary Feed */}
                    <div className="sidebar-section">
                        <CommentaryFeed
                            messages={liveCommentary}
                            sendMatchEvent={handleSendMatchEvent}
                        />
                    </div>

                    {/* Event Feed */}
                    <div className="sidebar-section">
                        <EventFeed matchSession={matchSession} />
                    </div>
                </div>
            </div>
        </div>
    )
}
