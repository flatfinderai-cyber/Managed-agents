---
name: pr-analysis
description: "Use when reviewing pull requests, checking changed files, identifying risks, or generating concise PR findings from current git changes."
---

# PR Analysis Skill

## Goal
Produce a high-signal pull-request review focused on defects, risk, and missing tests.

## Required Output
Return markdown with exactly these sections:
1. Findings
2. Risks
3. Suggested Fixes
4. Summary

## Rules
- Prioritize correctness, security, reliability, and regression risk.
- Cite changed file paths when possible.
- Keep findings concrete and actionable.
- If there are no critical issues, write: `No critical findings.`

## Procedure
1. Inspect current branch changes and file diffs.
2. Identify behavioral deltas and potential breakpoints.
3. Call out untested changed behavior.
4. Produce final report in required section order.
