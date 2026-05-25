"""LangGraph workflow for live notes patching after match events/VLM observations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from models.narrative_beat import NarrativeBeat
from models.notes_store import NotesStore


EVENT_TAGS = {
    "goal": ["goal"],
    "yellow_card": ["yellow_card"],
    "red_card": ["red_card"],
    "substitution": ["substitution"],
    "foul": ["foul"],
    "corner": ["corner"],
    "offside": ["offside"],
}


@dataclass
class LiveNotesPatchState:
    match_id: str
    match_session: str
    event_id: str
    event_type: str
    description: str
    source: str = "system"
    confidence: float = 1.0
    payload: Dict[str, Any] = field(default_factory=dict)
    notes_store_payload: Dict[str, Any] = field(default_factory=dict)
    notes_store: Optional[NotesStore] = None
    patched_notes_store: Optional[NotesStore] = None
    impacted_sections: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    patch_summary: str = ""
    vlm_context: Dict[str, Any] = field(default_factory=dict)


class LiveNotesPatchWorkflow:
    """Small, event-driven graph for live commentary-notes updates."""

    async def classify_event(self, state: LiveNotesPatchState) -> LiveNotesPatchState:
        event_type = (state.event_type or "").strip().lower()
        if not event_type:
            lowered = state.description.lower()
            if "red card" in lowered or "sent off" in lowered:
                event_type = "red_card"
            elif "sub" in lowered or "off for" in lowered or "on for" in lowered:
                event_type = "substitution"
            elif "goal" in lowered or "scores" in lowered:
                event_type = "goal"
            elif "yellow" in lowered or "booking" in lowered:
                event_type = "yellow_card"
            else:
                event_type = "match_state"
        state.event_type = event_type
        state.impacted_sections = self._impacted_sections(event_type)
        return state

    async def load_latest_notes(self, state: LiveNotesPatchState) -> LiveNotesPatchState:
        if state.notes_store is None:
            state.notes_store = NotesStore.from_dict(state.notes_store_payload)
        return state

    async def patch_notes(self, state: LiveNotesPatchState) -> LiveNotesPatchState:
        if state.notes_store is None:
            raise ValueError("Live patch workflow requires an existing NotesStore")

        timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        section_title = "LIVE MATCH UPDATES"
        patch_line = self._build_patch_line(state, timestamp)
        raw_markdown = state.notes_store.raw_markdown.rstrip()
        if f"## {section_title}" not in raw_markdown:
            raw_markdown = f"{raw_markdown}\n\n---\n\n## {section_title}\n"
        raw_markdown = f"{raw_markdown}\n\n- {patch_line}\n"

        beats = list(state.notes_store.beats)
        beats.append(
            NarrativeBeat(
                text=patch_line,
                event_tags=EVENT_TAGS.get(state.event_type, [state.event_type]),
                players=self._players_from_payload(state.payload),
                section="live_updates",
                source=state.source,
                source_urls=[],
                source_attribution=[{"label": state.source, "url": ""}],
                confidence=max(0.0, min(1.0, float(state.confidence or 0.0))),
            )
        )
        state.patched_notes_store = NotesStore(raw_markdown=raw_markdown, beats=beats)
        state.patch_summary = patch_line
        return state

    async def validate_patch(self, state: LiveNotesPatchState) -> LiveNotesPatchState:
        if state.patched_notes_store is None:
            state.errors.append("Patch did not produce a NotesStore")
            return state
        if len(state.patched_notes_store.raw_markdown) <= len(state.notes_store.raw_markdown if state.notes_store else ""):
            state.warnings.append("Patch did not increase notes length")
        return state

    async def build_updated_vlm_context(self, state: LiveNotesPatchState) -> LiveNotesPatchState:
        notes = state.patched_notes_store
        if notes is None:
            return state
        state.vlm_context = {
            "notes_version": 0,
            "vlm_context_version": 0,
            "markdown_context": notes.raw_markdown[-12000:],
            "beat_count": len(notes.beats),
            "lookup_tags": sorted(notes.lookup.keys()),
            "latest_patch": {
                "event_id": state.event_id,
                "event_type": state.event_type,
                "summary": state.patch_summary,
                "impacted_sections": state.impacted_sections,
            },
        }
        return state

    def build_graph(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except Exception as exc:
            raise RuntimeError("LangGraph is required for live notes patching") from exc

        graph = StateGraph(LiveNotesPatchState)
        graph.add_node("classify_event", self.classify_event)
        graph.add_node("load_latest_notes", self.load_latest_notes)
        graph.add_node("patch_notes", self.patch_notes)
        graph.add_node("validate_patch", self.validate_patch)
        graph.add_node("build_updated_vlm_context", self.build_updated_vlm_context)
        graph.add_edge(START, "classify_event")
        graph.add_edge("classify_event", "load_latest_notes")
        graph.add_edge("load_latest_notes", "patch_notes")
        graph.add_edge("patch_notes", "validate_patch")
        graph.add_edge("validate_patch", "build_updated_vlm_context")
        graph.add_edge("build_updated_vlm_context", END)
        return graph.compile()

    async def run(self, state: LiveNotesPatchState) -> LiveNotesPatchState:
        result = await self.build_graph().ainvoke(state)
        if isinstance(result, LiveNotesPatchState):
            return result
        return LiveNotesPatchState(**result)

    def _impacted_sections(self, event_type: str) -> list[str]:
        if event_type == "substitution":
            return ["lineups", "player_profiles", "tactical_profile", "matchups"]
        if event_type == "red_card":
            return ["tactical_profile", "risk_register", "expected_match_dynamic"]
        if event_type == "goal":
            return ["storylines", "expected_match_dynamic", "momentum"]
        return ["live_updates"]

    def _build_patch_line(self, state: LiveNotesPatchState, timestamp: str) -> str:
        description = state.description.strip() or f"{state.event_type} detected"
        impacted = ", ".join(state.impacted_sections) or "live_updates"
        return (
            f"**{timestamp} | {state.event_type.replace('_', ' ').title()}**: "
            f"{description} Source: {state.source}. Confidence: {state.confidence:.2f}. "
            f"Refresh these booth cues: {impacted}."
        )

    def _players_from_payload(self, payload: Dict[str, Any]) -> list[str]:
        players = []
        for key in ("player", "player_in", "player_out", "scorer", "dismissed_player"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                players.append(value)
        return players
