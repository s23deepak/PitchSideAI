"""
Enum + config map of every data source the system can use.
Agents reference this to declare their capabilities.
"""
from __future__ import annotations

from enum import Enum


class DataSource(str, Enum):
    # ── Structured APIs (Tier 1) ──
    ESPN = "espn"
    FOOTBALL_DATA = "football_data_org"
    SPORTMONKS = "sportmonks"
    ONE_VS_ONE = "one_versus_one"
    STATSBOMB = "statsbomb"
    PREMIER_LEAGUE_OFFICIAL = "premier_league"

    # ── Scraped Structured (Tier 2) ──
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

    # ── News/Editorial (Tier 2) ──
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

    # ── Web Search (Tier 3) ──
    TAVILY = "tavily"
    EXA = "exa"
    BRAVE_SEARCH = "brave"
    SERPAPI = "serpapi"

    # ── Content Extraction (Tier 3) ──
    FIRECRAWL = "firecrawl"
    BRIGHTDATA_MCP = "brightdata_mcp"
    JINA_READER = "jina"
    SCRAPINGBEE = "scrapingbee"
    DIFFBOT = "diffbot"

    # ── Knowledge (Tier 3) ──
    WIKIPEDIA = "wikipedia"
    DBPEDIA = "dbpedia"
    WIKIDATA = "wikidata"
    FORVO = "forvo"
    YOUGLISH = "youglish"

    # ── Weather (Tier 1) ──
    OPEN_METEO = "open_meteo"
    WEATHER_API = "weather_api"
    VISUAL_CROSSING = "visual_crossing"

    # ── LLM (Tier 4) — NOT data sources, generated content ──
    OPENAI_GPT = "openai"
    ANTHROPIC_CLAUDE = "anthropic"
    VLLM_QWEN = "vllm"
    DEEPSEEK = "deepseek"
    TOGETHER_AI = "together"
    GROQ = "groq"
    WAFER_NOVA = "wafer"


# Tier mapping: 1=official API, 2=scraped structured, 3=web search/LLM-extract, 4=LLM synthesis
SOURCE_TIERS: dict[DataSource, int] = {
    # Tier 1: Official APIs with structured data contracts
    DataSource.FOOTBALL_DATA: 1,
    DataSource.SPORTMONKS: 1,
    DataSource.STATSBOMB: 1,
    DataSource.PREMIER_LEAGUE_OFFICIAL: 1,
    DataSource.ONE_VS_ONE: 1,
    DataSource.OPEN_METEO: 1,
    DataSource.WEATHER_API: 1,
    DataSource.VISUAL_CROSSING: 1,

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

    # Tier 3: Web search / LLM-extracted (unstructured)
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
    DataSource.FORVO: 3,
    DataSource.YOUGLISH: 3,

    # Tier 4: LLM synthesis (generated content, not data)
    DataSource.OPENAI_GPT: 4,
    DataSource.ANTHROPIC_CLAUDE: 4,
    DataSource.VLLM_QWEN: 4,
    DataSource.DEEPSEEK: 4,
    DataSource.TOGETHER_AI: 4,
    DataSource.GROQ: 4,
    DataSource.WAFER_NOVA: 4,
}


def get_source_tier(source_name: str) -> int:
    """Look up tier for a source by name string."""
    try:
        ds = DataSource(source_name.lower().replace("-", "_").replace(" ", "_"))
        return SOURCE_TIERS.get(ds, 3)
    except ValueError:
        # Try fuzzy match for common aliases
        aliases = {
            "espn": DataSource.ESPN,
            "football_data": DataSource.FOOTBALL_DATA,
            "football-data.org": DataSource.FOOTBALL_DATA,
            "statsbomb": DataSource.STATSBOMB,
            "transfermarkt": DataSource.TRANSFERMARKT,
            "sofascore": DataSource.SOFASCORE,
            "fbref": DataSource.FBREF,
            "whoscored": DataSource.WHOSCORED,
            "11v11": DataSource.ELEVEN_V_ELEVEN,
            "fotmob": DataSource.FOTMOB,
            "open-meteo": DataSource.OPEN_METEO,
            "tavily": DataSource.TAVILY,
            "exa": DataSource.EXA,
            "wikipedia": DataSource.WIKIPEDIA,
            "dbpedia": DataSource.DBPEDIA,
            "wikidata": DataSource.WIKIDATA,
            "firecrawl": DataSource.FIRECRAWL,
            "brightdata": DataSource.BRIGHTDATA_MCP,
            "jina": DataSource.JINA_READER,
            "goal.com": DataSource.GOAL_COM,
            "rotowire": DataSource.ROTOWIRE,
            "sky_sports": DataSource.SKY_SPORTS,
            "bbc_sport": DataSource.BBC_SPORT,
            "the_athletic": DataSource.THE_ATHLETIC,
            "sports_mole": DataSource.SPORTS_MOLE,
            "onefootball": DataSource.ONE_FOOTBALL,
            "forvo": DataSource.FORVO,
            "youglish": DataSource.YOUGLISH,
            "openai": DataSource.OPENAI_GPT,
            "vllm": DataSource.VLLM_QWEN,
            "deepseek": DataSource.DEEPSEEK,
            "wafer": DataSource.WAFER_NOVA,
            "groq": DataSource.GROQ,
            "together": DataSource.TOGETHER_AI,
        }
        match: DataSource | None = aliases.get(source_name.lower())
        if match is not None:
            return SOURCE_TIERS.get(match, 3)
        return 3


def get_source_enum(source_name: str) -> DataSource | None:
    """Resolve a source name string to its DataSource enum member."""
    try:
        return DataSource(source_name.lower().replace("-", "_").replace(" ", "_"))
    except ValueError:
        aliases = {
            "espn": DataSource.ESPN,
            "football_data": DataSource.FOOTBALL_DATA,
            "football-data.org": DataSource.FOOTBALL_DATA,
            "statsbomb": DataSource.STATSBOMB,
            "transfermarkt": DataSource.TRANSFERMARKT,
            "sofascore": DataSource.SOFASCORE,
            "fbref": DataSource.FBREF,
            "whoscored": DataSource.WHOSCORED,
            "11v11": DataSource.ELEVEN_V_ELEVEN,
            "fotmob": DataSource.FOTMOB,
            "open-meteo": DataSource.OPEN_METEO,
            "tavily": DataSource.TAVILY,
            "exa": DataSource.EXA,
            "wikipedia": DataSource.WIKIPEDIA,
            "dbpedia": DataSource.DBPEDIA,
            "wikidata": DataSource.WIKIDATA,
            "firecrawl": DataSource.FIRECRAWL,
            "brightdata": DataSource.BRIGHTDATA_MCP,
            "jina": DataSource.JINA_READER,
            "goal.com": DataSource.GOAL_COM,
            "rotowire": DataSource.ROTOWIRE,
            "sky_sports": DataSource.SKY_SPORTS,
            "bbc_sport": DataSource.BBC_SPORT,
            "the_athletic": DataSource.THE_ATHLETIC,
            "sports_mole": DataSource.SPORTS_MOLE,
            "onefootball": DataSource.ONE_FOOTBALL,
            "forvo": DataSource.FORVO,
            "youglish": DataSource.YOUGLISH,
            "openai": DataSource.OPENAI_GPT,
            "vllm": DataSource.VLLM_QWEN,
            "deepseek": DataSource.DEEPSEEK,
            "wafer": DataSource.WAFER_NOVA,
            "groq": DataSource.GROQ,
            "together": DataSource.TOGETHER_AI,
        }
        return aliases.get(source_name.lower())