# HW6 – DAX Measure Library (Wildcat Capital)

This builds a set of Power BI measures on the posted `Wildcat_Star_Model.pbix`, checks every number against pandas, answers the design questions, and documents one measure drafted with Claude.

## Folder structure
```
hw06/
├── README.md                          this file
├── powerbi/
│   ├── hw06.pbix                      posted model + _Measures table + "Measures" report page
│   ├── measures.md                    Part A (DAX, pattern, meaning for each measure) + Part C answers
│   ├── measures_dax.txt               all 16 measures as one DEFINE block (paste into DAX query view)
│   └── powerbi_values_export.dax      the DAX query that produces reports/powerbi_values.csv
├── scripts/
│   └── 01_reconcile_measures.py       Part B: pandas recompute + comparison
├── reports/
│   ├── powerbi_values.csv             numbers exported from Power BI DAX query view (172 rows)
│   ├── pandas_values.csv              pandas numbers on their own (written by the script)
│   └── measure_reconciliation.csv     side-by-side comparison (172 rows, all match)
└── claude/
    ├── model_metadata.md              the three INFO.VIEW query exports + context the metadata can't show
    ├── dax_session.md                 Part D prompts and Claude's full replies (Top 10 Client Share)
    └── verification.md                Part D checks, edge cases and what changed
```

## Measures (all in the `_Measures` table)
`Total Fees`, `Net Flows`, `AUM (naive SUM)` (kept only to show the mistake, never on the report; its description says "WRONG"), `Ending AUM`, `Ending Clients`, `Avg AUM per Client`, `Ending AUM LY`, `AUM YoY %`, `Ending AUM PM`, `AUM MoM %`, `Avg Monthly AUM`, `Fee Yield (bps)`, `Organic Growth Rate`, `AUM-Weighted Alpha`, `Alpha Signal`, `Top 10 Client Share`. Each one is formatted as currency, %, a count or bps.

## How to run the reconciliation
The script reads five of the clean CSVs from `../hw05/` (Assignment 5): `fact_portfolio_snapshot`, `fact_fees`, `fact_transactions`, `dim_client` and `dim_date`. It doesn't need `dim_advisor`, `dim_benchmark` or `dim_security`, because `advisor_id` is already on the snapshot table. It reads the Power BI numbers from `reports/powerbi_values.csv`.

```bash
cd hw06
python scripts/01_reconcile_measures.py
```

It writes `reports/pandas_values.csv` and `reports/measure_reconciliation.csv`, and prints a summary. The exit code is 0 only when every row matches and nothing is missing, extra or duplicated.

Tolerance:
- **Currency:** 0.01.
- **Ratios:** 0.0001, plus a relative check (1e-6), so a small ratio can't be 10% off and still pass.
- **Counts:** must match exactly.

**Result: 172 rows compared, 172 match, 0 do not.**

Slices covered:
- every measure at the grand total
- measures 1, 4, 6–10 for each year 2020–2024, plus the naive SUM, Ending Clients, Avg AUM per Client, Total Fees, Net Flows and Top 10 by year
- measures 1, 3, 4, 7–11 for each client tier in 2024 (tiers are read from `dim_client`)
- measure 5 for December 2024, March 2024 (prior month is February, a short month) and January 2020 (no prior month, so it must be blank)
- Ending AUM and Top 10 Client Share for each of the 25 advisors in 2023. This is the slice that exposed the bug in Claude's first Top 10 draft (Part D).

Only 5 rows are allowed to be blank in both tools: the 2020 prior-year rows (Ending AUM LY, AUM YoY %, Organic Growth Rate) and the Jan 2020 prior-month rows (Ending AUM PM, AUM MoM %). Any other blank counts as a failure.

`AUM (naive SUM)` and its pandas twin also match ($566.7B vs the real $12.7B Ending AUM). So both tools make the same mistake if you add up a balance across months.

To refresh `powerbi_values.csv`: open `hw06.pbix` → DAX query view → run `powerbi/powerbi_values_export.dax` → Copy → Entire table → save as CSV with the columns `measure, slice, value`. Each value uses `FORMAT ( v, "0.000000000000" )` (12 decimals). Power BI stores numbers with only about 15–16 significant digits, so large values come out like `88551598743.619900000000`. When saving the CSV I removed the trailing zeros (giving `88551598743.6199`). No Excel step was used. This changes no result: the largest difference it can cause is far below the 0.01 currency tolerance.

**"All match" means the two tools agree, not that every definition is perfect.** The pandas code follows the same business definitions as the DAX. Two examples where both tools agree but the number needs care:
- Organic Growth Rate at the grand total divides five years of flows by Dec 2023 AUM.
- Net Flows counts every Deposit and Withdrawal row.

## Mismatches and fixes
- **No reconciliation row was off in the final run.** I also tested the check itself: I planted 4 errors in `powerbi_values.csv` (Claude's draft Top 10 value for advisor 1, a UHNW Organic Growth 10% off, an unexpected blank, an extra row). The script caught all 4, then I put the real values back.
- **`Top 10 Client Share` (Claude's first draft):** it matched at the total, every year and every 2024 tier, but **Power BI was wrong** for 7 advisors in 2023. For example, advisor 1 showed 0.8739 vs 0.7644 in pandas. The draft ranked each client at their *own* last snapshot, so clients who had left were still counted. I pinned the whole calculation to the filter's last snapshot date. Details are in `claude/verification.md`.
- **Variable name error:** I first named a variable `LastDate`. Power BI rejected it because it clashes with the function `LASTDATE`. I renamed it `LastSnap`.

## Claude Code review findings
I ran `claude` in the `hw06` folder and asked it to review `scripts/01_reconcile_measures.py` before committing. It found **no bug that changed any of the 91 results**, but it found ways a wrong number could slip through. It said to fix items 1–4 and 7 before committing. I fixed those and most of the others, then reran: **172 of 172 match**.

| # | What Claude Code flagged | What I did about it |
|---|---|---|
| 1 | The 0.0001 ratio tolerance is too loose for small values. UHNW Organic Growth is 0.001, so a 10% error would pass | Kept the assignment's limits and added a relative check of 1e-6 for ratios. Tested: a planted 0.0011 now fails |
| 2 | "Both blank" counted as a match on any row, so a misspelled slice could pass | Only the 5 expected rows (2020 prior-year, Jan 2020 prior-month) may be blank. Any other blank fails. Tested with a planted blank |
| 3 | Rows only in the Power BI file were never reported. No check for duplicates or row count | The script now uses an outer merge and reports extra rows and duplicate (measure, slice) rows as problems. Exit code 1 if any |
| 4 | Tier list and date range were typed into the code | Tiers now come from `dim_client.csv` and the date range from `dim_date.csv` |
| 5 | pandas copies the DAX, so it can't catch a design mistake | Added a note in the script and this README: "all match" = the tools agree. Gave the Organic Growth total and Net Flows examples |
| 6 | Dec 2024 and Year 2024 repeat the Total rows. DATEADD never tested where it could go wrong | Added Mar 2024 (prior month is February) and Jan 2020 (no prior month, must be blank) |
| 7 | The 2023 by-advisor check behind the Top 10 fix wasn't in the script | Added Ending AUM and Top 10 for all 25 advisors in 2023 (50 rows) and exported their Power BI values. All match. Tested: Claude's draft value for advisor 1 (0.8739) now fails |
| 8 | Some measures were only checked at the grand total | Added Ending Clients, Avg AUM per Client, Total Fees, Net Flows and Top 10 by year |
| 9 | `pandas_values.csv` was only written when the Power BI file was missing | It's now written on every run |
| 10 | `nlargest(10)` keeps exactly 10, DAX `TOPN` keeps ties | No change. There are no ties at 10th place in any slice, and every Top 10 row matches. Noted as a known difference |
| 11 | Ending Clients was labelled a "ratio" | Made it its own "count" kind that needs an exact match |
| 12 | Calculations ran on import, not inside `main()` | Moved them into `build_pandas()`, which `main()` calls |

## Notes
- `hw06.pbix` was built in Power BI Desktop on Apporto. That version is older than the one that made the posted file, so the data was **never refreshed** in Apporto. The model data is the data that came with `Wildcat_Star_Model.pbix`.
- The **Measures** page has 4 cards (Ending AUM, Ending Clients, Avg AUM per Client, Top 10 Client Share) along the top, the year table, the 2024 tier table, and a small **"Card values" table** at the bottom. In Apporto's older Power BI the Card visual draws blank, even though each card holds the right measure. The "Card values" table shows the same 4 numbers ($12,729,572,079 · 2,325 · $5,475,085 · 6.16%), so they are visible in any Power BI version.
- The posted model has Power BI's Auto date/time hidden tables (`LocalDateTable_…`). I left them as they were. No measure uses them.
