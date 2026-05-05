import { useState, useRef, useEffect } from 'react'

/**
 * ControlsTray — Story 3.3 & 3.4: Commentary Settings & Language Toggle
 *
 * Five controls in a bottom bar:
 * - Language toggle (EN | ES)
 * - Bias slider (Team A fan [-1] to Neutral [0] to Team B fan [+1])
 * - Excitement slider (Subdued [0] to Maximum [1])
 * - Knowledge Depth slider (Beginner [0] to Tactical [1])
 * - View toggle (Fan Lens / Commentator Dashboard)
 */
export default function ControlsTray({
    homeTeam,
    awayTeam,
    onSettingsChange,
    onLanguageChange,
    onViewChange,
    currentView = 'fan', // 'fan' | 'commentator'
}) {
    // Settings state
    const [bias, setBias] = useState(0) // -1 to +1
    const [excitement, setExcitement] = useState(0.5) // 0 to 1
    const [knowledgeDepth, setKnowledgeDepth] = useState(0.5) // 0 to 1
    const [language, setLanguage] = useState('en') // 'en' | 'es'
    const [isHovering, setIsHovering] = useState(false)
    const [hasSeenTooltip, setHasSeenTooltip] = useState(false)

    const trayRef = useRef(null)
    const idleTimeoutRef = useRef(null)

    // Load seen-tooltip state from localStorage
    useEffect(() => {
        const stored = localStorage.getItem('pitchai-controls-tooltip-seen')
        if (stored === 'true') {
            setHasSeenTooltip(true)
        }
    }, [])

    // Auto-hide tray in Community Visitor mode after 3s idle
    useEffect(() => {
        const resetIdleTimer = () => {
            setIsHovering(true)
            clearTimeout(idleTimeoutRef.current)
            idleTimeoutRef.current = setTimeout(() => {
                setIsHovering(false)
            }, 3000)
        }

        const tray = trayRef.current
        if (tray) {
            tray.addEventListener('mousemove', resetIdleTimer)
            tray.addEventListener('mouseleave', () => {
                clearTimeout(idleTimeoutRef.current)
                idleTimeoutRef.current = setTimeout(() => {
                    setIsHovering(false)
                }, 3000)
            })
        }

        return () => {
            clearTimeout(idleTimeoutRef.current)
            if (tray) {
                tray.removeEventListener('mousemove', resetIdleTimer)
                tray.removeEventListener('mouseleave', resetIdleTimer)
            }
        }
    }, [])

    // Send settings update via WebSocket
    const sendSettingsUpdate = (newBias, newExcitement, newKnowledge) => {
        const message = {
            type: 'settings_update',
            bias: newBias,
            excitement: newExcitement,
            knowledge_depth: newKnowledge,
        }

        // Send to WebSocket if available (via parent component)
        onSettingsChange?.(message)

        // Also dispatch custom event for parent to handle
        window.dispatchEvent(new CustomEvent('pitchai:settings', { detail: message }))
    }

    // Handle language toggle
    const handleLanguageToggle = () => {
        const newLanguage = language === 'en' ? 'es' : 'en'
        setLanguage(newLanguage)

        onLanguageChange?.({ language: newLanguage })

        // Dispatch custom event
        window.dispatchEvent(new CustomEvent('pitchai:language', {
            detail: { language: newLanguage }
        }))
    }

    // Handle view toggle
    const handleViewToggle = () => {
        const newView = currentView === 'fan' ? 'commentator' : 'fan'
        onViewChange?.(newView)
    }

    // Slider change handlers
    const handleBiasChange = (e) => {
        const newValue = parseFloat(e.target.value)
        setBias(newValue)
        sendSettingsUpdate(newValue, excitement, knowledgeDepth)
    }

    const handleExcitementChange = (e) => {
        const newValue = parseFloat(e.target.value)
        setExcitement(newValue)
        sendSettingsUpdate(bias, newValue, knowledgeDepth)
    }

    const handleKnowledgeChange = (e) => {
        const newValue = parseFloat(e.target.value)
        setKnowledgeDepth(newValue)
        sendSettingsUpdate(bias, excitement, newValue)
    }

    // Keyboard navigation with proper min/max bounds per slider
    const handleKeyDown = (e, setter, currentValue, step = 0.1, min = -1, max = 1) => {
        if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
            e.preventDefault()
            setter(Math.max(currentValue - step, min))
        } else if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
            e.preventDefault()
            setter(Math.min(currentValue + step, max))
        }
    }

    // Keyboard handler that also sends settings update (fix #10, #11)
    const handleBiasKeyDown = (e) => {
        if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
            e.preventDefault()
            const newValue = Math.max(bias - 0.1, -1)
            setBias(newValue)
            sendSettingsUpdate(newValue, excitement, knowledgeDepth)
        } else if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
            e.preventDefault()
            const newValue = Math.min(bias + 0.1, 1)
            setBias(newValue)
            sendSettingsUpdate(newValue, excitement, knowledgeDepth)
        }
    }

    const handleExcitementKeyDown = (e) => {
        if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
            e.preventDefault()
            const newValue = Math.max(excitement - 0.1, 0)
            setExcitement(newValue)
            sendSettingsUpdate(bias, newValue, knowledgeDepth)
        } else if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
            e.preventDefault()
            const newValue = Math.min(excitement + 0.1, 1)
            setExcitement(newValue)
            sendSettingsUpdate(bias, newValue, knowledgeDepth)
        }
    }

    const handleKnowledgeKeyDown = (e) => {
        if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
            e.preventDefault()
            const newValue = Math.max(knowledgeDepth - 0.1, 0)
            setKnowledgeDepth(newValue)
            sendSettingsUpdate(bias, excitement, newValue)
        } else if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
            e.preventDefault()
            const newValue = Math.min(knowledgeDepth + 0.1, 1)
            setKnowledgeDepth(newValue)
            sendSettingsUpdate(bias, excitement, newValue)
        }
    }

    // Tooltip content
    const getTooltip = (control) => {
        if (hasSeenTooltip) return null

        const tooltips = {
            language: 'Switch commentary language between English and Spanish',
            bias: `Adjust commentary bias: ${homeTeam} fan ← → ${awayTeam} fan`,
            excitement: 'Adjust excitement level: Subdued ← → Maximum',
            knowledge: 'Adjust tactical depth: Beginner ← → Expert',
            view: 'Switch view: Fan Lens ← → Commentator Dashboard',
        }
        return tooltips[control]
    }

    const [showTooltip, setShowTooltip] = useState(null)

    const handleMouseEnter = (control) => {
        if (!hasSeenTooltip) {
            setShowTooltip(control)
            localStorage.setItem('pitchai-controls-tooltip-seen', 'true')
            setHasSeenTooltip(true)
        }
    }

    return (
        <div
            className={`controls-tray ${isHovering ? 'visible' : ''}`}
            ref={trayRef}
            role="toolbar"
            aria-label="Commentary controls"
        >
            {/* Language Toggle */}
            <div
                className="control-group"
                onMouseEnter={() => handleMouseEnter('language')}
                onMouseLeave={() => setShowTooltip(null)}
            >
                <button
                    className="language-toggle"
                    onClick={handleLanguageToggle}
                    onKeyDown={(e) => e.key === 'Enter' && handleLanguageToggle()}
                    aria-label={`Switch commentary to ${language === 'en' ? 'Spanish' : 'English'}`}
                    tabIndex={0}
                >
                    <span className={`lang-code ${language === 'en' ? 'active' : ''}`}>EN</span>
                    <span className="lang-separator">|</span>
                    <span className={`lang-code ${language === 'es' ? 'active' : ''}`}>ES</span>
                </button>
                {showTooltip === 'language' && (
                    <div className="control-tooltip">Switch commentary language between English and Spanish</div>
                )}
            </div>

            {/* Bias Slider */}
            <div
                className="control-group"
                onMouseEnter={() => handleMouseEnter('bias')}
                onMouseLeave={() => setShowTooltip(null)}
            >
                <label className="slider-label" id="bias-label">
                    Bias
                </label>
                <div className="slider-container slider-bias">
                    <span className="slider-min">{homeTeam.slice(0, 3)}</span>
                    <input
                        type="range"
                        min="-1"
                        max="1"
                        step="0.01"
                        value={bias}
                        onChange={handleBiasChange}
                        onKeyDown={handleBiasKeyDown}
                        aria-labelledby="bias-label"
                        aria-valuemin="-1"
                        aria-valuemax="1"
                        aria-valuenow={bias}
                        tabIndex={0}
                    />
                    <span className="slider-max">{awayTeam.slice(0, 3)}</span>
                </div>
                {showTooltip === 'bias' && (
                    <div className="control-tooltip">Adjust commentary bias: {homeTeam} fan to {awayTeam} fan</div>
                )}
            </div>

            {/* Excitement Slider */}
            <div
                className="control-group"
                onMouseEnter={() => handleMouseEnter('excitement')}
                onMouseLeave={() => setShowTooltip(null)}
            >
                <label className="slider-label" id="excitement-label">
                    Excitement
                </label>
                <div className="slider-container slider-excitement">
                    <span className="slider-min">Calm</span>
                    <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.01"
                        value={excitement}
                        onChange={handleExcitementChange}
                        onKeyDown={handleExcitementKeyDown}
                        aria-labelledby="excitement-label"
                        aria-valuemin="0"
                        aria-valuemax="1"
                        aria-valuenow={excitement}
                        tabIndex={0}
                    />
                    <span className="slider-max">Hype</span>
                </div>
                {showTooltip === 'excitement' && (
                    <div className="control-tooltip">Adjust excitement level from calm to maximum</div>
                )}
            </div>

            {/* Knowledge Depth Slider */}
            <div
                className="control-group"
                onMouseEnter={() => handleMouseEnter('knowledge')}
                onMouseLeave={() => setShowTooltip(null)}
            >
                <label className="slider-label" id="knowledge-label">
                    Knowledge
                </label>
                <div className="slider-container slider-knowledge">
                    <span className="slider-min">Basic</span>
                    <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.01"
                        value={knowledgeDepth}
                        onChange={handleKnowledgeChange}
                        onKeyDown={handleKnowledgeKeyDown}
                        aria-labelledby="knowledge-label"
                        aria-valuemin="0"
                        aria-valuemax="1"
                        aria-valuenow={knowledgeDepth}
                        tabIndex={0}
                    />
                    <span className="slider-max">Tactical</span>
                </div>
                {showTooltip === 'knowledge' && (
                    <div className="control-tooltip">Adjust tactical depth from beginner to expert</div>
                )}
            </div>

            {/* View Toggle */}
            <div
                className="control-group"
                onMouseEnter={() => handleMouseEnter('view')}
                onMouseLeave={() => setShowTooltip(null)}
            >
                <button
                    className="view-toggle"
                    onClick={handleViewToggle}
                    onKeyDown={(e) => e.key === 'Enter' && handleViewToggle()}
                    aria-label={`Switch to ${currentView === 'fan' ? 'Commentator Dashboard' : 'Fan Lens'}`}
                    tabIndex={0}
                >
                    <span className={`view-icon ${currentView === 'fan' ? 'active' : ''}`}>👁️</span>
                    <span className="view-separator">|</span>
                    <span className={`view-icon ${currentView === 'commentator' ? 'active' : ''}`}>🎙️</span>
                </button>
                {showTooltip === 'view' && (
                    <div className="control-tooltip">Switch view: Fan Lens to Commentator Dashboard</div>
                )}
            </div>
        </div>
    )
}
