import { useState, useRef } from 'react'

const BACKEND = import.meta.env.VITE_BACKEND_URL || ''

const ICON_MAP = {
    'High Press': '⬆️',
    'Low Block': '🛡️',
    'Counter Attack': '⚡',
    'Build-Up Play': '🔄',
    'Set Piece': '🎯',
    'Transition': '↔️',
    'Normal Play': '⚽',
    'Attacking Field': '🏏',
    'Defensive Field': '🛡️',
    'Spin Attack': '🌀',
    'Pace Attack': '💨',
}

/* Soccer pitch SVG with dynamic formation dots */
function SoccerPitch({ detection }) {
    return (
        <svg className="pitch-svg" viewBox="0 0 400 280" xmlns="http://www.w3.org/2000/svg">
            {/* Pitch lines */}
            <rect x="10" y="10" width="380" height="260" fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="2" rx="4" />
            {/* Centre circle */}
            <circle cx="200" cy="140" r="40" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="1.5" />
            <line x1="200" y1="10" x2="200" y2="270" stroke="rgba(255,255,255,0.2)" strokeWidth="1.5" />
            <circle cx="200" cy="140" r="3" fill="rgba(255,255,255,0.4)" />
            {/* Penalty areas */}
            <rect x="10" y="80" width="80" height="120" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="1.5" />
            <rect x="310" y="80" width="80" height="120" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="1.5" />
            {/* Goals */}
            <rect x="10" y="110" width="18" height="60" fill="rgba(255,255,255,0.08)" stroke="rgba(255,255,255,0.3)" strokeWidth="1.5" />
            <rect x="372" y="110" width="18" height="60" fill="rgba(255,255,255,0.08)" stroke="rgba(255,255,255,0.3)" strokeWidth="1.5" />

            {/* Formation dots — home team (blue) */}
            {[
                [50, 140],  // GK
                [100, 80], [100, 140], [100, 200],  // defence
                [150, 100], [150, 180],              // midfield
                [175, 140],                           // CM
                [190, 80], [190, 200],               // wings
                [210, 140],                           // striker
            ].map(([cx, cy], i) => (
                <circle key={`h${i}`} cx={cx} cy={cy} r="7" fill="rgba(79,156,249,0.85)" stroke="white" strokeWidth="1.5" />
            ))}

            {/* Formation dots — away team (red) */}
            {[
                [350, 140],  // GK
                [300, 80], [300, 140], [300, 200],  // defence
                [250, 100], [250, 180],              // midfield
                [225, 140],                           // CM
                [210, 80], [210, 200],               // wings
                [230, 140],                           // striker
            ].map(([cx, cy], i) => (
                <circle key={`a${i}`} cx={cx} cy={cy} r="7" fill="rgba(248,113,113,0.85)" stroke="white" strokeWidth="1.5" />
            ))}

            {/* Ball */}
            <circle cx="200" cy="140" r="5" fill="white" opacity="0.9" />
        </svg>
    )
}

export default function TacticalOverlay({ sport }) {
    const [detection, setDetection] = useState(null)
    const [loading, setLoading] = useState(false)
    const fileInputRef = useRef()

    const handleFileChange = async (e) => {
        const file = e.target.files[0]
        if (!file) return
        setLoading(true)

        const reader = new FileReader()
        reader.onload = async (ev) => {
            const b64 = ev.target.result.split(',')[1]
            try {
                const res = await fetch(`${BACKEND}/api/frame`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ frame_b64: b64, sport }),
                })
                const data = await res.json()
                setDetection(data)
            } catch (err) {
                console.error('Frame analysis failed', err)
            } finally {
                setLoading(false)
            }
        }
        reader.readAsDataURL(file)
    }

    return (
        <div className="tactical-section">
            <div className="pitch-container">
                <SoccerPitch detection={detection} />
                {detection && (
                    <div className="tactical-label-badge">
                        {ICON_MAP[detection.tactical_label] || '⚽'} {detection.tactical_label}
                    </div>
                )}
            </div>

            <div className="tactical-info">
                <div className="detection-card">
                    <div className="detection-label">Tactical Label</div>
                    <div className="detection-value">
                        {detection ? detection.tactical_label : '—'}
                    </div>
                    {detection?.key_observation && (
                        <div className="detection-sub">{detection.key_observation}</div>
                    )}
                    {detection?.confidence != null && (
                        <>
                            <div className="confidence-bar">
                                <div className="confidence-fill" style={{ width: `${detection.confidence * 100}%` }} />
                            </div>
                            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                                {Math.round(detection.confidence * 100)}% confidence
                            </div>
                        </>
                    )}
                </div>

                <div className="detection-card">
                    <div className="detection-label">Formation (Home)</div>
                    <div className="detection-value">{detection?.formation_home || '4-3-3'}</div>
                </div>

                <div className="detection-card">
                    <div className="detection-label">Formation (Away)</div>
                    <div className="detection-value">{detection?.formation_away || '4-2-3-1'}</div>
                </div>

                <button className="upload-frame-btn" onClick={() => fileInputRef.current.click()} disabled={loading}>
                    {loading ? <><span className="spinner" /> Analyzing...</> : <>📸 Upload Frame</>}
                </button>
                <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    style={{ display: 'none' }}
                    onChange={handleFileChange}
                />
            </div>
        </div>
    )
}
