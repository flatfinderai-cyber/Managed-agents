"""
Block 2 — Run per task. Pass the task as a CLI argument.
Example: python run.py "Fix the type error in example/main.py and open a PR"
"""
import argparse
import os
import sys
from pathlib import Path

import anthropic
from pr_agent.setup import (
    ENV_PATH,
    REQUIRED_VARS,
    load_env_file,
    missing_vars,
    provision_managed_agent,
    upsert_env_values,
)

GITHUB_REPO = "https://github.com/flatfinderai-cyber/Managed-agents"
REPO_MOUNT = "/repo"

MANAGED_VARS = (
    "MANAGED_AGENT_VAULT_ID",
    "MANAGED_AGENT_ENV_ID",
    "MANAGED_AGENT_ID",
    "MANAGED_AGENT_VERSION",
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a managed-agent task and stream output until idle.",
    )
    parser.add_argument(
        "task",
        nargs="?",
        help="Task text for the agent.",
    )
    parser.add_argument(
        "--task-file",
        help="Path to a text file containing the task.",
    )
    parser.add_argument(
        "--no-auto-bootstrap",
        action="store_true",
        help="Fail if managed agent IDs are missing instead of creating them.",
    )
    return parser.parse_args(argv)


def read_task_from_file(task_file: str) -> str:
    path = Path(task_file)
    if not path.exists():
        raise FileNotFoundError(f"Task file not found: {path}")

    if not (text := path.read_text(encoding="utf-8").strip()):
        raise ValueError(f"Task file is empty: {path}")
    return text


def resolve_task(args: argparse.Namespace) -> str:
    if args.task_file:
        return read_task_from_file(args.task_file)
    if args.task:
        return args.task.strip()
    raise ValueError("Missing task. Pass a task string or --task-file <path>.")


def ensure_managed_vars(client: anthropic.Anthropic, auto_bootstrap: bool) -> bool:
    missing = missing_vars(MANAGED_VARS)
    if not missing:
        return True

    if not auto_bootstrap:
        return False

    print("Managed IDs missing; auto-bootstrapping resources...")
    managed_values = provision_managed_agent(client)
    upsert_env_values(ENV_PATH, managed_values)
    for key, value in managed_values.items():
        os.environ[key] = value
    print(f"Saved managed IDs to {ENV_PATH}")
    return True


def main() -> int:
    args = parse_args(sys.argv[1:])

    try:
        task = resolve_task(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    load_env_file(ENV_PATH)

    if base_missing := missing_vars(REQUIRED_VARS):
        for var in base_missing:
            print(f"Error: {var} is not set.", file=sys.stderr)
        print("Set required values in .env or your shell and retry.", file=sys.stderr)
        return 1

    client = anthropic.Anthropic()

    if not ensure_managed_vars(client, auto_bootstrap=not args.no_auto_bootstrap):
        for var in missing_vars(MANAGED_VARS):
            print(f"Error: {var} is not set.", file=sys.stderr)
        print(
            "Run python pr_agent/setup.py first or remove --no-auto-bootstrap.",
            file=sys.stderr,
        )
        return 1

    try:
        agent_version = int(os.environ["MANAGED_AGENT_VERSION"])
    except (KeyError, ValueError):
        print(
            "Error: MANAGED_AGENT_VERSION is missing or not an integer.",
            file=sys.stderr,
        )
        return 1

    repo_url = os.environ.get("GITHUB_REPO", GITHUB_REPO)

    session = client.beta.sessions.create(
        agent={
            "type": "agent",
            "id": os.environ["MANAGED_AGENT_ID"],
            "version": agent_version,
        },
        environment_id=os.environ["MANAGED_AGENT_ENV_ID"],
        vault_ids=[os.environ["MANAGED_AGENT_VAULT_ID"]],
        title=task[:80],
        resources=[
            {
                "type": "github_repository",
                "url": repo_url,
                "mount_path": REPO_MOUNT,
                "authorization_token": os.environ["GITHUB_TOKEN"],
            }
        ],
    )
    print(f"session.id = {session.id}")

    # Stream-first: open event stream, then send the task while stream is live.
    with client.beta.sessions.events.stream(session_id=session.id) as stream:
        try:
            client.beta.sessions.events.send(
                session_id=session.id,
                events=[
                    {
                        "type": "user.message",
                        "content": [{"type": "text", "text": task}],
                    }
                ],
            )
        except Exception as exc:
            print(f"Error: failed to send task event: {exc}", file=sys.stderr)
            return 1

        for event in stream:
            if event.type == "agent.message":
                for block in event.content:
                    if block.type == "text":
                        print(block.text, end="", flush=True)
            elif event.type == "agent.tool_use":
                print(f"\n[tool: {event.name}]", flush=True)
            elif event.type == "session.status_idle":
                print("\n[idle - done]")
                break
            elif event.type == "session.status_terminated":
                print("\n[terminated]")
                break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
