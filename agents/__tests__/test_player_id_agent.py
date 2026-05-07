"""
Tests for Story 2.4: Player Identification for Q&A

Coverage:
- AC1: Visual Cue Priority
- AC2: High Confidence Identification (> 90%)
- AC3: Medium Confidence Identification (70-90%)
- AC4: Low Confidence Ambiguity (< 70%)
- AC5: Accuracy Requirement (> 90% on known players)
- AC6: Overlay Confidence Mapping
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from agents.player_id_agent import (
    PlayerIDAgent,
    PlayerIdentification,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    QUALIFIERS,
    CUE_WEIGHTS,
)
from models.game_state import GameState


@pytest.fixture
def player_id_agent():
    """Create PlayerIDAgent instance for testing."""
    agent = PlayerIDAgent(sport="soccer")
    # Set up lineup data
    agent.set_lineup_data({
        "home_xi": [
            {"name": "Haaland", "jersey_number": 9, "position": "striker", "height_cm": 194},
            {"name": "De Bruyne", "jersey_number": 17, "position": "attacking_mid", "height_cm": 181},
            {"name": "Rodri", "jersey_number": 16, "position": "defensive_mid", "height_cm": 191},
            {"name": "Foden", "jersey_number": 47, "position": "left_wing", "height_cm": 171},
        ],
        "away_xi": [
            {"name": "Salah", "jersey_number": 11, "position": "right_wing", "height_cm": 175},
            {"name": "Van Dijk", "jersey_number": 4, "position": "center_back", "height_cm": 193},
            {"name": "Alexander-Arnold", "jersey_number": 66, "position": "fullback", "height_cm": 180},
        ],
    })
    return agent


@pytest.fixture
def sample_frame_b64():
    """Sample base64-encoded frame (mock)."""
    return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


class TestAC1_VisualCuePriority:
    """AC1: Visual Cue Priority (Jersey Number → Position → Movement → Build)."""

    def test_cue_weights_sum_to_one(self):
        """Visual cue weights sum to 1.0 (100%)."""
        total_weight = sum(CUE_WEIGHTS.values())
        assert total_weight == 1.0

    def test_jersey_number_has_highest_weight(self):
        """Jersey number has 50% weight (highest)."""
        assert CUE_WEIGHTS["jersey_number"] == 0.50

    def test_position_weight(self):
        """Position has 20% weight."""
        assert CUE_WEIGHTS["position"] == 0.20

    def test_movement_pattern_weight(self):
        """Movement pattern has 15% weight."""
        assert CUE_WEIGHTS["movement_pattern"] == 0.15

    def test_build_weight(self):
        """Build has 15% weight."""
        assert CUE_WEIGHTS["build"] == 0.15

    @pytest.mark.asyncio
    async def test_visual_cues_extracted_from_frame(self, player_id_agent, sample_frame_b64):
        """Visual cues are extracted from frame."""
        with patch.object(player_id_agent, 'call_llm', AsyncMock(return_value='''{
            "jersey_number": 9,
            "jersey_number_confidence": 0.95,
            "position": "striker",
            "position_confidence": 0.85,
            "movement_pattern": "making_run",
            "movement_confidence": 0.70,
            "build": "tall",
            "build_confidence": 0.90,
            "jersey_color": "primary",
            "occlusion": "none"
        }''')):
            cues = await player_id_agent._extract_visual_cues(sample_frame_b64)

            assert "jersey_number" in cues
            assert "position" in cues
            assert "movement_pattern" in cues
            assert "build" in cues


class TestAC2_HighConfidenceIdentification:
    """AC2: High Confidence Identification (> 90%)."""

    def test_confidence_tier_high_threshold(self):
        """High confidence threshold is 90%."""
        assert CONFIDENCE_HIGH == 0.90

    def test_high_confidence_no_qualifier(self, player_id_agent):
        """High confidence (> 90%) has no qualifier."""
        qualifier = player_id_agent._get_qualifier(
            player_name="Haaland",
            confidence=0.95,
            source="jersey_number + lineup_data",
        )

        assert qualifier == ""  # No qualifier

    @pytest.mark.asyncio
    async def test_high_confidence_direct_identification(self, player_id_agent, sample_frame_b64):
        """High confidence allows direct player identification by name."""
        with patch.object(player_id_agent, 'call_llm', AsyncMock(return_value='''{
            "jersey_number": 9,
            "jersey_number_confidence": 0.98,
            "position": "striker",
            "position_confidence": 0.90,
            "movement_pattern": "making_run",
            "movement_confidence": 0.80,
            "build": "tall",
            "build_confidence": 0.95,
            "jersey_color": "primary",
            "occlusion": "none"
        }''')):
            result = await player_id_agent.identify_player(
                frame_b64=sample_frame_b64,
                game_state=None,
            )

            assert result.player_name == "Haaland"
            assert result.confidence > CONFIDENCE_HIGH
            assert result.qualifier == ""


class TestAC3_MediumConfidenceIdentification:
    """AC3: Medium Confidence Identification (70-90%)."""

    def test_confidence_tier_medium_threshold(self):
        """Medium confidence threshold is 70%."""
        assert CONFIDENCE_MEDIUM == 0.70

    def test_medium_confidence_has_qualifier(self, player_id_agent):
        """Medium confidence (70-90%) includes qualifier."""
        qualifier = player_id_agent._get_qualifier(
            player_name="De Bruyne",
            confidence=0.80,
            source="jersey_number + lineup_data",
        )

        assert "appears to be" in qualifier
        assert "De Bruyne" in qualifier
        assert "jersey_number" in qualifier

    def test_medium_confidence_qualifier_template(self):
        """Medium confidence qualifier template is correct."""
        expected = QUALIFIERS["medium"]
        assert "appears to be" in expected
        assert "{player_name}" in expected
        assert "{source}" in expected


class TestAC4_LowConfidenceAmbiguity:
    """AC4: Low Confidence Ambiguity (< 70%)."""

    def test_low_confidence_no_name_used(self, player_id_agent):
        """Low confidence (< 70%) does not use player name."""
        qualifier = player_id_agent._get_qualifier(
            player_name=None,
            confidence=0.50,
            source="visual_analysis",
        )

        # Low confidence should use position description, not name
        assert "player in" in qualifier.lower()

    def test_low_confidence_qualifier_template(self):
        """Low confidence qualifier template is correct."""
        expected = QUALIFIERS["low"]
        assert "player in" in expected.lower()
        assert "{position_description}" in expected


class TestAC5_AccuracyRequirement:
    """AC5: Accuracy Requirement (> 90% on known players)."""

    def test_contextual_bonus_applied(self, player_id_agent):
        """Contextual bonus (+10%) applied for active players."""
        # Set up active players and recent touches
        player_id_agent.active_players = {"Haaland", "De Bruyne"}
        player_id_agent.recent_touches = {"Haaland"}

        result = PlayerIdentification(
            player_name="Haaland",
            confidence=0.85,  # Below 90% before bonus
            source="jersey_number",
        )

        player_id_agent._apply_contextual_bonus(result)

        # Should have +10% bonus
        assert result.confidence == 0.95

    def test_contextual_bonus_capped_at_100(self, player_id_agent):
        """Contextual bonus is capped at 1.0 (100%)."""
        player_id_agent.active_players = {"Haaland"}

        result = PlayerIdentification(
            player_name="Haaland",
            confidence=0.95,
            source="jersey_number",
        )

        player_id_agent._apply_contextual_bonus(result)

        assert result.confidence == 1.0

    def test_jersey_number_lookup_direct(self, player_id_agent):
        """Direct jersey number lookup is highly accurate."""
        players = player_id_agent._get_players_by_jersey_number(9)
        assert "Haaland" in players

    def test_position_based_retrieval(self, player_id_agent):
        """Position-based retrieval works."""
        players = player_id_agent._get_players_by_position("striker")
        assert "Haaland" in players

        players = player_id_agent._get_players_by_position("right_wing")
        assert "Salah" in players


class TestAC6_OverlayConfidenceMapping:
    """AC6: Overlay Confidence Mapping."""

    def test_high_confidence_precise_circle(self, player_id_agent):
        """High confidence (> 90%) renders precise circle overlay."""
        player_id = PlayerIdentification(
            player_name="Haaland",
            confidence=0.95,
            position="striker",
            visual_cues={"position": "striker"},
        )

        overlay = player_id_agent._generate_overlay_coordinates(player_id)

        assert overlay is not None
        assert overlay["type"] == "circle"
        assert overlay["r"] == 8  # Tight radius
        assert overlay["stroke"] == "#00ff00"  # Green

    def test_medium_confidence_zone_highlight(self, player_id_agent):
        """Medium confidence (70-90%) renders zone highlight overlay."""
        player_id = PlayerIdentification(
            player_name="De Bruyne",
            confidence=0.80,
            position="attacking_mid",
            visual_cues={"position": "attacking_mid"},
        )

        overlay = player_id_agent._generate_overlay_coordinates(player_id)

        assert overlay is not None
        assert overlay["type"] == "zone"
        assert overlay["rx"] == 15  # Ellipse radii
        assert overlay["ry"] == 12
        assert overlay["stroke"] == "#ffff00"  # Yellow

    def test_low_confidence_no_overlay(self, player_id_agent):
        """Low confidence (< 70%) does not render overlay."""
        player_id = PlayerIdentification(
            player_name=None,
            confidence=0.50,
            visual_cues={},
        )

        overlay = player_id_agent._generate_overlay_coordinates(player_id)

        assert overlay is None


class TestPlayerIdentificationDataclass:
    """Test PlayerIdentification dataclass."""

    def test_player_identification_creation(self):
        """PlayerIdentification can be created."""
        pid = PlayerIdentification(
            player_name="Haaland",
            confidence=0.95,
            source="jersey_number + lineup_data",
            jersey_number=9,
            position="striker",
        )

        assert pid.player_name == "Haaland"
        assert pid.confidence == 0.95
        assert pid.jersey_number == 9
        assert pid.position == "striker"

    def test_player_identification_confidence_validation(self):
        """Confidence must be in valid range."""
        with pytest.raises(ValueError):
            PlayerIdentification(
                player_name="Test",
                confidence=1.5,  # Invalid
            )

        with pytest.raises(ValueError):
            PlayerIdentification(
                player_name="Test",
                confidence=-0.1,  # Invalid
            )


class TestLineupContextFusion:
    """Test lineup context fusion."""

    def test_set_lineup_data(self, player_id_agent):
        """Lineup data can be set."""
        assert "Haaland" in player_id_agent.active_players
        assert "Salah" in player_id_agent.active_players

    def test_extract_active_players(self, player_id_agent):
        """Active players extracted from lineup."""
        lineup = {
            "home_xi": [{"name": "Player A"}, {"name": "Player B"}],
            "away_xi": [{"name": "Player C"}],
        }

        players = player_id_agent._extract_active_players(lineup)
        assert "Player A" in players
        assert "Player B" in players
        assert "Player C" in players

    def test_update_recent_touches(self, player_id_agent):
        """Recent touches can be updated."""
        player_id_agent.update_recent_touches({"Haaland", "De Bruyne"})

        assert "Haaland" in player_id_agent.recent_touches
        assert "De Bruyne" in player_id_agent.recent_touches


class TestPlayerIDForQA:
    """Test player ID for Q&A integration."""

    @pytest.mark.asyncio
    async def test_jersey_number_question_direct_lookup(self, player_id_agent):
        """Jersey number questions use direct lookup."""
        result = await player_id_agent.identify_player_for_qa(
            frame_b64=None,
            question="Who is number 9?",
            game_state=None,
        )

        assert result["player_name"] == "Haaland"
        assert result["confidence"] == 0.95  # High confidence from direct lookup
        assert result["source"] == "jersey_number_lookup"

    @pytest.mark.asyncio
    async def test_general_player_question(self, player_id_agent, sample_frame_b64):
        """General player questions use vision analysis."""
        with patch.object(player_id_agent, 'call_llm', AsyncMock(return_value='''{
            "jersey_number": 11,
            "jersey_number_confidence": 0.90,
            "position": "right_wing",
            "position_confidence": 0.85,
            "movement_pattern": "cutting_inside",
            "movement_confidence": 0.75,
            "build": "medium",
            "build_confidence": 0.80,
            "jersey_color": "primary",
            "occlusion": "none"
        }''')):
            result = await player_id_agent.identify_player_for_qa(
                frame_b64=sample_frame_b64,
                question="Who's that on the right wing?",
                game_state=None,
            )

            assert result["player_name"] == "Salah"
            assert result["jersey_number"] == 11


class TestSourceAttribution:
    """Test source attribution for transparency."""

    def test_source_includes_jersey_number(self, player_id_agent):
        """Source includes jersey number when used."""
        result = player_id_agent._fuse_with_lineup_context(
            cue_scores={
                "jersey_number": {"value": 9, "score": 0.475, "candidates": ["Haaland"]},
                "position": {"value": None, "score": 0, "candidates": []},
                "movement_pattern": {"value": None, "score": 0, "candidates": []},
                "build": {"value": None, "score": 0, "candidates": []},
            },
            lineup_context=None,
            game_state=None,
        )

        assert "jersey_number" in result.source

    def test_source_includes_lineup_data(self, player_id_agent):
        """Source includes lineup data when fused."""
        result = player_id_agent._fuse_with_lineup_context(
            cue_scores={
                "jersey_number": {"value": 9, "score": 0.475, "candidates": ["Haaland"]},
                "position": {"value": "striker", "score": 0.17, "candidates": ["Haaland"]},
                "movement_pattern": {"value": None, "score": 0, "candidates": []},
                "build": {"value": None, "score": 0, "candidates": []},
            },
            lineup_context={"home_xi": []},
            game_state=None,
        )

        assert "lineup_data" in result.source


# Run with: pytest agents/__tests__/test_player_id_agent.py -v
