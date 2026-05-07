import { useSearchParams } from 'react-router-dom'
// @ts-expect-error — JSX contexts/pages have no .d.ts; runtime types are correct
import { LiveSessionProvider } from '@/contexts/LiveSessionContext'
import TopNavBar from '@/components/TopNavBar'
// @ts-expect-error
import FanLensBroadcast from '@/pages/FanLensBroadcast'
// @ts-expect-error
import CommentatorDashboard from '@/pages/CommentatorDashboard'
// @ts-expect-error
import NotesGenerationHub from '@/pages/NotesGenerationHub'

const TABS = [
    { value: 'fan-lens', label: 'Fan Lens', Component: FanLensBroadcast },
    { value: 'commentator', label: 'Commentator', Component: CommentatorDashboard },
    { value: 'notes', label: 'Notes Hub', Component: NotesGenerationHub },
]

export default function TabbedLivePage() {
    const [searchParams, setSearchParams] = useSearchParams()

    const tab = searchParams.get('tab') || 'fan-lens'
    const home = searchParams.get('home') || 'Barcelona'
    const away = searchParams.get('away') || 'Real Madrid'
    const sport = searchParams.get('sport') || 'soccer'

    const handleTabChange = (newTab: string) => {
        setSearchParams({ tab: newTab, home, away, sport }, { replace: true })
    }

    return (
        <LiveSessionProvider homeTeam={home} awayTeam={away} sport={sport}>
            <div className="tabbed-live-page">
                {/* TopNavBar uses useLocation() internally for active-tab highlighting */}
                <TopNavBar
                    onSettingsClick={() => console.log('settings')}
                    onAccountClick={() => console.log('account')}
                />
                <div className="live-tab-content">
                    {TABS.map(({ value, Component }) => (
                        <div
                            key={value}
                            role="tabpanel"
                            aria-selected={tab === value}
                            style={{ display: tab === value ? 'block' : 'none' }}
                        >
                            <Component onTabChange={handleTabChange} />
                        </div>
                    ))}
                </div>
            </div>
        </LiveSessionProvider>
    )
}