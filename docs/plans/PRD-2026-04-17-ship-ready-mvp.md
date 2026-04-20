# Ship-Ready MVP — FlatFinder™ PRD

> © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.  
> FlatFinder™: Housing Revolutionised™ | Confidential & Proprietary

| Field | Value |
|-------|--------|
| **PRD ID** | `PRD-2026-04-17` |
| **Date** | 2026-04-17 |
| **Owner** | Lila Alexandra Olufemi Inglis Abegunrin |
| **Status** | Ready for Dev |

---

## 1. Overview

This PRD defines the **minimum shippable slice** of FlatFinder™ that proves the business: verified renters and landlords can use **Supabase-backed auth**, **tenant and landlord verification APIs**, **matching and VMC** flows, **Benny** (Perplexity-powered housing guide), **compliance surfacing** (Wall of Shame, listings), and **repeatable deploy** (Vercel + secrets + CI). It is not a hobby scope; it is the **startup execution bar** for the next funding or launch checkpoint.

---

## 2. Problem

Rental markets rely on **gatekeeping** (e.g. illegal 3× income rules) and **opaque agent behaviour**. Renters lose money and dignity; bad actors repeat harm. FlatFinder™ must **ship** a credible product: real auth, real data paths, real AI assist, and production-grade configuration — not a demo that breaks when env or sessions change.

---

## 3. Goal

**Success** means: a paying or pilot-ready operator can run `bash start.sh`, complete **sign-in → tenant or landlord path → match/VMC smoke**, and deploy the web app to **Vercel** with **documented env vars**, **green CI**, and **no placeholder service keys** in production.

---

## 4. Scope

### In Scope

| Area | Deliverable |
|------|-------------|
| **Secrets** | `flatfinder/.env.local` complete: `NEXT_PUBLIC_SUPABASE_*`, `SUPABASE_SERVICE_KEY`, `SUPABASE_JWT_SECRET`, `PERPLEXITY_API_KEY` (Benny), `INTERNAL_API_KEY` (internal routes), optional `ANTHROPIC_API_KEY` (orchestrator only). |
| **Supabase SSR** | `@supabase/ssr` clients (`utils/supabase/server`, `client`, middleware `updateSession`) used for **new** session-aware UI; legacy `lib/supabase` remains for anon reads until migrated. |
| **Auth UX** | Sign-in / sign-up (or magic link if chosen) so **JWT** reaches FastAPI on protected routes. |
| **API parity** | Tenant, landlord, match, VMC routes tested with **Bearer** token; Benny uses **Perplexity** (`/api/benny/*`). |
| **Deploy** | Vercel project linked; preview + production env vars; `flatfinder.rentals` or primary domain pointed. |
| **CI** | `pytest` (packages) + `npm run build` + `type-check` green on `main`. |

### Out of Scope (this PRD)

- Mobile native apps  
- Full payment / Search Blitz billing automation  
- Qdrant vector search production hardening (unless already blocking launch)  
- Multi-region Supabase beyond current project  

---

## 5. User Stories

| As a… | I want to… | So that… |
|--------|------------|----------|
| Renter | Sign in and complete tenant verification | My identity tier is stored and matching can run under policy |
| Landlord | Sign in and list with verified profile path | Listings and matches respect compliance rules |
| Operator (you) | Run `start.sh` and deploy one command path | Time is spent on product, not debugging env |
| Investor / pilot partner | See a stable URL and working flows | They can evaluate the business, not a prototype |

---

## 6. Functional Requirements

| # | Requirement | Priority |
|---|-------------|----------|
| F1 | Supabase **service_role** and **JWT secret** set in env; FastAPI starts without 503 on auth routes | Must Have |
| F2 | Next.js loads **root** `.env.local` (already via `next.config`); publishable **or** anon key documented | Must Have |
| F3 | **Middleware** refreshes session (`updateSession` + `getUser`) on matched routes | Must Have |
| F4 | **Benny** returns 200 from `/api/benny/chat/complete` when `PERPLEXITY_API_KEY` set | Must Have |
| F5 | At least one **E2E smoke** (Playwright): health or affordability or dev pipeline (gated env) | Should Have |
| F6 | **Landlord** pages stop using mock user IDs; use session + Bearer | Should Have |
| F7 | **Vertical stack** decisions recorded for every listing ingress path | Should Have |

---

## 7. Technical Specification

### Stack Context

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14 (App Router), TailwindCSS |
| Backend | FastAPI (Python 3.11) |
| Database & Auth | Supabase (Postgres, RLS, Auth) |
| Benny | Perplexity API (`backend/routes/benny.py`) |
| Orchestrator / agents | Anthropic SDK (`agents/`, optional for MVP demo) |
| Deploy | Vercel (frontend); Cloudflare DNS as per `CLAUDE.md` |

### Files to Create / Modify (tracking)

| File / area | Action |
|-------------|--------|
| `apps/web/utils/supabase/*` | Done — SSR clients + root `middleware.ts` |
| `apps/web` auth pages | Sign-in / sign-up + Nav (if not present) |
| `apps/web/app/landlord/*` | Replace mock user with `createClient` session + `authFetch` |
| `backend/.env` | Copy from root `start.sh` pattern — already copies `.env.local` |
| `supabase/migrations/` | Only if schema gap for production RLS |

### API Endpoints (reference)

| Method | Path | Notes |
|--------|------|--------|
| POST | `/api/benny/chat`, `/api/benny/chat/complete` | Perplexity |
| GET/POST | `/api/tenant/*`, `/api/landlord/*`, `/api/match/*`, `/api/vmc/*` | Bearer JWT |
| POST | `/api/orchestrator/pipeline` | `X-Internal-Key` |

### Environment Variables Required

```env
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
SUPABASE_JWT_SECRET=
PERPLEXITY_API_KEY=
NEXT_PUBLIC_API_URL=
INTERNAL_API_KEY=
# Optional: ANTHROPIC_API_KEY (orchestrator / agents only)
```

---

## 8. Acceptance Criteria

- [ ] `bash start.sh` starts backend `:8000` and frontend `:3000` without manual env hacks  
- [ ] `SUPABASE_SERVICE_KEY` is real in `.env.local` (not `FILL_IN_…`) for non-local demo  
- [ ] `SUPABASE_JWT_SECRET` matches **JWT Secret** in Supabase (single string; not Key ID / JWKS block)  
- [ ] User can sign in in the web app and call at least one protected API with **200** (not 401/503)  
- [ ] Benny completes a message via `/api/benny/chat/complete`  
- [ ] `npm run build` passes in `apps/web` on CI branch  
- [ ] `pytest` passes for `packages/affordability`, `compliance`, `scraper` as in CI  
- [ ] All new files carry the IP header per template  

---

## 9. IP Header (Required on Every New File)

```
// © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
// FlatFinder™: Housing Revolutionised™ | Confidential & Proprietary
```

(Python: `#` prefix; SQL: `--` prefix.)

---

## 10. Execution Order (recommended)

| Step | Task |
|------|------|
| 1 | Finalise `.env.local` (service role, JWT secret, Perplexity) |
| 2 | Wire **landlord** + any remaining **mock user** pages to session |
| 3 | Run **CI-equivalent** locally: `make test`, `cd apps/web && npm run build` |
| 4 | Vercel env + first production deploy |
| 5 | One **Playwright** smoke (optional but recommended before external demos) |

---

## 11. Notes

- **Owner IP:** All output remains owned by Lila Alexandra Olufemi Inglis Abegunrin; this PRD is for **execution**, not dilution of scope.  
- **British English** in user-facing copy.  
- **Benny** is **not** Claude in production path; orchestrator may still use Anthropic — do not conflate env vars in docs.  
- If a single “definition of done” is needed for a board or investor: **F1–F4 + first deploy** = minimum credible ship.

---

_End of PRD_
