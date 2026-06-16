import asyncio

import pytest

from agents.base import (
    COMMENTARY_NOTES_WAFER_CONCURRENCY_ENV,
    _COMMENTARY_NOTES_WAFER_SEMAPHORES,
    _get_commentary_notes_wafer_semaphore,
)
from agents.specialized_commentary.matchup_analysis_agent import MatchupAnalysisAgent
from agents.specialized_commentary.news_agent import NewsAgent
from agents.specialized_commentary.note_organizer_agent import CommentaryNoteOrganizerAgent
from agents.specialized_commentary.player_research_agent import PlayerResearchAgent
from agents.specialized_commentary.team_form_agent import TeamFormAgent
from data_sources.espn_retriever import ESPNDataRetriever, _get_serie_a_slug
from data_sources.football_data_retriever import FootballDataRetriever
from data_sources.fixture_resolver import FixtureResolver
from quality.evidence import build_evidence_quality_report, filter_allowed_search_results, validate_search_result
from workflows.commentary_notes_workflow import CommentaryNotesState, CommentaryNotesWorkflow


def test_team_news_rejects_team_adjacent_headline_without_fixture_or_news_context():
    item = {
        "title": "Chelsea injury latest before Tottenham trip",
        "content": "Chelsea team news for a different fixture.",
        "url": "https://www.espn.com/soccer/story/_/id/1/chelsea-headlines",
        "source": "ESPN",
    }

    status, reason = validate_search_result(
        item,
        home_team="Chelsea",
        away_team="Sunderland",
        topic="team_news",
    )

    assert status == "rejected"
    assert reason == "other_fixture_context"


def test_trusted_media_team_news_is_accepted_but_official_sources_rank_first():
    accepted, rejected = filter_allowed_search_results(
        [
            {
                "title": "BBC preview: Arsenal v PSG team news",
                "content": "Arsenal and PSG team news before the Champions League final.",
                "url": "https://www.bbc.co.uk/sport/football/articles/arsenal-psg-team-news",
                "source": "BBC Sport",
                "score": 0.99,
            },
            {
                "title": "UEFA Paris vs Arsenal final facts",
                "content": "Paris and Arsenal meet in the Champions League final.",
                "url": "https://www.uefa.com/uefachampionsleague/news/facts",
                "source": "UEFA",
                "score": 0.5,
            },
        ],
        home_team="Arsenal",
        away_team="Paris Saint-Germain",
        topic="team_news",
        max_results=2,
    )

    assert rejected == []
    assert [item["source_tier"] for item in accepted] == ["official", "trusted_media"]


def test_source_policy_accepts_lineup_media_and_rejects_other_sports_noise():
    accepted, rejected = filter_allowed_search_results(
        [
            {
                "title": "PSG vs Arsenal predicted lineups, team news",
                "content": "Arsenal predicted lineup and PSG predicted lineup for the Champions League final.",
                "url": "https://www.nbcsports.com/soccer/news/psg-vs-arsenal-predicted-lineups-team-news-analysis-for-epic-champions-league-final",
                "score": 0.9,
            },
            {
                "title": "F1: Lewis Hamilton hunts down Max Verstappen at Canadian GP",
                "content": "Arsenal video playlist item mixed into a Sky page.",
                "url": "https://www.skysports.com/f1/video/30998/hamilton-verstappen-canadian-gp",
                "score": 0.95,
            },
        ],
        home_team="Arsenal",
        away_team="Paris Saint-Germain",
        topic="lineup",
        max_results=2,
    )

    assert accepted[0]["source_tier"] == "trusted_media"
    assert accepted[0]["url"].startswith("https://www.nbcsports.com/")
    assert rejected[0].reason == "other_sport"


def test_news_agent_extracts_match_level_predicted_lineups():
    agent = NewsAgent(sport="soccer", search_service=None)
    text = (
        "PSG vs Arsenal predicted lineups, team news, analysis for epic Champions League final. "
        "## Arsenal predicted lineup ——- Raya ——- —— Timber —- Saliba —- Gabriel —- Calafiori —- "
        "—— Odegaard —- Rice —- Eze —— —— Saka —— Havertz —— Trossard —— [...] "
        "## PSG predicted lineup —— Safonov ——- —- Hakimi —- Marquinhos —- Pacho —— Mendes —— "
        "—— Neves —- Ruiz —- Vitinha —— —— Doue —- Dembele —- Kvaratskhelia —— [...]"
    )

    assert agent._extract_predicted_lineup_block(text, ["Arsenal"]) == [
        "Raya",
        "Timber",
        "Saliba",
        "Gabriel",
        "Calafiori",
        "Odegaard",
        "Rice",
        "Eze",
        "Saka",
        "Havertz",
        "Trossard",
    ]
    assert agent._extract_predicted_lineup_block(text, ["PSG"]) == [
        "Safonov",
        "Hakimi",
        "Marquinhos",
        "Pacho",
        "Mendes",
        "Neves",
        "Ruiz",
        "Vitinha",
        "Doue",
        "Dembele",
        "Kvaratskhelia",
    ]


def test_news_agent_strips_lineup_labels_and_structures_positions():
    agent = NewsAgent(sport="soccer", search_service=None)
    segment = (
        "Predicted XI | GK Courtois | RBCastagne | CB Vertonghen | LB Theate | "
        "CM De Bruyne | AM Trossard | RW Doku | ST Lukaku | FW Openda | "
        "Midfielder Onana | Winger Bakayoko"
    )

    entries = agent._lineup_entries_from_segment(segment)

    assert [entry["name"] for entry in entries] == [
        "Courtois",
        "Castagne",
        "Vertonghen",
        "Theate",
        "De Bruyne",
        "Trossard",
        "Doku",
        "Lukaku",
        "Openda",
        "Onana",
        "Bakayoko",
    ]
    assert entries[0] == {"name": "Courtois", "position": "GK"}
    assert entries[1] == {"name": "Castagne", "position": "RB"}
    assert "Predicted XI" not in [entry["name"] for entry in entries]


def test_commentary_notes_wafer_semaphore_is_loop_local(monkeypatch):
    monkeypatch.setenv(COMMENTARY_NOTES_WAFER_CONCURRENCY_ENV, "1")
    _COMMENTARY_NOTES_WAFER_SEMAPHORES.clear()

    async def get_semaphore():
        return _get_commentary_notes_wafer_semaphore()

    first = asyncio.run(get_semaphore())
    second = asyncio.run(get_semaphore())

    assert first is not second


def test_football_data_semaphore_is_loop_local():
    retriever = FootballDataRetriever(api_key="token")

    async def get_semaphore():
        return retriever._get_semaphore()

    first = asyncio.run(get_semaphore())
    second = asyncio.run(get_semaphore())

    assert first is not second


@pytest.mark.asyncio
async def test_espn_resolves_psg_against_ligue_1_slug(monkeypatch):
    retriever = ESPNDataRetriever()
    calls = []

    async def fake_get(url, params=None):
        calls.append(url)
        return {
            "sports": [{
                "leagues": [{
                    "teams": [{
                        "team": {"id": "160", "displayName": "Paris Saint-Germain"}
                    }]
                }]
            }]
        }

    monkeypatch.setattr(retriever, "_get", fake_get)

    assert _get_serie_a_slug("Paris Saint-Germain") == "fra.1"
    assert await retriever._resolve_team_id("Paris Saint-Germain", "soccer", "fra.1") == "160"
    assert calls == []


@pytest.mark.asyncio
async def test_espn_resolves_croatia_belgium_against_world_slug(monkeypatch):
    retriever = ESPNDataRetriever()
    calls = []

    async def fake_get(url, params=None):
        calls.append(url)
        return {}

    monkeypatch.setattr(retriever, "_get", fake_get)

    assert _get_serie_a_slug("Croatia") == "fifa.world"
    assert _get_serie_a_slug("Belgium") == "fifa.world"
    assert await retriever._resolve_team_id("Croatia", "soccer", "fifa.world") == "477"
    assert await retriever._resolve_team_id("Belgium", "soccer", "fifa.world") == "459"
    assert calls == []


@pytest.mark.asyncio
async def test_espn_resolves_usa_paraguay_against_world_slug(monkeypatch):
    retriever = ESPNDataRetriever()
    calls = []

    async def fake_get(url, params=None):
        calls.append(url)
        return {}

    monkeypatch.setattr(retriever, "_get", fake_get)

    assert _get_serie_a_slug("USA") == "fifa.world"
    assert _get_serie_a_slug("United States") == "fifa.world"
    assert _get_serie_a_slug("Paraguay") == "fifa.world"
    assert await retriever._resolve_team_id("USA", "soccer", "fifa.world") == "660"
    assert await retriever._resolve_team_id("United States", "soccer", "fifa.world") == "660"
    assert await retriever._resolve_team_id("Paraguay", "soccer", "fifa.world") == "210"
    assert calls == []


def test_evidence_gate_clears_synthesis_when_news_inputs_were_rejected():
    outputs = {
        "home_team": "Sunderland",
        "away_team": "Chelsea",
        "news": {
            "home_team": {
                "news_items": [{
                    "title": "Sunderland vs Chelsea team news",
                    "content": "Official match preview.",
                    "url": "https://www.safc.com/news/team-news/sunderland-chelsea",
                    "source": "SAFC",
                }],
                "injuries": [],
                "synthesis": "Official match preview.",
            },
            "away_team": {
                "news_items": [{
                    "title": "Chelsea academy headlines before Tottenham trip",
                    "content": "Chelsea-adjacent news, but not this fixture.",
                    "url": "https://www.espn.com/soccer/story/_/id/1/chelsea-headlines",
                    "source": "ESPN",
                }],
                "injuries": [],
                "synthesis": "Chelsea academy headlines before Tottenham trip.",
            },
        },
    }

    report = build_evidence_quality_report(outputs, mutate=True)

    assert report["rejected_evidence_count"] == 1
    assert outputs["news"]["away_team"]["synthesis"] == ""
    assert outputs["news"]["away_team"]["validation_status"] == "degraded"


@pytest.mark.asyncio
async def test_news_agent_filters_polluted_espn_headlines_before_llm(monkeypatch):
    captured_prompts = []
    agent = NewsAgent(sport="soccer", search_service=None)

    class FakeRetriever:
        async def get_team_news(self, team_name, sport):
            return [
                {
                    "headline": "Arsenal vs Paris Saint-Germain team news",
                    "description": "Fixture-specific team news.",
                    "url": "https://www.espn.com/soccer/story/_/id/1/arsenal-psg-team-news",
                },
                {
                    "headline": "Arsenal Premier League headlines before Chelsea trip",
                    "description": "Arsenal-adjacent, unrelated item.",
                    "url": "https://www.espn.com/soccer/story/_/id/2/arsenal-chelsea-headlines",
                },
            ]

        async def get_injuries(self, team_name, sport):
            return []

    async def fake_call_llm(prompt, **kwargs):
        captured_prompts.append(prompt)
        return "Arsenal vs Paris Saint-Germain team news is the accepted source."

    agent.retriever = FakeRetriever()
    monkeypatch.setattr(agent, "call_llm", fake_call_llm)

    result = await agent.get_team_news("Arsenal", opponent="Paris Saint-Germain")

    assert len(result["news_items"]) == 1
    assert "Paris Saint-Germain team news" in captured_prompts[0]
    assert "Premier League headlines before Chelsea trip" not in captured_prompts[0]
    assert agent._format_injuries([]) == "Not verified in this run"


@pytest.mark.asyncio
async def test_team_form_missing_data_stays_unavailable_and_skips_llm():
    agent = TeamFormAgent(sport="soccer", football_data_retriever=None)

    class FakeRetriever:
        async def get_recent_form(self, team_name, sport, num_games=5):
            return {}

    async def fail_call_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called for empty form data")

    agent.retriever = FakeRetriever()
    agent.football_data = None
    agent.call_llm = fail_call_llm

    result = await agent.analyze_team_form("Paris Saint-Germain")

    assert result["data_status"] == "unavailable"
    assert result["recent_form"]["record"] == {"wins": None, "draws": None, "losses": None}
    assert result["recent_form"]["goals_for"] is None
    assert result["recent_form"]["goals_against"] is None


@pytest.mark.asyncio
async def test_player_research_rejects_mock_squad_placeholders(monkeypatch):
    agent = PlayerResearchAgent(sport="soccer")

    class FakeRetriever:
        async def get_team_squad(self, team_name, sport):
            return {
                "team": team_name,
                "players": [
                    {"name": f"{team_name} Player {i}", "position": "Midfielder"}
                    for i in range(1, 6)
                ],
            }

    agent.retriever = FakeRetriever()

    result = await agent.research_squad("Paris Saint-Germain")

    assert result["players"] == []
    assert result["data_status"] == "unavailable"


@pytest.mark.asyncio
async def test_player_research_uses_fixture_candidates_when_retriever_mock_filtered(monkeypatch):
    agent = PlayerResearchAgent(sport="soccer")

    class FakeRetriever:
        async def get_team_squad(self, team_name, sport):
            return {
                "team": team_name,
                "players": [{"name": f"{team_name} Player 1", "position": "Midfielder"}],
            }

    agent.retriever = FakeRetriever()

    result = await agent.research_squad(
        "Club Alpha",
        fixture_players=[{
            "name": "Alex Rivera",
            "position": "Forward",
            "profile": "Club Alpha forward Alex Rivera is named in the official preview.",
            "source_urls": ["https://example.com/preview"],
            "data_source": "fixture_resolver",
        }],
    )

    assert result["data_status"] == "accepted"
    assert result["players"][0]["name"] == "Alex Rivera"
    assert result["players"][0]["candidate_status"] == "fixture-evidence; not confirmed starter"


@pytest.mark.asyncio
async def test_player_research_rejects_ambiguous_fixture_surname_fragment(monkeypatch):
    agent = PlayerResearchAgent(sport="soccer")

    class FakeRetriever:
        async def get_team_squad(self, team_name, sport):
            return {
                "team": team_name,
                "players": [{"name": f"{team_name} Player 1", "position": "Midfielder"}],
            }

    agent.retriever = FakeRetriever()

    result = await agent.research_squad(
        "Egypt",
        fixture_players=[
            {
                "name": "De Bruyne",
                "position": "Midfielder",
                "profile": "The Egyptian King has come out on top in prior meetings with De Bruyne.",
                "data_source": "fixture_resolver",
            },
            {
                "name": "Mo Salah",
                "position": "Forward",
                "profile": 'I know all about Mo Salah as I coached him at Roma." Salah remains the focal point.',
                "data_source": "fixture_resolver",
            },
        ],
    )

    names = [player["name"] for player in result["players"]]
    assert "De Bruyne" not in names
    assert "Mo Salah" in names
    assert "as I coached" not in result["players"][0]["profile"]


@pytest.mark.asyncio
async def test_matchup_analysis_catches_away_attackers_against_home_defenders(monkeypatch):
    agent = MatchupAnalysisAgent(sport="soccer", fbref_retriever=None)

    async def fake_matchup(player1, player2):
        return {
            "player1": player1["name"],
            "player2": player2["name"],
            "analysis": "Wide runner against fullback cover.",
        }

    async def fake_implications(matchups, weak_points):
        return ""

    monkeypatch.setattr(agent, "_analyze_player_matchup", fake_matchup)
    monkeypatch.setattr(agent, "_generate_tactical_implications", fake_implications)

    result = await agent.analyze_key_matchups(
        home_lineup=[{"name": "Home Fullback", "position": "LB"}],
        away_lineup=[{"name": "Away Winger", "position": "RW"}],
    )

    assert result["validation_status"] == "accepted"
    assert result["critical_matchups"] == [{
        "player1": "Away Winger",
        "player2": "Home Fullback",
        "analysis": "Wide runner against fullback cover.",
    }]


@pytest.mark.asyncio
async def test_matchup_analysis_rejects_placeholder_players(monkeypatch):
    agent = MatchupAnalysisAgent(sport="soccer", fbref_retriever=None)

    async def fail_matchup(*args, **kwargs):
        raise AssertionError("placeholder players should not be analyzed")

    async def fake_implications(matchups, weak_points):
        return ""

    monkeypatch.setattr(agent, "_analyze_player_matchup", fail_matchup)
    monkeypatch.setattr(agent, "_generate_tactical_implications", fake_implications)

    result = await agent.analyze_key_matchups(
        home_lineup=[{"name": "Arsenal Player 1", "position": "CM"}],
        away_lineup=[{"name": "Paris Saint-Germain Player 1", "position": "CM"}],
    )

    assert result["validation_status"] == "degraded"
    assert result["critical_matchups"] == []


@pytest.mark.asyncio
async def test_matchup_analysis_builds_candidate_duel_when_positions_unknown(monkeypatch):
    agent = MatchupAnalysisAgent(sport="soccer", fbref_retriever=None)

    async def fake_implications(matchups, weak_points):
        return ""

    monkeypatch.setattr(agent, "_generate_tactical_implications", fake_implications)

    result = await agent.analyze_key_matchups(
        home_lineup=[{"name": "Alex Rivera", "position": "Unknown", "source_urls": ["https://example.com/a"]}],
        away_lineup=[{"name": "Bruno Silva", "position": "Unknown", "source_urls": ["https://example.com/b"]}],
    )

    assert result["validation_status"] == "accepted"
    assert result["critical_matchups"][0]["player1"] == "Alex Rivera"
    assert result["critical_matchups"][0]["player2"] == "Bruno Silva"
    assert result["critical_matchups"][0]["position"] == "candidate"
    assert "not confirmed" in result["critical_matchups"][0]["candidate_status"]


@pytest.mark.asyncio
async def test_matchup_analysis_uses_deterministic_note_when_stats_missing():
    agent = MatchupAnalysisAgent(sport="soccer", fbref_retriever=None)

    result = await agent._analyze_player_matchup(
        {"name": "Alex Rivera", "position": "Forward"},
        {"name": "Bruno Silva", "position": "Defender"},
    )

    assert result["importance"] == "medium"
    assert "No verified season-stat edge" in result["analysis"]
    assert "cannot be determined" not in result["analysis"]


@pytest.mark.asyncio
async def test_matchup_analysis_replaces_tactical_refusal_text(monkeypatch):
    agent = MatchupAnalysisAgent(sport="soccer", fbref_retriever=None)

    async def fake_call_llm(*args, **kwargs):
        return "I'm unable to provide tactical analysis from the supplied context."

    monkeypatch.setattr(agent, "call_llm", fake_call_llm)

    result = await agent._generate_tactical_implications(
        [{"player1": "Alex Rivera", "player2": "Bruno Silva"}],
        {"home_vulnerabilities": [], "away_vulnerabilities": []},
    )

    assert "unable to provide" not in result.lower()
    assert "verified matchup detail is incomplete" in result


def test_note_organizer_filters_refusal_tactical_summary():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    brief = organizer._build_tactical_brief({
        "home_team": "Belgium",
        "away_team": "Egypt",
        "team_form": {},
        "matchups": {
            "tactical_implications": (
                "Based on the limited information available in your prompt, "
                "I cannot generate a substantive tactical analysis."
            ),
            "positional_strength": {},
            "weak_points": {},
            "critical_matchups": [],
        },
        "historical": {},
        "weather": {},
    })

    assert "cannot generate" not in brief["summary"].lower()
    assert "Belgium vs Egypt profiles as a balanced tactical battle" in brief["summary"]


def test_note_organizer_dedupes_and_rejects_unrelated_storylines():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")
    accepted = [
        {"claim": "Belgium vs Egypt at World Cup 2026", "source_tier": "structured", "source_name": "espn.com"},
        {"claim": "Belgium vs Egypt at World Cup 2026", "source_tier": "structured", "source_name": "espn.com"},
        {"claim": "Kimmich: Germany don't have an easy group at World Cup", "source_tier": "structured", "source_name": "espn.com"},
    ]

    assert organizer._source_backed_facts(accepted) == [
        "Belgium vs Egypt at World Cup 2026 (structured: espn.com)"
    ]


def test_note_organizer_sanitizes_garbled_player_cue():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    output = organizer._format_player_profile_grid(
        [{
            "name": "Mo Salah",
            "position": "Forward",
            "profile": 'I know all about Mo Salah as I coached him at Roma." Salah remains the focal point.',
        }],
        "Egypt",
    )

    assert "as I coached" not in output
    assert "Use only confirmed live role" in output


def test_note_organizer_fixture_candidate_grid_avoids_unknown_placeholders_and_duplicates():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    output = organizer._format_player_profile_grid(
        [
            {"name": "Mo Salah", "position": "Unknown", "age": "Unknown", "nationality": "N/A", "profile": "Mo Salah is a fixture-evidence candidate."},
            {"name": "Mohamed Salah", "position": "Unknown", "age": "Unknown", "nationality": "N/A", "profile": "Mohamed Salah is a fixture-evidence candidate."},
        ],
        "Egypt",
    )

    assert output.count("No. tbc") == 1
    assert "Mohamed Salah |" not in output
    assert "Unknown" not in output
    assert "N/A" not in output
    assert "Egypt" in output


def test_note_organizer_suppresses_unbalanced_plausible_lineup():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    output = organizer._format_plausible_lineups(
        {
            "basis": "role-balanced researched squad order",
            "confidence": "medium",
            "away_team": {
                "formation": "4-3-3",
                "players": ["Mohamed El Shenawy", "Mostafa Shobeir", "El Mahdi Soliman", "Mohamed Salah"],
                "roles": {
                    "goalkeeper": ["Mohamed El Shenawy", "Mostafa Shobeir", "El Mahdi Soliman"],
                    "defenders": ["Mohamed Hany", "Tarek Alaa", "Hamdy Fathy", "Rami Rabia"],
                    "midfielders": ["Mo Salah", "Mohamed Salah", "Marwan Ateya"],
                    "forwards": ["Omar Marmoush"],
                },
            },
        },
        "Belgium",
        "Egypt",
    )

    assert "Egypt plausible XI not promoted" in output
    assert "GK: Mohamed El Shenawy, Mostafa Shobeir" not in output


def test_note_organizer_degraded_news_is_concise():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    degraded_output = organizer._format_news(
        {
            "validation_status": "degraded",
            "synthesis": "Belgium have limited information available and should be framed through home tempo.",
            "news_items": [{"title": "Belgium predicted XI and injury news", "source": "accepted source"}],
        },
        team_name="Belgium",
        side_label="home",
    )

    accepted_unconfirmed_output = organizer._format_news(
        {
            "validation_status": "accepted",
            "lineup_status": {"status": "predicted"},
            "synthesis": "Belgium are preparing for a broadcast fixture and must await official lineups.",
            "news_items": [{"title": "Belgium vs Egypt TV channel, live stream, predicted line-ups"}],
        },
        team_name="Belgium",
        side_label="home",
    )

    for output in (degraded_output, accepted_unconfirmed_output):
        assert output == "No verified Belgium team-news update was accepted in this run."
        assert "Recent Headlines" not in output
        assert "limited information" not in output


def test_note_organizer_empty_historical_frame_is_concise():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    record, narrative = organizer._format_historical_frame({}, "Belgium", "Egypt")

    assert record == "Unavailable from trusted sources in this run"
    assert narrative == "Historical H2H unavailable from accepted evidence."


@pytest.mark.asyncio
async def test_fixture_resolver_extracts_generic_venue_and_players_without_team_hardcode():
    class FakeSearch:
        async def search(self, *args, **kwargs):
            return {
                "results": [{
                    "title": "Club Alpha vs Club Beta Continental Cup Final guide",
                    "content": (
                        "Club Alpha face Club Beta in the Continental Cup Final at Riverfront Arena "
                        "on Saturday, May 30, 2026. Club Alpha winger Alex Rivera can stretch play. "
                        "Club Beta defender Bruno Silva is the cover defender."
                    ),
                    "url": "https://example.com/fixture-guide",
                }],
                "answer": "",
            }

    resolver = FixtureResolver(search_service=FakeSearch())

    result = await resolver.resolve(
        home_team="Club Alpha",
        away_team="Club Beta",
        sport="soccer",
        competition="Continental Cup Final",
    )

    assert result["status"] == "accepted"
    assert result["venue"] == "Riverfront Arena"
    assert result["match_datetime"].startswith("2026-05-30")
    assert result["players"]["home_team"][0]["name"] == "Alex Rivera"
    assert result["players"]["away_team"][0]["name"] == "Bruno Silva"


@pytest.mark.asyncio
async def test_fixture_resolver_prefers_uefa_source_for_champions_league_fixture():
    class FakeSearch:
        async def search(self, *args, **kwargs):
            assert "uefa.com" in kwargs.get("include_domains", [])
            return {
                "results": [
                    {
                        "title": "Media guide",
                        "content": "Arsenal face Paris Saint-Germain at Neutral Stadium on Friday, May 29, 2026.",
                        "url": "https://www.bbc.co.uk/sport/football/articles/media-guide",
                        "score": 0.99,
                    },
                    {
                        "title": "UEFA Paris vs Arsenal final",
                        "content": "Paris vs Arsenal UEFA Champions League Final at Puskas Arena on Saturday, May 30, 2026 at 18:00 CEST.",
                        "url": "https://www.uefa.com/uefachampionsleague/match/2047742--paris-vs-arsenal/final/",
                        "source": "UEFA",
                        "score": 0.1,
                    },
                ],
                "answer": "",
            }

    resolver = FixtureResolver(search_service=FakeSearch())

    result = await resolver.resolve(
        home_team="Arsenal",
        away_team="Paris Saint-Germain",
        sport="soccer",
        competition="Champions League Final",
    )

    assert result["status"] == "accepted"
    assert result["venue"] == "Puskas Arena"
    assert result["sources"][0]["source_tier"] == "official"


@pytest.mark.asyncio
async def test_fixture_resolver_uses_exa_first_before_fallback_search():
    class FakeExaSearch:
        is_available = True

        def __init__(self):
            self.calls = []

        async def search(self, query, **kwargs):
            self.calls.append((query, kwargs))
            return {
                "source": "exa",
                "results": [{
                    "title": "Club Alpha vs Club Beta Continental Cup Final preview",
                    "content": (
                        "Club Alpha vs Club Beta Continental Cup Final kicks off at Exa Arena "
                        "on Saturday, May 30, 2026 at 18:00 UTC. Club Alpha forward Alex Rivera "
                        "and Club Beta defender Bruno Silva are listed in the preview."
                    ),
                    "url": "https://www.espn.com/soccer/story/exa-fixture-preview",
                    "source": "exa",
                    "score": 0.2,
                }],
            }

    class FakeFallbackSearch:
        async def search(self, *args, **kwargs):
            return {
                "results": [{
                    "title": "Club Alpha vs Club Beta old media guide",
                    "content": (
                        "Club Alpha face Club Beta in the Continental Cup Final at Fallback Stadium "
                        "on Friday, May 29, 2026."
                    ),
                    "url": "https://example.com/fallback-fixture-guide",
                    "score": 0.99,
                }],
                "answer": "",
            }

    exa = FakeExaSearch()
    resolver = FixtureResolver(
        search_service=FakeFallbackSearch(),
        exa_search_service=exa,
    )

    result = await resolver.resolve(
        home_team="Club Alpha",
        away_team="Club Beta",
        sport="soccer",
        competition="Continental Cup Final",
    )

    assert exa.calls
    assert '"Club Alpha vs Club Beta"' in exa.calls[0][0]
    assert exa.calls[0][1]["topic"] == "fixture"
    assert result["status"] == "accepted"
    assert result["venue"] == "Exa Arena"
    assert result["match_datetime"].startswith("2026-05-30T18:00:00+00:00")
    assert result["sources"][0]["url"] == "https://www.espn.com/soccer/story/exa-fixture-preview"
    assert result["search_provenance"]["fixture_first_provider"] == "exa"
    assert result["search_provenance"]["exa_source"] == "exa"
    assert result["search_provenance"]["exa_result_count"] == 1


@pytest.mark.asyncio
async def test_fixture_resolver_rejects_stale_official_club_page_for_final():
    class FakeSearch:
        async def search(self, *args, **kwargs):
            return {
                "results": [
                    {
                        "title": "Arsenal vs Paris Saint-Germain | UEFA Champions League | April 29 2025",
                        "content": "Arsenal faced Paris Saint-Germain at Arsenal Stadium on Tuesday, April 29, 2025.",
                        "url": "https://www.arsenal.com/fixture/arsenal/2025-Apr-29/paris-saint-germain-fc",
                        "score": 0.99,
                    },
                    {
                        "title": "Paris vs Arsenal | The final | UEFA Champions League 2025/26 Final",
                        "content": "Paris vs Arsenal UEFA Champions League Final at Puskas Arena on Saturday, May 30, 2026 at 18:00 CEST.",
                        "url": "https://www.uefa.com/uefachampionsleague/match/2047742--paris-vs-arsenal/final/",
                        "source": "UEFA",
                        "score": 0.1,
                    },
                ],
                "answer": "",
            }

    resolver = FixtureResolver(search_service=FakeSearch())

    result = await resolver.resolve(
        home_team="Arsenal",
        away_team="Paris Saint-Germain",
        sport="soccer",
        competition="UEFA Champions League Final",
    )

    assert result["status"] == "accepted"
    assert result["venue"] == "Puskas Arena"
    assert result["match_datetime"].startswith("2026-05-30T18:00:00+02:00")
    assert result["sources"][0]["url"] == "https://www.uefa.com/uefachampionsleague/match/2047742--paris-vs-arsenal/final/"


def test_fixture_resolver_prefers_fixture_date_over_article_publish_date():
    resolver = FixtureResolver(search_service=None)
    text = (
        "Published Monday, May 11, 2026. Club Alpha vs Club Beta Continental Cup Final. "
        "Date, kick-off time and venue: Club Alpha vs Club Beta is scheduled for a "
        "5pm BST kick-off on Saturday May 30, 2026. The match will take place at Riverfront Arena."
    )

    assert resolver._extract_datetime(text).startswith("2026-05-30T17:00:00+01:00")


def test_fixture_resolver_uses_derived_team_acronym_for_relevance_and_player_side():
    resolver = FixtureResolver(search_service=None)
    text = (
        "Club Alpha vs Paris Saint-Germain Continental Cup Final preview. "
        "For PSG, defender Bruno Silva is the main recovery runner."
    )

    assert resolver._is_relevant_fixture_text(text, "Club Alpha", "Paris Saint-Germain", "Continental Cup Final")
    assert resolver._sentence_side("For PSG, defender Bruno Silva is the main recovery runner.", "Club Alpha", "Paris Saint-Germain") == "away_team"


def test_fixture_resolver_keeps_hyphenated_player_names_and_rejects_photo_credits():
    resolver = FixtureResolver(search_service=None)
    names = resolver._extract_person_names(
        "For PSG, midfielder Warren Zaire-Emery covers the channel. Getty For PSG show a preview image.",
        "Club Alpha",
        "Paris Saint-Germain",
        "Continental Cup Final",
    )

    assert "Warren Zaire-Emery" in names
    assert "Getty For" not in names


def test_fixture_resolver_cleans_position_prefixed_player_candidates():
    resolver = FixtureResolver(search_service=None)
    names = resolver._extract_person_names(
        (
            "Predicted XI should not be treated as a player. "
            "For Belgium, GK Thibaut Courtois starts behind RBCastagne and "
            "midfielder Kevin De Bruyne."
        ),
        "Belgium",
        "Egypt",
        "Friendly",
    )

    assert "Predicted XI" not in names
    assert "Thibaut Courtois" in names
    assert "Castagne" in names
    assert "Kevin De Bruyne" in names


def test_fixture_resolver_keeps_lineup_players_on_their_side():
    resolver = FixtureResolver(search_service=None)
    resolution = resolver._resolve_from_results(
        home_team="Belgium",
        away_team="Egypt",
        competition="FIFA World Cup 2026",
        results=[{
            "title": "Belgium vs Egypt World Cup predicted line-ups",
            "url": "https://example.com/belgium-egypt",
            "content": (
                "Team News Belgium Predicted XI: 4-2-3-1 GK:Thibaut Courtois "
                "LB:Maxim De Cuyper; CB:Brandon Mechele; CAM:Kevin De Bruyne. "
                "Egypt Predicted XI: 4-2-3-1 GK: Mostafa Ahmed Shobeir "
                "LB:Ahmed Abou El Fotouh; CB:Yasser Ibrahim; RW:Mohamed Salah CF:Omar Marmoush."
                " Image 28 ## Talking Points The match will also see Kevin De Bruyne and Mohamed Salah "
                "on the field thanks to their exploits with Manchester City and Liverpool."
                " Egypt squad Midfielders: Haissem Hassan (Real Ovideo)."
            ),
        }],
    )

    home_names = {player.name for player in resolution.players["home_team"]}
    away_names = {player.name for player in resolution.players["away_team"]}

    assert {"Thibaut Courtois", "Maxim De Cuyper", "Brandon Mechele", "Kevin De Bruyne"} <= home_names
    assert {"Mostafa Ahmed Shobeir", "Ahmed Abou El Fotouh", "Yasser Ibrahim", "Mohamed Salah", "Omar Marmoush"} <= away_names
    assert "Kevin De Bruyne" not in away_names
    assert "Talking Points" not in away_names
    assert "Manchester City" not in away_names
    assert "Real Ovideo" not in away_names
    assert all(not name.endswith((" CF", " LB", " CM")) for name in home_names | away_names)


def test_fixture_resolver_rejects_caption_club_and_official_phrases_as_players():
    resolver = FixtureResolver(search_service=None)
    names = resolver._extract_person_names(
        (
            "Holders Paris meet Real Madrid references in the guide. "
            "Photo by FRANCK FIFE / AFP via Getty Images lists Rafael Foltyn GER Fourth official "
            "and Assistant Referee Bastian Dankert. And Andy, midfield, right, is a transcript fragment."
        ),
        "Arsenal",
        "Paris Saint-Germain",
        "Champions League Final",
    )

    assert names == []


@pytest.mark.asyncio
async def test_fixture_resolver_ignores_unanchored_search_answer():
    class FakeSearch:
        async def search(self, *args, **kwargs):
            return {
                "results": [],
                "answer": "The match is at Riverfront Arena on Saturday, May 30, 2026.",
            }

    resolver = FixtureResolver(search_service=FakeSearch())

    result = await resolver.resolve(
        home_team="Club Alpha",
        away_team="Club Beta",
        sport="soccer",
        competition="Continental Cup Final",
    )

    assert result["status"] == "unavailable"
    assert result["venue"] == ""
    assert result["match_datetime"] == ""


@pytest.mark.asyncio
async def test_team_form_sequence_only_uses_deterministic_comparison(monkeypatch):
    agent = TeamFormAgent(sport="soccer", football_data_retriever=None)

    home = {
        "team_name": "Club Alpha",
        "recent_form": {"form_string": "WWWWW", "record": {"wins": None, "draws": None, "losses": None}},
        "home_away_split": {},
        "comprehensive_analysis": "",
        "data_status": "partial",
    }
    away = {
        "team_name": "Club Beta",
        "recent_form": {"form_string": "DDWWL", "record": {"wins": None, "draws": None, "losses": None}},
        "home_away_split": {},
        "comprehensive_analysis": "",
        "data_status": "partial",
    }

    async def fail_call_llm(*args, **kwargs):
        raise AssertionError("sequence-only comparison should not call the LLM")

    monkeypatch.setattr(agent, "call_llm", fail_call_llm)

    result = await agent._compare_form(home, away)

    assert result["data_status"] == "partial"
    assert "Club Alpha's recent-results cue is WWWWW" in result["comparative_assessment"]
    assert "not a prediction" in result["comparative_assessment"]


@pytest.mark.asyncio
async def test_custom_fixture_resolves_fixture_context_before_unverified_warning(monkeypatch):
    async def fake_resolve(self, **kwargs):
        return {
            "status": "accepted",
            "venue": "Riverfront Arena",
            "match_datetime": "2026-05-30T20:00:00",
            "venue_lat": 0.0,
            "venue_lon": 0.0,
            "players": {"home_team": [], "away_team": [], "unknown": []},
            "sources": [{"title": "Fixture guide", "url": "https://example.com/fixture-guide"}],
        }

    monkeypatch.setattr(FixtureResolver, "resolve", fake_resolve)
    workflow = CommentaryNotesWorkflow()
    state = CommentaryNotesState(
        match_id="custom-club-alpha-beta",
        home_team="Club Alpha",
        away_team="Club Beta",
        competition="Continental Cup Final",
    )

    initialized = await workflow.initialize_workflow(state)

    assert initialized.match_datetime == "2026-05-30T20:00:00"
    assert initialized.venue == "Riverfront Arena"
    assert "Kickoff time unverified for custom fixture" not in initialized.warnings
    assert "Venue unverified for custom fixture" not in initialized.warnings


@pytest.mark.asyncio
async def test_custom_fixture_does_not_inherit_unrelated_next_event_context(monkeypatch):
    async def fake_resolve(self, **kwargs):
        return {
            "status": "unavailable",
            "venue": "",
            "match_datetime": "",
            "players": {"home_team": [], "away_team": [], "unknown": []},
            "sources": [],
        }

    monkeypatch.setattr(FixtureResolver, "resolve", fake_resolve)
    workflow = CommentaryNotesWorkflow()
    state = CommentaryNotesState(
        match_id="custom-club-alpha-beta",
        home_team="Club Alpha",
        away_team="Club Beta",
        competition="Continental Cup Final",
    )

    initialized = await workflow.initialize_workflow(state)

    assert initialized.match_datetime == ""
    assert initialized.venue == "Unknown"
    assert "Kickoff time unverified for custom fixture" in initialized.warnings
    assert "Venue unverified for custom fixture" in initialized.warnings
