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
import Teleprompter from './Teleprompter'
import ControlsTray from './ControlsTray'
import { FanLensLayout } from '@/layouts/FanLensLayout'
import { CommentatorLayout } from '@/layouts/CommentatorLayout'

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
    setLiveCommentary,
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
    const [currentView, setCurrentView] = useState('fan') // 'fan' | 'commentator'
    const [settings, setSettings] = useState({ bias: 0, excitement: 0.5, knowledge_depth: 0.5 })
    const [language, setLanguage] = useState('en')

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

    // Handle settings change (Story 3.3)
    const handleSettingsChange = (message) => {
        console.log('[MatchDashboard] Settings update:', message)
        setSettings({
            bias: message.bias,
            excitement: message.excitement,
            knowledge_depth: message.knowledge_depth,
        })
        // Send to WebSocket (will be handled by parent App component)
        window.dispatchEvent(new CustomEvent('pitchai:settings', { detail: message }))
    }

    // Handle language change (Story 3.4)
    const handleLanguageChange = ({ language: newLanguage }) => {
        console.log('[MatchDashboard] Language switch:', newLanguage)
        setLanguage(newLanguage)
        window.dispatchEvent(new CustomEvent('pitchai:language', { detail: { language: newLanguage } }))
    }

    // Handle view toggle
    const handleViewChange = (newView) => {
        setCurrentView(newView)
    }

    // Handle beat highlight (Story 3.2)
    const handleBeatChange = ({ beatIndex, confidence, nextIndices }) => {
        console.log('[MatchDashboard] Beat changed:', { beatIndex, confidence, nextIndices })
        // Forward to Teleprompter via custom event
        window.dispatchEvent(new CustomEvent('pitchai:beat_highlight', {
            detail: { beatIndex, confidence, nextIndices }
        }))
    }

    // Fan Lens View - Use FanLensLayout
    if (currentView === 'fan') {
        return (
            <FanLensLayout
                controlsTray={
                    <ControlsTray
                        homeTeam={homeTeam}
                        awayTeam={awayTeam}
                        onSettingsChange={handleSettingsChange}
                        onLanguageChange={handleLanguageChange}
                        onViewChange={handleViewChange}
                        currentView={currentView}
                    />
                }
                triviaCards={
                    <MatchInsight
                        matchSession={matchSession}
                        homeTeam={homeTeam}
                        awayTeam={awayTeam}
                        sport={sport}
                        initialTrivia={commentaryData?.notes?.beats || []}
                    />
                }
                micButton={
                    <MicButton
                        onQuestionSubmit={handleQuestionSubmit}
                        isAiReady={isAiReady}
                        isSplitScreenActive={isSplitScreenActive}
                    />
                }
                questionChips={null}
            >
                {/* Main Video Canvas */}
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
            </FanLensLayout>
        )
    }

    // Commentator Dashboard View - Use CommentatorLayout
    return (
        <CommentatorLayout
            videoCanvas={
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
            }
            teleprompter={
                showNotes ? (
                    <Teleprompter
                        notesData={commentaryData}
                        buildingNotes={buildingNotes}
                        buildProgress={buildProgress}
                        buildStatus={buildStatus}
                        onGenerateNotes={onPrepareNotes}
                        liveDetection={detection}
                        onBeatChange={handleBeatChange}
                    />
                ) : (
                    <div className="teleprompter-placeholder flex items-center justify-center h-full text-text-secondary">
                        Click "Show Notes" or switch to Fan Lens view
                    </div>
                )
            }
            controlsTray={
                <ControlsTray
                    homeTeam={homeTeam}
                    awayTeam={awayTeam}
                    onSettingsChange={handleSettingsChange}
                    onLanguageChange={handleLanguageChange}
                    onViewChange={handleViewChange}
                    currentView={currentView}
                />
            }
        />
    )
}
