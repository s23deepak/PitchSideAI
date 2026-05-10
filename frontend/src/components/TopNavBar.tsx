import { useNavigate, useLocation } from 'react-router-dom'

interface TopNavBarProps {
    onSettingsClick?: () => void
    onAccountClick?: () => void
}

export default function TopNavBar({ onSettingsClick, onAccountClick }: TopNavBarProps) {
    const navigate = useNavigate()
    const location = useLocation()

    const isActive = (tab: string) => {
        if (location.pathname === `/${tab}`) return true
        return location.pathname === '/live' && new URLSearchParams(location.search).get('tab') === tab
    }

    const navigateToTab = (tab: string) => {
        const params = new URLSearchParams(location.search)
        params.set('tab', tab)
        navigate(`/live?${params.toString()}`)
    }

    return (
        <nav className="top-nav-bar">
            <div className="top-nav-logo" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>
                PITCHSIDEAI
            </div>

            <div className="top-nav-links">
                <button
                    className={`top-nav-link ${isActive('fan-lens') ? 'active' : ''}`}
                    onClick={() => navigateToTab('fan-lens')}
                >
                    Fan Lens
                </button>
                <button
                    className={`top-nav-link ${isActive('commentator') ? 'active' : ''}`}
                    onClick={() => navigateToTab('commentator')}
                >
                    Broadcast Studio
                </button>
                <button
                    className={`top-nav-link ${isActive('notes') ? 'active' : ''}`}
                    onClick={() => navigateToTab('notes')}
                >
                    Notes Hub
                </button>
            </div>

            <div className="top-nav-actions">
                <button
                    className="top-nav-icon-btn"
                    onClick={onSettingsClick}
                    aria-label="Settings"
                >
                    <span className="material-icons">settings</span>
                </button>
                <button
                    className="top-nav-icon-btn"
                    onClick={onAccountClick}
                    aria-label="Account"
                >
                    <span className="material-icons">account_circle</span>
                </button>
            </div>
        </nav>
    )
}
