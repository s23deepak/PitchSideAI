import { useState, useRef, useEffect, useCallback } from 'react'

const BACKEND = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

/**
 * MatchInsight — Fan Lens trivia cards and guided Q&A discovery.
 *
 * Displays trivia cards in a priority queue with suggested question chips.
 * Users can tap chips to instantly ask questions and see answers.
 *
 * Features:
 * - Priority queue (max 5 cards, sorted by confidence desc)
 * - Suggested question chips ("Ask about this", "Related tactics", "Player stats")
 * - Q&A mode with smooth transitions
 * - Auto-dismiss timer (15s for non-interacted cards)
 * - Empty state with placeholder + starter questions
 */
export default function MatchInsight({
    matchSession,
    homeTeam = 'Home',
    awayTeam = 'Away',
    sport = 'soccer',
    onQuery,
    onAnswer,
    initialTrivia = [],
}) {
    // Card queue state
    const [triviaQueue, setTriviaQueue] = useState([])
    const [currentCardIndex, setCurrentCardIndex] = useState(0)
    const [qaMode, setQaMode] = useState(false)
    const [currentQuestion, setCurrentQuestion] = useState('')
    const [currentAnswer, setCurrentAnswer] = useState('')
    const [isLoadingAnswer, setIsLoadingAnswer] = useState(false)
    const [wsConnected, setWsConnected] = useState(false)

    const wsRef = useRef(null)
    const dismissTimer = useRef(null)

    // Question chip definitions
    const QUESTION_CHIPS = [
        { label: 'Ask about this', prefix: 'Tell me more about:' },
        { label: 'Related tactics', prefix: 'What tactical patterns led to this?' },
        { label: 'Player stats', prefix: 'Show me stats for' },
        { label: 'Historical context', prefix: 'Has this happened before this season?' },
    ]

    // Starter questions for empty state
    const STARTER_QUESTIONS = [
        `What's ${homeTeam}'s recent form?`,
        `Key tactical battle to watch?`,
        `Head-to-head history?`,
    ]

    // Connect to WebSocket for trivia/answer updates
    const connectWebSocket = useCallback(() => {
        const wsUrl = BACKEND.replace(/^http/, 'ws') + '/ws/live'
        const ws = new WebSocket(wsUrl)
        wsRef.current = ws

        ws.onopen = () => {
            ws.send(JSON.stringify({
                type: 'init',
                home_team: homeTeam,
                away_team: awayTeam,
                match_session: matchSession,
                sport: sport,
            }))
            setWsConnected(true)
        }

        ws.onmessage = (e) => {
            if (typeof e.data !== 'string') return
            try {
                const msg = JSON.parse(e.data)

                switch (msg.type) {
                    case 'ready':
                        setWsConnected(true)
                        break

                    case 'trivia_card':
                        // Add to queue with priority sorting
                        const newCard = {
                            id: `trivia-${Date.now()}-${Math.random()}`,
                            text: msg.text,
                            source: msg.source,
                            confidence: msg.confidence,
                            timestamp: Date.now(),
                            displayDurationMs: msg.display_duration_ms || (msg.confidence >= 0.8 ? 5000 : 3000),
                            fadeInMs: msg.fade_in_ms || 400,
                            fadeOutMs: msg.fade_out_ms || 400,
                        }
                        setTriviaQueue(prev => {
                            const updated = [...prev, newCard]
                            // Sort by confidence desc, then by recency
                            updated.sort((a, b) => {
                                if (b.confidence !== a.confidence) {
                                    return b.confidence - a.confidence
                                }
                                return b.timestamp - a.timestamp
                            })
                            // Keep max 5 cards
                            return updated.slice(0, 5)
                        })
                        break

                    case 'answer':
                        // Display answer in QA mode
                        setCurrentAnswer(msg.text || msg.answer)
                        setIsLoadingAnswer(false)
                        onAnswer?.(msg)
                        break

                    case 'error':
                        console.error('MatchInsight error:', msg.message)
                        setIsLoadingAnswer(false)
                        break
                }
            } catch (err) {
                console.warn('WS parse error:', err)
            }
        }

        ws.onerror = (err) => {
            console.error('WebSocket error:', err)
            setWsConnected(false)
        }

        ws.onclose = () => {
            wsRef.current = null
            setWsConnected(false)
        }
    }, [homeTeam, awayTeam, matchSession, sport, onAnswer])

    // Initialize WebSocket connection
    useEffect(() => {
        connectWebSocket()
        return () => {
            wsRef.current?.close()
        }
    }, [connectWebSocket])

    // Load initial trivia from props (pre-generated notes)
    useEffect(() => {
        if (initialTrivia && initialTrivia.length > 0) {
            const starterCards = initialTrivia
                .filter(beat => beat.confidence > 0.7)
                .slice(0, 2)
                .map((beat, i) => ({
                    id: `starter-${i}`,
                    text: beat.text,
                    source: beat.source,
                    confidence: beat.confidence,
                    timestamp: Date.now() - i * 1000, // Stagger timestamps
                    displayDurationMs: 15000, // Longer for starter cards
                    fadeInMs: 400,
                    fadeOutMs: 400,
                    isStarter: true,
                }))
            setTriviaQueue(prev => [...starterCards, ...prev].slice(0, 5))
        }
    }, [initialTrivia])

    // Auto-dismiss timer for current card
    useEffect(() => {
        if (triviaQueue.length > 0 && !qaMode) {
            const currentCard = triviaQueue[currentCardIndex]
            if (currentCard && !currentCard.isStarter) {
                if (dismissTimer.current) clearTimeout(dismissTimer.current)
                dismissTimer.current = setTimeout(() => {
                    // Auto-advance to next card
                    setCurrentCardIndex(prev => {
                        const next = prev + 1
                        return next >= triviaQueue.length ? 0 : next
                    })
                }, currentCard.displayDurationMs)
            }
        }
        return () => {
            if (dismissTimer.current) clearTimeout(dismissTimer.current)
        }
    }, [triviaQueue, currentCardIndex, qaMode])

    // Handle question chip tap
    const handleQuestionChipTap = (chip) => {
        const currentCard = triviaQueue[currentCardIndex]
        if (!currentCard) return

        let query = chip.prefix
        if (chip.prefix === 'Tell me more about:') {
            query = `${chip.prefix} ${currentCard.text.substring(0, 100)}`
        } else if (chip.prefix === 'Show me stats for') {
            // Try to extract player name from card text (simple heuristic)
            const playerMatch = currentCard.text.match(/^([A-Z][a-z]+(?: [A-Z][a-z]+)?)/)
            const playerName = playerMatch ? playerMatch[1] : 'this player'
            query = `${chip.prefix} ${playerName}`
        }

        setCurrentQuestion(query)
        setQaMode(true)
        setIsLoadingAnswer(true)
        setCurrentAnswer('')

        // Send query over WebSocket
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
                type: 'query',
                question: query,
                match_session: matchSession,
            }))
        }

        onQuery?.(query)
    }

    // Handle starter question tap
    const handleStarterQuestionTap = (question) => {
        setCurrentQuestion(question)
        setQaMode(true)
        setIsLoadingAnswer(true)
        setCurrentAnswer('')

        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
                type: 'query',
                question: question,
                match_session: matchSession,
            }))
        }

        onQuery?.(question)
    }

    // Navigate to next card
    const handleNextCard = () => {
        setCurrentCardIndex(prev => {
            const next = prev + 1
            return next >= triviaQueue.length ? 0 : next
        })
    }

    // Navigate to previous card
    const handlePrevCard = () => {
        setCurrentCardIndex(prev => {
            const prevIndex = prev - 1
            return prevIndex < 0 ? triviaQueue.length - 1 : prevIndex
        })
    }

    // Exit QA mode
    const handleBackToTrivia = () => {
        setQaMode(false)
        setCurrentQuestion('')
        setCurrentAnswer('')
    }

    // Remove current card from queue
    const handleDismissCard = () => {
        setTriviaQueue(prev => {
            const updated = prev.filter((_, i) => i !== currentCardIndex)
            return updated
        })
        if (currentCardIndex >= triviaQueue.length - 1) {
            setCurrentCardIndex(0)
        }
    }

    const currentCard = triviaQueue[currentCardIndex]

    return (
        <div className="match-insight" style={{
            background: 'var(--surface, #1e293b)',
            borderRadius: 12,
            padding: 16,
            border: '1px solid var(--border-color, #334155)',
            minHeight: 280,
        }}>
            {/* Header */}
            <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 12,
            }}>
                <div>
                    <h3 style={{ margin: 0, fontSize: 14, color: 'var(--text-primary, #f1f5f9)' }}>
                        Match Insights
                    </h3>
                    <span style={{ fontSize: 10, color: 'var(--text-muted, #94a3b8)' }}>
                        {triviaQueue.length} {triviaQueue.length === 1 ? 'card' : 'cards'} in queue
                    </span>
                </div>
                {wsConnected && (
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 4,
                        fontSize: 10,
                        color: 'var(--text-muted, #94a3b8)',
                    }}>
                        <div style={{
                            width: 6,
                            height: 6,
                            borderRadius: '50%',
                            background: '#22c55e',
                            animation: 'pulse 1.5s infinite',
                        }}
                        />
                        Live
                    </div>
                )}
            </div>

            {/* Content */}
            {qaMode ? (
                /* Q&A Mode */
                <div className="qa-mode">
                    <div style={{
                        background: 'rgba(59, 130, 246, 0.1)',
                        borderRadius: 8,
                        padding: 12,
                        marginBottom: 12,
                        border: '1px solid rgba(59, 130, 246, 0.2)',
                    }}>
                        <div style={{
                            fontSize: 10,
                            color: '#60a5fa',
                            fontWeight: 600,
                            textTransform: 'uppercase',
                            letterSpacing: 0.5,
                            marginBottom: 4,
                        }}>
                            Question
                        </div>
                        <div style={{ fontSize: 13, color: 'var(--text-primary, #f1f5f9)', lineHeight: 1.4 }}>
                            {currentQuestion}
                        </div>
                    </div>

                    <div style={{
                        background: 'rgba(34, 197, 94, 0.1)',
                        borderRadius: 8,
                        padding: 12,
                        border: '1px solid rgba(34, 197, 94, 0.2)',
                    }}>
                        <div style={{
                            fontSize: 10,
                            color: '#4ade80',
                            fontWeight: 600,
                            textTransform: 'uppercase',
                            letterSpacing: 0.5,
                            marginBottom: 4,
                        }}>
                            Answer
                        </div>
                        {isLoadingAnswer ? (
                            <div style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 8,
                                fontSize: 13,
                                color: 'var(--text-muted, #94a3b8)',
                            }}>
                                <div className="spinner" style={{
                                    width: 14,
                                    height: 14,
                                    border: '2px solid rgba(255,255,255,0.1)',
                                    borderTopColor: '#4ade80',
                                    borderRadius: '50%',
                                    animation: 'spin 1s linear infinite',
                                }}
                                />
                                Generating answer...
                            </div>
                        ) : (
                            <div style={{ fontSize: 13, color: 'var(--text-primary, #f1f5f9)', lineHeight: 1.4 }}>
                                {currentAnswer || 'Waiting for answer...'}
                            </div>
                        )}
                    </div>

                    <button
                        className="btn btn-secondary btn-sm"
                        onClick={handleBackToTrivia}
                        style={{ marginTop: 12, width: '100%' }}
                    >
                        ← Back to trivia
                    </button>
                </div>
            ) : triviaQueue.length > 0 && currentCard ? (
                /* Trivia Card Display */
                <div className="trivia-display">
                    <div
                        className="trivia-card"
                        style={{
                            background: 'linear-gradient(135deg, rgba(15,23,42,0.95) 0%, rgba(30,41,59,0.9) 100%)',
                            borderRadius: 12,
                            padding: 16,
                            border: '1px solid rgba(148,163,184,0.2)',
                            boxShadow: '0 10px 40px rgba(0,0,0,0.4)',
                            animation: `slideUp ${currentCard.fadeInMs}ms ease-out`,
                        }}
                    >
                        {/* Confidence badge */}
                        <div style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            marginBottom: 8,
                        }}>
                            <span style={{
                                background: currentCard.confidence >= 0.8
                                    ? 'rgba(34, 197, 94, 0.2)'
                                    : 'rgba(234, 179, 8, 0.2)',
                                color: currentCard.confidence >= 0.8 ? '#4ade80' : '#fbbf24',
                                padding: '2px 8px',
                                borderRadius: 12,
                                fontSize: 10,
                                fontWeight: 600,
                            }}>
                                {currentCard.confidence >= 0.8 ? 'High confidence' : 'Medium confidence'}
                            </span>
                            {currentCard.source && (
                                <span style={{
                                    background: 'rgba(59, 130, 246, 0.2)',
                                    color: '#60a5fa',
                                    padding: '2px 8px',
                                    borderRadius: 12,
                                    fontSize: 10,
                                }}>
                                    {currentCard.source}
                                </span>
                            )}
                        </div>

                        {/* Card text */}
                        <div style={{
                            fontSize: 14,
                            color: '#e2e8f0',
                            lineHeight: 1.6,
                            marginBottom: 12,
                        }}>
                            {currentCard.text}
                        </div>

                        {/* Navigation */}
                        {triviaQueue.length > 1 && (
                            <div style={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                marginTop: 8,
                                paddingTop: 12,
                                borderTop: '1px solid rgba(148,163,184,0.1)',
                            }}>
                                <button
                                    className="btn btn-secondary btn-sm"
                                    onClick={handlePrevCard}
                                    style={{ padding: '4px 10px', fontSize: 11 }}
                                >
                                    ← Prev
                                </button>
                                <span style={{ fontSize: 10, color: 'var(--text-muted, #94a3b8)' }}>
                                    {currentCardIndex + 1} / {triviaQueue.length}
                                </span>
                                <button
                                    className="btn btn-secondary btn-sm"
                                    onClick={handleNextCard}
                                    style={{ padding: '4px 10px', fontSize: 11 }}
                                >
                                    Next →
                                </button>
                            </div>
                        )}
                    </div>

                    {/* Question Chips */}
                    <div style={{ marginTop: 12 }}>
                        <div style={{
                            fontSize: 10,
                            color: 'var(--text-muted, #94a3b8)',
                            fontWeight: 600,
                            textTransform: 'uppercase',
                            letterSpacing: 0.5,
                            marginBottom: 8,
                        }}>
                            Ask about this
                        </div>
                        <div style={{
                            display: 'flex',
                            flexWrap: 'wrap',
                            gap: 6,
                        }}>
                            {QUESTION_CHIPS.map((chip, i) => (
                                <button
                                    key={i}
                                    className="question-chip"
                                    onClick={() => handleQuestionChipTap(chip)}
                                    style={{
                                        background: 'rgba(59, 130, 246, 0.15)',
                                        border: '1px solid rgba(59, 130, 246, 0.3)',
                                        borderRadius: 16,
                                        padding: '5px 12px',
                                        fontSize: 11,
                                        color: '#60a5fa',
                                        cursor: 'pointer',
                                        transition: 'all 150ms',
                                    }}
                                    onMouseOver={(e) => {
                                        e.currentTarget.style.background = 'rgba(59, 130, 246, 0.25)'
                                    }}
                                    onMouseOut={(e) => {
                                        e.currentTarget.style.background = 'rgba(59, 130, 246, 0.15)'
                                    }}
                                >
                                    {chip.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Dismiss button */}
                    <button
                        className="btn btn-secondary btn-sm"
                        onClick={handleDismissCard}
                        style={{
                            marginTop: 12,
                            width: '100%',
                            fontSize: 11,
                            padding: '6px 0',
                        }}
                    >
                        Dismiss this card
                    </button>
                </div>
            ) : (
                /* Empty State */
                <div className="empty-state" style={{
                    textAlign: 'center',
                    padding: 32,
                    color: 'var(--text-muted, #94a3b8)',
                }}>
                    <div style={{ fontSize: 40, marginBottom: 12 }}>💡</div>
                    <div style={{
                        fontSize: 14,
                        fontWeight: 600,
                        color: 'var(--text-primary, #f1f5f9)',
                        marginBottom: 4,
                    }}>
                        Match Insights
                    </div>
                    <div style={{
                        fontSize: 12,
                        lineHeight: 1.5,
                        marginBottom: 16,
                    }}>
                        Trivia cards will appear here as the action unfolds.
                        Tap on any card to explore deeper insights.
                    </div>

                    {/* Starter questions */}
                    <div style={{
                        fontSize: 10,
                        color: 'var(--text-muted, #94a3b8)',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: 0.5,
                        marginBottom: 8,
                    }}>
                        Or ask about:
                    </div>
                    <div style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 6,
                    }}>
                        {STARTER_QUESTIONS.map((question, i) => (
                            <button
                                key={i}
                                className="starter-question"
                                onClick={() => handleStarterQuestionTap(question)}
                                style={{
                                    background: 'rgba(148, 163, 184, 0.1)',
                                    border: '1px solid rgba(148, 163, 184, 0.2)',
                                    borderRadius: 8,
                                    padding: '8px 12px',
                                    fontSize: 11,
                                    color: 'var(--text-primary, #f1f5f9)',
                                    cursor: 'pointer',
                                    textAlign: 'left',
                                    transition: 'all 150ms',
                                }}
                                onMouseOver={(e) => {
                                    e.currentTarget.style.background = 'rgba(148, 163, 184, 0.2)'
                                    e.currentTarget.style.borderColor = 'rgba(148, 163, 184, 0.3)'
                                }}
                                onMouseOut={(e) => {
                                    e.currentTarget.style.background = 'rgba(148, 163, 184, 0.1)'
                                    e.currentTarget.style.borderColor = 'rgba(148, 163, 184, 0.2)'
                                }}
                            >
                                {question}
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {/* CSS Animations */}
            <style>{`
                @keyframes pulse {
                    0%, 100% { opacity: 1; transform: scale(1); }
                    50% { opacity: 0.5; transform: scale(1.1); }
                }
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
                @keyframes slideUp {
                    from { opacity: 0; transform: translateY(20px); }
                    to { opacity: 1; transform: translateY(0); }
                }
            `}</style>
        </div>
    )
}
