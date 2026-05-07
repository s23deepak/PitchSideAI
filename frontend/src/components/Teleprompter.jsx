import { useState, useRef, useEffect, useCallback } from 'react'

/**
 * Teleprompter — Story 3.1 + Story 3.2: Static Notes Display + Vision-Synced Highlighting
 *
 * Displays pre-generated commentary notes in a scrollable panel.
 * - Tabbed Mode (pre-match): 5 sections as tabs
 * - Long-Sheet Mode (live): continuous scroll with auto-highlighting
 * - Progress bar during generation
 * - Auto-scroll to keep current beat at ~30% from top (smooth 300ms)
 * - Highlight current beat: Amber 400 bg at 15%, 3px left border, ▶ marker
 * - Show next 3 lines below (fading opacity), previous line above
 * - Hold Mode: manual scroll cancels auto-scroll, shows "Back to live"/"Catch up" button
 * - Confidence gating: don't highlight beats with confidence < 0.7
 */
export default function Teleprompter({
    notesData,
    buildingNotes,
    buildProgress,
    buildStatus,
    onGenerateNotes,
    liveDetection,
    onBeatChange, // Used for beat change notifications to parent
}) {
    const [activeTab, setActiveTab] = useState('match_info')
    const [isLongSheetMode, setIsLongSheetMode] = useState(false)
    const [isHoldMode, setIsHoldMode] = useState(false)
    const [highlightedBeatIndex, setHighlightedBeatIndex] = useState(null)
    const [beatConfidence, setBeatConfidence] = useState(0)
    const scrollContainerRef = useRef(null)
    const beatRefs = useRef({}) // Map of beat index → DOM element
    const userScrollTimeoutRef = useRef(null)
    const autoScrollAnimationRef = useRef(null)
    const isMountedRef = useRef(true) // Fix #4: Prevent setState on unmounted component

    // Switch to long-sheet mode when match is live
    useEffect(() => {
        if (liveDetection) {
            setIsLongSheetMode(true)
        }
    }, [liveDetection])

    // Listen for beat highlight messages from WebSocket (via parent)
    useEffect(() => {
        const handleBeatHighlight = (e) => {
            const { beatIndex, confidence, nextIndices } = e.detail
            console.log('[Teleprompter] Beat highlight received:', { beatIndex, confidence, nextIndices })

            // Confidence gating: don't highlight below 0.6 threshold (Story 5.6 AC)
            if (confidence < 0.6) {
                console.log('[Teleprompter] Skipping highlight: confidence too low', confidence)
                return
            }

            setHighlightedBeatIndex(beatIndex)
            setBeatConfidence(confidence)

            // Auto-scroll to keep beat at ~30% from top (if not in hold mode)
            if (!isHoldMode && beatRefs.current[beatIndex]) {
                scrollToBeat(beatIndex)
            }

            // Notify parent of beat change
            onBeatChange?.({ beatIndex, confidence, nextIndices })
        }

        window.addEventListener('pitchai:beat_highlight', handleBeatHighlight)
        return () => window.removeEventListener('pitchai:beat_highlight', handleBeatHighlight)
    }, [isHoldMode, onBeatChange])

    // Reset beatConfidence when notesData changes (fix #6)
    useEffect(() => {
        setBeatConfidence(0)
        setHighlightedBeatIndex(null)
    }, [notesData])

    // Cleanup effect for memory leaks (fix #4, #5)
    useEffect(() => {
        isMountedRef.current = true
        return () => {
            isMountedRef.current = false
            // Clear user scroll timeout
            if (userScrollTimeoutRef.current) {
                clearTimeout(userScrollTimeoutRef.current)
            }
            // Cancel any pending scroll animation
            if (autoScrollAnimationRef.current) {
                cancelAnimationFrame(autoScrollAnimationRef.current)
            }
            // Clear beat refs to prevent stale references
            beatRefs.current = {}
        }
    }, [])

    // Scroll to a specific beat with smooth animation
    const scrollToBeat = useCallback((beatIndex) => {
        const container = scrollContainerRef.current
        const beatElement = beatRefs.current[beatIndex]

        if (!container || !beatElement) return

        // Calculate scroll position to keep beat at ~30% from top
        const containerRect = container.getBoundingClientRect()
        const beatRect = beatElement.getBoundingClientRect()
        let targetScroll = container.scrollTop + beatRect.top - containerRect.top - (containerRect.height * 0.3)

        // Bounds clamping (fix #21)
        const maxScroll = container.scrollHeight - container.clientHeight
        targetScroll = Math.max(0, Math.min(targetScroll, maxScroll))

        // Smooth scroll with 300ms animation
        if (autoScrollAnimationRef.current) {
            cancelAnimationFrame(autoScrollAnimationRef.current)
        }

        const startScroll = container.scrollTop
        const delta = targetScroll - startScroll
        const duration = 300
        const startTime = performance.now()

        const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3)

        const animateScroll = (currentTime) => {
            // Fix #4: Check if component is still mounted before updating scrollTop
            if (!isMountedRef.current || !container) return

            const elapsed = currentTime - startTime
            const progress = Math.min(elapsed / duration, 1)
            const easedProgress = easeOutCubic(progress)

            container.scrollTop = startScroll + delta * easedProgress

            if (progress < 1) {
                autoScrollAnimationRef.current = requestAnimationFrame(animateScroll)
            }
        }

        autoScrollAnimationRef.current = requestAnimationFrame(animateScroll)
    }, [])

    // Handle manual scroll — enter hold mode if within 500ms of auto-scroll
    const handleScroll = useCallback(() => {
        if (!isLongSheetMode) return

        // Clear any pending timeout
        if (userScrollTimeoutRef.current) {
            clearTimeout(userScrollTimeoutRef.current)
        }

        // If user scrolls during auto-scroll animation, cancel auto-scroll and enter hold mode
        if (autoScrollAnimationRef.current && highlightedBeatIndex !== null) {
            cancelAnimationFrame(autoScrollAnimationRef.current)
            setIsHoldMode(true)
            console.log('[Teleprompter] Hold mode activated: user scrolled during auto-scroll')
        }

        // Set timeout to potentially exit hold mode after user stops scrolling
        userScrollTimeoutRef.current = setTimeout(() => {
            // Check if user is near the current beat
            if (highlightedBeatIndex !== null && beatRefs.current[highlightedBeatIndex]) {
                const container = scrollContainerRef.current
                const beatElement = beatRefs.current[highlightedBeatIndex]
                const containerRect = container.getBoundingClientRect()
                const beatRect = beatElement.getBoundingClientRect()
                const distance = Math.abs(beatRect.top - containerRect.top - (containerRect.height * 0.3))

                // If within 200px of target, exit hold mode (increased from 100px for better UX)
                if (distance < 200) {
                    setIsHoldMode(false)
                    console.log('[Teleprompter] Hold mode deactivated: user near current beat')
                }
            }
        }, 500)
    }, [isLongSheetMode, highlightedBeatIndex])

    // Return to live (exit hold mode and scroll to current beat)
    const handleReturnToLive = useCallback(() => {
        if (highlightedBeatIndex !== null) {
            scrollToBeat(highlightedBeatIndex)
            setIsHoldMode(false)
            console.log('[Teleprompter] Returned to live: scrolling to beat', highlightedBeatIndex)
        }
    }, [highlightedBeatIndex, scrollToBeat])

    // Fix #1: Compute hold mode button label without stale closure
    const holdModeButtonLabel = useCallback(() => {
        if (highlightedBeatIndex === null || !scrollContainerRef.current || !beatRefs.current[highlightedBeatIndex]) {
            return 'Back to live'
        }
        const container = scrollContainerRef.current
        const beatElement = beatRefs.current[highlightedBeatIndex]
        const containerRect = container.getBoundingClientRect()
        const beatRect = beatElement.getBoundingClientRect()
        // If beat is below viewport top, user scrolled up → "Back to live"
        // If beat is above viewport top, user scrolled past → "Catch up"
        return beatRect.top > containerRect.top ? 'Back to live' : 'Catch up'
    }, [highlightedBeatIndex])

    // Parse notes into beats for long-sheet mode
    // Fix: Add fallback for markdown-only notes (no beats structure)
    const parseBeats = () => {
        if (!notesData) return []

        // If beats array exists, use it
        if (notesData.beats && Array.isArray(notesData.beats)) {
            return notesData.beats
        }

        // Fallback: parse markdown into pseudo-beats
        if (notesData.markdown_notes) {
            const lines = notesData.markdown_notes.split('\n').filter(line => line.trim())
            return lines.map((line, index) => ({
                text: line.replace(/^[#\-*]\s*/, ''),
                source: 'markdown',
                confidence: 1.0, // Fix #5: Markdown fallback should highlight (bypasses 0.6 gating)
                event_tags: [],
                section: 'general',
                index,
            }))
        }

        return []
    }

    const beats = parseBeats()

    // Parse notes into sections for tabbed mode
    const parseSections = () => {
        if (!notesData?.markdown_notes) return []

        const markdown = notesData.markdown_notes
        const sectionMarkers = [
            { id: 'match_info', label: 'Match Info', regex: /^##\s+Match\s+Info/im },
            { id: 'home_team', label: 'Home Team', regex: /^##\s+Home\s+Team/im },
            { id: 'away_team', label: 'Away Team', regex: /^##\s+Away\s+Team/im },
            { id: 'tactical', label: 'Tactical', regex: /^##\s+Tactical/im },
            { id: 'historical', label: 'Historical', regex: /^##\s+Historical/im },
        ]

        const sections = []
        let lastIndex = 0

        sectionMarkers.forEach((marker, idx) => {
            const match = marker.regex.exec(markdown)
            if (match) {
                const startIdx = match.index
                const nextMarker = sectionMarkers[idx + 1]
                const nextMatch = nextMarker ? nextMarker.regex.exec(markdown) : null
                const endIdx = nextMatch ? nextMatch.index : markdown.length

                sections.push({
                    id: marker.id,
                    label: marker.label,
                    content: markdown.slice(startIdx, endIdx).trim(),
                })
            }
        })

        return sections.length > 0 ? sections : [{ id: 'full', label: 'Full Notes', content: markdown }]
    }

    const sections = parseSections()

    // Render markdown with basic formatting
    const renderMarkdown = (text) => {
        if (!text) return null

        const lines = text.split('\n')
        return lines.map((line, idx) => {
            const trimmed = line.trim()
            if (!trimmed) return <br key={idx} />

            // Headers
            if (trimmed.startsWith('## ')) {
                return <h3 key={idx} className="teleprompter-h3">{trimmed.slice(3)}</h3>
            }
            if (trimmed.startsWith('### ')) {
                return <h4 key={idx} className="teleprompter-h4">{trimmed.slice(4)}</h4>
            }

            // List items
            if (trimmed.startsWith('- ')) {
                return (
                    <li key={idx} className="teleprompter-li">
                        {renderInlineFormatting(trimmed.slice(2))}
                    </li>
                )
            }

            // Bold/italic inline formatting
            return (
                <p key={idx} className="teleprompter-p">
                    {renderInlineFormatting(trimmed)}
                </p>
            )
        })
    }

    const renderInlineFormatting = (text) => {
        const segments = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g).filter(Boolean)
        return segments.map((segment, idx) => {
            if (segment.startsWith('**') && segment.endsWith('**')) {
                return <strong key={idx}>{segment.slice(2, -2)}</strong>
            }
            if (segment.startsWith('*') && segment.endsWith('*')) {
                return <em key={idx}>{segment.slice(1, -1)}</em>
            }
            return segment
        })
    }

    // Render a single beat with highlighting
    const renderBeat = useCallback((beat, index) => {
        const isHighlighted = index === highlightedBeatIndex
        const isNextBeat = beatConfidence >= 0.6 && index > highlightedBeatIndex && index <= highlightedBeatIndex + 3
        const isPreviousBeat = index === highlightedBeatIndex - 1
        const nextOffset = isNextBeat ? index - highlightedBeatIndex : 0

        // Confidence gating: don't highlight below 0.6 (Story 5.6 AC)
        const shouldHighlight = isHighlighted && beatConfidence >= 0.6

        // Fix #16: Keyboard navigation for accessibility
        const handleBeatKeyDown = (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                // Select this beat for focus
                beatRefs.current[index]?.focus()
            }
        }

        return (
            <div
                key={index}
                ref={(el) => (beatRefs.current[index] = el)}
                className={`teleprompter-beat ${shouldHighlight ? 'highlighted' : ''} ${isNextBeat ? 'next-beat' : ''} ${isPreviousBeat ? 'previous-beat' : ''}`}
                data-beat-index={index}
                data-confidence={beat.confidence}
                data-offset={nextOffset}
                tabIndex={0}
                role="listitem"
                aria-label={`Beat ${index + 1}: ${beat.text.substring(0, 50)}${beat.text.length > 50 ? '...' : ''}`}
                onKeyDown={handleBeatKeyDown}
            >
                <div className="beat-header">
                    <span className="beat-source badge badge-source">{beat.source || 'Unknown'}</span>
                    <span className="beat-confidence badge badge-confidence">
                        {(beat.confidence * 100).toFixed(0)}%
                    </span>
                    {shouldHighlight && <span className="beat-marker">▶</span>}
                </div>
                <p className={`beat-text ${shouldHighlight ? 'highlighted' : ''}`}>
                    {beat.text}
                </p>
                {beat.event_tags && beat.event_tags.length > 0 && (
                    <div className="beat-tags">
                        {beat.event_tags.map((tag) => (
                            <span key={tag} className="beat-tag badge">{tag}</span>
                        ))}
                    </div>
                )}
            </div>
        )
    }, [highlightedBeatIndex, beatConfidence])

    // Empty state - no notes generated yet
    if (!notesData && !buildingNotes) {
        return (
            <div className="teleprompter teleprompter-empty" role="complementary" aria-label="Commentary teleprompter">
                <div className="teleprompter-empty-state">
                    <div className="empty-icon">📋</div>
                    <h3>Commentary Notes</h3>
                    <p>Generate commentary notes to get started.</p>
                    <button className="teleprompter-generate-btn" onClick={onGenerateNotes}>
                        <span>⚡</span> Generate Commentary Notes
                    </button>
                </div>
            </div>
        )
    }

    // Progress state - generating notes via SSE
    if (buildingNotes) {
        return (
            <div className="teleprompter teleprompter-generating" role="complementary" aria-label="Commentary teleprompter">
                <div className="teleprompter-progress">
                    <h3>Generating Commentary Notes...</h3>
                    <div className="progress-bar">
                        <div className="progress-fill" style={{ width: buildStatus === 'loading' ? '60%' : '90%' }} />
                    </div>
                    <p className="progress-status">{buildProgress || 'Processing agents...'}</p>
                </div>
            </div>
        )
    }

    // Ready state - show regenerate button
    if (notesData && !buildingNotes && buildStatus === 'ready') {
        // Add regenerate button to header in long-sheet mode
    }

    // Error state
    if (buildStatus === 'error') {
        return (
            <div className="teleprompter teleprompter-error" role="complementary" aria-label="Commentary teleprompter">
                <div className="teleprompter-error-state">
                    <div className="error-icon">❌</div>
                    <h3>Couldn't generate notes</h3>
                    <p>{buildProgress || 'Generation failed'}</p>
                    <button className="btn btn-secondary" onClick={onGenerateNotes}>
                        Retry
                    </button>
                </div>
            </div>
        )
    }

    // Notes ready - Tabbed Mode (pre-match)
    if (!isLongSheetMode) {
        return (
            <div className="teleprompter" role="complementary" aria-label="Commentary teleprompter">
                <div className="teleprompter-header">
                    <h3 className="teleprompter-title">Commentary Notes</h3>
                    <div className="teleprompter-header-actions">
                        {/* Generate Notes button - hidden when notes exist (Story 5.5 AC) */}
                        {!notesData && (
                            <button
                                className="btn btn-sm btn-primary"
                                onClick={onGenerateNotes}
                                title="Generate commentary notes"
                            >
                                ⚡ Generate Notes
                            </button>
                        )}
                        {/* Regenerate Notes button - shown when notes are ready */}
                        {notesData && buildStatus === 'ready' && (
                            <button
                                className="btn btn-sm btn-secondary"
                                onClick={onGenerateNotes}
                                title="Regenerate commentary notes"
                            >
                                🔄 Regenerate Notes
                            </button>
                        )}
                        <button
                            className="btn btn-sm btn-ghost"
                            onClick={() => setIsLongSheetMode(true)}
                            title="Switch to long-sheet mode"
                        >
                            📜 Long Sheet
                        </button>
                    </div>
                </div>

                {/* Tab Navigation */}
                <div className="teleprompter-tabs">
                    {sections.map((section) => (
                        <button
                            key={section.id}
                            className={`teleprompter-tab ${activeTab === section.id ? 'active' : ''}`}
                            onClick={() => setActiveTab(section.id)}
                        >
                            {section.label}
                        </button>
                    ))}
                </div>

                {/* Tab Content */}
                <div className="teleprompter-content">
                    {sections
                        .filter((s) => s.id === activeTab)
                        .map((section) => (
                            <div key={section.id} className="teleprompter-section">
                                {renderMarkdown(section.content)}
                            </div>
                        ))}
                </div>

                {/* Metadata footer */}
                <div className="teleprompter-footer">
                    <span className="teleprompter-meta">
                        Source: {notesData?.json_structure?.sources_used || 'Pre-match research'}
                    </span>
                    {notesData?.preparation_time_ms && (
                        <span className="teleprompter-meta">
                            Generated in {(notesData.preparation_time_ms / 1000).toFixed(1)}s
                        </span>
                    )}
                </div>
            </div>
        )
    }

    // Notes ready - Long-Sheet Mode (live) with auto-highlighting
    return (
        <div className="teleprompter teleprompter-long-sheet" role="complementary" aria-label="Commentary teleprompter">
            <div className="teleprompter-header">
                <h3 className="teleprompter-title">Live Commentary Notes</h3>
                <div className="teleprompter-header-actions">
                    <button
                        className="btn btn-sm btn-ghost"
                        onClick={() => setIsLongSheetMode(false)}
                        title="Switch to tabbed view"
                    >
                        📑 Tabbed View
                    </button>
                    {/* Regenerate Notes button (Story 5.5 AC) */}
                    {buildStatus === 'ready' && (
                        <button
                            className="btn btn-sm btn-secondary"
                            onClick={onGenerateNotes}
                            title="Regenerate commentary notes"
                        >
                            🔄 Regenerate Notes
                        </button>
                    )}
                    {isHoldMode && (
                        <button
                            className="btn btn-sm btn-primary"
                            onClick={handleReturnToLive}
                            title="Return to live auto-scroll"
                        >
                            {holdModeButtonLabel()}
                        </button>
                    )}
                </div>
            </div>

            {/* Hold Mode Indicator */}
            {isHoldMode && (
                <div className="hold-mode-indicator">
                    <span className="hold-icon">⏸️</span>
                    <span className="hold-text">Auto-scroll paused — manual review</span>
                </div>
            )}

            {/* Beats Container with Auto-Scroll */}
            <div
                className="teleprompter-scroll-container"
                ref={scrollContainerRef}
                onScroll={handleScroll}
                role="log"
                aria-live="polite"
                aria-label="Live commentary beats"
            >
                {beats.map((beat, index) => renderBeat(beat, index))}
            </div>

            {/* Metadata footer */}
            <div className="teleprompter-footer">
                <span className="teleprompter-meta">
                    {beats.length} beats loaded
                </span>
                {highlightedBeatIndex !== null && (
                    <span className="teleprompter-meta">
                        Current: beat #{highlightedBeatIndex + 1} ({(beatConfidence * 100).toFixed(0)}% confidence)
                    </span>
                )}
            </div>
        </div>
    )
}
