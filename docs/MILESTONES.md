# Milestones

Three milestones, pass/fail. One file for all three projects: the shared boxes first, then your project's boxes.

| When (America/Chicago) | What |
|---|---|
| **Sun Sep 27, 11:59pm** | SETUP, individual: GitHub username + hello URL (see `SETUP.md`) |
| **Sun Oct 4, 11:59pm** | **M1**: the read, deployed `web/`, schema |
| **Sun Oct 11, 11:59pm** | **M2**: the build |
| **Sun Oct 18, 11:59pm** | **M3**: evals + Loom + peer review |
| **Thu Oct 22, 6:00pm** | **M3 live Q&A** |

## What "pass" means

- **Every box is checked, with evidence someone else could check.** Something Hamza can open or run: the live URL, a file path on `main`, a PR, an Actions run, a query and its result, a row in a log.
- A box with no evidence is an unchecked box. "It works on my machine" is not evidence.
- Hamza checks your fork's `main` branch and your live URL. A paused Supabase project means a broken live URL. Open your live URL the day you submit.

## What happens on a miss

- Hamza replies with the boxes that failed and why.
- You get **one fix-up round**: reply with the fixes **within 48 hours** of his note.
- That's the only round. After it, the milestone is recorded as it stands.
- The individual boxes work the same way, per person.

---

## Every member, every milestone

Checked per person. A group can pass while one member misses these. That miss is the member's, not the group's.

- [ ] **You own 2 or more GitHub Issues** in this milestone (you're the assignee), each with a done-condition.
- [ ] **You authored 1 or more merged PRs** in this milestone.
- [ ] **`logs/<name>.md` is updated** for this milestone, in the Week 1 format: `| Claim | Source | Tier | Verdict |`. Rows for your share of the work. See `VERIFY.md`.
- [ ] **`logs/hours.md` has your honest hours** for this milestone.

---

## M1: the read · due Sun Oct 4, 11:59pm CT

### All projects

- [ ] **The read:** a memo of 400 words or fewer, answering your project's question(s) from the data. Template: `templates/memo.md`. Committed to `main`. Its path is in your submission.
- [ ] **Every specific in the read has a row** in at least one member's `logs/<name>.md`.
- [ ] **`web/` is deployed** from the owner's Vercel project (Root Directory `web`) at a live URL, connected to the group's Supabase project.

### Project A: Bayou Detail full-stack

- [ ] The read answers **Ray's four questions**, 400 words or fewer.
- [ ] A **`/health` page** on the live URL reads one row from Supabase.
- [ ] A **schema plan** is committed: tables, columns, and the constraints and RLS policies M2 will need.

### Project B: HVAC ads pipeline

- [ ] The read answers **the owner's four questions**, 400 words or fewer, from the starter snapshot in `data/`.
- [ ] A **Supabase schema**: a **raw table per source** and a **normalized fact table**, as SQL committed to the repo.
- [ ] **One source backfilled by hand** from the API into its raw table. Evidence: a query showing its row count and date range.

### Project C: prospect research agent

- [ ] The read answers **"Which 10 should Zapp call first, and why?"**, 400 words or fewer. **Every claim is tied to a URL** in the logs.
- [ ] The **schema**, as SQL committed to the repo.

---

## M2: the build · due Sun Oct 11, 11:59pm CT

### Project A: Bayou Detail full-stack

- [ ] A **booking flow**: name, phone, vehicle, zip, service, date and slot.
- [ ] The **zip gate is enforced in the database**: a constraint or an RLS `with check`, **not `with check (true)`**. A check that lives only in the browser doesn't count.
- [ ] **Duration-aware slots.**
- [ ] A **concurrency-safe capacity of 2** per slot.
- [ ] A **confirmation that restates the booking.**
- [ ] **Waitlist capture** on rejected zips.
- [ ] An **owner dashboard at `/owner`** that computes the read's key numbers from the CSVs loaded into Supabase.

### Project B: HVAC ads pipeline

- [ ] A **GitHub Actions worker** in the fork with a **resumable backfill**: cursor saved in the database, **backoff on 429 and 503**, **idempotent upserts**.
- [ ] A **daily cron** that re-pulls the last 7 days.
- [ ] An **incremental CRM sync.**
- [ ] The **dashboard**: true CPL by channel and month, reported vs unique leads, brand vs non-brand, and a **freshness badge**.

### Project C: prospect research agent

- [ ] The **full run**: every business in `data/prospects.csv`, results in Supabase.
- [ ] A **UI** with the ranked list, facts with their source URLs, and **conflicts and unknowns visible**.
- [ ] **Email drafts**, each citing 2 or more verified specifics.
- [ ] The LLM step runs **locally** with `claude -p` on your own Pro plan. The deployed app only displays results. No API keys.

---

## M3: evals and the Loom · Loom due Sun Oct 18, 11:59pm CT · live Q&A Thu Oct 22, 6pm CT

### All projects

- [ ] A **Loom, 5 minutes or less.** Show the live app doing the work, not slides. Link in your submission. Anyone with the link can view it.
- [ ] **Every member at the live Q&A** on Thu Oct 22, ready to answer for the part they built.
- [ ] **Every member submits the peer review** (below).

### Project A: Bayou Detail full-stack

- [ ] An **eval of 8 or more cases**, including should-reject: an out-of-area zip, a day Bayou doesn't work, a full slot, a past date, a booking that overflows past closing, a double-submit.
- [ ] A **test that the dashboard reconciles** to the CSV totals.
- [ ] The **Loom shows a rejected zip.**

### Project B: HVAC ads pipeline

- [ ] A **data-quality eval of 8 or more checks**, including should-flag cases for: a restated day, a duplicate caller, a time-zone boundary, and each data problem your read and pipeline found.
- [ ] An **anomaly alert**, shown firing on a real anomaly in the data.

### Project C: prospect research agent

- [ ] An **eval harness on `evals/public.jsonl`**: field accuracy, should-flag traps, label agreement, and a **fabrication check on the emails**.
- [ ] The harness **takes the eval file as an input**. Hamza runs it on a hidden set in the same format, so don't tune to the public 20.

---

## Peer review (M3)

- **Private. Only Hamza reads it.**
- **It feeds Build-phase placement, not grades.**
- Hamza emails the form link by Fri Oct 16. Submit it by Sun Oct 18, 11:59pm CT.

For each teammate:

| Question | Answer |
|---|---|
| **Contribution:** how much of the group's work did they do? | 1 to 5 |
| **Reliability:** did they do what they said, when they said? | 1 to 5 |
| **Quality of work:** did their work hold up when someone checked it? | 1 to 5 |
| **One sentence** about their work | Text |

Rate what you saw: issues, PRs, reviews, logs. Not how much you like them.

---

## How to submit

**Reply to Hamza's email thread by the deadline.** One reply per group. The owner sends it. If the owner can't, anyone in the group can.

```
Group: <name> · Project: <A / B / C> · Milestone: <M1 / M2 / M3>
Fork: https://github.com/<owner>/<fork-name>
Live: https://<your-project>.vercel.app
Read (M1): <path to the memo in the repo>
Loom (M3): <link>
```

Before you send it:
- `HZapperz` is a collaborator on the fork.
- The live URL works in a private window.
- Every member's boxes above are checked, with evidence.
