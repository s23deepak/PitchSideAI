import { useState, useEffect, useRef } from 'react'

const BACKEND = import.meta.env.VITE_BACKEND_URL || ''

/* ── Push-to-Talk Component ─────────────────────────────────────────────────── */
export default function PushToTalk({ matchReady, homeTeam, awayTeam, sport }) {
    const [status, setStatus] = useState('idle') // idle | listening | speaking | error
    const [transcript, setTranscript] = useState('')
    const [agentReply, setAgentReply] = useState('')
    const wsRef = useRef(null)
    const mediaRecorderRef = useRef(null)
    const audioChunksRef = useRef([])
    const audioCtxRef = useRef(null)

    // Clean up on unmount
    useEffect(() => () => wsRef.current?.close(), [])

    const connectWS = () => {
        const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
        const host = BACKEND.replace(/^https?:\/\//, '') || window.location.host
        const ws = new WebSocket(`${proto}://${host}/ws/live`)
        wsRef.current = ws

        ws.onopen = () => {
            ws.send(JSON.stringify({ type: 'init', home_team: homeTeam, away_team: awayTeam, sport }))
        }

        ws.onmessage = (e) => {
            if (typeof e.data === 'string') {
                const msg = JSON.parse(e.data)
                if (msg.type === 'ready') setStatus('idle')
                else if (msg.type === 'status') setAgentReply(msg.message)
                else if (msg.type === 'error') { setStatus('error'); setAgentReply(msg.message) }
            } else {
                // Binary audio data from Gemini — play it
                setStatus('speaking')
                playAudio(e.data)
            }
        }

        ws.onerror = () => setStatus('error')
        ws.onclose = () => { setStatus('idle'); wsRef.current = null }
    }

    const playAudio = async (arrayBuffer) => {
        if (!audioCtxRef.current) audioCtxRef.current = new AudioContext({ sampleRate: 16000 })
        const ctx = audioCtxRef.current
        const buffer = await ctx.decodeAudioData(arrayBuffer.slice(0))
        const source = ctx.createBufferSource()
        source.buffer = buffer
        source.connect(ctx.destination)
        source.onended = () => setStatus('idle')
        source.start()
    }

    const startListening = async () => {
        if (!matchReady) return
        if (!wsRef.current) connectWS()

        setStatus('listening')
        setTranscript('Listening...')
        audioChunksRef.current = []

        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })
        mediaRecorderRef.current = recorder

        recorder.ondataavailable = (e) => {
            audioChunksRef.current.push(e.data)
            if (wsRef.current?.readyState === WebSocket.OPEN) {
                wsRef.current.send(e.data)
            }
        }

        recorder.onstop = () => {
            stream.getTracks().forEach(t => t.stop())
            setStatus('speaking')
            setTranscript('Processing...')
        }

        recorder.start(250) // Send audio every 250ms
    }

    const stopListening = () => {
        mediaRecorderRef.current?.stop()
    }

    const handleTextQuery = async (e) => {
        e.preventDefault()
        if (!transcript || !matchReady) return
        setStatus('speaking')
        const res = await fetch(`${BACKEND}/api/v1/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: transcript, home_team: homeTeam, away_team: awayTeam }),
        })
        const data = await res.json()
        setAgentReply(data.answer)
        setStatus('idle')
    }

    const btnLabel = {
        idle: '🎙️',
        listening: '🔴',
        speaking: '🔊',
        error: '⚠️',
    }[status]

    return (
        <div className="ptt-section">
            <button
                className={`ptt-btn ${status}`}
                onMouseDown={startListening}
                onMouseUp={stopListening}
                onTouchStart={startListening}
                onTouchEnd={stopListening}
                disabled={!matchReady || status === 'speaking'}
                title={matchReady ? 'Hold to talk' : 'Build match notes first'}
            >
                {btnLabel}
            </button>

            <div className="ptt-info">
                <div className="ptt-title">Ask the Match</div>
                <div className="ptt-subtitle">
                    {status === 'idle' && (matchReady ? 'Hold mic to ask anything — pitch knowledge, rules, tactics.' : 'Build Match Notes first to enable Q&A.')}
                    {status === 'listening' && '🔴 Listening — release to send...'}
                    {status === 'speaking' && '🔊 Gemini is answering...'}
                    {status === 'error' && '⚠️ Connection error. Retry.'}
                </div>
            </div>

            <div className="ptt-transcript">
                {agentReply
                    ? <span className="agent-msg">🤖 {agentReply}</span>
                    : <span style={{ color: 'var(--text-muted)' }}>Agent responses appear here...</span>
                }
            </div>

            {/* Text fallback for browsers without mic */}
            <form onSubmit={handleTextQuery} style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                <input
                    type="text"
                    placeholder="Type a question..."
                    value={transcript}
                    onChange={e => setTranscript(e.target.value)}
                    style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)', padding: '6px 12px', fontFamily: 'inherit', fontSize: 13 }}
                />
                <button type="submit" className="btn btn-secondary" disabled={!matchReady}>Send</button>
            </form>
        </div>
    )
}
