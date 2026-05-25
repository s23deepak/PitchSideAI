import pytest

from workflows.commentary_notes_workflow import CommentaryNotesState, CommentaryNotesWorkflow


@pytest.mark.asyncio
async def test_workflow_synthesis_refuses_rejected_evidence_and_reports_degradation(monkeypatch):
    monkeypatch.setenv("DEEP_NOTES_ENABLED", "false")
    workflow = CommentaryNotesWorkflow()
    state = CommentaryNotesState(
        match_id="golden-sunderland-chelsea",
        home_team="Sunderland",
        away_team="Chelsea",
        competition="Champions League Final",
        match_datetime="2026-05-24T16:00:00+01:00",
        venue="Stadium of Light",
        player_research={
            "home_team": {"team_name": "Sunderland", "players": [{"name": "Sunderland Player", "position": "MF"}]},
            "away_team": {"team_name": "Chelsea", "players": [{"name": "Chelsea Player", "position": "MF"}]},
        },
        team_form={"home_team": {}, "away_team": {}, "comparative_analysis": {}},
        team_news={
            "home_team": {
                "team_name": "Sunderland",
                "news_items": [
                    {
                        "title": "Sunderland v Chelsea official match preview",
                        "content": "Sunday May 24 2026, 4pm UK, Stadium of Light.",
                        "url": "https://www.safc.com/news/team-news/sunderland-chelsea-preview",
                        "source": "SAFC",
                    }
                ],
                "injuries": [],
                "synthesis": "Official preview confirms the fixture.",
                "lineup_status": {"status": "reported"},
                "brightdata_status": {"available": True, "degraded_count": 0},
            },
            "away_team": {
                "team_name": "Chelsea",
                "news_items": [
                    {
                        "title": "Chelsea vs Tottenham team news",
                        "content": "Tottenham angle should be rejected.",
                        "url": "https://www.chelseafc.com/en/news/article/chelsea-vs-tottenham-team-news",
                        "source": "Chelsea",
                    }
                ],
                "injuries": [],
                "synthesis": "Chelsea vs Tottenham team news.",
                "lineup_status": {"status": "reported"},
                "brightdata_status": {"available": False, "degraded_count": 0},
            },
            "critical_updates": [],
        },
        historical_context={
            "h2h_history": {"total_matches": 0, "team1_wins": 0, "team2_wins": 0, "draws": 0, "recent_matches": []},
            "storylines": [],
            "narrative": "0-0-0 first-ever meeting.",
        },
        weather_context={"data_source": "tavily_search", "current_conditions": {}, "forecast": [], "narrative": ""},
        matchup_analysis={},
    )

    completed = await workflow.synthesize_notes(state)

    markdown = completed.notes_store.raw_markdown
    assert "Champions League Final" in markdown
    assert "## Team News Caveats" in markdown
    assert "Chelsea vs Tottenham" not in markdown
    assert "Probable Starters" not in markdown
    assert "H2H Record: **Unavailable from trusted sources in this run**" in markdown
    assert "No verified Chelsea team-news update was accepted" in markdown
    assert "historical_h2h" in completed.quality_report["degraded_sections"]
    assert completed.quality_report["rejected_evidence_count"] >= 1
