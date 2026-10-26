# HW4 Decision Log — Wildcat Capital data cleaning

Written **before** the cleaning code, from the raw audit (`reports/dq_summary_raw.csv`, `reports/profile_raw.csv`). Each entry is the instruction `scripts/02_clean.py` was built from. Entries marked **leave as is** are deliberate: the value looks odd but is either a legitimate structure, or cannot be corrected without inventing data.

Defect vs legitimate structure, in one line: a **defect** is a value that is wrong or will break a join or a calculation; a **legitimate structure** is a blank or odd-looking value that the business logic explains (an ETF has no sector; a cash deposit has no security).

---

## Defects that get fixed

### D01 — Near-duplicate clients
| Field | |
|---|---|
| **Table / column** | `dim_client` (whole row; `last_name`) |
| **Evidence** | 25 rows, client_id 2501–2525. Each one matches exactly one earlier client on first_name, age, city, zip_code, initial_aum (to the cent), client_since, advisor_id, state, risk_profile, tier, account type and is_active. The only difference is a mis-keyed `last_name`: usually the last letter is cut off (2501 "Taylo" = 674 "Taylor"), twice a letter is added (2512 "Leen" = 1193 "Lee", 2515 "Pacen" = 889 "Pace"). Business key (first_name, age, city, zip, initial_aum, client_since) is duplicated on 50 rows = 25 pairs. **0** fee, snapshot or transaction rows point at any of the 25 ids, while every one of the 25 originals has full history — so the facts, not the spelling, decide which row is the copy. |
| **Dimension violated** | Uniqueness |
| **Decision** | **Quarantine** the 25 truncated copies; keep the originals. |
| **Justification** | Same person loaded twice. Keeping both would count 2,525 clients instead of 2,500 and split nothing (no facts) but inflate client counts and "initial AUM" totals by the duplicates' $ value. Verified against the fact tables: no activity is lost. |
| **Risk** | If any were a genuinely different person, a real client is dropped from the dimension. Low: 11+ columns match exactly and none have activity. Rows stay in the quarantine file with the matching original id. |

### D02 — State written as full name
| Field | |
|---|---|
| **Table / column** | `dim_client.state` |
| **Evidence** | 78 of 2,525 values are full names instead of USPS codes: Pennsylvania 25, Florida 15, New York 14, New Jersey 13, California 5, Illinois 4, Texas 2. All other 2,447 are 2-letter codes. |
| **Dimension violated** | Consistency, Validity |
| **Decision** | **Standardize** to the 2-letter code with a fixed lookup (Pennsylvania → PA, …). |
| **Justification** | A map or slicer by state would show "PA" and "Pennsylvania" as two states and understate Pennsylvania (our largest state) by 25 clients. |
| **Risk** | Essentially none — the mapping is one-to-one. Assert: after the fix every value is a valid code. |

### D03 — return_ytd stored as percent text
| Field | |
|---|---|
| **Table / column** | `fact_portfolio_snapshot.return_ytd` |
| **Evidence** | 300 values are strings like `9.28%` while the other 129,247 are decimals (`0.019504`). They fail to parse as numbers, and the alpha rule (alpha = return − benchmark) fails on exactly these 300 rows. Example: snapshot 42, `9.28%`, benchmark 0.08279 + alpha 0.009966 = 0.092756. |
| **Dimension violated** | Validity, Consistency |
| **Decision** | **Convert** to a decimal. Use `benchmark_return_ytd + active_alpha_ytd` (full precision, rounded to 6 dp) **after verifying** it agrees with the percent text ÷ 100 within 0.00005 for every one of the 300 rows. |
| **Justification** | Default parsing would turn these into NaN (dropping 300 months from any return average) or, if the % is stripped without dividing, into returns 100× too large. Reconciling against two other columns proves the meaning instead of assuming it. |
| **Risk** | If a row fails the reconciliation, the script stops (assert) — nothing is guessed. |

### D04 — security_id stored as decimal text
| Field | |
|---|---|
| **Table / column** | `fact_transactions.security_id` |
| **Evidence** | All 197,175 non-blank values look like `45.0`; `dim_security.security_id` is `45`. Text-key match rate = 0%; numeric match = 100%. |
| **Dimension violated** | Validity, Referential Integrity |
| **Decision** | **Convert** to whole-number text (`45.0` → `45`). |
| **Justification** | The FK is an integer that went through a float somewhere upstream. As text it joins to nothing, so every trade would lose its security, asset class and benchmark in Power BI. |
| **Risk** | None if every value ends in `.0` — asserted before the change (no `45.5`-style values) and after (every key exists in `dim_security`). |

### D05 — Buy transactions with negative shares
| Field | |
|---|---|
| **Table / column** | `fact_transactions.shares` |
| **Evidence** | 836 rows, all `txn_type = Buy`, have negative shares (e.g. txn 272: −261.9719 × 441.71) while `amount` is positive (115,715.61). For all 836, amount = |shares| × price to the cent. Sells and Dividends are all positive. |
| **Dimension violated** | Validity, Consistency |
| **Decision** | **Convert** shares to the absolute value. |
| **Justification** | Direction lives in `txn_type` (every other Buy/Sell is positive). A negative Buy would cancel out $52.0M of purchases in any share or position sum. The amount column independently confirms the magnitude. |
| **Risk** | If the sign meant "this Buy was really a Sell", fixing the sign keeps the wrong type. Not supported: amount and type agree, and only the sign is off. |

### D06 — Transactions for clients that do not exist
| Field | |
|---|---|
| **Table / column** | `fact_transactions.client_id` → `dim_client.client_id` |
| **Evidence** | 200 rows (txn_id 298,573–298,772, the last 200 rows of the file) carry 200 different client_ids from 2,702 to 3,192. `dim_client` stops at 2,525. Total amount $10,888,495.37 (0.07% of $16.16B). |
| **Dimension violated** | Referential Integrity |
| **Decision** | **Quarantine.** |
| **Justification** | There is no client to attach them to, and no column that could recover the right id (advisor alone is not unique). Keeping them would create a blank "unknown client" bucket in every client report. |
| **Risk** | $10.9M of activity is excluded from client-level reports. Rows kept whole in `quarantine_fact_transactions_orphan_client.csv` so the source system owner can supply the missing clients. |

### D07 — Raw file name
| Field | |
|---|---|
| **Table / column** | `fact_transactions(2).csv` |
| **Evidence** | The extract arrived as `fact_transactions(2).csv` (a browser re-download name); the data dictionary calls it `fact_transactions.csv`. |
| **Dimension violated** | Consistency (naming) |
| **Decision** | **Standardize**: the script accepts either name, writes the clean file as `fact_transactions.csv`. Raw file not renamed. |
| **Justification** | Assignment 5 and any Power BI query expect the documented name. |
| **Risk** | None. |

---

## Suspicious but not correctable → flag (0/1 column), keep the row

### D08 — Missing risk profile
| Field | |
|---|---|
| **Table / column** | `dim_client.risk_profile` |
| **Evidence** | 76 blanks (75 after D01). All 3,942 snapshot rows for those 75 clients use benchmark 3 (60/40 Blend), which is also the benchmark every "Balanced" client gets. |
| **Dimension violated** | Completeness |
| **Decision** | **Flag** (`flag_risk_profile_missing` = 1); leave the value blank. |
| **Justification** | Filling "Balanced" is tempting, but the 60/40 blend is also the obvious default a system would assign when the profile is unknown. A risk profile is a suitability record — we must not invent one. Benchmark evidence is noted for the compliance team. |
| **Risk** | If they really are Balanced, the "Balanced" segment is understated by 75 clients (3%) and an "(blank)" group shows in reports. That is visible and honest; a wrong fill would not be. |

### D09 — Implausible year-to-date returns
| Field | |
|---|---|
| **Table / column** | `fact_portfolio_snapshot.return_ytd` (and `active_alpha_ytd`) |
| **Evidence** | 976 rows / 144 clients have |return_ytd| > 100% (max 9,466.8%); 977 after D03, because one of the 300 percent strings was `1170.15%`. They are internally consistent: alpha = return − benchmark holds, and they follow AUM jumps on small accounts (client 29: AUM 9,104.59 → 52,089.80, return −32% → +287%). |
| **Dimension violated** | Accuracy / Plausibility |
| **Decision** | **Flag** (`flag_return_implausible`); leave values. |
| **Justification** | The return seems to be computed from AUM change, which includes deposits, so it is not a true investment return. We cannot recompute it without cash-flow-adjusted data. Flag lets the committee exclude them from average-return KPIs. |
| **Risk** | If not filtered, average return and alpha by advisor are badly distorted (mean return_ytd 11.4% vs median 3.2%). |

### D10 — AUM stuck at 1,000.00
| Field | |
|---|---|
| **Table / column** | `fact_portfolio_snapshot.aum` (also `fact_fees.aum_basis`) |
| **Evidence** | 420 snapshot rows / 92 clients have AUM exactly 1,000.00 (386 fee rows use the same basis). This is the column minimum; values around it are not near 1,000 (client 29: 16,704.59 → 1,000.00 → 1,013.46). It looks like a floor applied by the source system. |
| **Dimension violated** | Accuracy / Plausibility |
| **Decision** | **Flag** (`flag_aum_at_floor`); leave values. |
| **Justification** | The true value is unknown; replacing it would invent data. The effect on total AUM is tiny ($420K of ~$567B across all snapshots), but the flag explains odd fee and return figures. |
| **Risk** | Low. |

### D11 — Activity after an account was closed
| Field | |
|---|---|
| **Table / column** | `fact_transactions.txn_date` vs `dim_client.is_active` and last snapshot |
| **Evidence** | 2,410 transactions for 131 inactive clients are dated after that client's last snapshot month. Snapshots end exactly when a client becomes inactive (175 inactive clients, all with last snapshot before Dec-2024; all 2,325 active ones run to Dec-2024). |
| **Dimension violated** | Accuracy / Plausibility (cross-table) |
| **Decision** | **Flag** (`flag_after_account_close`); keep. |
| **Justification** | Could be legitimate wind-down activity (final sales, late dividends) or wrong dates. We can't tell which, so we keep them visible. |
| **Risk** | If they are errors, flows and trading volume are overstated slightly (0.8% of rows). |

---

## Checked and left as is (legitimate structure or not fixable)

| # | Table / column | Evidence | Dimension | Decision | Justification | Risk |
|---|---|---|---|---|---|---|
| D12 | `dim_security.sector` / `expense_ratio_bps` | sector blank on 219 rows = exactly the 219 ETFs; expense ratio blank on 281 rows = exactly the 281 single stocks | Completeness (looks like) | **Leave as is** | Structural: funds have no sector, stocks have no expense ratio. Filling would be invented. | None; BI must allow blanks. |
| D13 | `fact_transactions.security_id / shares / price` | blank on 101,597 rows = exactly the Deposit, Withdrawal and Advisory Fee rows; never blank on Buy/Sell/Dividend | Completeness (looks like) | **Leave as is** | Cash movements have no security. | None. |
| D14 | `dim_advisor.certifications` | 6 advisors have the text `None` | Validity (looks like) | **Leave as is** | Means "no certification", a real answer. Read as text so it is not turned into a null. | A BI tool reading defaults could blank it; noted in README_clean. |
| D15 | `dim_client.zip_code` | 232 zips start with 0 (e.g. 03897) | Validity | **Leave as is** (text) | Real New England/NJ zips. Default parsing would drop the zero. | Must be typed as Text in Power BI. |
| D16 | `dim_security.name` | 3 names appear twice ("Jones Inc Fund") with different tickers and benchmarks | Uniqueness (looks like) | **Leave as is** | Different securities from the same issuer; ticker is unique (500/500). | None. |
| D17 | `return_ytd`, `active_alpha_ytd` | 135 and 756 values in scientific notation (`-1.9e-05`) | Consistency | **Leave as is** | Valid numbers; every parser reads them. Changing text format adds no value. | None. |
| D18 | Fees/snapshots before `client_since` | 858 fee rows and 930 snapshot rows dated before client_since — **all** in the client's onboarding month (records are dated the 1st) | Plausibility | **Leave as is** | Month-start convention, not an error. | None. |
| D19 | Snapshot months with no fee | 7,350 of 129,547 snapshots have no fee row | Completeness | **Leave as is** | Fees can be waived or billed differently; every fee row *does* have a snapshot, and fee aum_basis = snapshot aum on 100% of rows. Creating fees would invent revenue. | Fee revenue per AUM is slightly lower in those months — correct as recorded. |
| D20 | Trades on non-trading days | 56,146 of 197,175 Buy/Sell/Dividend rows (28.5%) fall on a Saturday/Sunday per `dim_date.is_trading_day` | Plausibility | **Leave as is** (documented) | Spread evenly over all years and types, so it is a property of the source extract (likely trade vs. booking date), not a few bad rows. Moving dates would invent data. | Daily trading charts show weekend volume; use monthly grain. |
| D21 | Advisory Fee transactions vs `fact_fees` | Client totals differ by >5% for 2,340 of 2,500 real clients (raw audit: 2,364 of 2,524, because the 24 fake client ids from D06 have fee debits but no fees) | Consistency | **Leave as is** | Two different processes: cash debits vs. monthly fee accruals. `fact_fees` is the source of truth for revenue (it recomputes exactly). | Someone summing both would double-count fees; noted in README_clean. |
| D22 | `dim_client.initial_aum` vs first snapshot | 40 clients differ by >25% | Consistency | **Leave as is** | initial_aum is at client_since (as early as 2015); the first snapshot is Jan-2020 or later. | None. |
| D23 | `dim_benchmark` id 6 | MSCI Emerging Markets is not used by any security or snapshot | Referential (unused member) | **Leave as is** | A valid reference row. | None. |
| D24 | `dim_date` | All 1,827 rows: year, quarter, month, names, flags agree with the date; no gaps; `is_trading_day` = weekdays only (no holidays) | — | **Leave as is** | Clean. Holiday calendar missing is a known limitation. | Holiday trades not detectable. |
| D25 | `fact_transactions` Dividend rows | All 53,864 Dividend rows have shares and price, and amount = shares × price — i.e. the dividend equals the full market value of the position | Plausibility | **Leave as is** (documented) | Internally consistent and no source for the real dividend rate; changing it would invent income. | Dividend income is likely overstated if summed; noted as a limitation. |
| D26 | `fact_fees` | amount = aum_basis × bps ÷ 10,000 ÷ 12 on 122,197/122,197 rows; advisor matches client on 100%; no duplicates | — | **Leave as is** | Verified clean. | None. |

## Order of cleaning steps (and why)
1. **Load as text, accept the renamed file (D07).**
2. **Type/format repairs first (D04, D02, D03, D05)** — keys and numbers must be in one format before any join or duplicate check, otherwise `45.0` vs `45` looks like an orphan.
3. **Dimension de-duplication (D01)** — the client list must be final before checking fact foreign keys against it. Asserted that no fact row uses a quarantined id.
4. **Fact RI quarantine (D06)** — orphans are measured against the final dimension.
5. **Flags last (D08–D11)** — computed on the final data so they describe what Power BI will see.
