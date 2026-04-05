# Advanced Agent Architecture — PitchSide AI v2.0

## Overview

The refactored agent system is built on a **scalable, sport-agnostic architecture** with dynamic prompts, professional base classes, and efficient API integration.

### Key Improvements

✅ **Dynamic Sport Support** - Single codebase for 6+ sports (Soccer, Cricket, Basketball, Tennis, Rugby, more)
✅ **Centralized Prompts** - System prompts stored separately, configurable per sport
✅ **Base Agent Class** - Common patterns (logging, error handling, multi-backend model calls)
✅ **Backend Abstraction** - Bedrock by default, with Ollama, OpenAI, and vLLM support behind the same agent interface
✅ **Complex & Efficient** - More sophisticated than prototypes, production-ready
✅ **Better Logging** - Structured event tracking and performance monitoring

---

## Architecture

### Module Structure

```
agents/
├── __init__.py           # Agent exports
├── base.py              # Base classes for all agents
├── research_agent.py    # Pre-match research + Q&A
├── vision_agent.py      # Frame analysis + tactical recognition
├── live_agent.py        # Real-time questions + commentary
└── commentary_agent.py  # Commentary generation + analysis

config/
├── sports.py            # Sport definitions & configurations
└── prompts.py           # Dynamic system prompts
```

### Base Agent Class Hierarchy

```
BaseAgent (abstract)
├── ResearchAgent      → research_agent.ResearchAgent
├── VisionAgent        → vision_agent.VisionAgent
├── LiveAgent          → live_agent.LiveAgent
└── CommentaryAgent    → commentary_agent.CommentaryAgent
```

---

## Agent Specifications

### 1. **ResearchAgent** (Nova Pro)

**Purpose**: Pre-match research and live question answering

**Methods**:
```python
async execute(home_team, away_team) -> str
    → Alias for build_match_brief

async build_match_brief(home_team, away_team) -> str
    → Generate comprehensive match analysis
    → Dynamically adapts to sport type
    → Chunks and indexes for RAG

async answer_live_query(query, home_team=None, away_team=None) -> str
    → Answer fan Q&A during match
    → Uses RAG context retrieval
    → Sport-specific prompt

async research_multiple_topics(home_team, away_team, topics: List[str]) -> Dict[str, str]
    → Research specific topics in detail
    → Returns per-topic analysis
```

**Dynamic Prompts**:
- Soccer: Recent form, tactics, head-to-head, player stats
- Cricket: Runs/wickets, pitch conditions, team combinations
- Basketball: Form, defensive schemes, bench depth
- Rugby: Scrum strength, lineout accuracy, backline pace
- Tennis: Surface preference, serve consistency, fitness

### 2. **VisionAgent** (Nova Lite)

**Purpose**: Real-time frame analysis, tactical recognition, and Bedrock-native clip analysis

**Methods**:
```python
async execute(image_data: bytes) -> Dict[str, Any]
    → Alias for analyze_frame

async analyze_frame(image_data: bytes) -> Dict[str, Any]
    → Analyze single video frame
    → Returns JSON with confidence scores
    → Logs high-confidence detections

async analyze_frame_b64(b64_str: str) -> Dict[str, Any]
    → Analyze base64-encoded JPEG
    → Handles decoding and framing
    → Feeds both the Tactical Brief UI and the live `tactical_detection` WebSocket path

async analyze_frame_sequence(frames: List[bytes], interval: int = 1) -> List[Dict]
    → Analyze multiple frames efficiently
    → Skip-by-interval for optimization
    → Perfect for scene changes or highlight moments

async analyze_video_sequence(frames: List[bytes], timestamps_ms: List[int] | None = None) -> Dict[str, Any]
    → Summarize temporal change across sampled frames
    → Used as the fallback path when the active backend lacks native video input

async analyze_video_clip(video_data: bytes, video_format: str) -> Dict[str, Any]
    → Analyze an uploaded clip natively through Bedrock or vLLM video input
    → Returns the primary tactical phase, key temporal change, and commentary cue

async analyze_video_clip_windowed(video_data: bytes, video_format: str) -> Dict[str, Any]
    → Split a longer clip into overlapping native-video windows with OpenCV
    → Analyze each window natively, then merge them into one tactical summary
```

**Dynamic Outputs**:
- Soccer: Formation, high press, counter-attack, build-up play
- Cricket: Attacking field, defensive field, pace attack, spin attack
- Basketball: Zone defense, fast break, isolation, transitions
- Rugby: Scrum attack, lineout drive, ruck control, set phase

### 3. **LiveAgent** (Nova Sonic)

**Purpose**: Live match interaction and Q&A

**Methods**:
```python
async execute(query: str) -> str
    → Alias for handle_text_query

async start_session(home_team, away_team, sport=None) -> str
    → Initialize live session
    → Pre-load match context via research agent
    → Returns brief text

async handle_text_query(query: str) -> str
    → Answer live fan questions
    → Combines match context + recent events
    → Uses RAG for context

async stream_audio(audio_bytes: bytes) -> str
    → Handle audio chunks (simulated)
    → Future: integrate speech-to-text

async generate_live_commentary(event_description: str) -> str
    → Generate commentary for match event
    → Sport-adaptive response
    → Real-time engagement
    → Also used for tactical detections after the server emits the explicit analyst note
```

### 4. **CommentaryAgent** (Nova Pro)

**Purpose**: Professional match commentary

**Methods**:
```python
async generate_commentary(match_context: str, recent_events: str) -> str
    → Generate live commentary segment
    → Sport-specific language

async generate_tactical_commentary(tactical_situation: str, team_context=None) -> str
    → Analyze tactical patterns
    → Strategic insights

async generate_player_insight(player_name, team_name, recent_performance) -> str
    → Individual player analysis
    → Broadcast-quality insight

async generate_match_narrative(periods: List[Dict]) -> str
    → Multi-period narrative arc
    → Highlights key turning points

async generate_prediction(current_state, remaining_time=None) -> str
    → Forecast likely scenarios
    → Next likely outcomes

async generate_match_summary(final_score, key_moments, match_stats=None) -> str
    → Post-match analysis
    → Statistical breakdown
```

---

## Sport Configuration System

### Adding a New Sport

1. **Define Sport Type**:
```python
# config/sports.py
class SportType(str, Enum):
    NEW_SPORT = "new_sport"
```

2. **Create Configuration**:
```python
SPORTS_CONFIG: Dict[SportType, SportConfig] = {
    SportType.NEW_SPORT: SportConfig(
        sport_type=SportType.NEW_SPORT,
        display_name="New Sport",
        formation_regex=[...],
        key_metrics=[...],
        tactical_labels=[...],
        team_positions=[...],
        research_topics=[...]
    ),
}
```

3. **Agents automatically adapt** - No code changes needed in agents!

### Supported Sports (Out of Box)

| Sport | Formations | Tactical Labels | Key Metrics |
|-------|-----------|-----------------|-------------|
| ⚽ Soccer | 4-3-3, 3-5-2, etc | High Press, Counter Attack | Possession, Shots |
| 🏏 Cricket | N/A | Pace Attack, Spin Attack | Run Rate, Wickets |
| 🏀 Basketball | N/A | Pick & Roll, Fast Break | Points, Assists |
| 🎾 Tennis | N/A | Serve & Volley, Rally | Serve Speed, Aces |
| 🏈 Rugby | N/A | Scrum Attack, Maul | Tries, Tackles |
| 🧊 Hockey | N/A | Power Play, Penalty Kill | Goals, Shots |

---

## Dynamic Prompts System

### Prompt Organization

```
config/prompts.py

SystemPrompts class:
├── research_brief_prompt(home_team, away_team, sport) → str
├── live_query_prompt(context, query, sport) → str
├── frame_analysis_prompt(sport, include_formations) → str
├── commentary_generation_prompt(sport, match_context, events) → str
└── tactical_analysis_prompt(sport, patterns) → str
```

### How Prompts Work

1. **Sport-Aware Content**:
```python
# Soccer → "formation", "tactical_label"
# Cricket → "field setup", "bowling strategy"
# Basketball → "defensive scheme", "timeout strategy"

config = get_sport_config("soccer")
labels = config.tactical_labels  # Returns sport-specific tactics
metrics = config.key_metrics    # Returns sport-specific stats
```

2. **Dynamic Prompt Generation**:
```python
prompt = get_frame_prompt("soccer")
# Returns soccer-specific frame analysis prompt

prompt = get_frame_prompt("cricket")
# Returns cricket-specific frame analysis prompt
# Same code, different sport!
```

---

## Integration with Orchestration

### Registering Agents with Orchestrator

```python
# api/server.py
orchestrator = get_orchestrator()

# Register agent handlers
from agents.research_agent import ResearchAgent
from agents.vision_agent import VisionAgent

research = ResearchAgent()
orchestrator.register_agent_handler(
    AgentType.RESEARCH,
    research.execute
)
```

### Using in Workflows

```python
# Submit research task
task_id = await orchestrator.submit_task(
    workflow_id,
    AgentType.RESEARCH,
    "build_brief",
    {
        "home_team": "Manchester City",
        "away_team": "Liverpool",
        "sport": "soccer"
    },
    priority=10
)

# Get result
result = orchestrator.get_task_result(task_id)
```

---

## Event Logging

### Structured Event Tracking

All agents log events to DynamoDB via `tools.dynamodb_tool.write_event()`:

```python
# Video frame analysis
write_event("tactical_detection", observation, {
    "label": "High Press",
    "confidence": 0.92,
    "sport": "soccer"
})

# Live Q&A
write_event("fan_qa", question, {
    "question": "What's the pressing strategy?",
    "answer": "They're using aggressive gegenpressing...",
    "sport": "soccer"
})

# Commentary
write_event("commentary", snippet, {
    "full_commentary": "...",
    "sport": "soccer"
})
```

### Performance Logging

Agents track execution time and success:

```python
logger.log_performance(
    operation="research_agent.bedrock_call",
    duration_ms=1234.5,
    success=True
)
```

---

## Error Handling

### Graceful Degradation

```python
# Video analysis fails
try:
    result = await vision_agent.analyze_frame(image_bytes)
except Exception as exc:
    logger.error("frame_analysis_parse_error", error=str(exc))
    # Return default fallback
    result = {
        "tactical_label": "Analysis Failed",
        "confidence": 0.0,
        "actionable_insight": "Retrying next frame"
    }
```

### Automatic Retry

Connection pool handles retries:

```python
result = await pool.execute_with_retry(
    agent.call_bedrock(...),
    max_retries=3
)
```

---

## Performance Characteristics

### API Latency (Bedrock)

| Operation | Model | Latency | Input |
|-----------|-------|---------|-------|
| Frame Analysis | Nova Lite | 2-3s | 1 JPEG |
| Research Brief | Nova Pro | 5-10s | Text prompt |
| Live Query | Nova Pro | 2-4s | Context + question |
| Commentary | Nova Pro | 3-5s | Events + context |

### Concurrency Model

```
Max Concurrent Tasks: 20 (configurable)
Per-Client Rate Limit: 100 req/min
Burst Capacity: 10 tokens
```

### Memory Profile

- Research Agent: ~50MB (loads RAG retriever)
- Vision Agent: ~30MB (Nova Lite model handles image encoding)
- Live Agent: ~40MB (includes research agent)
- Commentary Agent: ~50MB (uses Nova Pro)

---

## Usage Examples

### Example 1: Pre-Match Research

```python
research = ResearchAgent(sport="soccer")

# Generate brief
brief = await research.build_match_brief(
    "Manchester City",
    "Liverpool"
)

# Research specific topics
topics_result = await research.research_multiple_topics(
    "Manchester City",
    "Liverpool",
    ["recent form", "key injuries", "head-to-head record"]
)
```

### Example 2: Real-Time Vision

```python
vision = VisionAgent(sport="soccer")

# Single frame
result = await vision.analyze_frame(jpeg_bytes)

# Multiple frames (optimized)
results = await vision.analyze_frame_sequence(
    [frame1, frame2, frame3],
    interval=2  # Analyze every 2nd frame
)
```

### Example 3: Live Commentary

```python
commentary = CommentaryAgent(sport="soccer")

# Generate play-by-play
commentary_text = await commentary.generate_commentary(
    match_context=match_brief,
    recent_events="Goal scored by Haaland"
)

# Tactical breakdown
tactical = await commentary.generate_tactical_commentary(
    "High press activated by Manchester City"
)
```

### Example 4: Orchestrated Workflow

```python
orchestrator = get_orchestrator()

# Create workflow
context = WorkflowContext(
    match_id="man_city_vs_liverpool",
    home_team="Manchester City",
    away_team="Liverpool",
    sport="soccer"
)
workflow_id = await orchestrator.start_workflow(context)

# Submit parallel tasks
research_task = await orchestrator.submit_task(
    workflow_id, AgentType.RESEARCH, "build_brief", {...}
)
vision_task = await orchestrator.submit_task(
    workflow_id, AgentType.VISION, "analyze", {...}
)

# Wait for results
research_result = orchestrator.get_task_result(research_task)
vision_result = orchestrator.get_task_result(vision_task)
```

---

## Comparison: Old vs New Architecture

| Aspect | Old | New |
|--------|-----|-----|
| **Sport Support** | 2 (Soccer, Cricket) | 6+ (fully extensible) |
| **Prompts** | Hardcoded in agents | Centralized, dynamic |
| **Base Class** | None | Complete base class |
| **Error Handling** | Basic try/catch | Comprehensive |
| **Logging** | Print statements | Structured events |
| **Concurrency** | Simple | Advanced (circuits/pools) |
| **Code Lines** | ~150 per agent | ~250 per agent (more capability) |
| **Extensibility** | Hard | Easy (add sport config) |
| **Performance** | Average | Optimized |

---

## Backend Strategy

1. **Bedrock Stays Default** - AWS-managed Nova models remain the primary production path.
2. **vLLM Enables Native Local Video** - Video-capable VLMs can now receive uploaded clips directly through the OpenAI-compatible server.
3. **Windowed Native Retry Protects vLLM** - When a full clip exceeds the active vLLM context length, the backend retries the upload as overlapping native-video windows and merges the results.
4. **Ollama Remains Image-Only Here** - Tactical video still works locally through dense sampled-frame fallback when native clip input is unavailable.
5. **Single Agent Interface** - All of these backends still route through `BaseAgent`, so agent logic remains backend-agnostic.
6. **Operational Choice** - Teams can trade off managed infrastructure, self-hosting, and model selection without forking the agent layer.

---

## Next Steps

### Immediate
1. ✅ Centralized sport configurations
2. ✅ Dynamic prompts system
3. ✅ Base agent classes
4. ✅ Refactored agents (research, vision, live, commentary)

### Soon
- [ ] API endpoint for setting sport type
- [ ] Agent telemetry dashboard
- [ ] A/B testing different prompts
- [ ] Multi-model comparison (Lite vs Pro)

### Future
- [ ] Agent fine-tuning with match data
- [ ] Real speech-to-text integration
- [ ] Custom agent types per sport
- [ ] Agent chaining for complex workflows

---

## Files Modified/Created

```
NEW FILES:
✅ config/sports.py              - Sport definitions
✅ config/prompts.py             - Dynamic prompts
✅ agents/base.py               - Base classes
✅ agents/commentary_agent.py    - New agent

UPDATED FILES:
✅ agents/research_agent.py      - Dynamic prompts, base class
✅ agents/vision_agent.py        - Dynamic prompts, base class
✅ agents/live_agent.py          - Dynamic prompts, base class
```

---

**Architecture Version**: 2.0 | **Status**: Production Ready | **Last Updated**: March 2026
