import { useState, useEffect, useRef } from 'react'

const BACKEND = import.meta.env.VITE_BACKEND_URL || ''

const EVENT_ICONS = {
    tactical_detection: '🔍',
    tactical_analyst_note: '🧠',
    fan_qa: '🎙️',
    commentary: '📢',
    live_commentary: '📢',
    test: '🧪',
}

function timeAgo(isoStr) {
    const diff = Math.floor((Date.now() - new Date(isoStr)) / 1000)
    if (diff < 60) return `${diff}s ago`
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
    return `${Math.floor(diff / 3600)}h ago`
}

export default function EventFeed({ matchSession }) {
    const [events, setEvents] = useState([])
    const [connected, setConnected] = useState(false)
    const bottomRef = useRef(null)
    const esRef = useRef(null)

    const connect = () => {
        if (esRef.current) esRef.current.close()

        const params = new URLSearchParams({ n: '30' })
        if (matchSession) {
            params.set('match_session', matchSession)
        }

        const es = new EventSource(`${BACKEND}/api/v1/events/stream?${params.toString()}`)
        esRef.current = es

        es.onopen = () => setConnected(true)

        es.onmessage = (e) => {
            try {
                setEvents(JSON.parse(e.data) || [])
            } catch { /* ignore */ }
        }

        es.onerror = () => {
            setConnected(false)
            // EventSource auto-reconnects; no manual retry needed
        }
    }

    useEffect(() => {
        connect()
        return () => esRef.current?.close()
    }, [matchSession]) // eslint-disable-line react-hooks/exhaustive-deps

    // Auto-scroll to newest event
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [events.length])

    return (
        <div className="event-feed">
            <div className="event-header">
                <div className="event-title">⚡ Live Event Feed</div>
                <span style={{ fontSize: 11, color: connected ? 'var(--accent-green, #4ade80)' : 'var(--text-muted)' }}>
                    {connected ? '● live' : '○ reconnecting...'}
                </span>
            </div>

            {events.length === 0 && (
                <div className="events-empty">
                    <span style={{ fontSize: 28 }}>⚡</span>
                    <span>No events yet.</span>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        Events appear when you ask questions or upload frames.
                    </span>
                </div>
            )}

            {events.map((ev) => (
                <div key={ev.id} className="event-item">
                    <div className={`event-icon ${ev.type}`}>
                        {EVENT_ICONS[ev.type] || '📌'}
                    </div>
                    <div className="event-body">
                        <div className="event-desc">{ev.description}</div>
                        <div className="event-time">{timeAgo(ev.timestamp)}</div>
                    </div>
                </div>
            ))}

            <div ref={bottomRef} />
        </div>
    )
}
