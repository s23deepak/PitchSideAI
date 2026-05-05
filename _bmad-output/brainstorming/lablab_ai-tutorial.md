---
title: "Build and Deploy an AI App on AMD MI300X as a HuggingFace Space"
description: "Learn how to build a Gradio chat interface on top of a vLLM endpoint running on AMD MI300X and deploy it as a HuggingFace Space, turning your backend into a live, shareable demo in under 20 minutes."
image: "https://res.cloudinary.com/dygkv9gam/image/upload/v1777559490/LabLab_Build_AI_App.png"
authorUsername: "stevekimoi"
---

<video controls width="100%">
  <source src="https://res.cloudinary.com/dygkv9gam/video/upload/v1777475886/tutorials/amd-hf-space-deployment/demo.mp4" type="video/mp4" />
</video>

## Introduction

The [AMD Developer Cloud tutorial](https://lablab.ai/ai-tutorials/amd-developer-cloud-host-llm-vllm) gets you to a live vLLM API endpoint running on AMD MI300X hardware in under 30 minutes. That's your backend sorted. But a raw API endpoint isn't a demo. Judges can't click on it, teammates can't try it, and it can't win the HuggingFace Category Prize.

This tutorial picks up from that point. You will build a Gradio chat interface that connects to your vLLM endpoint, push it to HuggingFace as a Space, and end up with a live, publicly accessible demo that anyone can use without touching your GPU.

**What you'll build:** a working chat app hosted under the [lablab-ai-amd-developer-hackathon](https://huggingface.co/spaces/lablab-ai-amd-developer-hackathon/) org on HuggingFace, backed by a model running on AMD MI300X.

**Time:** under 20 minutes if your vLLM endpoint is already running.

## Prerequisites

- A running vLLM endpoint on AMD MI300X (follow the [AMD Developer Cloud tutorial](https://lablab.ai/ai-tutorials/amd-developer-cloud-host-llm-vllm) first)
- The public IP and port of your endpoint (e.g. `http://129.x.x.x:8000/v1`)
- A HuggingFace account
- Python 3.10 or higher

## Step 1: Open Port 8000 on Your AMD Droplet

By default, the AMD Developer Cloud droplet blocks all ports except 22, 80, and 443. Your Gradio Space needs to reach port 8000 to talk to vLLM.

SSH into your droplet and run:

```bash
ufw allow 8000
```

Verify the endpoint is reachable from outside:

```bash
curl -s http://YOUR_DROPLET_IP:8000/v1/models
```

You should see a JSON response listing your loaded model. If you do, your endpoint is publicly accessible.

## Step 2: Create the Project Files

Create a new folder on your local machine:

```bash
mkdir amd-gradio-demo && cd amd-gradio-demo
```

You need three files: `app.py`, `requirements.txt`, and `README.md`.

### app.py

This is the entire chat application (about 30 lines of Python):

```python
import os
import gradio as gr
from openai import OpenAI

VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "meta-llama/Llama-3.1-8B-Instruct")

client = OpenAI(base_url=VLLM_BASE_URL, api_key="not-required")


def chat(message, history):
    messages = [{"role": "system", "content": "You are a helpful assistant."}]
    for item in history:
        if isinstance(item, dict):
            messages.append({"role": item["role"], "content": item["content"]})
        else:
            messages.append({"role": "user", "content": item[0]})
            if item[1]:
                messages.append({"role": "assistant", "content": item[1]})
    messages.append({"role": "user", "content": message})

    stream = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        stream=True,
    )

    partial = ""
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            partial += delta
            yield partial


demo = gr.ChatInterface(
    fn=chat,
    title="AMD MI300X AI Demo",
    description="Chat with an LLM running on AMD MI300X GPU via vLLM.",
    examples=["Explain what AMD MI300X is.", "Write a Python hello world."],
    cache_examples=False,
)

if __name__ == "__main__":
    demo.launch()
```

A few things worth noting:

- `VLLM_BASE_URL` and `MODEL_NAME` are read from environment variables. This means you don't hardcode your endpoint. You configure it via HuggingFace Space secrets instead.
- The `OpenAI` client works directly with vLLM because vLLM exposes an OpenAI-compatible API at `/v1`.
- The `chat` function is a generator. It yields partial responses as they stream in, which gives you the typing effect in the UI.

### requirements.txt

```text
openai>=1.0.0
```

You don't list Gradio here. HuggingFace Spaces installs it automatically based on the `sdk_version` in your README.

### README.md

HuggingFace reads the YAML block at the top of this file to configure your Space:

```markdown
---
title: AMD HuggingFace Demo
emoji: 🚀
colorFrom: red
colorTo: yellow
sdk: gradio
sdk_version: 5.29.0
app_file: app.py
pinned: false
tags:
  - amd
  - amd-hackathon-2026
  - vllm
  - gradio
---

# AMD MI300X AI Demo

A Gradio chat interface connected to a vLLM endpoint running on AMD MI300X GPU.

## Setup

Add these as Space secrets (Settings → Variables and secrets):

| Secret | Value |
|--------|-------|
| `VLLM_BASE_URL` | Your AMD vLLM endpoint, e.g. `http://your-ip:8000/v1` |
| `MODEL_NAME` | Model ID loaded by vLLM, e.g. `Qwen/Qwen2.5-1.5B-Instruct` |
```

The tags are important if you're submitting to the AMD hackathon. The `amd-hackathon-2026` tag makes your Space discoverable under the [lablab-ai-amd-developer-hackathon](https://huggingface.co/spaces/lablab-ai-amd-developer-hackathon/) org.

## Step 3: Test Locally Before Pushing

Install the dependencies in a Python 3.10+ virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install "gradio>=5.0.0" openai
```

Run the app with your AMD endpoint:

```bash
VLLM_BASE_URL="http://YOUR_DROPLET_IP:8000/v1" \
MODEL_NAME="Qwen/Qwen2.5-1.5B-Instruct" \
python app.py
```

Open `http://127.0.0.1:7860` in your browser and send a message. If the model responds, everything is wired up correctly.

![Local Gradio chat interface responding from the AMD MI300X vLLM endpoint](https://res.cloudinary.com/dygkv9gam/image/upload/v1777371964/tutorials/amd-hf-space-deployment/local-test.png)

Testing locally first saves you a round-trip of pushing to the Space, waiting for the build, and debugging in the logs. Catch issues here before they become Space build failures.

Common problems at this stage:

- **Connection refused:** vLLM isn't running inside the container. SSH into the droplet and run `docker exec rocm ps aux | grep vllm` to check. If it's not there, restart it with `docker exec -d rocm bash -c 'vllm serve YOUR_MODEL --host 0.0.0.0 --port 8000 > /tmp/vllm.log 2>&1'`.
- **Timeout:** port 8000 is still blocked. Run `ufw allow 8000` on the droplet.
- **Model not found error:** `MODEL_NAME` doesn't match the model ID vLLM loaded. Check the exact ID with `curl -s http://YOUR_DROPLET_IP:8000/v1/models`.

## Step 4: Create the HuggingFace Space

Go to [huggingface.co/new-space](https://huggingface.co/new-space) and fill in the details:

- **Owner:** `lablab-ai-amd-developer-hackathon` (select the [hackathon org](https://huggingface.co/spaces/lablab-ai-amd-developer-hackathon/))
- **Space name:** choose a name (e.g. `amd-gradio-demo`)
- **SDK:** Gradio
- **Visibility:** Public (required for the hackathon prize) or Private during development

Once created, you'll have an empty git repository at `huggingface.co/spaces/lablab-ai-amd-developer-hackathon/your-space-name`.

## Step 5: Push Your Files to the Space

HuggingFace Spaces are git repositories. Push your files using the `huggingface_hub` Python library:

```python
from huggingface_hub import HfApi

api = HfApi()

for filename in ["app.py", "requirements.txt", "README.md"]:
    api.upload_file(
        path_or_fileobj=filename,
        path_in_repo=filename,
        repo_id="lablab-ai-amd-developer-hackathon/your-space-name",
        repo_type="space",
    )
    print(f"Uploaded: {filename}")
```

Or push via git if you prefer:

```bash
git init
git remote add origin https://huggingface.co/spaces/lablab-ai-amd-developer-hackathon/your-space-name
git add .
git commit -m "Initial commit"
git push origin main
```

The Space will start building immediately after the push. You can watch the build logs in the Space's **App** tab.

## Step 6: Add Your Endpoint as Space Secrets

Your app reads `VLLM_BASE_URL` and `MODEL_NAME` from environment variables. Set them in the Space settings so the hosted app can reach your AMD endpoint.

Go to your Space → **Settings** → **Variables and secrets** → **New secret**:

| Secret name | Value |
|---|---|
| `VLLM_BASE_URL` | `http://YOUR_DROPLET_IP:8000/v1` |
| `MODEL_NAME` | `Qwen/Qwen2.5-1.5B-Instruct` |

Add them as **Secrets** (not Variables). Secrets are private and won't appear in your Space's public settings. The Space will restart automatically once you save.

## Step 7: Verify the Live Space

Open your Space URL (`huggingface.co/spaces/lablab-ai-amd-developer-hackathon/your-space-name`) and send a message. You should see streaming responses from the model running on your AMD MI300X.

![Live HuggingFace Space running on AMD MI300X via vLLM](https://res.cloudinary.com/dygkv9gam/image/upload/v1777371966/tutorials/amd-hf-space-deployment/hf-space-live.png)

If the Space shows a build error, check the **Logs** tab. The most common issues are:

- Wrong `sdk_version` in README.md (use `5.29.0` or higher)
- Missing secrets (`VLLM_BASE_URL` not set)
- Port 8000 still blocked on the droplet

## Conclusion

You now have a live AI app backed by AMD MI300X hardware, deployed as a HuggingFace Space that anyone can use. The full flow took three files and about 30 lines of Python.

If you're submitting to the AMD Developer Hackathon, make sure your Space is public and tagged with `amd-hackathon-2026` before the deadline. The HuggingFace Category Prize goes to the Space with the most likes, so share your link early.

The complete demo Space is available at [huggingface.co/spaces/lablab-ai-amd-developer-hackathon/amd-huggingface-demo](https://huggingface.co/spaces/lablab-ai-amd-developer-hackathon/amd-huggingface-demo).


---
title: "Using Agent Harnesses for AI Hackathons with Claude Code"
description: "Build a Claude Agent SDK harness that autonomously finds and fixes bugs in a Python codebase. A practical guide for AI hackathon teams who need agents that work without babysitting."
image: "https://res.cloudinary.com/dygkv9gam/image/upload/v1777024113/lablab-tutorials/claude-code-agent-harness-tutorial-cover.png"
authorUsername: "stevekimoi"
---

## Introduction

An agent harness is the scaffolding that lets an AI model operate autonomously on a real task: run tools, observe results, and loop until the job is done. Unlike a chat interface where you steer every turn, a harness hands the agent a goal and gets out of the way.

In this tutorial you will build a codebase health agent. Give it a Python project with failing tests and it will run the test suite, read the failures, fix every bug in the source files, and verify the fixes, all without any input from you after the initial command. The agent uses the [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview) and the starter repo is at [github.com/Stephen-Kimoi/claude-code-agent-harness](https://github.com/Stephen-Kimoi/claude-code-agent-harness).

This pattern is directly applicable to [AI hackathons](https://lablab.ai/ai-hackathons): instead of manually triaging failures during a crunch, you fire the agent at a broken test suite and redirect your attention to the feature work that matters.

Here's a preview of the codebase health agent in action:

<video controls width="100%" style={{borderRadius: "8px"}}>
  <source src="https://res.cloudinary.com/dygkv9gam/video/upload/v1777043807/lablab-tutorials/claude-code-agent-harness-demo.mp4" type="video/mp4" />
</video>

### What You'll Build

A Python script (`agent.py`) that:

- Streams a full Claude Code session via the Agent SDK
- Logs every tool call (Bash, Read, Edit, Grep) with color-coded output
- Runs `pytest`, reads failures, edits source files, and re-runs tests
- Reports cost and elapsed time when it finishes

### Prerequisites

- Python 3.10+
- An [Anthropic API key](https://platform.claude.com/)
- Basic familiarity with pytest

---

## Demo

Watch the agent run end-to-end: it picks up 4 failing tests, traces each bug to the source, applies the fixes, and verifies all 6 tests pass.

<video controls width="100%" style={{borderRadius: "8px"}}>
  <source src="https://res.cloudinary.com/dygkv9gam/video/upload/v1777043807/lablab-tutorials/claude-code-agent-harness-demo.mp4" type="video/mp4" />
</video>

---

## Step 1: Clone the Repo and Inspect the Project

```bash
git clone https://github.com/Stephen-Kimoi/claude-code-agent-harness.git
cd claude-code-agent-harness
python3 -m venv venv
source venv/bin/activate
pip install claude-agent-sdk pytest
export ANTHROPIC_API_KEY=your-api-key-here
```

The repo has four files that matter:

<table>
  <thead>
    <tr><th>File</th><th>Purpose</th></tr>
  </thead>
  <tbody>
    <tr><td>`stats.py`</td><td>Python utility library with 3 seeded bugs</td></tr>
    <tr><td>`test_stats.py`</td><td>pytest suite, 4 failures out of 6 tests at the start</td></tr>
    <tr><td>`CLAUDE.md`</td><td>Persistent instructions loaded into every agent session</td></tr>
    <tr><td>`agent.py`</td><td>The harness: drives the SDK, streams output, logs tool calls</td></tr>
  </tbody>
</table>

Confirm the tests are failing before you run the agent:

```bash
pytest test_stats.py -v
# Expected: 4 failed, 2 passed
```

---

## Step 2: Understand the Buggy Source File

`stats.py` contains three intentional bugs that represent real categories of off-by-one and edge-case mistakes:

[`stats.py` lines 1–16 on GitHub](https://github.com/Stephen-Kimoi/claude-code-agent-harness/blob/main/stats.py#L1-L16)

```python
def mean(numbers):
    return sum(numbers) / len(numbers) - 1        # bug: subtracts 1 from every result


def median(numbers):
    sorted_data = sorted(numbers)
    mid = len(sorted_data) // 2
    if len(sorted_data) % 2 == 0:
        return sorted_data[mid]                   # bug: returns one middle element instead of averaging both
    return sorted_data[mid]


def normalize(numbers):
    min_val = min(numbers)
    max_val = max(numbers)
    return [(x - min_val) / (max_val - min_val) for x in numbers]  # bug: ZeroDivisionError when all values are equal
```

The test suite in `test_stats.py` covers all three functions including the edge cases:

[`test_stats.py` lines 5–26 on GitHub](https://github.com/Stephen-Kimoi/claude-code-agent-harness/blob/main/test_stats.py#L5-L26)

```python
def test_mean_basic():
    assert mean([1, 2, 3, 4, 5]) == 3.0

def test_mean_two_values():
    assert mean([10, 20]) == 15.0

def test_median_odd():
    assert median([3, 1, 2]) == 2

def test_median_even():
    assert median([1, 2, 3, 4]) == 2.5           # fails: gets 3 instead of 2.5

def test_normalize_basic():
    assert normalize([0, 5, 10]) == [0.0, 0.5, 1.0]

def test_normalize_uniform():
    assert normalize([5, 5, 5]) == [0.0, 0.0, 0.0]  # fails: ZeroDivisionError
```

The agent's job is to find these failures, trace them to the source, and fix them.

---

## Step 3: Write the Agent's Persistent Instructions (CLAUDE.md)

`CLAUDE.md` is loaded into every Claude Code session automatically. For an agent harness it serves as the standing operating procedure: what the agent must always do, what it must never do, and how it should report results.

[`CLAUDE.md` on GitHub](https://github.com/Stephen-Kimoi/claude-code-agent-harness/blob/main/CLAUDE.md)

```markdown
# Codebase Health Agent

You are a codebase health agent. Your job is to find and fix bugs in Python source files.

## Rules

- Always run the test suite first to see what is failing before touching any code.
- Fix only source files. Never modify test files.
- After making all fixes, run the test suite again to confirm every test passes.
- If a test is still failing after a fix attempt, read the error carefully and try again.
- Report what you fixed and why at the end.
```

Three things make this effective:

1. **Test-first mandate** keeps the agent from guessing. It always has ground truth before editing.
2. **"Never modify test files"** is the guardrail that matters most. Without it, an agent could trivially make tests pass by deleting assertions.
3. **Verify-after-fix** prevents the agent from declaring success after an edit without confirming the tests actually pass.

---

## Step 4: Build the Harness (agent.py)

### 4.1 Imports and Color Palette

The harness imports the Agent SDK types and sets up ANSI colors so tool activity is easy to scan at a glance.

[`agent.py` lines 1–31 on GitHub](https://github.com/Stephen-Kimoi/claude-code-agent-harness/blob/main/agent.py#L1-L31)

```python
import asyncio
import time
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    UserMessage,
    SystemMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
)

RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
CYAN    = "\033[36m"
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
BLUE    = "\033[34m"
MAGENTA = "\033[35m"
RED     = "\033[31m"

TOOL_COLORS = {
    "Bash": CYAN,
    "Read": BLUE,
    "Edit": YELLOW,
    "Grep": MAGENTA,
}
```

Each tool gets a distinct color so you can track what the agent is doing (running commands, reading files, editing code, searching patterns) without reading the full output line by line.

### 4.2 Tool Call Logger

The `log_tool_call` function intercepts each `ToolUseBlock` before it executes and prints a readable summary. The Edit branch shows a mini-diff (up to 3 lines before/after) so you can see exactly what changed without reading the full file:

[`agent.py` lines 34–66 on GitHub](https://github.com/Stephen-Kimoi/claude-code-agent-harness/blob/main/agent.py#L34-L66)

```python
def log_tool_call(block: ToolUseBlock):
    color = TOOL_COLORS.get(block.name, CYAN)
    inp = block.input

    if block.name == "Bash":
        cmd = inp.get("command", "").strip()
        print(f"\n{color}{BOLD}[{block.name}]{RESET} {cmd}")

    elif block.name == "Read":
        path = inp.get("file_path", "")
        limit = inp.get("limit", "")
        suffix = f"  (lines {inp['offset']}–{inp['offset']+limit})" if inp.get("offset") else ""
        print(f"\n{color}{BOLD}[{block.name}]{RESET} {path}{DIM}{suffix}{RESET}")

    elif block.name == "Edit":
        path = inp.get("file_path", "")
        old = inp.get("old_string", "").strip().splitlines()
        new = inp.get("new_string", "").strip().splitlines()
        print(f"\n{color}{BOLD}[{block.name}]{RESET} {path}")
        for line in old[:3]:
            print(f"  {RED}- {line}{RESET}")
        for line in new[:3]:
            print(f"  {GREEN}+ {line}{RESET}")
        if len(old) > 3 or len(new) > 3:
            print(f"  {DIM}... ({max(len(old), len(new))} lines total){RESET}")

    elif block.name == "Grep":
        pattern = inp.get("pattern", "")
        path = inp.get("path", inp.get("include", ""))
        print(f"\n{color}{BOLD}[{block.name}]{RESET} {pattern!r} in {path or '.'}")

    else:
        print(f"\n{color}{BOLD}[{block.name}]{RESET} {str(inp)[:120]}")
```

### 4.3 The Main Loop

The core of the harness is an `async for` loop over the `query()` stream. The SDK emits typed message objects and you handle each type:

[`agent.py` lines 83–135 on GitHub](https://github.com/Stephen-Kimoi/claude-code-agent-harness/blob/main/agent.py#L83-L135)

```python
async def main():
    start = time.time()
    print(f"\n{BOLD}{'─' * 56}{RESET}")
    print(f"{BOLD}  Codebase Health Agent  —  Claude Agent SDK{RESET}")
    print(f"{BOLD}{'─' * 56}{RESET}\n")

    async for message in query(
        prompt=(
            "Run the test suite to see what is failing. "
            "Read the source files to understand the bugs. "
            "Fix every bug in the source files. "
            "Run the tests again to confirm all tests pass. "
            "Do not modify test files."
        ),
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Bash", "Edit", "Grep"],
            permission_mode="acceptEdits",
        ),
    ):
        if isinstance(message, SystemMessage):
            if message.subtype == "init":
                session_id = message.data.get("session_id", "")
                print(f"{DIM}session  {session_id}{RESET}\n")

        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    print(f"\n{DIM}{block.text.strip()}{RESET}")
                elif isinstance(block, ToolUseBlock):
                    log_tool_call(block)

        elif isinstance(message, UserMessage):
            if isinstance(message.content, list):
                for block in message.content:
                    if isinstance(block, ToolResultBlock):
                        log_tool_result(block)

        elif isinstance(message, ResultMessage):
            elapsed = time.time() - start
            cost = f"  ${message.total_cost_usd:.4f}" if message.total_cost_usd else ""
            turns = f"  {message.num_turns} turns"
            print(f"\n{BOLD}{GREEN}{'─' * 56}{RESET}")
            print(f"{BOLD}{GREEN}  Done{RESET}{DIM}  {elapsed:.1f}s{turns}{cost}{RESET}")
            print(f"{BOLD}{GREEN}{'─' * 56}{RESET}\n")
            if message.result:
                print(message.result)


asyncio.run(main())
```

Two `ClaudeAgentOptions` fields control the permission boundary:

- **`allowed_tools`**: only `Read`, `Bash`, `Edit`, and `Grep` are available. The agent cannot create files, make network calls, or access anything outside the working directory.
- **`permission_mode="acceptEdits"`**: file edits are auto-approved without a prompt. This is safe here because the task is scoped to a local project and the `CLAUDE.md` rule prevents test file modification.

---

## Step 5: Run the Agent

```bash
python3 agent.py
```

The agent will:

1. Run `pytest test_stats.py -v` and read the 4 failures
2. Open `stats.py` and trace each failure to its root cause
3. Edit `stats.py` three times, one fix per bug
4. Re-run `pytest` to confirm all 6 tests pass
5. Print a summary with elapsed time and API cost

A typical run takes 30-60 seconds and costs under $0.05 at current Claude pricing.

### What the output looks like

```
────────────────────────────────────────────────────────
  Codebase Health Agent  —  Claude Agent SDK
────────────────────────────────────────────────────────

session  abc123...

[Bash] pytest test_stats.py -v
  FAILED test_stats.py::test_mean_basic
  FAILED test_stats.py::test_mean_two_values
  FAILED test_stats.py::test_median_even
  FAILED test_stats.py::test_normalize_uniform

[Read] stats.py

[Edit] stats.py
  - return sum(numbers) / len(numbers) - 1
  + return sum(numbers) / len(numbers)

[Edit] stats.py
  - return sorted_data[mid]
  + return (sorted_data[mid - 1] + sorted_data[mid]) / 2

[Edit] stats.py
  - return [(x - min_val) / (max_val - min_val) for x in numbers]
  + ... (4 lines total)

[Bash] pytest test_stats.py -v
  6 passed

────────────────────────────────────────────────────────
  Done  42.3s  8 turns  $0.0312
────────────────────────────────────────────────────────
```

---

## Adapting the Harness for Your Own Projects

The structure stays the same for any autonomous coding task. Three things change:

**1. The prompt** in `main()` describes the goal. For a different task, swap it:

```python
prompt="Refactor all functions longer than 40 lines. Extract helpers. Keep tests passing."
```

**2. The `allowed_tools` list** defines what the agent can touch. Add `Write` if the task involves creating new files. Remove `Bash` if you want to block command execution entirely.

**3. `CLAUDE.md`** sets standing rules for the project. Constraints that should apply to every run (never touch migrations, always update the changelog, run the linter after edits) belong here rather than in the prompt.

---

## Hackathon Tips

At an [AI hackathon](https://lablab.ai/ai-hackathons) you rarely have time to triage every failing test manually. A harness like this fits naturally into a parallel workflow:

- **Session 1:** run the harness against your test suite while you work on new features
- **Session 2:** keep active development open in Claude Code Desktop
- **Session 3:** run a separate harness pass focused on a specific module

The harness is stateless and cheap to re-run. If the agent's fixes introduce a regression, re-run with the same prompt and let it self-correct.

Want to practice this pattern under real time pressure? Browse [upcoming AI hackathons on LabLab.ai](https://lablab.ai/ai-hackathons).

---

## Frequently Asked Questions

**Do I need Claude Code Desktop to use the Agent SDK?**

No. The Agent SDK is a Python library that runs from any terminal. Claude Code Desktop is a separate product. The SDK communicates with the Anthropic API directly using your `ANTHROPIC_API_KEY`.

**What does `permission_mode="acceptEdits"` actually do?**

It tells the SDK to auto-approve any file write or edit the agent proposes, without prompting you. Use this only for trusted, scoped tasks. For tasks that touch production code or shared infrastructure, omit this option so you can review each edit before it lands.

**Can the agent modify test files?**

By default, nothing in the SDK prevents it. The protection in this harness comes from the `CLAUDE.md` rule ("Fix only source files. Never modify test files."). That instruction is loaded into every session and Claude follows it reliably for this task.

**How do I point the agent at a different buggy codebase?**

Change the working directory before running the script, or pass a `cwd` parameter to `ClaudeAgentOptions`. Update `CLAUDE.md` to match the test command for that project (for example, `npm test` instead of `pytest`).

**What is the cost of a typical run?**

A single run on this project costs roughly $0.02-0.05 at current Claude Sonnet pricing. The exact cost is printed in the `ResultMessage` at the end of every run via `message.total_cost_usd`.

---

## Conclusion

You now have a working agent harness: a Python script that wraps the Claude Agent SDK, streams a full coding session, logs every tool call, and hands back control only when all tests pass. The same three-part structure (a goal prompt, a constrained tool list, and a `CLAUDE.md` rule set) scales to more complex tasks without changing the harness itself.

The full starter repo is at [github.com/Stephen-Kimoi/claude-code-agent-harness](https://github.com/Stephen-Kimoi/claude-code-agent-harness). Claude Agent SDK reference is at [code.claude.com/docs/en/agent-sdk/overview](https://code.claude.com/docs/en/agent-sdk/overview). Ready to test this under real hackathon pressure? Find your next event at [lablab.ai/ai-hackathons](https://lablab.ai/ai-hackathons).