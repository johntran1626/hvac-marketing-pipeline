# CLAUDE.md

<!-- Starter for your fork's root CLAUDE.md. Fill in the <placeholders>, delete what you don't use, delete this comment. Keep it under 60 lines: every line loads every session and costs usage. When Claude gets something wrong twice, add a rule. -->

## Project
- <Project name>. <One sentence: who the client is and what they need.>
- Brief: `README.md`. Handbook: `docs/`.
- The app lives in `web/`: Next.js App Router, TypeScript, Tailwind. Database: Supabase Postgres with RLS. Hosting: Vercel, deployed from `main` by <owner>.
- Current milestone: <M1 / M2 / M3>, due <date>. Done means: <the checklist items you're working on>.

## Data
- Data files: <list them, e.g. `data/<file>.csv`>. Never edit them.
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

## Commands
- Dev server: `cd web && npm run dev`, then http://localhost:3000
- Build (run before every PR): `cd web && npm run build`
- Lint: `cd web && npm run lint`
- Tests / evals: `<command>`
- Worker (Project B): `<command>`
- Headless extraction (Project C): `<command>`

## Git
- Work on a branch named `<issue-number>-<short-name>`. Never commit to `main`.
- Don't commit or push unless I ask.
