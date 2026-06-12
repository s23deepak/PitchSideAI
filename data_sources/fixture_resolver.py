"""
Generic fixture resolver for commentary-notes context.

The resolver searches for authoritative fixture pages using the requested
teams and competition, then extracts venue, kickoff, and named player evidence.
It intentionally does not contain competition-specific or team-specific rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from dateutil import parser as date_parser

from data_sources.cache import DataCache
from data_sources.tavily_search_service import TavilySearchService
from quality.evidence import classify_source_tier, preferred_domains_for_topic, source_tier_priority

logger = logging.getLogger(__name__)


VENUE_PATTERN = re.compile(
    r"(?:venue|stadium)\s*:\s*(?P<label>[A-ZÀ-Þ][\wÀ-ÿ'’ .-]{2,80})"
    r"|(?:at|hosted at|held at|played at|take place at|takes place at)\s+"
    r"(?:the\s+)?(?P<at>[A-ZÀ-Þ][\wÀ-ÿ'’ .-]{2,80}?"
    r"(?:Stadium|Arena|Aréna|Park|Ground|Bowl|Field|Dome|Centre|Center))",
    re.I,
)
FREE_VENUE_PATTERN = re.compile(
    r"\b([A-ZÀ-Þ][\wÀ-ÿ'’.-]+(?:\s+[A-ZÀ-Þ][\wÀ-ÿ'’.-]+){0,4}\s+"
    r"(?:Stadium|Arena|Aréna|Park|Ground|Bowl|Field|Dome|Centre|Center))\b"
)
DATE_PATTERNS = [
    re.compile(r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*,?\s+[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}(?:\s+at\s+\d{1,2}:?\d{0,2}\s*(?:CET|CEST|UTC|GMT|BST|ET|PT)?)?", re.I),
    re.compile(r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*,?\s+\d{1,2}\s+[A-Z][a-z]+\s+\d{4}(?:\s+at\s+\d{1,2}:?\d{0,2}\s*(?:CET|CEST|UTC|GMT|BST|ET|PT)?)?", re.I),
    re.compile(r"\b[A-Z][a-z]+\s+\d{1,2},\s+\d{4}(?:\s+at\s+\d{1,2}:?\d{0,2}\s*(?:CET|CEST|UTC|GMT|BST|ET|PT)?)?", re.I),
    re.compile(r"\b\d{1,2}\s+[A-Z][a-z]+\s+\d{4}(?:\s+at\s+\d{1,2}:?\d{0,2}\s*(?:CET|CEST|UTC|GMT|BST|ET|PT)?)?", re.I),
    re.compile(r"\b\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)?\b"),
]
TZINFOS = {
    "UTC": 0,
    "GMT": 0,
    "BST": 3600,
    "CET": 3600,
    "CEST": 7200,
    "ET": -5 * 3600,
    "PT": -8 * 3600,
}
PERSON_PATTERN = re.compile(
    r"\b([A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+(?:\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+){1,3})\b"
)
POSITION_KEYWORDS = {
    "goalkeeper": "GK",
    "keeper": "GK",
    "defender": "Defender",
    "centre-back": "Defender",
    "center-back": "Defender",
    "full-back": "Defender",
    "right-back": "Defender",
    "left-back": "Defender",
    "midfielder": "Midfielder",
    "midfield": "Midfielder",
    "winger": "Forward",
    "forward": "Forward",
    "striker": "Forward",
    "attacker": "Forward",
}
NON_PERSON_TERMS = {
    "Against Bayern",
    "Arsenal",
    "Assistant Referee Bastian Dankert",
    "Bayern Munich",
    "Final",
    "French Ligue",
    "Holders Paris",
    "Les Parisiens",
    "Marc Atkins",
    "Mark Leech",
    "Semi Final",
    "Quarter Final",
    "Match Preview",
    "Kick Off",
    "Team News",
    "Match News",
    "Kickoff",
    "Pass-happy PSG",
    "Paris St Germain",
    "Preview",
    "Real Madrid",
    "Stamford Bridge",
    "Stadium",
    "Arena",
    "Aréna",
    "The Gunners",
    "UEFA Champions League Round",
}
PERSON_PREFIX_STOPWORDS = {
    "Against",
    "And",
    "Assistant",
    "Youngster",
    "Manager",
    "Coach",
    "Captain",
    "Goalkeeper",
    "Defender",
    "Midfielder",
    "Forward",
    "Striker",
    "Winger",
    "French",
    "Holders",
    "Pass-happy",
    "The",
}
PERSON_TOKEN_STOPWORDS = {
    "AFP",
    "Assistant",
    "Bridge",
    "Champions",
    "FIFE",
    "Fourth",
    "GER",
    "Getty",
    "Image",
    "Images",
    "League",
    "Photo",
    "Referee",
    "Reuters",
    "Round",
    "Stamford",
    "SUI",
    "UEFA",
    "Video",
    "For",
}
NON_PLAYER_SENTENCE_MARKERS = (
    "afp via getty",
    "assistant referee",
    "fourth official",
    "getty images",
    "photo by",
    "video assistant",
)


@dataclass
class ResolvedPlayer:
    name: str
    team_side: str
    position: str = "Unknown"
    source_url: str = ""
    source_title: str = ""
    evidence: str = ""
    confidence: float = 0.6

    def to_player_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "position": self.position,
            "stats": {},
            "profile": self.evidence[:180],
            "data_source": "fixture_resolver",
            "source_urls": [self.source_url] if self.source_url else [],
            "evidence": self.evidence,
            "confidence": self.confidence,
            "candidate_status": "fixture-evidence; not confirmed starter",
        }


@dataclass
class FixtureResolution:
    venue: str = ""
    match_datetime: str = ""
    venue_lat: float = 0.0
    venue_lon: float = 0.0
    confidence: float = 0.0
    sources: List[Dict[str, str]] = field(default_factory=list)
    players: Dict[str, List[ResolvedPlayer]] = field(
        default_factory=lambda: {"home_team": [], "away_team": [], "unknown": []}
    )
    status: str = "unavailable"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "venue": self.venue,
            "match_datetime": self.match_datetime,
            "venue_lat": self.venue_lat,
            "venue_lon": self.venue_lon,
            "confidence": self.confidence,
            "sources": self.sources,
            "players": {
                side: [player.to_player_dict() for player in players]
                for side, players in self.players.items()
            },
            "status": self.status,
        }


class FixtureResolver:
    """Resolve fixture facts from current, fixture-specific web evidence."""

    def __init__(
        self,
        *,
        cache: Optional[DataCache] = None,
        search_service: Optional[TavilySearchService] = None,
    ) -> None:
        self.cache = cache or DataCache(ttl_seconds=3600)
        self.search_service = search_service or TavilySearchService(cache=self.cache)

    async def resolve(
        self,
        *,
        home_team: str,
        away_team: str,
        sport: str,
        competition: str = "",
    ) -> Dict[str, Any]:
        cache_key = "|".join([home_team, away_team, sport, competition]).lower()
        cached = self.cache.get("fixture_resolution", cache_key)
        if cached:
            return cached

        query = (
            f"{home_team} vs {away_team} {competition} {sport} official "
            "fixture venue date kickoff match preview squads key players"
        ).strip()
        search = await self.search_service.search(
            query,
            search_depth="advanced",
            topic="general",
            max_results=8,
            include_answer=True,
            cache_namespace="fixture_resolution_search",
            include_domains=preferred_domains_for_topic("fixture", competition),
        )

        resolution = self._resolve_from_results(
            home_team=home_team,
            away_team=away_team,
            competition=competition,
            results=search.get("results", []),
            answer=search.get("answer", ""),
        )
        payload = resolution.to_dict()
        self.cache.set("fixture_resolution", cache_key, payload)
        return payload

    def _resolve_from_results(
        self,
        *,
        home_team: str,
        away_team: str,
        competition: str,
        results: List[Dict[str, Any]],
        answer: str = "",
    ) -> FixtureResolution:
        resolution = FixtureResolution()
        candidates = []
        for result in results:
            text = self._result_text(result)
            if not self._is_relevant_fixture_text(text, home_team, away_team, competition):
                continue
            candidates.append(result)
        candidates.sort(key=lambda result: self._source_rank(result, competition))

        for result in candidates:
            text = self._result_text(result)
            source = {
                "title": str(result.get("title") or ""),
                "url": str(result.get("url") or ""),
                "source_tier": classify_source_tier(str(result.get("url") or ""), str(result.get("source") or "")),
            }
            if source not in resolution.sources:
                resolution.sources.append(source)

            if not resolution.venue:
                resolution.venue = self._extract_venue(text)
            if not resolution.match_datetime:
                resolution.match_datetime = self._extract_datetime(text)

            self._merge_players(
                resolution,
                home_team=home_team,
                away_team=away_team,
                competition=competition,
                text=text,
                source=source,
            )

        answer_is_relevant = bool(answer) and self._is_relevant_fixture_text(
            answer,
            home_team,
            away_team,
            competition,
        )
        if not resolution.venue and answer_is_relevant:
            resolution.venue = self._extract_venue(answer)
        if not resolution.match_datetime and answer_is_relevant:
            resolution.match_datetime = self._extract_datetime(answer)

        resolution.confidence = self._score_resolution(resolution)
        resolution.status = "accepted" if resolution.confidence >= 0.45 else "unavailable"
        return resolution

    def _source_rank(self, result: Dict[str, Any], competition: str = "") -> Tuple[int, float, float, str]:
        tier = classify_source_tier(str(result.get("url") or ""), str(result.get("source") or ""))
        return (
            source_tier_priority(tier),
            -self._fixture_specificity_score(result, competition),
            -float(result.get("score") or 0.0),
            str(result.get("title") or ""),
        )

    def _fixture_specificity_score(self, result: Dict[str, Any], competition: str = "") -> float:
        """Prefer exact fixture pages over broad or older official club pages."""
        text = self._result_text(result).lower()
        title = str(result.get("title") or "").lower()
        url = str(result.get("url") or "").lower()
        competition_terms = [
            term for term in re.split(r"\W+", competition.lower())
            if len(term) > 3
        ]

        score = 0.0
        if competition_terms:
            score += 0.5 * sum(1 for term in competition_terms if term in text)
            if all(term in text for term in competition_terms):
                score += 2.0

        if "final" in competition.lower():
            if "final" in title or "final" in url:
                score += 4.0
            elif re.search(r"\bfinal\b", text):
                score += 1.0

        if "champions league" in competition.lower() and "uefa.com/uefachampionsleague/match/" in url:
            score += 5.0
        if re.search(r"(?:paris|psg)[-/ ]vs[-/ ]arsenal|arsenal[-/ ]vs[-/ ](?:paris|psg)", url):
            score += 2.0

        return score

    def _result_text(self, result: Dict[str, Any]) -> str:
        return " ".join(
            str(result.get(key) or "")
            for key in ("title", "content", "raw_content", "url")
        )

    def _is_relevant_fixture_text(
        self,
        text: str,
        home_team: str,
        away_team: str,
        competition: str,
    ) -> bool:
        lowered = text.lower()
        if not self._mentions_team(lowered, home_team) or not self._mentions_team(lowered, away_team):
            return False
        if competition:
            competition_terms = [term for term in re.split(r"\W+", competition.lower()) if len(term) > 3]
            if competition_terms and not any(term in lowered for term in competition_terms):
                return False
        return True

    def _mentions_team(self, lowered_text: str, team_name: str) -> bool:
        return any(alias.lower() in lowered_text for alias in self._team_aliases(team_name))

    def _team_aliases(self, team_name: str) -> List[str]:
        aliases = [team_name]
        normalized = team_name.lower()
        if "paris saint-germain" in normalized or "paris saint germain" in normalized:
            aliases.extend(["PSG", "Paris"])
        words = [word for word in re.split(r"[\s-]+", team_name) if word]
        if len(words) > 1:
            aliases.append(" ".join(words))
        meaningful = [
            word for word in words
            if word.lower() not in {"fc", "cf", "sc", "ac", "club", "football"}
        ]
        if len(meaningful) >= 2:
            acronym = "".join(word[0] for word in meaningful if word[0].isalpha()).upper()
            if len(acronym) >= 2:
                aliases.append(acronym)
        elif meaningful:
            aliases.append(meaningful[0])
        return list(dict.fromkeys(aliases))

    def _extract_venue(self, text: str) -> str:
        for match in VENUE_PATTERN.finditer(text):
            venue = (match.group("label") or match.group("at") or "").strip(" .,-")
            cleaned = self._clean_venue(venue)
            if cleaned:
                return cleaned
        for match in FREE_VENUE_PATTERN.finditer(text):
            cleaned = self._clean_venue(match.group(1))
            if cleaned:
                return cleaned
        return ""

    def _clean_venue(self, venue: str) -> str:
        venue = re.sub(r"\s+", " ", venue).strip(" .,-")
        if not venue or len(venue) < 4:
            return ""
        if any(term.lower() in venue.lower() for term in ("League Final", "Match Preview")):
            return ""
        return venue[:120]

    def _extract_datetime(self, text: str) -> str:
        candidates = self._datetime_candidates(text)
        if candidates:
            candidates.sort(key=lambda item: item[0], reverse=True)
            return candidates[0][1]
        return ""

    def _datetime_candidates(self, text: str) -> List[Tuple[float, str]]:
        candidates: List[Tuple[float, str]] = []
        for pattern in DATE_PATTERNS:
            for match in pattern.finditer(text):
                raw = match.group(0).strip()
                try:
                    parsed = date_parser.parse(raw, fuzzy=True, tzinfos=TZINFOS)
                    if parsed.year < 2000:
                        continue
                    value = self._with_context_time(parsed, text, match.start(), match.end()).isoformat()
                except Exception:
                    value = raw
                score = self._score_datetime_candidate(text, match.start(), match.end(), raw)
                candidates.append((score, value))
        return candidates

    def _with_context_time(self, parsed: datetime, text: str, start: int, end: int) -> datetime:
        if parsed.hour or parsed.minute or parsed.second:
            return parsed
        context = text[max(0, start - 120): min(len(text), end + 120)]
        time_match = re.search(
            r"\b(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<ampm>am|pm)?\s*(?P<tz>CET|CEST|UTC|GMT|BST|ET|PT)\b",
            context,
            flags=re.I,
        )
        if not time_match:
            return parsed
        hour = int(time_match.group("hour"))
        minute = int(time_match.group("minute") or 0)
        ampm = (time_match.group("ampm") or "").lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        tz_name = time_match.group("tz").upper()
        tzinfo = timezone(timedelta(seconds=TZINFOS[tz_name])) if tz_name in TZINFOS else parsed.tzinfo
        return parsed.replace(hour=hour, minute=minute, tzinfo=tzinfo)

    def _score_datetime_candidate(self, text: str, start: int, end: int, raw: str) -> float:
        context = text[max(0, start - 180): min(len(text), end + 180)].lower()
        score = 0.0
        if re.search(r"\b(?:kick-?off|begin|start|take place|takes place|played|will be played|scheduled|date)\b", context):
            score += 4.0
        if re.search(r"\b(?:venue|stadium|arena|host|final)\b", context):
            score += 2.0
        if re.search(r"\d{1,2}:?\d{0,2}\s*(?:CET|CEST|UTC|GMT|BST|ET|PT)\b", raw, re.I):
            score += 2.0
        if re.search(r"\b(?:published|updated|crawled|last updated|article)\b", context):
            score -= 6.0
        return score

    def _merge_players(
        self,
        resolution: FixtureResolution,
        *,
        home_team: str,
        away_team: str,
        competition: str,
        text: str,
        source: Dict[str, str],
    ) -> None:
        for sentence in self._sentences(text):
            side = self._sentence_side(sentence, home_team, away_team)
            for name in self._extract_person_names(sentence, home_team, away_team, competition):
                if self._player_seen(resolution, name):
                    continue
                player = ResolvedPlayer(
                    name=name,
                    team_side=side,
                    position=self._infer_position(sentence),
                    source_url=source.get("url", ""),
                    source_title=source.get("title", ""),
                    evidence=sentence[:260],
                    confidence=0.7 if side in {"home_team", "away_team"} else 0.55,
                )
                resolution.players.setdefault(side, []).append(player)

    def _sentences(self, text: str) -> List[str]:
        compact = re.sub(r"\s+", " ", text)
        return [part.strip() for part in re.split(r"(?<=[.!?])\s+", compact) if part.strip()]

    def _sentence_side(self, sentence: str, home_team: str, away_team: str) -> str:
        lowered = sentence.lower()
        home_hit = self._mentions_team(lowered, home_team)
        away_hit = self._mentions_team(lowered, away_team)
        if home_hit and not away_hit:
            return "home_team"
        if away_hit and not home_hit:
            return "away_team"
        return "unknown"

    def _extract_person_names(
        self,
        sentence: str,
        home_team: str,
        away_team: str,
        competition: str,
    ) -> List[str]:
        names: List[str] = []
        excluded = self._excluded_name_phrases(home_team, away_team, competition)
        for match in PERSON_PATTERN.finditer(sentence):
            name = match.group(1).strip()
            if self._is_non_player_name(name, sentence, excluded):
                continue
            names.append(name)
        return names

    def _is_non_player_name(self, name: str, sentence: str, excluded: set[str]) -> bool:
        if name in excluded or any(name.lower() == item.lower() for item in excluded):
            return True
        if any(marker in sentence.lower() for marker in NON_PLAYER_SENTENCE_MARKERS):
            return True
        if any(token in name for token in ("Final", "Stadium", "Arena", "Aréna", "Kick")):
            return True
        if name.endswith("-"):
            return True
        tokens = name.split()
        if not tokens or len(tokens) > 4:
            return True
        if name.isupper() and len(tokens) > 1:
            return True
        if tokens[0] in PERSON_PREFIX_STOPWORDS:
            return True
        if any(token in PERSON_TOKEN_STOPWORDS for token in tokens):
            return True
        return False

    def _excluded_name_phrases(self, home_team: str, away_team: str, competition: str) -> set[str]:
        excluded = {phrase for phrase in (home_team, away_team, competition) if phrase}
        excluded.update(NON_PERSON_TERMS)
        for phrase in list(excluded):
            tokens = [token for token in re.split(r"\W+", phrase) if len(token) > 2]
            excluded.update(tokens)
        return excluded

    def _infer_position(self, sentence: str) -> str:
        lowered = sentence.lower()
        for keyword, position in POSITION_KEYWORDS.items():
            if keyword in lowered:
                return position
        return "Unknown"

    def _player_seen(self, resolution: FixtureResolution, name: str) -> bool:
        return any(
            player.name.lower() == name.lower()
            for players in resolution.players.values()
            for player in players
        )

    def _score_resolution(self, resolution: FixtureResolution) -> float:
        score = 0.0
        if resolution.venue:
            score += 0.35
        if resolution.match_datetime:
            score += 0.25
        if resolution.sources:
            score += min(0.2, 0.05 * len(resolution.sources))
        if resolution.players.get("home_team") or resolution.players.get("away_team"):
            score += 0.2
        return min(score, 1.0)
