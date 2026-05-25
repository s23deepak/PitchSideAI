"""Evidence normalization and quality gates for commentary notes."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse


TRUSTED_OFFICIAL_DOMAINS = {
    "chelseafc.com",
    "safc.com",
    "sunderlandafc.com",
    "premierleague.com",
}
TRUSTED_STRUCTURED_DOMAINS = {
    "espn.com",
    "espn.co.uk",
    "football-data.org",
}
TRUSTED_WEATHER_DOMAINS = {
    "metoffice.gov.uk",
    "weather.com",
    "accuweather.com",
    "bbc.co.uk",
}
ALLOWED_DOMAINS = TRUSTED_OFFICIAL_DOMAINS | TRUSTED_STRUCTURED_DOMAINS | TRUSTED_WEATHER_DOMAINS

OTHER_SPORT_TERMS = {
    "nba",
    "knicks",
    "basketball",
    "cricket",
    "ipl",
    "rcb",
    "srh",
    "tennis",
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
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
        return "trusted_official"
    if domain and any(domain == d or domain.endswith(f".{d}") for d in TRUSTED_STRUCTURED_DOMAINS):
        return "trusted_structured"
    if domain and any(domain == d or domain.endswith(f".{d}") for d in TRUSTED_WEATHER_DOMAINS):
        return "trusted_weather"
    if source in {"espn", "football_data", "football-data"}:
        return "trusted_structured"
    if source == "brightdata_mcp":
        return "trusted_scrape"
    return "search_result" if url else "untrusted"


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
        status, reason = validate_search_result(result, home_team=home_team, away_team=away_team)
        if status == "accepted":
            accepted.append(result)
            if len(accepted) >= max_results:
                break
        else:
            rejected.append(_evidence_from_result(
                result,
                topic=topic,
                team_scope=home_team if home_team and home_team.lower() in _result_text(result) else "",
                match_scope=f"{home_team} vs {away_team}",
                status="rejected",
                reason=reason,
            ))
    return accepted, rejected


def validate_search_result(
    result: dict[str, Any],
    *,
    home_team: str,
    away_team: str,
) -> tuple[str, str]:
    url = str(result.get("url") or "")
    text = _result_text(result)
    if not is_allowed_url(url):
        return "rejected", "domain_not_allowed"
    if any(term in text for term in OTHER_SPORT_TERMS):
        return "rejected", "other_sport"
    teams = [team.lower() for team in (home_team, away_team) if team]
    if teams and not any(team in text for team in teams):
        return "rejected", "missing_team_context"
    if _looks_like_other_fixture(text, home_team, away_team):
        return "rejected", "other_fixture"
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
    teams = [team.lower() for team in (home_team, away_team) if team]
    if teams and not any(team in text for team in teams):
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
        for item in team_news.get("news_items", []) or []:
            status, reason = validate_search_result(item, home_team=team, away_team=away_team if team == home_team else home_team)
            if status == "accepted" or _is_safe_structured_news_item(item, team, reason):
                kept_items.append(item)
                accepted.append(_evidence_from_result(item, topic="team_news", team_scope=team, match_scope=match_scope, status="accepted"))
            else:
                rejected.append(_evidence_from_result(item, topic="team_news", team_scope=team, match_scope=match_scope, status="rejected", reason=reason))
        team_news["news_items"] = kept_items
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
    trusted_urls = [url for url in urls if classify_source_tier(url).startswith("trusted_weather")]
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
        if total <= 0 and not recent and wins <= 0:
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
            accepted.append(EvidenceItem(
                claim="Verified H2H data available",
                source_name="historical",
                source_tier="trusted_structured",
                topic="h2h",
                match_scope=match_scope,
                confidence=0.75,
                validation_status="accepted",
            ))

    kept_storylines = []
    for story in historical.get("storylines", []) or []:
        text = f"{story.get('title', '')} {story.get('description', '')}".lower()
        if not text.strip() or any(term in text for term in OTHER_SPORT_TERMS) or _looks_like_other_fixture(text, home_team, away_team):
            rejected.append(EvidenceItem(
                claim=story.get("title", "Storyline rejected"),
                source_name=story.get("source", "search"),
                topic="storylines",
                match_scope=match_scope,
                validation_status="rejected",
                reason="irrelevant_storyline",
            ))
            continue
        kept_storylines.append(story)
    historical["storylines"] = kept_storylines
    if not kept_storylines:
        degraded_sections.append("storylines")
        unavailable_facts.append("verified match storylines")


def _looks_like_other_fixture(text: str, home_team: str, away_team: str) -> bool:
    normalized = text.lower()
    current_teams = [team.lower() for team in (home_team, away_team) if team]
    if not any(marker in normalized for marker in (" vs ", " v ", " versus ")):
        return False
    return any(team in normalized for team in current_teams) and not all(team in normalized for team in current_teams)


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
        confidence=0.8 if status == "accepted" else 0.0,
        validation_status=status,
        reason=reason,
    )


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
    return bool(team and team.lower() in text)


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
