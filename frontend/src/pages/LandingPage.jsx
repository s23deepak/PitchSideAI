import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

/* ── LandingPage — Self-Guided Demo Entry Point (Story 4.2) ─────────────────── */
export default function LandingPage() {
    const navigate = useNavigate()
    const [isHovered, setIsHovered] = useState(false)

    const handleStartWatching = () => {
        navigate('/watch')
    }

    const quickMatches = [
        { home: 'Roma', away: 'Napoli', label: 'Serie A 2023/24' },
        { home: 'Manchester City', away: 'Arsenal', label: 'Premier League' },
        { home: 'Real Madrid', away: 'Barcelona', label: 'El Clásico' },
    ]

    return (
        <div className="landing-page">
            {/* Centered Hero Section */}
            <div className="landing-hero">
                <h1 className="landing-title">PitchAI</h1>
                <p className="landing-tagline">Your AI Broadcast Companion</p>

                {/* Amber Pill CTA Button */}
                <button
                    className="landing-cta"
                    onClick={handleStartWatching}
                    onMouseEnter={() => setIsHovered(true)}
                    onMouseLeave={() => setIsHovered(false)}
                    onFocus={() => setIsHovered(true)}
                    onBlur={() => setIsHovered(false)}
                    style={{
                        background: isHovered ? '#F59E0B' : '#FBBF24',
                        color: '#020617',
                        border: 'none',
                        borderRadius: '9999px',
                        padding: '12px 32px',
                        fontSize: '16px',
                        fontWeight: '600',
                        cursor: 'pointer',
                        transition: 'background-color 0.2s ease',
                        marginTop: '24px',
                    }}
                >
                    Start Watching
                </button>

                {/* Feature Pills */}
                <div className="feature-pills">
                    <span className="feature-pill">Live Commentary Notes</span>
                    <span className="feature-pill">Contextual Q&A</span>
                    <span className="feature-pill">Cross-Language Translation</span>
                </div>
            </div>

            {/* Quick Match Suggestions (Self-Guided Mode) */}
            <div className="quick-matches-section">
                <p className="quick-matches-label">Try a sample match:</p>
                <div className="quick-match-grid">
                    {quickMatches.map((match, idx) => (
                        <button
                            key={idx}
                            className="quick-match-chip"
                            onClick={() => {
                                // Store selected match for demo mode
                                localStorage.setItem('pitchai_demo_match', JSON.stringify(match))
                                navigate('/watch')
                            }}
                        >
                            <span className="quick-match-teams">
                                {match.home} vs {match.away}
                            </span>
                            <span className="quick-match-label">{match.label}</span>
                        </button>
                    ))}
                </div>
            </div>

            {/* Green Pitch Line Accent */}
            <div className="pitch-accent-line" />
        </div>
    )
}
