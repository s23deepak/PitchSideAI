from quality.evidence import build_evidence_quality_report, validate_scraped_content


def test_sunderland_chelsea_quality_gate_rejects_polluted_claims():
    outputs = {
        "home_team": "Sunderland",
        "away_team": "Chelsea",
        "news": {
            "home_team": {
                "team_name": "Sunderland",
                "news_items": [
                    {
                        "title": "Sunderland v Chelsea official preview",
                        "content": "Sunday May 24 2026, Stadium of Light.",
                        "url": "https://www.safc.com/news/team-news/sunderland-chelsea-preview",
                        "source": "SAFC",
                    }
                ],
                "injuries": [],
                "synthesis": "Sunderland official preview is available.",
                "lineup_status": {"status": "reported", "summary": ""},
                "brightdata_status": {"available": True, "degraded_count": 0},
            },
            "away_team": {
                "team_name": "Chelsea",
                "news_items": [
                    {
                        "title": "Chelsea vs Tottenham team news",
                        "content": "Chelsea and Tottenham injury latest.",
                        "url": "https://www.chelseafc.com/en/news/article/chelsea-vs-tottenham-team-news",
                        "source": "Chelsea",
                    },
                    {
                        "title": "NBA playoffs",
                        "content": "Knicks basketball result.",
                        "url": "https://www.espn.com/nba/story/_/id/1",
                        "source": "ESPN",
                    },
                ],
                "injuries": [],
                "synthesis": "Chelsea-Tottenham news should not survive.",
                "lineup_status": {"status": "reported", "summary": ""},
                "brightdata_status": {"available": False, "degraded_count": 0},
            },
        },
        "weather": {
            "data_source": "tavily_search",
            "current_conditions": {"temperature_c": 18},
            "forecast": [{"source_url": "https://example.com/weather"}],
            "narrative": "Generic unrelated weather.",
        },
        "historical": {
            "h2h_history": {
                "total_matches": 0,
                "team1_wins": 0,
                "team2_wins": 0,
                "draws": 0,
                "recent_matches": [],
            },
            "storylines": [
                {
                    "title": "Chelsea vs Tottenham tactical preview",
                    "description": "London derby preview.",
                    "source": "search",
                }
            ],
            "narrative": "0-0-0 first meeting.",
        },
    }

    report = build_evidence_quality_report(outputs, mutate=True)

    assert report["accepted_evidence_count"] == 1
    assert report["rejected_evidence_count"] >= 3
    assert outputs["news"]["home_team"]["news_items"][0]["source"] == "SAFC"
    assert outputs["news"]["away_team"]["news_items"] == []
    assert outputs["news"]["away_team"]["synthesis"] == ""
    assert outputs["weather"]["validation_status"] == "degraded"
    assert outputs["historical"]["h2h_history"]["status"] == "unavailable"
    assert outputs["historical"]["h2h_history"]["total_matches"] is None
    assert outputs["historical"]["storylines"] == []
    assert "Sunderland vs Chelsea verified H2H" in report["unavailable_facts"]


def test_scraped_content_validator_rejects_other_fixture_and_other_sport():
    assert validate_scraped_content(
        "Chelsea vs Tottenham team news",
        url="https://www.chelseafc.com/en/news/article/team-news",
        home_team="Sunderland",
        away_team="Chelsea",
    ) == ("rejected", "other_fixture")

    assert validate_scraped_content(
        "NBA and Knicks basketball updates",
        url="https://www.espn.com/soccer/story/_/id/1",
        home_team="Sunderland",
        away_team="Chelsea",
    ) == ("rejected", "other_sport")
