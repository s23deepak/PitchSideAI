"""
Player ID Agent — Story 2.4: Player Identification for Q&A

Handles player identification from visual cues and lineup context
with confidence-gated output for Q&A answers and overlays.

FRs covered: FR6 (Player Identification), FR11 (Graceful Fallback)
"""
import base64
import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set, Tuple

from agents.base import VisionAgent as BaseVisionAgent
from models.game_state import GameState
from tools.dynamodb_tool import write_event


@dataclass
class PlayerIdentification:
    """Result of player identification analysis."""
    player_name: Optional[str] = None
    confidence: float = 0.0
    source: str = ""  # e.g., "jersey_number + lineup_data"
    jersey_number: Optional[int] = None
    position: Optional[str] = None
    visual_cues: Dict[str, Any] = field(default_factory=dict)
    qualifier: str = ""  # For medium/low confidence answers

    def __post_init__(self) -> None:
        """Validate confidence is in valid 0.0-1.0 range."""
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {self.confidence}")


# ── Confidence Tiers ──────────────────────────────────────────────────────────

CONFIDENCE_HIGH = 0.90
CONFIDENCE_MEDIUM = 0.70

# ── Qualifier Templates ───────────────────────────────────────────────────────

QUALIFIERS = {
    "high": "",  # No qualifier - direct identification
    "medium": "That appears to be {player_name} based on {source}",
    "low": "The player in {position_description}",  # Ambiguous - no name used
}

# ── Cue Priority Weights ──────────────────────────────────────────────────────

CUE_WEIGHTS = {
    "jersey_number": 0.50,  # 50% weight - most reliable
    "position": 0.20,  # 20% weight
    "movement_pattern": 0.15,  # 15% weight
    "build": 0.15,  # 15% weight
}

CONTEXTUAL_BONUS = 0.10  # +10% if matches lineup + recent touch


class PlayerIDAgent(BaseVisionAgent):
    """
    Story 2.4: Player Identification for Q&A

    Identifies players from visual cues (jersey number OCR, position,
    movement pattern, build) fused with lineup context.

    Outputs confidence-gated results for Q&A answers and SVG overlays.
    """

    def __init__(self, model_id: str = None, sport: str = "soccer"):
        from config import VISION_MODEL
        super().__init__(model_id or VISION_MODEL, sport)
        self.lineup_data: Optional[Dict[str, Any]] = None  # Starting XI + subs
        self.active_players: Set[str] = set()  # Players currently on pitch
        self.recent_touches: Set[str] = set()  # Players with recent touches

    def set_lineup_data(self, lineup: Dict[str, Any]) -> None:
        """
        Set pre-match lineup data.

        Args:
            lineup: Dict with home_xi, away_xi, substitutes, formations
        """
        self.lineup_data = lineup
        self.active_players = self._extract_active_players(lineup)
        self.log_event("lineup_data_loaded", {
            "home_xi_count": len(lineup.get("home_xi", [])),
            "away_xi_count": len(lineup.get("away_xi", [])),
        })

    def _extract_active_players(self, lineup: Dict[str, Any]) -> Set[str]:
        """Extract set of active players from lineup data."""
        players = set()
        for xi in lineup.get("home_xi", []) + lineup.get("away_xi", []):
            if isinstance(xi, dict):
                players.add(xi.get("name", ""))
            else:
                players.add(str(xi))
        return players

    def update_recent_touches(self, players: Set[str]) -> None:
        """Update set of players with recent touches."""
        self.recent_touches = players

    async def identify_player(
        self,
        frame_b64: str,
        lineup_context: Optional[Dict[str, Any]] = None,
        game_state: Optional[GameState] = None,
    ) -> PlayerIdentification:
        """
        Identify player from visual cues with priority order.

        Cue Priority:
        1. Jersey number (OCR) - 50% weight
        2. Position on pitch - 20% weight
        3. Movement pattern - 15% weight
        4. Build - 15% weight
        5. Contextual bonus (+10% if lineup + recent touch)

        Args:
            frame_b64: Base64-encoded JPEG frame
            lineup_context: Optional lineup data override
            game_state: Optional game state for active player filter

        Returns:
            PlayerIdentification with confidence and source
        """
        self.log_event("player_identification_started", {})

        # Step 1: Extract visual cues from frame
        visual_cues = await self._extract_visual_cues(frame_b64)

        # Step 2: Score each cue
        cue_scores = self._score_visual_cues(visual_cues)

        # Step 3: Fuse with lineup context
        fused_result = self._fuse_with_lineup_context(
            cue_scores,
            lineup_context or self.lineup_data,
            game_state,
        )

        # Step 4: Apply contextual bonus
        self._apply_contextual_bonus(fused_result)

        # Step 5: Determine qualifier based on confidence
        fused_result.qualifier = self._get_qualifier(
            fused_result.player_name,
            fused_result.confidence,
            fused_result.source,
        )

        self.log_event("player_identification_completed", {
            "player_name": fused_result.player_name,
            "confidence": fused_result.confidence,
            "source": fused_result.source,
        })

        return fused_result

    async def _extract_visual_cues(
        self,
        frame_b64: str,
    ) -> Dict[str, Any]:
        """
        Extract visual cues from frame using vision model.

        Returns:
            Dict with jersey_number, position, movement_pattern, build
        """
        try:
            frame_bytes = base64.b64decode(frame_b64)
        except Exception as exc:
            self.logger.error("frame_decode_error", error=str(exc))
            return {}

        # Prompt for visual cue extraction
        prompt = f"""You are an expert football vision analyst. Extract player identification cues from this frame.

Return ONLY valid JSON:
{{
    "jersey_number": <int or null>,
    "jersey_number_confidence": <0.0-1.0>,
    "position": "<left_wing|right_wing|center_back|defensive_mid|attacking_mid|striker|goalkeeper|fullback>",
    "position_confidence": <0.0-1.0>,
    "movement_pattern": "<making_run|dropping_deep|pressing|tracking_back|crossing|shooting|passing>",
    "movement_confidence": <0.0-1.0>,
    "build": "<tall|medium|short|stocky|lean|athletic>",
    "build_confidence": <0.0-1.0>,
    "jersey_color": "<primary|secondary|goalkeeper>",
    "occlusion": "<none|partial|heavy>"
}}

If jersey number is not visible due to occlusion or angle, set it to null.
Be honest about confidence levels."""

        response_text = await self.call_llm(
            prompt,
            temperature=0.3,  # Low temp for factual extraction
            max_tokens=300,
            image_data=frame_bytes,
            response_format="json",
        )

        try:
            cues = await self.parse_json_response(response_text)
        except Exception:
            self.logger.warning("visual_cues_parse_error")
            cues = {}

        return cues

    def _score_visual_cues(
        self,
        visual_cues: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Score each visual cue with weighted confidence.

        Returns:
            Dict mapping cue type to {score, candidate_players}
        """
        scores = {}

        # Jersey number scoring (50% weight)
        jersey_num = visual_cues.get("jersey_number")
        jersey_conf = visual_cues.get("jersey_number_confidence", 0.0)
        scores["jersey_number"] = {
            "value": jersey_num,
            "score": jersey_conf * CUE_WEIGHTS["jersey_number"],
            "candidates": self._get_players_by_jersey_number(jersey_num) if jersey_num else [],
        }

        # Position scoring (20% weight)
        position = visual_cues.get("position")
        position_conf = visual_cues.get("position_confidence", 0.0)
        scores["position"] = {
            "value": position,
            "score": position_conf * CUE_WEIGHTS["position"],
            "candidates": self._get_players_by_position(position) if position else [],
        }

        # Movement pattern scoring (15% weight)
        movement = visual_cues.get("movement_pattern")
        movement_conf = visual_cues.get("movement_confidence", 0.0)
        scores["movement_pattern"] = {
            "value": movement,
            "score": movement_conf * CUE_WEIGHTS["movement_pattern"],
            "candidates": self._get_players_by_movement(movement) if movement else [],
        }

        # Build scoring (15% weight)
        build = visual_cues.get("build")
        build_conf = visual_cues.get("build_confidence", 0.0)
        scores["build"] = {
            "value": build,
            "score": build_conf * CUE_WEIGHTS["build"],
            "candidates": self._get_players_by_build(build) if build else [],
        }

        return scores

    def _fuse_with_lineup_context(
        self,
        cue_scores: Dict[str, Dict[str, Any]],
        lineup_context: Optional[Dict[str, Any]],
        game_state: Optional[GameState],
    ) -> PlayerIdentification:
        """
        Fuse visual cue scores with lineup context.

        Args:
            cue_scores: Scored visual cues
            lineup_context: Lineup data
            game_state: Game state for active player filter

        Returns:
            PlayerIdentification with fused confidence
        """
        # Collect candidate players from each cue
        all_candidates: Dict[str, float] = {}  # player_name -> cumulative score

        for cue_type, cue_data in cue_scores.items():
            candidates = cue_data.get("candidates", [])
            score = cue_data.get("score", 0.0)
            for player in candidates:
                all_candidates[player] = all_candidates.get(player, 0.0) + score

        if not all_candidates:
            return PlayerIdentification(
                player_name=None,
                confidence=0.0,
                source="visual_cues_only",
                qualifier=QUALIFIERS["low"],
            )

        # Find best candidate
        best_player = max(all_candidates, key=all_candidates.get)
        raw_confidence = all_candidates[best_player]

        # Normalize confidence (max possible is sum of all weights = 1.0)
        normalized_confidence = min(raw_confidence, 1.0)

        # Determine source attribution
        sources = []
        if cue_scores.get("jersey_number", {}).get("value") is not None:
            sources.append("jersey_number")
        if cue_scores.get("position", {}).get("value") is not None:
            sources.append("position_data")
        if lineup_context:
            sources.append("lineup_data")

        return PlayerIdentification(
            player_name=best_player,
            confidence=normalized_confidence,
            source=" + ".join(sources) if sources else "visual_analysis",
            jersey_number=cue_scores.get("jersey_number", {}).get("value"),
            position=cue_scores.get("position", {}).get("value"),
            visual_cues={k: v.get("value") for k, v in cue_scores.items()},
        )

    def _apply_contextual_bonus(self, result: PlayerIdentification) -> None:
        """Apply +10% bonus if player is in lineup and has recent touch."""
        if not result.player_name:
            return

        bonus_applied = False

        # Check if player is in active lineup
        if result.player_name in self.active_players:
            bonus_applied = True

        # Check if player has recent touch
        if result.player_name in self.recent_touches:
            bonus_applied = True

        if bonus_applied:
            result.confidence = min(result.confidence + CONTEXTUAL_BONUS, 1.0)
            result.source += " + contextual_bonus"

    def _get_qualifier(
        self,
        player_name: Optional[str],
        confidence: float,
        source: str,
    ) -> str:
        """
        Get qualifier string based on confidence tier.

        Tiers:
        - High (> 90%): No qualifier - direct ID
        - Medium (70-90%): "That appears to be X based on Y"
        - Low (< 70%): Ambiguous - no name used
        """
        if confidence >= CONFIDENCE_HIGH:
            return QUALIFIERS["high"]
        elif confidence >= CONFIDENCE_MEDIUM:
            return QUALIFIERS["medium"].format(
                player_name=player_name or "the player",
                source=source,
            )
        else:
            return QUALIFIERS["low"].format(
                position_description="central position"  # Would be more specific in prod
            )

    def _get_players_by_jersey_number(
        self,
        jersey_number: int,
    ) -> List[str]:
        """Get list of players with given jersey number."""
        if not self.lineup_data:
            return []

        candidates = []
        for xi in self.lineup_data.get("home_xi", []) + self.lineup_data.get("away_xi", []):
            if isinstance(xi, dict) and xi.get("jersey_number") == jersey_number:
                candidates.append(xi.get("name", ""))
        return candidates

    def _get_players_by_position(
        self,
        position: str,
    ) -> List[str]:
        """Get list of players who play in given position."""
        if not self.lineup_data:
            return []

        candidates = []
        for xi in self.lineup_data.get("home_xi", []) + self.lineup_data.get("away_xi", []):
            if isinstance(xi, dict):
                player_pos = xi.get("position", "").casefold()
                if position.casefold() in player_pos:
                    candidates.append(xi.get("name", ""))
        return candidates

    def _get_players_by_movement(
        self,
        movement_pattern: str,
    ) -> List[str]:
        """
        Get players likely to exhibit given movement pattern.

        This is a simplified version - in prod, would use player stats.
        """
        # Movement patterns associated with positions
        position_map = {
            "making_run": ["striker", "winger", "forward"],
            "dropping_deep": ["midfielder", "attacking_mid"],
            "pressing": ["forward", "winger", "striker"],
            "tracking_back": ["winger", "fullback", "midfielder"],
            "crossing": ["winger", "fullback"],
            "shooting": ["striker", "forward", "attacking_mid"],
            "passing": ["midfielder", "defensive_mid"],
        }

        positions = position_map.get(movement_pattern.casefold(), [])
        return self._get_players_by_position(positions[0] if positions else "")

    def _get_players_by_build(
        self,
        build: str,
    ) -> List[str]:
        """
        Get players matching physical build.

        Simplified - in prod, would use player height/weight data.
        """
        if not self.lineup_data:
            return []

        # Map build descriptors to height ranges (cm)
        height_map = {
            "tall": (185, 210),
            "medium": (175, 185),
            "short": (160, 175),
            "stocky": (170, 185),
            "lean": (175, 190),
            "athletic": (175, 190),
        }

        height_range = height_map.get(build.casefold(), (0, 220))
        candidates = []

        for xi in self.lineup_data.get("home_xi", []) + self.lineup_data.get("away_xi", []):
            if isinstance(xi, dict):
                height = xi.get("height_cm")
                if height and height_range[0] <= height <= height_range[1]:
                    candidates.append(xi.get("name", ""))

        return candidates

    async def identify_player_for_qa(
        self,
        frame_b64: str,
        question: str,
        game_state: Optional[GameState] = None,
    ) -> Dict[str, Any]:
        """
        Identify player specifically for Q&A answer generation.

        Handles questions like "Who is number 10?" or "Who just scored?"

        Args:
            frame_b64: Current frame
            question: Fan question text
            game_state: Current game state

        Returns:
            Dict for QAAgent to include in answer payload
        """
        self.log_event("player_id_for_qa", {
            "question": question[:50],
        })

        # Extract player reference from question
        jersey_match = re.search(r"number\s*(\d+)", question, re.IGNORECASE)
        if jersey_match:
            jersey_num = int(jersey_match.group(1))
            # Direct lookup from lineup
            player = self._get_players_by_jersey_number(jersey_num)
            if player:
                return {
                    "player_name": player[0],
                    "confidence": 0.95,  # High confidence from direct lookup
                    "source": "jersey_number_lookup",
                    "jersey_number": jersey_num,
                }

        # General player identification from frame
        result = await self.identify_player(frame_b64, game_state=game_state)

        return {
            "player_name": result.player_name,
            "confidence": result.confidence,
            "source": result.source,
            "jersey_number": result.jersey_number,
            "position": result.position,
            "qualifier": result.qualifier,
            "overlay_coordinates": self._generate_overlay_coordinates(result),
        }

    def _generate_overlay_coordinates(
        self,
        player_id: PlayerIdentification,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate SVG overlay coordinates based on confidence.

        High confidence (> 90%): Precise circle
        Medium confidence (70-90%): Zone highlight
        Low confidence (< 70%): No overlay

        Returns:
            Overlay coordinates dict or None
        """
        if player_id.confidence < CONFIDENCE_MEDIUM:
            return None

        # Extract position from visual cues
        position = player_id.visual_cues.get("position", "center")

        # Map position to approximate field coordinates (percentage-based)
        position_coords = {
            "left_wing": {"cx": 25, "cy": 50},
            "right_wing": {"cx": 75, "cy": 50},
            "center_back": {"cx": 50, "cy": 20},
            "defensive_mid": {"cx": 50, "cy": 35},
            "attacking_mid": {"cx": 50, "cy": 65},
            "striker": {"cx": 50, "cy": 80},
            "goalkeeper": {"cx": 50, "cy": 5},
            "fullback": {"cx": 15 if position == "left" else 85, "cy": 25},
        }

        coords = position_coords.get(position, {"cx": 50, "cy": 50})

        if player_id.confidence >= CONFIDENCE_HIGH:
            # Precise circle
            return {
                "type": "circle",
                "cx": coords["cx"],
                "cy": coords["cy"],
                "r": 8,  # Tight radius
                "stroke": "#00ff00",
                "stroke_width": 3,
                "fill": "none",
            }
        else:
            # Zone highlight
            return {
                "type": "zone",
                "cx": coords["cx"],
                "cy": coords["cy"],
                "rx": 15,  # Ellipse radii
                "ry": 12,
                "stroke": "#ffff00",
                "stroke_width": 2,
                "fill": "rgba(255, 255, 0, 0.2)",
            }

    async def log_player_identification(
        self,
        result: PlayerIdentification,
        match_session: Optional[str] = None,
    ) -> None:
        """Log player identification event to DynamoDB."""
        if not result.player_name:
            return

        await write_event(
            "player_identification",
            f"Identified: {result.player_name}",
            {
                "player_name": result.player_name,
                "confidence": result.confidence,
                "source": result.source,
                "jersey_number": result.jersey_number,
                "sport": self.sport,
            },
            match_session=match_session,
        )
