# HW5 – Wildcat Capital Star Schema in Power BI

MIS3060 Business Intelligence with AI · Villanova University

This folder models the eight clean Wildcat Capital tables as a star schema. It covers which columns are keys, what one row of each fact table means, how each number may be added up, and how the tables are linked in Power BI.

## Folder structure

```
hw05/
├── README.md                      this file
├── star_design.md                 Parts A, B, C, E and F (keys, grain, measures, design questions, reflection)
├── check_star_schema.py           code that proves the keys, joins and grain (Parts A and B)
├── powerbi/
│   ├── hw05.pbix                  Power BI model (Part D)
│   └── model_view.png             Model view screenshot: all 8 tables and 13 relationships
├── dim_advisor.csv                \
├── dim_benchmark.csv               |
├── dim_client.csv                  |
├── dim_date.csv                    |  the eight clean tables from "Wildcat Capital Clean"
├── dim_security.csv                |
├── fact_fees.csv                   |
├── fact_portfolio_snapshot.csv     |
├── fact_transactions.csv          /
├── HW05_Star_Schema_and_Power_BI.md   assignment handout
└── powerbi_guide.md                   Power BI guide
```

## How to run

1. Install Python 3 and pandas (`pip install pandas`).
2. Open this `hw05` folder in VS Code (the eight CSVs must be in the same folder as the script).
3. Run:

   ```
   python check_star_schema.py
   ```

4. All 44 checks should say `PASS`, and the last line should say `ALL CHECKS PASSED`. The script exits with code 1 if any check fails, so a failure can't be missed.

The script checks:
- **Dates** in dim_date and the three fact tables are all valid dates.
- **Row counts** match the handout for all eight tables.
- **Primary keys** are unique and never blank (plus `dim_date[date]`, the column the facts join on).
- **Foreign keys**: all 13 point to a real row (0 orphans). The only blanks are 101,528 `security_id` values. A separate check proves these are only on Deposit, Withdrawal and Advisory Fee rows; every Buy, Sell and Dividend row has a security.
- **Grain**: snapshots are one row per `client_id + snapshot_date` and fees are one row per `client_id + fee_date`, with no blank key columns. Both monthly dates are always the 1st of the month. Transactions are one row per `txn_id`, and no two transactions are identical apart from their ID.
- **Part E(b)**: each fact row's `advisor_id` matches the client's advisor in `dim_client` on every row.

To open the model, open `powerbi/hw05.pbix` in Power BI Desktop (Apporto virtual desktop).

## Power BI model summary

- 8 tables loaded as-is: no surrogate keys, no new columns, no extra tables.
- 13 relationships, all many-to-one with single cross-filter direction:
  - 11 fact → dimension relationships (active). Dates join to `dim_date[date]`, not `date_id`.
  - `dim_security → dim_benchmark` (active, the one snowflake branch).
  - `dim_client → dim_advisor` (**inactive**, so dim_advisor has only one active path to each fact).
- `dim_date` is marked as the date table on `date`.
- Auto date/time is turned off, so Power BI adds no hidden date tables.
- No DAX measures, since measures start in ICE 9 / Assignment 6.

## Claude Code findings

I ran Claude Code on `check_star_schema.py` before committing. It confirmed the script ran and that the primary key and foreign key logic was correct. Its main point was that `star_design.md` claimed several things the script never actually tested. Claude Code checked each claim separately and the data satisfied all of them, so the write-up was right but not backed by code yet.

**What it found in check_star_schema.py, and what I changed**

| # | Finding | What I did |
|---|---|---|
| 1 | The fee grain in the code (`client_id + fee_date + fee_type`) was weaker than the one in star_design.md (one fee per client per month). With `fee_type` in the key, a client could have two fees in one month and still pass. | **Fixed.** The grain is now `client_id + fee_date`. It still has 0 duplicates. |
| 2 | The `fact_transactions` grain check just repeated the `txn_id` primary key check. | **Fixed.** It is now labeled honestly as "grain = one transaction (`txn_id`)", plus a new check that no two rows are identical apart from `txn_id` (0 found). |
| 3 | Three claims in star_design.md were only printed or not tested at all: monthly dates are always the 1st, Buy/Sell/Dividend rows always have a `security_id`, and the advisor matches `dim_client` on every fact row. A failure would still have ended in "ALL CHECKS PASSED". | **Fixed.** All three are now real PASS/FAIL checks. All pass. |
| 4 | Blank values in the grain columns weren't checked, and `duplicated()` treats two blanks as equal. | **Fixed.** The grain checks now also count blank key values (0 found). |
| 5 | The script always exited with code 0, even if a check failed. | **Fixed.** It now exits with code 1 when any check fails. |
| 6 | `pd.to_datetime` would crash on a bad date instead of reporting it. | **Fixed.** Dates use `errors="coerce"` and a new check reports any unreadable date (0 found). |
| 7 | Readability: a confusing f-string in the foreign key output, `zip_code` typed for every table, and a fallback for the old `fact_transactions(2).csv` name. | **Fixed.** Simplified the message, only `dim_client` sets `zip_code` as text, and I renamed the CSV to `fact_transactions.csv` and removed the fallback. Added a comment explaining that `security_id` reads as 45.0 vs 45 but still matches. |
| 8 | Optional: wrap the code in a `main()` function instead of using a `global` counter, and check that the snapshot `year`/`month` columns match `snapshot_date`. | **Not changed.** Not required for the assignment. Claude Code checked that year/month agree with the date on every row. |

After the changes the script runs **44 checks, all passing**.

**Power BI model review (Claude, before the code review)**
- Found a leftover `_Measure` table with a "Total Fees" measure and a calculated `Advisor` column in dim_advisor. The assignment says no measures and no new columns yet, so both were **removed**, along with two test visuals on the report page.
- Found three hidden auto date/time tables Power BI had added on its own. Turned **Auto date/time off**, which removed them.
- Found that `dim_date` was **not marked as a date table**. Marked it on `date`.
- Found that the `dim_client → dim_advisor` link was missing. **Added it as inactive** so the model shows the foreign key without creating a second path to dim_advisor.
- Confirmed in DAX query view: row counts match the handout, column types follow the guide (`zip_code` is Text, `is_active` is True/False, dates are Date), and there are no orphan keys.
