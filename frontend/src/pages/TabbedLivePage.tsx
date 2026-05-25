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
    const home = searchParams.get('home') || 'Home Team'
    const away = searchParams.get('away') || 'Away Team'
    const sport = searchParams.get('sport') || 'soccer'
    const competition = searchParams.get('competition') || ''
    const activeTab = TABS.find((item) => item.value === tab) || TABS[0]
    const ActiveComponent = activeTab.Component

    const handleTabChange = (newTab: string) => {
        const next = new URLSearchParams(searchParams)
        next.set('tab', newTab)
        next.set('home', home)
        next.set('away', away)
        next.set('sport', sport)
        if (competition) next.set('competition', competition)
        setSearchParams(next, { replace: true })
    }

    return (
        <LiveSessionProvider homeTeam={home} awayTeam={away} sport={sport} competition={competition} autoConnectLive={activeTab.value !== 'notes'}>
            <div className="tabbed-live-page">
                {/* TopNavBar uses useLocation() internally for active-tab highlighting */}
                <TopNavBar
                    onSettingsClick={() => console.log('settings')}
                    onAccountClick={() => console.log('account')}
                />
                <div className="live-tab-content">
                    <div role="tabpanel" aria-selected="true">
                        <ActiveComponent onTabChange={handleTabChange} />
                    </div>
                </div>
            </div>
        </LiveSessionProvider>
    )
}
