# Project B: HVAC ads pipeline

**Zapp AI Agent Lab, Fall 2026.** A group project. It runs from Sep 24 to Oct 22.

New here? Start with [docs/SETUP.md](docs/SETUP.md).

| | What | Due |
|---|---|---|
| **Setup** | Everyone's accounts and tools, and your own calculator URL deployed. See [docs/SETUP.md](docs/SETUP.md) | Sun Sep 27, 11:59pm CT |
| **M1** | **The read.** A memo to Diane, the owner, with a source for every number. The app skeleton deployed and a first pull from the API | **Sun Oct 4, 11:59pm CT** |
| **M2** | **The build.** The worker, the schema and the dashboard | **Sun Oct 11, 11:59pm CT** |
| **M3** | **Prove it.** The data-quality eval, an anomaly alert, a Loom, and the peer review | **Sun Oct 18, 11:59pm CT** |
| **Live Q&A** | Your group answers my questions about your project, live | Thu Oct 22, 6pm CT |

Budget **4 to 6 hours per person per week**. If a week is running past six, stop and send what you have. Knowing when something is done enough is part of what's being read.

---

## Read this part first

**Wren Air & Heat is made up. The shape of its data is real.** The API in this project behaves like the real ones: Google Ads, Meta, Google Local Services Ads, a call-tracking tool and a field-service CRM, each in its own format. The numbers are generated, and they were built so that a model gets things wrong on them.

**It's graded, and the grade is for learning, not for ranking.** Nobody's spot depends on it. What it's actually for: the whole program is about whether you can be trusted with a model's output. A model will give you a confident answer on this data in thirty seconds. Whether that answer survives checking is the interesting part.

**How your group is graded:**
- **Each milestone is a pass/fail checklist.** The checklists are in [docs/MILESTONES.md](docs/MILESTONES.md). You should never be guessing at what's being checked. Miss a box and you get one fix-up round, explained there.
- **Each of you is accountable, every milestone.** Every member owns at least 2 GitHub Issues, authors at least 1 merged PR, and adds their hours to `logs/hours.md`. The group's work is checked once. Your part of it is checked too.
- **Peer review at M3.** You'll privately rate each teammate on contribution, reliability and quality (1 to 5), with one sentence each. Only I read it. It feeds Build-phase placement, not grades.

**Use whatever AI you want.** Claude, Cursor, whatever. I do. I'd think less of you if you didn't. What's graded is whether *you* reviewed, verified, and adjusted what came out. That is the Week 1 lesson, applied.

**I will ask about this on Thursdays, and live on Oct 22.** Not a gotcha. Be ready to explain any choice your group made, including the ones you made because Claude suggested them. "Claude suggested it and we checked X" is a great answer. "We don't know" is a fine one. A made-up answer is the only bad one. Each of you answers for the part you built.

**You do not need to be right. You need to be legible.** I'd rather read a wrong answer I can follow than a right one I can't.

---

## The company

Wren Air & Heat is a heating and air conditioning company in northwest Houston, founded in 2011 and run by its owner, Diane Wren. One office, six trucks, two people on the phones, a service area of about 25 zip codes.

What they sell:
- diagnostic visits, $89
- repairs, $150 to $1,800
- maintenance visits, $129, or $189 a year for a plan that covers two visits
- new system installs, $7,000 to $16,000

Paid channels: Google Search ads, Meta ads (Facebook and Instagram), and Google Local Services Ads (the "Google Guaranteed" ads, paid per lead). Calls come in on tracking numbers. Every job lives in the company's CRM.

### Diane's note

> We're Wren Air & Heat: six trucks, two people on the phones, northwest Houston since 2011. We spend about $11,400 a month on ads between Google, the Google Guaranteed ads, and Meta. Google says we got 1,209 leads this summer at $24.00 each, and our Brand campaign is the best of them at $8.44 a lead. The new agency took over on May 1 and this was our best summer: 1,388 completed jobs June to August, up from 1,245 last summer. Meta is the opposite. For a whole week in August (Aug 4 to Aug 10) it showed zero leads while we still paid $291.15. Winter is what scares me. Last November to February we averaged 7.0 completed jobs a day, against 15.1 a day this summer, and we have turned away 77 jobs from Katy this year because it's outside our area. So my plan: double the ad budget November through February to keep the trucks busy, cut Meta, and look at a small office in Katy. Tell me if that's right. I just don't want trucks sitting in the yard all winter.
>
> Diane Wren, owner

### Your group's four questions

1. **What is actually driving the phones?**
2. **What would you do in the next 30 days on the current budget?** Be specific per campaign: which campaigns and ad sets keep running, which stop, where the money moves, and what you expect the cost per real lead to do.
3. **What would you refuse to do, and why?**
4. **What number would tell you you were wrong?** Name the metric, the threshold, and when you would check it.

---

## The data

Two ways in. Same data.

### 1. The snapshot (for M1)

`data/snapshot-2026-09-23/` holds five CSVs: what the API returned on Sep 23, 2026, for everything through Sep 22, flattened into files. Use it for the read. No pipeline needed.

| File | One row per |
|---|---|
| `google_ads_insights.csv` | day and Google Ads ad group |
| `meta_insights.csv` | day and Meta ad set |
| `lsa_leads.csv` | Local Services lead |
| `calls.csv` | tracked phone call |
| `crm_jobs.csv` | job in the CRM, in its latest state as of the snapshot |

What each column means is in [data/snapshot-2026-09-23/README.md](data/snapshot-2026-09-23/README.md) and [docs/API.md](docs/API.md). Read them before you trust a column name.

### 2. The live API (for M2 and M3)

The same sources, served by a mock API that behaves like the real ones: a key, date limits, paging, rate limits, the occasional failed request, and a new day of data every day.

- **Base URL:** `https://ads-api.lab.zappstudios.us`
- **Docs:** [docs/API.md](docs/API.md). The same page is at the base URL in a browser.
- **Your key:** I send it to your group privately. Your whole group shares it. Treat it like a password. **Never commit it.** It lives in three places only: a GitHub Actions secret in your fork (for the worker), your own git-ignored `.env.local` for local runs, and a Vercel environment variable without the `NEXT_PUBLIC_` prefix if your app ever needs it. Not in code, not in chat, not in a screenshot, not in a Loom.

---

## M1: the read (Sun Oct 4)

### The memo

**One memo per group, to Diane. 400 words max. Hard cap.** Count the words with a tool. Start from `memo/_template.md` and commit it to `main` as `memo/read.md`.

Answer Diane's four questions, the ones right under her note, in her order. Use them word for word as the memo's four headings.

The fourth one is not a throwaway. **Name the metric, name the threshold, name when you'd check it.** "Monitor CPL closely" earns nothing.

Use the snapshot. Charts optional. If you make one, it should carry the argument, not decorate it.

Write it for Diane. She runs an HVAC company, not a data team.

### Every number has a source

Every number or fact in the memo cites where it came from: the file and row (or the query or script that produced it), or a URL. List them in the memo's **Sources** line. If you can't point at where a number came from, cut it.

Every dataset in this lab was built so that a model gets things wrong on it. Find where.

### The skeleton

- `web/` scaffolded, deployed on Vercel, and connected to your Supabase project. A `/health` page that reads one row is the simplest proof.
- A Supabase schema, as SQL committed to the repo: a raw table for each source (rows as the API returns them) and a normalized fact table the dashboard will read. It will change in M2. That's fine.
- One source backfilled by hand from the API into its raw table. A script you run on your laptop is fine for M1. The evidence is a query showing its row count and date range.

---

## M2: the build (Sun Oct 11)

### Why a worker, not a Vercel function

A full backfill today is about 54,000 rows. The API gives you at most 31 days per request and 200 rows per page, and allows 60 requests a minute. That's roughly 300 requests: about five minutes at the rate limit, before a single retry. Our reference backfill took about 5.5 minutes. A Vercel function on the free plan stops at 300 seconds, and Vercel cron runs once a day.

So the pull runs somewhere built for long jobs: a scheduled **GitHub Actions** workflow in your fork. One job can run for up to 6 hours. [docs/STACK.md](docs/STACK.md) has the whole ladder of options, with their limits and prices.

Three things to know about Actions:
- **GitHub disables Actions in forks until you turn them on.** Open the Actions tab in your fork and enable workflows.
- **Secrets are per repo.** Add the API key and your Supabase keys in your fork's settings (Secrets and variables, then Actions).
- **Scheduled runs use UTC and can start late** when GitHub is busy, so don't schedule on the hour. Private repos get 2,000 free minutes a month: a daily job that takes a few minutes fits easily, one that runs every 5 minutes doesn't.

### 1. The worker

- **A resumable backfill.** It pulls everything the API has. Its progress (the cursor, the last finished window) is saved in the database, so if the job dies halfway, the next run picks up where it stopped instead of starting over.
- **Backoff.** On 429 and 503 it waits for `Retry-After`, then tries again, a limited number of times. It never hammers the API.
- **Idempotent upserts.** Running the same pull twice leaves exactly the same rows. No duplicates, ever.
- **A daily scheduled run that re-pulls the last 7 days**, because recent days can still change (see "Numbers that change" in [docs/API.md](docs/API.md)).
- **An incremental CRM sync** with `updated_since`: only the jobs that changed since the last sync.

### 2. The schema

A raw table per source, loaded as the API returns it, plus a normalized fact table that puts the sources side by side. The dashboard reads the fact table. Every schema change is a migration file in git.

### 3. The dashboard

- **True cost per lead, by channel and by month.** Write your definition of a lead on the page.
- **Reported leads vs unique leads**, side by side.
- **Brand vs non-brand.**
- **A data-freshness badge:** when the data last synced, and the last date it covers.

---

## M3: prove it (Loom Sun Oct 18, live Q&A Thu Oct 22)

### The data-quality eval

At least **8 checks**, run against your database with one command, listed under Commands in your `CLAUDE.md`. Each check has a name, says what it tests, and reports pass or fail.

- Include **should-flag cases**: inputs where the right behavior is to raise a flag, not to load or chart the number quietly. At least: a restated day, a duplicate caller, a time-zone boundary, and each data problem your read and pipeline found.
- For every check, show one input where it stays quiet and one where it fires. Constructed bad rows are fine for this. Say which ones you constructed.
- At least one check ties your database back to the source: pick a fixed date range, total the spend for each channel in your database and from the API, and show they match to the cent.

### The anomaly alert

An alert that fires when a channel's numbers stop behaving like themselves. You choose the rule, and you write down why. It goes somewhere a person would see it: an email, a GitHub Issue the workflow opens, or a banner on the dashboard.

Show it firing on a real anomaly in the data, and say whether anything else it fired on was real.

### The Loom

**5 minutes or less.** Show the live app and the worker doing the work, not slides. Show the worker running, and resuming after you cancel it halfway. Walk the dashboard, run the eval, show the alert. Tell me what you'd have done with another two hours. Anyone with the link can view it.

### The live Q&A

Thu Oct 22, 6pm CT. Every member is there, ready to answer for the part they built. I'll ask about choices you made, in the memo and in the code.

### The peer review

I email the form by Fri Oct 16. Each of you submits it by Sun Oct 18, 11:59pm CT. The questions are in [docs/MILESTONES.md](docs/MILESTONES.md).

---

## How to work

- **Fork this repo to your own GitHub account.** One fork per group. The fork owner deploys. Add your teammates and Hamza (`HZapperz`) as collaborators on the fork.
- **Scaffold the app in `web/`:** `npx create-next-app@latest web`. On Vercel, set the project's Root Directory to `web`.
- **Enable Actions in the fork** on day one: open the Actions tab and turn workflows on.
- **Branch, PR, merge.** Vercel's free plan only deploys commits made by the account owner, so everyone opens pull requests and the fork owner merges them with a merge commit (not squash). Details in [docs/WORKFLOW.md](docs/WORKFLOW.md).
- **Work from Issues.** One Issue per task, with an owner and a done-condition. The Issue template asks for both.
- **Leave the starter files alone.** This README, `data/` and `docs/` come from the starter repo. Don't edit them, so pulling my fixes stays clean. Your own notes and commands go in `CLAUDE.md` and in files you create.
- **Keep your access.** Don't leave the starter repo. If your access to it goes away, GitHub deletes your private fork with it.

Read these before you start:

| Doc | What's in it |
|---|---|
| [docs/SETUP.md](docs/SETUP.md) | Accounts and installs. Due Sun Sep 27 |
| [docs/WORKFLOW.md](docs/WORKFLOW.md) | Fork, collaborators, branches, PRs, who merges, Vercel settings, enabling Actions |
| [docs/STACK.md](docs/STACK.md) | Next.js, Supabase and Vercel, their free-plan limits, and where long jobs go |
| [docs/WORKING-WITH-CLAUDE.md](docs/WORKING-WITH-CLAUDE.md) | How to work with Claude: small pieces, one conversation each, check what comes back. Read this first |
| [docs/CLAUDE-CODE.md](docs/CLAUDE-CODE.md) | Driving Claude Code without burning through your usage |
| [docs/MILESTONES.md](docs/MILESTONES.md) | The pass/fail checklists for M1, M2 and M3 |
| [docs/API.md](docs/API.md) | The API: auth, dates, paging, rate limits, every endpoint |

`CLAUDE.md` in this repo is a starter. Edit it as your group learns what Claude needs to be told.

---

## How to submit

By each deadline, the fork owner replies to my email thread for your group. One reply per group, in the format in [docs/MILESTONES.md](docs/MILESTONES.md): your fork URL, your live URL, the path to the memo (M1), and the Loom link (M3).

Everything else lives in the repo: the memo in `memo/`, the hours in `logs/`. I check your fork's `main` branch, your Actions runs and your live URL, so merge before you reply. Before you send it: `HZapperz` is a collaborator on the fork, and the live URL works in a private window.

---

## Questions?

Reply to the email thread. Asking a good question about this brief is not a mark against you, it's most of the job. Nobody is going to hand you a clean spec at this company, and I'm not starting now.

Hamza
