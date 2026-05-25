import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { LiveSessionProvider, useLiveSession, buildMatchSessionKey } from '../LiveSessionContext'

jest.mock('@/lib/backend-url', () => ({
    backendUrl: (path) => path,
    backendWsUrl: (path) => `ws://localhost${path}`,
}))

class MockEventSource {
    static instances = []

    constructor(url) {
        this.url = url
        this.close = jest.fn()
        this.onmessage = null
        this.onerror = null
        MockEventSource.instances.push(this)
    }
}

function NotesHarness() {
    const { prepareNotes, commentaryData, buildStatus } = useLiveSession()
    return (
        <div>
            <button onClick={() => prepareNotes('Arsenal', 'Paris Saint-Germain')}>prepare</button>
            <span data-testid="status">{buildStatus || 'idle'}</span>
            <span data-testid="markdown">{commentaryData?.markdown_notes || ''}</span>
        </div>
    )
}

describe('LiveSessionContext notes preparation', () => {
    beforeEach(() => {
        MockEventSource.instances = []
        global.EventSource = MockEventSource
        global.fetch = jest.fn()
        jest.spyOn(console, 'error').mockImplementation(() => {})
        jest.useFakeTimers()
    })

    afterEach(() => {
        jest.useRealTimers()
        jest.restoreAllMocks()
    })

    it('includes competition in the session key', () => {
        expect(buildMatchSessionKey(
            'Arsenal',
            'Paris Saint-Germain',
            'soccer',
            'Champions League Final',
        )).toBe('soccer#arsenal#vs#paris-saint-germain#champions-league-final')
    })

    it('posts competition and recovers completed notes after a transient SSE drop', async () => {
        global.fetch.mockImplementation((url, options = {}) => {
            if (String(url).startsWith('/api/notes/')) {
                return Promise.resolve({ status: 404, ok: false })
            }
            if (options.method === 'POST') {
                return Promise.resolve({
                ok: true,
                json: async () => ({
                    job_id: 'job-1',
                    created: true,
                    events_url: '/api/v1/commentary/notes-jobs/job-1/events',
                    status_url: '/api/v1/commentary/notes-jobs/job-1',
                }),
                })
            }
            return Promise.resolve({
                ok: true,
                json: async () => ({
                    status: 'succeeded',
                    result: {
                        status: 'success',
                        markdown_notes: '## Match Frame\nChampions League Final',
                        beats: [{ text: 'Opening cue' }],
                        beat_count: 1,
                    },
                }),
            })
        })

        render(
            <LiveSessionProvider
                homeTeam="Arsenal"
                awayTeam="Paris Saint-Germain"
                sport="soccer"
                competition="Champions League Final"
                autoConnectLive={false}
            >
                <NotesHarness />
            </LiveSessionProvider>
        )

        fireEvent.click(screen.getByText('prepare'))

        await waitFor(() => expect(MockEventSource.instances).toHaveLength(1))
        const postCall = global.fetch.mock.calls.find((call) => call[1]?.method === 'POST')
        const requestBody = JSON.parse(postCall[1].body)
        expect(requestBody.competition).toBe('Champions League Final')

        await act(async () => {
            MockEventSource.instances[0].onerror()
            await Promise.resolve()
            jest.advanceTimersByTime(1500)
            await Promise.resolve()
        })

        await waitFor(() => {
            expect(screen.getByTestId('status')).toHaveTextContent('ready')
            expect(screen.getByTestId('markdown')).toHaveTextContent('Champions League Final')
        })
    })
})
