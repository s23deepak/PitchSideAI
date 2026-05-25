"""Optional DeepAgents-powered quality layer for commentary notes."""

from __future__ import annotations

import json
import os
from typing import Any, Dict


class DeepNotesResearchAgent:
    """Runs a DeepAgent to produce richer synthesis guidance when enabled.

    DeepAgents is intentionally optional so the production workflow remains
    deployable in environments that have not yet installed/configured the SDK.
    """

    def __init__(self) -> None:
        self.enabled = os.getenv("DEEP_NOTES_ENABLED", "false").lower() in {"1", "true", "yes"}
        self.model = os.getenv("DEEPAGENTS_MODEL", "openai:gpt-5.4")

    async def enrich(self, all_outputs: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "enabled": False,
                "reason": "DEEP_NOTES_ENABLED is not true",
            }

        try:
            from deepagents import create_deep_agent
        except Exception as exc:
            return {
                "enabled": False,
                "reason": f"deepagents package unavailable: {exc}",
            }

        prompt = (
            "You are producing production broadcast football notes. "
            "Use only the supplied JSON. Do not invent facts. Return concise JSON with keys: "
            "storylines, tactical_questions, precision_checks, commentary_directives.\n\n"
            f"INPUT_JSON:\n{json.dumps(all_outputs, default=str)[:60000]}"
        )
        agent = create_deep_agent(
            model=self.model,
            tools=[],
            system_prompt=(
                "You are a senior football broadcast research editor. "
                "Plan carefully, identify weak evidence, and produce precise, source-aware guidance."
            ),
        )
        result = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
        content = self._extract_content(result)
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {"raw": content}
        parsed["enabled"] = True
        parsed["model"] = self.model
        return parsed

    def _extract_content(self, result: Any) -> str:
        if isinstance(result, dict):
            messages = result.get("messages") or []
            if messages:
                last = messages[-1]
                content = getattr(last, "content", None) or (last.get("content") if isinstance(last, dict) else None)
                if content:
                    return str(content)
        return str(result)
