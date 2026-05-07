import { useNavigate } from 'react-router-dom'

/* ── LandingPage — Midnight Stadium Design (UX Spec v2) ─────────────────────── */
export default function LandingPage() {
    const navigate = useNavigate()

    const handleEnterLiveStream = () => {
        navigate('/live?tab=fan-lens')
    }

    const handleWatchDemo = () => {
        // For now, same route - can be extended to demo-specific flow
        navigate('/watch')
    }

    const quickMatches = [
        { home: 'Barcelona', away: 'Real Madrid', label: 'Now Live' },
    ]

    return (
        <div className="landing-page-v2">
            {/* Top Navigation Bar */}
            <header className="landing-header">
                <div className="landing-logo">PITCH AI</div>
                <nav className="landing-nav">
                    <button onClick={() => navigate('/live?tab=fan-lens')} className="nav-link">Fan Lens</button>
                    <button onClick={() => navigate('/live?tab=commentator')} className="nav-link">Commentator</button>
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
                        Live Broadcast Companion
                    </div>

                    {/* Headline - "PitchAI: The Future of" + "Football Intelligence" in green */}
                    <h1 className="landing-hero-title">
                        PitchAI: The Future of{' '}
                        <span className="landing-title-gradient">Football Intelligence</span>
                    </h1>

                    {/* Subtitle */}
                    <p className="hero-subtitle">
                        A Proactive AI Broadcast Companion for Fans and Commentators.
                        Delivering real-time narrative intelligence, contextual stream Q&A,
                        and cross-language mastery.
                    </p>

                    {/* CTAs */}
                    <div className="hero-ctas">
                        <button
                            className="btn-primary"
                            onClick={handleEnterLiveStream}
                        >
                            <span className="btn-content">
                                Enter Live Stream
                                <span className="material-icons">sensors</span>
                            </span>
                            <span className="btn-indicator">
                                <span className="indicator-dot" />
                            </span>
                        </button>

                        <button
                            className="btn-secondary"
                            onClick={handleWatchDemo}
                        >
                            Watch Demo
                            <span className="material-icons">play_arrow</span>
                        </button>
                    </div>

                    {/* Now Live Indicator */}
                    <div className="now-live-indicator">
                        <span className="live-dot" />
                        Now Live: {quickMatches[0].home} vs. {quickMatches[0].away}
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
                        <h3 className="pillar-title">Commentary Notes Engine</h3>
                        <p className="pillar-description">
                            Peter Drury-style narrative intelligence. AI agents analyze
                            real-time play to surface compelling stats, historical context,
                            and poetic phrasing directly to commentators.
                        </p>
                    </div>

                    {/* Pillar 2: Contextual Q&A */}
                    <div className="pillar-card">
                        <div className="pillar-icon">
                            <span className="material-icons">splitscreen</span>
                        </div>
                        <h3 className="pillar-title">Contextual Stream Q&A</h3>
                        <p className="pillar-description">
                            Split-screen temporal navigation with AI overlays. Ask questions
                            about the live feed and receive instant, visually-grounded answers
                            highlighting key players and movements.
                        </p>
                    </div>

                    {/* Pillar 3: Cross-Language */}
                    <div className="pillar-card">
                        <div className="pillar-icon">
                            <span className="material-icons">translate</span>
                        </div>
                        <h3 className="pillar-title">Cross-Language Commentary</h3>
                        <p className="pillar-description">
                            Meaning-preserving translation that maintains the emotion,
                            idioms, and pace of the original broadcast, ensuring a global
                            audience feels the intensity.
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
                            PitchAI processes high-frame-rate video streams with sub-second
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
                        <div className="diagram-row">
                            <div className="diagram-node">
                                Live Video Ingestion
                                <span className="material-icons">videocam</span>
                            </div>
                        </div>
                        <div className="diagram-connector" />
                        <div className="diagram-row">
                            <div className="diagram-node accent">Vision Agent (VLM)</div>
                            <div className="diagram-node">Data Agent (Stats)</div>
                        </div>
                        <div className="diagram-connector" />
                        <div className="diagram-row">
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
                    <h4 className="footer-logo">PITCH AI</h4>
                    <p className="footer-tagline">Built for the AMD Hackathon 2026</p>
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
                    <p className="footer-copyright">© 2026 PitchAI Team.</p>
                </div>
            </footer>
        </div>
    )
}
