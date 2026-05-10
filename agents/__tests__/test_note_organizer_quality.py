from agents.specialized_commentary.note_organizer_agent import CommentaryNoteOrganizerAgent


def test_tactical_plan_replaces_numbered_unavailable_llm_stub():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    notes = organizer._organize_tactical_section(
        home_team="Roma",
        away_team="Napoli",
        tactical_brief=organizer._build_tactical_brief({
            "home_team": "Roma",
            "away_team": "Napoli",
            "team_form": {
                "home_team": {
                    "team_name": "Roma",
                    "recent_form": {
                        "record": {"wins": 2, "draws": 1, "losses": 2},
                        "form_string": "WDLWL",
                    },
                    "comprehensive_analysis": "1. Current Form Status: Unavailable 2.",
                },
                "away_team": {
                    "team_name": "Napoli",
                    "recent_form": {
                        "record": {"wins": 3, "draws": 1, "losses": 1},
                        "form_string": "WWDLW",
                    },
                    "comprehensive_analysis": "1. Current Form Status: Unavailable 2.",
                },
                "comparative_analysis": {
                    "comparative_assessment": "1. Current Form Status: Unavailable 2.",
                },
            },
            "matchups": {},
            "historical": {},
            "weather": {},
        }),
        matchups={},
        historical={},
        weather={},
    )

    assert "Current Form Status: Unavailable" not in notes
    assert "How Roma Can Tilt The Match" in notes
    assert "Roma enter with a recent record of 2W-1D-2L" in notes
    assert "How Napoli Can Tilt The Match" in notes
    assert "Napoli enter with a recent record of 3W-1D-1L" in notes


def test_team_analysis_uses_actual_team_name_and_sanitized_form():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    section = organizer._organize_team_analysis_section(
        player_research={"team_name": "Roma", "players": []},
        form_analysis={
            "team_name": "Roma",
            "recent_form": {"record": {"wins": 2, "draws": 0, "losses": 1}},
            "comprehensive_analysis": "1. Current Form Status: Unavailable 2.",
        },
        news={},
        team_label="Roma",
        page_number=2,
    )

    assert "## PAGE 2: ROMA ANALYSIS" in section
    assert "Recent Form (Roma)" in section
    assert "Current Form Status: Unavailable" not in section
    assert "Home Team" not in section


def test_tactical_plan_rejects_markdown_artifacts_and_bad_metric_claims():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    plan = organizer._extract_team_plan(
        {
            "team_name": "Roma",
            "recent_form": {"record": {"wins": 4, "draws": 0, "losses": 11}},
            "comprehensive_analysis": (
                "**** Declining **** - Defensive record: 4 wins, 11 losses - "
                "Goal-scoring rate: 52 goals against 29 goals scored."
            ),
        },
        "Roma",
    )

    assert "****" not in plan
    assert "defensive record: 4 wins" not in plan
    assert "Roma enter with a recent record of 4W-0D-11L" in plan


def test_tactical_plan_rejects_zero_defensive_record_colon_form():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    plan = organizer._extract_team_plan(
        {
            "team_name": "Roma",
            "recent_form": {"record": {"wins": 0, "draws": 0, "losses": 0}},
            "comprehensive_analysis": (
                "Stable Defensive record: 0 wins, 0 draws, 0 losses; "
                "Goal-scoring rate: 0 goals for, 0 goals against."
            ),
        },
        "Roma",
    )

    assert "Defensive record: 0 wins" not in plan
    assert "live cues" in plan


def test_matchup_analysis_is_cleaned_to_commentary_blurb():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    rendered = organizer._format_matchups([
        {
            "player1": "Matias Soule",
            "player2": "Alessandro Buongiorno",
            "analysis": (
                "### Statistical Advantage\nBoth players have zero goals and assists each. "
                "### Tactical Edge\nThe duel is about depth runs against recovery defending."
            ),
        }
    ])

    assert "###" not in rendered
    assert "Statistical Advantage" not in rendered
    assert "Matias Soule vs Alessandro Buongiorno" in rendered


def test_zero_record_no_data_uses_live_cue_fallback():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    plan = organizer._extract_team_plan(
        {
            "team_name": "Napoli",
            "recent_form": {
                "record": {"wins": 0, "draws": 0, "losses": 0},
                "form_string": "No data",
            },
            "comprehensive_analysis": (
                "Stable - Defensive record: 0 wins, 0 draws, 0 losses. "
                "No clear direction as they have not played any matches."
            ),
        },
        "Napoli",
    )

    assert "0W-0D-0L" not in plan
    assert "live cues" in plan


def test_historical_zero_zero_zero_claim_is_replaced():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    narrative = organizer._clean_historical_narrative(
        "This head-to-head record stands at 0-0-0, with no previous encounters between these two teams.",
        "Roma",
        "Napoli",
    )

    assert "0-0-0" not in narrative
    assert "without overstating verified head-to-head numbers" in narrative


def test_match_dynamic_drops_unverified_weather_inference():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    dynamic = organizer._format_match_dynamic(
        matchups={"critical_matchups": [{"player1": "A", "player2": "B"}]},
        historical={},
        weather={"narrative": "The weather conditions remain unknown, but we can infer calm conditions."},
    )

    assert "weather conditions remain unknown" not in dynamic.lower()
    assert "we can infer" not in dynamic.lower()
