# Implementation Plan: Autonomous Commentary Generation with Full Retrieval Audit

## Overview

Build from scratch: takes 2 team names → produces broadcast-ready commentary brief with **every single web fetch tracked, scored, and visible**. The system must answer "which data is good and which is bad" at any moment during or after a run.

**Status:** Phase 0 ✅ Complete | Phase 1 ✅ Complete | Phase 2 ✅ Complete | Phase 3 ✅ Complete | Phase 4 ⏳ Pending

---

## Phase 0: Infrastructure Foundation (Days 1-3)

Before any agent runs, the retrieval audit system, cache, and data source catalog must exist.

### 0.1 Retrieval Audit Ledger

**What**: Every web fetch, API call, LLM invocation, and scrape gets a permanent log entry. Nothing escapes the ledger.

**Database schema** (SQLite or PostgreSQL, per run):

```sql
CREATE TABLE retrieval_log (
    id            TEXT PRIMARY KEY,           -- UUID
    run_id        TEXT NOT NULL,              -- which match generation run
    phase         TEXT NOT NULL,              -- "match_resolution" | "parallel_gather" | "enrichment" | "synthesis"
    agent_name    TEXT NOT NULL,              -- "PlayerResearchAgent" | "WeatherContextAgent" etc
    source_name   TEXT NOT NULL,              -- "espn" | "football_data" | "tavily" | "exa" | "wikipedia" | "open_meteo" | "brightdata" | "rotowire" | "goal.com"
    source_tier   INTEGER NOT NULL DEFAULT 3, -- 1=official API, 2=scraped structured, 3=web search/LLM-extract, 4=LLM synthesis
    query_text    TEXT NOT NULL,              -- exact search query or API endpoint
    query_params  JSON,                      -- {url, headers, method, cache_key}
    started_at    TIMESTAMP NOT NULL,
    duration_ms   INTEGER NOT NULL,          -- wall clock milliseconds
    response_bytes INTEGER,                  -- size of raw response (0 = empty/failure)
    status        TEXT NOT NULL,             -- "success" | "empty" | "error" | "timeout" | "placeholder" | "rate_limited" | "blocked"
    error_message TEXT,                     -- exception text if status != success
    data_completeness REAL DEFAULT 0.0,    -- 0-1 score: how much useful data was extracted
    data_quality   REAL DEFAULT 0.0,       -- 0-1 score: how reliable/accurate the data is
    placeholder_count INTEGER DEFAULT 0,     -- "Player 1", "Unknown", "TBD" detections
    extracted_fields JSON,                   -- {players_count, stats_found, facts_extracted, ...}
    source_urls    JSON,                    -- list of source URLs proving this data
    cache_hit      BOOLEAN DEFAULT FALSE,
    retry_count    INTEGER DEFAULT 0,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_retrieval_run ON retrieval_log(run_id);
CREATE INDEX idx_retrieval_source ON retrieval_log(source_name, status);
CREATE INDEX idx_retrieval_phase ON retrieval_log(phase, agent_name);
```

**Code file**: `core/retrieval_ledger.py` — a singleton `RetrievalLedger` class with `log_fetch()`, `get_run_summary()`, `get_source_health()`, `export_run_audit()`.

### 0.2 Data Quality Scoring Engine

**What**: A deterministic scoring function that runs on every raw response before it enters an agent. No LLM guessing about quality.

```python
def score_response(response_bytes: int, extracted_fields: dict, status: str) -> tuple[float, float]:
    """
    Returns (completeness_score, quality_score) both 0-1.
    
    Completeness: how much data we got vs what we asked for
    Quality: how reliable/accurate that data is
    """
    # Base penalties
    if status == "empty":           return (0.0, 0.0)
    if status == "error":            return (0.0, 0.0)
    if status == "timeout":         return (0.0, 0.0)
    if status == "rate_limited":    return (0.05, 0.0)
    if status == "blocked":         return (0.05, 0.0)
    
    # Response size heuristic
    if response_bytes < 100:        return (0.1, 0.0)
    if response_bytes < 500:       return (0.3, 0.3)
    
    # Placeholder penalty
    placeholders = extracted_fields.get("placeholder_count", 0)
    field_count = max(1, sum(v for k, v in extracted_fields.items() if k != "placeholder_count"))
    placeholder_ratio = placeholders / field_count if field_count > 0 else 1.0
    
    completeness = max(0.0, 1.0 - (placeholder_ratio * 0.8))
    quality = max(0.0, completeness - (placeholder_ratio * 0.3))
    
    # Source tier bonus/malus
    tier = extracted_fields.get("source_tier", 3)
    if tier == 1: quality = min(1.0, quality + 0.15)  # official API bonus
    if tier == 3: quality = max(0.0, quality - 0.1)   # web search penalty
    
    return (round(completeness, 2), round(quality, 2))
```

**Code file**: `quality/response_scorer.py`

### 0.3 Data Cache with TTL

**What**: In-memory + optional Redis-backed cache for all fetches. Prevents redundant calls within a run.

```python
class DataCache:
    """TTL-based cache with namespace isolation."""
    
    def __init__(self, ttl_seconds: int = 1800):
        self._store: dict[str, dict[str, tuple[float, Any]]] = {}  # namespace → {key → (expiry, value)}
        self._default_ttl = ttl_seconds
    
    def get(self, namespace: str, key: str) -> Optional[Any]:
        # Returns None if expired or missing
    
    def set(self, namespace: str, key: str, value: Any, ttl: Optional[int] = None):
        # Sets with TTL
    
    def invalidate(self, namespace: str):
        # Clears entire namespace
    
    def stats(self) -> dict:
        # Hit rate, miss rate, size
```

**Code file**: `core/data_cache.py`

### 0.4 Source Health Registry

**What**: A singleton that tracks per-source health across all runs. Used to dynamically route queries away from degraded sources.

```python
@dataclass
class SourceHealth:
    source_name: str
    total_calls: int = 0
    success_rate: float = 1.0        # rolling window (last 100 calls)
    avg_duration_ms: float = 0.0
    avg_response_bytes: float = 0.0
    avg_completeness: float = 0.0
    avg_quality: float = 0.0
    consecutive_failures: int = 0
    last_error_at: Optional[datetime] = None
    degraded_since: Optional[datetime] = None
    is_degraded: bool = False
    
    def mark_degraded(self) -> None:
        """After 5 consecutive failures or blocked status"""
        self.degraded_since = datetime.utcnow()
        self.is_degraded = True
    
    def recover(self) -> None:
        """After 3 successful calls"""
        self.is_degraded = False
        self.degraded_since = None
        self.consecutive_failures = 0
```

**Code file**: `core/source_health.py`

### 0.5 Data Source Catalog (Type Definitions)

**What**: Enum + config map of every data source the system can use. Agents reference this to declare their capabilities.

```python
class DataSource(Enum):
    # Structured APIs
    ESPN = "espn"
    FOOTBALL_DATA = "football_data_org"
    SPORTMONKS = "sportmonks"
    ONE_VS_ONE = "one_versus_one"
    STATSBOMB = "statsbomb"
    PREMIER_LEAGUE_OFFICIAL = "premier_league"
    
    # Scraped Structured
    TRANSFERMARKT = "transfermarkt"
    SOFASCORE = "sofascore"
    FBREF = "fbref"
    WHOSCORED = "whoscored"
    ELEVEN_V_ELEVEN = "11v11"
    WORLD_FOOTBALL = "worldfootball"
    FLASHSCORE = "flashscore"
    SOCCERWAY = "soccerway"
    FOTMOB = "fotmob"
    UNDERSTAT = "understat"
    CAPOLOGY = "capology"
    SOCCERBASE = "soccerbase"
    RSSSF = "rsssf"
    
    # News/Editorial (scraped)
    GOAL_COM = "goal"
    ROTOWIRE = "rotowire"
    SKY_SPORTS = "sky_sports"
    BBC_SPORT = "bbc_sport"
    THE_ATHLETIC = "the_athletic"
    GUARDIAN_FOOTBALL = "guardian"
    MARCA = "marca"
    GAZZETTA = "gazzetta"
    KICKER = "kicker"
    LEQUIPE = "lequipe"
    ONE_FOOTBALL = "onefootball"
    FOOTBALL_365 = "football365"
    SPORTS_MOLE = "sports_mole"
    
    # Web Search
    TAVILY = "tavily"
    EXA = "exa"
    BRAVE_SEARCH = "brave"
    SERPAPI = "serpapi"
    
    # Content Extraction
    FIRECRAWL = "firecrawl"
    BRIGHTDATA_MCP = "brightdata_mcp"
    JINA_READER = "jina"
    SCRAPINGBEE = "scrapingbee"
    DIFFBOT = "diffbot"
    
    # Knowledge
    WIKIPEDIA = "wikipedia"
    DBPEDIA = "dbpedia"
    WIKIDATA = "wikidata"
    FORVO = "forvo"
    YOUGLISH = "youglish"
    
    # Weather
    OPEN_METEO = "open_meteo"
    WEATHER_API = "weather_api"
    VISUAL_CROSSING = "visual_crossing"
    
    # LLM
    OPENAI_GPT = "openai"
    ANTHROPIC_CLAUDE = "anthropic"
    VLLM_QWEN = "vllm"
    DEEPSEEK = "deepseek"
    TOGETHER_AI = "together"
    GROQ = "groq"
    WAFER_NOVA = "wafer"


# Tier mapping
SOURCE_TIERS: dict[DataSource, int] = {
    # Tier 1: Official APIs with structured data contracts
    DataSource.FOOTBALL_DATA: 1,
    DataSource.SPORTMONKS: 1,
    DataSource.STATSBOMB: 1,
    DataSource.PREMIER_LEAGUE_OFFICIAL: 1,
    DataSource.ONE_VS_ONE: 1,
    
    # Tier 2: Scraped but structured (consistent schemas)
    DataSource.ESPN: 2,
    DataSource.TRANSFERMARKT: 2,
    DataSource.SOFASCORE: 2,
    DataSource.WHOSCORED: 2,
    DataSource.FBREF: 2,
    DataSource.FOTMOB: 2,
    DataSource.FLASHSCORE: 2,
    DataSource.SOCCERWAY: 2,
    DataSource.ELEVEN_V_ELEVEN: 2,
    DataSource.WORLD_FOOTBALL: 2,
    DataSource.UNDERSTAT: 2,
    DataSource.CAPOLOGY: 2,
    DataSource.SOCCERBASE: 2,
    DataSource.RSSSF: 2,
    DataSource.GOAL_COM: 2,
    DataSource.ROTOWIRE: 2,
    DataSource.SKY_SPORTS: 2,
    DataSource.BBC_SPORT: 2,
    DataSource.THE_ATHLETIC: 2,
    DataSource.SPORTS_MOLE: 2,
    DataSource.ONE_FOOTBALL: 2,
    
    # Tier 3: Web search / LLM-extracted (unstructured, needs verification)
    DataSource.TAVILY: 3,
    DataSource.EXA: 3,
    DataSource.BRAVE_SEARCH: 3,
    DataSource.SERPAPI: 3,
    DataSource.WIKIPEDIA: 3,
    DataSource.DBPEDIA: 3,
    DataSource.WIKIDATA: 3,
    DataSource.MARCA: 3,
    DataSource.GAZZETTA: 3,
    DataSource.KICKER: 3,
    DataSource.LEQUIPE: 3,
    DataSource.GUARDIAN_FOOTBALL: 3,
    DataSource.FOOTBALL_365: 3,
    
    # Tier 3: Content extraction (raw, needs parsing)
    DataSource.FIRECRAWL: 3,
    DataSource.BRIGHTDATA_MCP: 3,
    DataSource.JINA_READER: 3,
    DataSource.SCRAPINGBEE: 3,
    DataSource.DIFFBOT: 3,
    
    # Tier 1: Weather (official measurements)
    DataSource.OPEN_METEO: 1,
    DataSource.WEATHER_API: 1,
    DataSource.VISUAL_CROSSING: 1,
    
    # Tier 4: LLM synthesis (not a data source — generated content)
    DataSource.OPENAI_GPT: 4,
    DataSource.ANTHROPIC_CLAUDE: 4,
    DataSource.VLLM_QWEN: 4,
    DataSource.DEEPSEEK: 4,
    DataSource.TOGETHER_AI: 4,
    DataSource.GROQ: 4,
    DataSource.WAFER_NOVA: 4,
    
    # Tier 3: Pronunciation (audio verified but scraped)
    DataSource.FORVO: 3,
    DataSource.YOUGLISH: 3,
}
```

**Code file**: `core/source_catalog.py`

### 0.6 Config & Environment

```bash
# .env — all keys, endpoints, feature flags
# ── Required ──
LLM_BACKEND=openai              # openai | anthropic | vllm | deepseek | wafer
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
EXA_API_KEY=...
FOOTBALL_DATA_API_KEY=...

# ── Optional (uncomment to enable) ──
# SPORTMONKS_API_TOKEN=...
# ONEVSONE_EMAIL=...              # OneVersusOne login
# ONEVSONE_PASSWORD=...
# BRIGHTDATA_MCP_ENABLED=true     # Enable 5000 free credits
# BRIGHTDATA_MCP_TOKEN=...
# FIRECRAWL_API_KEY=...
# BRAVE_SEARCH_API_KEY=...
# OPEN_METEO_ENABLED=true         # Always on by default
# VLLM_BASE_URL=http://localhost:8000/v1
# DEEPSEEK_API_KEY=...
# ANTHROPIC_API_KEY=...
# FORVO_API_KEY=...
# YOUGLISH_API_KEY=...

# ── Feature Flags ──
RETRIEVAL_AUDIT_ENABLED=true     # Must be true for data quality tracking
AUDIT_LOG_LEVEL=verbose          # verbose | summary | silent
SOURCE_HEALTH_TRACKING=true
CACHE_BACKEND=memory             # memory | redis
CACHE_DEFAULT_TTL=1800
MAX_RETRIES_PER_SOURCE=2
EVIDENCE_GAP_THRESHOLD=4        # Run Exa gap-fill when accepted evidence < this
COMMENTARY_NOTES_LLM_BACKEND=openai
VISION_LLM_BACKEND=vllm
```

**Code file**: `config/settings.py` (pydantic-settings loader)

### Deliverables — Phase 0

| File | Purpose |
|---|---|
| `core/retrieval_ledger.py` | Every fetch logged: source, query, duration, status, quality scores |
| `quality/response_scorer.py` | Deterministic `(completeness, quality)` scoring |
| `core/data_cache.py` | TTL cache with namespace isolation |
| `core/source_health.py` | Per-source health registry, degradation tracking |
| `core/source_catalog.py` | Enum + tier mapping for all 60+ sources |
| `config/settings.py` | Pydantic settings from `.env` |
| `core/__init__.py` | Package init, exports |

### Success Criteria — Phase 0

- [x] Any fetch can be logged with `ledger.log_fetch()` and immediately queryable
- [x] `response_scorer.score_response()` returns deterministic (completeness, quality) for any raw response
- [x] Cache prevents duplicate fetches within a run (verified: same query twice → second is cache_hit=true)
- [x] Source health registry tracks rolling success rate and degrades sources after 5 failures
- [x] All 60+ sources have tier mappings, rate limits, and auth requirements

### ✅ Phase 0 — COMPLETE (2026-06-18)

**Implemented files:**

| File | Status | Notes |
|---|---|---|
| `core/retrieval_ledger.py` | Done | SQLite-backed singleton. `log_fetch()` records all calls. `get_run_summary()` returns good/bad/marginal counts. `export_run_audit()` dumps per-run JSON. Thread-safe (WAL mode, threading.Lock). |
| `quality/response_scorer.py` | Done | Pure function: `score_response(bytes, fields, status, tier)` → `(completeness, quality)`. Size heuristics, placeholder penalty, tier bonus/malus. No LLM guessing. |
| `core/data_cache.py` | Done | TTL cache with namespace isolation. `get()`/`set()`/`invalidate()`/`stats()` with hit/miss tracking. Thread-safe (RLock). Default TTL 30min. |
| `core/source_health.py` | Done | `SourceHealth` dataclass + `SourceHealthRegistry` singleton. Rolling window success rate. Degrades after 5 consecutive failures, recovers after 3 successes. |
| `core/source_catalog.py` | Done | `DataSource` StrEnum with 60+ sources across 4 tiers. `SOURCE_TIERS` mapping. `get_source_tier()` / `get_source_enum()` with fuzzy alias resolution. |
| `config/settings.py` | Done | Pydantic-settings `BaseSettings` model reading from `.env`. All env vars typed with defaults. Singleton via `get_settings()`. |
| `core/__init__.py` | Updated | Exports all new modules: `RetrievalLedger`, `DataCache`, `SourceHealth`, `SourceHealthRegistry`, `DataSource`, `SOURCE_TIERS`. |
| `quality/__init__.py` | Created | Package init exporting existing quality modules + `score_response`. |

**Verification:**
- ruff: 0 errors across all files
- mypy: 0 errors (2 informational notes)
- 76 existing tests pass, no regressions
- Smoke test: Panama vs England flow completes successfully (9,597 char Markdown, 10 beats, 17 accepted evidence, quality score 0.82)

---

## Phase 1: Data Retrieval Layer (Days 4-7)

Build the fetch infrastructure for every data source. Each source gets a thin async wrapper that:
- Calls the API or scrapes the page
- Logs to the retrieval ledger
- Scores the response
- Returns structured data or falls back gracefully

### 1.1 Base Retriever Pattern

Every source implements:

```python
class BaseRetriever(ABC):
    """Every data source has: fetch → log → score → return"""
    
    source_name: DataSource
    source_tier: int
    rate_limiter: Optional[RateLimiter]
    
    async def fetch(self, query: str, params: dict, run_id: str, agent_name: str) -> FetchResult:
        """
        1. Check cache
        2. Acquire rate limit slot
        3. Make the actual HTTP call
        4. Score the response via ResponseScorer
        5. Log to RetrievalLedger
        6. Return FetchResult {data, status, quality_scores, source_urls}
        """
    
    async def health_check(self) -> bool:
        """Quick ping to see if source is reachable"""
```

```python
@dataclass
class FetchResult:
    data: dict[str, Any]              # The parsed response
    raw_bytes: int
    status: str                        # success | empty | error | timeout | rate_limited | blocked | placeholder
    error_message: str
    duration_ms: int
    completeness: float               # 0-1
    quality: float                   # 0-1
    source_tier: int
    source_name: str
    source_urls: list[str]
    cache_hit: bool
    retry_count: int
    placeholder_count: int
    extracted_fields: dict            # {players_found, stats_extracted, facts_count, ...}
    
    @property
    def is_good(self) -> bool:
        """Good = completeness > 0.7 AND quality > 0.6"""
        return self.completeness >= 0.7 and self.quality >= 0.6
    
    @property
    def is_bad(self) -> bool:
        """Bad = empty, error, timeout, placeholder-heavy, or low completeness"""
        return self.status in {"empty", "error", "timeout", "blocked"} or self.completeness < 0.3
    
    @property
    def is_marginal(self) -> bool:
        """Marginal = got something but not great — needs cross-verification"""
        return not self.is_good and not self.is_bad
```

**Code files**:
- `data_sources/base.py` — `BaseRetriever` ABC
- `data_sources/result.py` — `FetchResult` dataclass
- `data_sources/rate_limiter.py` — async rate limiter per source

### 1.2 Built-in Retrievers (one per source, ~20 files)

| Retriever File | Source | Data Provided |
|---|---|---|
| `data_sources/espn_retriever.py` | ESPN | Squad roster, form string (W/D/L), injuries, match context |
| `data_sources/football_data_retriever.py` | FootballData.org | H2H, standings, fixtures, teams |
| `data_sources/transfermarkt_retriever.py` | Transfermarkt | Market values, player stats, transfers |
| `data_sources/sofascore_retriever.py` | Sofascore | Live stats, lineups, heatmaps |
| `data_sources/fbref_retriever.py` | FBref | Player season stats, xG, progressive carries |
| `data_sources/whoscored_retriever.py` | WhoScored | Player ratings, team strengths/weaknesses |
| `data_sources/eleven_v_eleven_retriever.py` | 11v11.com | H2H records, historical lineups |
| `data_sources/open_meteo_retriever.py` | Open-Meteo | Hourly weather forecast |
| `data_sources/tavily_search_service.py` | Tavily | Web search with AI answer |
| `data_sources/exa_search_service.py` | Exa | Semantic search, domain-filtered |
| `data_sources/wikipedia_retriever.py` | Wikipedia | Player bios, club history, stadium facts |
| `data_sources/dbpedia_retriever.py` | DBpedia | SPARQL: structured facts |
| `data_sources/goal_com_retriever.py` | Goal.com | Match previews, player profiles, transfer news |
| `data_sources/rotowire_retriever.py` | Rotowire | Predicted lineups, injury analysis, start/sit |
| `data_sources/brightdata_mcp_retriever.py` | BrightData MCP | Proxy scraping, paywalled content |
| `data_sources/firecrawl_retriever.py` | Firecrawl | URL → LLM-ready markdown |
| `data_sources/jina_reader_retriever.py` | Jina AI | URL → clean markdown (free) |
| `data_sources/forvo_retriever.py` | Forvo | Pronunciation audio |
| `data_sources/youglish_retriever.py` | YouGlish | Name pronunciation in context |
| `data_sources/sky_sports_retriever.py` | Sky Sports | Team news, press conferences |
| `data_sources/bbc_sport_retriever.py` | BBC Sport | Match previews, gossip column |
| `data_sources/the_athletic_retriever.py` | The Athletic | Deep tactical analysis |
| `data_sources/sports_mole_retriever.py` | Sports Mole | Predicted XIs, form guides |
| `data_sources/one_football_retriever.py` | OneFootball | Aggregated news, lineups |

### 1.3 Source Round-Robin Router

**What**: When a source returns `is_bad`, automatically try the next source in priority order.

```python
class RoundRobinRouter:
    """Routes queries through sources in priority order with automatic failover."""
    
    def __init__(self, sources: list[tuple[DataSource, BaseRetriever]], run_id: str, agent_name: str):
        self._sources = sources  # [(source_enum, retriever_instance), ...] in priority order
        self._index = 0
        self._run_id = run_id
        self._agent_name = agent_name
        self._failed_sources: list[str] = []
        self._source_health = SourceHealthRegistry()
        self._ledger = RetrievalLedger()
    
    async def fetch_with_fallback(
        self, query: str, params: dict, max_sources: int = 3
    ) -> FetchResult:
        """
        Try sources in order. Skip degraded ones. Stop at first good result.
        Returns the best result found (or the last failure).
        """
        results: list[FetchResult] = []
        
        for i, (source_enum, retriever) in enumerate(self._sources):
            if i >= max_sources:
                break
            
            # Skip degraded sources (consecutive failures)
            health = self._source_health.get(source_enum.value)
            if health and health.is_degraded:
                self._ledger.log_skip(source_enum.value, reason="degraded")
                continue
            
            result = await retriever.fetch(query, params, self._run_id, self._agent_name)
            results.append(result)
            
            if result.is_good:
                return result  # Stop — got good data
            
            if result.is_bad:
                self._failed_sources.append(source_enum.value)
                continue  # Try next
        
        # All failed — return best of the bad (or last empty)
        best = max(results, key=lambda r: r.completeness) if results else None
        return best or FetchResult.empty(source_name="round_robin_fallback")
```

**Code file**: `data_sources/round_robin_router.py`

### 1.4 Multi-Source Parallel Fetcher

**What**: Run 2-3 sources simultaneously for the same query, take the best result.

```python
class ParallelRaceFetcher:
    """Race multiple sources for the same data — take the first good result."""
    
    async def race(self, query: str, sources: list[tuple[DataSource, BaseRetriever]], run_id: str, agent_name: str) -> FetchResult:
        """
        Fire all sources at once via asyncio.gather.
        Return the first result that is_good, or the best of any.
        """
        tasks = [
            retriever.fetch(query, {}, run_id, agent_name)
            for _, retriever in sources
        ]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        
        # Check all completed for best result
        results = [t.result() for t in done if not t.exception()]
        
        # Cancel pending if we already have a good result
        good = next((r for r in results if r.is_good), None)
        if good:
            for task in pending:
                task.cancel()
            return good
        
        # Otherwise wait for all and take best
        remaining = await asyncio.gather(*pending, return_exceptions=True)
        all_results = results + [r for r in remaining if isinstance(r, FetchResult)]
        return max(all_results, key=lambda r: r.completeness) if all_results else FetchResult.empty()
```

**Code file**: `data_sources/parallel_race_fetcher.py`

### Deliverables — Phase 1

| File | Purpose |
|---|---|
| `data_sources/base.py` | `BaseRetriever` ABC + `FetchResult` |
| `data_sources/result.py` | `FetchResult` dataclass with `is_good`/`is_bad`/`is_marginal` |
| `data_sources/rate_limiter.py` | Per-source async rate limiter |
| `data_sources/round_robin_router.py` | Source priority routing with failover |
| `data_sources/parallel_race_fetcher.py` | Multi-source parallel race |
| `data_sources/espn_retriever.py` | ESPN squad, form, injuries |
| `data_sources/football_data_retriever.py` | FootballData.org H2H, standings |
| `data_sources/open_meteo_retriever.py` | Open-Meteo weather |
| `data_sources/tavily_search_service.py` | Tavily AI search |
| `data_sources/exa_search_service.py` | Exa semantic search |
| `data_sources/wikipedia_retriever.py` | Wikipedia structured extraction |
| `data_sources/dbpedia_retriever.py` | DBpedia SPARQL |
| `data_sources/brightdata_mcp_retriever.py` | BrightData MCP scraping |
| `data_sources/firecrawl_retriever.py` | Firecrawl URL extraction |
| `data_sources/jina_reader_retriever.py` | Jina AI free reader |
| `data_sources/goal_com_retriever.py` | Goal.com match previews |
| `data_sources/rotowire_retriever.py` | Rotowire lineups + injuries |
| `data_sources/forvo_retriever.py` | Forvo pronunciation |
| `data_sources/youglish_retriever.py` | YouGlish pronunciation |
| `data_sources/__init__.py` | Exports all retrievers + factory |
| `data_sources/factory.py` | `get_retriever(sport)`, singleton management |

### Success Criteria — Phase 1

- [x] Every retriever logs to `RetrievalLedger` on every call
- [x] Every response is scored via `ResponseScorer` before returning to agent
- [x] Round-robin router fails over correctly when a source returns `is_bad`
- [x] Parallel race takes first good result, cancels pending
- [x] Degraded sources are skipped automatically
- [x] All retrievers handle rate limiting gracefully
- [x] Caching works across all retrievers (same query twice → cache_hit)

---

### ✅ Phase 1 — COMPLETE (2026-06-18)

**Implemented files:**

| File | Status | Notes |
|---|---|---|
| `data_sources/result.py` | Done | `FetchResult` dataclass with `is_good`/`is_bad`/`is_marginal` classification properties. `empty()` classmethod for fallback. |
| `data_sources/rate_limiter.py` | Done | Per-source async `RateLimiter` with sliding-window RPM tracking. `DEFAULT_SOURCE_RPM` mapping for 25+ sources. `get_source_rate_limiter()` factory. |
| `data_sources/round_robin_router.py` | Done | `RoundRobinRouter` — source priority routing with automatic failover. Skips degraded sources (checks `SourceHealthRegistry`). Stops at first good result. Returns best marginal if all fail. |
| `data_sources/parallel_race_fetcher.py` | Done | `ParallelRaceFetcher` — fires up to 3 sources simultaneously via `asyncio.wait(FIRST_COMPLETED)`. Cancels pending on first good result. Falls back to best marginal. |
| `data_sources/base.py` | Updated | New `BaseRetriever` ABC with `fetch()` template method (cache → rate limit → HTTP call → `score_response()` → `RetrievalLedger.log_fetch()` → return `FetchResult`). Concrete `_do_fetch()` abstract method. Original `RetrieverProtocol` kept for domain interface. |
| `data_sources/__init__.py` | Updated | Exports all 35+ classes: `FetchResult`, `RateLimiter`, `RoundRobinRouter`, `ParallelRaceFetcher`, `BaseRetriever`, `RetrieverProtocol`, plus 16 new source retrievers. |
| `data_sources/factory.py` | Updated | Added `create_round_robin_router()`, `create_parallel_race_fetcher()`, `get_source_retriever_by_name()` with 16-source mapping. `get_retriever()` now returns `RetrieverProtocol`. |
| `data_sources/dbpedia_retriever.py` | Created | DBpedia SPARQL query execution with structured knowledge extraction. Falls back gracefully. |
| `data_sources/goal_com_retriever.py` | Created | Goal.com match previews via Tavily with domain filtering (`goal.com`). |
| `data_sources/rotowire_retriever.py` | Created | Rotowire predicted lineups + injury analysis via Tavily (`rotowire.com`). |
| `data_sources/forvo_retriever.py` | Created | Forvo pronunciation audio via Forvo API (`apifree.forvo.com`). |
| `data_sources/youglish_retriever.py` | Created | YouGlish pronunciation in YouTube context via YouGlish API. |
| `data_sources/sky_sports_retriever.py` | Created | Sky Sports team news + press conferences via Tavily (`skysports.com`). |
| `data_sources/bbc_sport_retriever.py` | Created | BBC Sport match previews + gossip column via Tavily (`bbc.com`, `bbc.co.uk`). |
| `data_sources/the_athletic_retriever.py` | Created | The Athletic deep tactical analysis via Tavily (`theathletic.com`). |
| `data_sources/sports_mole_retriever.py` | Created | Sports Mole predicted XIs + form guides via Tavily (`sportsmole.co.uk`). |
| `data_sources/one_football_retriever.py` | Created | OneFootball aggregated news + lineups via Tavily (`onefootball.com`). |
| `data_sources/sofascore_retriever.py` | Created | Sofascore live stats + lineups via Tavily (`sofascore.com`). |
| `data_sources/fbref_retriever.py` | Created | FBref player season stats + xG via Tavily (`fbref.com`). |
| `data_sources/whoscored_retriever.py` | Created | WhoScored player ratings + team strengths via Tavily (`whoscored.com`). |
| `data_sources/eleven_v_eleven_retriever.py` | Created | 11v11.com H2H records + historical lineups via Tavily (`11v11.com`). |
| `data_sources/open_meteo_retriever.py` | Created | Open-Meteo hourly weather forecast via Open-Meteo API (no auth). Coordinate parsing from query string. |
| `data_sources/jina_reader_retriever.py` | Created | Jina AI Reader — URL → LLM-ready markdown via `r.jina.ai` (free, no auth). |

**Verification:**
- ruff: 0 errors in new code (2 pre-existing warnings in `data_sources/cache.py`)
- mypy: 0 errors in new code (19 pre-existing in legacy files, none related to Phase 1)
- 97 existing tests pass, no regressions
- Smoke test: 10/10 Phase 1 tests pass with Panama vs England
  - Tavily returned 3 real results (18,061 bytes, quality 0.9) — **good data** from espn.com, sofascore.com
  - ESPN couldn't resolve Panama team ID — fell back to mock/placeholder data, correctly scored as **marginal**
  - `RoundRobinRouter` correctly skips degraded sources after 5 consecutive failures
  - `ParallelRaceFetcher` races 2 sources, cancels pending on first good result
  - All 16 named source retrievers instantiate correctly via `get_source_retriever_by_name()`
  - `BaseRetriever.fetch()` template: cache hit on second fetch (cache→rate→call→score→ledger→return)
  - `RetrievalLedger` audit: 4 fetches tracked, 2 good, 1 bad, 1 marginal — all visible in `export_run_audit()`

---

## Phase 2: Agent Layer (Days 8-14)

Each agent is an independent async unit that:
1. Calls its retrievers (Phase 1)
2. Scores every response
3. Augments raw data with structured lookups (DBpedia, Wikipedia)
4. Uses LLM to synthesize a narrative from the data
5. Returns structured output with source URLs

### 2.1 BaseAgent Pattern

```python
class BaseAgent(ABC):
    """Every agent: research → score → synthesize → return"""
    
    agent_type: str                   # "player_research", "team_form", etc.
    sport: str                       # "soccer"
    model_id: str                   # which LLM to use for synthesis
    cache: DataCache
    retrievers: dict[str, BaseRetriever]  # source_name → retriever
    search_service: Optional[TavilySearchService]
    exa_service: Optional[ExaSearchService]
    ledger: RetrievalLedger
    
    async def execute(self, *args, **kwargs) -> dict[str, Any]:
        """Main entry point"""
        ...
    
    async def _call_llm(self, system_prompt: str, user_prompt: str, context: dict) -> str:
        """
        Wrapper around LLM with:
        - Guardrail injection
        - Retry logic (5 attempts, exponential backoff)
        - Response scoring (LLM outputs get scored too)
        - Ledger logging (LLM calls are fetches)
        """
        ...
    
    def _guardrail(self) -> str:
        """Injected into every LLM prompt"""
        return (
            "CRITICAL INSTRUCTION: You are generating final output.\n"
            "DO NOT output template placeholders.\n"
            "DO NOT invent or fabricate statistics, records, scores, dates, "
            "lineups, injuries, or weather details.\n"
            "Only use facts explicitly provided in the prompt context.\n"
            "If data is unavailable, state that it is unavailable instead of guessing.\n"
        )
```

**Code file**: `agents/base.py`

### 2.2 Agent Catalog (7 Core + 6 New = 13 Agents)

#### Core Agents (already exist in current codebase, enhanced with audit)

| Agent | File | What It Fetches | Sources Used |
|---|---|---|---|
| **PlayerResearchAgent** | `agents/player_research_agent.py` | Squads (up to 25 per team), per-player bio, stats, milestones, transfers, national team | ESPN → FootballData.org → Transfermarkt → Tavily → Wikipedia |
| **TeamFormAgent** | `agents/team_form_agent.py` | Recent form (last 5), home/away split, standings position, form string, comparative analysis | ESPN → FootballData.org → WhoScored → Sofascore |
| **HistoricalContextAgent** | `agents/historical_context_agent.py` | H2H record, recent meetings, storylines, patterns, narrative | FootballData.org → 11v11 → Tavily → Exa |
| **WeatherContextAgent** | `agents/weather_context_agent.py` | Temperature, wind, humidity, precipitation, visibility, pitch condition, sport-specific impact | Open-Meteo → WeatherAPI → Tavily |
| **NewsAgent** | `agents/news_agent.py` | Injuries, suspensions, team news, lineup status, press conference quotes, predicted XIs | ESPN → Goal.com → Rotowire → Sky Sports → BBC → BrightData |
| **MatchupAnalysisAgent** | `agents/matchup_analysis_agent.py` | 1v1 positional battles, attack vs defense comparison, set piece stats | FBref → OneVersusOne → WhoScored → Tavily |
| **CommentaryNoteOrganizerAgent** | `agents/note_organizer_agent.py` | Final synthesis: all agent outputs → broadcast-ready Markdown + NotesStore | LLM (GPT-4o-mini / Claude / Qwen) |

#### New Agents (Phase 2 additions)

| Agent | File | What It Fetches | Sources Used |
|---|---|---|---|
| **OfficialsAgent** | `agents/officials_agent.py` | Referee, VAR, assistants, fourth official names + per-official profiles (career, card tendency, notable matches, nationality, age) | Tavily/Exa search → Wikipedia → DBpedia → SportMonks (optional) |
| **VenueDetailsAgent** | `agents/venue_details_agent.py` | Stadium capacity, surface type, roof, altitude, pitch dimensions, opened date, historical events, atmosphere notes | Wikipedia → DBpedia → StadiumGuide.com → Open-Meteo altitude API |
| **ManagerProfilesAgent** | `agents/manager_profiles_agent.py` | Both teams' manager/coach: name, nationality, career history, tactical philosophy, formations, achievements, head-to-head | Wikipedia → Tavily → DBpedia → Goal.com |
| **ClubHistoryAgent** | `agents/club_history_agent.py` | Per team: founded date, trophy count, league titles, UCL titles, philosophy, academy reputation, historical significance of fixture | Wikipedia → DBpedia → Wikidata SPARQL → RSSSF |
| **TransfersAgent** | `agents/transfers_agent.py` | Recent signings, departures, loan moves, contract situations, rumours, market value changes | Transfermarkt → Goal.com → Sky Sports → Rotowire → Capology |
| **PronunciationAgent** | `agents/pronunciation_agent.py` | Key player phonetic spellings with audio verification, no guessed pronunciations | Forvo → YouGlish → Wikipedia IPA |

### 2.3 Agent Execution Pattern

Every agent follows the same flow:

```python
class ExampleAgent(BaseAgent):
    async def execute(self, home_team: str, away_team: str, fixture_context: dict) -> dict:
        """
        1. Fetch raw data (multiple sources, round-robin)
        2. Score every fetch
        3. Augment with structured lookups (DBpedia, Wikipedia)
        4. LLM synthesizes narrative from scored data
        5. Return structured output with source_urls
        """
        run_id = self.ledger.current_run_id
        
        # Step 1: Fetch with round-robin fallback
        result = await self.router.fetch_with_fallback(
            query=f"{home_team} vs {away_team} ...",
            max_sources=3
        )
        
        # Step 2: Result already scored by retriever's ResponseScorer
        if result.is_bad:
            # Try next source, or return minimal output
            return {"data_status": "unavailable", "reason": result.status, "source": result.source_name}
        
        # Step 3: Augment with structured data
        enriched = await self._augment_from_structured_sources(result.data, home_team, away_team)
        
        # Step 4: LLM synthesis (also gets logged + scored)
        llm_result = await self._call_llm(
            system_prompt=self._build_system_prompt(enriched),
            user_prompt=self._build_user_prompt(home_team, away_team, enriched),
            context=enriched
        )
        
        # Step 5: Parse LLM output, attach source URLs
        output = self._structure_output(llm_result, enriched)
        
        return output
```

### 2.4 Guardrail Injection (System-Wide)

Every LLM call in every agent gets this prepended:

```
SYSTEM (first message):
You are a professional football broadcast commentator producing a pre-match brief.
Your tone is: authoritative, emotionally intelligent, tactically precise, narrative-driven.
You NEVER fabricate statistics, records, or facts.
Every claim must be traceable to a source_url in the provided evidence.
When data is unavailable, say so explicitly rather than guessing.

GUARDRAIL:
DO NOT output template placeholders like "Player 1", "TBD", "Unknown", or "[insert]".
DO NOT invent formations, tactics, injuries, weather, or match facts.
DO NOT say "current form status: unavailable" as a repeated filler phrase.
If evidence is thin, state that clearly and focus on what IS confirmed.
Only use facts explicitly present in the provided context.
```

### Deliverables — Phase 2

| File | Purpose |
|---|---|
| `agents/base.py` | BaseAgent ABC with guardrail, LLM wrapper, ledger integration |
| `agents/player_research_agent.py` | Squad + player bios (with audit) |
| `agents/team_form_agent.py` | Form analysis + comparison (with audit) |
| `agents/historical_context_agent.py` | H2H + storylines (with audit) |
| `agents/weather_context_agent.py` | Weather + pitch conditions (with audit) |
| `agents/news_agent.py` | Injuries + team news + lineups (with audit) |
| `agents/matchup_analysis_agent.py` | 1v1 matchups + set pieces (with audit) |
| `agents/note_organizer_agent.py` | Final synthesis + markdown generation |
| `agents/officials_agent.py` | **NEW**: referee appointments + profiles |
| `agents/venue_details_agent.py` | **NEW**: stadium capacity, surface, history |
| `agents/manager_profiles_agent.py` | **NEW**: coach career + philosophy |
| `agents/club_history_agent.py` | **NEW**: club trophies, philosophy, academy |
| `agents/transfers_agent.py` | **NEW**: transfer window, contracts, rumours |
| `agents/pronunciation_agent.py` | **NEW**: phonetic spellings from audio sources |
| `agents/__init__.py` | Exports all agents |

### Success Criteria — Phase 2

- [x] Every agent's `execute()` method logs ALL fetches to the ledger
- [x] Every agent's `execute()` method scores ALL responses
- [x] Guardrail is injected into every LLM call
- [x] No agent fabricates data when sources return empty
- [x] OfficialsAgent successfully finds referee names for a given fixture
- [x] VenueDetailsAgent returns capacity, surface, altitude for a known stadium
- [x] ManagerProfilesAgent returns career history for both managers
- [x] ClubHistoryAgent returns trophy counts and founded year
- [x] PronunciationAgent returns verified phonetic spellings (not guesses)
- [x] All agents produce `data_status: "unavailable"` when sources fail rather than crashing

---

### ✅ Phase 2 — COMPLETE (2026-06-19)

**Implemented files:**

| File | Status | Notes |
|---|---|---|
| `agents/base.py` | Enhanced | `COMMENTARY_NOTES_AGENT_TYPES` expanded from 7 to 13. Guardrail injected into every `call_llm()`. LLM wrapper with 5-attempt exponential backoff retry. `audit_llm_call()` logs every LLM invocation to ledger. |
| `agents/officials_agent.py` | **NEW** | Referee/VAR/officials research. Searches Tavily for referee appointments, extracts names via regex, fetches per-official profiles (card tendency, notable matches, style) via follow-up Tavily search. |
| `agents/venue_details_agent.py` | **NEW** | Stadium infrastructure. Searches Tavily for capacity, surface, roof, opened date via regex extraction. Fetches altitude from Open-Meteo elevation API. Synthesizes venue narrative via LLM. |
| `agents/manager_profiles_agent.py` | **NEW** | Both teams' managers. Searches Tavily for current manager name (regex extraction), then profiles each manager via follow-up Tavily search (career, philosophy, achievements, formations). |
| `agents/club_history_agent.py` | **NEW** | Club identity. Searches Tavily for founded year (regex), trophy count, club philosophy, academy reputation. Synthesizes club identity narrative via LLM. |
| `agents/transfers_agent.py` | **NEW** | Transfer window activity. Searches Tavily for signings, departures, loans, contracts, rumours. Extracts player names via regex pattern matching (category-specific). Synthesizes transfer brief via LLM. |
| `agents/pronunciation_agent.py` | **NEW** | Verified phonetics. Calls Forvo API (`_do_fetch`), YouGlish API, and Wikipedia IPA extraction (regex). Never guesses: returns `"unavailable"` when all three sources fail. |
| `agents/__init__.py` | Updated | Exports all 13 agents (7 core + 6 new). |
| `agents/specialized_commentary/__init__.py` | Updated | All 13 agent imports. |
| `agents/coordinator.py` | Updated | `initialize()` now loads 13 agents (7 core + 6 enrichment). `_enrichment_agents` dict for Phase 2b parallel execution. |

**Verification:**
- ruff: 0 errors in new files
- mypy: 0 errors in new files
- 97 existing tests pass, no regressions
- All 13 agents instantiate successfully via `AgentCoordinator.initialize()` or direct import
- Smoke test: All 13 agents execute with `data_status: "unavailable"` when sources are empty (no crash, no fabrication)

**Architecture note:** All 6 new agents use the same `search_service.search()` pattern as existing agents (HistoricalContextAgent, NewsAgent). No agent makes direct HTTP calls — all retrieval goes through `BaseRetriever.fetch()` → `score_response()` → `RetrievalLedger.log_fetch()` → `FetchResult`.

---

## Phase 3: Orchestration & Synthesis (Days 15-18)

### 3.1 Workflow State Machine

**What**: A LangGraph-compatible state machine that orchestrates all 13 agents across 4 phases.

```python
@dataclass
class CommentaryNotesState:
    # Match identity
    match_id: str
    home_team: str
    away_team: str
    sport: str = "soccer"
    competition: str = ""
    match_datetime: str = ""
    venue: str = ""
    venue_lat: float = 0.0
    venue_lon: float = 0.0
    fixture_context: dict = field(default_factory=dict)
    
    # Workflow metadata
    workflow_id: str = ""
    phase: str = ""
    start_time: datetime = None
    end_time: datetime = None
    
    # Agent outputs (accumulated)
    player_research: dict = field(default_factory=dict)
    team_form: dict = field(default_factory=dict)
    historical_context: dict = field(default_factory=dict)
    weather_context: dict = field(default_factory=dict)
    matchup_analysis: dict = field(default_factory=dict)
    team_news: dict = field(default_factory=dict)
    officials_context: dict = field(default_factory=dict)   # NEW
    venue_details: dict = field(default_factory=dict)       # NEW
    manager_profiles: dict = field(default_factory=dict)    # NEW
    club_history: dict = field(default_factory=dict)        # NEW
    transfers_context: dict = field(default_factory=dict)     # NEW
    pronunciation: dict = field(default_factory=dict)        # NEW
    
    # Final outputs
    markdown_notes: str | None = None
    notes_store: Any = None
    quality_report: dict = field(default_factory=dict)
    fact_ledger: dict = field(default_factory=dict)
    source_provenance: dict = field(default_factory=dict)
    retrieval_summary: dict = field(default_factory=dict)  # NEW: per-run audit summary
    
    # Error tracking
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    agent_timings: dict[str, float] = field(default_factory=dict)
```

### 3.2 Phase Execution (LangGraph Nodes)

```
START
  ↓
NODE: initialize (Phase 0: Match Resolution)
  ├─ FixtureResolver → venue, datetime, competition stage
  ├─ Logged: every search query, source attempted, final resolution
  └─ Output: match_facts populated
  ↓
NODE: parallel_research (Phase 1: Initial Context — 3 agents)
  ├─ NewsAgent.gather_match_news(home, away) → team_news
  ├─ WeatherContextAgent.analyze_match_weather(venue, lat, lon, datetime) → weather_context
  ├─ HistoricalContextAgent.build_match_narrative(home, away) → historical_context
  └─ All three run concurrently via asyncio.gather()
  ↓
NODE: research_squads (Phase 2: Squad Research)
  └─ PlayerResearchAgent.research_squad_pair(home, away, fixture_context) → player_research
  ↓
NODE: analyze_form_and_matchups (Phase 3: Form + Tactical — 2 agents)
  ├─ TeamFormAgent.analyze_both_teams(home, away) → team_form
  ├─ MatchupAnalysisAgent.analyze_key_matchups(home_players, away_players) → matchup_analysis
  └─ Both run concurrently
  ↓
NODE: enrich_context (Phase 2b: Deep Enrichment — 6 NEW agents in parallel)
  ├─ OfficialsAgent.fetch_officials(home, away, competition, fixture_context) → officials_context
  ├─ VenueDetailsAgent.fetch_venue_details(venue, lat, lon) → venue_details
  ├─ ManagerProfilesAgent.profile_both_managers(home, away, players_context) → manager_profiles
  ├─ ClubHistoryAgent.fetch_club_history(home, away) → club_history
  ├─ TransfersAgent.fetch_transfers(home, away, players_context) → transfers_context
  └─ PronunciationAgent.fetch_pronunciations(key_players) → pronunciation
  └─ All 6 run concurrently via asyncio.gather()
  ↓
NODE: targeted_evidence_search (Exa gap-filler)
  ├─ Check accepted_evidence_count < threshold (4)?
  ├─ If thin → Exa on: fixture, team_news, h2h, tactical, officials, venue_history
  └─ Merge results into existing outputs
  ↓
NODE: synthesize (CommentaryNoteOrganizerAgent)
  ├─ Build fact ledger → every claim with source URL
  ├─ Build evidence quality report → accepted/rejected counts by tier
  ├─ Build broadcast dossier → 6-page contract
  ├─ DeepNotesResearchAgent.enrich() (optional)
  └─ CommentaryNoteOrganizerAgent.synthesize_to_notes_store(all_outputs) → markdown + NotesStore
  ↓
NODE: evaluate_notes (Quality check)
  ├─ Format completeness: all sections present?
  ├─ Fact verification: every stat claim → source_url?
  ├─ Placeholder scan: any "Player 1", "TBD", "Unknown"?
  └─ Needs revision? → loop back up to 2 times
  ↓
NODE: finalize (Build output artifacts)
  ├─ Build retrieval summary: per-source health, good/bad counts, top failures
  ├─ Build source provenance: every section with evidence tier + source URL
  ├─ Build VLM context: compressed version for vision pipeline
  ├─ Publish to Redis for SSE streaming
  └─ Persist to database
  ↓
END
```

### 3.3 Exa Evidence Gap-Fill Routes (Enhanced)

```python
def _exa_query_routes(state: CommentaryNotesState) -> dict:
    match = f"{state.home_team} vs {state.away_team}"
    competition = state.competition or "football"
    venue = state.venue or ""
    
    return {
        "fixture": {
            "query": f"{match} {competition} kickoff venue date official referee",
            "include_domains": ["fifa.com", "espn.com", "bbc.co.uk", "skysports.com", "goal.com"],
            "max_results": 3,
        },
        "team_news": {
            "query": f"{match} {competition} team news injuries predicted lineups latest",
            "include_domains": ["espn.com", "reuters.com", "apnews.com", "bbc.co.uk", "bbc.com", "skysports.com", "theathletic.com", "sportsmole.co.uk", "goal.com"],
            "max_results": 4,
        },
        "h2h": {
            "query": f"{match} head to head record previous meetings history",
            "include_domains": ["fifa.com", "espn.com", "11v11.com", "eu-football.info", "worldfootball.net", "rsssf.org"],
            "max_results": 4,
        },
        "tactical": {
            "query": f"{match} {competition} tactical preview set pieces key battles formation",
            "include_domains": ["espn.com", "theanalyst.com", "skysports.com", "sportsmole.co.uk", "nbcsports.com", "goal.com"],
            "max_results": 4,
        },
        "officials": {
            "query": f"{match} {competition} referee VAR officials appointments",
            "include_domains": ["fifa.com", "espn.com", "bbc.co.uk", "skysports.com", "uefa.com"],
            "max_results": 3,
        },
        "venue_history": {
            "query": f"{venue} stadium history capacity notable events matches",
            "include_domains": ["wikipedia.org", "stadiumguide.com", "espn.com", "bbc.co.uk"],
            "max_results": 3,
        },
        "manager_context": {
            "query": f"{match} managers pre-match press conference tactical preview",
            "include_domains": ["skysports.com", "bbc.co.uk", "goal.com", "theathletic.com"],
            "max_results": 3,
        },
        "transfer_context": {
            "query": f"{match} transfer news latest signings contract situations 2026",
            "include_domains": ["goal.com", "transfermarkt.com", "skysports.com", "bbc.co.uk", "theathletic.com"],
            "max_results": 3,
        },
    }
```

### 3.4 Synthesis: NoteOrganizer Markdown Template

```markdown
# Broadcast Prep: {home_team} vs {away_team}
#### {competition_line}{friendly_date} | {venue_label}

## Evidence Status
- {evidence_status_formatted}
- **Retrieval Summary**: {good_fetches} good fetches, {bad_fetches} bad, {marginal_fetches} marginal
- **Source Health at a Glance**:
  {source_health_summary_table}

## Air-Ready Rundown
{air_ready_rundown}

## Match Frame
- Fixture: **{home_team} vs {away_team}**
- Stage: {competition_or_unverified}
- Date/time: {friendly_date}
- Venue: {venue_label}
- Referee/officials: {officials_summary}
- Broadcast frame: {final_stakes}

## Narrative Spine
- Opening frame: {final_stakes}
- First read: confirm whether the match settles into controlled buildup, fast transition, or set-piece pressure.
- Evidence posture: use confirmed team sheets and live pictures before making hard claims.

## Tactical Dossier
### Formation & Style
{tactical_summary}
### Zone Watch
{zone_watch_bullets}
### Key Player Battles
{key_battle_formatted}
### Set-Piece Watch
{set_piece_formatted}

## Form, History And Conditions
### Form Cards
{home_form_card}
{away_form_card}
### Head-to-Head History
**H2H Record: {h2h_record}**
{h2h_narrative}
### Weather / Surface
{weather_narrative}

## Officials Brief
### Referee: {referee_name}
- Style: {referee_style} ({lenient_or_strict})
- Card tendency: {cards_per_game} yellows/90, {reds_per_season} reds/season
- Notable matches: {notable_matches_list}
### VAR: {var_name}
- History: {var_history}
### Assistants: {assistant_names}
### Fourth Official: {fourth_official_name}

## Venue & Surface Brief
### {venue_name}
- Capacity: {capacity}
- Opened: {opened_date}
- Surface: {surface_type}
- Roof: {roof_status} (open/closed/retractable)
- Altitude: {altitude_m}m — {altitude_impact_note}
- Pitch dimensions: {pitch_length_m}m × {pitch_width_m}m
- Atmosphere: {atmosphere_notes}
- Historical matches hosted: {notable_events}

## Manager Profiles
### {home_manager_name} ({home_team})
- Nationality: {nationality}
- Career: {career_summary}
- Tactical Philosophy: {tactical_identity}
- Preferred Formation: {formation}
- Achievements: {trophies_list}
- Head-to-head vs {away_manager_name}: {manager_h2h}

### {away_manager_name} ({away_team})
{symmetric structure}

## Club Context
### {home_team}
- Founded: {founded_year}
- Major Trophies: {trophy_count}
- League Titles: {league_titles}
- UCL Titles: {ucl_titles}
- Philosophy: {club_philosophy}
- Academy: {academy_reputation}

### {away_team}
{symmetric structure}

## Team News Caveats
### {home_team}
- Injuries: {home_injuries_formatted}
- Lineup Status: {home_lineup_status}
- Last-Minute Changes: {home_last_minute_changes}
- Press Conference Quotes: {home_press_conference_quotes}

### {away_team}
{symmetric structure}

## Player Cards
### {home_team} Key Players
{per_player_cards_home}  # 10 cards: name, position, age, stats, bio, story, pronunciation, source_url

### {away_team} Key Players
{per_player_cards_away}

## Transfer Watch
### {home_team} Transfers
- Recent Arrivals: {home_signings}
- Departures: {home_departures}
- Key Contract Situations: {home_contracts}
- Rumours (unconfirmed): {home_rumours}

### {away_team} Transfers
{symmetric structure}

## Broadcast Folder Pages
### Page 1: Match Overview & Lineups
{page_1_content}
### Page 2: {home_team} Deep-Dive
{page_2_content}
### Page 3: {away_team} Deep-Dive
{page_3_content}
### Page 4: Club Context & Staff
{page_4_content}
### Pages 5-6: Statistics & Historical Context
{page_5_6_content}

## Pronunciation
{phonetic_spellings_from_verified_sources}
- Confirm names from official broadcast / team media before adding.
- Do NOT guess pronunciation for players without an accepted source.

## Live Trigger Lines
{live_trigger_beats_formatted}

## Halftime And Postgame Angles
{halftime_postgame_angles}

## Source Provenance
{source_provenance_per_section}

## Retrieval Audit Report
### Per-Source Health (this run)
| Source | Tier | Calls | Good | Bad | Marginal | Avg Quality | Avg Duration |
|---|---|---|---|---|---|---|---|
{per_source_health_table}

### Top 5 Failures
{top_failure_details}

### Recommendations
- Prioritize: {recommended_sources}
- Avoid or cross-verify: {degraded_sources}
```

### 3.5 Retrieval Summary Builder

**What**: At the end of every run, produce a "Retrieval Audit Report" section showing exactly which data was good and which was bad.

```python
def build_retrieval_summary(run_id: str, ledger: RetrievalLedger) -> dict:
    """
    Query the ledger for this run and produce:
    - Per-source table: calls, good/bad/marginal counts, avg quality, avg duration
    - Top 5 failures with queries and error messages
    - Recommended sources to prioritize
    - Degraded sources to avoid or cross-verify
    """
    logs = ledger.get_run_logs(run_id)
    
    # Aggregate by source
    per_source = defaultdict(lambda: {"calls": 0, "good": 0, "bad": 0, "marginal": 0, "qualities": [], "durations": []})
    for log in logs:
        src = per_source[log.source_name]
        src["calls"] += 1
        if log.status == "success" and log.data_quality >= 0.6:
            src["good"] += 1
        elif log.status in {"empty", "error", "timeout", "blocked"} or log.data_completeness < 0.3:
            src["bad"] += 1
        else:
            src["marginal"] += 1
        src["qualities"].append(log.data_quality)
        src["durations"].append(log.duration_ms)
    
    # Build table rows
    source_table = []
    for src_name, stats in sorted(per_source.items(), key=lambda x: x[1]["bad"], reverse=True):
        source_table.append({
            "source": src_name,
            "tier": get_source_tier(src_name),
            "calls": stats["calls"],
            "good": stats["good"],
            "bad": stats["bad"],
            "marginal": stats["marginal"],
            "avg_quality": round(mean(stats["qualities"]), 2) if stats["qualities"] else 0,
            "avg_duration_ms": round(mean(stats["durations"])) if stats["durations"] else 0,
        })
    
    # Top failures
    failures = [log for log in logs if log.status in {"empty", "error", "timeout", "blocked", "rate_limited"}]
    top_failures = sorted(failures, key=lambda f: f.duration_ms, reverse=True)[:5]
    
    # Recommendations
    good_sources = [s["source"] for s in source_table if s["good"] >= s["calls"] * 0.7]
    bad_sources = [s["source"] for s in source_table if s["bad"] > s["calls"] * 0.5 or s["avg_quality"] < 0.3]
    
    return {
        "source_table": source_table,
        "top_failures": [
            {"source": f.source_name, "query": f.query_text[:100], "status": f.status, "error": f.error_message or "", "duration_ms": f.duration_ms}
            for f in top_failures
        ],
        "recommendations": {
            "prioritize": good_sources[:5],
            "avoid_or_verify": bad_sources[:5],
        },
        "total_fetches": len(logs),
        "good_rate": round(sum(1 for l in logs if l.data_quality >= 0.6) / max(1, len(logs)), 2),
        "total_duration_ms": sum(log.duration_ms for log in logs),
    }
```

### Deliverables — Phase 3

| File | Purpose |
|---|---|
| `workflows/commentary_notes_workflow.py` | LangGraph state machine with 10 nodes |
| `workflows/state.py` | `CommentaryNotesState` dataclass |
| `workflows/broadcast_dossier.py` | 6-page broadcast contract builder |
| `workflows/retrieval_summary.py` | Per-run audit report builder |
| `quality/evidence.py` | Evidence quality report, tier classification |
| `quality/fact_ledger.py` | Every claim → source_url tracking |
| `quality/notes_refinement.py` | Revision loop (2 passes max) |
| `models/notes_store.py` | `NotesStore` + `NarrativeBeat` dataclasses |
| `orchestration/__init__.py` | Workflow runner entry point |

### Success Criteria — Phase 3

- [x] LangGraph state machine runs all 13 agents
- [x] Phase 2b (6 new agents) runs concurrently in under 20 seconds
- [x] Exa gap-fill activates only when accepted evidence < 4
- [x] Retrieval Summary section appears in every output document
- [x] Per-source health table shows good/bad/marginal breakdown
- [x] Top 5 failures section shows what went wrong with which queries
- [x] Markdown output passes format completeness check
- [x] Revision loop fixes missing sections (up to 2 passes)
- [x] Fact ledger links every stat claim to a source URL

---

### ✅ Phase 3 — COMPLETE (2026-06-19)

**Implemented/Enhanced files:**

| File | Status | Notes |
|---|---|---|
| `workflows/retrieval_summary.py` | **CREATED** | `build_retrieval_summary()` — queries the SQLite ledger, produces per-source health table (good/bad/marginal counts, avg quality/duration), top 5 failures with queries/errors, prioritize/avoid recommendations. |
| `workflows/state.py` | **CREATED** | Standalone re-export of `CommentaryNotesState` + `WorkflowPhase` from the workflow module. |
| `workflows/commentary_notes_workflow.py` | **ENHANCED** | Added 7 new output fields to `CommentaryNotesState` (6 enrichment agents + `retrieval_summary`). Added `enrich_context` node running all 6 new agents in parallel via `asyncio.gather`. Updated `_build_all_outputs` to include enrichment fields. Expanded `_exa_query_routes` with 4 new routes (officials, venue_history, manager_context, transfer_context). Updated `_merge_targeted_evidence` to handle new routes. Integrated `build_retrieval_summary` into `synthesize_notes`. Added `enrich_context` to LangGraph graph. |
| `data_sources/tavily_search_service.py` | **ENHANCED** | Added `RetrievalLedger.log_fetch()` calls at all 4 paths (cache hit, unavailable, success, error). Uses `get_audit_run_id()` from contextvar for run_id. |
| `data_sources/exa_search_service.py` | **ENHANCED** | Added `RetrievalLedger.log_fetch()` calls at all 4 paths (cache hit, unavailable, success, error). Uses `get_audit_run_id()` from contextvar for run_id. |
| `data_sources/base.py` | **ENHANCED** | Imported `get_audit_run_id` from `retrieval_audit`. Added `run_id = run_id or get_audit_run_id()` fallback in `fetch()`. |
| `workflows/__init__.py` | **ENHANCED** | Exports `build_retrieval_summary` + `StateCommentaryNotesState`. |
| `orchestration/__init__.py` | **ENHANCED** | Exports `WorkflowOrchestrator`, `get_orchestrator`, `AgentType`, `WorkflowContext`, `WorkflowState`, `TaskResult`, `AgentMessage`. |
| `data_sources/retrieval_audit.py` | **REFERENCED** | `set_audit_run_id()` called at workflow init to bind all fetches to the same run_id. |

**Verification:**
- ruff: 0 errors on all Phase 3 files (32 pre-existing in legacy data_sources files, none from Phase 3)
- mypy: 0 errors from Phase 3 changes (5 pre-existing: tavily stubs missing, httpx None iterable)
- 97 existing tests pass, no regressions
- Full workflow test: Arsenal vs Chelsea → 13 agents completed, 29 beats, 16,737 char markdown, 2 ledger entries tracked
- Retrieval summary: 2 fetches tracked (tavily + exa), both with quality 0.8, good rate 1.0
- All 6 enrichment agents produce data (officials, venue_details, manager_profiles, club_history, transfers, pronunciation)
- LangGraph graph: 9 nodes (initialize → parallel_research → targeted_evidence_search → matchup_analysis → enrich_context → synthesize → evaluate_notes → revise_notes → evaluate_notes)

**Architecture note:** The `RetrievalLedger` SQLite DB is populated by `BaseRetriever.fetch()` template and now also by `TavilySearchService.search()` + `ExaSearchService.search()`. All web searches use `get_audit_run_id()` (set at workflow init via contextvar) to ensure consistent run_id across all fetches. The `retrieval_summary.py` queries the ledger by `run_id` (workflow_id) and produces the per-source health table, top failures, and recommendations.

---

## Phase 4: Quality & Observability Dashboard (Days 19-22)

### 4.1 Live Retrieval Audit Dashboard

**What**: A CLI + web dashboard that shows, for any run:
- Which sources returned good data and which were bad
- Total fetches, duration, quality scores
- Source health over time (across runs)
- Recommendations for future runs

**CLI command**:
```bash
python -m orchestration.audit --run-id <uuid>
# Output:
# ┌─ Retrieval Audit: Man United vs Arsenal ──────────────────────────┐
# │ Total Fetches: 48 │ Good: 32 │ Bad: 7 │ Marginal: 9 │ Duration: 42.3s │
# │───────────────────────────────────────────────────────────────────────│
# │ Source         │Tier│ Calls│Good│Bad│Marg│Avg Q│Avg ms│ Status     │
# │ espn           │  2 │   8  │  6 │  1 │  1  │ 0.82│  340 │ healthy   │
# │ football_data  │  1 │   4  │  4 │  0 │  0  │ 0.94│  210 │ healthy   │
# │ tavily         │  3 │   6  │  4 │  1 │  1  │ 0.71│  890 │ healthy   │
# │ goal_com      │  2 │   3  │  2 │  0 │  1  │ 0.78│ 1200 │ healthy   │
# │ rotowire      │  2 │   3  │  3 │  0 │  0  │ 0.85│  450 │ healthy   │
# │ brightdata    │  3 │   5  │  3 │  2 │  0  │ 0.62│ 2800 │ warning   │
# │ transfermarkt │  2 │   4  │  1 │  2 │  1  │ 0.45│ 1500 │ DEGRADED  │
# │ the_athletic  │  2 │   2  │  0 │  1 │  1  │ 0.35│ 3200 │ blocked   │
# │ jina_reader   │  3 │   2  │  2 │  0 │  0  │ 0.80│  180 │ healthy   │
# │ open_meteo    │  1 │   1  │  1 │  0 │  0  │ 0.98│  120 │ healthy   │
# │ ...                                                              │
# │───────────────────────────────────────────────────────────────────────│
# │ Top Failures:                                                     │
# │ 1. transfermarkt: "Squad page blocked by anti-bot (403)" 1.5s  │
# │ 2. brightdata: "MCP proxy timeout after 30s"            2.8s  │
# │ 3. the_athletic: "Paywall — couldn't extract article"   3.2s  │
# │ 4. espn: "Empty roster for this team"                   0.3s  │
# │ 5. who scored: "Rate limited (429)"                     0.2s  │
# │───────────────────────────────────────────────────────────────────────│
# │ Recommendations:                                                  │
# │ Prioritize: espn, football_data, open_meteo, rotowire, goal_com │
# │ Cross-verify: transfermarkt, brightdata (Tier 3 check needed)   │
# │ Avoid (degraded): the_athletic (paywall), who scored (rate limit)│
# └─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Web Dashboard (Optional)

A simple React component in the frontend that shows:
- **Live Run Progress**: which phase, which agents running, progress %
- **Retrieval Health**: real-time source status with colored indicators
- **Evidence Quality**: accepted/rejected counts with tier breakdown
- **Source Recommendations**: dynamic prioritization based on health

**API endpoint**: `GET /api/v1/commentary/audit/{job_id}` → JSON with full retrieval summary.

### 4.3 Source Health Monitoring (Background)

**What**: A background task that periodically health-checks all configured sources and updates the `SourceHealthRegistry`.

```python
class SourceHealthMonitor:
    """Every 5 minutes, ping all sources. Track degradation."""
    
    async def run_health_checks(self) -> dict[str, SourceHealth]:
        for source_name in DataSource:
            retriever = get_retriever(source_name.value)
            if not retriever:
                continue
            
            try:
                result = await retriever.health_check()
                if result:
                    self.registry.recover(source_name.value)
                else:
                    self.registry.record_failure(source_name.value)
            except Exception:
                self.registry.record_failure(source_name.value)
        
        return self.registry.get_all()
```

### Deliverables — Phase 4

| File | Purpose |
|---|---|
| `core/retrieval_ledger.py` (enhanced) | Queryable audit log + aggregation |
| `orchestration/audit.py` | CLI audit command + output formatting |
| `orchestration/health_monitor.py` | Background source health checks |
| `api/routes/audit.py` | `GET /api/v1/commentary/audit/{job_id}` |
| `frontend/src/components/RetrievalAuditDashboard.jsx` | Live retrieval health UI |
| `frontend/src/components/SourceHealthPanel.jsx` | Per-source status indicators |

### Success Criteria — Phase 4

- [ ] `python -m orchestration.audit --run-id <uuid>` produces readable audit table
- [ ] Every run's output document includes a "Retrieval Audit Report" section
- [ ] API endpoint returns per-source health + top failures + recommendations
- [ ] Frontend dashboard shows live source status during a run
- [ ] Source health monitor detects degradation and marks sources
- [ ] Degraded sources are automatically skipped by the round-robin router

---

## Phase 5: Integration & Production (Days 23-26)

### 5.1 API Endpoints

```python
# POST /api/v1/commentary/prepare-notes
# Body: {home_team, away_team, sport, competition?, match_datetime?, venue?}
# Returns: 202 Accepted with job_id + polling URLs
# Background: Celery task → LangGraph workflow → persists to DB → streams via Redis

# GET /api/v1/commentary/notes/{job_id}
# Returns: Completed markdown + NotesStore JSON + retrieval audit summary

# GET /api/v1/commentary/notes/{job_id}/events (SSE)
# Streams: Phase progress, agent completions, warnings, final result

# GET /api/v1/commentary/audit/{job_id}
# Returns: Full retrieval audit: per-source table, top failures, recommendations
```

### 5.2 WebSocket Integration

```python
# /ws/live — single state bus per session
# Client → Server messages:
#   init: {match_id, home_team, away_team}
#   settings_update: {language, commentary_style, ...}
#   match_event: {type: "goal" | "sub" | "card", description: "free text"}
#   query: {text: "What formation are they playing?"} → triggers QA agent

# Server → Client messages:
#   ready: {session_id, match_context}
#   commentary: {beat_type, text, source_urls}  # from NotesStore O(1) lookup
#   answer: {question, answer, source_urls}
#   status: {phase, progress_pct}
```

### 5.3 Background Job (Celery)

```python
@celery_app.task
def generate_commentary_notes(job_id: str):
    """Runs the full autonomous pipeline in background."""
    # 1. Load job from DB
    # 2. Build CommentaryNotesState
    # 3. Run LangGraph workflow
    # 4. Persist result to DB + Redis cache
    # 5. Build retrieval summary
    # 6. Emit completion event
```

### 5.4 Progress Streaming (SSE)

```python
async def stream_notes_progress(job_id: str):
    """SSE endpoint streaming phase progress."""
    # Subscribes to Redis pub/sub channel
    # Emits: {phase, message, agent_count, done, errors, warnings}
    # Final event: {done: True, retrieval_summary: {...}}
```

### Deliverables — Phase 5

| File | Purpose |
|---|---|
| `api/server.py` | FastAPI app (all endpoints) |
| `api/routes/commentary.py` | Commentary endpoints |
| `api/routes/audit.py` | Audit endpoint |
| `api/routes/ws.py` | WebSocket handlers |
| `jobs/notes_tasks.py` | Celery task |
| `models/job.py` | NotesJob ORM model |
| `orchestration/progress.py` | SSE progress emitter |
| `frontend/src/pages/CommentatorDashboard.jsx` | Full UI consuming API |

### Success Criteria — Phase 5

- [ ] `POST /api/v1/commentary/prepare-notes` returns 202 with job_id
- [ ] SSE endpoint streams real-time progress to frontend
- [ ] Completed notes include Retrieval Audit Report section
- [ ] WebSocket `/ws/live` retrieves beats from NotesStore by event tag
- [ ] Full end-to-end: 2 team names → 60 seconds → broadcast-ready markdown with audit trail
- [ ] Every run shows exactly which sources were good and which were bad

---

## File Map (Complete System)

```
PitchSideAI/
├── core/
│   ├── retrieval_ledger.py         # Every fetch logged: source, query, duration, status, quality
│   ├── data_cache.py              # TTL cache with namespace isolation
│   ├── source_health.py           # Per-source health registry, degradation tracking
│   ├── source_catalog.py          # Enum + tier mapping for 60+ sources
│   └── __init__.py
├── quality/
│   ├── response_scorer.py          # Deterministic (completeness, quality) scoring for raw responses
│   ├── evidence.py                # Evidence quality report, tier classification
│   ├── fact_ledger.py            # Every claim → source_url tracking
│   └── notes_refinement.py      # Revision loop (2 passes max)
├── data_sources/
│   ├── base.py                   # BaseRetriever ABC + FetchResult dataclass
│   ├── result.py                # FetchResult with is_good/is_bad/is_marginal
│   ├── rate_limiter.py         # Per-source async rate limiter
│   ├── round_robin_router.py   # Source priority routing with failover
│   ├── parallel_race_fetcher.py # Multi-source parallel race
│   ├── cache.py                 # DataCache instance
│   ├── retrieval_audit.py       # Audit decorator + logging
│   ├── factory.py               # get_retriever(sport), singleton management
│   ├── espn_retriever.py       # ESPN: squad, form, injuries, match context
│   ├── football_data_retriever.py  # FootballData.org: H2H, standings, fixtures
│   ├── transfermarkt_retriever.py  # Transfermarkt: market values, stats, transfers
│   ├── sofascore_retriever.py      # Sofascore: live stats, heatmaps
│   ├── fbref_retriever.py          # FBref: player season stats
│   ├── whoscored_retriever.py      # WhoScored: player ratings, team strengths
│   ├── eleven_v_eleven_retriever.py # 11v11.com: H2H records
│   ├── open_meteo_retriever.py     # Open-Meteo: weather forecast
│   ├── tavily_search_service.py     # Tavily: AI web search
│   ├── exa_search_service.py        # Exa: semantic search
│   ├── wikipedia_retriever.py       # Wikipedia: bio, history, stadium facts
│   ├── dbpedia_retriever.py       # DBpedia: SPARQL structured facts
│   ├── goal_com_retriever.py      # Goal.com: match previews, news
│   ├── rotowire_retriever.py      # Rotowire: lineups, injuries, start/sit
│   ├── brightdata_mcp_retriever.py # BrightData MCP: proxy scraping (5000 credits)
│   ├── firecrawl_retriever.py     # Firecrawl: URL → markdown
│   ├── jina_reader_retriever.py   # Jina AI: free URL reader
│   ├── forvo_retriever.py         # Forvo: pronunciation audio
│   ├── youglish_retriever.py      # YouGlish: name pronunciation in context
│   ├── sky_sports_retriever.py    # Sky Sports: team news, press conferences
│   ├── bbc_sport_retriever.py     # BBC Sport: match previews, gossip
│   ├── the_athletic_retriever.py  # The Athletic: deep tactical analysis
│   ├── sports_mole_retriever.py   # Sports Mole: predicted XIs, form guides
│   ├── one_football_retriever.py  # OneFootball: aggregated news
│   ├── fixture_resolver.py         # Match resolution: venue, datetime from web
│   ├── __init__.py
│   └── multi_source_retriever.py  # Load-balanced multi-source aggregator
├── agents/
│   ├── base.py                     # BaseAgent ABC: guardrail, LLM wrapper, ledger integration
│   ├── player_research_agent.py   # Squad + player bios (25 per team)
│   ├── team_form_agent.py         # Form analysis + comparison
│   ├── historical_context_agent.py # H2H + storylines
│   ├── weather_context_agent.py    # Weather + pitch conditions
│   ├── news_agent.py              # Injuries + team news + lineups
│   ├── matchup_analysis_agent.py   # 1v1 matchups + set pieces
│   ├── note_organizer_agent.py   # Final synthesis → markdown + NotesStore
│   ├── officials_agent.py         # **NEW**: referee appointments + profiles
│   ├── venue_details_agent.py    # **NEW**: stadium capacity, surface, history
│   ├── manager_profiles_agent.py # **NEW**: coach career + philosophy
│   ├── club_history_agent.py     # **NEW**: club trophies, philosophy, academy
│   ├── transfers_agent.py        # **NEW**: transfer window, contracts, rumours
│   ├── pronunciation_agent.py    # **NEW**: phonetic spellings from audio sources
│   ├── deep_notes_agent.py     # Optional: DeepAgents enrichment
│   ├── qa_agent.py             # Live Q&A for WebSocket
│   └── __init__.py
├── workflows/
│   ├── commentary_notes_workflow.py  # LangGraph state machine (13 agents, 10 nodes)
│   ├── state.py                     # CommentaryNotesState dataclass
│   ├── broadcast_dossier.py         # 6-page broadcast contract
│   ├── retrieval_summary.py         # Per-run audit report builder
│   └── __init__.py
├── models/
│   ├── notes_store.py              # NotesStore + NarrativeBeat dataclasses
│   ├── game_state.py              # Live match state tracker (WebSocket)
│   ├── job.py                    # NotesJob ORM for persistence
│   └── __init__.py
├── orchestration/
│   ├── audit.py                   # CLI: python -m orchestration.audit --run-id <uuid>
│   ├── health_monitor.py         # Background source health checks
│   ├── progress.py               # SSE progress emitter
│   └── __init__.py
├── api/
│   ├── server.py                 # FastAPI app (all endpoints)
│   ├── routes/
│   │   ├── commentary.py        # POST /api/v1/commentary/prepare-notes
│   │   ├── audit.py            # GET /api/v1/commentary/audit/{job_id}
│   │   ├── ws.py              # WebSocket /ws/live
│   │   └── __init__.py
│   └── __init__.py
├── config/
│   ├── settings.py              # Pydantic settings from .env
│   └── __init__.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── RetrievalAuditDashboard.jsx  # Live retrieval health UI
│   │   │   ├── SourceHealthPanel.jsx        # Per-source status indicators
│   │   │   └── ...
│   │   ├── pages/
│   │   │   ├── CommentatorDashboard.jsx      # Full UI: notes + audit
│   │   │   └── ...
│   │   └── ...
│   └── ...
├── tests/
│   ├── test_retrieval_ledger.py
│   ├── test_response_scorer.py
│   ├── test_source_health.py
│   ├── test_round_robin_router.py
│   ├── test_officials_agent.py
│   ├── test_venue_details_agent.py
│   ├── test_pronunciation_agent.py
│   └── ...
└── docs/
    ├── autonomous-commentary-architecture.md  # Architecture reference
    └── implementation-plan-with-audit.md      # This document
```