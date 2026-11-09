# HW6 – DAX Measure Library: AUM & Performance

All measures live in the `_Measures` table of `powerbi/hw06.pbix`. Every number below was reconciled to an independent pandas calculation (`reports/measure_reconciliation.csv`).

**The three additivity patterns (from Assignment 5 Part C):**
- **SUM** – additive columns (fee `amount`, transaction `amount`). They can be added across any dimension.
- **Last balance** – semi-additive columns (`aum`). Take the balance at the last snapshot date that has data in the current filter (`LASTNONBLANK`). Never add balances across months.
- **Recompute-and-weight** – non-additive rates (fee yield, growth, alpha). Rebuild each rate from additive parts with `DIVIDE`, or weight it row by row with `SUMX`. Never sum or simple-average the rate.

Snapshot dates fall on the 1st of each month, so `LASTDATE` / `ENDOFMONTH` would land on dates with no data. That's why every balance uses `LASTNONBLANK`.

---

## Part A – Measure library

### Base measures (from ICE 9)
| Measure | DAX | Pattern | Format |
|---|---|---|---|
| Total Fees | `SUM ( fact_fees[amount] )` | SUM | $ |
| Net Flows | `CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[txn_type] = "Deposit" ) - CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[txn_type] = "Withdrawal" )` | SUM (filtered) | $ |

### 0. AUM (naive SUM) – **WRONG, kept only to show the trap**
```DAX
AUM (naive SUM) = SUM ( fact_portfolio_snapshot[aum] )
```
- **Pattern:** SUM, which is the wrong pattern for a balance.
- **Meaning:** It adds the same money once for every month it was held. At the grand total it shows **$566.68B**, about 45× the real $12.73B the firm manages. It is never placed on the report.

### 1. Ending AUM
```DAX
Ending AUM =
CALCULATE (
    SUM ( fact_portfolio_snapshot[aum] ),
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
)
```
- **Pattern:** last balance.
- **Meaning:** How much money Wildcat manages at the end of the selected period. Today (Dec 2024) that's **$12.73B**.

### 2. Ending Clients
```DAX
Ending Clients =
CALCULATE (
    DISTINCTCOUNT ( fact_portfolio_snapshot[client_id] ),
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
)
```
- **Pattern:** last balance (a count taken at the last snapshot).
- **Meaning:** How many clients have money with Wildcat at the end of the period. Today that's **2,325**, because the other 175 clients have left.

### 3. Avg AUM per Client
```DAX
Avg AUM per Client = DIVIDE ( [Ending AUM], [Ending Clients] )
```
- **Pattern:** recompute-and-weight (a ratio of two last balances).
- **Meaning:** The size of a typical relationship at period end: **$5.48M** firm-wide, from $383K for Retail to $39.5M for UHNW.

### 4. Ending AUM LY and AUM YoY %
```DAX
Ending AUM LY = CALCULATE ( [Ending AUM], SAMEPERIODLASTYEAR ( dim_date[date] ) )
AUM YoY %     = DIVIDE ( [Ending AUM] - [Ending AUM LY], [Ending AUM LY] )
```
- **Pattern:** last balance, shifted back one year. Then recompute (growth from two balances).
- **Meaning:** How much bigger the book is than a year ago. 2024 grew **+19.6%**. 2020 is blank because there is no 2019 data. There is deliberately no `0` alternate in `DIVIDE`, so a missing prior year is never shown as "0% growth".

### 5. Ending AUM PM and AUM MoM %
```DAX
Ending AUM PM = CALCULATE ( [Ending AUM], DATEADD ( dim_date[date], -1, MONTH ) )
AUM MoM %     = DIVIDE ( [Ending AUM] - [Ending AUM PM], [Ending AUM PM] )
```
- **Pattern:** last balance, shifted back one month. Then recompute.
- **Meaning:** Month-over-month change in the book. December 2024 was **+4.2%** over November.

### 6. Avg Monthly AUM
```DAX
Avg Monthly AUM =
DIVIDE (
    SUM ( fact_portfolio_snapshot[aum] ),
    DISTINCTCOUNT ( fact_portfolio_snapshot[snapshot_date] )
)
```
- **Pattern:** recompute (sum of balances ÷ number of months = average balance).
- **Meaning:** The average amount managed during the period, not just at the end. In 2024 it was **$11.29B**, compared with $12.73B at year-end. This is the fair base for anything earned over the whole year.

### 7. Fee Yield (bps)
```DAX
Fee Yield (bps) =
DIVIDE ( [Total Fees] * 12 * 10000, SUM ( fact_portfolio_snapshot[aum] ) )
```
- **Pattern:** recompute-and-weight across **two fact tables** (additive fees ÷ summed monthly balances).
- **Meaning:** What Wildcat earns per year on each dollar it manages: **43.2 bps** in 2024. Retail pays the most (82.8 bps) and UHNW the least (36.1 bps).

### 8. Organic Growth Rate
```DAX
Organic Growth Rate = DIVIDE ( [Net Flows], [Ending AUM LY] )
```
- **Pattern:** recompute (additive flows ÷ a last balance).
- **Meaning:** Growth from clients bringing in new money, as opposed to markets lifting existing balances. In 2024 that was **+0.7%** of last year's book.

### 9. AUM-Weighted Alpha
```DAX
AUM-Weighted Alpha =
VAR LastSnap =
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
RETURN
    CALCULATE (
        DIVIDE (
            SUMX ( fact_portfolio_snapshot,
                   fact_portfolio_snapshot[aum] * fact_portfolio_snapshot[active_alpha_ytd] ),
            SUM ( fact_portfolio_snapshot[aum] )
        ),
        LastSnap,
        fact_portfolio_snapshot[is_return_suspect] = 0
    )
```
- **Pattern:** recompute-and-weight (SUMX of aum × alpha ÷ SUM of aum), read at the last snapshot only.
- **Meaning:** How much clients beat their benchmarks so far this year, counting a $50M account 50 times more than a $1M account. 2024: **+1.45%**.

### 10. Alpha Signal
```DAX
Alpha Signal =
VAR a = [AUM-Weighted Alpha]
RETURN
    SWITCH ( TRUE (),
        ISBLANK ( a ), BLANK (),
        a >= 0.02,  "Outperforming",
        a <= -0.02, "Lagging",
        "In line" )
```
- **Pattern:** a text label built on a recomputed rate.
- **Meaning:** A plain-English flag a manager can scan. It is blank when there is no alpha to judge. 2022 and 2024 Retail are "Outperforming"; everything else is "In line".

### 11. Top 10 Client Share
```DAX
Top 10 Client Share =
VAR LastSnap =
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
VAR Top10 =
    CALCULATE (
        SUMX (
            TOPN ( 10, VALUES ( dim_client[client_id] ),
                   CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ) ) ),
            CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ) )
        ),
        LastSnap
    )
RETURN
    DIVIDE ( Top10, [Ending AUM] )
```
- **Pattern:** recompute (the top 10 clients' last balances ÷ all last balances). `VALUES ( dim_client[client_id] )` keeps the ranking **inside the current filter**, so a tier row only ranks that tier's clients.
- **Meaning:** How concentrated the business is. The 10 largest clients hold **6.2%** of firm AUM, and 8.1% of UHNW AUM. Losing one of them would show up quickly.

---

## Part C – Design questions

### (a) `Ending AUM` vs `SUMX ( VALUES ( dim_client[client_id] ), [Ending AUM] )`
| Measure (no filters) | Value |
|---|---|
| `Ending AUM` | **$12,729,572,078.86** |
| `SUMX ( VALUES ( dim_client[client_id] ), [Ending AUM] )` | **$13,149,297,713.80** |
| Difference | **$419,725,634.94** |

`Ending AUM` finds **one** last date for the whole firm (Dec 1, 2024) and adds up every balance on that date.

The SUMX version loops over all 2,500 clients. Context transition gives **each client their own last date**. For the 2,325 current clients that is Dec 2024, but for the **175 clients who have left** it is their final month before leaving (between Dec 2022 and Nov 2023). Those 175 old balances add up to exactly **$419.73M**, which is money Wildcat no longer manages.

So `Ending AUM` ($12.73B) is the answer to "How much do we manage today?" The SUMX total mixes balances from different dates and counts clients who are gone.

### (b) Why 2024 `Fee Yield (bps)` is lower than ICE 9 `Effective Fee Rate (bps)`
| 2024 | Fees | Denominator | Rate |
|---|---|---|---|
| Effective Fee Rate (ICE 9) | $48,714,005.93 | Σ `fact_fees[aum_basis]` = $128.39B | **45.5 bps** |
| Fee Yield (bps) | $48,714,005.93 | Σ `fact_portfolio_snapshot[aum]` = $135.46B | **43.2 bps** |

Both rates use the same fees, so the difference has to be in the denominator. pandas evidence (matching the two fact tables on `client_id` + month):
- Wherever both tables have a row, `aum_basis` equals `aum` **exactly** (0.00 difference on all 26,216 matched rows). So the balances are not the cause.
- **1,684 client-months in 2024 have an AUM snapshot but no fee row at all.** They hold **$7.07B**, or 5.2% of the year's summed AUM. Fee Yield counts that money in the denominator with zero fees. The Effective Fee Rate never sees it, because it only looks at rows that were billed.
- It happens every year (1,139 to 1,684 client-months a year, 7,350 in total, spread across 2,261 clients and all three tiers in their normal proportions). Only about 2% of the gaps are a client's first month, so it is not an onboarding effect.

**Data limitation:** `fact_fees` is **incomplete**. Some client-months have assets but no fee record, and the data does not say whether the fee was waived, billed late, or simply missing. The Effective Fee Rate quietly ignores unbilled assets, so it overstates what the firm earns on its whole book. Fee Yield is the more honest firm-wide number, but neither can tell us whether the missing fees were really never charged.

### (c) Why `AUM-Weighted Alpha` uses the last snapshot only and excludes suspects
- **Last snapshot only:** `active_alpha_ytd` is **year-to-date**. January's value covers one month and December's covers twelve. Weighting all 12 months together mixes a 1-month result with an 11-month one, so the answer means nothing. The December 2024 snapshot already contains the full year. Across all months of 2020–2024 (suspects excluded), the weighted value would be **0.38%** instead of the correct **1.45%**.
- **Exclude `is_return_suspect = 1`:** these rows have impossible returns, as high as +7,134% for a single account in Dec 2024. They are data errors, not performance.

| Dec 2024 snapshot | Value |
|---|---|
| AUM-Weighted Alpha (suspects excluded) – **the measure** | **+1.45%** |
| Simple mean of `active_alpha_ytd`, same rows (suspects excluded) | +0.88% |
| AUM-weighted, **suspects included** (148 suspect rows) | +1.67% |

The simple mean (0.88%) treats a $50K account like a $50M one, which understates how the firm's money actually did. Including suspects raises the result to 1.67% on the strength of bad data. That's enough to push it close to the "Outperforming" line, which would be a misleading flag.

### (d) Organic Growth Rate vs AUM YoY % by client tier, 2024
| Tier | Ending AUM | AUM YoY % | Organic Growth Rate |
|---|---|---|---|
| Retail | $0.53B | +19.1% | **+9.9%** |
| HNW | $2.55B | +19.6% | +1.2% |
| UHNW | $9.65B | +19.6% | +0.1% |
| Firm | $12.73B | +19.6% | +0.7% |

**What it says:** All three tiers grew about 19–20%, but almost none of that came from new money. For the firm, only 0.7 points of the 19.6% is net new money; the rest is market gains on existing balances. **Retail is the only tier really bringing in new money** (+9.9% of last year's book). UHNW, which holds three-quarters of the assets, added almost nothing (+0.1%). Wildcat's organic growth comes from its smallest clients.

**What it does not tell you:**
- *Why* the growth happened. Investment returns, client withdrawals and lost clients are all mixed into AUM YoY %.
- *How much revenue* the growth brings. Retail flows are large relative to Retail's small book, but they are small in dollars (Retail is only 4% of AUM).
- Whether the growth will last. It is one year, one ratio, and says nothing about client counts or retention.
- Whether new money came from **new clients or existing ones**.
