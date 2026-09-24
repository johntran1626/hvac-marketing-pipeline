# The stack

One default stack for all three projects. Use it unless you have a reason you can write down in an issue.

Every limit and price on this page was checked on Sep 24, 2026 against the linked official page. They change. Hamza re-checks before M2. If you rely on a number, open the link yourself.

## The default

| Layer | Default | Why |
|---|---|---|
| App | **Next.js** (App Router) + **TypeScript** + **Tailwind**, in `web/` | Pages and server code in one project. Deploys on Vercel with no config |
| Database | **Supabase** Postgres + **RLS** | Real Postgres. Access rules live in the database, not only in your UI |
| Hosting | **Vercel Hobby** | Free. Deploys every merge to `main` |
| Code, tasks, reviews | **GitHub**: private fork, Issues, pull requests | One place for code, the task board and review |
| Scheduled or long jobs | See **the job ladder** below | Project B needs a worker. Most apps don't |
| LLM (Project C) | `claude -p` on your own Pro plan, run locally | No API keys, no spend. See [CLAUDE-CODE.md](CLAUDE-CODE.md) |

**The app lives in `web/`.** From the root of your fork:

```bash
npx create-next-app@latest web
```

Docs, data, notes and logs stay outside `web/`. On Vercel, set the project's **Root Directory** to `web`.

---

## Vercel Hobby: the rules that bite

| Rule | What it means for you | Source |
|---|---|---|
| Non-commercial, personal use only | Fine for the Lab. Not for client work | https://vercel.com/docs/limits/fair-use-guidelines |
| Can't deploy a private repo owned by a GitHub **organization** | Fork into a personal account, not an org | https://vercel.com/docs/git |
| Commits deploy only if the **commit author is the Hobby owner**. Otherwise the deploy is blocked | Teammates open PRs. The owner merges with **Create a merge commit**. That merge commit is the owner's, so it deploys. Squash and rebase merges can keep the teammate as author, and then the deploy is blocked | https://vercel.com/kb/guide/why-aren-t-commits-triggering-deployments-on-vercel |
| Collaboration on projects is **Pro only** ($20 per developer seat, 14-day trial) | Only the owner sees the Vercel project and its env vars. Teammates test locally with `npm run dev` | https://vercel.com/docs/accounts |
| Functions: **300 s** default and max | Anything longer gets killed. Project B's full backfill takes longer. That's the point | https://vercel.com/docs/functions/configuring-functions/duration |
| Cron: **once per day**, timing precision **±59 min** | Not for anything that must run on time or more often | https://vercel.com/docs/cron-jobs/usage-and-pricing |
| Root Directory = `web` | Set it at import. Otherwise the build can't find the app | Project Settings in the Vercel dashboard |

The full owner and PR workflow is in [WORKFLOW.md](WORKFLOW.md).

---

## Supabase Free: the rules that bite

| Rule | What it means for you | Source |
|---|---|---|
| **2 active free projects per person**, counted across every org where you're **Owner or Admin**. Paused projects don't count | The owner creates the group project. Teammates join as **Developer**, so it doesn't use their slots | https://supabase.com/docs/guides/platform/billing-on-supabase |
| **Pauses after about 1 week** of low activity. Restorable | A paused project breaks your live URL. Open your live URL the day you submit | https://supabase.com/docs/guides/platform/free-project-pausing |
| 500 MB database, 5 GB egress, 1 GB storage, **no backups** | Keep every schema change as a `.sql` file in git so you can rebuild | https://supabase.com/pricing |
| Unlimited team members on Free. Roles: Owner, Admin, Developer. **Invites expire after 24 h** | Accept the invite the day it arrives | https://supabase.com/docs/guides/platform/access-control |
| CLI: `npx supabase <cmd>` (per project: `npm i supabase --save-dev`), or Scoop on Windows. `npm i -g supabase` is **not supported**. The local stack needs Docker | Don't fight a global install | https://supabase.com/docs/guides/local-development/cli/getting-started |

### RLS enabled is not RLS enforcing

This one shipped in past submissions. The table had RLS switched on. The policy let everything through.

**Anti-example. Don't write this:**

```sql
alter table public.leads enable row level security;

create policy "anyone can insert"
  on public.leads for insert
  to anon
  with check (true);  -- every row passes. RLS is on, and it checks nothing.
```

The dashboard shows RLS enabled. A green badge. Anyone with your publishable key can insert anything.

**A policy that enforces something:**

```sql
create policy "insert only in-area leads"
  on public.leads for insert
  to anon
  with check (
    zip in (select zip from public.service_zips)
  );
```

Now an insert with a zip that isn't in `service_zips` fails. Two things to know:
- The subquery runs as `anon` too. If `service_zips` has RLS on, `anon` needs a read policy on it, or every insert fails.
- A policy only binds roles RLS applies to. The secret key skips RLS. A **constraint** (`check` or a foreign key) binds everyone. For a rule that must always hold, a constraint is often the better tool.

**Test it the way an attacker would.** The SQL Editor runs as an admin role that skips RLS, so a plain insert there proves nothing. Switch role inside a transaction:

```sql
begin;
set local role anon;
insert into public.leads (name, zip) values ('Test', '99999');  -- must fail
rollback;
```

You want `new row violates row-level security policy for table "leads"`. If the insert succeeds, your policy doesn't enforce what you think. The `rollback` throws the test row away either way.

"Claude says the policy blocks bad zips" proves nothing. Running this and watching it fail does.

### Keys and secrets

| Key | Where it may go | Where it must never go |
|---|---|---|
| **Publishable** (`sb_publishable_...`) or legacy `anon` | Browser code, `NEXT_PUBLIC_` env vars | No limit: it's public by design. That's why RLS has to protect your data |
| **Secret** (`sb_secret_...`) or legacy `service_role` | Server code only: Vercel env vars **without** `NEXT_PUBLIC_`, GitHub Actions secrets, your own `.env.local` | Browser code, any `NEXT_PUBLIC_` variable, git, chat, issues, screenshots, your Loom |

Supabase says the secret key must never go "in a browser, a shipped application, or source control." The legacy `anon` and `service_role` keys are being deprecated by the end of 2026. Source: https://supabase.com/docs/guides/api/api-keys

- **Anything named `NEXT_PUBLIC_...` ends up in the browser.** Never give the secret key that prefix.
- **`.env*` goes in `.gitignore`**, at the repo root and in `web/`. Check before your first commit.
- **Leaked a secret?** Tell your group and Hamza the same day. The owner replaces the key in Supabase (**Settings → API Keys**) and updates every place it's used. Deleting the file doesn't help: git history keeps it.

---

## The job ladder

Most work runs inside a request and finishes in seconds. Some doesn't: a backfill of tens of thousands of rows, a nightly sync, a crawl. Climb only as high as the job needs. Cheapest first:

| Rung | Limits | Cost |
|---|---|---|
| 1. **Vercel function** | ≤ 300 s per invocation on Hobby | Free |
| 2. **Vercel Cron** → a function | Once a day on Hobby, ±59 min. Function ≤ 300 s | Free |
| 3. **Supabase pg_cron** (+ an Edge Function via `pg_net`) | Up to 8 concurrent jobs, each should run under 10 min. Edge Functions: 150 s wall clock, 2 s CPU per request | Free |
| 4. **GitHub Actions** scheduled workflow | Job ≤ 6 h. Schedule at most every 5 min, in UTC. Start can be delayed or dropped at busy times. Runs from the default branch | Private repos: 2,000 min/month free on GitHub Free |
| 5. **Railway** | Cron at most every 5 min. The service must exit when done | $5 trial credit, then Hobby $5/mo |
| 6. **A VPS** (e.g. DigitalOcean) | Anything. You maintain it | $4 to $6/mo |

Also on the market:
- **Render:** cron from $1/mo, no free workers.
- **Heroku:** the Scheduler isn't guaranteed to run, and the company moved to sustaining engineering in Feb 2026. $5+/mo. **Don't start new work there.**

### Which rung?

| My job takes | It runs | It needs | Use |
|---|---|---|---|
| Under 300 s | When a user clicks or a webhook fires | | Vercel function |
| Under 300 s | Once a day, an hour late is fine | | Vercel Cron |
| Under 150 s, or pure SQL under 10 min | Every few minutes to hourly | To sit next to the database | Supabase pg_cron (+ Edge Function) |
| Minutes to 6 h | On a schedule, every 5 min or less often, a late start is fine | Secrets, free minutes, logs you can read | **GitHub Actions** |
| Minutes to 6 h | On a schedule | A hosted service outside GitHub | Railway |
| More than 6 h, or it never stops | Always | A machine you control | VPS |

**Project B:** a correct backfill takes several minutes. That's more than a Vercel function's 300 s. Your worker is a GitHub Actions workflow in your fork.

### GitHub Actions: what bites

- **Disabled in forks** until someone opens the fork's **Actions** tab and enables them. Do it on day one ([WORKFLOW.md](WORKFLOW.md)).
- **Secrets are per repo.** Set them in the fork: **Settings → Secrets and variables → Actions**. The upstream starter repo's secrets don't carry over.
- **Schedules are UTC** and can start late, or be dropped, at busy times. Avoid minute `:00`. Pick an odd minute.
- **Schedules run from the default branch.** A workflow on your feature branch doesn't run on schedule.
- **Private repos use free minutes:** 2,000 a month on GitHub Free, on the fork owner's account. A 10-minute nightly job uses about 300 a month.
- **Jobs get cancelled.** Save your cursor in the database and make every write an idempotent upsert, so a rerun picks up where it stopped and never double-counts.

Sources: https://docs.github.com/en/actions/reference/limits · https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows

The shape of a scheduled workflow (`.github/workflows/nightly.yml`). Adjust paths and names to your repo:

```yaml
name: nightly-sync
on:
  schedule:
    - cron: "17 11 * * *"   # 11:17 UTC every day. Not :00.
  workflow_dispatch: {}     # adds a "Run workflow" button on the Actions tab
jobs:
  sync:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
      - run: npm ci
        working-directory: worker
      - run: node sync.mjs
        working-directory: worker
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SECRET_KEY: ${{ secrets.SUPABASE_SECRET_KEY }}
          LAB_API_KEY: ${{ secrets.LAB_API_KEY }}
```

Run it by hand with the **Run workflow** button before you trust the schedule. Then read the log. "It's scheduled" is not "it ran."

---

## Links

| What | Link |
|---|---|
| Vercel limits and fair use | https://vercel.com/docs/limits/fair-use-guidelines |
| Vercel function duration | https://vercel.com/docs/functions/configuring-functions/duration |
| Vercel cron pricing and limits | https://vercel.com/docs/cron-jobs/usage-and-pricing |
| Why commits don't deploy on Hobby | https://vercel.com/kb/guide/why-aren-t-commits-triggering-deployments-on-vercel |
| Supabase billing and project limits | https://supabase.com/docs/guides/platform/billing-on-supabase |
| Supabase pausing | https://supabase.com/docs/guides/platform/free-project-pausing |
| Supabase API keys | https://supabase.com/docs/guides/api/api-keys |
| Supabase Cron | https://supabase.com/docs/guides/cron |
| Supabase Edge Function limits | https://supabase.com/docs/guides/functions/limits |
| GitHub Actions limits | https://docs.github.com/en/actions/reference/limits |
| Railway cron | https://docs.railway.com/reference/cron-jobs |
| Render cron | https://render.com/docs/cronjobs |
| DigitalOcean droplet pricing | https://www.digitalocean.com/pricing/droplets |
| Heroku Scheduler | https://devcenter.heroku.com/articles/scheduler |
