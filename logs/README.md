# Logs

Two kinds of file live here. The full rules are in [docs/VERIFY.md](../docs/VERIFY.md).

## `logs/<name>.md`: your verification log

- **One file per person**, your first name in lowercase: `logs/sam.md`. Copy `_template.md` to start. Your log lands through your own PR.
- **The Week 1 format:** `| Claim | Source | Tier | Verdict |`. Every specific in your share of the work gets a row: numbers, names, dates, campaign names, channels, quotes, filenames, and claims that something works.
- **Tiers:** 1 = I ran it / checked it myself · 2 = I watched a recording / saw evidence of it · 3 = it reads correct, unverified · 4 = the model asserted it, nothing more.
- **Verdicts:** `correct` · `wrong: corrected` · `wrong: removed` · `unverified: marked`. If you removed or corrected something, the row stays and shows what you did.
- **Sources have locations.** A file plus the query or script that produced the number. An API call plus its parameters. A table plus the SQL. A workflow run plus its log. "The data" is not a source.
- **Build it as you go, in a second window.** A log rebuilt from memory is fiction, and it shows: every tier is 1, nothing was ever wrong, the sources have no locations.
- **Every specific in the memo has a row in someone's log.** Before you submit, one person walks the memo line by line against the logs.
- **Keep logging after M1.** In M2 and M3 the claims are about your pipeline. "Running the backfill twice doesn't change the row count" is a claim. Its source is the two runs and the counts you saw.

A log where nothing was ever wrong is a warning sign, not an A.

Worth adding at the end of each milestone: which of the six failure modes you caught ([docs/VERIFY.md](../docs/VERIFY.md)), the quote, how you caught it, and one specific change to a prompt or a `CLAUDE.md` rule that would have prevented it. "Be more careful" is worth nothing.

## `logs/hours.md`: everyone's hours

One file for the group, one section per person. Log hours the day you work them, rounded to the half hour, and add rows only at the bottom of your own section. Honest numbers.
