import { useSearchParams } from 'react-router-dom'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs'
import { LiveSessionProvider } from '@/contexts/LiveSessionContext'
import TopNavBar from '@/components/TopNavBar'
import FanLensBroadcast from '@/pages/FanLensBroadcast'
import CommentatorDashboard from '@/pages/CommentatorDashboard'
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
                <TopNavBar onSettingsClick={() => console.log('settings')} onAccountClick={() => console.log('account')} />
                <div className="live-tab-content">
                    {TABS.map(({ value, Component }) => (
                        <div key={value} style={{ display: tab === value ? 'block' : 'none' }}>
                            <Component />
                        </div>
                    ))}
                </div>
            </div>
        </LiveSessionProvider>
    )
}