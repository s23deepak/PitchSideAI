import pytest

from agents.specialized_commentary.note_organizer_agent import CommentaryNoteOrganizerAgent


@pytest.mark.asyncio
async def test_professional_final_notes_include_competition_frame_and_no_scaffold():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    notes = await organizer.synthesize_to_notes_store({
        "home_team": "Arsenal",
        "away_team": "Paris Saint-Germain",
        "sport": "soccer",
        "competition": "Champions League Final",
        "match_datetime": "2026-05-30T20:00:00+01:00",
        "venue": "Wembley Stadium",
        "player_research": {
            "home_team": {
                "team_name": "Arsenal",
                "players": [{
                    "name": "Bukayo Saka",
                    "position": "RW",
                    "profile": "Bukayo Saka gives Arsenal a verified right-sided outlet.",
                    "source_urls": ["https://example.com/saka"],
                    "data_source": "test_source",
                }],
            },
            "away_team": {
                "team_name": "Paris Saint-Germain",
                "players": [{
                    "name": "Achraf Hakimi",
                    "position": "RB",
                    "profile": "Achraf Hakimi gives PSG a verified right-sided transition runner.",
                    "source_urls": ["https://example.com/hakimi"],
                    "data_source": "test_source",
                }],
            },
        },
        "team_form": {
            "home_team": {
                "team_name": "Arsenal",
                "recent_form": {"record": {"wins": 4, "draws": 1, "losses": 0}, "form_string": "WWDWW"},
                "comprehensive_analysis": "Arsenal arrive with controlled possession spells and a strong counter-press.",
            },
            "away_team": {
                "team_name": "Paris Saint-Germain",
                "recent_form": {"record": {"wins": 3, "draws": 1, "losses": 1}, "form_string": "WDWLW"},
                "comprehensive_analysis": "Paris Saint-Germain carry transition speed and wide overload threat.",
            },
            "comparative_analysis": {
                "comparative_assessment": "Both sides can control midfield, but the decisive question is transition protection.",
            },
        },
        "matchups": {
            "critical_matchups": [{
                "player1": "Bukayo Saka",
                "player2": "Achraf Hakimi",
                "analysis": "This duel can decide whether Arsenal pin PSG back or PSG release pressure into transition.",
                "source_urls": ["https://example.com/duel"],
            }],
            "tactical_implications": "Expect the right-sided duel and midfield counter-press to shape the match rhythm.",
            "positional_strength": {},
            "weak_points": {},
        },
        "historical": {
            "h2h_history": {"team1_wins": 1, "team2_wins": 1, "draws": 2},
            "narrative": "The verified historical frame is balanced, so the booth should focus on control and transitions.",
        },
        "weather": {
            "current_conditions": {"temperature_c": 18, "conditions": "clear", "wind_kmh": 8},
            "narrative": "Clear conditions should allow a quick passing tempo.",
        },
        "news": {
            "home_team": {"synthesis": "Arsenal preparation notes point to a settled tactical focus.", "news_items": []},
            "away_team": {"synthesis": "Paris Saint-Germain preparation notes point to a settled tactical focus.", "news_items": []},
        },
        "quality_report": {"strict_mode": True, "degraded_sections": [], "unavailable_facts": []},
    })

    markdown = notes.raw_markdown

    assert "Champions League Final" in markdown
    assert "## Match Frame" in markdown
    assert "## Tactical Themes" in markdown
    assert "## Key Player Battles" in markdown
    assert "## Team News Caveats" in markdown
    assert "## Broadcast Folder Pages" in markdown
    assert "### Page 1: Team Sheets And Officials" in markdown
    assert "### Pages 2-3: Individual Player Profiles" in markdown
    assert "### Pages 4-5: Tactical And Historical Context" in markdown
    assert "### Archival Trivia" in markdown
    assert "## Live-Trigger Beats" in markdown
    assert "## Halftime And Postgame Angles" in markdown
    assert "Bukayo Saka vs Achraf Hakimi" in markdown
    assert len(notes.beats) >= 3
    for tag in ("goal", "substitution", "yellow_card", "red_card"):
        assert tag in notes.lookup
    banned = [
        "No stadium-specific angle",
        "No verified",
        "Opening Shape Cues",
        "balanced tactical battle",
        "AI summary",
        "placeholder",
    ]
    for phrase in banned:
        assert phrase not in markdown


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
    assert "Roma: Use the recent sequence WDLWL only as a context cue" in notes
    assert "How Napoli Can Tilt The Match" in notes
    assert "Napoli: Use the recent sequence WWDLW only as a context cue" in notes


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
    assert "Roma: In possession, watch first-pass security" in plan


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
    assert "In possession, watch first-pass security" in plan


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
    assert "Real Madrid: Use the recent sequence DLWDW only as a context cue" in plan


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
    assert "In possession, watch first-pass security" in plan


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
    assert "treat them as context rather than a script" in copy


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
    assert "No verified home side team-news update was accepted" in news
    assert "Central lane" in matchups


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


def test_researched_players_are_not_rendered_as_probable_starters_without_confirmed_lineups():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    section = organizer._organize_lineups_section(
        home_squad={"team_name": "Sunderland", "players": [{"name": "Player A", "position": "GK"}]},
        away_squad={"team_name": "Chelsea", "players": [{"name": "Player B", "position": "GK"}]},
        match_datetime="2026-05-24T16:00:00+01:00",
        venue="Stadium of Light",
        weather={"current_conditions": {}},
        news={
            "home_team": {"lineup_status": {"status": "reported"}},
            "away_team": {"lineup_status": {"status": "unavailable"}},
        },
    )

    assert "Probable Starters" not in section
    assert "Confirmed Starters" not in section
    assert "Opening Shape Cues" in section
    assert "UTC+01:00" in section


def test_confirmed_lineups_can_render_table_from_accepted_evidence():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    section = organizer._organize_lineups_section(
        home_squad={"team_name": "Sunderland", "players": [{"name": "Player A", "position": "GK"}]},
        away_squad={"team_name": "Chelsea", "players": [{"name": "Player B", "position": "GK"}]},
        match_datetime="2026-05-24T16:00:00+01:00",
        venue="Stadium of Light",
        weather={"current_conditions": {}},
        news={
            "home_team": {"lineup_status": {"status": "confirmed"}},
            "away_team": {"lineup_status": {"status": "confirmed"}},
        },
    )

    assert "Confirmed Starters From Accepted Evidence" in section
    assert "| Player A | GK | Player B |" in section


def test_degraded_news_and_h2h_do_not_emit_false_claims():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    news = organizer._format_news(
        {"validation_status": "degraded", "news_items": [], "injuries": [], "synthesis": ""},
        team_name="Chelsea",
        side_label="away",
    )
    tactical = organizer._organize_tactical_section(
        home_team="Sunderland",
        away_team="Chelsea",
        tactical_brief=organizer._build_tactical_brief({
            "home_team": "Sunderland",
            "away_team": "Chelsea",
            "team_form": {},
            "matchups": {},
            "historical": {"h2h_history": {"status": "unavailable"}},
            "weather": {},
        }),
        matchups={},
        historical={"h2h_history": {"status": "unavailable"}, "narrative": ""},
        weather={},
    )

    assert "No verified Chelsea team-news update was accepted" in news
    assert "rich rivalry history" not in tactical
    assert "H2H Record: **Unavailable from trusted sources in this run**" in tactical
    assert "0-0-0" not in tactical


@pytest.mark.asyncio
async def test_air_ready_rundown_surfaces_source_backed_and_blocked_claims():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    markdown = await organizer._build_markdown_document({
        "home_team": "Arsenal",
        "away_team": "Paris Saint-Germain",
        "competition": "Champions League Final",
        "match_datetime": "2026-05-30T18:00:00+02:00",
        "venue": "Puskas Arena",
        "quality_report": {
            "strict_mode": True,
            "accepted_evidence_count": 1,
            "accepted_evidence": [{
                "claim": "UEFA confirms Paris vs Arsenal at Puskas Arena.",
                "source_name": "UEFA",
                "source_tier": "official",
                "source_url": "https://www.uefa.com/uefachampionsleague/match/2047742--paris-vs-arsenal/final/",
            }],
            "degraded_sections": ["team_news:Arsenal"],
            "unavailable_facts": ["Arsenal verified team news"],
        },
        "historical": {"storylines": []},
        "news": {},
        "team_form": {},
        "matchups": {},
        "weather": {},
        "player_research": {},
    })

    assert "## Air-Ready Rundown" in markdown
    assert "### Ready To Say" in markdown
    assert "UEFA confirms Paris vs Arsenal at Puskas Arena" in markdown
    assert "### Wait For Confirmation" in markdown
    assert "Arsenal verified team news" in markdown


@pytest.mark.asyncio
async def test_broadcast_folder_pages_match_a4_reference_structure():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    markdown = await organizer._build_markdown_document({
        "home_team": "Arsenal",
        "away_team": "Paris Saint-Germain",
        "competition": "Champions League Final",
        "match_datetime": "2026-05-30T18:00:00+02:00",
        "venue": "Puskas Arena",
        "quality_report": {"strict_mode": True, "degraded_sections": [], "unavailable_facts": []},
        "historical": {
            "h2h_history": {"team1_wins": 2, "team2_wins": 2, "draws": 3},
            "narrative": "UEFA lists seven previous meetings.",
            "storylines": [{
                "title": "Paris and Arsenal meet in a European final",
                "source": "UEFA",
            }],
        },
        "matchups": {
            "critical_matchups": [{
                "player1": "Bukayo Saka",
                "player2": "Nuno Mendes",
                "analysis": "Wide control against recovery speed.",
            }],
        },
        "possible_lineups": {
            "source": "Opta/Sky/NBC/UEFA consensus",
            "source_urls": [
                "https://theanalyst.com/articles/psg-vs-arsenal-prediction-champions-league-final-05-2026",
                "https://www.skysports.com/football/news/11095/13548482/champions-league-final-who-does-mikel-arteta-pick-in-his-arsenal-starting-xi-to-face-psg-in-budapest",
                "https://www.nbcsports.com/soccer/news/psg-vs-arsenal-predicted-lineups-team-news-analysis-for-epic-champions-league-final",
                "https://www.uefa.com/uefachampionsleague/news/02a5-20b60cd56a21-50353358258b-1000--champions-league-final-predicted-starting-line-ups-team-news/",
            ],
            "home_team": {"players": ["Raya", "Saliba", "Saka"], "out": ["White"]},
            "away_team": {"players": ["Safonov", "Vitinha", "Dembélé"], "doubtful": ["Hakimi"]},
        },
        "plausible_lineups": {
            "basis": "recent-start model",
            "confidence": "medium",
            "home_team": {
                "formation": "4-3-3",
                "players": ["Raya", "Timber", "Saliba", "Gabriel", "Calafiori", "Rice", "Ødegaard", "Saka"],
                "caveat": "final XI depends on late fitness checks",
            },
            "away_team": {
                "formation": "4-3-3",
                "players": ["Safonov", "Hakimi", "Marquinhos", "Vitinha", "Dembélé"],
            },
        },
        "team_form": {},
        "weather": {},
        "news": {},
        "player_research": {},
    })

    assert "## Broadcast Folder Pages" in markdown
    assert "Confirmed XIs: leave editable until official team sheets arrive" in markdown
    assert "Officials: add referee, VAR, and assistants only when confirmed" in markdown
    assert "#### Plausible XIs - Recent-Start Model" in markdown
    assert "Arsenal plausible XI (recent-start model, 4-3-3; confidence medium): Raya, Timber, Saliba" in markdown
    assert "Arsenal caveat: final XI depends on late fitness checks" in markdown
    assert "#### Source-Predicted XIs - Not Confirmed" in markdown
    assert "Arsenal source-predicted XI (Opta/Sky/NBC/UEFA consensus, unconfirmed): Raya, Saliba, Saka" in markdown
    assert "Paris Saint-Germain source-predicted XI (Opta/Sky/NBC/UEFA consensus, unconfirmed): Safonov, Vitinha, Dembélé" in markdown
    assert "Arsenal listed out: White" in markdown
    assert "Paris Saint-Germain listed doubtful: Hakimi" in markdown
    assert "https://theanalyst.com/articles/psg-vs-arsenal-prediction-champions-league-final-05-2026" in markdown
    assert "https://www.skysports.com/football/news/11095/13548482/champions-league-final-who-does-mikel-arteta-pick-in-his-arsenal-starting-xi-to-face-psg-in-budapest" in markdown
    assert "https://www.nbcsports.com/soccer/news/psg-vs-arsenal-predicted-lineups-team-news-analysis-for-epic-champions-league-final" in markdown
    assert "### Pages 2-3: Individual Player Profiles" in markdown
    assert "### Pages 4-5: Tactical And Historical Context" in markdown
    assert "Paris and Arsenal meet in a European final" in markdown
    assert "Bukayo Saka vs Nuno Mendes" in markdown
    assert "2-3-2" in markdown


def test_unknown_venue_is_rendered_as_broadcast_angle_not_placeholder():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    assert organizer._format_venue_summary("Unknown Venue") == "Stadium not verified in this run"
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


def test_tactical_summary_drops_missing_metrics_form_favorability_claim():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    brief = organizer._build_tactical_brief({
        "home_team": "Arsenal",
        "away_team": "Paris Saint-Germain",
        "team_form": {},
        "matchups": {
            "tactical_implications": (
                "As an elite soccer analyst, Arsenal holds a clear form favorability, "
                "contrasting sharply with a declining PSG side lacking available performance metrics."
            )
        },
        "historical": {},
        "weather": {},
    })

    assert "clear form favorability" not in brief["summary"].lower()
    assert "lacking available performance metrics" not in brief["summary"].lower()
    assert "balanced tactical battle" in brief["summary"]


def test_team_plan_rejects_bare_numbered_form_status():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    plan = organizer._extract_team_plan(
        {
            "team_name": "Paris Saint-Germain",
            "recent_form": {"form_string": "DDWWL"},
            "comprehensive_analysis": "1. Declining.",
        },
        "Paris Saint-Germain",
    )

    assert "1. Declining" not in plan
    assert "Paris Saint-Germain: Use the recent sequence DDWWL only as a context cue" in plan


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


@pytest.mark.asyncio
async def test_note_organizer_suppresses_placeholder_players_in_notes_and_beats():
    organizer = CommentaryNoteOrganizerAgent(sport="soccer")

    notes = await organizer.synthesize_to_notes_store({
        "home_team": "Arsenal",
        "away_team": "Paris Saint-Germain",
        "sport": "soccer",
        "competition": "Champions League Final",
        "player_research": {
            "home_team": {"team_name": "Arsenal", "players": []},
            "away_team": {
                "team_name": "Paris Saint-Germain",
                "players": [{
                    "name": "Paris Saint-Germain Player 1",
                    "position": "Midfielder",
                    "profile": "Mock fallback profile that should not reach the booth.",
                }],
            },
        },
        "team_form": {},
        "matchups": {
            "critical_matchups": [{
                "player1": "Paris Saint-Germain Player 1",
                "player2": "Arsenal Player 1",
                "analysis": "Both have 0G 0A, so this is placeholder filler.",
            }],
            "tactical_implications": "",
            "positional_strength": {},
            "weak_points": {},
        },
        "historical": {},
        "weather": {},
        "news": {},
    })

    rendered = notes.raw_markdown
    beat_text = " ".join(beat.text for beat in notes.beats)

    assert "Paris Saint-Germain Player 1" not in rendered
    assert "Arsenal Player 1" not in rendered
    assert "Paris Saint-Germain Player 1" not in beat_text
    assert "0G 0A" not in rendered
