import json

import pytest

from agents.specialized_commentary.weather_context_agent import WeatherContextAgent
from data_sources.cache import DataCache
from data_sources.retrieval_audit import AuditedRetrieverProxy, get_audit_dir, set_audit_run_id
from data_sources.tavily_search_service import TavilySearchService
from data_sources.weather_retriever import WeatherDataRetriever


@pytest.mark.asyncio
async def test_tavily_disables_live_calls_after_plan_limit():
    class PlanLimitedClient:
        def __init__(self):
            self.calls = 0

        def search(self, **kwargs):
            self.calls += 1
            raise Exception("403 Forbidden: plan limit exceeded")

    client = PlanLimitedClient()
    service = TavilySearchService(api_key="test-key", cache=DataCache())
    service._client = client
    service._available = True

    first = await service.search("Panama vs England team news")
    second = await service.search("Panama vs England weather")

    assert first["source"] == "fallback"
    assert second["source"] == "fallback"
    assert client.calls == 1
    assert service.is_available is False
    assert service._unavailable_reason == "plan_or_quota_limit"


@pytest.mark.asyncio
async def test_weather_retriever_uses_open_meteo_fallback_when_tavily_unavailable(monkeypatch):
    class UnavailableSearch:
        is_available = False

    retriever = WeatherDataRetriever(cache=DataCache(), search_service=UnavailableSearch())

    async def fake_hourly(self, venue_name, latitude, longitude, match_datetime):
        return {
            "forecast_hours": [
                {
                    "time": "2026-06-20T18:00:00+00:00",
                    "temp_c": 18.4,
                    "humidity": 62,
                    "wind_kmh": 11.2,
                    "conditions": "partly_cloudy",
                    "summary": "partly_cloudy at 18:00 UTC",
                    "offset_seconds": -3600,
                },
                {
                    "time": "2026-06-20T19:00:00+00:00",
                    "temp_c": 17.9,
                    "humidity": 66,
                    "wind_kmh": 13.4,
                    "conditions": "cloudy",
                    "summary": "cloudy at 19:00 UTC",
                    "offset_seconds": 0,
                },
            ],
            "data_source": "open_meteo",
        }

    monkeypatch.setattr(WeatherDataRetriever, "_open_meteo_hourly", fake_hourly)

    weather = await retriever.get_match_day_weather(
        "Test Stadium",
        51.5,
        -0.12,
        "2026-06-20T19:00:00Z",
    )
    forecast = await retriever.get_forecast_trend(
        "Test Stadium",
        51.5,
        -0.12,
        "2026-06-20T19:00:00Z",
    )

    assert weather["data_source"] == "open_meteo"
    assert weather["temp_c"] == 17.9
    assert weather["conditions"] == "cloudy"
    assert forecast["data_source"] == "open_meteo"
    assert len(forecast["forecast_hours"]) == 2
    assert "wind 13.4 km/h peak" in forecast["general_trend"]


@pytest.mark.asyncio
async def test_weather_retriever_emits_concise_unavailable_without_coordinates():
    retriever = WeatherDataRetriever(cache=DataCache(), search_service=None)

    weather = await retriever.get_match_day_weather(
        "Unknown",
        0.0,
        0.0,
        "2026-06-20T19:00:00Z",
    )
    impact = await retriever.contextualize_weather(weather)

    assert weather["data_source"] == "unavailable"
    assert weather["weather_summary"] == ""
    assert impact["general"] == "Weather impact unavailable from accepted sources."


@pytest.mark.asyncio
async def test_weather_agent_uses_deterministic_unavailable_narrative(monkeypatch):
    async def fail_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called for unavailable weather")

    agent = WeatherContextAgent(sport="soccer")
    monkeypatch.setattr(agent, "call_llm", fail_llm)

    narrative = await agent._generate_weather_narrative(
        {"data_source": "unavailable"},
        {"data_source": "unavailable"},
        {"general": "Weather impact unavailable from accepted sources."},
    )

    assert narrative == "Weather details are unavailable from accepted sources for this fixture."


@pytest.mark.asyncio
async def test_audited_football_data_h2h_accepts_limit_without_proxy_error(tmp_path, monkeypatch):
    monkeypatch.setenv("RETRIEVAL_DEBUG_DUMP", "true")
    monkeypatch.setenv("RETRIEVAL_DEBUG_DIR", str(tmp_path))

    class DummyFootballData:
        is_available = True

        async def get_head_to_head(self, team1, team2, sport="soccer", limit=10):
            return {"team1": team1, "team2": team2, "limit": limit}

    set_audit_run_id("football-data-h2h-proxy-run")
    proxy = AuditedRetrieverProxy("football_data", DummyFootballData())

    result = await proxy.get_head_to_head("Panama", "England", limit=3)

    assert result["limit"] == 3
    events = [
        json.loads(line)
        for line in (get_audit_dir() / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(events) == 1
    assert events[0]["provider"] == "football_data"
    assert events[0]["method"] == "get_head_to_head"
    assert events[0]["error"] is None
