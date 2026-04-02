import { useState, useEffect, useRef } from 'react'

const BACKEND = import.meta.env.VITE_BACKEND_URL || ''

const EVENT_ICONS = {
    tactical_detection: '🔍',
    fan_qa: '🎙️',
    commentary: '📢',
    test: '🧪',
}

function timeAgo(isoStr) {
    const diff = Math.floor((Date.now() - new Date(isoStr)) / 1000)
    if (diff < 60) return `${diff}s ago`
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
    return `${Math.floor(diff / 3600)}h ago`
}

export default function EventFeed() {
    const [events, setEvents] = useState([])
    const [loading, setLoading] = useState(false)
    const bottomRef = useRef(null)

    const fetchEvents = async () => {
        setLoading(true)
        try {
            const res = await fetch(`${BACKEND}/api/v1/events?n=30`)
            const data = await res.json()
            setEvents(data.events || [])
        } catch {
            // silently fail on poll
        } finally {
            setLoading(false)
        }
    }

    // Poll every 5 seconds for new events
    useEffect(() => {
        fetchEvents()
        const interval = setInterval(fetchEvents, 30000)
        return () => clearInterval(interval)
    }, [])

    // Auto-scroll to newest event
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [events.length])

    return (
        <div className="event-feed">
            <div className="event-header">
                <div className="event-title">⚡ Live Event Feed</div>
                <button
                    className="btn btn-secondary"
                    onClick={fetchEvents}
                    disabled={loading}
                    style={{ padding: '3px 10px', fontSize: 11 }}
                >
                    {loading ? <span className="spinner" style={{ color: 'var(--accent-blue)' }} /> : '↻ Refresh'}
                </button>
            </div>

            {events.length === 0 && !loading && (
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
