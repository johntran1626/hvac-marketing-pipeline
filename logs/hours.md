# Hours

Save as `logs/hours.md`. One file for the group, one section per person.

- Log hours the day you work them. Not on Sunday night from memory.
- Round to the nearest half hour.
- Count everything: reading, meetings, building, reviewing, being stuck.
- Add rows only at the bottom of **your own section**, so two people never edit the same lines.
- Honest numbers only. Zero is an honest number. A week of identical round numbers isn't.

## John Tran

| Date | Hours | What I did | Issue / PR |
|---|---|---|---|
| 2026-09-30 | 1.0 | Forked the starter repo, set up M1 milestone and issues, assigned owners, created the Supabase project | #9 |
| 2026-10-01 | 2.0 | Read the brief, invited the team to Supabase, mapped Diane's questions to the snapshot data, opened and merged my first PR | #1, #9, #13 |
| 2026-10-02 | 4.0 | Backfilled all LSA leads into Supabase, deployed the site to Vercel, filled the dashboard table so /health works, reviewed Kelsey's schema and memo PRs, team planning | #8, #11, #19, #20, #21 |
| 2026-10-03 | 1.0 | Reviewed and approved Kelsey's PRs, merged Kelsey's hours PR, cleaned up PR descriptions and checkboxes, created and organized the M2 issues | #15, #16, #17, #19, #24, #25–#37 |
| 2026-10-04 | 1.5 | Ran the final M1 audit, reviewed and merged Ruslan's PR, removed the empty hours section, sent the M1 submission to Hamza | #12, #39, #40 |
| 2026-10-08 | 2.0 | Built the M2 worker: saved sync progress, LSA and Google Ads loaders, daily Actions workflow; ran the migrations, backfilled Google Ads, tested kill and resume, added Actions secrets, opened PRs | #25, #26, #28, #32, #43–#46 |
| 2026-10-10 | 2.0 | Set up the GitHub Actions secrets and ran the worker locally; agreed the unique-lead rule and lead summing with the team; planned the fact table rebuild and dashboard | #32, #31, #33 |
| 2026-10-11 | 3.0 | Reviewed and merged the M2 PRs (#43 to #51); built the Meta loader, fact table rebuild and dashboard (#52); ran the migrations, set the Vercel env vars, ran the sync workflow; moved the daily sync to the evening (#53); audited M2 and closed the finished issues | #27, #30, #32, #33, #34, #35 |

## Kelsey Mellor

| Date | Hours | What I did | Issue / PR |
|---|---|---|---|
| 2026-09-28 | 0.5 | Project setup and planning, repo review, M1 task planning | M1 setup |
| 2026-09-29 | 0.5 | Team coordination and project workflow planning | M1 planning |
| 2026-09-30 | 3.5 | Team planning, repo and issue setup, Supabase setup, web scaffold, and raw schema work | #5, #9, #10 |
| 2026-10-01 | 3.0 | Raw and normalized schema work, PR review fixes, Git branch cleanup, and Supabase/project coordination | #5, #6, #9, #10 |
| 2026-10-02 | 4.0 | Committed the M1 decision memo and check script, implemented the Supabase schema migration, and added the Supabase-backed /health verification route | #3, #7, #10 |
| 2026-10-03 | 0.5 | Attended team check-in meeting and reviewed/approved assigned PRs | #21, #22 |
| 2026-10-03 | 0.5 | Project risk audit, unmerged contingency backups for #2/#4, final #10 verification/closeout, and project documentation. Backup work was risk mitigation only and does not claim ownership of teammates' assigned deliverables. | #2, #4, #10 |

## Ruslan Buhayenko

| Date | Hours | What I did | Issue / PR |
|---|---|---|---|
| 2026-10-02 | 2.0 | Read the brief, milestones, data map and team notes; caught up on the issues and open PRs to plan my part; team check-in meeting | #2, #4 |
| 2026-10-03 | 2.0 | Verified M1 evidence: ran the LSA backfill, fact table and constraint queries in Supabase, tested the live site and /health in a private window, set up the repo and Python locally, ran both memo scripts plus a Heating Repair month-by-month check, reviewed and approved 5 PRs | #4, #13, #19, #20, #21, #22 |
| 2026-10-03 | 1.0 | Wrote the memo verification note and Heating Repair script, posted evidence on #2 and #4, logged hours, opened this PR | #2, #4 |
| 2026-10-06 | 0.5 | Read Hamza's M1 feedback, the M2 team notes and the M2 GitHub issues; planned my M2 work and order (#36 first, then #37, #29, #34) | #36, #37, #29, #34 |
| 2026-10-09 | 1.5 | Read docs/API.md and John's worker scaffold (#43); wrote API client tests (paging, 429, 503, give-up, windows, cursor, no secrets in logs); found and fixed a crash on non-integer Retry-After in worker/http.py | #36 |
| 2026-10-09 | 1.0 | Reviewed and approved #43: ran worker tests, checked sync_state, fact grain and RLS in Supabase | #43 |
| 2026-10-10 | 2.0 | Reviewed and approved #46 (ran the worker locally, checked sync_state); built the calls loader and tests, loaded 30,554 calls, ran the evidence queries (match the snapshot exactly) | #46, #37 |
