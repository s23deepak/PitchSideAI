/* ── Demo Seed Data — Self-Guided Mode (Story 4.2) ──────────────────────────── */

/**
 * Pre-seeded demo fixture for self-guided demo mode.
 * Provides sample match video, commentary notes, trivia cards, and suggested questions.
 */

export const DEMO_FIXTURE = {
    homeTeam: 'Roma',
    awayTeam: 'Napoli',
    competition: 'Serie A 2023/24',
    videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4', // Placeholder - replace with actual football footage
    commentaryNotes: `# Roma vs Napoli - Live Commentary Notes

## Pre-Match Context
- **Roma**: Fighting for European spots under Mourinho
- **Napoli**: League leaders with Osimhen in top form
- **Venue**: Stadio Olimpico, Rome

## Key Players to Watch
### Roma
- **Paulo Dybala** (#21): Creative hub, 8 goals this season
- **Lorenzo Pellegrini** (#10): Captain, set-piece specialist
- **Tammy Abraham** (#9): Target forward, aerial threat

### Napoli
- **Victor Osimhen** (#9): 15 goals in 20 Serie A appearances
- **Khvicha Kvaratskhelia** (#77): Georgian wizard, 10 assists
- **Piotr Zielinski** (#20): Midfield metronome

## Tactical Setup
- **Roma**: 4-2-3-1 with inverted wingers cutting inside
- **Napoli**: 4-3-3 with high press and wide overloads

## Match Facts
- **Referee**: Daniele Orsato
- **Weather**: Clear, 18°C
- **Attendance**: 65,000 (sold out)
`,
    triviaCards: [
        {
            text: 'Victor Osimhen has scored 15 goals in 20 Serie A appearances this season, making him the league\'s top scorer.',
            source: 'StatsBomb · 2023/24 season',
            eventTag: 'goal',
            timestampMs: 34000,
        },
        {
            text: 'Paulo Dybala has directly contributed to 12 goals (8G, 4A) in Serie A this season.',
            source: 'Opta · Serie A 2023/24',
            eventTag: 'goal',
            timestampMs: 78000,
        },
        {
            text: 'Napoli have kept 14 clean sheets this season - the most in Serie A.',
            source: 'StatsBomb · Defensive stats',
            eventTag: 'yellow_card',
            timestampMs: 125000,
        },
        {
            text: 'Lorenzo Pellegrini is Roma\'s captain and leads the team in chances created with 45 this season.',
            source: 'Opta · Chance creation',
            eventTag: 'substitution',
            timestampMs: 180000,
        },
        {
            text: 'Khvicha Kvaratskhelia has completed 89 dribbles this season - more than any other player in Serie A.',
            source: 'StatsBomb · Dribble stats',
            eventTag: 'goal',
            timestampMs: 240000,
        },
    ],
    suggestedQuestions: [
        {
            text: 'Why is that a red card?',
            answer: 'The defender denied a clear goal-scoring opportunity with a reckless challenge from behind. According to Law 12, this is a sending-off offense for denying an obvious goal-scoring opportunity (DOGSO).',
            timestampMs: 67000,
        },
        {
            text: 'Who is number 10?',
            answer: 'That\'s Lorenzo Pellegrini, Roma\'s captain and creative hub. He\'s been with Roma since 2017 and is known for his set-piece delivery and long-range shooting.',
            timestampMs: 12000,
        },
        {
            text: 'What formation are they playing?',
            answer: 'Roma are in a 4-2-3-1 with inverted wingers cutting inside from wide areas. Napoli counter with a 4-3-3 featuring a high press and overlapping fullbacks.',
            timestampMs: null,
        },
    ],
}

/**
 * Get trivia card that should be displayed at given video time
 * @param {number} videoTimeMs - Current video time in milliseconds
 * @returns {object|null} - Trivia card or null if none scheduled
 */
export function getTriviaCardAtTime(videoTimeMs) {
    const sortedCards = [...DEMO_FIXTURE.triviaCards].sort(
        (a, b) => a.timestampMs - b.timestampMs
    )

    for (const card of sortedCards) {
        if (videoTimeMs >= card.timestampMs && !card._shown) {
            card._shown = true
            return card
        }
    }
    return null
}

/**
 * Get all trivia cards
 * @returns {array} - All trivia cards
 */
export function getAllTriviaCards() {
    return DEMO_FIXTURE.triviaCards
}

/**
 * Get suggested questions
 * @returns {array} - Suggested questions with answers
 */
export function getSuggestedQuestions() {
    return DEMO_FIXTURE.suggestedQuestions
}

/**
 * Get demo fixture info
 * @returns {object} - Demo fixture data
 */
export function getDemoFixture() {
    return DEMO_FIXTURE
}
