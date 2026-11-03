# HW5 – Wildcat Capital Star Schema Design

All numbers below come from `check_star_schema.py`, which loads the eight clean CSVs and tests every key and grain. Every check passes.

---

## Part A – Keys

| Table | Type | Primary key | Foreign keys (column → table[column]) |
|---|---|---|---|
| dim_advisor | Dimension | `advisor_id` | — |
| dim_benchmark | Dimension | `benchmark_id` | — |
| dim_client | Dimension | `client_id` | `advisor_id` → dim_advisor[advisor_id] |
| dim_date | Dimension | `date_id` (facts join on `date`, which is also unique) | — |
| dim_security | Dimension | `security_id` | `benchmark_id` → dim_benchmark[benchmark_id] |
| fact_fees | Fact | `fee_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`fee_date` → dim_date[date] |
| fact_portfolio_snapshot | Fact | `snapshot_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`benchmark_id` → dim_benchmark[benchmark_id]<br>`snapshot_date` → dim_date[date] |
| fact_transactions | Fact | `txn_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`security_id` → dim_security[security_id] *(can be blank)*<br>`txn_date` → dim_date[date] |

**Proof in code (`check_star_schema.py`):**
- All 8 primary keys are unique with no blanks. `dim_date[date]` is unique too, so it can act as the "one" side of the date relationships.
- All 13 foreign keys have **0 orphans**. Every value matches a row in the table it points to.
- **Key that can be blank:** `fact_transactions[security_id]` is blank on 101,528 rows. These are exactly the Deposit (35,956), Advisory Fee (35,742) and Withdrawal (29,830) rows. Cash moving in or out of an account does not involve a security, so there is nothing to point to. Every Buy, Sell and Dividend row has a valid `security_id`.
- **Date keys:** the fact tables store calendar dates (for example `2023-12-16`), not `date_id` numbers, so they match `dim_date[date]`. All fact dates fall inside the 2020–2024 calendar.

---

## Part B – Grain

- **fact_portfolio_snapshot:** One row represents one client's account for one month (client + month, dated the 1st of the month). There are 0 duplicates on `client_id + snapshot_date`, and every `snapshot_date` is the 1st of the month.
- **fact_fees:** One row represents the one fee charged to one client in one month. There are 0 duplicates on `client_id + fee_date`, and every `fee_date` is the 1st of the month, so this means one fee per client per month. `fee_type` says what kind of fee it was (Management, Advisory, Custodial or Performance).
- **fact_transactions:** One row represents a single transaction (a buy, sell, dividend, deposit, withdrawal or advisory-fee debit) for one client on one day. `txn_id` is unique, and no two rows are identical apart from `txn_id`.

---

## Part C – Measures

Test used for each column: *if I add this up across clients, across months, or both, does the total mean something?*

### Fact measures

| Table | Column | Type | What that means for summing |
|---|---|---|---|
| fact_fees | `amount` | **Additive** | Fee dollars can be summed across clients, months and fee types to give total fee revenue. |
| fact_fees | `aum_basis` | **Semi-additive** | It is a balance at one point in time. Summing across clients for one month is fine, but summing across months double-counts the same money. |
| fact_fees | `bps_charged` | **Non-additive** | It is a rate. Adding rates is meaningless, so use an average weighted by `aum_basis`. |
| fact_portfolio_snapshot | `aum` | **Semi-additive** | Sum across clients for one month to get firm AUM, but never across months. Use the last month of a period instead. |
| fact_portfolio_snapshot | `return_ytd` | **Non-additive** | It is a percentage, and it already builds up through the year. Never sum it. Show the latest month or an AUM-weighted average. |
| fact_portfolio_snapshot | `benchmark_return_ytd` | **Non-additive** | Same reason as `return_ytd`. |
| fact_portfolio_snapshot | `active_alpha_ytd` | **Non-additive** | It is a difference of two percentages (return minus benchmark), so it is never summed. |
| fact_portfolio_snapshot | `cash_pct` | **Non-additive** | It is a share of each account. Use an AUM-weighted average, not a sum. |
| fact_transactions | `amount` | **Additive (within one `txn_type`)** | Every amount is stored as a positive number and the direction comes from `txn_type`. Summing deposits alone is fine, but adding deposits and withdrawals together gives a meaningless total. |
| fact_transactions | `shares` | **Additive (within one security and `txn_type`)** | Shares of the same security can be summed across clients and days. Shares of different securities cannot be added together. |
| fact_transactions | `price` | **Non-additive** | It is a price per share. Adding prices is meaningless, so average it (weighted by shares) or use it to calculate value. |

### Numeric columns that are not measures

- **Keys:** `fee_id`, `snapshot_id`, `txn_id`, and every `client_id`, `advisor_id`, `security_id`, `benchmark_id` and `date_id`. They are labels, not quantities.
- **Date parts:** `fact_portfolio_snapshot[year]`, `[month]`, and in dim_date `year`, `quarter`, `month`, `week_of_year`.
- **Flags (0/1):** `fact_portfolio_snapshot[is_return_suspect]`, `fact_transactions[is_post_departure_txn]`, and dim_date `is_month_end`, `is_quarter_end`, `is_year_end`, `is_trading_day`. Use them to filter or count rows, not as amounts.

### Numeric attributes in dimension tables that should never be summed

- `dim_client[age]`: total age is meaningless; average it instead.
- `dim_client[initial_aum]`: a one-time starting balance. Adding it to the monthly fact AUM would double count.
- `dim_advisor[years_experience]` and `dim_advisor[aum_target_mm]`: describe one advisor each.
- `dim_security[expense_ratio_bps]`: a rate, blank for non-ETFs.

In Power BI these columns, plus every ID, date-part and flag column above, are set to **Don't summarize**, so Power BI never adds them up by default.

---

## Part E – Relationships and design questions

**Model built (hw05.pbix):** 8 tables and 13 relationships. Every relationship is many-to-one (fact on the many side) with single cross-filter direction. 12 are active and 1 is inactive. `dim_date` is marked as the date table on `date`. Auto date/time is turned off, so Power BI does not add hidden date tables.

**(a) Why do some transactions have no `security_id`? Is that a defect?**
No, it is not a defect. The 101,528 blank rows are all Deposits, Withdrawals and Advisory Fee debits. These are cash moving in or out of the account and do not involve buying, selling or holding a security, so there is no security to point to. In Power BI they appear as a `(Blank)` row when you slice by security. That is expected, and filling them in with a fake "Cash" ID would only hide what the rows are.

**(b) `advisor_id` is in `dim_client` and all three facts. Which relationship(s) are active, and why?**
The three fact → dim_advisor relationships are **active**. dim_client → dim_advisor is kept but **inactive** (dotted line). Power BI allows only one active path between two tables. If client → advisor were active, a filter from dim_advisor could reach each fact two ways (directly, and through dim_client), which is ambiguous. I chose the direct fact links because each fact row records the advisor responsible *at the time of that row*, while dim_client only holds the client's *current* advisor. Today the two agree on every row (the check script found 0 mismatches in all three facts), but the fact column stays correct if a client is ever reassigned. The `is_post_departure_txn` flag shows advisors do leave. The inactive relationship can still be used later with `USERELATIONSHIP` if we want "current advisor" reporting.

**(c) Which date column did you join on, and why?**
`dim_date[date]`. The facts store calendar dates (`txn_date`, `fee_date`, `snapshot_date`), and no fact table contains a `date_id`. Joining a date to `date_id` (a number from 1 to 1,827) would match nothing. `dim_date[date]` is unique and covers every fact date (0 orphans), and it is also the column used to mark the date table.

**(d) Star or snowflake?**
Two links connect one dimension to another: **dim_client → dim_advisor** and **dim_security → dim_benchmark**. I kept both. dim_client → dim_advisor is inactive for the reason in (b). dim_security → dim_benchmark is **active** because it is the only way to see which benchmark a transaction's security tracks (fact_transactions has no `benchmark_id`), and it creates no second path. So the model is a star with one small snowflake branch (security → benchmark). `dim_benchmark` is a **conformed dimension**: it filters fact_portfolio_snapshot directly and fact_transactions through dim_security. dim_client, dim_advisor and dim_date are conformed dimensions shared by all three facts.

---

## Part F – Reflection

1. **Fees:** *"What was our total fee revenue by fee type each quarter in 2024?"*
   **One visual, no DAX.** `amount` is additive, so a column chart with dim_date quarter on the axis, `fee_type` as the legend and Sum of `amount` gives the right answer.

2. **Portfolio snapshots:** *"What was total AUM by advisor region at the end of each year?"*
   **Not safe with a plain visual.** AUM is semi-additive, so putting `year` on the axis makes Power BI add up all 12 monthly balances, about 12 times too high. It only works if you filter the visual to one month, such as December. The real fix is a DAX measure that takes the last month in the period (Assignment 6). A schema change could also help: add a year-end or "latest snapshot" flag column to filter on.

3. **Transactions:** *"How much net new money (deposits minus withdrawals) did each advisor bring in per month?"*
   **Not answerable in one visual without a workaround.** Amounts are stored as positive numbers for every type, so Sum of `amount` adds withdrawals instead of subtracting them. You would need two visuals or a DAX measure. **Schema fix:** store a signed amount (money in positive, money out negative) or add a `direction` column (+1 / −1). Another option is splitting cash flows (deposits, withdrawals, fees) into their own fact table, separate from trades (buy, sell, dividend). Then net flow is a simple sum.
