import { useState, useEffect, useCallback } from 'react'
import { useLiveSession } from '@/contexts/LiveSessionContext'
import TopNavBar from '@/components/TopNavBar'
import VideoCanvas from '@/components/VideoCanvas'
import MatchInsight from '@/components/MatchInsight'
import MicButton from '@/components/MicButton'
import ControlsTray from '@/components/ControlsTray'
import SplitScreen from '@/components/SplitScreen'
import { FanLensLayout } from '@/layouts/FanLensLayout'

export default function FanLensBroadcast() {
    const {
        homeTeam,
        awayTeam,
        sport,
        matchSession,
        liveCommentary,
        setLiveCommentary,
        detection,
        setDetection,
        isConnected,
        sendMatchEvent,
        sendTacticalDetection,
        sendQuery,
        updateSettings,
        updateLanguage,
    } = useLiveSession()

    // Local UI state for settings and language
    const [settings, setSettings] = useState({ bias: 0, excitement: 0.5, knowledge_depth: 0.5 })
    const [language, setLanguage] = useState('en')
    const [triviaCards, setTriviaCards] = useState([])

    // SplitScreen state for Q&A temporal navigation (Story 5.8)
    const [splitScreenActive, setSplitScreenActive] = useState(false)
    const [qaAnswer, setQaAnswer] = useState(null)
    const [isDismissing, setIsDismissing] = useState(false) // Race condition fix

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

    // Handle question submission from MicButton - use context's sendQuery
    const handleQuestionSubmit = async ({ text, confidence }) => {
        await sendQuery(text, confidence)
    }

    // Listen for pitchai:qa_answer CustomEvent from WebSocket (Story 5.8)
    useEffect(() => {
        const handleQaAnswer = (e) => {
            const answer = e.detail
            console.log('[FanLensBroadcast] Q&A answer received:', answer)

            // Race condition fix: Ignore answer if currently dismissing previous split
            if (isDismissing) {
                console.log('[FanLensBroadcast] Ignoring Q&A answer: split screen is dismissing')
                return
            }

            setQaAnswer(answer)
            setSplitScreenActive(true)
            setIsDismissing(false) // Reset dismissing state on new answer
        }

        window.addEventListener('pitchai:qa_answer', handleQaAnswer)
        return () => window.removeEventListener('pitchai:qa_answer', handleQaAnswer)
    }, [isDismissing])

    // Handle SplitScreen dismissal with race condition protection
    const handleSplitScreenDismiss = useCallback(() => {
        setIsDismissing(true) // Block new answers during dismissal
        setSplitScreenActive(false)
        setQaAnswer(null)
        // Dispatch pitchai:split_resolved event (Story 5.8 AC)
        window.dispatchEvent(new CustomEvent('pitchai:split_resolved', { detail: { dismissed: true } }))

        // Reset dismissing state after animation completes (300ms matches ANIMATION_DURATION)
        setTimeout(() => {
            setIsDismissing(false)
        }, 300)
    }, [])

    return (
        <FanLensLayout
            controlsTray={
                <ControlsTray
                    homeTeam={homeTeam}
                    awayTeam={awayTeam}
                    onSettingsChange={handleSettingsChange}
                    onLanguageChange={handleLanguageChange}
                    onViewChange={(view) => {
                        if (view === 'commentator') {
                            window.location.href = '/commentator'
                        }
                    }}
                    currentView="fan"
                />
            }
            triviaCards={
                <MatchInsight
                    matchSession={matchSession}
                    homeTeam={homeTeam}
                    awayTeam={awayTeam}
                    sport={sport}
                    initialTrivia={[]}
                />
            }
            micButton={
                <MicButton
                    onQuestionSubmit={handleQuestionSubmit}
                    isAiReady={isConnected}
                    isSplitScreenActive={splitScreenActive}
                />
            }
            splitScreen={
                <SplitScreen
                    answer={qaAnswer}
                    isActive={splitScreenActive}
                    onDismiss={handleSplitScreenDismiss}
                >
                    {/* Left panel content (live video) passed through */}
                </SplitScreen>
            }
        >
            {/* Top Navigation Bar */}
            <TopNavBar />

            {/* Video Canvas */}
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
        </FanLensLayout>
    )
}
