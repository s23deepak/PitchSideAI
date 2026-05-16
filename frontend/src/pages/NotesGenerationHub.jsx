import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLiveSession } from '@/contexts/LiveSessionContext'

export default function NotesGenerationHub() {
    const {
        homeTeam,
        awayTeam,
        sport,
        commentaryData,
        buildingNotes,
        buildStatus,
        buildProgress,
        prepareNotes,
        liveLogs,
    } = useLiveSession()

    const [notes, setNotes] = useState(null)
    const [agentProgress, setAgentProgress] = useState({})
    const [activeTab, setActiveTab] = useState('section1')
    const [parsedSections, setParsedSections] = useState([])

    // Sync with context commentaryData
    useEffect(() => {
        if (commentaryData) {
            setNotes(commentaryData)
            // Parse markdown into sections for tab navigation
            const sections = parseMarkdownToSections(commentaryData.markdown_notes || '')
            setParsedSections(sections)
            setActiveTab(sections[0]?.id || 'page1')
        }
    }, [commentaryData])

    // Parse markdown into sections
    const parseMarkdownToSections = (markdown) => {
        if (!markdown) return []

        const sections = []
        const lines = markdown.split('\n')
        let currentSection = null
        let sectionCounter = 0

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i]
            const h1Match = line.match(/^#\s+(.*)$/)
            const h2Match = line.match(/^##\s+(.*)$/)
            const h3Match = line.match(/^###\s+(.*)$/)
            const h4Match = line.match(/^####\s+(.*)$/)

            // Skip H1 (title line like "# Commentary Notes: ...")
            if (h1Match) {
                continue
            }

            // H2 starts a new section
            if (h2Match) {
                if (currentSection) {
                    sections.push(currentSection)
                }
                sectionCounter++
                // Clean title: remove "PAGE X:" prefix and extra chars
                let title = h2Match[1].replace(/[:*]/g, '').trim()
                title = title.replace(/^PAGE\s*\d+[-\s]*/i, '').trim()
                title = title.replace(/^PAGES\s*\d+[-\s]*\d+[-\s]*/i, '').trim()
                currentSection = { id: `section${sectionCounter}`, title, content: [] }
            } else if (h3Match) {
                if (!currentSection) {
                    sectionCounter++
                    currentSection = { id: `section${sectionCounter}`, title: 'Overview', content: [] }
                }
                currentSection.content.push({ type: 'h3', text: h3Match[1] })
            } else if (h4Match) {
                if (!currentSection) {
                    sectionCounter++
                    currentSection = { id: `section${sectionCounter}`, title: 'Overview', content: [] }
                }
                currentSection.content.push({ type: 'h4', text: h4Match[1] })
            } else if (line.startsWith('|')) {
                if (!currentSection) {
                    sectionCounter++
                    currentSection = { id: `section${sectionCounter}`, title: 'Overview', content: [] }
                }
                currentSection.content.push({ type: 'table-row', text: line })
            } else if (line.startsWith('- **') || line.startsWith('- ')) {
                if (!currentSection) {
                    sectionCounter++
                    currentSection = { id: `section${sectionCounter}`, title: 'Overview', content: [] }
                }
                currentSection.content.push({ type: 'list-item', text: line })
            } else if (line.trim() === '---') {
                if (currentSection) {
                    currentSection.content.push({ type: 'divider' })
                }
            } else if (line.trim()) {
                if (!currentSection) {
                    sectionCounter++
                    currentSection = { id: `section${sectionCounter}`, title: 'Overview', content: [] }
                }
                currentSection.content.push({ type: 'text', text: line })
            }
        }

        if (currentSection && currentSection.content.length > 0) {
            sections.push(currentSection)
        }

        return sections
    }

    // Derive agent states from buildProgress
    // buildProgress is a float 0-1 representing overall completion
    const progressValue = parseFloat(buildProgress) || 0
    const progressPercent = Math.max(0, Math.min(100, progressValue * 100))
    const progressPercentLabel = `${progressPercent.toFixed(1)}%`

    // Agent completion thresholds based on overall progress
    const getAgentStatus = (agentId, threshold) => {
        if (buildStatus === 'ready') return 'completed'
        if (progressValue >= threshold) return 'completed'
        if (progressValue >= threshold - 0.15) return 'running'
        return 'pending'
    }

    const agents = [
        {
            id: 'news',
            name: 'News Agent',
            description: 'Researching latest team news and updates.',
            icon: 'newspaper',
            status: getAgentStatus('news', 0.10),
            progress: buildStatus === 'ready' ? 100 : Math.min(100, Math.round((progressValue / 0.10) * 100)),
            completed: null,
            total: null,
        },
        {
            id: 'weather',
            name: 'Weather Agent',
            description: 'Checking match day weather conditions.',
            icon: 'cloud',
            status: getAgentStatus('weather', 0.15),
            progress: buildStatus === 'ready' ? 100 : Math.min(100, Math.round(((progressValue - 0.10) / 0.05) * 100)),
            completed: null,
            total: null,
        },
        {
            id: 'historical',
            name: 'Historical Context',
            description: 'Analyzing historical matchup data.',
            icon: 'history',
            status: getAgentStatus('historical', 0.20),
            progress: buildStatus === 'ready' ? 100 : Math.min(100, Math.round(((progressValue - 0.15) / 0.05) * 100)),
            completed: null,
            total: null,
        },
        {
            id: 'player-research',
            name: 'Player Research',
            description: 'Compiling player profiles and metrics.',
            icon: 'person_search',
            status: getAgentStatus('player-research', 0.50),
            progress: buildStatus === 'ready' ? 100 : Math.min(100, Math.round(((progressValue - 0.20) / 0.30) * 100)),
            completed: buildStatus === 'ready' ? 25 : Math.min(25, Math.floor(((progressValue - 0.20) / 0.30) * 25)),
            total: 25,
        },
        {
            id: 'team-form',
            name: 'Team Form',
            description: 'Analyzing recent form and tactical patterns.',
            icon: 'groups',
            status: getAgentStatus('team-form', 0.70),
            progress: buildStatus === 'ready' ? 100 : Math.min(100, Math.round(((progressValue - 0.50) / 0.20) * 100)),
            completed: null,
            total: null,
        },
        {
            id: 'matchup',
            name: 'Matchup Analysis',
            description: 'Breaking down key tactical battles.',
            icon: 'strategy',
            status: getAgentStatus('matchup', 0.85),
            progress: buildStatus === 'ready' ? 100 : Math.min(100, Math.round(((progressValue - 0.70) / 0.15) * 100)),
            completed: null,
            total: null,
        },
        {
            id: 'organizer',
            name: 'Notes Organizer',
            description: 'Synthesizing all data into commentary notes.',
            icon: 'auto_awesome',
            status: getAgentStatus('organizer', 1.0),
            progress: buildStatus === 'ready' ? 100 : Math.min(100, Math.round(((progressValue - 0.85) / 0.15) * 100)),
            completed: null,
            total: null,
        },
    ]

    // Use live logs from context (streamed from SSE) instead of hardcoded logs
    const displayLogs = liveLogs && liveLogs.length > 0 ? liveLogs : []

    const handleStartNotesGeneration = async () => {
        await prepareNotes(homeTeam, awayTeam)
    }

    return (
        <div className="notes-hub-page">
            <main className="notes-hub-main">
                {/* Header */}
                <header className="notes-hub-header">
                    <div>
                        <h1 className="notes-hub-title">Full Notes Pipeline</h1>
                        <p className="notes-hub-subtitle">
                            Research, audit, and organize the complete commentary-notes artifact for {homeTeam} vs {awayTeam}.
                        </p>
                    </div>
                    <div className="notes-hub-status-badge">
                        <div className={`notes-hub-status-dot ${buildStatus === 'ready' ? 'ready' : 'active'}`}></div>
                        <span className="notes-hub-status-label">
                            {buildStatus === 'ready' ? 'READY' : 'SYSTEM ACTIVE'}
                        </span>
                    </div>
                </header>

                {/* Global Status Card */}
                <div className="notes-hub-global-status">
                    <div className="notes-hub-status-content">
                        <div className="notes-hub-status-text" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                            <div className="notes-hub-status-icon">
                                <span className="material-icons">hub</span>
                            </div>
                            <div>
                                <h2>Research Agent Progress</h2>
                                <p>
                                    {buildStatus === 'ready'
                                        ? 'All agents completed successfully'
                                        : progressValue < 0.15
                                            ? 'Connecting to data sources...'
                                            : progressValue < 0.30
                                                ? 'Retrieving team and player statistics...'
                                                : progressValue < 0.45
                                                    ? 'Analyzing team form and tactical patterns...'
                                                    : progressValue < 0.70
                                                        ? `Processing player profiles... ${Math.floor((progressValue / 0.70) * 25)}/25`
                                                        : progressValue < 0.85
                                                            ? 'Loading historical matchup data...'
                                                            : 'Synthesizing commentary notes...'}
                                </p>
                            </div>
                        </div>

                        <div className="notes-hub-progress-container">
                            <div className="notes-hub-progress-label">
                                <span>Overall Completion</span>
                                <span>{progressPercentLabel}</span>
                            </div>
                            <div className="notes-hub-progress-bar">
                                <div
                                    className="notes-hub-progress-fill"
                                    style={{ width: `${progressPercent}%` }}
                                ></div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Action Button */}
                {buildStatus !== 'ready' && (
                    <button
                        className="notes-hub-start-btn"
                        onClick={handleStartNotesGeneration}
                        disabled={buildingNotes}
                    >
                        <span className="material-icons">{buildingNotes ? 'sync' : 'play_arrow'}</span>
                        {buildingNotes ? 'Generating Full Notes...' : 'Generate Full Commentary Notes'}
                    </button>
                )}

                {/* Pipeline Grid */}
                <div className="notes-hub-grid">
                    {/* Agents Grid */}
                    <div className="notes-hub-agents-grid">
                        {agents.map((agent) => (
                            <div
                                key={agent.id}
                                className={`notes-hub-agent-card notes-hub-agent-card--${agent.status}`}
                            >
                                <div className="notes-hub-agent-header">
                                    <div className="notes-hub-agent-title-group">
                                        <span className={`material-icons notes-hub-agent-icon--${agent.status}`}>
                                            {agent.icon}
                                        </span>
                                        <h3 className={`notes-hub-agent-name--${agent.status}`}>
                                            {agent.name}
                                        </h3>
                                    </div>
                                    <span className={`material-icons notes-hub-agent-status--${agent.status}`}>
                                        {agent.status === 'running' ? 'sync' : agent.status === 'completed' ? 'check_circle' : 'schedule'}
                                    </span>
                                </div>

                                <p className={`notes-hub-agent-description--${agent.status}`}>
                                    {agent.description}
                                </p>

                                <div className="notes-hub-agent-progress">
                                    <div className={`notes-hub-agent-progress-bar--${agent.status}`}>
                                        <div
                                            className={`notes-hub-agent-progress-fill--${agent.status}`}
                                            style={{ width: `${agent.progress}%` }}
                                        ></div>
                                    </div>
                                    {agent.completed !== null && (
                                        <span className={`notes-hub-agent-count--${agent.status}`}>
                                            {agent.completed}/{agent.total}
                                        </span>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Live Logs Sidebar */}
                    <div className="notes-hub-logs-sidebar">
                        <div className="notes-hub-logs-header">
                            <span className="material-icons notes-hub-logs-icon">terminal</span>
                            <h3 className="notes-hub-logs-title">Live Output Stream</h3>
                        </div>

                        <div className="notes-hub-logs-stream">
                            {displayLogs.map((log, index) => (
                                <div key={index} className="notes-hub-log-entry">
                                    <span className="notes-hub-log-time">[{log.time}]</span>
                                    <span className={
                                        log.type === 'success'
                                            ? 'notes-hub-log-message_success'
                                            : log.type === 'running'
                                            ? 'notes-hub-log-message_running'
                                            : log.type === 'error'
                                            ? 'notes-hub-log-message_error'
                                            : ''
                                    }>
                                        {log.message}
                                    </span>
                                </div>
                            ))}
                            {buildingNotes && (
                                <div className="notes-hub-log-entry">
                                    <span className="notes-hub-log-cursor">_</span>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Generated Notes Display */}
                {buildStatus === 'ready' && notes && notes.markdown_notes && parsedSections.length > 0 && (
                    <div className="notes-hub-results">
                        <div className="notes-hub-results-header">
                            <h2 className="notes-hub-results-title">Generated Commentary Notes</h2>
                            <div className="notes-hub-meta">
                                <span className="notes-hub-meta-item">
                                    <span className="material-icons">schedule</span>
                                    {Number.isFinite(notes.preparation_time_ms)
                                        ? `${(notes.preparation_time_ms / 1000).toFixed(1)}s`
                                        : 'Recovered'}
                                </span>
                                <span className="notes-hub-meta-item">
                                    <span className="material-icons">format_list_numbered</span>
                                    {notes.beat_count} beats
                                </span>
                            </div>
                        </div>

                        {/* Tab Navigation */}
                        <div className="notes-hub-tabs">
                            {parsedSections.map((section) => (
                                <button
                                    key={section.id}
                                    className={`notes-hub-tab ${activeTab === section.id ? 'active' : ''}`}
                                    onClick={() => setActiveTab(section.id)}
                                >
                                    {section.title}
                                </button>
                            ))}
                        </div>

                        {/* Tab Content */}
                        <div className="notes-hub-content">
                            {parsedSections
                                .filter((s) => s.id === activeTab)
                                .map((section) => (
                                    <div key={section.id} className="notes-hub-section">
                                        {section.content.map((item, idx) => {
                                            if (item.type === 'h3') {
                                                return (
                                                    <h3 key={idx} className="notes-hub-h3">
                                                        {item.text}
                                                    </h3>
                                                )
                                            }
                                            if (item.type === 'h4') {
                                                return (
                                                    <h4 key={idx} className="notes-hub-h4">
                                                        {item.text}
                                                    </h4>
                                                )
                                            }
                                            if (item.type === 'table-row') {
                                                const isHeaderRow = item.text.includes('| Pos |') || item.text.includes('|---')
                                                const cells = item.text.split('|').filter(Boolean).map(c => c.trim())
                                                // Skip separator row like |---|---|---|
                                                if (cells.every(c => c.startsWith('---'))) return null
                                                return (
                                                    <div key={idx} className={`notes-hub-table-row ${isHeaderRow ? 'notes-hub-table-header-row' : ''}`}>
                                                        {cells.map((cell, cIdx) => (
                                                            <span key={cIdx} className={isHeaderRow ? 'notes-hub-table-header' : 'notes-hub-table-cell'}>
                                                                {cell}
                                                            </span>
                                                        ))}
                                                    </div>
                                                )
                                            }
                                            if (item.type === 'list-item') {
                                                return (
                                                    <div key={idx} className="notes-hub-list-item">
                                                        <span className="notes-hub-bullet">•</span>
                                                        <span dangerouslySetInnerHTML={{ __html: item.text.replace(/^- /, '').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }} />
                                                    </div>
                                                )
                                            }
                                            if (item.type === 'divider') {
                                                return <hr key={idx} className="notes-hub-divider" />
                                            }
                                            return (
                                                <p key={idx} className="notes-hub-text" dangerouslySetInnerHTML={{ __html: item.text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\*/g, '') }} />
                                            )
                                        })}
                                    </div>
                                ))}
                        </div>
                    </div>
                )}
            </main>
        </div>
    )
}
