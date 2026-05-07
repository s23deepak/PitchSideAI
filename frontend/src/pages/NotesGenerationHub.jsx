import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLiveSession } from '@/contexts/LiveSessionContext'
import TopNavBar from '@/components/TopNavBar'

export default function NotesGenerationHub() {
    const navigate = useNavigate()
    const {
        homeTeam,
        awayTeam,
        sport,
        commentaryData,
        buildingNotes,
        buildStatus,
        buildProgress,
        prepareNotes,
    } = useLiveSession()

    const [notes, setNotes] = useState(null)
    const [logs, setLogs] = useState([])

    // Sync with context commentaryData
    useEffect(() => {
        if (commentaryData) {
            setNotes(commentaryData)
        }
    }, [commentaryData])

    // Demo agent states
    const [agents] = useState([
        {
            id: 'player-research',
            name: 'PlayerResearch Agent',
            description: 'Compiling recent tactical shifts and individual metrics.',
            icon: 'person_search',
            status: buildStatus === 'ready' ? 'completed' : 'running',
            progress: buildStatus === 'ready' ? 100 : Math.min(88, (parseFloat(buildProgress) || 0) * 100),
            completed: buildStatus === 'ready' ? 25 : Math.min(22, Math.floor((parseFloat(buildProgress) || 0) * 25)),
            total: 25,
        },
        {
            id: 'team-form',
            name: 'TeamForm Analysis',
            description: 'Historical data mapped. Win/Loss vectors established.',
            icon: 'groups',
            status: 'completed',
            progress: 100,
        },
        {
            id: 'stat-retrieval',
            name: 'Stat Retrieval',
            description: 'API connections verified. Core statistics loaded.',
            icon: 'query_stats',
            status: 'completed',
            progress: 100,
        },
        {
            id: 'tactical-history',
            name: 'Tactical History',
            description: 'Awaiting PlayerResearch output to initialize.',
            icon: 'strategy',
            status: buildStatus === 'ready' ? 'completed' : 'pending',
            progress: buildStatus === 'ready' ? 100 : 0,
        },
        {
            id: 'narrative-engine',
            name: 'Narrative Engine',
            description: 'Standing by for synthesized context matrix.',
            icon: 'auto_awesome',
            status: buildStatus === 'ready' ? 'completed' : 'pending',
            progress: buildStatus === 'ready' ? 100 : 0,
        },
    ])

    // Demo logs
    useEffect(() => {
        const demoLogs = [
            { time: '08:42:01', message: 'SYS_INIT: Booting 7-agent pipeline.', type: 'info' },
            { time: '08:42:05', message: 'StatRetrieval: Connected to Opta API.', type: 'info' },
            { time: '08:42:12', message: 'StatRetrieval: SUCCESS. 4,200 data points ingested.', type: 'success' },
            { time: '08:42:15', message: 'TeamForm: Analyzing last 5 fixtures.', type: 'info' },
            { time: '08:42:28', message: 'TeamForm: SUCCESS. Form vectors plotted.', type: 'success' },
            { time: '08:42:30', message: 'PlayerResearch: Initializing target queue (25 items).', type: 'info' },
            { time: '08:43:01', message: 'PlayerResearch: Processing target #1 (Striker).', type: 'running' },
            { time: '08:44:15', message: 'PlayerResearch: Processing target #10 (Midfield).', type: 'running' },
        ]

        setLogs(demoLogs)
    }, [])

    const handleStartNotesGeneration = async () => {
        await prepareNotes(homeTeam, awayTeam)
    }

    return (
        <div className="notes-hub-page-wrapper">
            {/* Top Navigation Bar */}
            <TopNavBar />

            {/* Main Content */}
            <main className="notes-hub-main">
                {/* Header */}
                <header className="notes-hub-header">
                    <div>
                        <h1 className="notes-hub-title">Generation Pipeline</h1>
                        <p className="notes-hub-subtitle">
                            Pre-match analysis sequence {buildStatus === 'ready' ? 'complete' : 'in progress'}.
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
                                <h2>Agent Swarm Progress</h2>
                                <p>
                                    {buildStatus === 'ready'
                                        ? 'All agents completed successfully'
                                        : `Researching player profiles... ${Math.floor((parseFloat(buildProgress) || 0) * 25)}/25`}
                                </p>
                            </div>
                        </div>

                        <div className="notes-hub-progress-container">
                            <div className="notes-hub-progress-label">
                                <span>Overall Completion</span>
                                <span>{Math.round((parseFloat(buildProgress) || 0) * 100)}%</span>
                            </div>
                            <div className="notes-hub-progress-bar">
                                <div
                                    className="notes-hub-progress-fill"
                                    style={{ width: `${(parseFloat(buildProgress) || 0) * 100}%` }}
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
                    >
                        <span className="material-icons">play_arrow</span>
                        Generate Commentary Notes
                    </button>
                )}

                {/* Pipeline Grid */}
                <div className="notes-hub-grid">
                    {/* Agents Grid */}
                    <div className="notes-hub-agents-grid">
                        {agents.map((agent) => (
                            <div
                                key={agent.id}
                                className={`notes-hub-agent-card notes-hub-agent-card_${agent.status}`}
                            >
                                <div className="notes-hub-agent-header">
                                    <div className="notes-hub-agent-title-group">
                                        <span className={`material-icons notes-hub-agent-icon notes-hub-agent-icon_${agent.status}`}>
                                            {agent.icon}
                                        </span>
                                        <h3 className={`notes-hub-agent-name notes-hub-agent-name_${agent.status}`}>
                                            {agent.name}
                                        </h3>
                                    </div>
                                    <span className={`material-icons notes-hub-agent-status notes-hub-agent-status_${agent.status}`}>
                                        {agent.status === 'running' ? 'sync' : agent.status === 'completed' ? 'check_circle' : 'schedule'}
                                    </span>
                                </div>

                                <p className={`notes-hub-agent-description notes-hub-agent-description_${agent.status}`}>
                                    {agent.description}
                                </p>

                                <div className="notes-hub-agent-progress">
                                    <div className={`notes-hub-agent-progress-bar notes-hub-agent-progress-bar_${agent.status}`}>
                                        <div
                                            className={`notes-hub-agent-progress-fill notes-hub-agent-progress-fill_${agent.status}`}
                                            style={{ width: `${agent.progress}%` }}
                                        ></div>
                                    </div>
                                    {agent.completed !== null && (
                                        <span className={`notes-hub-agent-count notes-hub-agent-count_${agent.status}`}>
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
                            {logs.map((log, index) => (
                                <div key={index} className="notes-hub-log-entry">
                                    <span className="notes-hub-log-time">[{log.time}]</span>
                                    <span className={
                                        log.type === 'success'
                                            ? 'notes-hub-log-message_success'
                                            : log.type === 'running'
                                            ? 'notes-hub-log-message_running'
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
                {buildStatus === 'ready' && notes && (
                    <div className="notes-hub-results">
                        <h2 className="notes-hub-results-title">Generated Commentary Notes</h2>
                        <pre className="notes-hub-results-content">
                            {JSON.stringify(notes, null, 2)}
                        </pre>
                    </div>
                )}
            </main>
        </div>
    )
}
