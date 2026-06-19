# Autonomous Commentary Generation: From-Scratch Architecture

## The Commentator's Lens

A 90-minute broadcast doesn't need a spreadsheet. It needs **stories**.

| Data Dump (bad) | Broadcast Brief (good) |
|---|---|
| "Team A has 65% possession, 2.3 xG/90" | "Team A suffocates opponents — they've turned midfield into a no-fly zone, winning the ball back within 7 seconds." |
| "Player X: 12 goals, 5 assists" | "Player X is on a tear — 5 goals in his last 3, including that late winner at the Bernabéu that still haunts this fixture." |
| "H2H: 8-3-6" | "These two haven't produced a draw in 14 meetings. Someone always leaves with blood on their shirt." |

**The priority:** narrative hooks, emotional stakes, tactical identity, and *what's different tonight*.

---

## External Resources: The Complete Arsenal

### Structured Sports Data APIs

| Source | Provides | Auth | RPM / Limits | Cost |
|---|---|---|---|---|
| **FootballData.org** | Fixtures, standings, H2H, teams, scorers | API key | 10 req/min free | Free tier |
| **ESPN (scraped)** | Squad rosters, form string (W/D/L), injuries, news, match context | None | ~120/min | Free |
| **Transfermarkt (scraped)** | Market values, player stats, transfers, contract expiry | None | ~20/min | Free |
| **Sofascore (scraped)** | Live stats, heatmaps, player ratings, lineups | None | ~30/min | Free |
| **FBref / Sports Reference** | Per-player season stats, xG, progressive carries, scouting reports | None | ~15/min | Free |
| **WhoScored** | Detailed match stats, player ratings, strengths/weaknesses | None (scraped) | ~10/min | Free |
| **11v11.com** | Comprehensive H2H records, lineups, historical match data | None | Unlimited | Free |
| **WorldFootball.net** | International + club fixtures, results, squads | None (scraped) | ~15/min | Free |
| **RSSSF (Rec.Sport.Soccer Statistics Foundation)** | Historical records, tournament archives | None | Unlimited | Free |
| **Flashscore** | Live scores, fixtures, standings, H2H | None (scraped) | ~20/min | Free |
| **Soccerway** | Fixtures, results, tables, squad lists | None (scraped) | ~15/min | Free |
| **FotMob** | Deep match stats, player ratings, heatmaps, news | None (scraped) | ~15/min | Free |
| **Understat** | xG, xA, shot maps, passing networks | None (scraped) | ~10/min | Free |
| **Capology** | Player salaries, contract details, wage bills | None (scraped) | ~5/min | Free |
| **Soccerbase** | Player appearance history, career stats | None (scraped) | ~10/min | Free |
| **Premier League Official** | Fixtures, stats, tables (limited free tier) | None | ~5/min | Free |

### Paid Sports Data (Higher Fidelity)

| Source | Provides | Cost |
|---|---|---|
| **SportMonks** | Fixtures, lineups, squads, stats, officials, venues, live scores | €49/mo |
| **OneVersusOne** | Player 1v1 index, progressive carries, pre-assists, xG, shot maps | ~$15/mo |
| **Opta / The Analyst** | Enterprise-grade event data, pass networks, pressure events, possession chains | POA (enterprise) |
| **StatsBomb** | Event data, 360 data, player positions, pass maps | Free for historical; paid for live |
| **FootballAPI** | Comprehensive football data: fixtures, players, stats, odds | ~$30/mo |
| **SportRadar** | Official league data for 30+ competitions | POA (enterprise) |
| **WyScout** | Video + data scouting platform | POA (enterprise) |

### News & Editorial Sources (Scraped)

| Source | Provides | Access |
|---|---|---|
| **Goal.com** | Match previews, player profiles, transfer news, tactical analysis | Web scraped; rich editorial |
| **Rotowire (soccer)** | Fantasy-focused: predicted lineups, injury updates, form analysis, start/sit | Web scraped; excellent for lineup intel |
| **Sky Sports** | Pre-match press conferences, team news, pundit analysis | Web scraped |
| **BBC Sport** | Match previews, gossip columns, official team news | Web scraped |
| **ESPN FC** | Transfer news, injury reports, tactical breakdowns | Web scraped + API |
| **The Athletic** | Deep tactical analysis, long-form profiles | Web scraped (paywalled) |
| **The Guardian Football** | Match previews, player features, weekly columns | Web scraped |
| **MARCA / AS (Spain)** | La Liga-specific: lineups, injuries, press conferences | Web scraped |
| **Gazzetta dello Sport (Italy)** | Serie A-specific: formations, tactical previews | Web scraped |
| **Kicker (Germany)** | Bundesliga-specific: squad news, ratings | Web scraped |
| **L'Équipe (France)** | Ligue 1-specific: team news, player profiles | Web scraped |
| **OneFootball** | Aggregated news, lineups, transfer rumours | Web scraped |
| **Football365** | Opinion, stats, features, "Mediawatch" | Web scraped |
| **Sports Mole** | Match previews, predicted XIs, form guides | Web scraped |

### Web Search & Content Extraction

| Source | Provides | Cost | Notes |
|---|---|---|---|
| **Tavily** | AI-search: results + answer summary, domain filtering | ~$25/mo (5000 searches) | Best for quick synthesis |
| **Exa** | Semantic search, date-filtered, domain-filtered, content embeddings | ~$75/mo (2500 searches) | Best for targeted evidence |
| **Brave Search API** | Web search with structured results | Free tier (2000/mo) | Budget alternative |
| **SerpAPI** | Google search results structured | ~$50/mo | Reliable but expensive |
| **Firecrawl** | URL → clean LLM-ready markdown, anti-bot bypass | Free tier (500 credits) | Ideal for article extraction |
| **BrightData MCP** | Residential proxies + structured scraping + pre-built scrapers | **5000 free credits** | Best for paywalled content; includes ready-made sports scrapers |
| **Jina AI Reader** | Any URL → clean markdown (free, no auth) | Free | Quick single-page extraction |
| **ScrapingBee** | Headless browser scraping, anti-bot | ~$49/mo | For JS-heavy sites |
| **Diffbot** | Automatic article extraction, entity recognition | ~$299/mo | Enterprise-grade |

### Structured Knowledge

| Source | Provides | Access |
|---|---|---|
| **Wikipedia** | Player bios, club history, stadium facts, competition details | Free (scrape or API) |
| **DBpedia** | SPARQL queries: "all players of club X", "stadium capacity", founded date, trophies | Free (SPARQL endpoint) |
| **Wikidata** | Entity-fact database: Q-items for every player, club, stadium, competition | Free (SPARQL) |
| **Gracenote Sports** | Player and team metadata | POA |
| **DataFactory Sports** | Comprehensive metadata for 40+ sports | POA |

### Weather & Conditions

| Source | Provides | Auth | Cost |
|---|---|---|---|
| **Open-Meteo** | Hourly forecast: temp, wind, humidity, precipitation, pressure, visibility | None | Free |
| **WeatherAPI.com** | Current + forecast, wind, UV, visibility | API key | Free tier (1M calls/mo) |
| **VisualCrossing** | Historical + forecast weather, 15-day outlook | API key | Free tier (1000/day) |
| **Tomorrow.io** | Hyperlocal weather, minute-by-minute | API key | Free tier (500/day) |

### LLM Backends (for Synthesis)

| Option | Model | Context | Cost |
|---|---|---|---|
| **OpenAI** | GPT-4o-mini (cheap), GPT-4o (quality) | 128K | ~$0.15/1M tokens (mini) |
| **Anthropic** | Claude 3.5 Sonnet (narrative), Haiku (fast) | 200K | ~$3/1M tokens |
| **vLLM (self-hosted)** | Qwen 2.5 72B, DeepSeek v3, Llama 3 70B | 128K+ | Zero marginal cost |
| **DeepSeek API** | DeepSeek v3, DeepSeek R1 | 128K | ~$0.27/1M tokens |
| **Together.ai** | Mixtral, Qwen, Llama (hosted) | 128K | ~$0.60/1M tokens |
| **Groq** | Llama 3 70B, Mixtral (fast inference) | 128K | ~$0.59/1M tokens |
| **Wafer (self-hosted)** | Nova Pro, Nova Lite, Nova Sonic (Wafer-hosted models) | Variable | Internal |

### Audio / Pronunciation (Bonus)

| Source | Provides |
|---|---|
| **Forvo** | Crowd-sourced pronunciation audio for player names |
| **YouGlish** | YouTube clips of names spoken in context |
| **NameShouts** | Phonetic + audio pronunciation API |

---

## Architecture: The Autonomous Pipeline

```
INPUT: Two team names (+ optional competition, optional date)
       ↓
PHASE 0: MATCH RESOLUTION (10-15 sec)
  ├─ Query: "{home} vs {away} {competition} fixture kickoff venue 2026"
  ├─ Sources: Exa/Tavily → ESPN → FootballData.org → Sofascore (round-robin)
  ├─ Extract: venue name, venue lat/lon, kickoff datetime, competition stage
  ├─ Fallback: If no competition given, search current week's fixtures
  └─ Output: MatchIdentity {venue, datetime, competition_stage, fixture_urls}
       ↓
PHASE 1: PARALLEL DATA GATHERING (30-45 sec, 16 fetchers concurrent)
  ┌─────────────────────────────────────────────────────────────┐
  │  Fetch 1:  SQUADS         (ESPN roster + FootballData)  │
  │  Fetch 2:  RECENT FORM    (ESPN last 5 results)        │
  │  Fetch 3:  H2H RECORD     (FootballData.org + 11v11)   │
  │  Fetch 4:  STANDINGS       (FootballData.org table)      │
  │  Fetch 5:  WEATHER         (Open-Meteo hourly forecast)  │
  │  Fetch 6:  OFFICIALS       (Web search + extract names) │
  │  Fetch 7:  TEAM NEWS       (Goal.com + Sky Sports RSS) │
  │  Fetch 8:  INJURIES        (ESPN + Rotowire scraped)    │
  │  Fetch 9:  LINEUP PREDS    (Rotowire + Sports Mole)     │
  │  Fetch 10: PLAYER BIOS      (Wikipedia per top 18)      │
  │  Fetch 11: PLAYER STATS     (FBref + Transfermarkt)     │
  │  Fetch 12: MATCH PREVIEWS   (Goal.com + BBC + Sky)      │
  │  Fetch 13: TRANSFER NEWS    (Transfermarkt + Goal.com)   │
  │  Fetch 14: MANAGER PROFILE  (Wikipedia + Tavily search)  │
  │  Fetch 15: CLUB HISTORY     (DBpedia + Wikipedia)       │
  │  Fetch 16: PRONUNCIATION    (Forvo + YouGlish API)      │
  └─────────────────────────────────────────────────────────────┘
       ↓
PHASE 2: EVIDENCE GAP-FILL & ENRICHMENT (15-20 sec)
  ├─ Check: accepted_evidence_count < threshold (4 items)?
  ├─ If thin → Exa targeted search on 4 topics:
  │   ├─ fixture:    "{home} vs {away} kickoff venue date referee"
  │   ├─ team_news: "{home} vs {away} injuries predicted lineups press conference"
  │   ├─ h2h:       "{home} vs {away} head to head record history"
  │   └─ tactical:  "{home} vs {away} tactical preview set pieces key battles"
  ├─ Per player (top 18): bio → stats → milestone check → transfer news
  │   ├─ Pull club + national team from Wikipedia infobox
  │   ├─ Stats from FBref/Transfermarkt (season: goals, assists, apps, xG, progressive carries)
  │   ├─ Milestone: "{player} 1 goal away from 100th career goal" type search
  │   └─ Transfer: "{player} transfer rumours latest contract 2026"
  ├─ Per official: name → profile → card tendency → VAR history → notable matches
  ├─ Per manager: name → career history → tactical philosophy → notable achievements
  ├─ Per venue: name → capacity → surface → roof → altitude → historical events
  ├─ Per club: name → founded → trophies → philosophy → academy reputation
  └─ All data normalized into unified "Match Brief" JSON
       ↓
PHASE 3: NARRATIVE SYNTHESIS (LLM, 15-30 sec)
  ├─ Input: Match Brief JSON (all Phase 1+2 outputs, ~40KB structured data)
  ├─ LLM: GPT-4o-mini or Claude 3.5 Sonnet or self-hosted Qwen 72B
  ├─ Prompt structure (see §Synthesis Prompt below)
  ├─ Generated sections:
  │   ├─ Broadcast Prep Header
  │   ├─ Evidence Status (accepted/rejected counts)
  │   ├─ Air-Ready Rundown (say-now facts, watch-say-prove cards)
  │   ├─ Match Frame (fixture, stage, datetime, venue, officials)
  │   ├─ Narrative Spine (opening frame, first read, evidence posture)
  │   ├─ Tactical Dossier (zone watch, key battles, set-piece watch)
  │   ├─ Form, History & Conditions (form cards, H2H story, weather)
  │   ├─ Team News Caveats (per-team injuries, lineup status)
  │   ├─ Officials Brief (referee profile, VAR team, card tendency)
  │   ├─ Venue & Surface Brief (stadium character, pitch, altitude)
  │   ├─ Manager Profiles (per-team: philosophy, career, achievements)
  │   ├─ Club Context (history, trophies, academy, tactical identity)
  │   ├─ Player Cards (1 card per key player: bio, stats, story, pronunciation)
  │   ├─ Broadcast Folder Pages (1-pager per team, quick-reference cards)
  │   ├─ Live Trigger Lines (event→cue mapping: goal/sub/card/corner/freekick)
  │   ├─ Halftime & Postgame Angles
  │   ├─ Deep Research Synthesis (optional enrichment layer)
  │   └─ Pronunciation (phonetic spellings from Forvo/YouGlish)
  └─ Guardrail injected system-wide: "DO NOT fabricate statistics. Only use provided facts."
       ↓
PHASE 4: QUALITY CHECK & REVISION (5-10 sec)
  ├─ Fact verification: every numeric claim must link to a source_url
  ├─ Placeholder detection: regex scan for "Player 1", "TBD", "Unknown", "unavailable"
  ├─ Evidence grading: Tier 1 (official API) → Tier 2 (scraped structured) → Tier 3 (web search LLM-extract)
  ├─ Missing section detection: format completeness check
  ├─ Revision loop: up to 2 passes if sections missing or unsupported claims found
  └─ Final artifact: Markdown broadcast brief + structured NotesStore JSON
       ↓
OUTPUT: Broadcast Brief Markdown + Structured NotesStore JSON
        (O(1) tag-based lookup for live WebSocket pipeline)
```

---

## Search Query Templates

### 1. Venue & Weather

```python
# Match resolution (Exa/Tavily priority, then ESPN)
query = f"{home} vs {away} {competition} fixture kickoff time venue date official"
# → Exa search with include_domains=["espn.com", "fifa.com", "bbc.co.uk", "skysports.com", "goal.com"]

# Venue details (separate search if venue name found)
query = f"{venue_name} stadium capacity surface type roof pitch dimensions history altitude notable events atmosphere"
# → Wikipedia + DBpedia SPARQL:
#   SELECT ?capacity ?surface ?opened ?owner WHERE { dbr:{venue_name} dbo:seatingCapacity ?capacity . }

# Weather (API, not search)
# GET https://api.open-meteo.com/v1/forecast?
#   latitude={lat}&longitude={lon}
#   &hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,
#            precipitation,visibility,pressure_msl
#   &forecast_hours=6  # 3h window around kickoff
#   &timezone=auto
```

### 2. Officials

```python
# Match officials appointment
query = f"{home} vs {away} {competition} referee VAR officials appointed 2026"
# → Exa: include_domains=["fifa.com", "espn.com", "bbc.co.uk", "skysports.com"]
# → SportMonks API (if paid): /fixtures/{id}/officials

# Per-official profile (once names extracted)
query = f"{referee_name} football referee career profile cards tendency style notable matches history"
# → Wikipedia infobox: date of birth, nationality, FIFA badge year, notable matches
# → DBpedia SPARQL: SELECT ?birthDate ?nationality WHERE { dbr:{referee_name} ... }

query = f"{var_name} VAR official history assignments notable decisions"
query = f"{assistant_name} assistant referee profile career"

# Extract patterns from fixture resolver:
# "Referee: {name}" | "VAR: {name}" | "Assistant referees: {name}, {name}" | "Fourth official: {name}"
```

### 3. Team Details (per team, both sides)

```python
# Coach / Manager
query = f"{team} current manager head coach 2026 tactical philosophy career history"
# → Wikipedia API: GET /page/summary/{team_name}
# → Tavily: search_team_manager(team, sport="soccer")  # already exists
# → DBpedia: SELECT ?manager WHERE { dbr:{team} dbo:manager ?manager }
# → Transfermarkt: club page → staff section

# Squad (structured API)
# ESPN: /team/_/name/{team}/roster
# FootballData.org: GET /teams/{id}
# Sofascore: team page → squad tab (scraped)
# Transfermarkt: club page → squad (scraped)
# Goal.com: team page → squad list

# Team playstyle / formation
query = f"{team} formation tactics playing style 2025-26 season possession press transition build-up"
# → WhoScored: team page → style of play, strengths, weaknesses
# → The Athletic: tactical analysis articles
# → Understat: team xG, shot maps, pass networks (scraped)

# Per-player bio (for each of ~25 players)
query = f"{player_name} football player biography career history clubs nationality position age"
# → Wikipedia (structured infobox): position, current club, national team, DOB, height
# → DBpedia SPARQL: all structured facts for player entity
# → Soccerbase: career appearance history, clubs, seasons
# → Transfermarkt: player page → career stats, market value

# Per-player current stats
# FBref: player page → standard stats table (goals, assists, apps, xG, progressive carries)
# Transfermarkt: player page → appearances, goals, assists, market value
# OneVersusOne: API → 1v1 index, progressive carries, pre-assists, xG, shot maps
# WhoScored: player page → ratings, strengths, weaknesses
# Understat: player page → xG, xA, shot maps
# FotMob: player page → stats, heatmap, rating history

# Per-player milestone check
query = f"{player_name} upcoming milestone approaching record achievement {player_stat_context}"
# → e.g., "1 goal away from 100th career goal" | "3 apps from 200th club appearance"
# → Wikipedia: career statistics table

# Per-player transfer / contract news
query = f"{player_name} transfer news rumours contract expiry latest 2026"
# → Goal.com: transfer news section
# → Transfermarkt: player page → transfer history + rumours
# → Sky Sports: transfer centre
# → BBC Sport: gossip column
# → The Athletic: transfer tracker
# → Rotowire: player news

# Per-player injury / suspension status
query = f"{player_name} injury suspension status latest update {home} vs {away} availability"
# → ESPN: injury report
# → Rotowire: injury updates + start/sit
# → Goal.com: team news section
# → Sky Sports: team news

# Per-player national team context
query = f"{player_name} national team {country} call-up recent form caps international"
# → Wikipedia: national team section
# → FIFA.com: national team stats

# Supporting staff (if available)
query = f"{team} assistant coaches first-team staff coaching setup 2026"
# → Transfermarkt: club page → staff section
# → Club official website: coaching staff page

# Team milestones
query = f"{team} football club upcoming milestone approaching record achievement history"
# → Wikipedia: club page → honours section
# → DBpedia: trophy list
```

### 4. H2H & Form Comparison

```python
# Head-to-head (structured API + search)
# FootballData.org: GET /matches?team1={id}&team2={id}
# 11v11.com: team head-to-head page
query = f"{home} vs {away} head to head record history previous meetings results"

# Recent form (both teams)
# ESPN: team page → schedule/results (last 5)
# FootballData.org: GET /teams/{id}/matches?limit=5&status=FINISHED
# Sofascore: team page → recent results
query = f"{team} last 5 matches results form 2026"

# Form comparison / strengths vs weaknesses
query = f"{home} vs {away} form comparison recent results strengths weaknesses tactical matchup"
# → WhoScored: team comparison
# → Sports Mole: match preview with form guide
# → Goal.com: match preview
```

### 5. Matchups (1v1 & Group vs Group)

```python
# General key battles
query = f"{home} vs {away} key player battles tactical preview positional matchups 2026"
# → Goal.com: match preview
# → Sky Sports: tactical preview
# → BBC Sport: match preview

# Attack vs Defense comparison
query = f"{home} attack vs {away} defense comparison stats goals scored conceded xG strengths"
# → WhoScored: team comparison
# → OneVersusOne: team comparison endpoint

# Center backs vs striker (specific matchup)
query = f"{home_cb_name} vs {away_st_name} duel matchup comparison defensive record"
# → OneVersusOne: player comparison

# Historical 1v1 (if players have faced each other before)
query = f"{player1} vs {player2} head to head previous meetings duel history"

# Formation-based matchups
query = f"{home} 4-3-3 vs {away} 3-5-2 tactical matchup formation battle"

# Set piece analysis
query = f"{home} {away} set piece stats corners free kicks conversion rate penalty takers 2025-26"
# → WhoScored: set piece stats
# → Understat: set piece xG
# → Opta: set piece data

# Substitution strategy / bench strength
query = f"{home} {away} bench strength substitutes impact depth comparison"
```

### 6. Miscellaneous

```python
# Storylines / narrative hooks
query = f"{home} vs {away} match preview storylines narratives talking points rivalry history stakes"
# → BBC Sport: match preview
# → The Athletic: pre-match feature
# → Goal.com: match preview

# Press conference quotes (pre-match, manager)
query = f"{home} manager pre-match press conference quotes {away} opponent 2026"
query = f"{away} manager pre-match press conference quotes {home} opponent 2026"
# → Sky Sports: press conference coverage
# → Club YouTube channels: press conference videos

# Fan atmosphere / crowd expectations
query = f"{home} vs {away} fan atmosphere crowd expectations ticket sales stadium atmosphere"
# → Local news: matchday coverage
# → Twitter/X: fan sentiment (optional)

# Competition-specific rules
query = f"{competition} format rules regulations away goals extra time substitutions VAR protocol 2026"
# → Wikipedia: competition page
# → FIFA/UEFA: competition regulations PDF

# Transfers & squad changes
query = f"{team} summer transfer window signings departures squad changes 2026"
# → Transfermarkt: club transfer history
# → Goal.com: transfer news
# → Sky Sports: transfer centre

# Pronunciation
query = f"{player_name} name pronunciation phonetic spelling how to pronounce"
# → Forvo: pronunciation audio (API)
# → YouGlish: YouTube clips of spoken name
# → NameShouts: phonetic + audio

# Historical venue context
query = f"{venue_name} stadium history notable matches events hosted {competition} connection"
# → Wikipedia: stadium page
# → StadiumGuide.com: venue history

# Social media buzz / viral moments
query = f"{home} {away} social media buzz pre-match viral moments fans predictions 2026"
# → Goal.com: social media roundup
# → OneFootball: fan content
```

---

## Synthesis Prompt Structure

```
SYSTEM: You are a professional football broadcast commentator producing a pre-match brief.
Your tone is: authoritative, emotionally intelligent, tactically precise, narrative-driven.
You NEVER fabricate statistics, records, or facts.
Every claim must be traceable to a source_url in the provided evidence.
When data is unavailable, say so explicitly rather than guessing.

GUARDRAIL (injected as first user message):
DO NOT output template placeholders like "Player 1", "TBD", "Unknown", or "[insert]" .
DO NOT invent formations, tactics, injuries, weather, or match facts.
DO NOT say "current form status: unavailable" as a repeated filler phrase.
If evidence is thin, state that clearly and focus on what IS confirmed.
Only use facts explicitly present in the Match Brief JSON below.

MATCH BRIEF JSON (provided):
{
  "match_facts": {
    "home_team": "Manchester United",
    "away_team": "Arsenal",
    "competition": "Premier League",
    "stage": "Matchday 24",
    "match_datetime": "2026-02-15T16:30:00Z",
    "venue": "Old Trafford",
    "venue_capacity": 74310,
    "venue_surface": "Grass (Desso GrassMaster)",
    "venue_altitude_m": 45,
    "venue_opened": 1910,
    "officials": {
      "referee": "Michael Oliver",
      "var": "Jarred Gillett",
      "assistant_referees": ["Stuart Burt", "Simon Bennett"],
      "fourth_official": "Andy Madley"
    }
  },
  "home_team": {
    "team_name": "Manchester United",
    "manager": {
      "name": "Rúben Amorim",
      "nationality": "Portuguese",
      "career_summary": "...",
      "tactical_philosophy": "High-press 3-4-3, aggressive ball recovery, vertical transitions",
      "notable_achievements": ["Primeira Liga ×2", "Taça da Liga ×3"]
    },
    "club_history": {
      "founded": 1878,
      "major_trophies": 68,
      "league_titles": 20,
      "ucl_titles": 3,
      "philosophy": "Youth development, attacking tradition, never-say-die culture"
    },
    "recent_form": {
      "last_5": ["W 2-1 vs Chelsea", "D 1-1 vs Liverpool", "L 0-2 vs City", "W 3-0 vs Spurs", "W 1-0 vs Newcastle"],
      "form_string": "W D L W W",
      "goals_for": 8,
      "goals_against": 3,
      "possession_avg": 52.3,
      "home_form": "W W D W L",
      "away_form": "W D L D W"
    },
    "injuries": [
      {"player": "Luke Shaw", "status": "out", "injury": "hamstring", "return": "late Feb"},
      {"player": "Mason Mount", "status": "doubtful", "injury": "calf"}
    ],
    "lineup_status": "predicted (not yet confirmed — official team sheet due 60 min before kickoff)",
    "players": [
      {
        "name": "Bruno Fernandes",
        "position": "AM",
        "nationality": "Portugal",
        "current_club": "Manchester United",
        "age": 31,
        "stats": {"apps": 24, "goals": 10, "assists": 8, "xG": 7.2, "progressive_passes": 184},
        "bio_summary": "Captain, talismanic playmaker, leads PL in chances created (78)...",
        "milestone": "3 goals from 100th United goal in all competitions",
        "transfer_status": "Contracted to 2027, €75M market value",
        "pronunciation": "BROO-noh fer-NAN-desz",
        "national_team": {"caps": 72, "goals": 16},
        "source_urls": ["https://fbref.com/...", "https://en.wikipedia.org/...", "https://transfermarkt.com/..."]
      },
      // ... 17 more players
    ]
  },
  "away_team": { /* symmetric structure */ },
  "h2h_history": {
    "total_matches": 238,
    "home_wins": 98,
    "away_wins": 83,
    "draws": 57,
    "recent_meetings": ["2025-12-03: Arsenal 2-0 United", "2025-05-11: United 1-1 Arsenal"],
    "patterns": ["No draw in last 6 meetings", "Arsenal unbeaten at OT in 4 of last 5"],
    "source": "11v11.com"
  },
  "weather": {
    "temp_c": 7,
    "feels_like_c": 4,
    "conditions": "Partly cloudy",
    "wind_kmh": 18,
    "wind_direction": "NW",
    "humidity_pct": 72,
    "precipitation_chance": 15,
    "visibility_km": 12,
    "impact_narrative": "Cool, dry — no weather disruption expected. Light NW wind favours the Stretford End in second half."
  },
  "matchups": {
    "critical_matchups": [
      {"player1": "Bruno Fernandes", "player2": "Declan Rice", "analysis": "Playmaker vs destroyer — Fernandes will target spaces Rice vacates when pressing..."},
      // ...
    ]
  },
  "team_news": {
    "home_team": {
      "synthesis": "Amorim confirmed Shaw out, Mount doubtful. 'We know Arsenal's patterns...' — press conference.",
      "last_minute_changes": ["Late fitness test for Mount"],
      "lineup_status": "predicted"
    },
    "away_team": { /* symmetric */ }
  },
  "storylines": [
    {"title": "Arsenal's Old Trafford Hex", "description": "Arsenal haven't lost at OT in 4 of last 5 visits..."},
    {"title": "Fernandes Milestone Watch", "description": "3 goals from 100th United goal, could reach it against former rival..."}
  ],
  "pronunciation": {
    "home_key_players": [
      {"name": "Bruno Fernandes", "phonetic": "BROO-noh fer-NAN-desz"},
      {"name": "Rasmus Højlund", "phonetic": "RAS-moos HOY-loond"}
    ],
    "away_key_players": [
      {"name": "Bukayo Saka", "phonetic": "boo-KYE-oh SAH-kah"},
      {"name": "Declan Rice", "phonetic": "DECK-lan RICE"}
    ]
  }
}

OUTPUT SECTIONS (generate in order):

## Broadcast Prep Header
- Teams, competition, stage, date/time, venue
- Quick-ref: "Man United vs Arsenal, PL Matchday 24, Sunday Feb 15 2026 16:30, Old Trafford"

## Evidence Status
- Accepted evidence count, rejected count, evidence tiers
- "12 source-backed facts accepted, 2 web-search items flagged as Tier 3"

## Air-Ready Rundown
- 5-8 immediately usable facts: "Here's what you can say right now..."
- Watch-Say-Prove cards: facts that need live confirmation
- "Wait for team sheets before..." warnings

## Match Frame
- Fixture, stage, date/time, venue, officials, broadcast context

## Narrative Spine
- Opening frame: "This is framed as {competition}; use trophy-stage language..."
- First read: what to look for in first 10 min
- Evidence posture: what's confirmed vs what needs live verification

## Tactical Dossier
- Zone watch: where the game will be won/lost
- Key player battles: top 3 matchups with stats
- Set-piece watch: first corner, free-kick, throw-in cues

## Form, History & Conditions
- Form cards: both teams' last 5 with home/away split
- H2H story: narrative from record + recent meetings
- Weather/surface: temperature, wind, pitch condition

## Team News Caveats (per team)
- Injuries, suspensions, lineup status, last-minute changes
- Press conference quotes

## Officials Brief
- Referee: name, nationality, style (lenient/strict), card tendency, notable matches
- VAR: name, history
- Assistants: names
- Fourth official: name

## Venue & Surface Brief
- Stadium: capacity, opened date, surface type, roof, altitude
- Pitch notes: dimensions, recent condition, drainage
- Atmosphere: typical attendance, notable historical matches hosted
- Any connection to this fixture or competition

## Manager Profiles
- Per manager: name, nationality, career, tactical philosophy, achievements
- Head-to-head: have these managers faced each other before?

## Club Context
- Per team: founded, trophies, league titles, UCL titles, philosophy
- Academy reputation, youth pipeline
- Historical significance of this fixture for the club

## Player Cards (1 per key player, top 10 each side)
- Name, position, age, nationality, current club
- Season stats: apps, goals, assists, xG, progressive carries
- Bio: career summary, achievements, playing style
- Story: what makes them interesting tonight (milestone, transfer, form)
- Pronunciation: phonetic spelling
- National team: caps, goals, recent call-ups

## Broadcast Folder Pages (1-pager per team)
- Quick-reference team sheets, formation, key stats

## Live Trigger Lines
- On goal: "Reset broadcast around scorer role, tactical cause, and what {losing_team} must now adjust"
- On substitution: "Connect the change to role, shape, energy, and the matchup it alters"
- On yellow card: "Explain how booking changes duel risk, pressing aggression, defensive cover"
- On red card: "Immediately reframe territory, rest defense, and the side that must manage space"
- On corner: "Call delivery side, marking scheme, blockers, second-ball shape, counter-attack risk"
- On free kick (dangerous): "Identify taker, wall setup, delivery angle, runners, rebound coverage"
- On VAR check: "Explain what's being reviewed, likely outcome, and how delay affects momentum"
- On injury: "Impact on shape, potential sub, and who inherits the vacated role"
- On disallowed goal: "Immediately explain what the referee/VAR saw"

## Halftime & Postgame Angles
- Halftime narrative: "Compare intended tactical routes with territory, chance quality, set-piece patterns"
- Postgame questions: "Anchor first question in the clearest verified swing, not unverified assumptions"
- If home leads: "Did control come from sustained pressure or isolated transition moments?"
- If away leads: "Did their outlet and counter-press give them repeatable relief?"

## Pronunciation
- Key player names with phonetic spellings (from Forvo/YouGlish verified sources)
- Confirm names from official broadcast/team media before adding
- Do NOT guess pronunciation without an accepted source

## Source Provenance
- Every section's facts linked back to source_urls
- Evidence tier for each claim
- "Unavailable" markers where data was missing
```

---

## Design Principles

1. **Search first, synthesize second.** Never ask an LLM to invent facts. Every prompt is backed by real search results with source URLs.

2. **Parallelism everywhere.** Phase 1 runs 16 fetchers concurrently via `asyncio.gather()`. Player bios batch in groups of 5 parallel LLM calls. The only serial dependency: Phase 0 (match resolution) must complete before data gathering.

3. **Graceful degradation with source round-robin.** If ESPN returns empty → try FootballData.org → try Transfermarkt → try Sofascore → fall back to Exa/Tavily web search. The output always notes what's "unavailable from accepted evidence."

4. **Evidence tiering.** Every fact is graded:
   - **Tier 1** (green): Official APIs (FootballData.org, SportMonks) — verified, use freely
   - **Tier 2** (yellow): Scraped structured data (ESPN, Transfermarkt, WhoScored) — check against other sources
   - **Tier 3** (red): Web search / LLM-extracted — flag as "unconfirmed", treat as narrative color only

5. **Wait-for-confirmation pattern.** Lineups, formations, and injury statuses are marked as "predicted/unconfirmed" until official team sheets arrive. The system distinguishes between what's sourced and what's confirmed.

6. **The guardrail (injected into every LLM prompt).**
   ```
   DO NOT fabricate statistics, records, scores, dates, lineups, injuries,
   suspensions, biographies, or weather details.
   Only use facts explicitly provided in the prompt context.
   If data is unavailable, state that it is unavailable rather than guessing.
   ```

7. **Source provenance.** Every generated fact carries a `source_url`. The final document includes a `## Source Provenance` section. No stat floats without an origin URL.

8. **Caching with TTLs.** Match Brief JSON: 4 hours. Player bios: 1 hour. Weather: 30 minutes. News: 30 minutes. H2H records: 4 hours. Never re-fetch the same match within a session.

9. **No blocking I/O.** All data fetches are `async`. All LLM calls are `async`. BrightData MCP calls are `async`. The pipeline uses `asyncio.gather` for all parallel phases.

10. **Output is dual-format.** Markdown for human eyes (commentator's tablet). Structured JSON (NotesStore) with O(1) tag-based lookup for machine consumption (WebSocket pipeline retrieves facts by event type: "goal" → lookup "scorer narrative" + "tactical cause" beats).

11. **Deterministic fallback.** When an API returns empty or a search fails, produce a minimal, honest output rather than fabricating. "Unavailable from accepted evidence" is better than a hallucinated stat.

12. **BrightData MCP integration.** Use the 5000 free credits for:
    - Paywalled content extraction (The Athletic, premium news sites)
    - Anti-bot scraping (Transfermarkt, WhoScored, Sofascore)
    - Residential proxy rotation for geo-restricted content
    - Pre-built sports scrapers for structured extraction
    - Bulk article extraction from multiple sources simultaneously

13. **Rotowire + Goal.com integration.** Both provide editorial, human-written content — ideal for:
    - Lineup predictions with reasoning (Rotowire)
    - Injury analysis with return timelines (Rotowire)
    - Tactical previews and match analysis (Goal.com)
    - Player form narratives and start/sit recommendations (Rotowire)
    - These sources are scraped via BrightData MCP or Firecrawl

14. **No batching bottlenecks.** Player bios use parallel LLM calls (5 at a time max to respect API rate limits). The entire pipeline completes in under 60 seconds for a typical match.

15. **Exa as evidence gap-filler.** When structured APIs return thin data, Exa's semantic search targets specific domains (fifa.com, espn.com, bbc.co.uk, skysports.com, goal.com, theathletic.com) to fill the gaps with web evidence.

16. **Pronunciation from verified sources only.** Forvo API or YouGlish for audio-confirmed pronunciations. Never guess phonetic spellings from text patterns — that's how you get "BROO-noh" wrong on air.

---

## Implementation Notes

### Agent Architecture
- Each data fetcher is an independent async agent (Python class extending BaseAgent)
- Agents share a common `DataCache` with configurable TTL
- Agents report their source provenance (`data_source` field on every output)
- Agents fail independently — one agent failing doesn't block others
- The workflow orchestrator (LangGraph or custom state machine) manages phases and progress emission

### LLM Configuration
- **Synthesis LLM**: GPT-4o-mini or Claude 3.5 Sonnet or self-hosted Qwen 72B
- **Per-player bio LLM**: Cheaper model (Nova Sonic / GPT-4o-mini) for bulk parallel processing
- **LLM backend** configurable via `LLM_BACKEND` env var (openai | anthropic | vllm | deepseek | wafer)
- **Commentary notes** can override via `COMMENTARY_NOTES_LLM_BACKEND`
- **Self-hosted vLLM** for zero-cost batch processing at scale

### BrightData MCP (5000 Free Credits)
- **Use for**: paywalled article extraction (The Athletic, premium newspapers), anti-bot-blocked sites (Transfermarkt, WhoScored), geo-restricted content
- **Pre-built scrapers**: BrightData marketplace has ready-made soccer scrapers for all major sports sites
- **Credits burn rate**: ~1 credit per page scrape; 5000 credits = 5000 pages
- **Strategy**: Use on high-value, hard-to-scrape sources; use free tools (Jina, Wikipedia) for easy sources
- **MCP integration**: BrightData MCP server provides structured data extraction with schema mapping

### Caching Strategy
| Data Type | TTL | Reason |
|---|---|---|
| Match Brief JSON (full) | 4 hours | Match context doesn't change |
| Player bios + stats | 1 hour | Can update with late news |
| Weather forecast | 30 minutes | Forecast updates frequently |
| Team news / injuries | 30 minutes | Breaking news window |
| H2H records | 4 hours | Historical, static |
| Squad lists | 1 hour | Late changes possible |
| Lineup predictions | 20 minutes | Until team sheets confirmed |
| Officials assignments | 4 hours | Confirmed pre-match |
| Manager profiles | 4 hours | Static for the season |
| Club history | 24 hours | Fully static |
| Pronunciation | 24 hours | Names don't change |

### Rate Limiting Strategy
- **FootballData.org**: 10 req/min — respect strictly, cache aggressively
- **ESPN**: ~120/min — generous, use as primary source
- **Tavily**: 5000 searches/month — use for synthesis queries only
- **Exa**: 2500 searches/month — reserve for evidence gap-filling
- **Open-Meteo**: Unlimited — always use for weather
- **Wikipedia**: No rate limit — use freely for structured data
- **BrightData**: 5000 credits — budget for high-value paywalled content

### Error Recovery
- Every agent returns `data_status: "unavailable"` on failure, not an exception
- Failed agents don't block the pipeline — warnings accumulate in state
- Exa gap-filler activates only when accepted evidence count < threshold (4 items)
- Deep Research enrichment (optional) runs only if configured
- The NoteOrganizer synthesizes what's available, not what's ideal

### Progress Emission
- WebSocket-compatible progress events throughout the pipeline
- SSE streaming for the commentary notes endpoint
- Redis pub/sub for background job status
- Progress format: `{phase, message, agent_count, done}`

### Output Formats
1. **Markdown**: Full broadcast brief with sections, bullet lists, tables
2. **NotesStore JSON**: Structured with O(1) tag-lookup (event_type → NarrativeBeats)
3. **NarrativeBeats**: Individual fact units with source URLs, confidence scores, event tags
4. **Fact Ledger**: Every claim tracked with source URL and evidence tier
5. **Quality Report**: Accepted/rejected evidence counts, missing sections, revision count