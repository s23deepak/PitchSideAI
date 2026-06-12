import pytest

from data_sources.cache import DataCache
from data_sources.exa_search_service import ExaSearchService


@pytest.mark.asyncio
async def test_exa_search_uses_highlights_domain_filters_and_monthly_cache(monkeypatch):
    cache = DataCache(ttl_seconds=31 * 24 * 60 * 60)
    service = ExaSearchService(cache=cache, api_key="test-key")
    calls = []

    def fake_post(body):
        calls.append(body)
        return {
            "requestId": "req_1",
            "results": [{
                "title": "Korea Republic v Czechia team news",
                "url": "https://www.espn.com/soccer/story/team-news",
                "highlights": ["Son status requires confirmation."],
                "highlightScores": [0.88],
                "publishedDate": "2026-06-10T10:00:00Z",
            }],
        }

    monkeypatch.setattr(service, "_post_search", fake_post)

    first = await service.search(
        "Korea Republic Czechia team news",
        topic="team_news",
        include_domains=["espn.com"],
        start_published_date="2026-06-01T00:00:00Z",
    )
    second = await service.search(
        "Korea Republic Czechia team news",
        topic="team_news",
        include_domains=["espn.com"],
        start_published_date="2026-06-01T00:00:00Z",
    )

    assert len(calls) == 1
    assert calls[0]["type"] == "auto"
    assert calls[0]["contents"] == {"highlights": True}
    assert calls[0]["includeDomains"] == ["espn.com"]
    assert calls[0]["startPublishedDate"] == "2026-06-01T00:00:00Z"
    assert first["results"][0]["content"] == "Son status requires confirmation."
    assert second["source"] == "cache"


@pytest.mark.asyncio
async def test_exa_search_returns_empty_when_key_missing(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.delenv("EXA_API", raising=False)
    service = ExaSearchService(api_key="")

    result = await service.search("Arsenal PSG H2H", topic="h2h")

    assert result["results"] == []
    assert result["source"] == "unavailable"
