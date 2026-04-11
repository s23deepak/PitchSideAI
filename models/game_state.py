"""
Lightweight match state tracker for live commentary sessions.

Parses user-submitted event descriptions (e.g. "Goal by Haaland 34'") to
maintain a running score, match minute, phase, and event timeline.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Any, Optional

# ── Constants ─────────────────────────────────────────────────────────────────

_MAX_EVENTS = 50
_RECENT_DISPLAY = 10

# ── Regex patterns (compiled once) ────────────────────────────────────────────

_RE_MINUTE = re.compile(r"(\d{1,3})[''′]")
_RE_GOAL = re.compile(r"\bgoals?\b|\bscores?\b|\bscored\b|\bfinds the net\b", re.I)
_RE_EXPLICIT_SCORE = re.compile(r"\b(\d{1,2})\s*[-–]\s*(\d{1,2})\b")
_RE_YELLOW = re.compile(r"\byellow\s*card\b|\bbooked\b|\bcaution", re.I)
_RE_RED = re.compile(r"\bred\s*card\b|\bsent\s*off\b|\bdismissed\b", re.I)
_RE_SUB = re.compile(r"\bsub(?:stitut)?\b|\bcomes?\s*on\b|\breplaces?\b", re.I)
_RE_KICKOFF = re.compile(r"\bkick[\s-]?off\b", re.I)
_RE_HALFTIME = re.compile(r"\bhalf[\s-]?time\b", re.I)
_RE_SECOND_HALF = re.compile(r"\bsecond[\s-]?half\b", re.I)
_RE_FULLTIME = re.compile(r"\bfull[\s-]?time\b|\bfinal\s*whistle\b", re.I)
_RE_OWN_GOAL = re.compile(r"\bown[\s-]?goal\b", re.I)


# ── Enums & dataclasses ──────────────────────────────────────────────────────

class MatchPhase(str, Enum):
    PRE_MATCH = "pre_match"
    FIRST_HALF = "first_half"
    HALF_TIME = "half_time"
    SECOND_HALF = "second_half"
    EXTRA_TIME = "extra_time"
    PENALTIES = "penalties"
    FULL_TIME = "full_time"


_PHASE_DISPLAY = {
    MatchPhase.PRE_MATCH: "Pre-Match",
    MatchPhase.FIRST_HALF: "1st Half",
    MatchPhase.HALF_TIME: "Half Time",
    MatchPhase.SECOND_HALF: "2nd Half",
    MatchPhase.EXTRA_TIME: "Extra Time",
    MatchPhase.PENALTIES: "Penalties",
    MatchPhase.FULL_TIME: "Full Time",
}


@dataclass
class GameEvent:
    minute: Optional[int]
    event_type: str  # goal, yellow_card, red_card, substitution, phase, other
    description: str
    team: Optional[str] = None
    player: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Main class ────────────────────────────────────────────────────────────────

@dataclass
class GameState:
    home_team: str
    away_team: str
    home_score: int = 0
    away_score: int = 0
    match_minute: Optional[int] = None
    phase: MatchPhase = MatchPhase.PRE_MATCH
    events: List[GameEvent] = field(default_factory=list)

    # ── Public API ────────────────────────────────────────────────────────────

    def update_from_event(self, description: str) -> None:
        """Parse a free-text match event and update state accordingly."""
        desc_lower = description.lower()

        # Extract minute
        m = _RE_MINUTE.search(description)
        minute = int(m.group(1)) if m else self.match_minute
        if minute is not None:
            self.match_minute = minute

        # Detect phase transitions
        if _RE_KICKOFF.search(desc_lower):
            if self.phase in (MatchPhase.PRE_MATCH, MatchPhase.HALF_TIME):
                self.phase = (
                    MatchPhase.FIRST_HALF
                    if self.phase == MatchPhase.PRE_MATCH
                    else MatchPhase.SECOND_HALF
                )
            self._append_event(minute, "phase", description)
            return

        if _RE_HALFTIME.search(desc_lower):
            self.phase = MatchPhase.HALF_TIME
            self._append_event(minute, "phase", description)
            return

        if _RE_FULLTIME.search(desc_lower):
            self.phase = MatchPhase.FULL_TIME
            self._append_event(minute, "phase", description)
            return

        if _RE_SECOND_HALF.search(desc_lower):
            self.phase = MatchPhase.SECOND_HALF
            self._append_event(minute, "phase", description)
            return

        # Identify which team the event relates to
        team = self._identify_team(desc_lower)

        # Detect goals
        if _RE_GOAL.search(desc_lower):
            # Check for explicit score override (e.g. "2-1")
            score_match = _RE_EXPLICIT_SCORE.search(description)
            if score_match:
                self.home_score = int(score_match.group(1))
                self.away_score = int(score_match.group(2))
            elif team:
                # Own goal goes to the OTHER team
                if _RE_OWN_GOAL.search(desc_lower):
                    if team == self.home_team:
                        self.away_score += 1
                    else:
                        self.home_score += 1
                else:
                    if team == self.home_team:
                        self.home_score += 1
                    else:
                        self.away_score += 1
            self._append_event(minute, "goal", description, team=team)
            return

        # Detect cards
        if _RE_RED.search(desc_lower):
            self._append_event(minute, "red_card", description, team=team)
            return

        if _RE_YELLOW.search(desc_lower):
            self._append_event(minute, "yellow_card", description, team=team)
            return

        # Detect substitutions
        if _RE_SUB.search(desc_lower):
            self._append_event(minute, "substitution", description, team=team)
            return

        # Everything else
        self._append_event(minute, "other", description, team=team)

    def update_from_detection(self, analysis: Dict[str, Any]) -> None:
        """Light-weight update from a vision detection. Does NOT modify score."""
        ts_ms = analysis.get("timestamp_ms")
        if isinstance(ts_ms, (int, float)) and ts_ms >= 0:
            self.match_minute = int(ts_ms // 60_000)

    def to_context_string(self) -> str:
        """Compact prompt string for LLM injection. Returns '' if no state yet."""
        if self.phase == MatchPhase.PRE_MATCH and not self.events:
            return ""

        phase_str = _PHASE_DISPLAY.get(self.phase, self.phase.value)
        minute_str = f"{self.match_minute}'" if self.match_minute is not None else ""
        sep = " | " if minute_str else ""

        header = (
            f"MATCH STATE: {self.home_team} {self.home_score} - "
            f"{self.away_score} {self.away_team}{sep}{minute_str} ({phase_str})"
        )

        significant = [
            e for e in self.events
            if e.event_type in ("goal", "red_card", "yellow_card", "substitution")
        ]
        if not significant:
            return header

        recent = significant[-_RECENT_DISPLAY:]
        parts = []
        for e in recent:
            m = f"{e.minute}' " if e.minute is not None else ""
            t = e.event_type.upper().replace("_", " ")
            team_str = f" ({e.team})" if e.team else ""
            parts.append(f"{m}{t}{team_str}: {e.description[:80]}")

        return f"{header}\nRecent: " + " | ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable dict for WebSocket broadcast."""
        recent = self.events[-_RECENT_DISPLAY:]
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "home_score": self.home_score,
            "away_score": self.away_score,
            "match_minute": self.match_minute,
            "phase": self.phase.value,
            "recent_events": [
                {
                    "minute": e.minute,
                    "event_type": e.event_type,
                    "description": e.description,
                    "team": e.team,
                    "timestamp": e.timestamp,
                }
                for e in recent
            ],
        }

    # ── Internals ─────────────────────────────────────────────────────────────

    def _identify_team(self, desc_lower: str) -> Optional[str]:
        """Match home or away team name in the description."""
        home_match = self.home_team.lower() in desc_lower
        away_match = self.away_team.lower() in desc_lower
        if home_match and not away_match:
            return self.home_team
        if away_match and not home_match:
            return self.away_team
        return None

    def _append_event(
        self,
        minute: Optional[int],
        event_type: str,
        description: str,
        team: Optional[str] = None,
    ) -> None:
        self.events.append(GameEvent(
            minute=minute,
            event_type=event_type,
            description=description,
            team=team,
        ))
        if len(self.events) > _MAX_EVENTS:
            self.events = self.events[-_MAX_EVENTS:]
