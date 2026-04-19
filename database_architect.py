# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
# FlatFinder™ — Confidential & Proprietary Intellectual Property
#
# Agent 1: Database Architect
# Validates the Supabase schema, generates new migrations, checks RLS policies,
# and proposes index improvements — all autonomously via Claude tool-use loop.

from __future__ import annotations

import os
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .base_agent import BaseAgent

# Resolve migrations directory relative to this file
MIGRATIONS_DIR = Path(__file__).parent.parent / "supabase" / "migrations"

# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM = """\
You are the FlatFinder™ Database Architect Agent.
FlatFinder™ is a Canadian anti-gatekeeping rental platform that uses the economist-backed
33-40% income affordability rule instead of the discriminatory 3× rent multiplier.

Your role: autonomously validate, improve, and extend the Supabase (PostgreSQL) schema.

Core responsibilities:
1. Read the existing migration files to understand the current schema.
2. Validate table structures, indexes, and RLS policies.
3. Identify missing indexes, foreign-key gaps, or security holes.
4. Generate new migration SQL when improvements are needed.
5. Save any new migration to the migrations directory using the correct naming convention
   (YYYYMMDD_NNN_description.sql, e.g. 20260413_003_add_rls_policies.sql).

Rules you must enforce:
- Every table that references auth.users MUST have an RLS policy.
- Every foreign key column MUST be indexed.
- Monetary values are ALWAYS stored in cents (INTEGER), never FLOAT.
- All city/country fields use ISO codes or proper nouns consistently.
- The 40% affordability rule is the core engine — never store or suggest 3× multipliers
  as the qualification standard.

Output: structured recommendations + any SQL you generate.
"""

_TOOLS = [
    {
        "name": "list_migrations",
        "description": (
            "List all existing migration files in the supabase/migrations directory, "
            "sorted by filename (which is chronological order)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "read_migration",
        "description": "Read the full SQL content of a specific migration file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Exact filename, e.g. '20260327_001_initial_schema.sql'",
                }
            },
            "required": ["filename"],
        },
    },
    {
        "name": "validate_sql",
        "description": (
            "Validate SQL syntax by checking for common issues: "
            "unmatched parentheses, missing semicolons, reserved-word collisions. "
            "Does NOT execute against the database."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "The SQL to validate.",
                }
            },
            "required": ["sql"],
        },
    },
    {
        "name": "check_rls_coverage",
        "description": (
            "Analyse a migration SQL string and return which tables are missing "
            "Row Level Security (RLS) ENABLE and policy definitions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "Full schema SQL to analyse.",
                }
            },
            "required": ["sql"],
        },
    },
    {
        "name": "save_migration",
        "description": (
            "Save a new SQL migration file. "
            "The filename is auto-generated from the description and next sequence number."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Short snake_case description, e.g. 'add_rls_policies'",
                },
                "sql": {
                    "type": "string",
                    "description": "Full SQL content for the migration.",
                },
            },
            "required": ["description", "sql"],
        },
    },
    {
        "name": "list_tables_in_sql",
        "description": "Extract and list all table names defined in a SQL string.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string"},
            },
            "required": ["sql"],
        },
    },
]


class DatabaseArchitectAgent(BaseAgent):
    """
    Claude-powered database architect that validates and extends the FlatFinder™ schema.
    """

    @property
    def system_prompt(self) -> str:
        return _SYSTEM

    @property
    def tools(self) -> list[dict]:
        return _TOOLS

    # ── Tool implementations ──────────────────────────────────────────────────

    def execute_tool(self, name: str, tool_input: dict) -> Any:
        dispatch = {
            "list_migrations":    self._list_migrations,
            "read_migration":     self._read_migration,
            "validate_sql":       self._validate_sql,
            "check_rls_coverage": self._check_rls_coverage,
            "save_migration":     self._save_migration,
            "list_tables_in_sql": self._list_tables_in_sql,
        }
        fn = dispatch.get(name)
        if not fn:
            raise ValueError(f"Unknown tool: {name}")
        return fn(tool_input)

    def _list_migrations(self, _: dict) -> dict:
        if not MIGRATIONS_DIR.exists():
            return {"files": [], "note": "Migrations directory does not exist yet."}
        files = sorted(f.name for f in MIGRATIONS_DIR.glob("*.sql"))
        return {"files": files, "count": len(files)}

    def _read_migration(self, args: dict) -> dict:
        filename = args["filename"]
        path = MIGRATIONS_DIR / filename
        if not path.exists():
            return {"error": f"File not found: {filename}"}
        return {"filename": filename, "sql": path.read_text()}

    def _validate_sql(self, args: dict) -> dict:
        sql = args["sql"]
        issues = []

        # Unmatched parentheses
        opens = sql.count("(")
        closes = sql.count(")")
        if opens != closes:
            issues.append(f"Unmatched parentheses: {opens} '(' vs {closes} ')'")

        # Statements not ending with semicolon (basic check)
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        if statements and not sql.rstrip().endswith(";"):
            issues.append("SQL does not end with a semicolon.")

        # FLOAT for money
        if re.search(r"\bFLOAT\b|\bDOUBLE\b|\bREAL\b", sql, re.IGNORECASE):
            issues.append(
                "Monetary float type detected — use INTEGER (cents) instead of FLOAT/DOUBLE/REAL."
            )

        # 3x multiplier reference
        if re.search(r"3[xX]|three.times|3_times", sql, re.IGNORECASE):
            issues.append("Possible 3× multiplier reference — FlatFinder™ uses the 40% rule.")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "statement_count": len(statements),
        }

    def _check_rls_coverage(self, args: dict) -> dict:
        sql = args["sql"]
        sql_upper = sql.upper()

        # Tables defined via CREATE TABLE
        table_names = re.findall(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", sql_upper
        )

        # Tables with RLS enabled
        rls_enabled = set(re.findall(r"ALTER\s+TABLE\s+(\w+)\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY", sql_upper))

        # Tables with policies
        policy_tables = set(re.findall(r"CREATE\s+POLICY\s+\S+\s+ON\s+(\w+)", sql_upper))

        missing_rls = [t for t in table_names if t not in rls_enabled]
        missing_policies = [t for t in table_names if t not in policy_tables]

        return {
            "tables_found": table_names,
            "rls_enabled_on": list(rls_enabled),
            "policies_on": list(policy_tables),
            "missing_rls_enable": missing_rls,
            "missing_policies": missing_policies,
            "coverage_ok": len(missing_rls) == 0 and len(missing_policies) == 0,
        }

    def _save_migration(self, args: dict) -> dict:
        description = args["description"].lower().replace(" ", "_").replace("-", "_")
        sql = args["sql"]

        MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)

        # Determine next sequence number
        existing = sorted(MIGRATIONS_DIR.glob("*.sql"))
        next_seq = len(existing) + 1

        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        filename = f"{date_str}_{next_seq:03d}_{description}.sql"
        path = MIGRATIONS_DIR / filename

        if path.exists():
            return {"error": f"File already exists: {filename}"}

        # Prepend IP header
        header = textwrap.dedent(f"""\
            -- © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved. FlatFinder™
            -- Migration: {next_seq:03d} — {description}
            -- Generated by FlatFinder™ Database Architect Agent
            -- Date: {datetime.now(timezone.utc).isoformat()}

        """)
        path.write_text(header + sql)

        return {
            "saved": True,
            "filename": filename,
            "path": str(path),
            "byte_size": path.stat().st_size,
        }

    def _list_tables_in_sql(self, args: dict) -> dict:
        sql = args["sql"]
        tables = re.findall(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"']?(\w+)[\"']?",
            sql,
            re.IGNORECASE,
        )
        return {"tables": list(dict.fromkeys(tables))}  # deduplicated, order-preserving
