#!/usr/bin/env python3
# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
# FlatFinder™ — Confidential & Proprietary Intellectual Property
#
# CLI entry point for the FlatFinder™ agent system.
#
# Usage:
#   python -m agents.run                          # full pipeline (Toronto, $72k)
#   python -m agents.run --agent db               # database architect only
#   python -m agents.run --agent affordability    # affordability only
#   python -m agents.run --agent scraper          # scraper only
#   python -m agents.run --city Vancouver --income 85000
#   python -m agents.run --agent affordability --task "Is $2,800/mo affordable on $78k?"
#   python -m agents.run --save results.json      # save output to file

import argparse
import os
import sys
from pathlib import Path

# Ensure the flatfinder package root is on sys.path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from agents.orchestrator import FlatFinderOrchestrator


def _check_api_key() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit(
            "\n  ERROR: ANTHROPIC_API_KEY is not set.\n"
            "  Export it first:\n\n"
            "    export ANTHROPIC_API_KEY=sk-ant-...\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="flatfinder-agents",
        description="FlatFinder™ AI Agent System — Anthropic Python SDK",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m agents.run
  python -m agents.run --agent affordability --income 68000
  python -m agents.run --agent scraper --city Edinburgh
  python -m agents.run --city Vancouver --income 90000 --save results.json
  python -m agents.run --agent affordability --task "Is $3,100/mo affordable on $85,000/yr?"
        """,
    )

    parser.add_argument(
        "--agent",
        choices=["db", "affordability", "scraper", "all"],
        default="all",
        help="Which agent to run (default: all three in pipeline).",
    )
    parser.add_argument(
        "--city",
        default="Toronto",
        choices=["Toronto", "Vancouver", "Edinburgh", "Paris"],
        help="City for the scraper agent (default: Toronto).",
    )
    parser.add_argument(
        "--source",
        default="kijiji",
        choices=["kijiji", "craigslist", "gumtree", "leboncoin"],
        help="Scraper source (default: kijiji).",
    )
    parser.add_argument(
        "--income",
        type=float,
        default=72000,
        help="Annual income in CAD for affordability checks (default: 72000).",
    )
    parser.add_argument(
        "--task",
        type=str,
        default=None,
        help="Override the default task description for the chosen agent.",
    )
    parser.add_argument(
        "--save",
        type=str,
        default=None,
        metavar="FILE",
        help="Save pipeline results to a JSON file.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress verbose tool-call logging.",
    )

    args = parser.parse_args()
    _check_api_key()

    orch = FlatFinderOrchestrator(verbose=not args.quiet)

    # ── Single agent mode ──────────────────────────────────────────────────────
    if args.agent == "db":
        result = orch.run_database_architect(task=args.task)
        print("\n" + "─" * 60)
        print(result.text)

    elif args.agent == "affordability":
        result = orch.run_affordability(task=args.task, annual_income=args.income)
        print("\n" + "─" * 60)
        print(result.text)

    elif args.agent == "scraper":
        result = orch.run_scraper(
            task=args.task, city=args.city, source=args.source
        )
        print("\n" + "─" * 60)
        print(result.text)

    # ── Full pipeline ──────────────────────────────────────────────────────────
    else:
        pipeline = orch.run_pipeline(
            city=args.city,
            annual_income=args.income,
            scraper_source=args.source,
        )

        print("\n" + "═" * 60)
        if pipeline.db_result:
            print("\n── DATABASE ARCHITECT OUTPUT ──")
            print(pipeline.db_result.text)

        if pipeline.affordability_result:
            print("\n── AFFORDABILITY AGENT OUTPUT ──")
            print(pipeline.affordability_result.text)

        if pipeline.scraper_result:
            print("\n── SCRAPER AGENT OUTPUT ──")
            print(pipeline.scraper_result.text)

        if args.save:
            FlatFinderOrchestrator.save_results(pipeline, args.save)


if __name__ == "__main__":
    main()
