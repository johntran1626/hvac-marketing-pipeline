# CLAUDE.md

<!-- Starter for your fork's root CLAUDE.md, pre-filled for project B. Fill in the <placeholders>, delete what you don't use, delete this comment. Keep it under 60 lines: every line loads every session and costs usage. When Claude gets something wrong twice, add a rule. -->

## Project
- HVAC ads pipeline (Lab project B). Wren Air & Heat is a fictional heating and air conditioning company in northwest Houston. The owner, Diane Wren, needs a read on her marketing numbers, and a pipeline and dashboard she can trust.
- Brief: `README.md`. Handbook and checklists: `docs/` (`docs/MILESTONES.md`). API: `docs/API.md`.
- The app lives in `web/`: Next.js App Router, TypeScript, Tailwind. Database: Supabase Postgres with RLS, migrations in `supabase/migrations/`. Hosting: Vercel (Root Directory `web`), deployed from `main` by <owner>.
- The worker lives in `worker/` and runs on GitHub Actions (`.github/workflows/`), on a schedule and by hand.
- Current milestone: <M1 / M2 / M3>, due <date>. Done means: <the checklist items you're working on>.

## Data
- Data files: `data/snapshot-2026-09-23/` (five CSVs and a README). Never edit them.
- Live data: the Lab API at `https://ads-api.lab.zappstudios.us`. Read `docs/API.md` before you assume what a field means.
- **Read the data files. Do not recall them.** Open a file before you say anything about it. Quote the header row before you use a column.
- For totals, counts and rates, write a script and run it. No mental arithmetic.

## Rules
1. If a number isn't in a file I gave you, say unknown. Never estimate.
2. Use the exact names from the data files. Never invent placeholder names, services, prices, zips or businesses. If it isn't in the files, say so.
3. Never say something works unless you ran it. Say what you ran and paste the output. If you didn't run it, say "not run".
4. Never write an RLS policy with `with check (true)`. Never put the secret key in browser code or a `NEXT_PUBLIC_` variable. Never commit `.env` files.

Also:
- Do only what the task asks. If you skipped part of it, say which part.
- Ask before you add a dependency, delete a file, or change the database schema.
- Never print or commit `LAB_API_KEY` or `SUPABASE_SECRET_KEY`. Don't echo env vars in workflow logs.
- The worker is safe to re-run: upsert on each source's natural key. Save progress in the database, so a killed run resumes instead of restarting.
- On 429 or 503: wait for `Retry-After`, retry with a growing wait, cap the retries, log it.
- Keep raw rows as the API returned them. Transform them into the fact table. Never "fix" raw data in place.
- Every number on the dashboard comes from a query we can point to. No numbers copied from the snapshot or the memo.

## Commands
- Dev server: `cd web && npm run dev`, then http://localhost:3000
- Build (run before every PR): `cd web && npm run build`
- Lint: `cd web && npm run lint`
- Worker, locally: `python3 -m worker.run` (or `python3 -m worker.run lsa`). Tests: `python3 -m unittest discover -s worker/tests -t .`
- Data-quality eval: `<command>`
- Anomaly alert: `python3 -m worker.alerts` (`--since 2024-10-01` replays history). Rule and evidence: `notes/anomaly-alert.md`
- Supabase CLI: `npx supabase <command>` (never `npm i -g supabase`)
- App env vars (`web/.env.local`): `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
- Worker env vars (GitHub Actions secrets, or `.env.local` locally): `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `LAB_API_KEY`

## Git
- Work on a branch named `<issue-number>-<short-name>`. Never commit to `main`.
- Don't commit or push unless I ask.
- Don't edit `README.md`, `data/` or `docs/`. They come from the starter repo.
