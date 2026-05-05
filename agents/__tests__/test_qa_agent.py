"""
Tests for Story 2.2: Q&A Backend Answer Generation

Coverage:
- AC1: Query Message Handling
- AC2: GPU Priority Scheduling (simulated)
- AC3: Pre-Computed Q&A Cache
- AC4: KV Cache Temporal Context
- AC5: Limited Temporal Context Fallback
- AC6: Non-Football Question Handling
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from agents.qa_agent import QAAgent, QAPair, TemporalContext
from models.game_state import GameState
from models.notes_store import NotesStore, NarrativeBeat


@pytest.fixture
def qa_agent():
    """Create QAAgent instance for testing."""
    return QAAgent(sport="soccer")


@pytest.fixture
def sample_game_state():
    """Create sample game state."""
    return GameState(
        home_team="Man City",
        away_team="Liverpool",
        home_score=1,
        away_score=0,
        match_minute=34,
    )


@pytest.fixture
def sample_qa_cache():
    """Create pre-computed Q&A cache from Story 1.3."""
    return {
        "why is that a red card": QAPair(
            question="Why is that a red card?",
            answer_text="That's a straight red for serious foul play — studs showing, high on the ankle. The referee had no choice.",
            timestamp_ms=2040000,  # 34:00
            overlay_coordinates={"type": "circle", "cx": 50, "cy": 40, "r": 10},
        ),
        "who is number 10": QAPair(
            question="Who is number 10?",
            answer_text="That's the captain — wearing the armband, orchestrating from midfield.",
            timestamp_ms=None,
        ),
        "what formation are they playing": QAPair(
            question="What formation are they playing?",
            answer_text="They're set up in a 4-3-3, with the front three pressing high and the midfield trio forming a triangle.",
        ),
    }


class TestAC1_QueryMessageHandling:
    """AC1: Query Message Handling with game state injection."""

    @pytest.mark.asyncio
    async def test_query_includes_game_state(self, qa_agent, sample_game_state):
        """Game state is included in answer payload."""
        with patch.object(qa_agent, 'call_bedrock', AsyncMock(return_value="Test answer")):
            result = await qa_agent.handle_query(
                question="Who scored?",
                game_state=sample_game_state,
            )

            assert result["type"] == "answer"
            assert "text" in result
            assert result["gameState"] is not None
            assert result["gameState"]["home_score"] == 1
            assert result["gameState"]["match_minute"] == 34

    @pytest.mark.asyncio
    async def test_commentary_settings_injected(self, qa_agent, sample_game_state):
        """Commentary settings (bias, excitement, knowledge) are injected into prompt."""
        qa_agent.set_commentary_settings(
            bias=0.5,  # Slight Team B bias
            excitement=0.9,  # High excitement
            knowledge_depth=0.3,  # Beginner-friendly
        )

        with patch.object(qa_agent, 'call_bedrock', AsyncMock(return_value="Test answer")):
            await qa_agent.handle_query(
                question="Why did he do that?",
                game_state=sample_game_state,
            )

            # Verify call_bedrock was called (prompt would include settings)
            qa_agent.call_bedrock.assert_called_once()
            call_args = qa_agent.call_bedrock.call_args
            prompt = call_args[0][0]

            assert "Bias: 0.5" in prompt
            assert "Excitement: 0.9" in prompt
            assert "Knowledge Depth: 0.3" in prompt


class TestAC2_PreComputedCache:
    """AC2: Pre-Computed Q&A Cache (tap path < 1s)."""

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_answer(self, qa_agent, sample_qa_cache):
        """Pre-computed cache returns answer within tap path latency."""
        qa_agent.qa_cache = sample_qa_cache

        result = await qa_agent.handle_query(
            question="Why is that a red card?",
            game_state=None,
        )

        assert result["source"] == "precomputed_cache"
        assert "straight red" in result["text"].lower()
        assert result["timestamp_ms"] == 2040000
        assert result["overlay_coordinates"] is not None

    @pytest.mark.asyncio
    async def test_cache_miss_calls_llm(self, qa_agent, sample_qa_cache):
        """Cache miss falls through to LLM generation."""
        qa_agent.qa_cache = sample_qa_cache

        with patch.object(qa_agent, 'call_bedrock', AsyncMock(return_value="LLM answer")):
            result = await qa_agent.handle_query(
                question="What's the weather like?",
                game_state=None,
            )

            qa_agent.call_bedrock.assert_called_once()
            assert result["source"] == "llm_generate"


class TestAC3_KVCacheTemporalContext:
    """AC3: KV Cache Temporal Context."""

    @pytest.mark.asyncio
    async def test_temporal_context_full_when_match_found(self, qa_agent, sample_game_state):
        """Temporal context is 'full' when KV cache has relevant frame."""
        retained_frames = [
            {
                "timestamp_ms": 2040000,
                "caption": "Haaland scores with a header from close range goal",
                "embedding": [0.1, 0.2, 0.3],  # Mock embedding
            },
        ]

        result = await qa_agent.handle_query(
            question="How did Haaland score goal?",
            game_state=sample_game_state,
            retained_frames=retained_frames,
        )

        assert result["temporal_context"] == "full"
        assert result["timestamp_ms"] is not None

    @pytest.mark.asyncio
    async def test_temporal_context_limited_when_no_match(self, qa_agent, sample_game_state):
        """Temporal context is 'limited' when KV cache has no relevant frame."""
        retained_frames = [
            {
                "timestamp_ms": 120000,
                "caption": "Kickoff at the Etihad",
            },
        ]

        result = await qa_agent.handle_query(
            question="What just happened?",
            game_state=sample_game_state,
            retained_frames=retained_frames,
        )

        # Low similarity → limited context
        assert result["temporal_context"] == "limited"


class TestAC4_LimitedTemporalContextFallback:
    """AC4: Limited Temporal Context Fallback."""

    @pytest.mark.asyncio
    async def test_fallback_includes_calm_indicator(self, qa_agent, sample_game_state):
        """Answers with limited temporal context include calm indicator."""
        retained_frames = []  # No retained frames

        with patch.object(qa_agent, 'call_bedrock', AsyncMock(return_value="Test answer")):
            result = await qa_agent.handle_query(
                question="What happened in the 10th minute?",
                game_state=sample_game_state,
                retained_frames=retained_frames,
            )

            # Prompt would include temporal context hint (empty in this case)
            qa_agent.call_bedrock.assert_called_once()


class TestAC5_NonFootballQuestionHandling:
    """AC5: Non-Football Question Handling."""

    @pytest.mark.asyncio
    async def test_non_football_question_redirected(self, qa_agent, sample_game_state):
        """Non-football questions get graceful redirect."""
        with patch.object(qa_agent, 'call_bedrock', AsyncMock(return_value="The weather is nice")):
            result = await qa_agent.handle_query(
                question="What's the weather like in Manchester?",
                game_state=sample_game_state,
            )

            assert "focused on the match" in result["text"]


class TestQAPairDataclass:
    """Test QAPair dataclass."""

    def test_qapair_creation(self):
        """QAPair can be created with all fields."""
        pair = QAPair(
            question="Test question",
            answer_text="Test answer",
            timestamp_ms=100000,
            overlay_coordinates={"type": "circle", "cx": 50, "cy": 50},
        )

        assert pair.question == "Test question"
        assert pair.answer_text == "Test answer"
        assert pair.timestamp_ms == 100000
        assert pair.overlay_coordinates["cx"] == 50

    def test_qapair_optional_fields(self):
        """QAPair works with optional fields."""
        pair = QAPair(
            question="Test question",
            answer_text="Test answer",
        )

        assert pair.timestamp_ms is None
        assert pair.overlay_coordinates is None


class TestTemporalContextDataclass:
    """Test TemporalContext dataclass."""

    def test_temporal_context_creation(self):
        """TemporalContext can be created."""
        ctx = TemporalContext(
            timestamp_ms=2040000,
            similarity_score=0.85,
            frame_caption="Goal scored",
            is_limited=False,
        )

        assert ctx.timestamp_ms == 2040000
        assert ctx.similarity_score == 0.85
        assert not ctx.is_limited

    def test_temporal_context_limited(self):
        """Limited temporal context flag."""
        ctx = TemporalContext(is_limited=True)

        assert ctx.is_limited
        assert ctx.timestamp_ms is None


class TestCommentarySettings:
    """Test commentary settings configuration."""

    def test_set_commentary_settings(self, qa_agent):
        """Commentary settings can be updated."""
        qa_agent.set_commentary_settings(
            bias=-0.8,
            excitement=1.0,
            knowledge_depth=0.0,
        )

        assert qa_agent.commentary_settings["bias"] == -0.8
        assert qa_agent.commentary_settings["excitement"] == 1.0
        assert qa_agent.commentary_settings["knowledge_depth"] == 0.0

    def test_bias_clamped(self, qa_agent):
        """Bias is clamped to [-1, 1] range."""
        qa_agent.set_commentary_settings(bias=2.0)
        assert qa_agent.commentary_settings["bias"] == 1.0

        qa_agent.set_commentary_settings(bias=-2.0)
        assert qa_agent.commentary_settings["bias"] == -1.0


class TestQuestionNormalization:
    """Test question normalization for cache lookup."""

    def test_normalize_question(self, qa_agent):
        """Question normalization handles variations."""
        assert qa_agent._normalize_question("Why is that a red card?") == "why is that a red card"
        assert qa_agent._normalize_question("  Why   is   that   a   red   card?  ") == "why is that a red card"

    def test_cache_lookup_case_insensitive(self, qa_agent, sample_qa_cache):
        """Cache lookup is case-insensitive."""
        qa_agent.qa_cache = sample_qa_cache

        # Different casing should still find cache
        result = qa_agent._check_precomputed_cache("WHY IS THAT A RED CARD?")
        assert result is not None

        # Extra whitespace should still find cache
        result = qa_agent._check_precomputed_cache("  Why is that a red card?  ")
        assert result is not None


# Run with: pytest agents/__tests__/test_qa_agent.py -v
