# Wildcat Capital — clean data set (HW4)

Produced by `scripts/02_clean.py` from the eight raw extract files. Same file names and columns as the raw files, plus four 0/1 flag columns. Raw files were never modified (MD5 checked at the end of every run).

| File | Raw rows | Clean rows | Quarantined | Role |
|---|---:|---:|---:|---|
| `dim_advisor.csv` | 25 | 25 | 0 | Advisors |
| `dim_benchmark.csv` | 8 | 8 | 0 | Benchmarks |
| `dim_client.csv` | 2,525 | 2,500 | 25 | Clients |
| `dim_date.csv` | 1,827 | 1,827 | 0 | Calendar 2020-01-01 → 2024-12-31 |
| `dim_security.csv` | 500 | 500 | 0 | Securities and ETFs |
| `fact_fees.csv` | 122,197 | 122,197 | 0 | Monthly fee accruals |
| `fact_portfolio_snapshot.csv` | 129,547 | 129,547 | 0 | Month-start account snapshots |
| `fact_transactions.csv` | 298,772 | 298,572 | 200 | Trades, income, cash flows, fee debits |

Quarantined rows are in `data/audit/quarantine_*.csv`. Every cell that changed is in `data/audit/value_changes.csv`.

## Relationships (for the Power BI star schema)

All are many-to-one, single direction (dimension filters fact).

| From (many) | To (one) | Notes |
|---|---|---|
| `fact_fees.client_id` | `dim_client.client_id` | |
| `fact_fees.advisor_id` | `dim_advisor.advisor_id` | |
| `fact_fees.fee_date` | `dim_date.date` | always the 1st of the month |
| `fact_portfolio_snapshot.client_id` | `dim_client.client_id` | one row per client per month |
| `fact_portfolio_snapshot.advisor_id` | `dim_advisor.advisor_id` | |
| `fact_portfolio_snapshot.benchmark_id` | `dim_benchmark.benchmark_id` | follows the client's risk profile |
| `fact_portfolio_snapshot.snapshot_date` | `dim_date.date` | always the 1st of the month |
| `fact_transactions.client_id` | `dim_client.client_id` | |
| `fact_transactions.advisor_id` | `dim_advisor.advisor_id` | |
| `fact_transactions.security_id` | `dim_security.security_id` | blank for Deposit / Withdrawal / Advisory Fee (34% of rows) — by design |
| `fact_transactions.txn_date` | `dim_date.date` | any day |
| `dim_client.advisor_id` | `dim_advisor.advisor_id` | snowflake link; facts also carry advisor_id directly and always agree |
| `dim_security.benchmark_id` | `dim_benchmark.benchmark_id` | snowflake link |

`fact_portfolio_snapshot` and `fact_fees` share the grain (client, month): fee `aum_basis` equals snapshot `aum` on 100% of fee rows. Each fact has its own date column, so each fact gets its own active relationship to `dim_date`. Because facts reach `dim_advisor` both directly and through `dim_client`, Power BI will see two paths: keep the direct fact → advisor relationships active and make `dim_client → dim_advisor` inactive (they agree on 100% of rows, so either path gives the same answer).

Match rate after cleaning: 100% on all 13 relationships (`reports/ri_results.csv`).

## Column types a BI tool needs

Set these by hand — do **not** let Power BI auto-detect.

| Type | Columns |
|---|---|
| **Whole number** | every `*_id` column; `age`, `years_experience`, `aum_target_mm`, `year`, `quarter`, `month`, `week_of_year` |
| **Text** (important) | `zip_code` (232 start with 0 — a number type would turn 03897 into 3897); `certifications` (`None` is a real value = no certification, not a null) |
| **Date** | `date`, `client_since`, `fee_date`, `snapshot_date`, `txn_date` (all ISO `YYYY-MM-DD`) |
| **Decimal / fixed decimal (currency)** | `initial_aum`, `aum_basis`, `amount`, `aum`, `price` |
| **Decimal** | `shares` (4 dp), `bps_charged`, `expense_ratio_bps` |
| **Decimal shown as %** | `return_ytd`, `benchmark_return_ytd`, `active_alpha_ytd`, `cash_pct` — stored as fractions (0.0928 = 9.28%). A few use scientific notation (`-1.9e-05`); they parse correctly. |
| **True/False** | `is_active`, `is_etf` |
| **Whole number 0/1** | `is_month_end`, `is_quarter_end`, `is_year_end`, `is_trading_day`, and all `flag_*` columns |

Blanks that are **expected** (keep "allow nulls" on): `dim_security.sector` (ETFs), `dim_security.expense_ratio_bps` (single stocks), `fact_transactions.security_id / shares / price` (cash movements), `dim_client.risk_profile` (75 clients, flagged).

Sign convention: `shares` and `amount` are always positive. Direction comes from `txn_type` (Buy, Withdrawal, Advisory Fee = money/shares out of cash or position; Sell, Deposit, Dividend = in).

## Flag columns added (0/1)

| Table | Column | = 1 when | Rows flagged |
|---|---|---|---:|
| `dim_client` | `flag_risk_profile_missing` | risk_profile is blank | 75 |
| `fact_portfolio_snapshot` | `flag_return_implausible` | \|return_ytd\| > 100% | 977 |
| `fact_portfolio_snapshot` | `flag_aum_at_floor` | aum is exactly 1,000.00 | 420 |
| `fact_transactions` | `flag_after_account_close` | inactive client, dated after their last snapshot month | 2,410 |

Suggested use: exclude `flag_return_implausible = 1` from average-return and alpha measures; show the others as filters.

## Known limitations (not fixed, on purpose)

1. **Missing risk profiles (75 clients).** All of them are benchmarked to the 60/40 blend, like Balanced clients, but that may be a system default. A suitability record is not something we can infer. Left blank, flagged.
2. **Implausible YTD returns (977 snapshots, 144 clients).** Returns appear to be computed from AUM change including deposits, so small accounts show returns like +287%. A real (cash-flow-adjusted) return needs data we don't have. Values kept, flagged.
3. **AUM floor at 1,000.00 (420 snapshots, 92 clients).** Looks like a minimum imposed by the source system; true values unknown. Kept, flagged.
4. **Activity after account close (2,410 transactions, 131 inactive clients).** Could be wind-down trades or bad dates; can't tell. Kept, flagged.
5. **Weekend trading dates (56,117 Buy/Sell/Dividend rows, about 28%).** Spread evenly across years and types, so it is a property of the extract (booking vs trade date), not a few bad rows. `dim_date.is_trading_day` marks weekends only — it has no market holidays. Analyse trading at monthly grain.
6. **Advisory Fee transactions ≠ fact_fees.** The cash debits in `fact_transactions` do not reconcile to the monthly accruals in `fact_fees` (2,340 of 2,500 clients differ by more than 5%). They come from different processes; use **`fact_fees`** for fee revenue and never add the two together.
7. **7,350 snapshot months with no fee row.** Every fee has a snapshot, but not every snapshot has a fee (waivers or billing gaps). No fees were created.
8. **Dividend rows carry shares × price = amount.** The dividend amount equals the position's market value, which is unusually large for a dividend. Left as recorded; treat dividend dollars with care.
9. **200 quarantined transactions ($10,888,495.37)** belong to client ids 2702–3192 that are not in the client master. They need the missing client records from the source system before they can be loaded.
10. **Benchmark 6 (MSCI Emerging Markets)** is in the dimension but no security or snapshot uses it.
