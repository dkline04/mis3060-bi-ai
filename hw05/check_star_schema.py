"""
HW5 - Wildcat Capital star schema checks (Parts A, B and E).

Proves, in code:
  1. Every primary key is unique and never blank.
  2. Every foreign key matches a row in the table it points to (no orphans).
  3. The grain of each fact table (the columns that make one row unique).
  4. The specific claims made in star_design.md.

Run from the hw05 folder:   python check_star_schema.py
Exit code is 0 when every check passes and 1 if any check fails.
"""

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent


def load(name, **kwargs):
    """Read one of the eight clean CSVs from the hw05 folder."""
    return pd.read_csv(HERE / f"{name}.csv", **kwargs)


tables = {
    "dim_advisor": load("dim_advisor"),
    "dim_benchmark": load("dim_benchmark"),
    "dim_client": load("dim_client", dtype={"zip_code": str}),  # keep leading zeros
    "dim_date": load("dim_date"),
    "dim_security": load("dim_security"),
    "fact_fees": load("fact_fees"),
    "fact_portfolio_snapshot": load("fact_portfolio_snapshot"),
    "fact_transactions": load("fact_transactions"),
}

failures = 0


def report(ok, msg):
    """Print PASS/FAIL and count failures."""
    global failures
    print(("PASS  " if ok else "FAIL  ") + msg)
    if not ok:
        failures += 1


# Make the date columns real dates so fact dates can be matched to dim_date[date].
# errors="coerce" turns an unparseable date into a blank, which is then reported
# as a failure below instead of crashing the script.
date_columns = [("dim_date", "date"), ("fact_fees", "fee_date"),
                ("fact_portfolio_snapshot", "snapshot_date"), ("fact_transactions", "txn_date")]
for t, col in date_columns:
    tables[t][col] = pd.to_datetime(tables[t][col], errors="coerce")

print("\n=== Dates parse correctly ===")
for t, col in date_columns:
    bad = int(tables[t][col].isna().sum())
    report(bad == 0, f"{t}[{col}]: every value is a valid date ({bad} unreadable)")

# ---------------------------------------------------------------- row counts
print("\n=== Row counts (should match the handout) ===")
expected = {"dim_advisor": 25, "dim_benchmark": 8, "dim_client": 2500, "dim_date": 1827,
            "dim_security": 500, "fact_fees": 122197, "fact_portfolio_snapshot": 129547,
            "fact_transactions": 298572}
for t, n in expected.items():
    report(len(tables[t]) == n, f"{t}: {len(tables[t]):,} rows (expected {n:,})")

# ---------------------------------------------------------------- primary keys
print("\n=== Part A: primary keys are unique and not blank ===")
primary_keys = {
    "dim_advisor": "advisor_id", "dim_benchmark": "benchmark_id", "dim_client": "client_id",
    "dim_date": "date_id", "dim_security": "security_id", "fact_fees": "fee_id",
    "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id",
}
for t, pk in primary_keys.items():
    col = tables[t][pk]
    report(col.notna().all() and col.is_unique, f"{t}[{pk}] unique and never blank")

# dim_date is joined on [date], so [date] must be unique too
report(tables["dim_date"]["date"].is_unique, "dim_date[date] unique (the column facts join on)")

# ---------------------------------------------------------------- foreign keys
print("\n=== Part A: foreign keys match their target (no orphans) ===")
foreign_keys = [
    # (table, column, target table, target column, blanks allowed?)
    ("dim_client", "advisor_id", "dim_advisor", "advisor_id", False),
    ("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id", False),
    ("fact_fees", "client_id", "dim_client", "client_id", False),
    ("fact_fees", "advisor_id", "dim_advisor", "advisor_id", False),
    ("fact_fees", "fee_date", "dim_date", "date", False),
    ("fact_portfolio_snapshot", "client_id", "dim_client", "client_id", False),
    ("fact_portfolio_snapshot", "advisor_id", "dim_advisor", "advisor_id", False),
    ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark", "benchmark_id", False),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date", False),
    ("fact_transactions", "client_id", "dim_client", "client_id", False),
    ("fact_transactions", "advisor_id", "dim_advisor", "advisor_id", False),
    # security_id is read as a decimal (45.0) because it has blanks, while
    # dim_security[security_id] is a whole number (45). isin() still matches them.
    ("fact_transactions", "security_id", "dim_security", "security_id", True),
    ("fact_transactions", "txn_date", "dim_date", "date", False),
]
for t, col, target, tcol, blanks_ok in foreign_keys:
    values = tables[t][col]
    blanks = int(values.isna().sum())
    orphans = int((~values.dropna().isin(tables[target][tcol])).sum())
    bad_blanks = 0 if blanks_ok else blanks
    note = f", {blanks:,} blank (allowed)" if blanks_ok and blanks else ""
    report(orphans == 0 and bad_blanks == 0,
           f"{t}[{col}] -> {target}[{tcol}]: {orphans} orphans, {bad_blanks} bad blanks{note}")

# Blank security_id is only allowed on cash rows (Part A note and Part E(a))
txn = tables["fact_transactions"]
security_types = ["Buy", "Sell", "Dividend"]
bad = int((txn["security_id"].isna() & txn["txn_type"].isin(security_types)).sum())
report(bad == 0, f"Buy/Sell/Dividend rows always have a security_id ({bad} blank)")
cash = txn[txn["security_id"].isna()]["txn_type"].value_counts()
print("      Transaction types with a blank security_id: "
      + ", ".join(f"{k} {v:,}" for k, v in cash.items()))

# ---------------------------------------------------------------- grain
print("\n=== Part B: grain checks ===")
grains = {
    "fact_portfolio_snapshot": ["client_id", "snapshot_date"],  # one row per client per month
    "fact_fees": ["client_id", "fee_date"],                     # one fee per client per month
}
for t, cols in grains.items():
    blanks = int(tables[t][cols].isna().any(axis=1).sum())      # duplicated() treats blank = blank
    dupes = int(tables[t].duplicated(subset=cols).sum())
    report(dupes == 0 and blanks == 0,
           f"{t}: one row per {' + '.join(cols)} ({dupes} duplicates, {blanks} blank keys)")

# fact_transactions: grain = one transaction, which is the same as its primary key.
# Extra check: no two rows are identical apart from txn_id (no double-loaded transactions).
other_cols = [c for c in txn.columns if c != "txn_id"]
dupes = int(txn.duplicated(subset=other_cols).sum())
report(dupes == 0, f"fact_transactions: grain = one transaction (txn_id); "
                   f"{dupes} rows identical apart from txn_id")

# Monthly facts are always dated the 1st of the month
for t, col in [("fact_fees", "fee_date"), ("fact_portfolio_snapshot", "snapshot_date")]:
    off = int((tables[t][col].dt.day != 1).sum())
    report(off == 0, f"{t}[{col}] always the 1st of the month ({off} not)")

# ---------------------------------------------------------------- advisor paths (Part E(b))
print("\n=== Part E(b): advisor on each fact row matches the client's advisor ===")
client_adv = tables["dim_client"].set_index("client_id")["advisor_id"]
for t in ["fact_fees", "fact_portfolio_snapshot", "fact_transactions"]:
    f = tables[t]
    differ = int((f["advisor_id"] != f["client_id"].map(client_adv)).sum())
    report(differ == 0, f"{t}: {differ:,} of {len(f):,} rows have a different advisor than dim_client")

print(f"\n{'ALL CHECKS PASSED' if failures == 0 else str(failures) + ' CHECK(S) FAILED'}")
sys.exit(1 if failures else 0)
