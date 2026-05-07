import { useState } from 'react'
import { useLiveSession } from '@/contexts/LiveSessionContext'
import TopNavBar from '@/components/TopNavBar'
import VideoCanvas from '@/components/VideoCanvas'
import Teleprompter from '@/components/Teleprompter'
import ControlsTray from '@/components/ControlsTray'

export default function CommentatorDashboard() {
    const {
        homeTeam,
        awayTeam,
        sport,
        matchSession,
        commentaryData,
        buildingNotes,
        buildStatus,
        buildProgress,
        prepareNotes,
        liveCommentary,
        setLiveCommentary,
        detection,
        setDetection,
        isConnected,
        sendMatchEvent,
        sendTacticalDetection,
        updateSettings,
        updateLanguage,
    } = useLiveSession()

    // Local UI state
    const [settings, setSettings] = useState({ bias: 0, excitement: 0.5, knowledge_depth: 0.5 })
    const [language, setLanguage] = useState('en')
    const [showNotes, setShowNotes] = useState(true)

    // Handle settings change - update local state and send via context
    const handleSettingsChange = (newSettings) => {
        setSettings(newSettings)
        updateSettings(newSettings)
    }

    // Handle language change - update local state and send via context
    const handleLanguageChange = ({ language: newLanguage }) => {
        setLanguage(newLanguage)
        updateLanguage(newLanguage)
    }

    return (
        <div className="commentator-page-wrapper">
            {/* Top Navigation Bar */}
            <TopNavBar />

            {/* Main Content - 60/40 Split */}
            <div className="commentator-split-layout">
                {/* Video Section (60%) */}
                <div className="commentator-video-section">
                    <VideoCanvas
                        matchSession={matchSession}
                        homeTeam={homeTeam}
                        awayTeam={awayTeam}
                        sport={sport}
                        onTacticalDetection={(analysis) => {
                            setDetection?.(analysis)
                            sendTacticalDetection(analysis)
                        }}
                        onCommentary={(msg) => {
                            if (msg.type === 'commentary') {
                                setLiveCommentary?.((prev) => [msg, ...prev].slice(0, 100))
                            }
                        }}
                    />
                </div>

                {/* Teleprompter Section (40%) */}
                <div className="commentator-teleprompter-section">
                    {showNotes ? (
                        <Teleprompter
                            notesData={commentaryData}
                            buildingNotes={buildingNotes}
                            buildProgress={buildProgress}
                            buildStatus={buildStatus}
                            onGenerateNotes={prepareNotes}
                            liveDetection={detection}
                        />
                    ) : (
                        <div className="teleprompter-placeholder">
                            <p>Click "Show Notes" to view commentary notes</p>
                        </div>
                    )}
                </div>
            </div>

            {/* Controls Tray */}
            <div className="commentator-controls-area">
                <ControlsTray
                    homeTeam={homeTeam}
                    awayTeam={awayTeam}
                    onSettingsChange={handleSettingsChange}
                    onLanguageChange={handleLanguageChange}
                    onViewChange={(view) => {
                        if (view === 'fan') {
                            window.location.href = '/fan-lens'
                        }
                    }}
                    currentView="commentator"
                />
            </div>
        </div>
    )
}
