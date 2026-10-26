# HW4 — Cleaning the Wildcat Capital Data
MIS3060 Business Intelligence with AI · Villanova University

Audit, clean and validate the eight-table Wildcat Capital warehouse extract. Raw files are never modified; the result is a clean copy of all eight tables plus a full audit trail.

## Folder structure
```
hw04/
├── README.md                     this file
├── decision_log.md               Part B: one entry per issue (written before the cleaning code)
├── *.csv                         the 8 raw files, as received (fact_transactions arrived as "fact_transactions(2).csv")
├── scripts/
│   ├── wildcat_config.py         shared settings: paths, keys, types, allowed values, relationships, rules
│   ├── 01_profile.py             Part A: generic profiler + 4 groups of DQ checks
│   ├── 02_clean.py               Part C: step-by-step cleaning with asserts, quarantine, audit trail
│   └── 03_validate.py            Part D: reusable RI function, rules, reconciliations, IQR, scorecard
├── data/
│   ├── clean/                    8 clean tables + README_clean.md
│   └── audit/                    cleaning_log.csv, value_changes.csv, quarantine_*.csv
└── reports/
    ├── profile_raw.csv           per-column profile (raw)
    ├── dq_summary_raw.csv        every check, tagged ERROR / WARN / INFO / PASS (raw)
    ├── profile_clean.csv, dq_summary_clean.csv   same audit re-run on the clean data
    ├── ri_results.csv            13 relationships, raw and clean
    ├── rule_results.csv          business-bound rules, raw and clean
    ├── reconciliations.csv       recomputed vs stored amounts, raw and clean
    ├── outliers_iqr.csv          IQR flags on unbounded numeric columns
    ├── data_quality_scorecard.csv
    └── cleaning_report.md        Part E: report for the portfolio committee
```

## How to run
Requires Python 3.10+ and pandas (`pip install pandas`). From the `hw04` folder:

```bash
python scripts/01_profile.py                 # Part A  -> reports/profile_raw.csv, dq_summary_raw.csv
python scripts/02_clean.py                   # Part C  -> data/clean/, data/audit/
python scripts/01_profile.py --stage clean   # optional: same audit on the clean files
python scripts/03_validate.py                # Part D  -> reports/*.csv incl. data_quality_scorecard.csv
```

`02_clean.py` stops with an `AssertionError` if any fix does not do what the decision log says, or if raw rows ≠ clean rows + quarantined rows for any table.

## Results at a glance
| Table | Raw rows | Clean rows | Quarantined |
|---|---:|---:|---:|
| dim_client | 2,525 | 2,500 | 25 (near-duplicates) |
| fact_transactions | 298,772 | 298,572 | 200 (unknown client) |
| all other 6 tables | unchanged | unchanged | 0 |

198,389 cell changes are logged in `data/audit/value_changes.csv` (security_id 197,175 · shares 836 · return_ytd 300 · state 78). Referential match is 100% on all 13 relationships after cleaning.

## Claude Code review findings
Each script was drafted with Claude, run in VS Code, and reviewed by Claude Code before committing.

| Script | What Claude Code flagged | What I did about it |
|---|---|---|
| `02_clean.py` | (1) Audit-log note for D06 said "200 distinct client_ids" using the row count, not the distinct count. (2) The D08 flag assert compared a value with itself, and D10/D11 had no assert at all; nothing checked the flag column actually written. (3) The note "all their snapshots use benchmark 3" was never checked. (4) D06 did not assert the row count right after quarantining. (5) Hard-coded `pa_before + 25`, "Wrote 8 tables" and the file name in the D07 log. (6) `rstrip("%")` and `lstrip("-")` ran on unstripped text. (7) The security_id guard crashed if any value was already `45`; the D05 guard crashed if there were no negative rows; `min(dups)` crashed with no duplicates. (8) A reused quarantine name would silently overwrite rows. (9) The after-write check compared only row counts, not cell values. (10) Thresholds were hard-coded in two places. | Fixed all ten. The D06 note now uses the distinct count. A `check_flag()` helper asserts each written flag column is only 0/1 and matches its condition. Added asserts for the benchmark-3 claim, the D06 row count, a quarantine name used twice, no AUM below the floor, and no inactive client without snapshots. State matching ignores case/spaces and the PA count is computed. Text is stripped before parsing. Guards accept clean input. The file on disk is compared cell-for-cell with what was cleaned. Thresholds moved to `wildcat_config.py`. Re-ran: same results (2,500 clients, 298,572 transactions, 198,389 changes). **Not changed:** old quarantine files are not auto-deleted, because the script must never delete files. |
| `01_profile.py` | (1) The "blank by design" note counted rows where a value is not required, not rows actually blank. (2) A comment described a check with no code. (3) Blank dates counted as "before client_since" (text compare). (4) `set_index("date")` would crash if dim_date had duplicate dates. (5) The fee-debit vs fee-accrual check dropped clients missing on one side, and compared against all fee types without saying so. (6) Date min/max used text order. | Fixed all six. Blank dates are excluded and real dates are compared. Dates are de-duplicated before lookup. The fee check now fills missing sides with 0 and its note says it compares all fee types on purpose. Result: raw count went from 2,340 to 2,364 of 2,524, because the 24 fake client ids from the bad transactions are now included; clean stays 2,340 of 2,500. Decision log D21 updated. **Not changed:** the pair count assumes pairs of two, which `02_clean.py` asserts. |
| `03_validate.py` | (1) The fee-vs-snapshot lookup had no `drop_duplicates` and could crash. (2) `non_null_fk_rows` was rebuilt from a rounded rate. (3) Possible 0/0 when every FK is blank. (4) `pct_referential_match` mixed numbers and text. (5) IQR on transaction amount mixes all types. (6) "13 relationships" hard-coded. | Fixed all six. The RI function now also returns `n_nonnull`. The 0/0 case is guarded. The column holds numbers only, with a new `referential_note` column. The IQR note says the amounts mix types. The relationship count comes from the config. **Not changed:** the RI function signature, so it can be reused in Assignment 5. |
| `wildcat_config.py` | (1) `_applies` could mis-align pass/fail on a filtered table. (2) The floor rule (`aum > 1000`) and floor flag (`aum == 1000`) used different tests. (3) Benchmark returns compared as text. (4) Half-cent tolerance on a float boundary. (5) "inf" text parsed as a number. (6) No BOM-safe encoding. (7) If both transaction file names exist, one was picked silently. (8) A typo in `stage` silently read the clean files. Also: alpha rule double-counts unparseable returns, fee formula applied to all fee types, certification order, `is_trading_day` ignores holidays. | Fixed 1–8: index-safe `_applies`, same `!= 1000` test for rule and flag, numeric compare, 0.0051 tolerance, finite-only numbers, `utf-8-sig`, an error if both files exist, and an error on an unknown stage. **Left as is, on purpose:** a `9.28%` return really does break the alpha formula, so counting it there is correct. The fee formula matches 122,197 of 122,197 rows for all four fee types. Certifications only appear in one order in the data. dim_date has no holidays (documented as a limitation in README_clean). |

Issues found and fixed while first running the scripts (before the Claude Code review):
- `02_clean.py` first chose the duplicate client by the shorter last name. The asserts caught that this was wrong for 2 pairs ("Lee"/"Leen", "Pace"/"Pacen"), where the copy is the longer name. Changed to pick the copy as the row with no fact activity.
- The percent-return reconciliation tolerance was exactly at the rounding limit (0.00005), so a float rounding error made it fail. Added a 1e-9 allowance and a comment explaining why.
- The number-format check counted `1000.0` in decimal columns as a problem; restricted "integer-as-decimal" to integer columns, and made scientific notation INFO instead of ERROR.
