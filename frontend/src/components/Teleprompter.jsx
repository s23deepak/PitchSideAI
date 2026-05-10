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
    emptyKicker = 'Broadcast Notes',
    emptyTitle = 'Prepare the narrative sheet',
    emptyDescription = 'Generate notes before analysis starts. The agent pipeline will collect team form, player context, historical beats, and tactical talking points.',
    generateLabel = 'Generate Notes',
    progressTitle = 'Generating Broadcast Notes',
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

    const numericProgress = Number.parseFloat(buildProgress)
    const hasNumericProgress = Number.isFinite(numericProgress)
    const progressPercent = hasNumericProgress
        ? Math.max(0, Math.min(100, numericProgress * 100))
        : null
    const progressLabel = progressPercent !== null
        ? `${progressPercent.toFixed(1)}%`
        : buildProgress || 'Processing agents...'
    const progressWidth = progressPercent !== null
        ? `${progressPercent}%`
        : buildStatus === 'loading' ? '60%' : '90%'

    // Keep the full notes in tabbed mode. The old long-sheet view is only useful
    // once live beat extraction is quality-gated; otherwise it looks like a raw sheet.

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
    const parseBeats = () => {
        if (!notesData) return []

        if (Array.isArray(notesData.beats) && notesData.beats.length > 0) {
            return notesData.beats
        }

        if (Array.isArray(notesData.notes?.beats) && notesData.notes.beats.length > 0) {
            return notesData.notes.beats
                .map((beat) => ({
                    text: beat.text || beat.narrative || beat.title || '',
                    source: beat.source || beat.section || 'notes',
                    confidence: beat.confidence ?? 0.8,
                    event_tags: beat.event_tags || beat.tags || [],
                    section: beat.section || 'general',
                }))
                .filter((beat) => beat.text)
        }

        return []
    }

    const beats = parseBeats()
    const hasLiveBeats = beats.length > 0

    useEffect(() => {
        if (isLongSheetMode && !hasLiveBeats) {
            setIsLongSheetMode(false)
        }
    }, [isLongSheetMode, hasLiveBeats])

    // Parse notes into sections for tabbed mode
    const parseSections = () => {
        if (!notesData?.markdown_notes) return []

        const markdown = notesData.markdown_notes
        const matches = [...markdown.matchAll(/^##\s+(.+)$/gim)]

        if (matches.length === 0) {
            return [{ id: 'full', label: 'Full Notes', content: markdown }]
        }

        return matches.map((match, idx) => {
            const startIdx = match.index
            const nextMatch = matches[idx + 1]
            const endIdx = nextMatch ? nextMatch.index : markdown.length
            const rawTitle = match[1].replace(/[:*]/g, '').trim()
            const label = rawTitle
                .replace(/^PAGES?\s*\d+(?:\s*[-–]\s*\d+)?\s*/i, '')
                .trim() || `Section ${idx + 1}`

            return {
                id: label.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || `section_${idx + 1}`,
                label,
                content: markdown.slice(startIdx, endIdx).trim(),
            }
        })
    }

    const sections = parseSections()
    const selectedSection = sections.find((section) => section.id === activeTab) || sections[0]

    // Render markdown with basic formatting
    const renderMarkdown = (text) => {
        if (!text) return null

        const lines = text.split('\n')
        const elements = []

        for (let idx = 0; idx < lines.length; idx += 1) {
            const line = lines[idx]
            const trimmed = line.trim()
            if (!trimmed) {
                elements.push(<br key={idx} />)
                continue
            }

            if (trimmed === '---') {
                elements.push(<hr key={idx} className="teleprompter-hr" />)
                continue
            }

            if (trimmed.startsWith('|')) {
                const tableLines = []
                let tableIdx = idx
                while (tableIdx < lines.length && lines[tableIdx].trim().startsWith('|')) {
                    tableLines.push(lines[tableIdx].trim())
                    tableIdx += 1
                }
                const table = renderMarkdownTable(tableLines, idx)
                if (table) elements.push(table)
                idx = tableIdx - 1
                continue
            }

            // Headers
            if (trimmed.startsWith('# ')) {
                elements.push(<h3 key={idx} className="teleprompter-h3">{trimmed.slice(2)}</h3>)
                continue
            }
            if (trimmed.startsWith('## ')) {
                elements.push(<h3 key={idx} className="teleprompter-h3">{trimmed.slice(3)}</h3>)
                continue
            }
            if (trimmed.startsWith('### ')) {
                elements.push(<h4 key={idx} className="teleprompter-h4">{trimmed.slice(4)}</h4>)
                continue
            }
            if (trimmed.startsWith('#### ')) {
                elements.push(<h4 key={idx} className="teleprompter-h4">{trimmed.slice(5)}</h4>)
                continue
            }
            if (trimmed.startsWith('##### ')) {
                elements.push(<p key={idx} className="teleprompter-meta-line">{trimmed.slice(6)}</p>)
                continue
            }

            // List items
            if (trimmed.startsWith('- ')) {
                elements.push(
                    <li key={idx} className="teleprompter-li">
                        {renderInlineFormatting(trimmed.slice(2))}
                    </li>
                )
                continue
            }

            // Bold/italic inline formatting
            elements.push(
                <p key={idx} className="teleprompter-p">
                    {renderInlineFormatting(trimmed)}
                </p>
            )
        }

        return elements
    }

    const renderMarkdownTable = (tableLines, keyPrefix) => {
        const rows = tableLines
            .filter((line) => !/^\|\s*-+\s*(\|\s*-+\s*)+\|?$/.test(line))
            .map((line) => line.replace(/^\||\|$/g, '').split('|').map((cell) => cell.trim()))
            .filter((row) => row.some((cell) => cell && cell !== '-'))

        if (rows.length <= 1) return null

        const [headers, ...bodyRows] = rows
        if (bodyRows.length === 0) return null

        return (
            <div key={`table-${keyPrefix}`} className="teleprompter-table-wrap">
                <table className="teleprompter-table">
                    <thead>
                        <tr>
                            {headers.map((header, idx) => (
                                <th key={`${keyPrefix}-h-${idx}`}>{renderInlineFormatting(header)}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {bodyRows.map((row, rowIdx) => (
                            <tr key={`${keyPrefix}-r-${rowIdx}`}>
                                {headers.map((_header, cellIdx) => (
                                    <td key={`${keyPrefix}-c-${rowIdx}-${cellIdx}`}>
                                        {renderInlineFormatting(row[cellIdx] || '')}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        )
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
                    <div className="empty-icon">
                        <span className="material-icons">article</span>
                    </div>
                    <div className="teleprompter-empty-kicker">{emptyKicker}</div>
                    <h3>{emptyTitle}</h3>
                    <p>
                        {emptyDescription}
                    </p>
                    <div className="teleprompter-empty-status" aria-label="Notes setup status">
                        <span>Source</span>
                        <strong>Team context</strong>
                        <span>Video</span>
                        <strong>Optional for notes</strong>
                        <span>Output</span>
                        <strong>Broadcast sheet</strong>
                    </div>
                    <button className="teleprompter-generate-btn" onClick={onGenerateNotes}>
                        <span className="material-icons">bolt</span>
                        {generateLabel}
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
                    <div className="empty-icon active">
                        <span className="material-icons">sync</span>
                    </div>
                    <h3>{progressTitle}</h3>
                    <div className="progress-bar">
                        <div className="progress-fill" style={{ width: progressWidth }} />
                    </div>
                    <p className="progress-status">{progressLabel}</p>
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
                    <div className="error-icon">
                        <span className="material-icons">error</span>
                    </div>
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
                                <span className="material-icons">bolt</span>
                                Generate Notes
                            </button>
                        )}
                        {/* Regenerate Notes button - shown when notes are ready */}
                        {notesData && buildStatus === 'ready' && (
                            <button
                                className="btn btn-sm btn-secondary"
                                onClick={onGenerateNotes}
                                title="Regenerate commentary notes"
                            >
                                <span className="material-icons">refresh</span>
                                Regenerate Notes
                            </button>
                        )}
                    </div>
                </div>

                {/* Tab Navigation */}
                <div className="teleprompter-tabs">
                    {sections.map((section) => (
                        <button
                            key={section.id}
                            className={`teleprompter-tab ${selectedSection?.id === section.id ? 'active' : ''}`}
                            onClick={() => setActiveTab(section.id)}
                        >
                            {section.label}
                        </button>
                    ))}
                </div>

                {/* Tab Content */}
                <div className="teleprompter-content">
                    {selectedSection && (
                        <div key={selectedSection.id} className="teleprompter-section">
                            {renderMarkdown(selectedSection.content)}
                        </div>
                    )}
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
                            <span className="material-icons">view_week</span>
                            Tabbed View
                        </button>
                    {/* Regenerate Notes button (Story 5.5 AC) */}
                    {buildStatus === 'ready' && (
                        <button
                            className="btn btn-sm btn-secondary"
                            onClick={onGenerateNotes}
                            title="Regenerate commentary notes"
                        >
                            <span className="material-icons">refresh</span>
                            Regenerate Notes
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
