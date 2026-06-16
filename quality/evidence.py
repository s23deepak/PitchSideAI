"""Evidence normalization and quality gates for commentary notes."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse


SOURCE_TIER_PRIORITY = {
    "official": 0,
    "structured": 1,
    "weather": 1,
    "trusted_media": 2,
    "trusted_scrape": 3,
    "fallback_search": 4,
    "untrusted": 9,
}
TRUSTED_OFFICIAL_DOMAINS = {
    "uefa.com",
    "arsenal.com",
    "arsenal.co.uk",
    "psg.fr",
    "en.psg.fr",
    "ligue1.com",
    "the-afc.com",
    "fifa.com",
    "chelseafc.com",
    "safc.com",
    "sunderlandafc.com",
    "premierleague.com",
}
TRUSTED_STRUCTURED_DOMAINS = {
    "espn.com",
    "espn.co.uk",
    "football-data.org",
    "statsbomb.com",
    "theanalyst.com",
    "fbref.com",
    "transfermarkt.com",
    "transfermarkt.co.uk",
    "11v11.com",
    "eu-football.info",
    "worldfootball.net",
    "mlssoccer.com",
}
TRUSTED_WEATHER_DOMAINS = {
    "metoffice.gov.uk",
    "weather.com",
    "accuweather.com",
    "open-meteo.com",
}
TRUSTED_MEDIA_DOMAINS = {
    "bbc.co.uk",
    "bbc.com",
    "skysports.com",
    "reuters.com",
    "apnews.com",
    "theguardian.com",
    "theathletic.com",
    "nytimes.com",
    "nbcsports.com",
    "sportsmole.co.uk",
    "rotowire.com",
    "espn.com",
    "espn.co.uk",
}
ALLOWED_DOMAINS = (
    TRUSTED_OFFICIAL_DOMAINS
    | TRUSTED_STRUCTURED_DOMAINS
    | TRUSTED_WEATHER_DOMAINS
    | TRUSTED_MEDIA_DOMAINS
)

OTHER_SPORT_TERMS = {
    "nba",
    "knicks",
    "basketball",
    "cricket",
    "ipl",
    "rcb",
    "srh",
    "tennis",
    "f1",
    "formula 1",
    "formula one",
    "verstappen",
    "hamilton",
    "canadian gp",
}


@dataclass
class EvidenceItem:
    claim: str
    source_name: str
    url: str = ""
    source_tier: str = "untrusted"
    topic: str = "general"
    team_scope: str = ""
    match_scope: str = ""
    confidence: float = 0.0
    validation_status: str = "rejected"
    reason: str = ""
    published_at: str = ""
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_url"] = self.url
        return payload


def build_evidence_quality_report(
    all_outputs: dict[str, Any],
    *,
    mutate: bool = True,
) -> dict[str, Any]:
    """Validate workflow outputs and remove claims that are not safe for final notes.

    The notes generator is intentionally strict: if evidence is weak, missing, or
    about a different fixture, the section is marked degraded and the claim is
    removed before synthesis.
    """
    target = all_outputs if mutate else dict(all_outputs)
    home_team = str(target.get("home_team") or "")
    away_team = str(target.get("away_team") or "")
    match_scope = f"{home_team} vs {away_team}".strip()

    accepted: list[EvidenceItem] = []
    rejected: list[EvidenceItem] = []
    degraded_sections: list[str] = []
    unavailable_facts: list[str] = []

    _gate_news(target.get("news", {}), home_team, away_team, match_scope, accepted, rejected, degraded_sections, unavailable_facts)
    _gate_weather(target.get("weather", {}), match_scope, accepted, rejected, degraded_sections, unavailable_facts)
    _gate_historical(target.get("historical", {}), home_team, away_team, match_scope, accepted, rejected, degraded_sections, unavailable_facts)
    _gate_player_research(target.get("player_research", {}), home_team, away_team, match_scope, accepted, degraded_sections, unavailable_facts)

    report = {
        "accepted_evidence_count": len(accepted),
        "rejected_evidence_count": len(rejected),
        "accepted_evidence": [item.to_dict() for item in accepted[:40]],
        "rejected_evidence": [item.to_dict() for item in rejected[:80]],
        "degraded_sections": sorted(set(degraded_sections)),
        "unavailable_facts": sorted(set(unavailable_facts)),
        "strict_mode": True,
    }
    target["quality_report"] = report
    return report


def is_allowed_url(url: str) -> bool:
    domain = _domain(url)
    return bool(domain and any(domain == allowed or domain.endswith(f".{allowed}") for allowed in ALLOWED_DOMAINS))


def classify_source_tier(url: str, source_name: str = "") -> str:
    domain = _domain(url)
    source = source_name.lower()
    if domain and any(domain == d or domain.endswith(f".{d}") for d in TRUSTED_OFFICIAL_DOMAINS):
        return "official"
    if domain and any(domain == d or domain.endswith(f".{d}") for d in TRUSTED_STRUCTURED_DOMAINS):
        return "structured"
    if domain and any(domain == d or domain.endswith(f".{d}") for d in TRUSTED_WEATHER_DOMAINS):
        return "weather"
    if domain and any(domain == d or domain.endswith(f".{d}") for d in TRUSTED_MEDIA_DOMAINS):
        return "trusted_media"
    if source in {"espn", "football_data", "football-data"}:
        return "structured"
    if source == "brightdata_mcp":
        return "trusted_scrape"
    return "fallback_search" if url else "untrusted"


def source_tier_priority(tier: str) -> int:
    return SOURCE_TIER_PRIORITY.get(str(tier or "untrusted"), SOURCE_TIER_PRIORITY["untrusted"])


def preferred_domains_for_topic(topic: str, competition: str = "") -> list[str]:
    """Return source-target domains in the order they should be searched."""
    topic = (topic or "").lower()
    competition = competition.lower()
    official = ["uefa.com"] if "champions league" in competition else []
    if topic in {"fixture", "h2h", "storylines"}:
        return official + ["premierleague.com", "espn.com", "bbc.co.uk", "skysports.com", "reuters.com"]
    if topic in {"team_news", "lineup"}:
        return official + [
            "arsenal.com",
            "psg.fr",
            "premierleague.com",
            "bbc.co.uk",
            "skysports.com",
            "theanalyst.com",
            "nbcsports.com",
            "sportsmole.co.uk",
            "reuters.com",
            "theguardian.com",
            "theathletic.com",
            "espn.com",
        ]
    if topic == "weather":
        return ["metoffice.gov.uk", "weather.com", "accuweather.com", "bbc.co.uk"]
    return official + ["espn.com", "bbc.co.uk", "skysports.com", "reuters.com"]


def filter_allowed_search_results(
    results: list[dict[str, Any]],
    *,
    home_team: str,
    away_team: str,
    topic: str,
    max_results: int = 3,
) -> tuple[list[dict[str, Any]], list[EvidenceItem]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[EvidenceItem] = []
    for result in results:
        status, reason = validate_search_result(result, home_team=home_team, away_team=away_team, topic=topic)
        if status == "accepted":
            enriched = dict(result)
            source = str(enriched.get("source") or enriched.get("publisher") or "")
            tier = classify_source_tier(str(enriched.get("url") or ""), source)
            enriched["validation_status"] = "accepted"
            enriched["source_tier"] = tier
            enriched["source_policy_label"] = _source_policy_label(tier)
            enriched["confidence"] = _confidence_for_tier(tier)
            accepted.append(enriched)
        else:
            rejected.append(_evidence_from_result(
                result,
                topic=topic,
                team_scope=home_team if home_team and _mentions_team(_result_text(result), home_team) else "",
                match_scope=f"{home_team} vs {away_team}",
                status="rejected",
                reason=reason,
            ))
    accepted.sort(
        key=lambda item: (
            source_tier_priority(str(item.get("source_tier") or "")),
            -float(item.get("score") or 0.0),
            str(item.get("title") or ""),
        )
    )
    return accepted[:max_results], rejected


def validate_search_result(
    result: dict[str, Any],
    *,
    home_team: str,
    away_team: str,
    topic: str = "general",
) -> tuple[str, str]:
    url = str(result.get("url") or "")
    text = _result_text(result)
    if not is_allowed_url(url):
        return "rejected", "domain_not_allowed"
    if any(term in text for term in OTHER_SPORT_TERMS):
        return "rejected", "other_sport"
    teams = [team for team in (home_team, away_team) if team]
    if teams and not any(_mentions_team(text, team) for team in teams):
        return "rejected", "missing_team_context"
    if _looks_like_other_fixture(text, home_team, away_team):
        return "rejected", "other_fixture"
    if topic in {"team_news", "lineup"} and not _is_current_fixture_relevant(text, home_team, away_team):
        if _has_other_fixture_context(text):
            return "rejected", "other_fixture_context"
    if topic in {"team_news", "lineup"} and not (
        _is_current_fixture_relevant(text, home_team, away_team)
        or _is_explicit_team_news_item(text)
    ):
        return "rejected", "team_adjacent_without_fixture_or_team_news_context"
    return "accepted", ""


def validate_scraped_content(
    content: str,
    *,
    url: str,
    home_team: str,
    away_team: str,
) -> tuple[str, str]:
    """Validate scraped page text before it can become synthesis evidence."""
    if not is_allowed_url(url):
        return "rejected", "domain_not_allowed"
    text = f"{content or ''} {url}".lower()
    if any(term in text for term in OTHER_SPORT_TERMS):
        return "rejected", "other_sport"
    teams = [team for team in (home_team, away_team) if team]
    if teams and not any(_mentions_team(text, team) for team in teams):
        return "rejected", "missing_team_context"
    if _looks_like_other_fixture(text, home_team, away_team):
        return "rejected", "other_fixture"
    return "accepted", ""


def _gate_news(
    news: dict[str, Any],
    home_team: str,
    away_team: str,
    match_scope: str,
    accepted: list[EvidenceItem],
    rejected: list[EvidenceItem],
    degraded_sections: list[str],
    unavailable_facts: list[str],
) -> None:
    if not isinstance(news, dict):
        return
    for side, team in (("home_team", home_team), ("away_team", away_team)):
        team_news = news.get(side)
        if not isinstance(team_news, dict):
            continue
        kept_items = []
        rejected_team_items = 0
        for item in team_news.get("news_items", []) or []:
            status, reason = validate_search_result(
                item,
                home_team=team,
                away_team=away_team if team == home_team else home_team,
                topic="team_news",
            )
            if status == "accepted" or _is_safe_structured_news_item(item, team, reason):
                kept_items.append(item)
                accepted.append(_evidence_from_result(item, topic="team_news", team_scope=team, match_scope=match_scope, status="accepted"))
            else:
                rejected_team_items += 1
                rejected.append(_evidence_from_result(item, topic="team_news", team_scope=team, match_scope=match_scope, status="rejected", reason=reason))
        team_news["news_items"] = kept_items
        if rejected_team_items:
            team_news["synthesis"] = ""
        if not team_news.get("injuries"):
            team_news["injury_status"] = {
                "status": "unverified",
                "summary": "No verified injury report was accepted in this run",
            }
        brightdata_status = team_news.get("brightdata_status")
        if isinstance(brightdata_status, dict):
            if not brightdata_status.get("available"):
                degraded_sections.append(f"brightdata_team_news:{team}")
                unavailable_facts.append(f"{team} BrightData scrape enrichment")
            elif brightdata_status.get("degraded_count", 0):
                degraded_sections.append(f"brightdata_team_news:{team}")
        if not kept_items and not team_news.get("injuries"):
            team_news["synthesis"] = ""
            team_news["lineup_status"] = {"status": "unavailable", "summary": ""}
            team_news["validation_status"] = "degraded"
            degraded_sections.append(f"team_news:{team}")
            unavailable_facts.append(f"{team} verified team news")
        elif kept_items:
            team_news["validation_status"] = "accepted"


def _gate_weather(
    weather: dict[str, Any],
    match_scope: str,
    accepted: list[EvidenceItem],
    rejected: list[EvidenceItem],
    degraded_sections: list[str],
    unavailable_facts: list[str],
) -> None:
    if not isinstance(weather, dict) or not weather:
        return
    urls = _extract_urls(weather)
    trusted_urls = [url for url in urls if classify_source_tier(url) == "weather"]
    data_source = _weather_data_source(weather)
    has_structured_conditions = bool(
        weather.get("current_conditions", {}).get("temperature_c") is not None
        or weather.get("current_conditions", {}).get("wind_kmh") is not None
    )
    if trusted_urls or (has_structured_conditions and data_source not in {"tavily_search", "unavailable"}):
        for url in trusted_urls:
            accepted.append(EvidenceItem(
                claim="Verified weather source available",
                source_name="weather",
                url=url,
                source_tier=classify_source_tier(url),
                topic="weather",
                match_scope=match_scope,
                confidence=0.8,
                validation_status="accepted",
            ))
        weather["validation_status"] = "accepted"
        return

    for url in urls:
        rejected.append(EvidenceItem(
            claim="Weather source rejected",
            source_name="weather",
            url=url,
            source_tier=classify_source_tier(url),
            topic="weather",
            match_scope=match_scope,
            confidence=0.0,
            validation_status="rejected",
            reason="untrusted_weather_source",
        ))
    weather["current_conditions"] = {}
    weather["forecast"] = []
    weather["sport_impact"] = {}
    weather["narrative"] = ""
    weather["validation_status"] = "degraded"
    degraded_sections.append("weather")
    unavailable_facts.append("verified match weather")


def _gate_historical(
    historical: dict[str, Any],
    home_team: str,
    away_team: str,
    match_scope: str,
    accepted: list[EvidenceItem],
    rejected: list[EvidenceItem],
    degraded_sections: list[str],
    unavailable_facts: list[str],
) -> None:
    if not isinstance(historical, dict):
        return
    h2h = historical.get("h2h_history", {})
    if isinstance(h2h, dict):
        total = int(h2h.get("total_matches") or 0)
        recent = h2h.get("recent_matches") or []
        wins = int(h2h.get("team1_wins") or 0) + int(h2h.get("team2_wins") or 0) + int(h2h.get("draws") or 0)
        source_urls = [url for url in _extract_urls(h2h) if source_tier_priority(classify_source_tier(url)) <= source_tier_priority("trusted_media")]
        if total <= 0 and not recent and wins <= 0 and not source_urls:
            h2h.update({
                "status": "unavailable",
                "total_matches": None,
                "team1_wins": None,
                "team2_wins": None,
                "draws": None,
                "recent_matches": [],
                "note": "Trusted H2H data unavailable in this run",
            })
            historical["narrative"] = ""
            degraded_sections.append("historical_h2h")
            unavailable_facts.append(f"{home_team} vs {away_team} verified H2H")
        else:
            accepted_url = source_urls[0] if source_urls else ""
            accepted.append(EvidenceItem(
                claim="Verified H2H data available",
                source_name="historical",
                url=accepted_url,
                source_tier=classify_source_tier(accepted_url) if accepted_url else "structured",
                topic="h2h",
                match_scope=match_scope,
                confidence=_confidence_for_tier(classify_source_tier(accepted_url)) if accepted_url else 0.75,
                validation_status="accepted",
            ))

    kept_storylines = []
    for story in historical.get("storylines", []) or []:
        text = f"{story.get('title', '')} {story.get('description', '')}".lower()
        url = str(story.get("url") or "")
        source = str(story.get("source") or "")
        tier = classify_source_tier(url, source)
        if (
            not text.strip()
            or any(term in text for term in OTHER_SPORT_TERMS)
            or _looks_like_other_fixture(text, home_team, away_team)
            or source_tier_priority(tier) > source_tier_priority("trusted_media")
        ):
            rejected.append(EvidenceItem(
                claim=story.get("title", "Storyline rejected"),
                source_name=story.get("source", "search"),
                url=url,
                source_tier=tier,
                topic="storylines",
                match_scope=match_scope,
                validation_status="rejected",
                reason="irrelevant_storyline",
            ))
            continue
        story["source_tier"] = tier
        story["source_policy_label"] = _source_policy_label(tier)
        story["validation_status"] = "accepted"
        accepted.append(_evidence_from_result(story, topic="storylines", team_scope="", match_scope=match_scope, status="accepted"))
        kept_storylines.append(story)
    historical["storylines"] = kept_storylines
    if not kept_storylines:
        degraded_sections.append("storylines")
        unavailable_facts.append("verified match storylines")


def _gate_player_research(
    player_research: dict[str, Any],
    home_team: str,
    away_team: str,
    match_scope: str,
    accepted: list[EvidenceItem],
    degraded_sections: list[str],
    unavailable_facts: list[str],
) -> None:
    if not isinstance(player_research, dict):
        return

    for side, team in (("home_team", home_team), ("away_team", away_team)):
        squad = player_research.get(side)
        if not isinstance(squad, dict):
            continue

        players = squad.get("players") if isinstance(squad.get("players"), list) else []
        valid_players = [
            player for player in players
            if isinstance(player, dict)
            and str(player.get("name") or "").strip()
            and str(player.get("name") or "").strip().lower() != "unknown"
        ]
        sources = {
            str(source).strip().lower()
            for source in (squad.get("data_sources") or [])
            if str(source).strip()
        }
        has_structured_source = bool(sources & {"espn", "fbref", "football-data", "football_data", "transfermarkt"})

        if len(valid_players) >= 11 and (has_structured_source or squad.get("data_status") == "accepted"):
            squad["validation_status"] = "accepted"
            squad["verified_player_count"] = len(valid_players)
            accepted.append(EvidenceItem(
                claim=f"{team} structured squad list available with {len(valid_players)} players",
                source_name="ESPN" if "espn" in sources or not sources else ", ".join(sorted(sources)),
                source_tier="structured",
                topic="player_research",
                team_scope=team,
                match_scope=match_scope,
                confidence=0.88,
                validation_status="accepted",
            ))
            continue

        squad["validation_status"] = "degraded"
        degraded_sections.append(f"player_research:{team}")
        unavailable_facts.append(f"{team} verified squad list")


def _looks_like_other_fixture(text: str, home_team: str, away_team: str) -> bool:
    normalized = text.lower()
    current_teams = [team for team in (home_team, away_team) if team]
    if not any(marker in normalized for marker in (" vs ", " v ", " versus ")):
        return False
    return (
        any(_mentions_team(normalized, team) for team in current_teams)
        and not all(_mentions_team(normalized, team) for team in current_teams)
    )


def _evidence_from_result(
    result: dict[str, Any],
    *,
    topic: str,
    team_scope: str,
    match_scope: str,
    status: str,
    reason: str = "",
) -> EvidenceItem:
    url = str(result.get("url") or "")
    source = str(result.get("source") or result.get("publisher") or _domain(url) or "search")
    return EvidenceItem(
        claim=str(result.get("title") or result.get("content") or "")[:300],
        source_name=source,
        url=url,
        source_tier=classify_source_tier(url, source),
        topic=topic,
        team_scope=team_scope,
        match_scope=match_scope,
        confidence=_confidence_for_tier(classify_source_tier(url, source)) if status == "accepted" else 0.0,
        validation_status=status,
        reason=reason,
        published_at=str(
            result.get("published_at")
            or result.get("published")
            or result.get("published_date")
            or result.get("date")
            or ""
        ),
    )


def _confidence_for_tier(tier: str) -> float:
    if tier == "official":
        return 0.95
    if tier in {"structured", "weather"}:
        return 0.88
    if tier == "trusted_media":
        return 0.78
    if tier == "trusted_scrape":
        return 0.72
    if tier == "fallback_search":
        return 0.45
    return 0.0


def _source_policy_label(tier: str) -> str:
    if tier == "official":
        return "official fact"
    if tier in {"structured", "weather"}:
        return "structured source"
    if tier == "trusted_media":
        return "trusted media reporting"
    if tier == "trusted_scrape":
        return "scraped accepted source"
    return "candidate only"


def _extract_urls(value: Any) -> list[str]:
    urls: list[str] = []

    def _walk(item: Any) -> None:
        if isinstance(item, dict):
            for key in ("url", "source_url", "link"):
                url = item.get(key)
                if isinstance(url, str) and url.startswith(("http://", "https://")) and url not in urls:
                    urls.append(url)
            for key in ("source_urls", "urls"):
                source_urls = item.get(key)
                if isinstance(source_urls, list):
                    for url in source_urls:
                        if isinstance(url, str) and url.startswith(("http://", "https://")) and url not in urls:
                            urls.append(url)
            for child in item.values():
                _walk(child)
        elif isinstance(item, list):
            for child in item:
                _walk(child)

    _walk(value)
    return urls


def _result_text(result: dict[str, Any]) -> str:
    return f"{result.get('title', '')} {result.get('content', '')} {result.get('url', '')}".lower()


def _is_safe_structured_news_item(item: dict[str, Any], team: str, rejection_reason: str) -> bool:
    source = str(item.get("source", "")).lower()
    if source != "espn":
        return False
    if rejection_reason in {"other_sport", "other_fixture"}:
        return False
    text = _result_text(item)
    return bool(team and _mentions_team(text, team) and _is_explicit_team_news_item(text))


def _is_current_fixture_relevant(text: str, home_team: str, away_team: str) -> bool:
    teams = [team for team in (home_team, away_team) if team]
    return len(teams) == 2 and all(_mentions_team(text, team) for team in teams)


def _mentions_team(text: str, team_name: str) -> bool:
    normalized = text.lower()
    return any(alias in normalized for alias in _team_aliases(team_name))


def _team_aliases(team_name: str) -> list[str]:
    cleaned = str(team_name or "").strip().lower()
    aliases = [cleaned] if cleaned else []
    if "paris saint-germain" in cleaned or "paris saint germain" in cleaned:
        aliases.extend(["psg", "paris"])
    words = [word for word in cleaned.replace("-", " ").split() if word]
    meaningful = [word for word in words if word not in {"fc", "cf", "sc", "ac", "club", "football"}]
    if len(meaningful) >= 2:
        aliases.append("".join(word[0] for word in meaningful))
    elif meaningful:
        aliases.append(meaningful[0])
    return list(dict.fromkeys(alias for alias in aliases if alias))


def _has_other_fixture_context(text: str) -> bool:
    return any(
        marker in text
        for marker in (
            " trip",
            " visit",
            " visits",
            " derby",
            " against ",
            " before ",
            " ahead of ",
            " build-up to ",
        )
    )


def _is_explicit_team_news_item(text: str) -> bool:
    return any(
        marker in text
        for marker in (
            "team news",
            "injury",
            "injuries",
            "injured",
            "fitness",
            "availability",
            "available",
            "unavailable",
            "doubt",
            "doubtful",
            "ruled out",
            "suspension",
            "suspended",
            "ban",
            "banned",
            "lineup",
            "line-up",
            "starting xi",
            "team sheet",
            "squad",
            "selection",
            "returns",
            "returning",
        )
    )


def _weather_data_source(weather: dict[str, Any]) -> str:
    data_source = weather.get("data_source")
    if isinstance(data_source, str) and data_source:
        return data_source.lower()
    forecast = weather.get("forecast")
    if isinstance(forecast, list) and forecast and isinstance(forecast[0], dict):
        forecast_source = forecast[0].get("data_source")
        if isinstance(forecast_source, str):
            return forecast_source.lower()
    return ""


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host
