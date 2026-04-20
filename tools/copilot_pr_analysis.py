#!/usr/bin/env python3
"""Generate PR analysis using Copilot SDK with Copilot CLI fallback."""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "artifacts" / "copilot-pr-analysis.md"

PROMPT = """You are reviewing the current git working tree and branch diff as a pull request reviewer.
Focus only on high-signal findings:
- functional bugs and regressions
- security issues
- reliability and operational risks
- missing tests for changed behavior

Output strict markdown with these sections in order:
1. Findings
2. Risks
3. Suggested Fixes
4. Summary

Rules:
- Be concrete and concise.
- Include file paths when possible.
- If there are no findings, say exactly: No critical findings.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Copilot PR analysis.")
    parser.add_argument(
        "--mode",
        choices=("auto", "sdk", "cli"),
        default="auto",
        help="Execution mode.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output markdown file path.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="Timeout in seconds for each analysis call.",
    )
    return parser.parse_args()


def write_output(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def run_cli(timeout: float) -> str:
    if not shutil.which("copilot"):
        raise RuntimeError("Copilot CLI binary not found on PATH.")

    # Keep non-interactive permissions scoped to the repository path and GitHub URLs.
    # No shell is used, and command arguments are passed as a sequence.
    allowed_urls = "https://github.com,https://api.github.com"
    completed = subprocess.run(
        [
            "copilot",
            "-p",
            PROMPT,
            "--silent",
            "--no-ask-user",
            "--allow-all-tools",
            f"--add-dir={REPO_ROOT}",
            f"--allow-url={allowed_urls}",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if not (output := completed.stdout.strip()):
        raise RuntimeError("Copilot CLI returned empty output.")
    return output


async def run_sdk(timeout: float) -> str:
    from copilot import CopilotClient
    from copilot.session import PermissionRequestResult

    async def allow_all(_request):
        return PermissionRequestResult(kind="approved")

    client = CopilotClient(auto_start=False)
    await client.start()

    session = None
    try:
        auth_status = await client.get_auth_status()
        if not getattr(auth_status, "isAuthenticated", False):
            raise RuntimeError("Copilot SDK is not authenticated.")

        session = await client.create_session(
            on_permission_request=allow_all,
            working_directory=str(REPO_ROOT),
        )
        await session.send_and_wait(PROMPT, timeout=timeout)

        messages = await session.get_messages()
        assistant_chunks: list[str] = []
        for message in messages:
            if getattr(message, "type", None) == "assistantMessage" or str(
                getattr(message, "type", "")
            ).endswith("ASSISTANT_MESSAGE"):
                text = None
                data = getattr(message, "data", None)
                if data is not None:
                    text = getattr(data, "content", None) or getattr(data, "message", None)
                if text is None:
                    text = getattr(message, "message", None) or getattr(message, "content", None)

                if isinstance(text, str) and text.strip():
                    assistant_chunks.append(text.strip())

        output = "\n\n".join(assistant_chunks).strip()
        if not output:
            raise RuntimeError("Copilot SDK returned no assistant message.")
        return output
    finally:
        if session is not None:
            await session.disconnect()
        await client.stop()


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)

    if args.mode == "cli":
        result = run_cli(args.timeout)
    elif args.mode == "sdk":
        result = asyncio.run(run_sdk(args.timeout))
    else:
        sdk_error: Exception | None = None
        try:
            result = asyncio.run(run_sdk(args.timeout))
        except Exception as exc:  # fallback path
            sdk_error = exc
            result = run_cli(args.timeout)
            result = (
                "<!-- SDK failed; used CLI fallback: "
                + str(sdk_error).replace("--", "-")
                + " -->\n\n"
                + result
            )

    write_output(output_path, result)
    print(f"Wrote PR analysis: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
