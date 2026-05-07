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
                <TopNavBar />
                <div className="live-tab-bar">
                    <Tabs value={tab} onValueChange={handleTabChange}>
                        <TabsList className="live-tabs-list">
                            {TABS.map(({ value, label }) => (
                                <TabsTrigger key={value} value={value} className="live-tab-trigger">
                                    {label}
                                </TabsTrigger>
                            ))}
                        </TabsList>

                        {TABS.map(({ value, Component }) => (
                            <TabsContent key={value} value={value} className="live-tab-content" forceMount>
                                {/* Only render the active tab to avoid unnecessary work */}
                                {tab === value && <Component />}
                            </TabsContent>
                        ))}
                    </Tabs>
                </div>
            </div>
        </LiveSessionProvider>
    )
}