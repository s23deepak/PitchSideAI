import { useState, useRef, useEffect } from 'react'

const SOURCE_ICON = {
    event: '⚡',
    timer: '🕐',
    detection: '🔍',
    analysis: '🎯',
}

const SOURCE_LABEL = {
    event: 'Match Event',
    timer: 'Auto Update',
    detection: 'Analyst Note',
    analysis: 'Tactical Commentary',
}

function timeAgo(isoStr) {
    const diff = Math.floor((Date.now() - new Date(isoStr)) / 1000)
    if (diff < 60) return `${diff}s ago`
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
    return `${Math.floor(diff / 3600)}h ago`
}

function formatVideoTimestamp(timestampMs) {
    if (typeof timestampMs !== 'number' || Number.isNaN(timestampMs) || timestampMs < 0) {
        return null
    }

    const totalSeconds = Math.floor(timestampMs / 1000)
    const seconds = totalSeconds % 60
    const totalMinutes = Math.floor(totalSeconds / 60)
    const minutes = totalMinutes % 60
    const hours = Math.floor(totalMinutes / 60)

    if (hours > 0) {
        return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
    }

    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

export default function CommentaryFeed({ messages, sendMatchEvent }) {
    const [inputText, setInputText] = useState('')
    const feedRef = useRef(null)

    // Scroll to top when new messages arrive (newest first layout)
    useEffect(() => {
        if (feedRef.current) {
            feedRef.current.scrollTop = 0
        }
    }, [messages.length])

    const handleSend = () => {
        const text = inputText.trim()
        if (!text || !sendMatchEvent) return
        sendMatchEvent(text)
        setInputText('')
    }

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSend()
        }
    }

    return (
        <div className="event-feed" style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            <div className="event-header">
                <div className="event-title">🗣️ Live Commentary</div>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {messages.length > 0 ? `${messages.length} line${messages.length !== 1 ? 's' : ''}` : 'Waiting...'}
                </span>
            </div>

            {/* Feed */}
            <div
                ref={feedRef}
                style={{ overflowY: 'auto', maxHeight: 320, display: 'flex', flexDirection: 'column', gap: 8, padding: '8px 0' }}
            >
                {messages.length === 0 && (
                    <div className="events-empty">
                        <span style={{ fontSize: 28 }}>🗣️</span>
                        <span>Commentary will appear here.</span>
                        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                            Upload a frame or type a match event below.
                        </span>
                    </div>
                )}

                {messages.map((msg, i) => (
                    <div key={i} className="event-item" style={{ alignItems: 'flex-start' }}>
                        <div className="event-icon commentary" style={{ fontSize: 18, minWidth: 28 }}>
                            {SOURCE_ICON[msg.source] || '📢'}
                        </div>
                        <div className="event-body" style={{ flex: 1 }}>
                            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 4 }}>
                                <span className="commentary-source-chip">{SOURCE_LABEL[msg.source] || 'Commentary'}</span>
                                {msg.label && (
                                    <span className="commentary-source-chip commentary-source-chip-secondary">{msg.label}</span>
                                )}
                                {formatVideoTimestamp(msg.videoTimestampMs) && (
                                    <span className="commentary-source-chip commentary-source-chip-secondary">
                                        {formatVideoTimestamp(msg.videoTimestampMs)}
                                    </span>
                                )}
                                {msg.videoRangeLabel && (
                                    <span className="commentary-source-chip commentary-source-chip-secondary">
                                        {msg.videoRangeLabel}
                                    </span>
                                )}
                                {msg.confidence != null && (
                                    <span className="commentary-source-chip commentary-source-chip-muted">
                                        {Math.round(msg.confidence * 100)}% confidence
                                    </span>
                                )}
                            </div>
                            <div className="event-desc" style={{ lineHeight: 1.5 }}>{msg.text}</div>
                            <div style={{ display: 'flex', gap: 8, marginTop: 4, alignItems: 'center' }}>
                                <div className="event-time">{msg.timestamp ? timeAgo(msg.timestamp) : ''}</div>
                                {msg.trigger && (
                                    <div style={{ fontSize: 10, color: 'var(--text-muted)', fontStyle: 'italic' }}>
                                        triggered by: {msg.trigger}
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Manual event input */}
            <div style={{ display: 'flex', gap: 8, paddingTop: 8, borderTop: '1px solid var(--border-color)' }}>
                <input
                    type="text"
                    value={inputText}
                    onChange={e => setInputText(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="e.g. Goal by Haaland 34'…"
                    style={{ flex: 1, minWidth: 0 }}
                    disabled={!sendMatchEvent}
                />
                <button
                    className="btn btn-primary"
                    onClick={handleSend}
                    disabled={!inputText.trim() || !sendMatchEvent}
                    style={{ padding: '6px 14px', fontSize: 13 }}
                >
                    Send
                </button>
            </div>
        </div>
    )
}
