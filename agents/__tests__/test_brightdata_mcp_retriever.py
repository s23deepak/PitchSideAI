from data_sources.brightdata_mcp_retriever import (
    BrightDataMcpRetriever,
    build_brightdata_mcp_url,
    redact_brightdata_mcp_url,
)
from quality.evidence import filter_allowed_search_results


def test_brightdata_mcp_endpoint_construction_redacts_token():
    url = build_brightdata_mcp_url(
        "secret-token",
        base_url="https://mcp.brightdata.com/mcp",
        groups="advanced_scraping",
    )

    assert url == "https://mcp.brightdata.com/mcp?token=secret-token&groups=advanced_scraping"
    assert "secret-token" not in redact_brightdata_mcp_url(url)
    assert "token=[REDACTED]" in redact_brightdata_mcp_url(url)


def test_brightdata_retriever_reports_missing_token_without_leakage():
    retriever = BrightDataMcpRetriever(token="")

    assert retriever.is_available is False
    assert "token=" not in retriever.redacted_endpoint


def test_domain_allowlist_and_candidate_filtering_rejects_pollution():
    accepted, rejected = filter_allowed_search_results(
        [
            {
                "title": "Sunderland v Chelsea preview",
                "content": "Premier League fixture preview for Sunderland and Chelsea at Stadium of Light.",
                "url": "https://www.premierleague.com/match/12345",
                "source": "Premier League",
            },
            {
                "title": "Chelsea vs Tottenham team news",
                "content": "Chelsea face Tottenham in a London derby.",
                "url": "https://www.chelseafc.com/en/news/article/team-news-chelsea-tottenham",
                "source": "Chelsea",
            },
            {
                "title": "NBA playoffs latest",
                "content": "Knicks basketball result.",
                "url": "https://www.espn.com/nba/story/_/id/1",
                "source": "ESPN",
            },
            {
                "title": "Predicted lineups",
                "content": "Generic stale lineup page.",
                "url": "https://example.com/lineups",
                "source": "Example",
            },
        ],
        home_team="Sunderland",
        away_team="Chelsea",
        topic="team_news",
        max_results=3,
    )

    assert [item["url"] for item in accepted] == ["https://www.premierleague.com/match/12345"]
    reasons = {item.reason for item in rejected}
    assert {"other_fixture", "other_sport", "domain_not_allowed"} <= reasons
