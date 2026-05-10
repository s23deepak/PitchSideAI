import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'
import { DEMO_FIXTURE, getAllTriviaCards, getSuggestedQuestions } from '../lib/demo-seed'

/* ── Demo Mode Context (Story 4.2: Self-Guided Demo) ────────────────────────── */

const DemoModeContext = createContext(null)

/**
 * DemoModeProvider - Context provider for self-guided demo mode
 * Manages:
 * - Demo mode state (isDemoMode, isNarratorMode)
 * - First-visit tracking
 * - Trivia queue scheduling
 * - Feature trial tracking
 */
export function DemoModeProvider({ children }) {
    const [featuresTried, setFeaturesTried] = useState(new Set())
    const [triviaQueue, setTriviaQueue] = useState([])
    const [hasSeenFirstVisit, setHasSeenFirstVisit] = useState(false)
    // Patch #2: Use ref to track shown cards separately from state (prevents race condition)
    const shownCardsRef = useRef(new Set())

    // Initialize demo state
    useEffect(() => {
        // Check if first visit has been seen
        const firstVisitSeen = localStorage.getItem('pitchsideai_first_visit_seen') === 'true'
        setHasSeenFirstVisit(firstVisitSeen)

        // Initialize trivia queue (reset _shown flags)
        const cards = getAllTriviaCards().map(card => ({ ...card, _shown: false }))
        setTriviaQueue(cards)
    }, [])

    // Mark a feature as tried
    const markFeatureTried = useCallback((feature) => {
        setFeaturesTried(prev => new Set(prev).add(feature))
    }, [])

    // Check if a feature has been tried
    const hasFeatureBeenTried = useCallback((feature) => {
        return featuresTried.has(feature)
    }, [featuresTried])

    // Get next trivia card for display (Patch #2: immutable update with ref)
    const getNextTriviaCard = useCallback((videoTimeMs) => {
        const sortedCards = [...triviaQueue].sort((a, b) => a.timestampMs - b.timestampMs)

        for (const card of sortedCards) {
            if (videoTimeMs >= card.timestampMs && !shownCardsRef.current.has(card.timestampMs)) {
                // Mark as shown using ref (prevents race condition)
                shownCardsRef.current.add(card.timestampMs)
                return card
            }
        }
        return null
    }, [triviaQueue])

    // Get all trivia cards
    const allTriviaCards = triviaQueue

    // Get suggested questions
    const suggestedQuestions = getSuggestedQuestions()

    const value = {
        isDemoMode: true,
        isNarratorMode: false,
        hasSeenFirstVisit,
        triviaQueue: allTriviaCards,
        suggestedQuestions,
        featuresTried: Array.from(featuresTried),
        markFeatureTried,
        hasFeatureBeenTried,
        getNextTriviaCard,
        fixture: DEMO_FIXTURE,
    }

    return (
        <DemoModeContext.Provider value={value}>
            {children}
        </DemoModeContext.Provider>
    )
}

/**
 * Hook to access demo mode context
 * @returns {object} Demo mode context value
 */
export function useDemoMode() {
    const context = useContext(DemoModeContext)
    if (!context) {
        throw new Error('useDemoMode must be used within a DemoModeProvider')
    }
    return context
}
