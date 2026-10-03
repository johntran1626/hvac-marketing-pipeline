# Issue #4 independent memo review template

**Purpose:** contingency evidence for Issue #4. This file does **not** claim the independent review is complete. Another teammate who is not the primary memo author must run the verification, inspect the sources, and record their own conclusion.

## Reviewer steps

1. Start from the final M1 branch/commit being submitted.
2. Run:
   `python3 scripts/verify_issue4_memo.py`
3. Confirm the final line says:
   `ALL ISSUE #4 AUTOMATED CHECKS PASSED`
4. Read `memo/read.md` yourself.
5. Spot-check the cited raw CSVs and `notes/data-map.md` rather than relying only on the memo author's verification script.
6. Record the reviewer name, date, commit reviewed, and any exceptions below.

## Issue #4 checklist

- [ ] Reproduced the important calculations used in the memo.
- [ ] Verified each number against a cited/checkable source.
- [ ] Verified factual claims against the snapshot data.
- [ ] Confirmed all four required questions appear word-for-word as headings.
- [ ] Confirmed the four questions appear in the required order.
- [ ] Confirmed the memo is 400 words or fewer.
- [ ] Confirmed recommendations are specific and supported by evidence.
- [ ] Confirmed Question 4 identifies a specific metric.
- [ ] Confirmed Question 4 identifies a specific threshold.
- [ ] Confirmed Question 4 states when the metric will be checked.
- [ ] Confirmed all cited repository sources exist and are checkable.
- [ ] Confirmed the final file is `memo/read.md`.

## Automated evidence currently reproduced

The independent-source harness recomputes directly from the snapshot CSVs; it does not import `scripts/check_m1_memo.py`.

Expected passing results include:

- exact four headings in order
- memo word count: **390**
- latest 30 days: Google Ads **100 / $89.54**, LSA **68 / $45.22**, Meta **6 / $227.28**, GBP **126** qualifying real callers
- Brand summer: **$8.44** reported conversion CPL vs **$72.59** per qualifying real lead
- budget allocation totals **$11,400**
- current blended real-lead CPL **$76.97** vs modeled scenario **$63.56**
- Meta Aug 4–10: **$291.15 spend, 135 clicks, 0 reported leads, 4 tracked calls**
- Katy canceled jobs: **26 late-2024, 78 in 2025, 77 in 2026**
- Question 4 explicitly contains the metric, **$76.97** threshold, and **30 full days** timeframe

## Reviewer record

**Reviewer:**
**Date:**
**Commit reviewed:**
**Automated verifier result:**
**Manual source spot-checks performed:**
**Exceptions or concerns:**

## Suggested Issue #4 evidence comment after the reviewer actually completes the checks

> Independently reviewed `memo/read.md` against the snapshot data and cited repo sources. I ran `python3 scripts/verify_issue4_memo.py`, which recomputed the important memo figures directly from the raw CSVs and passed all automated checks. I also manually reviewed the memo structure, recommendations, source references, and Question 4 metric/threshold/timeframe. The memo is 390 words, contains all four required questions in order, and the checked calculations and factual claims match the source evidence. No blocking issues found.

Do not post the suggested comment until the named reviewer has actually performed the steps above.
