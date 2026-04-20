"""Provision Managed Agents resources and persist generated IDs to .env."""
import os
import sys
from pathlib import Path

from typing import Iterable

import anthropic

SYSTEM_PROMPT = """\
You are a senior Python engineer working on the Managed-agents project — \
a dual-API flat-finder system that uses Perplexity for listing search \
and Anthropic Managed Agents for automated code work.

Your workspace is the GitHub repository mounted at /repo (branch: main).

When given a task:
1. Understand the request fully before touching any file.
2. Read relevant files first (glob, grep, read).
3. Make the smallest correct change — no refactors, no new abstractions \
beyond what is asked.
4. Never hardcode secrets; read them from environment variables only.
5. Commit your changes to a new branch named agent/<short-description>.
6. Open a pull request against main with a clear one-line title and a \
body explaining what changed and why.
7. Report the PR URL when done.

Constraints:
- Never commit .env files or any file containing real credentials.
- Never push directly to main.
- If the task is ambiguous, do the minimal safe interpretation and note \
your assumptions in the PR body.\
"""

GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"
REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"
REQUIRED_VARS = ("ANTHROPIC_API_KEY", "GITHUB_TOKEN")
MANAGED_VARS = (
    "MANAGED_AGENT_VAULT_ID",
    "MANAGED_AGENT_ENV_ID",
    "MANAGED_AGENT_ID",
    "MANAGED_AGENT_VERSION",
)


def load_env_file(env_path: Path) -> None:
    """Load simple KEY=VALUE pairs from .env without overriding set vars."""
    if not env_path.exists():
        return

    preexisting_env = set(os.environ)

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key.isidentifier() or key in preexisting_env:
            continue

        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


def missing_vars(names: Iterable[str]) -> list[str]:
    return [name for name in names if not os.getenv(name)]


def upsert_env_values(env_path: Path, values: dict[str, str]) -> None:
    """Insert or update values in .env while preserving unrelated lines."""
    existing_lines: list[str] = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()

    remaining = dict(values)
    updated: list[str] = []

    for line in existing_lines:
        if "=" not in line or line.lstrip().startswith("#"):
            updated.append(line)
            continue

        key, _ = line.split("=", 1)
        key = key.strip()
        if key in remaining:
            updated.append(f"{key}={remaining.pop(key)}")
        else:
            updated.append(line)

    updated.extend(f"{key}={value}" for key, value in remaining.items())

    env_path.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")


def provision_managed_agent(client: anthropic.Anthropic) -> dict[str, str]:
    """Create vault, environment, and agent, and return IDs for .env."""
    print("Creating vault...")
    try:
        vault = client.beta.vaults.create(display_name="pr-agent-vault")
    except Exception as exc:
        raise RuntimeError(f"Failed to create managed-agent vault: {exc}") from exc

    print("Adding GitHub credential to vault...")
    try:
        client.beta.vaults.credentials.create(
            vault_id=vault.id,
            display_name="GitHub PAT",
            auth={
                "type": "mcp_oauth",
                "mcp_server_url": GITHUB_MCP_URL,
                "access_token": os.environ["GITHUB_TOKEN"],
                # PATs without expiry; update if your PAT has a real expiry date.
                "expires_at": "2099-12-31T00:00:00Z",
            },
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to store GitHub credential in vault: {exc}") from exc

    print("Creating environment...")
    try:
        env = client.beta.environments.create(
            name="pr-agent-env",
            config={
                "type": "cloud",
                "networking": {"type": "unrestricted"},
            },
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to create managed-agent environment: {exc}") from exc

    print("Creating agent...")
    try:
        agent = client.beta.agents.create(
            name="pr-agent",
            model="claude-opus-4-7",
            system=SYSTEM_PROMPT,
            mcp_servers=[
                {"type": "url", "name": "github", "url": GITHUB_MCP_URL},
            ],
            tools=[
                {"type": "agent_toolset_20260401"},
                {"type": "mcp_toolset", "mcp_server_name": "github"},
            ],
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to create managed agent: {exc}") from exc

    return {
        "MANAGED_AGENT_VAULT_ID": vault.id,
        "MANAGED_AGENT_ENV_ID": env.id,
        "MANAGED_AGENT_ID": agent.id,
        "MANAGED_AGENT_VERSION": str(agent.version),
    }


def main() -> int:
    load_env_file(ENV_PATH)

    if missing := missing_vars(REQUIRED_VARS):
        for var in missing:
            print(f"Error: {var} is not set.", file=sys.stderr)
        print("Set required values in .env or your shell and retry.", file=sys.stderr)
        return 1

    if not missing_vars(MANAGED_VARS):
        print("Managed agent values already present; skipping reprovision.")
        return 0

    try:
        client = anthropic.Anthropic()
        managed_values = provision_managed_agent(client)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: Anthropic setup failed: {exc}", file=sys.stderr)
        return 1
    upsert_env_values(ENV_PATH, managed_values)

    print("\n--- Managed agent values ---")
    for key, value in managed_values.items():
        print(f"{key}={value}")
    print(f"\nUpdated {ENV_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
