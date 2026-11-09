# Part D – Claude session for measure 11 (`Top 10 Client Share`)

Measure chosen: **11 – Top 10 Client Share**.
Workflow: **Draft → Test → Debug → Review** (Week 10).

Note on the tool: this session ran with Claude in the Claude app (the same model as Claude Desktop). The prompts and replies are copied below in full. The metadata I attached is `claude/model_metadata.md`.

---

## Prompt 1 – Draft

> I'm adding a measure to a Power BI model for Wildcat Capital (a wealth manager). The model metadata (columns, relationships, existing measures) from the three INFO.VIEW queries is attached as `model_metadata.md`.
>
> Things the metadata can't tell you:
> - **Grain:** `fact_portfolio_snapshot` has one row per client per month. `snapshot_date` is always the 1st of the month. The latest snapshot is 2024-12-01.
> - **`aum` is a balance** (semi-additive). Never add it up across months. Read it at the last snapshot in the filter.
> - **`active_alpha_ytd` is a year-to-date rate.** It's not used in this measure.
> - `dim_date` is the marked date table. It joins on `dim_date[date]`. `dim_client` joins on `client_id`.
> - 175 of the 2,500 clients have left. Their last snapshot is before Dec 2024.
> - An existing measure, `[Ending AUM]`, is `CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ), LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) ) )`.
>
> **Business definition:** `Top 10 Client Share` = the share of Ending AUM held by the 10 largest clients **within the current filter**. Use TOPN over `VALUES ( dim_client[client_id] )`.
>
> Please give me:
> 1. the DAX for the measure,
> 2. a plain explanation of its filter context (what each part sees),
> 3. a DAX query I can run in DAX query view to test it by year and in total.

## Claude's response 1

> Here's a first version that reuses `[Ending AUM]`:
>
> ```DAX
> Top 10 Client Share =
> VAR Top10 =
>     SUMX (
>         TOPN ( 10, VALUES ( dim_client[client_id] ), [Ending AUM] ),
>         [Ending AUM]
>     )
> RETURN
>     DIVIDE ( Top10, [Ending AUM] )
> ```
>
> **Filter context, step by step**
> - `VALUES ( dim_client[client_id] )` gives the clients visible in the current filter (for example, one tier, one advisor or one year).
> - `TOPN ( 10, …, [Ending AUM] )` ranks those clients. `[Ending AUM]` is a measure, so it runs inside a **context transition**: for each client, the row becomes a filter on that client. So each client is ranked by *their own* balance at *their own* last snapshot in the filter.
> - `SUMX ( …, [Ending AUM] )` adds those 10 balances together, using the same per-client context transition.
> - The denominator `[Ending AUM]` runs in the outer filter, so it's the firm (or tier, or year) balance at the last snapshot.
> - `DIVIDE` returns BLANK instead of an error when the denominator is blank.
>
> Because `aum` is a balance, nothing is summed across months. Each client contributes one balance.
>
> **Test query**
>
> ```DAX
> EVALUATE
> SUMMARIZECOLUMNS (
>     dim_date[year],
>     "Ending AUM", [Ending AUM],
>     "Top 10 Client Share", [Top 10 Client Share]
> )
> ORDER BY dim_date[year]
>
> EVALUATE
> { ( "Total", [Ending AUM], [Top 10 Client Share] ) }
> ```
>
> Expect a share between 0 and 1. Check it's no bigger than 10 × the largest single client's balance ÷ Ending AUM.

## What I got when I ran it (Test)

The draft ran as written. Results:

| Slice | Top 10 Client Share (draft) |
|---|---|
| Total | 0.061589 |
| 2020 | 0.070411 |
| 2021 | 0.063754 |
| 2022 | 0.055309 |
| 2023 | 0.060383 |
| 2024 | 0.061589 |
| 2024 HNW / Retail / UHNW | 0.031397 / 0.018348 / 0.081264 |

All of these matched pandas. Next I tested a slice the prompt didn't mention: **by advisor, in 2023**.

## Prompt 2 – Debug / Review

> I tested your measure by `dim_advisor[advisor_id]` with `dim_date[year] = 2023`. For 7 advisors (1, 5, 10, 14, 17, 18, 21), the share is higher than my pandas check. For example, advisor 1 shows 0.8739 in Power BI but 0.7644 in pandas. Pandas takes the top 10 clients **at the advisor's last snapshot date** (Dec 2023). Review your measure. Is `[Ending AUM]` inside TOPN/SUMX picking up the wrong date for some clients?

## Claude's response 2

> Yes – that's the bug. Inside `TOPN` and `SUMX`, the context transition makes `[Ending AUM]` look for **each client's own last snapshot** in the filter. For a client who left part-way through 2023 (for example, last snapshot in June 2023), that is their June balance. So a client who no longer has money with the firm can still be ranked in the top 10 and counted in the numerator.
>
> The denominator doesn't have this problem. It's evaluated once, at the **filter's** last snapshot (Dec 2023), where departed clients have no row. So the numerator includes stale balances that the denominator doesn't. The share goes up.
>
> The firm total, the years and the 2024 tiers looked fine only because no top-10 client in those slices had left before the slice's last date. That was luck, not correctness.
>
> **Fix:** find the filter's last snapshot date once, then rank and add up clients at that one date only:
>
> ```DAX
> Top 10 Client Share =
> VAR LastSnap =
>     LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
> VAR Top10 =
>     CALCULATE (
>         SUMX (
>             TOPN ( 10, VALUES ( dim_client[client_id] ),
>                    CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ) ) ),
>             CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ) )
>         ),
>         LastSnap
>     )
> RETURN
>     DIVIDE ( Top10, [Ending AUM] )
> ```
>
> - `LastSnap` is evaluated in the outer filter, so it's the same date the denominator uses.
> - `CALCULATE ( …, LastSnap )` pins the whole TOPN/SUMX to that one date. A client with no row on that date gets a blank balance, so they can't make the top 10.
> - `CALCULATE ( SUM ( aum ) )` still does the context transition per client, but now only at that one date.
>
> **Test query for the edge case:**
>
> ```DAX
> EVALUATE
> CALCULATETABLE (
>     SUMMARIZECOLUMNS (
>         dim_advisor[advisor_id],
>         "Ending AUM", [Ending AUM],
>         "Top 10 Client Share", [Top 10 Client Share]
>     ),
>     dim_date[year] = 2023
> )
> ORDER BY dim_advisor[advisor_id]
> ```
>
> Advisors 1, 5, 10, 14, 17, 18 and 21 should now match pandas. Everything else should be unchanged.

The fixed version is the one in the model and in `powerbi/measures.md`. `claude/verification.md` shows how I checked it.
