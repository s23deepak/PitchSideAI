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

            {/* Formation dots — home team (blue) 4-3-3 */}
            {[
                [50, 140],  // GK
                [100, 50], [100, 110], [100, 170], [100, 230], // DEF x4
                [150, 80], [150, 140], [150, 200],  // MID x3
                [210, 80], [210, 140], [210, 200],  // FWD x3
            ].map(([cx, cy], i) => (
                <circle key={`h${i}`} cx={cx} cy={cy} r="7" fill="rgba(79,156,249,0.85)" stroke="white" strokeWidth="1.5" />
            ))}

            {/* Formation dots — away team (red) 4-2-3-1 */}
            {[
                [350, 140],  // GK
                [300, 50], [300, 110], [300, 170], [300, 230], // DEF x4
                [260, 100], [260, 180], // CDM x2
                [220, 60], [220, 140], [220, 220], // CAM x3
                [180, 140],  // ST x1
            ].map(([cx, cy], i) => (
                <circle key={`a${i}`} cx={cx} cy={cy} r="7" fill="rgba(248,113,113,0.85)" stroke="white" strokeWidth="1.5" />
            ))}

            {/* Ball */}
            <circle cx="200" cy="140" r="5" fill="white" opacity="0.9" />
        </svg>
    )
}

export default function TacticalOverlay({ sport, detection, setDetection }) {
    const [loading, setLoading] = useState(false)
    const [previewUrl, setPreviewUrl] = useState(null)
    const fileInputRef = useRef()

    const handleFileChange = async (e) => {
        const file = e.target.files[0]
        if (!file) return
        setLoading(true)

        const reader = new FileReader()
        reader.onload = async (ev) => {
            const dataUrl = ev.target.result
            setPreviewUrl(dataUrl)
            const b64 = dataUrl.split(',')[1]
            try {
                const res = await fetch(`${BACKEND}/api/v1/frame/analyze`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ frame_b64: b64, sport }),
                })
                const data = await res.json()
                if (data.status === 'success') {
                    setDetection(data.analysis)
                } else {
                    console.error('Frame analysis returned error:', data)
                }
            } catch (err) {
                console.error('Frame analysis failed', err)
            } finally {
                setLoading(false)
                if (fileInputRef.current) {
                    fileInputRef.current.value = ''
                }
            }
        }
        reader.readAsDataURL(file)
    }

    return (
        <div className="tactical-section" style={{ flexDirection: 'column', alignItems: 'center', width: '100%', gap: '1.5rem' }}>
            <div className="pitch-container" style={{ width: '100%', position: 'relative' }}>
                {previewUrl ? (
                    <img src={previewUrl} alt="Uploaded Frame" style={{ width: '100%', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.2)', objectFit: 'contain' }} />
                ) : (
                    <SoccerPitch detection={detection} />
                )}
                {detection && (
                    <div className="tactical-label-badge" style={{ position: 'absolute', top: 16, left: 16, zIndex: 10 }}>
                        {ICON_MAP[detection.tactical_label] || '⚽'} {detection.tactical_label}
                    </div>
                )}
            </div>

            <div className="tactical-controls" style={{ width: '100%' }}>
                <button
                    className="upload-frame-btn"
                    onClick={() => fileInputRef.current.click()}
                    disabled={loading}
                    style={{ width: '100%', padding: '14px', fontSize: '1.1rem', fontWeight: 600 }}
                >
                    {loading ? <><span className="spinner" /> Analyzing Frame...</> : <>📸 Upload Live Broadcast Frame</>}
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
