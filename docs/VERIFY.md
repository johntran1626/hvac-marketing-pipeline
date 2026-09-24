# Verify

This is the Week 1 framework. It was in the lesson but never got taught live. From now on it's how your work is checked.

## The one line

**The model's confidence is uncorrelated with its correctness.**

Wrong output does not look wrong. It looks like the right output: well formatted, internally consistent, confident. It is often wrong anyway. With Claude Code it's wrong on your disk and in your database, not just in a chat.

Last cycle a submission had a clean one-pager with real-looking numbers. Several weren't in the data files. It looked better than most and was worth less than a blank page, because a blank page doesn't make anyone move a budget.

---

## The six failure modes

Learn all six on sight. Examples are from this stack.

| # | Failure mode | What it looks like here | How to catch it |
|---|---|---|---|
| 1 | **Fabricated specifics** | The memo says "CPL was $38.20 in July." No file, query or script you ran produced that number | Trace every specific to a source you can point at. Not "seems right": point at where it came from |
| 2 | **Plausible-but-wrong reasoning** | "Average CPL" computed as the mean of the daily CPLs. Every step reads fine. CPL is total spend divided by total leads, so the answer is wrong | Check the conclusion independently. Recompute it a different way. Don't re-read the argument: the argument is what fooled you |
| 3 | **Silent scope drift** | You asked for name, phone, vehicle, zip, service, date and slot. The form has six fields. Phone is missing. Nothing says so | Re-read your own brief against the output, line by line, as a checklist |
| 4 | **Confident summary of something unread** | "The CSV has columns for date, spend and leads." It guessed them from the filename. The header row says something else | Ask for a direct quote with a location: "Quote the header row" or "quote the sentence and give the line number" |
| 5 | **Generic-instead-of-specific** | The booking form offers Basic / Premium / Deluxe instead of the services in the data. The seed script inserts "Acme HVAC" | The contextual coherence check: pick three specifics and ask "could this have been written without opening the source?" If all three could, nothing was read |
| 6 | **Unverified "works"** | Claude says the RLS policy blocks bad zips. Nobody tried inserting one | Reading is not running. Name your tier of evidence (below). Then run it |

Fabricated specifics is the one that costs the most. Everything downstream of an invented number is worthless, and it looks fine.

Tell for silent scope drift: you catch yourself thinking "that was easier than I expected."

---

## Tiers of evidence

| Tier | Evidence | Trust |
|---|---|---|
| 1 | I ran it and watched the result | Verified |
| 2 | I watched a recording of it running | Strong |
| 3 | I read it carefully and it looks right | **Unverified** |
| 4 | It told me it works | **Nothing** |

For claims that aren't code: **1** = I checked it myself · **2** = I saw evidence of it · **3** = it reads correct, unverified · **4** = the model asserted it, nothing more.

Tier 3 is where most people stop and believe they're at tier 1. "Reads correct" is not "verified working." Say which tier you're on, out loud, every time: in your log, in your PR, in the Q&A.

What tier 1 looks like on this stack:

| Claim | Tier 1 means |
|---|---|
| "The zip gate works" | You inserted an out-of-area zip as `anon` and watched it fail ([STACK.md](STACK.md)) |
| "The page reads from Supabase" | You changed the row and watched the live page change |
| "The backfill is complete" | You counted rows per source and date range in Supabase and compared them to the source |
| "The owner's name is <name>" | You opened the page that says so. The URL is in your log |
| "The job runs nightly" | You opened the Actions tab and read a run's log |

---

## The verification log

The log is how someone else can act on your work without redoing it. Same format as Week 1:

| Claim | Source | Tier | Verdict |
|---|---|---|---|
| Vercel Hobby functions stop at 300 s | vercel.com/docs/functions/configuring-functions/duration, opened Sep 26 | 1: I opened the page | correct |
| "The insert policy on `leads` blocks out-of-area zips" | SQL Editor, `set local role anon`, inserted zip 99999: the insert succeeded | 1: I ran it | **wrong: corrected.** Policy was `with check (true)`. Fixed in PR #14, re-ran, insert rejected |
| `/health` reads a row on the live URL | Claude: "deployed and verified" | 4: it told me | **unverified: marked.** Haven't opened the live URL yet |
| Supabase free projects pause after exactly 7 days | Claude said "exactly 7 days". The pausing docs say "about 1 week of low activity" | 1: I opened the page | **wrong: corrected** to "about a week" |

**Verdicts:** `correct` · `wrong: corrected` · `wrong: removed` · `unverified: marked`. If you removed or corrected something, the row stays and shows what you did.

**Sources have locations.** A file plus column or row. A query you could paste. A URL plus the date you opened it. A command plus its output. "The data" and "research" are not sources.

Template: [templates/verification-log.md](templates/verification-log.md)

### The rules

1. **Every specific gets a row.** Numbers, names, dates, quotes, filenames, URLs.
2. **Anything you couldn't verify stays in, marked.** An unverified claim labelled unverified is honest and useful. The same claim unlabelled is a fabrication risk.
3. **The log is the deliverable, not an afterthought.** If it's built at the end from memory, it's fiction. Build it as you go, in a second window.
4. **A log with zero wrong or unverified claims is a warning sign, not an A.** It usually means the checking was too shallow. Aim to catch the model being wrong.

### What a faked log looks like

Hamza reads for these:
- Every tier is 1.
- No verdict is anything but `correct`.
- Sources have no locations or dates.
- The log's claims don't match the specifics actually in the work.

Two of those and the log reads as reconstructed. A messy log that caught a fabricated number, kept the row and explains how it got through beats a clean log every time.

---

## Logs in a group

- **Each member keeps their own log:** `logs/<name>.md`, e.g. `logs/sam.md`. One file per person, so you never edit the same file at the same time.
- **Log your share.** The claims you wrote, the code you built, the things you checked. Split the memo's claims by section or by issue, so every claim has an owner.
- **Every specific in the memo has a row in someone's log.** Before you submit, one person walks the memo line by line against the logs. Any specific without a row gets a row or gets cut.
- **Code claims go in the log too.** "The zip gate rejects 99999 as anon" is a claim. So is "the backfill resumes after a 429."
- **Project C:** every claim about a business ties to a URL.
- **Every PR says how it was verified,** with the tier ([templates/PULL_REQUEST_TEMPLATE.md](templates/PULL_REQUEST_TEMPLATE.md)). The reviewer checks that claim, not just the code.
- **Update your log every milestone.** `MILESTONES.md` checks it per person.

The log takes about 20% longer the first time. After that it's free, because you stop re-checking things you already checked.
