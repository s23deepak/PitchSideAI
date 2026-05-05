# Review #1: Blind Hunter

**Instructions:** You receive ONLY the diff. No spec, no context docs, no project access. Find every bug, flaw, and code smell.

---

## DIFF

### Modified: models/__init__.py

```diff
-"""Game models for PitchSide AI."""
+"""Game models for PitchAI."""
 
 from models.game_state import GameState, GameEvent, MatchPhase
+from models.narrative_beat import NarrativeBeat
+from models.notes_store import NotesStore, TagResolver, CANONICAL_TAGS
 
-__all__ = ["GameState", "GameEvent", "MatchPhase"]
+__all__ = [
+    "GameState",
+    "GameEvent",
+    "MatchPhase",
+    "NarrativeBeat",
+    "NotesStore",
+    "TagResolver",
+    "CANONICAL_TAGS",
+]
```

### New file: models/narrative_beat.py

```python
"""NarrativeBeat dataclass — pure data model for commentary notes."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class NarrativeBeat:
    text: str
    event_tags: List[str]
    players: List[str] = field(default_factory=list)
    section: str = ""
    source: str = ""
    confidence: float = 0.0
```

### New file: models/notes_store.py

```python
"""
NotesStore — structured commentary notes with O(1) tag lookup.

TagResolver — 3-tier event tag normalization (exact → synonym → substring → None)
with safety gate for goal events to prevent false calls.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from models.narrative_beat import NarrativeBeat

# ── Canonical event tags ──────────────────────────────────────────────────────

CANONICAL_TAGS: List[str] = [
    "goal",
    "yellow_card",
    "red_card",
    "substitution",
    "foul",
    "corner",
    "free_kick_dangerous",
    "offside",
]

# ── Synonym map (vision label → canonical tag) ────────────────────────────────

_SYNONYM_MAP: Dict[str, str] = {
    "goal scored": "goal",
    "goal": "goal",
    "booking": "yellow_card",
    "yellow card": "yellow_card",
    "sent off": "red_card",
    "red card": "red_card",
    "dismissal": "red_card",
    "substitution": "substitution",
    "sub": "substitution",
    "foul committed": "foul",
    "foul": "foul",
    "corner kick": "corner",
    "corner": "corner",
    "free kick": "free_kick_dangerous",
    "set piece": "free_kick_dangerous",
    "offside call": "offside",
    "offside": "offside",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _word_boundary_match(tag: str, text: str) -> bool:
    """Return True if all word tokens of `tag` appear in `text`.

    Tokens are separated by spaces, underscores, or hyphens.
    """
    text_tokens = set(re.split(r"[ _-]+", text))
    tag_tokens = set(re.split(r"[ _-]+", tag))
    return tag_tokens.issubset(text_tokens)


# ── Tag resolver ──────────────────────────────────────────────────────────────

class TagResolver:
    """3-tier event tag resolution with goal safety gate."""

    def resolve(
        self,

        vision_label: str,
        previous_score_total: Optional[int] = None,
        current_score_total: Optional[int] = None,
    ) -> Optional[str]:
        key = vision_label.casefold().strip()
        if not key:
            return None

        # Tier 1: exact canonical match
        for tag in CANONICAL_TAGS:
            if key == tag:
                return self._apply_goal_gate(
                    tag, previous_score_total, current_score_total
                )

        # Tier 2: synonym map
        synonym = _SYNONYM_MAP.get(key)
        if synonym is not None:
            return self._apply_goal_gate(
                synonym, previous_score_total, current_score_total
            )

        # Tier 3: word-boundary substring match
        for tag in CANONICAL_TAGS:
            if _word_boundary_match(tag, key):
                return self._apply_goal_gate(
                    tag, previous_score_total, current_score_total
                )

        return None

    def _apply_goal_gate(
        self,
        tag: str,
        previous_score_total: Optional[int],
        current_score_total: Optional[int],
    ) -> Optional[str]:
        if tag != "goal":
            return tag
        if previous_score_total is None or current_score_total is None:
            return tag
        if current_score_total > previous_score_total:
            return "goal"
        return None


# ── Notes store ───────────────────────────────────────────────────────────────

@dataclass
class NotesStore:
    raw_markdown: str
    beats: List[NarrativeBeat] = field(default_factory=list)
    lookup: Dict[str, List[int]] = field(default_factory=dict)
    index: Optional[Any] = None

    def __post_init__(self) -> None:
        if self.lookup:
            return
        self.lookup = {}
        for i, beat in enumerate(self.beats):
            for tag in beat.event_tags:
                self.lookup.setdefault(tag, []).append(i)

    def get_beats_for_tag(self, tag: str) -> List[NarrativeBeat]:
        indices = self.lookup.get(tag, [])
        return [self.beats[i] for i in indices]
```

### New file: tests/models/test_notes_store.py

47 tests across 4 test classes: TestNarrativeBeat, TestTagResolver, TestNotesStore, TestCanonicalTags. Covers instantiation, defaults, exact/synonym/substring/no-match resolution, goal safety gate (changed/unchanged/no-context/partial-context), lookup building, empty store, ordering, and canonical tags validation.

---

## OUTPUT FORMAT

For each finding:
1. **Category:** intent_gap | bad_spec | patch | defer | reject
2. **File and line**
3. **Finding:** what's wrong
4. **Severity:** critical | high | medium | low