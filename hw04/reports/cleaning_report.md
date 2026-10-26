# Wildcat Capital — Data Cleaning Report
**To:** Portfolio Committee  **From:** BI Analyst (MIS3060 HW4)  **Re:** Quality of the 2020–2024 warehouse extract

## Executive summary
The eight-table extract is **usable after cleaning**, and every number below comes from our own script output. Before cleaning, two problems would have broken reporting outright. First, **no trade could be linked to its security**: all 197,175 `security_id` values were stored as `45.0` instead of `45`, so the text join matched 0%. Second, **25 clients were loaded twice**, inflating the client count from 2,500 to 2,525. We also corrected 836 Buy trades recorded with negative shares ($52.0M of purchases that would have netted out), 300 returns stored as text such as `9.28%`, and 78 states written as full names.

We removed only **225 of 555,401 rows** (0.04%). The 25 duplicate clients had no activity, and the 200 transactions ($10.9M, 0.07% of transaction dollars) belong to clients that do not exist in the client master. All removed rows are kept in quarantine files. After cleaning, all 13 table relationships match at **100%**, and raw = clean + quarantined holds for every table.

Some issues **cannot be fixed without inventing data**, so we flagged them instead. The most important is **977 snapshots with year-to-date returns above 100%**. They will distort any average-return or alpha KPI unless filtered (mean return 11.4% vs. median 3.2%).

## Cleaning summary
| # | Table | Issue | Action | Rows |
|---|---|---|---|---:|
| D04 | fact_transactions | security_id stored as `45.0` (0% join to securities) | Convert to `45` | 197,175 |
| D05 | fact_transactions | Buy trades with negative shares | Absolute value (verified vs. amount) | 836 |
| D06 | fact_transactions | client_id not in client master (ids 2702–3192) | Quarantine | 200 |
| D03 | fact_portfolio_snapshot | return_ytd stored as `9.28%` text | Convert to decimal (verified vs. benchmark + alpha) | 300 |
| D01 | dim_client | Same client keyed twice, last name mis-typed | Quarantine copy | 25 |
| D02 | dim_client | State as full name (`Pennsylvania`) | Standardize to `PA` | 78 |
| D08 | dim_client | Risk profile blank | Flag, leave blank | 75 |
| D09 | fact_portfolio_snapshot | \|return_ytd\| > 100% | Flag | 977 |
| D10 | fact_portfolio_snapshot | AUM exactly 1,000.00 (system floor) | Flag | 420 |
| D11 | fact_transactions | Activity after an inactive client's last snapshot | Flag | 2,410 |

**Data quality scorecard (raw → clean)** — from `reports/data_quality_scorecard.csv`

| Table | Completeness | Key uniqueness | Type validity | Rule pass | Referential match |
|---|---|---|---|---|---|
| dim_client | 99.785% → 99.786% | 98.02% → 100% | 100% → 100% | 99.311% → 100% | 100% → 100% |
| fact_portfolio_snapshot | 100% → 100% | 100% → 100% | 99.981% → 100% | 99.906% → 99.923% | 100% → 100% |
| fact_transactions | 100% → 100% | 100% → 100% | 90.545% → 100% | 99.823% → 99.895% | 81.95% → 100% |
| other 5 tables | 100% | 100% | 100% | 100% | 100% / n/a |

Rule pass stays below 100% on purpose: the flagged plausibility issues (D09–D11) are still in the data, visible and filterable, not hidden.

## Key judgment calls
**1. We did not fill the 75 missing risk profiles.** All 3,942 snapshots for these clients use the 60/40 Blend benchmark, the same one Balanced clients get, so "Balanced" is a tempting fill. But that benchmark is also the obvious system default when the profile is unknown, and a risk profile is a suitability record. *Risk:* if they really are Balanced, that segment is understated by 75 clients (3%). An honest "blank" is better than a wrong compliance record.

**2. We let the fact tables decide which duplicate client to remove.** The 25 pairs match on 12 columns, down to initial AUM to the cent. The last name alone could not tell us which row was real: usually the copy is cut short ("Taylo"), but twice it is longer ("Leen" vs. "Lee"). Checking the facts settled it. Each original has full fee, snapshot and transaction history, and each copy has none. *Risk:* minimal. No activity was moved or lost, and the copies are kept in quarantine with the matched id.

**3. We corrected returns by reconciling, not by stripping the % sign.** For the 300 `9.28%` values, we used benchmark return + alpha and checked that it agreed with the text ÷ 100 on every row (largest gap 0.00005, the rounding of the text). Simply removing the % sign would have made those returns 100× too large. *Risk:* none remaining. The script stops if any row fails to reconcile.

**4. We kept, and flagged, implausible returns rather than deleting them.** The 977 rows (144 clients, mostly small accounts) are arithmetically consistent: return − benchmark = alpha, and the returns follow AUM jumps that appear to include deposits. Deleting them would remove real months of real accounts. *Risk:* if dashboards don't filter `flag_return_implausible = 1`, average return and advisor alpha will be overstated.

## Limitations
- **Fee cash debits vs. fee accruals do not reconcile.** For 2,340 of 2,500 clients, the "Advisory Fee" transactions differ by more than 5% from `fact_fees`. Use `fact_fees` for revenue (it recomputes exactly: AUM × bps ÷ 12 on 122,197 of 122,197 rows). Never add the two together.
- **56,117 trades (about 28%) are dated on weekends**, spread evenly over all years. This looks like a booking-date convention. The calendar has no market holidays. Report trading monthly, not daily.
- **2,410 transactions after account close** and **420 AUM-floor snapshots** are flagged, not corrected. The true values are unknown.
- **Dividend amounts equal the full position value** (shares × price), which overstates income if summed.
- **$10.9M in 200 quarantined transactions** needs the missing client records from the source system.
- **IQR outlier flags** (for example, 10.2% of snapshot AUM values) mark large clients, not errors. AUM is right-skewed by design.

---
*AI-assisted report — reviewed for factual accuracy on October 25, 2026 by Delia Kline*
