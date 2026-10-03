# M1 read: Wren Air & Heat

**For:** Diane Wren · **From:** Lab B team · **Date:** October 2, 2026 · **Data:** snapshot through September 22, 2026

## 1. What is actually driving the phones?

The phone log shows that paid-platform “leads” are not the same thing as real callers. In the latest 30 days, using a real lead as a unique first-time caller with a call of at least 30 seconds, Google Ads produced 100, LSA 68, and Meta 6. Their observed costs per real lead were $89.54, $45.22, and $227.28 respectively. (`scripts/check_m1_memo.py`, §§11–12)

## 2. What would you do in the next 30 days on the current budget?

Keep the budget at $11,400 and reallocate it: $4,000 to LSA, $3,000 to AC Replacement, $2,600 to AC Repair, $1,400 to Brand, and $400 to Meta. Pause Heating Repair, which spent $369.32 with zero qualifying real leads in the latest 30 days. Keep only Meta’s Site Visitors 180d and Video Viewers 50% ad sets as a small attribution test; their combined platform-reported CPL was $8.08, but Meta’s true call attribution is only available at channel level. If recent CPLs held after reallocation, blended real-lead CPL would move from $76.97 to about $63.56; that is a scenario, not a guarantee. (`scripts/check_m1_memo.py`, §§13–15)

## 3. What would you refuse to do, and why?

I would not double the winter budget yet, cut Meta solely because of Aug. 4–10, or open a Katy office from this snapshot. Winter completed jobs averaged 7.03/day versus 15.09/day in summer, but that does not prove more ad spend creates winter demand. Meta still generated four tracked calls during its reported zero-lead week, which points to a tracking problem. Katy cancellations were 77 in 2026, 78 in 2025, and 26 in late 2024, so the data does not show clear growth. (`scripts/check_m1_memo.py`, §§3, 5, 10)

## 4. What number would tell you you were wrong?

Check blended paid cost per real lead after the first 30 full days of the new mix. If it is not below the current $76.97 baseline, the reallocation did not improve efficiency and should be revisited. (`scripts/check_m1_memo.py`, §§12, 15)

---

**Sources:** `scripts/check_m1_memo.py` §§3, 5, 10–15 · `notes/data-map.md` · `data/snapshot-2026-09-23/*.csv` · `README.md`
