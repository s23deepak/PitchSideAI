import { useState } from 'react'

/* ── HomeScreen — Gemini-style Landing Page ─────────────────────────────────── */
export default function HomeScreen({ onStartMatch }) {
    const [homeTeam, setHomeTeam] = useState('')
    const [awayTeam, setAwayTeam] = useState('')
    const [isLoading, setIsLoading] = useState(false)

    const handleStart = async (e) => {
        e.preventDefault()
        if (!homeTeam.trim() || !awayTeam.trim()) return

        setIsLoading(true)
        try {
            await onStartMatch?.(homeTeam.trim(), awayTeam.trim())
        } finally {
            setIsLoading(false)
        }
    }

    const quickMatches = [
        { home: 'Manchester United', away: 'Liverpool', label: 'Premier League Classic' },
        { home: 'Real Madrid', away: 'Barcelona', label: 'El Clásico' },
        { home: 'Bayern Munich', away: 'Borussia Dortmund', label: 'Der Klassiker' },
        { home: 'Argentina', away: 'France', label: 'World Cup Final Rematch' },
    ]

    return (
        <div className="home-screen">
            <div className="home-screen-content">
                {/* Hero Section */}
                <div className="hero-section">
                    <div className="hero-icon">⚽</div>
                    <h1 className="hero-title">PitchSide AI</h1>
                    <p className="hero-subtitle">
                        Your intelligent football companion for the 2026 FIFA World Cup
                    </p>
                    <p className="hero-description">
                        Live commentary, tactical analysis, and instant answers — powered by AI.
                    </p>
                </div>

                {/* Match Input Card */}
                <div className="match-input-card">
                    <h2 className="card-title">Start a Live Match</h2>
                    <form onSubmit={handleStart} className="match-form">
                        <div className="team-inputs">
                            <div className="input-group">
                                <label htmlFor="home-team">Home Team</label>
                                <input
                                    id="home-team"
                                    type="text"
                                    placeholder="e.g., Manchester United"
                                    value={homeTeam}
                                    onChange={(e) => setHomeTeam(e.target.value)}
                                    className="team-input"
                                    autoComplete="off"
                                />
                            </div>

                            <div className="vs-divider">vs</div>

                            <div className="input-group">
                                <label htmlFor="away-team">Away Team</label>
                                <input
                                    id="away-team"
                                    type="text"
                                    placeholder="e.g., Liverpool"
                                    value={awayTeam}
                                    onChange={(e) => setAwayTeam(e.target.value)}
                                    className="team-input"
                                    autoComplete="off"
                                />
                            </div>
                        </div>

                        <button
                            type="submit"
                            className="start-match-btn"
                            disabled={isLoading || !homeTeam.trim() || !awayTeam.trim()}
                        >
                            {isLoading ? (
                                <>
                                    <span className="spinner" />
                                    Starting Match...
                                </>
                            ) : (
                                <>
                                    <span>🎯</span>
                                    Start Live Commentary
                                </>
                            )}
                        </button>
                    </form>
                </div>

                {/* Quick Match Suggestions */}
                <div className="quick-matches">
                    <p className="quick-matches-label">Or try a classic matchup:</p>
                    <div className="quick-match-grid">
                        {quickMatches.map((match, idx) => (
                            <button
                                key={idx}
                                className="quick-match-chip"
                                onClick={() => {
                                    setHomeTeam(match.home)
                                    setAwayTeam(match.away)
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

                {/* Features Section */}
                <div className="features-section">
                    <div className="feature-card">
                        <div className="feature-icon">📺</div>
                        <h3>Live Video Analysis</h3>
                        <p>Stream match footage and get real-time tactical commentary every 10 seconds</p>
                    </div>
                    <div className="feature-card">
                        <div className="feature-icon">🎙️</div>
                        <h3>Voice Q&A</h3>
                        <p>Ask questions verbally and get instant answers about the match</p>
                    </div>
                    <div className="feature-card">
                        <div className="feature-icon">📊</div>
                        <h3>Tactical Insights</h3>
                        <p>Deep analysis of formations, pressing patterns, and key moments</p>
                    </div>
                </div>
            </div>
        </div>
    )
}
