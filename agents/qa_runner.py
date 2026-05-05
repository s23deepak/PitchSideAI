#!/usr/bin/env python3
"""
Q&A Runner — Production Orchestration Module

Orchestrates Q&A Backend (Story 2.2) and Player Identification (Story 2.4)
agents in parallel for integrated fan Q&A experience.

This is a production module used by the WebSocket handler in api/server.py.

Usage:
    # Production usage (see api/server.py):
    from agents.qa_runner import QARunner

    runner = QARunner(sport="soccer")
    await runner.initialize_session(home_team, away_team, lineup_data, notes_store)
    result = await runner.handle_fan_question(question, frame_b64)

    # Testing:
    python -m agents.qa_runner --test
"""
import argparse
import asyncio
import base64
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agents.qa_agent import QAAgent, QAPair
from agents.player_id_agent import PlayerIDAgent, PlayerIdentification
from models.game_state import GameState
from models.notes_store import NotesStore


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class QARunner:
    """
    Production orchestrator for Q&A + Player ID parallel execution.

    Flow:
    1. Initialize both QAAgent and PlayerIDAgent
    2. Load lineup data and pre-computed Q&A cache from notes pipeline
    3. On fan question:
       - Detect if player reference (by number or name)
       - If yes and frame available: run PlayerID + QA in parallel via asyncio.gather()
       - If no: run QA only
    4. Merge results and broadcast to WebSocket clients

    Attributes:
        qa_agent: Q&A agent for answer generation (Story 2.2)
        player_id_agent: Player identification agent (Story 2.4)
        game_state: Current match state (score, minute, events)
        match_session: Session identifier for DynamoDB
    """

    def __init__(self, sport: str = "soccer"):
        """
        Initialize Q&A runner with sport-specific agents.

        Args:
            sport: Sport type (soccer, cricket, etc.)
        """
        self.qa_agent = QAAgent(sport=sport)
        self.player_id_agent = PlayerIDAgent(sport=sport)
        self.game_state: Optional[GameState] = None
        self.match_session: str = "demo_match"

    async def initialize_session(
        self,
        home_team: str,
        away_team: str,
        lineup_data: Optional[Dict[str, Any]] = None,
        notes_store: Optional[NotesStore] = None,
    ) -> None:
        """
        Initialize session with teams, lineup, and pre-computed notes.

        Args:
            home_team: Home team name
            away_team: Away team name
            lineup_data: Starting XI + substitutes from data sources
            notes_store: Pre-computed commentary notes from Story 1.3 pipeline
        """
        logger.info(f"Initializing session: {home_team} vs {away_team}")

        # Initialize Q&A agent with pre-computed notes cache
        await self.qa_agent.start_session(
            home_team=home_team,
            away_team=away_team,
            match_session=self.match_session,
            notes_store=notes_store,
        )

        # Set lineup data for player ID agent
        if lineup_data:
            self.player_id_agent.set_lineup_data(lineup_data)

        # Initialize game state tracker
        self.game_state = GameState(home_team=home_team, away_team=away_team)

        # Load Q&A cache from notes if available (O(1) lookup for pre-computed answers)
        if notes_store:
            self.qa_agent.load_qa_cache_from_notes(notes_store)
            logger.info(f"Loaded {len(self.qa_agent.qa_cache)} Q&A pairs from notes")

        logger.info("Session initialized")

    def _detect_player_reference(self, question: str) -> bool:
        """
        Check if question references a player (by number or name).

        Patterns detected:
        - "number 10", "who's #7" (jersey number)
        - "who is", "who just scored" (player identity)
        - Any standalone number token

        Args:
            question: Fan question text

        Returns:
            True if player reference detected
        """
        import re

        patterns = [
            r"number\s*\d+",  # "number 10", "who's #7"
            r"who\s+(is|just|scored)",  # "who is", "who just"
            r"\b\d+\b",  # Any number reference
        ]
        for pattern in patterns:
            if re.search(pattern, question, re.IGNORECASE):
                return True
        return False

    async def _run_player_identification(
        self,
        frame_b64: Optional[str],
        question: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Run player identification in parallel with Q&A.

        Args:
            frame_b64: Current frame (optional)
            question: Fan question

        Returns:
            Player ID result dict or None on failure
        """
        if not frame_b64:
            logger.warning("No frame provided for player ID")
            return None

        try:
            result = await self.player_id_agent.identify_player_for_qa(
                frame_b64=frame_b64,
                question=question,
                game_state=self.game_state,
            )
            return result
        except Exception as exc:
            logger.error(f"Player ID failed: {exc}")
            return None

    async def _run_qa_generation(
        self,
        question: str,
        player_id_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Run Q&A answer generation.

        Args:
            question: Fan question
            player_id_result: Optional player ID result to inject into answer

        Returns:
            QA result dict with answer, temporal_context, source, etc.
        """
        # Simulate retained frames for temporal context (in prod, from KV cache)
        retained_frames = []  # Would be populated from streaming bridge

        result = await self.qa_agent.handle_query(
            question=question,
            game_state=self.game_state,
            retained_frames=retained_frames,
        )

        # Inject player info if available from parallel PlayerID agent
        if player_id_result:
            result["player_identification"] = player_id_result
            result["overlay_coordinates"] = player_id_result.get("overlay_coordinates")

        return result

    async def handle_fan_question(
        self,
        question: str,
        frame_b64: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle fan question with parallel Q&A + Player ID execution.

        This is the main entry point called by the WebSocket handler.

        Args:
            question: Fan question text
            frame_b64: Optional current frame for player ID (base64 JPEG)

        Returns:
            Combined result dict with:
            - answer/text: The generated answer
            - player_identification: Player info if identified
            - overlay_coordinates: SVG overlay coords for split-screen
            - gameState: Current match state
        """
        logger.info(f"Handling question: {question}")

        # Check if player reference detected
        needs_player_id = self._detect_player_reference(question)

        if needs_player_id and frame_b64:
            # Run both agents in parallel (asyncio.gather with return_exceptions)
            logger.info("Running Q&A + Player ID in parallel")
            qa_task, player_id_task = await asyncio.gather(
                self._run_qa_generation(question, None),  # Will merge player info later
                self._run_player_identification(frame_b64, question),
                return_exceptions=True,
            )

            # Handle exceptions gracefully
            if isinstance(qa_task, Exception):
                logger.error(f"QA failed: {qa_task}")
                qa_result = {"type": "answer", "text": "Unable to process question"}
            else:
                qa_result = qa_task

            if isinstance(player_id_task, Exception):
                logger.error(f"Player ID failed: {player_id_task}")
                player_id_result = None
            else:
                player_id_result = player_id_task

            # Merge results if both succeeded
            if player_id_result:
                qa_result["player_identification"] = player_id_result
                qa_result["overlay_coordinates"] = player_id_result.get("overlay_coordinates")

                # Inject player name into answer if identified with high confidence
                if player_id_result.get("confidence", 0) > 0.7 and player_id_result.get("player_name"):
                    qa_result["answer_includes_player"] = True

        else:
            # Q&A only (no player reference or no frame available)
            logger.info("Running Q&A only (no player reference or no frame)")
            qa_result = await self._run_qa_generation(question)

        # Attach current game state for client display
        qa_result["gameState"] = self.game_state.to_dict() if self.game_state else None

        return qa_result

    async def run_demo(self, questions: List[str]) -> List[Dict[str, Any]]:
        """
        Run demo with sample questions.

        Args:
            questions: List of fan questions to process

        Returns:
            List of result dicts for each question
        """
        results = []

        # Demo frame (placeholder - in prod would be real frame from stream)
        demo_frame_b64 = None  # Would be base64-encoded JPEG

        for i, question in enumerate(questions):
            logger.info(f"Processing question {i+1}/{len(questions)}: {question}")
            result = await self.handle_fan_question(question, demo_frame_b64)
            results.append(result)

            # Simulate game state updates between questions
            if i == 0:
                self.game_state.home_score = 1
                self.game_state.match_minute = 34

        return results


async def run_test():
    """Run integration test for Stories 2.2 + 2.4."""
    logger.info("Starting Stories 2.2 + 2.4 Integration Test")

    # Create runner
    runner = QARunner(sport="soccer")

    # Initialize session with demo data
    lineup_data = {
        "home_xi": [
            {"name": "Haaland", "jersey_number": 9, "position": "striker", "height_cm": 194},
            {"name": "De Bruyne", "jersey_number": 17, "position": "attacking_mid", "height_cm": 181},
            {"name": "Rodri", "jersey_number": 16, "position": "defensive_mid", "height_cm": 191},
        ],
        "away_xi": [
            {"name": "Salah", "jersey_number": 11, "position": "right_wing", "height_cm": 175},
            {"name": "Van Dijk", "jersey_number": 4, "position": "center_back", "height_cm": 193},
        ],
    }

    await runner.initialize_session(
        home_team="Man City",
        away_team="Liverpool",
        lineup_data=lineup_data,
    )

    # Test questions covering different scenarios
    test_questions = [
        "Who is number 9?",  # Should trigger player ID
        "What formation are they playing?",  # Q&A only
        "Who just scored?",  # Should trigger player ID
        "Why is that a red card?",  # Q&A only (pre-computed cache)
    ]

    results = await runner.run_demo(test_questions)

    # Print results
    print("\n" + "=" * 60)
    print("STORIES 2.2 + 2.4 INTEGRATION TEST RESULTS")
    print("=" * 60)

    for i, (question, result) in enumerate(zip(test_questions, results)):
        print(f"\nQ{i+1}: {question}")
        print(f"  Answer: {result.get('text', 'N/A')[:100]}...")
        print(f"  Source: {result.get('source', 'N/A')}")
        print(f"  Temporal Context: {result.get('temporal_context', 'N/A')}")

        player_id = result.get("player_identification")
        if player_id:
            print(f"  Player ID: {player_id.get('player_name', 'N/A')}")
            print(f"  Confidence: {player_id.get('confidence', 0):.0%}")
            print(f"  Source: {player_id.get('source', 'N/A')}")

            overlay = player_id.get("overlay_coordinates")
            if overlay:
                print(f"  Overlay: {overlay.get('type')} at ({overlay.get('cx')}, {overlay.get('cy')})")

        print(f"  Game State: {result.get('gameState', {})}")

    print("\n" + "=" * 60)
    logger.info("Integration test completed")

    return results


def main():
    """CLI entry point for testing and interactive mode."""
    parser = argparse.ArgumentParser(
        description="Q&A Runner — Stories 2.2 (Q&A) and 2.4 (Player ID) orchestration"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run integration test",
    )
    parser.add_argument(
        "--home",
        type=str,
        default="Home Team",
        help="Home team name",
    )
    parser.add_argument(
        "--away",
        type=str,
        default="Away Team",
        help="Away team name",
    )
    parser.add_argument(
        "--question",
        type=str,
        default="Who is number 10?",
        help="Fan question to process",
    )

    args = parser.parse_args()

    if args.test:
        asyncio.run(run_test())
    else:
        # Interactive mode
        async def interactive():
            runner = QARunner()
            await runner.initialize_session(args.home, args.away)

            print(f"\nInteractive mode: {args.home} vs {args.away}")
            print("Type 'quit' to exit\n")

            while True:
                question = input("Fan question: ").strip()
                if question.lower() in ("quit", "exit"):
                    break

                result = await runner.handle_fan_question(question)
                print(f"Answer: {result.get('text', 'Unable to process')}\n")

        asyncio.run(interactive())


if __name__ == "__main__":
    main()
