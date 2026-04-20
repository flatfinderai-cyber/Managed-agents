<!-- FlatFinder™ pull request template — keep it short and linkable. -->

## Summary
<!-- One or two sentences: what does this PR change and why? -->

## Linked issue / task
<!-- e.g. Closes #123 — or a line from TASKS.md -->

## Changes
- [ ] API (`routes/`, `main.py`)
- [ ] Package logic (`packages/`)
- [ ] Frontend (`apps/web/`)
- [ ] Migration (`supabase/migrations/`)
- [ ] Docs / config

## Test evidence
<!-- Commands you ran and their results. Paste output or screenshots. -->

```
# example
cd packages/affordability && python -m pytest test_engine.py -v
```

## Migration notes
<!-- Only if `supabase/migrations/` was touched: migration id, reversibility, data impact. -->

## Screenshots
<!-- UI changes only. Before / after. -->

## Checklist
- [ ] Follows Conventional Commits (`feat:`, `fix:`, `chore:` …)
- [ ] No secrets, `.env`, or real credentials committed
- [ ] British English in user-facing strings
- [ ] Relevant tests pass locally
