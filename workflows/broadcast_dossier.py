"""Build source-aware broadcast dossier data for commentary notes."""

from __future__ import annotations

from typing import Any


def build_broadcast_dossier(all_outputs: dict[str, Any]) -> dict[str, Any]:
    """Normalize workflow outputs into a six-page broadcast prep contract."""
    home_team = str(all_outputs.get("home_team") or "Home")
    away_team = str(all_outputs.get("away_team") or "Away")
    fixture_context = all_outputs.get("fixture_context") if isinstance(all_outputs.get("fixture_context"), dict) else {}
    quality_report = all_outputs.get("quality_report") if isinstance(all_outputs.get("quality_report"), dict) else {}
    player_research = all_outputs.get("player_research") if isinstance(all_outputs.get("player_research"), dict) else {}
    historical = all_outputs.get("historical") if isinstance(all_outputs.get("historical"), dict) else {}
    team_form = all_outputs.get("team_form") if isinstance(all_outputs.get("team_form"), dict) else {}
    news = all_outputs.get("news") if isinstance(all_outputs.get("news"), dict) else {}
    matchups = all_outputs.get("matchups") if isinstance(all_outputs.get("matchups"), dict) else {}

    home_players = player_research.get("home_team", {}).get("players", [])
    away_players = player_research.get("away_team", {}).get("players", [])
    if not isinstance(home_players, list):
        home_players = []
    if not isinstance(away_players, list):
        away_players = []

    officials = _officials_from_fixture(fixture_context)
    match_sources = _source_urls(fixture_context.get("sources", []))
    accepted_facts = [
        item.get("claim", "")
        for item in quality_report.get("accepted_evidence", [])
        if isinstance(item, dict) and item.get("claim")
    ][:8]

    return {
        "version": 1,
        "match_facts": {
            "home_team": home_team,
            "away_team": away_team,
            "competition": all_outputs.get("competition") or "",
            "match_datetime": all_outputs.get("match_datetime") or fixture_context.get("match_datetime") or "",
            "venue": all_outputs.get("venue") or fixture_context.get("venue") or "",
            "officials": officials,
            "sources": match_sources,
            "accepted_facts": accepted_facts,
        },
        "page_contract": [
            "Page 1: Match Overview & Lineups",
            f"Page 2: {home_team} Deep-Dive",
            f"Page 3: {away_team} Deep-Dive",
            "Page 4: Club Context & Staff",
            "Pages 5-6: Statistics & Historical Context",
        ],
        "lineups": {
            "plausible": _build_plausible_lineups(home_players, away_players),
            "source_predicted": all_outputs.get("possible_lineups") or {},
            "confirmed": _confirmed_lineups_from_news(news),
        },
        "player_cards": {
            "home_team": _player_cards(home_players, home_team),
            "away_team": _player_cards(away_players, away_team),
        },
        "club_context": {
            "home_team": _club_context(home_team, player_research.get("home_team", {}), news.get("home_team", {})),
            "away_team": _club_context(away_team, player_research.get("away_team", {}), news.get("away_team", {})),
        },
        "statistics_context": {
            "home_form": _form_card(team_form.get("home_team", {}), home_team),
            "away_form": _form_card(team_form.get("away_team", {}), away_team),
            "h2h": historical.get("h2h_history", {}),
            "storylines": _storylines(historical, news),
            "key_duels": _key_duels(matchups),
        },
        "quality_bar": {
            "accepted_evidence_count": quality_report.get("accepted_evidence_count", 0),
            "rejected_evidence_count": quality_report.get("rejected_evidence_count", 0),
            "degraded_sections": quality_report.get("degraded_sections", []),
            "minimum_player_cards_per_side": 18,
            "target_player_cards_per_side": 25,
        },
    }


def _officials_from_fixture(fixture_context: dict[str, Any]) -> dict[str, str]:
    candidates = fixture_context.get("officials")
    if isinstance(candidates, dict):
        return {str(key): str(value) for key, value in candidates.items() if value}
    officials = {}
    for source_key, output_key in (
        ("referee", "referee"),
        ("var", "var"),
        ("assistant_referees", "assistant_referees"),
        ("fourth_official", "fourth_official"),
    ):
        value = fixture_context.get(source_key)
        if value:
            officials[output_key] = ", ".join(str(item) for item in value) if isinstance(value, list) else str(value)
    return officials


def _source_urls(value: Any) -> list[str]:
    urls: list[str] = []

    def walk(item: Any) -> None:
        if len(urls) >= 8:
            return
        if isinstance(item, dict):
            for key in ("url", "source_url", "link"):
                url = item.get(key)
                if isinstance(url, str) and url.startswith(("http://", "https://")) and url not in urls:
                    urls.append(url)
            for child in item.values():
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)
    return urls


def _build_plausible_lineups(home_players: list[dict[str, Any]], away_players: list[dict[str, Any]]) -> dict[str, Any]:
    home_lineup = _select_balanced_xi(home_players)
    away_lineup = _select_balanced_xi(away_players)
    return {
        "basis": "role-balanced researched squad order; unconfirmed until team sheets",
        "confidence": "medium" if len(home_lineup) >= 11 and len(away_lineup) >= 11 else "low",
        "home_team": _lineup_payload(home_lineup),
        "away_team": _lineup_payload(away_lineup),
    }


def _select_balanced_xi(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build an XI-shaped list instead of taking the first 11 squad rows."""
    role_targets = (("goalkeeper", 1), ("defender", 4), ("midfielder", 3), ("forward", 3))
    selected: list[dict[str, Any]] = []
    selected_names: set[str] = set()

    for role, target in role_targets:
        for player in players:
            if len([item for item in selected if _role(item) == role]) >= target:
                break
            name = str(player.get("name") or "").strip() if isinstance(player, dict) else ""
            if not name or name.lower() == "unknown" or name in selected_names:
                continue
            if _role(player) != role:
                continue
            selected.append(player)
            selected_names.add(name)

    for player in players:
        if len(selected) >= 11:
            break
        name = str(player.get("name") or "").strip() if isinstance(player, dict) else ""
        if not name or name.lower() == "unknown" or name in selected_names:
            continue
        selected.append(player)
        selected_names.add(name)

    return selected[:11]


def _lineup_payload(players: list[dict[str, Any]]) -> dict[str, Any]:
    grouped = {
        "goalkeeper": _names([player for player in players if _role(player) == "goalkeeper"]),
        "defenders": _names([player for player in players if _role(player) == "defender"]),
        "midfielders": _names([player for player in players if _role(player) == "midfielder"]),
        "forwards": _names([player for player in players if _role(player) == "forward"]),
    }
    return {
        "formation": "4-3-3" if len(players) >= 11 else "",
        "players": _names(players),
        "roles": grouped,
        "caveat": "role-balanced projection from researched squad order; not a confirmed XI",
    }


def _role(player: dict[str, Any]) -> str:
    position = str(player.get("position") or "").strip().lower()
    if position in {"gk", "goalkeeper", "keeper"}:
        return "goalkeeper"
    if any(token in position for token in ("defender", "back", "cb", "lb", "rb", "lwb", "rwb")):
        return "defender"
    if any(token in position for token in ("midfielder", "midfield", "cm", "dm", "am", "lm", "rm")):
        return "midfielder"
    if any(token in position for token in ("forward", "striker", "attacker", "winger", "wing", "st", "cf")):
        return "forward"
    return "midfielder"


def _confirmed_lineups_from_news(news: dict[str, Any]) -> dict[str, Any]:
    lineups: dict[str, Any] = {}
    for side in ("home_team", "away_team"):
        side_news = news.get(side, {}) if isinstance(news.get(side), dict) else {}
        status = side_news.get("lineup_status", {})
        if isinstance(status, dict) and status.get("status") == "confirmed":
            lineups[side] = status
    return lineups


def _player_cards(players: list[dict[str, Any]], team_name: str) -> list[dict[str, Any]]:
    cards = []
    for player in players[:25]:
        if not isinstance(player, dict):
            continue
        name = str(player.get("name") or "").strip()
        if not name or name.lower() == "unknown":
            continue
        stats = player.get("stats") if isinstance(player.get("stats"), dict) else {}
        cards.append({
            "name": name,
            "team": team_name,
            "shirt_number": player.get("squad_number") or player.get("shirt_number") or player.get("jersey") or "tbc",
            "position": player.get("position") or "role tbc",
            "age": player.get("age") or "age tbc",
            "nationality": player.get("nationality") or "nationality tbc",
            "stats_line": _stats_line(stats),
            "cue": _first_sentence(player.get("profile") or player.get("evidence") or player.get("biography") or ""),
            "source_urls": _source_urls(player),
            "confidence": player.get("confidence", 0.6),
        })
    return cards


def _club_context(team_name: str, squad: dict[str, Any], news: dict[str, Any]) -> dict[str, Any]:
    manager = squad.get("manager") or news.get("manager") or "manager not verified in accepted feed"
    return {
        "team_name": team_name,
        "manager": manager,
        "staff": squad.get("staff") or news.get("staff") or [],
        "data_status": squad.get("data_status") or "partial",
        "upcoming_fixtures": squad.get("upcoming_fixtures") or news.get("upcoming_fixtures") or [],
    }


def _form_card(form_data: dict[str, Any], team_name: str) -> str:
    recent = form_data.get("recent_form", {}) if isinstance(form_data, dict) else {}
    record = recent.get("record", {}) if isinstance(recent, dict) else {}
    parts = []
    for key, label in (("wins", "W"), ("draws", "D"), ("losses", "L")):
        value = record.get(key)
        if value is not None:
            parts.append(f"{value}{label}")
    form_string = recent.get("form_string") if isinstance(recent, dict) else ""
    if parts:
        return f"{team_name}: {'-'.join(parts)}"
    if form_string:
        return f"{team_name}: {form_string}"
    return f"{team_name}: form unavailable from accepted feed"


def _storylines(historical: dict[str, Any], news: dict[str, Any]) -> list[str]:
    items: list[str] = []

    def add(title: Any) -> None:
        value = str(title or "").strip()
        key = "".join(ch for ch in value.lower() if ch.isalnum())
        if not value or key in {"".join(ch for ch in item.lower() if ch.isalnum()) for item in items}:
            return
        if _is_unrelated_storyline(value):
            return
        items.append(value)

    for story in historical.get("storylines", []) if isinstance(historical.get("storylines"), list) else []:
        if isinstance(story, dict) and story.get("title"):
            add(story["title"])
    for side in ("home_team", "away_team"):
        side_news = news.get(side, {}) if isinstance(news.get(side), dict) else {}
        for item in side_news.get("news_items", [])[:3]:
            if isinstance(item, dict) and item.get("title"):
                add(item["title"])
    return items[:10]


def _is_unrelated_storyline(text: str) -> bool:
    lower = (text or "").lower()
    return any(marker in lower for marker in (
        "kimmich",
        "germany don't have",
        "germany dont have",
        "teenage prodigy bouaddi",
        "england players shelter",
    ))


def _key_duels(matchups: dict[str, Any]) -> list[str]:
    duels = []
    for matchup in matchups.get("critical_matchups", []) if isinstance(matchups.get("critical_matchups"), list) else []:
        if isinstance(matchup, dict) and matchup.get("player1") and matchup.get("player2"):
            duels.append(f"{matchup['player1']} vs {matchup['player2']}")
    return duels[:8]


def _names(players: list[dict[str, Any]]) -> list[str]:
    names = []
    for player in players:
        if not isinstance(player, dict) or not player.get("name"):
            continue
        name = str(player.get("name")).strip()
        tokens = name.split()
        if len(tokens) == 2 and tokens[0] in {"De", "Van", "Der", "Le", "El", "Al"}:
            continue
        names.append(name)
    return names


def _stats_line(stats: dict[str, Any]) -> str:
    parts = []
    for key, label in (("appearances", "apps"), ("goals", "goals"), ("assists", "assists")):
        value = stats.get(key)
        if value is not None and value != "":
            parts.append(f"{value} {label}")
    return ", ".join(parts) if parts else "season stats not verified"


def _first_sentence(text: Any) -> str:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return ""
    if cleaned.startswith("[...]") or " as I coached " in f" {cleaned} " or " as i coached " in f" {cleaned.lower()} ":
        return ""
    for sep in (". ", "! ", "? "):
        if sep in cleaned:
            return cleaned.split(sep, 1)[0].strip() + sep.strip()
    return cleaned[:220]
