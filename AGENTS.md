# Repository Guidelines

## Project Structure & Module Organization
`flatfinder` is a small monorepo managed with npm workspaces and Turbo.
- `apps/web/`: Next.js 14 frontend (`app/`, `components/`, `lib/`, `public/`).
- `backend/`: FastAPI service (`main.py`, `routes/`, `services/`, `templates/`, `static/`).
- `packages/`: shared Python/TS modules (`affordability`, `compliance`, `scraper`, `ip-header`).
- `supabase/migrations/`: ordered SQL migrations (`YYYYMMDD_NNN_description.sql`).
- `agents/`: orchestration and agent runtime scripts.

## Build, Test, and Development Commands
Run commands from repo root unless noted.
- `bash start.sh`: starts backend (`:8000`) and frontend (`:3000`) together.
- `npm run dev`: Turbo dev pipeline for workspace apps/packages.
- `npm run build`: builds all configured workspaces.
- `npm run test`: runs Turbo test pipeline.
- `cd apps/web && npm run lint`: Next.js ESLint checks.
- `cd apps/web && npm run type-check`: strict TypeScript checks.
- `cd packages/affordability && python -m pytest test_engine.py -v`
- `cd packages/compliance && python -m pytest test_scorer.py -v`

## Listing search (Pattern A)
- `POST /api/listings/search/assist` — body `{ "message": "..." }`; Perplexity returns validated filters + `query_params` for `GET /api/listings/search`.
- `GET /api/listings/search` — unchanged; `max_rent` is **whole monthly rent** (backend converts to cents).

## Search Blitz (Pattern B)
- `POST /api/search/order/{order_id}/fulfill` — **internal only**; header `X-Internal-Key` must match `INTERNAL_API_KEY`. Loads the order, matches listings from the DB (no in-request scrape), calls Perplexity once for `deliverable_report`, sets `status` to `complete` or `failed`.
- Apply migration `supabase/migrations/20260418_009_search_blitz_deliverable.sql` so `deliverable_report`, `matched_listing_ids`, and `fulfillment_error` exist on `search_blitz_orders`.

## Benny copilot (Pattern C)
- On the search page, **Benny** can push the renter’s last chat line into listing assist via `BennyChat`’s `onApplyToListingSearch` callback (same Perplexity assist as Pattern A).

## Coding Style & Naming Conventions
- Python: PEP 8, 4-space indentation, `snake_case` for functions/files, explicit type hints where practical.
- TypeScript/React: strict mode enabled, `PascalCase` components, `camelCase` variables, route folders follow Next.js App Router conventions.
- Keep API route modules focused by domain (for example `backend/routes/listings.py`, `backend/routes/agents.py`).
- Name migrations with sortable timestamps and a short action-focused suffix.

## Testing Guidelines
- Primary framework: `pytest` for Python packages; CI currently executes affordability and compliance suites.
- Add tests alongside each package as `test_*.py` (example: `packages/scraper/test_vertical_stack.py`).
- For frontend changes, run `npm run build` and `npm run lint` before opening a PR.

## Commit & Pull Request Guidelines
- Follow existing commit style: Conventional Commits (`feat: ...`, `fix: ...`, `chore: ...`).
- Keep each commit scoped to one logical change (API, UI, migration, or package logic).
- PRs should include:
  - concise problem/solution summary,
  - linked issue/task,
  - test evidence (commands + results),
  - screenshots for UI updates,
  - migration notes for any `supabase/migrations` changes.

## Security & Configuration Tips
- Never commit secrets; use `.env.local` (see `.env.example`).
- Validate Supabase keys and `NEXT_PUBLIC_API_URL` locally before running scrape or verification flows.
