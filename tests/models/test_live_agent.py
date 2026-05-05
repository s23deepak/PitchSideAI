"""
Unit tests for LiveAgent NotesStore integration.

Tests:
1. generate_live_commentary() uses NotesStore lookup when provided
2. generate_live_commentary() falls back to raw_markdown when tag misses
3. generate_live_commentary() returns dict with source, retrieved_beats, trivia_formatted
4. Trivia card formatting respects confidence thresholds
"""

import sys
import os
from pathlib import Path

# Add project root to sys.path for imports
_this_file = Path(__file__).resolve()
_project_root = _this_file.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
os.chdir(_project_root)

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from agents.live_agent import LiveAgent
from models.notes_store import NotesStore, TagResolver
from models.narrative_beat import NarrativeBeat


class TestLiveAgentNotesStoreIntegration:
    """Test LiveAgent integration with NotesStore."""

    @pytest.fixture
    def sample_notes_store(self):
        """Create a sample NotesStore with test beats."""
        beats = [
            NarrativeBeat(
                text="Haaland has scored 7 goals in his last 5 appearances, including a brace against Liverpool.",
                event_tags=["goal", "goal_scored"],
                players=["Haaland"],
                section="home_team",
                source="fbref",
                confidence=0.95,
            ),
            NarrativeBeat(
                text="De Bruyne's crossing accuracy from corner situations is 38%, highest in the Premier League.",
                event_tags=["corner"],
                players=["De Bruyne"],
                section="tactical",
                source="statsbomb",
                confidence=0.88,
            ),
            NarrativeBeat(
                text="Rodri has not received a yellow card in the last 8 matches, showing exceptional discipline.",
                event_tags=["yellow_card"],
                players=["Rodri"],
                section="away_team",
                source="firecrawl",
                confidence=0.72,
            ),
        ]
        raw_markdown = """# Match Notes

## Home Team
- Haaland has scored 7 goals in his last 5 appearances

## Tactical
- De Bruyne's crossing accuracy from corner situations is 38%

## Away Team
- Rodri has not received a yellow card in the last 8 matches
"""
        return NotesStore(raw_markdown=raw_markdown, beats=beats)

    @pytest.fixture
    def live_agent(self):
        """Create LiveAgent instance with mocked logging."""
        agent = LiveAgent(sport="soccer")
        # Mock log_event to avoid structlog conflicts
        agent.log_event = MagicMock()
        return agent

    @pytest.mark.asyncio
    async def test_generate_live_commentary_with_notes_store(self, live_agent, sample_notes_store):
        """Test that commentary generation uses NotesStore lookup when available."""
        # Setup
        live_agent.notes_store = sample_notes_store
        live_agent.home_team = "Man City"
        live_agent.away_team = "Liverpool"

        # Mock call_bedrock to return predictable commentary
        with patch.object(live_agent, 'call_bedrock', new_callable=AsyncMock) as mock_bedrock:
            mock_bedrock.return_value = "Haaland strikes again! What a finish from the Norwegian!"

            # Call with vision label that matches a beat tag
            result = await live_agent.generate_live_commentary(
                event_description="Haaland scores from close range!",
                vision_tactical_label="goal",
            )

        # Verify return type is dict
        assert isinstance(result, dict)

        # Verify source is notes_lookup (not raw_markdown)
        assert result["source"] == "notes_lookup"

        # Verify commentary was generated
        assert "commentary" in result
        assert len(result["commentary"]) > 0

        # Verify retrieved beats contain Haaland beat
        assert len(result["retrieved_beats"]) > 0
        retrieved_players = set()
        for beat in result["retrieved_beats"]:
            retrieved_players.update(beat.get("players", []))
        assert "Haaland" in retrieved_players

        # Verify resolved tag
        assert result["resolved_tag"] == "goal"

    @pytest.mark.asyncio
    async def test_generate_live_commentary_fallback_to_raw_markdown(self, live_agent, sample_notes_store):
        """Test fallback to raw_markdown when tag doesn't match."""
        # Setup
        live_agent.notes_store = sample_notes_store
        live_agent.home_team = "Man City"
        live_agent.away_team = "Liverpool"

        # Mock call_bedrock
        with patch.object(live_agent, 'call_bedrock', new_callable=AsyncMock) as mock_bedrock:
            mock_bedrock.return_value = "The match continues at a high tempo."

            # Call with vision label that has NO matching beats
            result = await live_agent.generate_live_commentary(
                event_description="Play continues in midfield",
                vision_tactical_label="offside",  # No offside beats in sample_notes_store
            )

        # Verify source is raw_markdown (fallback)
        assert result["source"] == "raw_markdown"

        # Verify no beats retrieved
        assert len(result["retrieved_beats"]) == 0

        # Verify resolved_tag is still set (tag resolved but no beats)
        assert result["resolved_tag"] == "offside"

    @pytest.mark.asyncio
    async def test_generate_live_commentary_without_notes_store(self, live_agent):
        """Test commentary generation without NotesStore (pure fallback)."""
        live_agent.home_team = "Man City"
        live_agent.away_team = "Liverpool"
        live_agent.notes_store = None

        with patch.object(live_agent, 'call_bedrock', new_callable=AsyncMock) as mock_bedrock:
            mock_bedrock.return_value = "Standard commentary without notes."

            result = await live_agent.generate_live_commentary(
                event_description="Haaland scores!",
                vision_tactical_label="goal",
            )

        # Verify source is raw_markdown (no NotesStore available)
        assert result["source"] == "raw_markdown"
        assert len(result["retrieved_beats"]) == 0
        assert result["resolved_tag"] is None

    @pytest.mark.asyncio
    async def test_trivia_card_formatting_high_confidence(self, live_agent, sample_notes_store):
        """Test trivia card formatting for high-confidence beats."""
        live_agent.notes_store = sample_notes_store
        live_agent.home_team = "Man City"
        live_agent.away_team = "Liverpool"

        with patch.object(live_agent, 'call_bedrock', new_callable=AsyncMock) as mock_bedrock:
            mock_bedrock.return_value = "Commentary text"

            result = await live_agent.generate_live_commentary(
                event_description="Haaland scores!",
                vision_tactical_label="goal",
            )

        # Verify trivia card is formatted
        trivia = result.get("trivia_formatted")
        assert trivia is not None
        assert "text" in trivia
        assert "source" in trivia
        assert trivia["source"] == "fbref"
        assert trivia["confidence"] == 0.95

        # Verify display timing for high confidence
        assert trivia["display_duration_ms"] == 5000
        assert trivia["fade_in_ms"] == 400
        assert trivia["fade_out_ms"] == 400

    @pytest.mark.asyncio
    async def test_trivia_card_formatting_medium_confidence(self, live_agent, sample_notes_store):
        """Test trivia card formatting for medium-confidence beats."""
        live_agent.notes_store = sample_notes_store
        live_agent.home_team = "Man City"
        live_agent.away_team = "Liverpool"

        with patch.object(live_agent, 'call_bedrock', new_callable=AsyncMock) as mock_bedrock:
            mock_bedrock.return_value = "Commentary text"

            result = await live_agent.generate_live_commentary(
                event_description="Rodri commits a foul",
                vision_tactical_label="yellow_card",
            )

        trivia = result.get("trivia_formatted")
        assert trivia is not None
        assert trivia["confidence"] == 0.72

        # Verify display timing for medium confidence (0.6-0.8)
        assert trivia["display_duration_ms"] == 3000
        assert trivia["fade_in_ms"] == 300
        assert trivia["fade_out_ms"] == 300

    @pytest.mark.asyncio
    async def test_trivia_card_not_shown_for_low_confidence(self, live_agent, sample_notes_store):
        """Test that trivia card is not shown for low-confidence beats."""
        # Create a low-confidence beat
        low_conf_beat = NarrativeBeat(
            text="Some uncertain observation",
            event_tags=["foul"],
            players=[],
            section="match_info",
            source="vision",
            confidence=0.45,  # Below 0.6 threshold
        )
        low_conf_store = NotesStore(
            raw_markdown="# Notes\n\n- Some uncertain observation",
            beats=[low_conf_beat],
        )

        live_agent.notes_store = low_conf_store
        live_agent.home_team = "Team A"
        live_agent.away_team = "Team B"

        with patch.object(live_agent, 'call_bedrock', new_callable=AsyncMock) as mock_bedrock:
            mock_bedrock.return_value = "Commentary text"

            result = await live_agent.generate_live_commentary(
                event_description="Foul committed",
                vision_tactical_label="foul",
            )

        # Trivia should be None for low confidence
        trivia = result.get("trivia_formatted")
        assert trivia is None


class TestTagResolver:
    """Test TagResolver for vision label normalization."""

    @pytest.fixture
    def resolver(self):
        return TagResolver()

    def test_exact_canonical_match(self, resolver):
        """Test exact match against canonical tags."""
        assert resolver.resolve("goal") == "goal"
        assert resolver.resolve("yellow_card") == "yellow_card"
        assert resolver.resolve("corner") == "corner"

    def test_synonym_match(self, resolver):
        """Test synonym resolution."""
        assert resolver.resolve("goal scored") == "goal"
        assert resolver.resolve("booking") == "yellow_card"
        assert resolver.resolve("sent off") == "red_card"
        assert resolver.resolve("sub") == "substitution"

    def test_substring_match(self, resolver):
        """Test word-boundary substring matching."""
        assert resolver.resolve("goal_situation") == "goal"
        assert resolver.resolve("yellow_card_incident") == "yellow_card"

    def test_goal_safety_gate(self, resolver):
        """Test goal tag requires score change."""
        # No score context - allow through
        assert resolver.resolve("goal", None, None) == "goal"

        # Score increased - allow
        assert resolver.resolve("goal", 0, 1) == "goal"

        # Score unchanged - block
        assert resolver.resolve("goal", 1, 1) is None

    def test_unknown_label_returns_none(self, resolver):
        """Test unknown labels return None for fallback."""
        assert resolver.resolve("unknown_event") is None
        assert resolver.resolve("midfield_play") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
