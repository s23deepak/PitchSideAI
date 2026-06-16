import pytest

from workflows.commentary_notes_workflow import CommentaryNotesState, create_workflow


class FakeRetriever:
    async def get_match_context(self, team_name, sport):
        return {"date": "2026-05-10T19:00:00Z", "venue": "Test Stadium"}


@pytest.mark.asyncio
async def test_commentary_notes_workflow_end_to_end_fast_path(monkeypatch):
    """Exercise the full notes workflow with external APIs and LLMs mocked."""
    from data_sources import factory
    from agents.specialized_commentary.news_agent import NewsAgent
    from agents.specialized_commentary.weather_context_agent import WeatherContextAgent
    from agents.specialized_commentary.historical_context_agent import HistoricalContextAgent
    from agents.specialized_commentary.player_research_agent import PlayerResearchAgent
    from agents.specialized_commentary.team_form_agent import TeamFormAgent
    from agents.specialized_commentary.matchup_analysis_agent import MatchupAnalysisAgent

    monkeypatch.setattr(factory, "get_retriever", lambda sport, cache=None: FakeRetriever())

    class FakeExaSearch:
        is_available = True

        async def search(self, query, **kwargs):
            if kwargs.get("topic") != "fixture":
                return {"source": "exa", "results": [], "query": query}
            return {
                "source": "exa",
                "results": [{
                    "title": "Home FC vs Away FC Champions League Final fixture guide",
                    "content": (
                        "Home FC vs Away FC Champions League Final kicks off at Test Stadium "
                        "on Sunday, May 10, 2026 at 19:00 UTC."
                    ),
                    "url": "https://www.espn.com/soccer/story/exa-fixture-guide",
                    "source": "exa",
                    "score": 0.9,
                }],
                "query": query,
            }

    monkeypatch.setattr(factory, "get_exa_search_service", lambda cache=None: FakeExaSearch())

    async def fake_news(self, home_team, away_team):
        return {
            "home_team": {"synthesis": f"{home_team} news clear", "news_items": [], "injuries": []},
            "away_team": {"synthesis": f"{away_team} news clear", "news_items": [], "injuries": []},
            "critical_updates": ["No critical updates"],
        }

    async def fake_weather(self, venue, latitude, longitude, match_datetime):
        return {
            "current_conditions": {"temperature_c": 20, "conditions": "clear", "wind_kmh": 4},
            "forecast": [],
            "sport_impact": {"general": "Calm conditions favor technical football"},
            "narrative": "Clear skies should keep the tempo crisp.",
        }

    async def fake_historical(self, home_team, away_team):
        return {
            "h2h_history": {"team1_wins": 1, "team2_wins": 1, "draws": 1, "recent_matches": []},
            "storylines": [{"title": "Balanced rivalry", "description": "Even recent meetings"}],
            "narrative": "This fixture has usually balanced control with sudden shifts.",
        }

    async def fake_players(self, home_team, away_team, fixture_context=None):
        def player(name, position, team):
            return {
                "name": name,
                "position": position,
                "team": team,
                "stats": {"goals": 3, "assists": 2, "appearances": 10},
                "profile": f"{name} offers a verified attacking cue.",
            }

        return {
            "home_team": {"team_name": home_team, "players": [player("Home Forward", "ST", home_team)]},
            "away_team": {"team_name": away_team, "players": [player("Away Defender", "CB", away_team)]},
        }

    async def fake_form(self, home_team, away_team):
        return {
            "home_team": {
                "team_name": home_team,
                "recent_form": {"record": {"wins": 2, "draws": 2, "losses": 1}},
                "comprehensive_analysis": f"{home_team} arrive stable and compact.",
            },
            "away_team": {
                "team_name": away_team,
                "recent_form": {"record": {"wins": 3, "draws": 1, "losses": 1}},
                "comprehensive_analysis": f"{away_team} carry strong transition momentum.",
            },
            "comparative_analysis": {"comparative_assessment": "The away side have a slight form edge."},
        }

    async def fake_matchups(self, home_lineup, away_lineup):
        return {
            "critical_matchups": [{
                "player1": "Home Forward",
                "player2": "Away Defender",
                "analysis": "A direct duel between depth runs and recovery defending.",
            }],
            "positional_strength": {},
            "weak_points": {"home_vulnerabilities": [], "away_vulnerabilities": []},
            "tactical_implications": "Expect the central duel to shape the match rhythm.",
        }

    monkeypatch.setattr(NewsAgent, "gather_match_news", fake_news)
    monkeypatch.setattr(WeatherContextAgent, "analyze_match_weather", fake_weather)
    monkeypatch.setattr(HistoricalContextAgent, "build_match_narrative", fake_historical)
    monkeypatch.setattr(PlayerResearchAgent, "research_squad_pair", fake_players)
    monkeypatch.setattr(TeamFormAgent, "analyze_both_teams", fake_form)
    monkeypatch.setattr(MatchupAnalysisAgent, "analyze_key_matchups", fake_matchups)

    progress = []

    async def on_progress(phase, message, extra):
        progress.append((phase, message, extra))

    state = CommentaryNotesState(
        match_id="home_away",
        home_team="Home FC",
        away_team="Away FC",
        sport="soccer",
        competition="Champions League Final",
    )

    result = await create_workflow().run_workflow(state, on_progress=on_progress)

    assert result.markdown_notes
    assert "Champions League Final" in result.markdown_notes
    assert "## Match Frame" in result.markdown_notes
    assert "## Tactical Dossier" in result.markdown_notes
    assert "## Live Trigger Lines" in result.markdown_notes
    assert "professional_score" in result.quality_report["notes_metrics"]
    assert result.notes_store is not None
    assert len(result.notes_store.beats) >= 3
    assert result.targeted_evidence["results_by_topic"]["fixture"][0]["url"] == (
        "https://www.espn.com/soccer/story/exa-fixture-guide"
    )
    assert any(
        "https://www.espn.com/soccer/story/exa-fixture-guide" in getattr(beat, "source_urls", [])
        for beat in result.notes_store.beats
    )
    assert "team_form" in result.completed_agents
    assert "matchup_analysis" in result.completed_agents
    assert any(phase == "parallel_phase" for phase, _message, _extra in progress)
    assert any(phase == "matchup_analysis" for phase, _message, _extra in progress)
