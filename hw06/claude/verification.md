# Part D – Verifying Claude's `Top 10 Client Share`

## 1. Did it run as written? What did the test query return?
**Yes.** Claude's first draft ran in DAX query view with no errors. Its test query returned:

| Slice | Share |
|---|---|
| Total (no filter) | 0.0616 (6.16%) |
| 2020 / 2021 / 2022 / 2023 / 2024 | 0.0704 / 0.0638 / 0.0553 / 0.0604 / 0.0616 |

All values are between 0 and 1, and the 2024 value equals the total, as it should (Dec 2024 is the last snapshot either way).

One problem came up when I typed in the **fixed** version: I first named the variable `LastDate`. That gave a syntax error because it clashes with the DAX function `LASTDATE`. I renamed it `LastSnap` (in this measure and in `AUM-Weighted Alpha`).

## 2. Which reconciliation rows prove it?
In `reports/measure_reconciliation.csv`, every row matches (172 of 172). The key rows for this measure:

| measure | slice | powerbi_value | pandas_value | match |
|---|---|---|---|---|
| Top 10 Client Share | Total | 0.061589267466 | 0.061589267466 | True |
| Top 10 Client Share | 2024 HNW | 0.031396747492 | 0.031396747492 | True |
| Top 10 Client Share | 2024 Retail | 0.018348218311 | 0.018348218311 | True |
| Top 10 Client Share | 2024 UHNW | 0.081264267522 | 0.081264267522 | True |
| Top 10 Client Share | 2023 Advisor 1 | 0.764410331919 | 0.764410331919 | True |
| Top 10 Client Share | 2023 Advisor 5 | 0.808151938117 | 0.808151938117 | True |
| Top 10 Client Share | 2023 Advisor 14 | 0.673058999258 | 0.673058999258 | True |
| Top 10 Client Share | 2023 Advisor 2 (control) | 0.726347361965 | 0.726347361965 | True |

After the Claude Code review, I added **all 25 advisors in 2023** to the script (and Top 10 for every year). All of them match the fixed measure. When I planted Claude's draft value for advisor 1 (0.8739), the script flagged it. So the reconciliation would now catch this bug if it came back.

The pandas side (`top10_share` in the script) never reads Power BI. It takes the rows at the **last snapshot date in the slice**, picks the 10 largest client balances, and divides by the total balance on that date.

## 3. Edge cases I checked
1. **Grand total** – 0.0616 in both tools (row above).
2. **The 2024 tier table** – HNW, Retail and UHNW all match (rows above). This also checks "within the current filter": each tier ranks its own top 10.
3. **Each year 2020–2024**, including **2022** – the draft and the final give the same value every year.
4. **By advisor, in 2023** (the one that broke the draft) – an advisor's book is small, so one departed client can land in the top 10:

| Advisor (2023) | Draft | Final | pandas | Departed client counted by the draft |
|---|---|---|---|---|
| 1 | 0.8739 | 0.7644 | 0.7644 | 1052 – left after Sep 2023, $32.6M |
| 5 | 0.8962 | 0.8082 | 0.8082 | 1268 – left after Mar 2023, $40.8M |
| 10 | 0.7753 | 0.7695 | 0.7695 | 1265 – left after Oct 2023, $5.9M |
| 14 | 0.7844 | 0.6731 | 0.6731 | 418 – left after Mar 2023, $35.4M |
| 17 | 0.7456 | 0.7403 | 0.7403 | 338 – left after May 2023, $7.4M |
| 18 | 0.7908 | 0.7883 | 0.7883 | 953 – left after Jul 2023, $5.1M |
| 21 | 0.7960 | 0.7397 | 0.7397 | 648 – left after Jul 2023, $34.2M |
| 2 (control) | 0.7263 | 0.7263 | 0.7263 | none |

## 4. What I changed and why
I changed the draft. It reused `[Ending AUM]` inside `TOPN` and `SUMX`. Because of context transition, each client got **their own** last snapshot. A client who left in March 2023 was still ranked by their March balance. The denominator only counts clients still there in December. So the numerator had money the denominator didn't, and the share was too high.

The fix finds the filter's last snapshot once (`VAR LastSnap`) and wraps the whole `TOPN`/`SUMX` in `CALCULATE ( …, LastSnap )`. Now the top 10 and the total use the same date. It only changes slices where a top-10 client left before the slice's last date. That's why the total, the years and the tiers didn't move.

## 5. A claim from Claude that I checked
**Claim (response 2):** *"The wrong numbers come from departed clients whose stale balances get into the top 10."*
**Confirmed in pandas.** For each of the 7 advisors, I reran the draft's logic (each client's own last row in 2023). Every one had exactly one top-10 client whose last snapshot was before Dec 2023 (the last column above). Advisor 2 had none, and its draft and final values are the same.

**Judgment of Claude's output:** the first draft was clean and explained its filter context correctly. But its test query only checked slices where the bug can't show up, so a "pass" there proved little. The fix in response 2 is correct, and I confirmed it in both tools.
