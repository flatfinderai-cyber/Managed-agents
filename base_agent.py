# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
# FlatFinder™ — Confidential & Proprietary Intellectual Property
#
# Base agent — supports Anthropic direct OR OpenRouter (cheaper for campaigns).
#
# Set AGENT_BACKEND=openrouter in .env.local to route through OpenRouter.
# OpenRouter is ~10x cheaper for high-volume use (free-tier campaign, etc.)

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any

# ── Backend detection ──────────────────────────────────────────────────────────
BACKEND = os.environ.get("AGENT_BACKEND", "anthropic").lower()

# Model routing
ANTHROPIC_MODEL   = "claude-sonnet-4-6"
OPENROUTER_MODEL  = "z-ai/glm-5.1"                   # GLM-5.1 via OpenRouter

MAX_TOKENS     = 4096
MAX_ITERATIONS = 20


class AgentResult:
    def __init__(self, text: str, tool_calls: list[dict], iterations: int):
        self.text        = text
        self.tool_calls  = tool_calls
        self.iterations  = iterations

    def __repr__(self) -> str:
        return (
            f"AgentResult(iterations={self.iterations}, "
            f"tools_used={[t['name'] for t in self.tool_calls]}, "
            f"text_length={len(self.text)})"
        )


class BaseAgent(ABC):

    def __init__(self, api_key: str | None = None, verbose: bool = True):
        self.verbose = verbose
        self._backend = BACKEND

        if self._backend == "openrouter":
            from openai import OpenAI
            self.client = OpenAI(
                api_key=os.environ.get("OPENROUTER_API_KEY") or api_key,
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": "https://flatfinder.ca",
                    "X-Title": "FlatFinder",
                },
            )
        else:
            import anthropic
            self.client = anthropic.Anthropic(
                api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
            )

    @property
    @abstractmethod
    def system_prompt(self) -> str: ...

    @property
    @abstractmethod
    def tools(self) -> list[dict]: ...

    @abstractmethod
    def execute_tool(self, name: str, tool_input: dict) -> Any: ...

    # ── Main loop ──────────────────────────────────────────────────────────────

    def run(self, user_message: str) -> AgentResult:
        if self.verbose:
            print(f"\n[{self.__class__.__name__}] backend={self._backend}")
            print(f"  Task: {user_message[:120]}…\n")

        if self._backend == "openrouter":
            return self._run_openai_compat(user_message)
        else:
            return self._run_anthropic(user_message)

    # ── Anthropic native ───────────────────────────────────────────────────────

    def _run_anthropic(self, user_message: str) -> AgentResult:
        import anthropic
        messages     = [{"role": "user", "content": user_message}]
        tool_history = []

        for iteration in range(1, MAX_ITERATIONS + 1):
            response = self.client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=MAX_TOKENS,
                system=self.system_prompt,
                tools=self.tools,
                messages=messages,
            )

            if self.verbose:
                print(f"  [iter {iteration}] stop_reason={response.stop_reason}")

            if response.stop_reason == "end_turn":
                text = "".join(b.text for b in response.content if hasattr(b, "text"))
                return AgentResult(text=text, tool_calls=tool_history, iterations=iteration)

            if response.stop_reason == "tool_use":
                tool_blocks  = [b for b in response.content if b.type == "tool_use"]
                tool_results = []

                for b in tool_blocks:
                    if self.verbose:
                        print(f"  → {b.name}({json.dumps(b.input)[:80]}…)")
                    try:
                        raw    = self.execute_tool(b.name, b.input)
                        result = json.dumps(raw, default=str) if not isinstance(raw, str) else raw
                        err    = False
                    except Exception as exc:
                        result = json.dumps({"error": str(exc)})
                        err    = True

                    tool_history.append({"name": b.name, "input": b.input, "output": result, "is_error": err})
                    entry = {"type": "tool_result", "tool_use_id": b.id, "content": result}
                    if err:
                        entry["is_error"] = True
                    tool_results.append(entry)

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user",      "content": tool_results})

        return AgentResult(text="[Max iterations reached]", tool_calls=tool_history, iterations=MAX_ITERATIONS)

    # ── OpenRouter / OpenAI-compat ─────────────────────────────────────────────

    def _run_openai_compat(self, user_message: str) -> AgentResult:
        import json

        # Convert Anthropic tool schema → OpenAI function schema
        oai_tools = [
            {
                "type": "function",
                "function": {
                    "name":        t["name"],
                    "description": t["description"],
                    "parameters":  t["input_schema"],
                },
            }
            for t in self.tools
        ]

        messages     = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user",   "content": user_message},
        ]
        tool_history = []

        for iteration in range(1, MAX_ITERATIONS + 1):
            response = self.client.chat.completions.create(
                model=OPENROUTER_MODEL,
                max_tokens=MAX_TOKENS,
                tools=oai_tools,
                messages=messages,
            )

            msg         = response.choices[0].message
            stop_reason = response.choices[0].finish_reason

            if self.verbose:
                print(f"  [iter {iteration}] finish_reason={stop_reason}")

            if stop_reason in ("stop", "end_turn") or not msg.tool_calls:
                text = msg.content or ""
                return AgentResult(text=text, tool_calls=tool_history, iterations=iteration)

            # Process tool calls
            messages.append({"role": "assistant", "content": msg.content, "tool_calls": msg.tool_calls})

            for tc in msg.tool_calls:
                name  = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {}

                if self.verbose:
                    print(f"  → {name}({json.dumps(args)[:80]}…)")

                try:
                    raw    = self.execute_tool(name, args)
                    result = json.dumps(raw, default=str) if not isinstance(raw, str) else raw
                    err    = False
                except Exception as exc:
                    result = json.dumps({"error": str(exc)})
                    err    = True

                tool_history.append({"name": name, "input": args, "output": result, "is_error": err})
                messages.append({
                    "role":         "tool",
                    "tool_call_id": tc.id,
                    "content":      result,
                })

        return AgentResult(text="[Max iterations reached]", tool_calls=tool_history, iterations=MAX_ITERATIONS)
