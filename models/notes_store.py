"""
NotesStore — structured commentary notes with O(1) tag lookup.

TagResolver — 3-tier event tag normalization (exact → synonym → substring → None)
with safety gate for goal events to prevent false calls.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from models.narrative_beat import NarrativeBeat

# ── Canonical event tags ──────────────────────────────────────────────────────

CANONICAL_TAGS: Tuple[str, ...] = (
    "goal",
    "yellow_card",
    "red_card",
    "substitution",
    "foul",
    "corner",
    "free_kick_dangerous",
    "offside",
)

# ── Synonym map (vision label → canonical tag) ────────────────────────────────

_SYNONYM_MAP: Mapping[str, str] = {
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
    This avoids false positives like plain substring matching would produce,
    while catching compound tags (e.g. "red_card" in "red_card_situation").
    """
    text_tokens = set(re.split(r"[ _-]+", text))
    tag_tokens = set(re.split(r"[ _-]+", tag))
    return tag_tokens.issubset(text_tokens)


# ── Tag resolver ──────────────────────────────────────────────────────────────


class TagResolver:
    """3-tier event tag resolution with goal safety gate.

    Resolution order:
    1. Exact canonical match (casefold)
    2. Synonym map lookup (casefold)
    3. Substring match against canonical tags (casefold)
    4. Return None (semantic/embedding fallback)
    """

    def resolve(
        self,
        vision_label: str,
        previous_score_total: Optional[int] = None,
        current_score_total: Optional[int] = None,
    ) -> Optional[str]:
        """Resolve a vision label to a canonical tag.

        Args:
            vision_label: Raw label from vision model (e.g. "Goal scored").
            previous_score_total: Pre-event score sum for goal safety gate.
            current_score_total: Current score sum for goal safety gate.

        Returns:
            Canonical tag string or None if no match / blocked by safety gate.
        """
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
        """Block 'goal' tag if score hasn't changed since previous total."""
        if tag != "goal":
            return tag
        if previous_score_total is None or current_score_total is None:
            # No score context provided — allow through (caller's responsibility)
            return tag
        if current_score_total > previous_score_total:
            return "goal"
        return None


# ── Notes store ───────────────────────────────────────────────────────────────


@dataclass
class NotesStore:
    """Structured commentary notes with O(1) tag-based lookup.

    Attributes:
        raw_markdown: Full markdown document (backwards compat with old string output).
        beats: All NarrativeBeats from the pipeline.
        lookup: Dict mapping event_tag → list of beat indices (0-based).
        index: Placeholder for numpy cosine similarity index (stretch goal).
    """

    raw_markdown: str
    beats: List[NarrativeBeat] = field(default_factory=list)
    lookup: Dict[str, List[int]] = field(default_factory=dict)
    index: Optional[Any] = None

    def __post_init__(self) -> None:
        """Build the lookup table from beats on initialisation."""
        if self.lookup:
            return  # already built (e.g. deserialisation)
        self.lookup = {}
        for i, beat in enumerate(self.beats):
            for tag in beat.event_tags:
                self.lookup.setdefault(tag, []).append(i)

    def get_beats_for_tag(self, tag: str) -> List[NarrativeBeat]:
        """Return all beats matching a canonical event tag. O(1).

        Includes bounds checking to handle stale indices if lookup dict
        is manually corrupted or deserialized from incompatible version.
        """
        indices = self.lookup.get(tag, [])
        result = []
        for i in indices:
            if 0 <= i < len(self.beats):
                result.append(self.beats[i])
        return result

    def get_beats_with_indices(self, tag: str) -> List[tuple]:
        """Return all beats matching a canonical event tag with their indices. O(1).

        Returns:
            List of (index, NarrativeBeat) tuples sorted by index.
        """
        indices = self.lookup.get(tag, [])
        result = []
        for i in sorted(indices):
            if 0 <= i < len(self.beats):
                result.append((i, self.beats[i]))
        return result
