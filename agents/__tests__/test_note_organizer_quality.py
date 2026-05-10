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
    assert "Check official" not in section
    assert "latest roster updates" not in section


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


def test_tactical_plan_rejects_broken_stable_no_matches_sentence():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    plan = organizer._extract_team_plan(
        {
            "team_name": "Real Madrid",
            "recent_form": {"record": {"wins": 0, "draws": 0, "losses": 0}, "form_string": "DLWDW"},
            "comprehensive_analysis": "Real Madrid's is stable. They have not won any matches, lost any matches, and drawn no matches.",
        },
        "Real Madrid",
    )

    assert "Real Madrid's is stable" not in plan
    assert "not won any matches" not in plan
    assert "Real Madrid's recent sequence reads DLWDW" in plan


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


def test_form_sequence_does_not_tell_user_to_verify():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    copy = organizer._build_team_form_fallback(
        {
            "team_name": "Real Madrid",
            "recent_form": {
                "record": {"wins": 0, "draws": 0, "losses": 0},
                "form_string": "DLWDW",
            },
        },
        "Real Madrid",
    )

    assert "verify" not in copy.lower()
    assert "Turn that into a live read" in copy


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


def test_missing_data_fallbacks_are_booth_guidance_not_homework():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    players = organizer._format_player_list([])
    news = organizer._format_news({
        "synthesis": (
            "Real Madrid has no recent news available. There are no reported injuries, "
            "and the lineup status is unavailable. No tactical adjustments are expected at this time."
        )
    })
    matchups = organizer._format_matchups([])
    tactical = organizer._organize_team_analysis_section(
        player_research={"team_name": "Real Madrid", "players": []},
        form_analysis={
            "team_name": "Real Madrid",
            "recent_form": {"record": {"wins": 0, "draws": 0, "losses": 0}, "form_string": "DLWDW"},
            "comprehensive_analysis": "",
        },
        news={"synthesis": "No recent news available. Lineup status is unavailable."},
        team_label="Real Madrid",
        page_number=2,
    )

    combined = "\n".join([players, news, matchups, tactical])
    banned = [
        "check official",
        "latest roster updates",
        "being finalized",
        "lineup status is unavailable",
        "no tactical adjustments are expected",
        "check back",
        "verify the real",
    ]
    for phrase in banned:
        assert phrase not in combined.lower()
    assert "first receiver" in players.lower()
    assert "No major home side disruption surfaced" in news
    assert "Call the matchup by zone" in matchups


def test_lineups_without_players_render_shape_cues_not_empty_table():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    section = organizer._organize_lineups_section(
        home_squad={"team_name": "Real Madrid", "players": []},
        away_squad={"team_name": "Barcelona", "players": []},
        match_datetime="2026-05-10T19:00:00Z",
        venue="Unknown Venue",
        weather={"current_conditions": {}},
    )

    assert "Probable Starters From Available Research" not in section
    assert "| - | - | - |" not in section
    assert "Opening Shape Cues" in section
    assert "No active weather angle" in section


def test_unknown_venue_is_rendered_as_broadcast_angle_not_placeholder():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    assert organizer._format_venue_summary("Unknown Venue") == "No stadium-specific angle in this run"
    assert organizer._format_venue_summary("Santiago Bernabeu") == "Santiago Bernabeu"


def test_missing_players_use_watch_cues_heading():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    section = organizer._organize_team_analysis_section(
        player_research={"team_name": "Real Madrid", "players": []},
        form_analysis={"recent_form": {"form_string": "DLWDW"}},
        news={},
        team_label="Real Madrid",
        page_number=2,
    )

    assert "Player Watch Cues" in section
    assert "Key Players (Sorted by Recent Form)" not in section


def test_home_and_away_missing_data_sections_are_not_duplicate():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    home = organizer._organize_team_analysis_section(
        player_research={"team_name": "Real Madrid", "players": []},
        form_analysis={"recent_form": {"form_string": "DLWDW"}},
        news={},
        team_label="Real Madrid",
        page_number=2,
    )
    away = organizer._organize_team_analysis_section(
        player_research={"team_name": "Barcelona", "players": []},
        form_analysis={"recent_form": {"form_string": "WWWWW"}},
        news={},
        team_label="Barcelona",
        page_number=3,
    )

    assert "home tempo" in home
    assert "travel composure" in away
    assert "Territory setter" in home
    assert "Back-post threat" in away
    assert "first escape pass" in away
    assert "use the first ten minutes to identify the roles live" not in home
    assert "use the first ten minutes to identify the roles live" not in away
    assert "Their form string is" not in home
    assert "Their form string is" not in away
    assert "opening home spell" in home
    assert "opening away spell" in away
    assert home != away


def test_tactical_summary_drops_no_critical_battles_scaffold():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    brief = organizer._build_tactical_brief({
        "home_team": "Real Madrid",
        "away_team": "Barcelona",
        "team_form": {"comparative_analysis": {"comparative_assessment": "Form Favorability: Real Madrid is in better form than Barcelona."}},
        "matchups": {"tactical_implications": "Based on the provided match-ups summary, there are no critical battles identified."},
        "historical": {},
        "weather": {},
    })

    assert "no critical battles identified" not in brief["summary"].lower()
    assert "Form Favorability" not in brief["summary"]
    assert "balanced tactical battle" in brief["summary"]
    assert all("Form Favorability" not in angle for angle in brief["commentary_angles"])


def test_pressure_points_reject_unverified_lineup_weaknesses():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    points = organizer._build_pressure_points(
        "Real Madrid",
        "Barcelona",
        {
            "home_vulnerabilities": [
                "Thin defensive cover in the verified lineup",
                "Limited midfield control based on listed starters",
            ],
            "away_vulnerabilities": ["Low attacking depth in the verified lineup"],
        },
    )

    combined = " ".join(points).lower()
    assert "verified lineup" not in combined
    assert "listed starters" not in combined
    assert "first buildup under pressure" in combined


def test_limited_historical_pattern_not_used_as_commentary_angle():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    angles = organizer._build_commentary_angles(
        "Real Madrid",
        "Barcelona",
        matchups={},
        historical={"h2h_history": {"patterns": {"pattern": "Limited historical data"}}},
        weather={},
        comparative="Form Favorability: Real Madrid is in better form than Barcelona.",
    )

    combined = " ".join(angles).lower()
    assert "limited historical data" not in combined
    assert "form favorability" not in combined
