import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

/* ── LandingPage — Midnight Stadium Design (UX Spec v2) ─────────────────────── */
export default function LandingPage() {
    const navigate = useNavigate()
    const [homeTeam, setHomeTeam] = useState('')
    const [awayTeam, setAwayTeam] = useState('')
    const [competition, setCompetition] = useState('')

    const openFanLens = (home = homeTeam, away = awayTeam, comp = competition) => {
        const params = new URLSearchParams({ tab: 'fan-lens' })
        if (home.trim()) params.set('home', home.trim())
        if (away.trim()) params.set('away', away.trim())
        if (comp.trim()) params.set('competition', comp.trim())
        navigate(`/live?${params.toString()}`)
    }

    const handleMatchSetup = (event) => {
        event.preventDefault()
        openFanLens()
    }

    const handleWatchDemo = () => {
        // For now, same route - can be extended to demo-specific flow
        navigate('/watch')
    }

    const handleFixtureClick = (fixture) => {
        setHomeTeam(fixture.home)
        setAwayTeam(fixture.away)
        setCompetition(fixture.competition)
        openFanLens(fixture.home, fixture.away, fixture.competition)
    }

    const presetFixtures = [
        { home: 'Real Madrid', away: 'Barcelona', competition: 'La Liga', label: 'El Clásico' },
        { home: 'Manchester United', away: 'Liverpool', competition: 'Premier League', label: 'Classic Rivalry' },
        { home: 'Bayern Munich', away: 'Borussia Dortmund', competition: 'Bundesliga', label: 'Der Klassiker' },
        { home: 'Argentina', away: 'France', competition: 'World Cup', label: 'Final Rematch' },
        { home: 'Manchester City', away: 'Arsenal', competition: 'Premier League', label: 'Title Clash' },
        { home: 'AC Milan', away: 'Inter Milan', competition: 'Serie A', label: 'Derby della Madonnina' },
    ]

    return (
        <div className="landing-page-v2">
            {/* Top Navigation Bar */}
            <header className="landing-header">
                <div className="landing-logo">PITCHSIDEAI</div>
                <nav className="landing-nav">
                    <button onClick={() => navigate('/live?tab=fan-lens')} className="nav-link">Fan Lens</button>
                    <button onClick={() => navigate('/live?tab=commentator')} className="nav-link">Broadcast Studio</button>
                    <button onClick={() => navigate('/live?tab=notes')} className="nav-link">Notes Hub</button>
                </nav>
                <div className="landing-actions">
                    <button className="icon-btn" aria-label="Settings">
                        <span className="material-icons">settings</span>
                    </button>
                    <button className="icon-btn" aria-label="Account">
                        <span className="material-icons">account_circle</span>
                    </button>
                </div>
            </header>

            {/* Hero Section */}
            <section className="landing-hero-section">
                <div className="hero-background-plain" />

                <div className="hero-content">
                    {/* Live Badge */}
                    <div className="live-badge">
                        <span className="badge-dot" />
                        AI Match Companion
                    </div>

                    {/* Headline - "PitchSideAI: The Future of" + "Football Intelligence" in green */}
                    <h1 className="landing-hero-title">
                        PitchSideAI: The Future of{' '}
                        <span className="landing-title-gradient">Football Intelligence</span>
                    </h1>

                    <p className="hero-subtitle">
                        Prepare match context, upload your own footage, and turn it into
                        personalized Q&A, commentary, and broadcast-ready intelligence.
                    </p>

                    <form className="match-context-panel" onSubmit={handleMatchSetup}>
                        <div className="match-context-header">
                            <span className="material-icons">sports_soccer</span>
                            <span>Set Match Context</span>
                        </div>
                        <div className="match-context-grid">
                            <label className="context-field">
                                <span>Home Team</span>
                                <input
                                    value={homeTeam}
                                    onChange={(event) => setHomeTeam(event.target.value)}
                                    placeholder="e.g., Real Madrid"
                                    autoComplete="off"
                                />
                            </label>
                            <label className="context-field">
                                <span>Away Team</span>
                                <input
                                    value={awayTeam}
                                    onChange={(event) => setAwayTeam(event.target.value)}
                                    placeholder="e.g., Barcelona"
                                    autoComplete="off"
                                />
                            </label>
                            <label className="context-field context-field-wide">
                                <span>Competition</span>
                                <input
                                    value={competition}
                                    onChange={(event) => setCompetition(event.target.value)}
                                    placeholder="Optional"
                                    autoComplete="off"
                                />
                            </label>
                        </div>
                        <p className="context-note">
                            PitchSideAI prepares team intelligence here. Video-aware commentary and Q&A start after you upload footage you have the right to use.
                        </p>
                        <button
                            className="btn-primary context-submit"
                            type="submit"
                            disabled={!homeTeam.trim() || !awayTeam.trim()}
                        >
                            <span className="btn-content">
                                Open Fan Lens
                                <span className="material-icons">arrow_forward</span>
                            </span>
                        </button>
                    </form>

                    <div className="hero-ctas secondary-ctas">
                        <button
                            className="btn-secondary"
                            onClick={() => {
                                setHomeTeam(presetFixtures[0].home)
                                setAwayTeam(presetFixtures[0].away)
                                setCompetition(presetFixtures[0].competition)
                            }}
                        >
                            Use Sample Context
                            <span className="material-icons">input</span>
                        </button>

                        <button
                            className="btn-secondary"
                            onClick={handleWatchDemo}
                        >
                            Watch Demo
                            <span className="material-icons">play_arrow</span>
                        </button>
                    </div>

                    <div className="now-live-indicator">
                        <span className="live-dot" />
                        Sample context: {presetFixtures[0].home} vs. {presetFixtures[0].away}
                    </div>
                </div>
            </section>

            {/* Matchup Presets Section */}
            <section className="quick-matches-section">
                <div className="quick-matches-content">
                    <h2 className="quick-matches-title">Matchup Presets</h2>
                    <p className="quick-matches-subtitle">
                        Use these as team-context shortcuts. They do not include broadcast video.
                    </p>
                    <div className="fixture-grid">
                        {presetFixtures.map((fixture, index) => (
                            <button
                                key={index}
                                className="fixture-button"
                                onClick={() => handleFixtureClick(fixture)}
                            >
                                <div className="fixture-matchup">
                                    <span className="fixture-home">{fixture.home}</span>
                                    <span className="fixture-vs">vs</span>
                                    <span className="fixture-away">{fixture.away}</span>
                                </div>
                                <div className="fixture-meta">
                                    <span className="fixture-competition">{fixture.competition}</span>
                                    <span className="fixture-label">{fixture.label} context</span>
                                </div>
                            </button>
                        ))}
                    </div>
                </div>
            </section>

            {/* Three Pillars Section */}
            <section className="pillars-section">
                <div className="pillars-header">
                    <h2 className="section-title">The Next Evolution of Broadcast</h2>
                    <p className="section-subtitle">
                        Elevating the viewing experience through real-time multi-agent intelligence.
                    </p>
                </div>

                <div className="pillars-grid">
                    {/* Pillar 1: Commentary Notes */}
                    <div className="pillar-card">
                        <div className="pillar-icon">
                            <span className="material-icons">mic</span>
                        </div>
                        <h3 className="pillar-title">Broadcast Notes Engine</h3>
                        <p className="pillar-description">
                            Multi-agent research builds the story before the clip starts:
                            player context, tactical themes, rivalry history, and phrasing
                            a commentator can actually use.
                        </p>
                    </div>

                    {/* Pillar 2: Contextual Q&A */}
                    <div className="pillar-card">
                        <div className="pillar-icon">
                            <span className="material-icons">splitscreen</span>
                        </div>
                        <h3 className="pillar-title">Fan Lens Q&A</h3>
                        <p className="pillar-description">
                            Upload your own footage, ask what happened, and get visually
                            grounded answers with split-screen replay context and overlays.
                        </p>
                    </div>

                    {/* Pillar 3: Cross-Language */}
                    <div className="pillar-card">
                        <div className="pillar-icon">
                            <span className="material-icons">translate</span>
                        </div>
                        <h3 className="pillar-title">Personalized Commentary</h3>
                        <p className="pillar-description">
                            Tune bias, excitement, language, and knowledge depth so Fan
                            Lens explains the same clip like a neutral analyst, a beginner
                            guide, or a supporter beside you.
                        </p>
                    </div>
                </div>
            </section>

            {/* Architecture Section */}
            <section className="architecture-section">
                <div className="architecture-content">
                    <div className="architecture-text">
                        <div className="architecture-label">
                            <span className="material-icons">memory</span>
                            Architecture
                        </div>
                        <h2 className="architecture-title">
                            Built for{' '}
                            <span className="text-accent">Performance</span>
                        </h2>
                        <p className="architecture-description">
                            Powered by the AMD MI300X GPU and StreamingVLM architecture,
                            PitchSideAI processes high-frame-rate video streams with sub-second
                            latency. Our multi-agent pipeline parallelizes vision tasks,
                            narrative generation, and stat retrieval to deliver real-time
                            broadcast enhancements.
                        </p>
                        <div className="architecture-features">
                            <div className="feature-chip">
                                <span className="material-icons">bolt</span>
                                <span>Sub-50ms Latency</span>
                            </div>
                            <div className="feature-chip">
                                <span className="material-icons">memory</span>
                                <span>AMD MI300X</span>
                            </div>
                        </div>
                    </div>

                    {/* Architecture Diagram */}
                    <div className="architecture-diagram">
                        <div className="diagram-row diagram-row-single">
                            <div className="diagram-node">
                                Live Video Ingestion
                                <span className="material-icons">videocam</span>
                            </div>
                        </div>
                        <div className="diagram-connector" />
                        <div className="diagram-row diagram-row-agents">
                            <div className="diagram-node accent">Vision Agent (VLM)</div>
                            <div className="diagram-node">Data Agent (Stats)</div>
                        </div>
                        <div className="diagram-connector" />
                        <div className="diagram-row diagram-row-single">
                            <div className="diagram-node full-width">
                                Synthesis Engine (LLM)
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Footer */}
            <footer className="landing-footer">
                <div className="footer-content">
                    <h4 className="footer-logo">PITCHSIDEAI</h4>
                    <p className="footer-tagline">Real-time AI Football Commentary</p>
                    <div className="footer-links">
                        <a href="#" className="footer-link">
                            <span className="material-icons">code</span>
                            GitHub
                        </a>
                        <a href="#" className="footer-link">
                            <span className="material-icons">public</span>
                            Hugging Face Space
                        </a>
                    </div>
                    <div className="footer-divider" />
                    <p className="footer-copyright">© 2026 PitchSideAI Team.</p>
                </div>
            </footer>
        </div>
    )
}
