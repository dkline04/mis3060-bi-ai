"""
HW6 Part B - reconcile every Power BI measure to an independent pandas calculation.

1. Recomputes each measure in pandas straight from the Wildcat Capital Clean CSVs
   (nothing is read from Power BI for this step). Writes reports/pandas_values.csv.
2. Reads the Power BI numbers from reports/powerbi_values.csv (measure, slice, value),
   exported from DAX query view with powerbi/powerbi_values_export.dax.
3. Writes reports/measure_reconciliation.csv:
   measure, slice, powerbi_value, pandas_value, abs_diff, match
   Tolerance: 0.01 for currency, 0.0001 for ratios (the assignment's limits) plus a relative
   check of 1e-6 for ratios; counts must match exactly. Only the rows in ALLOWED_BLANK may be
   blank. Extra or duplicate Power BI rows are reported as problems.

Note: the pandas side follows the same business definitions as the DAX, so "all match" means
the two tools agree - not that every definition is the best one (e.g. Organic Growth at the
grand total divides 5 years of flows by Dec 2023 AUM; Net Flows counts every Deposit and
Withdrawal row).

Run from the hw06 folder:   python scripts/01_reconcile_measures.py
Exit code is 0 when every row matches and there are no problems, 1 otherwise.
"""

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HW06 = Path(__file__).resolve().parents[1]
DATA = HW06.parent / "hw05"            # the eight Wildcat Capital Clean CSVs live in hw05/
REPORTS = HW06 / "reports"

# ------------------------------------------------------------------ load the clean CSVs
snap = pd.read_csv(DATA / "fact_portfolio_snapshot.csv", parse_dates=["snapshot_date"])
fees = pd.read_csv(DATA / "fact_fees.csv", parse_dates=["fee_date"])
txn = pd.read_csv(DATA / "fact_transactions.csv", parse_dates=["txn_date"])
client = pd.read_csv(DATA / "dim_client.csv", dtype={"zip_code": str})

# Bring client_tier onto each fact (same as the fact -> dim_client relationship in Power BI)
tier = client.set_index("client_id")["client_tier"]
for df in (snap, fees, txn):
    df["client_tier"] = df["client_id"].map(tier)

# A "slice" below is the set of calendar days in the filter, written as (first_day, last_day),
# plus an optional group filter: a client tier ("HNW") or an advisor (("advisor", 7)).
# The date range comes from dim_date (Claude Code review #4), not hard-coded.
dim_date = pd.read_csv(DATA / "dim_date.csv", parse_dates=["date"])
DATE_MIN, DATE_MAX = dim_date["date"].min(), dim_date["date"].max()
TIERS = sorted(client["client_tier"].dropna().unique())          # from dim_client, not hard-coded


def in_slice(df, col, start, end, grp=None):
    m = (df[col] >= start) & (df[col] <= end)
    if isinstance(grp, tuple):                  # ("advisor", id)
        m &= df["advisor_id"] == grp[1]
    elif grp is not None:                       # client tier
        m &= df["client_tier"] == grp
    return df[m]


def shift(start, end, years=0, months=0):
    """Shift a date window back like SAMEPERIODLASTYEAR / DATEADD and clip to the date table."""
    off = pd.DateOffset(years=years, months=months)
    s, e = start - off, end - off
    if e < DATE_MIN:
        return None
    return max(s, DATE_MIN), min(e, DATE_MAX)


# ------------------------------------------------------------------ measure definitions
def naive_sum(start, end, t=None):
    return in_slice(snap, "snapshot_date", start, end, t)["aum"].sum()


def last_rows(start, end, t=None):
    """Rows at the last snapshot date that has data in the slice (LASTNONBLANK)."""
    rows = in_slice(snap, "snapshot_date", start, end, t)
    if rows.empty:
        return rows
    return rows[rows["snapshot_date"] == rows["snapshot_date"].max()]


def ending_aum(start, end, t=None):
    r = last_rows(start, end, t)
    return r["aum"].sum() if not r.empty else np.nan


def ending_clients(start, end, t=None):
    r = last_rows(start, end, t)
    return r["client_id"].nunique() if not r.empty else np.nan


def avg_aum_per_client(start, end, t=None):
    return ending_aum(start, end, t) / ending_clients(start, end, t)


def ending_aum_ly(start, end, t=None):
    w = shift(start, end, years=1)
    return ending_aum(*w, t) if w else np.nan


def aum_yoy(start, end, t=None):
    ly = ending_aum_ly(start, end, t)
    return (ending_aum(start, end, t) - ly) / ly


def ending_aum_pm(start, end, t=None):
    w = shift(start, end, months=1)
    return ending_aum(*w, t) if w else np.nan


def aum_mom(start, end, t=None):
    pm = ending_aum_pm(start, end, t)
    return (ending_aum(start, end, t) - pm) / pm


def avg_monthly_aum(start, end, t=None):
    r = in_slice(snap, "snapshot_date", start, end, t)
    return r["aum"].sum() / r["snapshot_date"].nunique()


def total_fees(start, end, t=None):
    return in_slice(fees, "fee_date", start, end, t)["amount"].sum()


def net_flows(start, end, t=None):
    r = in_slice(txn, "txn_date", start, end, t)
    return (r.loc[r["txn_type"] == "Deposit", "amount"].sum()
            - r.loc[r["txn_type"] == "Withdrawal", "amount"].sum())


def fee_yield_bps(start, end, t=None):
    return total_fees(start, end, t) * 12 * 10_000 / naive_sum(start, end, t)


def organic_growth(start, end, t=None):
    return net_flows(start, end, t) / ending_aum_ly(start, end, t)


def weighted_alpha(start, end, t=None):
    r = last_rows(start, end, t)
    r = r[r["is_return_suspect"] == 0]
    return (r["active_alpha_ytd"] * r["aum"]).sum() / r["aum"].sum()


def alpha_signal(start, end, t=None):
    a = weighted_alpha(start, end, t)
    if pd.isna(a):
        return ""
    return "Outperforming" if a >= 0.02 else "Lagging" if a <= -0.02 else "In line"


def top10_share(start, end, t=None):
    r = last_rows(start, end, t)
    by_client = r.groupby("client_id")["aum"].sum()
    return by_client.nlargest(10).sum() / by_client.sum()


MEASURES = {
    "AUM (naive SUM)": (naive_sum, "currency"),
    "Ending AUM": (ending_aum, "currency"),
    "Ending Clients": (ending_clients, "count"),
    "Avg AUM per Client": (avg_aum_per_client, "currency"),
    "Ending AUM LY": (ending_aum_ly, "currency"),
    "AUM YoY %": (aum_yoy, "ratio"),
    "Ending AUM PM": (ending_aum_pm, "currency"),
    "AUM MoM %": (aum_mom, "ratio"),
    "Avg Monthly AUM": (avg_monthly_aum, "currency"),
    "Total Fees": (total_fees, "currency"),
    "Net Flows": (net_flows, "currency"),
    "Fee Yield (bps)": (fee_yield_bps, "ratio"),
    "Organic Growth Rate": (organic_growth, "ratio"),
    "AUM-Weighted Alpha": (weighted_alpha, "ratio"),
    "Alpha Signal": (alpha_signal, "text"),
    "Top 10 Client Share": (top10_share, "ratio"),
}

# ------------------------------------------------------------------ slices required by Part B
def build_slices():
    ALL = (DATE_MIN, DATE_MAX)
    Y = lambda y: (pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y}-12-31"))
    M = lambda y, mo: (pd.Timestamp(y, mo, 1), pd.Timestamp(y, mo, 1) + pd.offsets.MonthEnd(0))
    out = []                                   # (measure, slice label, start, end, group)
    for m in MEASURES:                         # every measure at the grand total
        out.append((m, "Total", *ALL, None))
    by_year = ["AUM (naive SUM)", "Ending AUM", "Ending AUM LY", "AUM YoY %", "Avg Monthly AUM",
               "Fee Yield (bps)", "Organic Growth Rate", "AUM-Weighted Alpha", "Alpha Signal",
               # extra by-year coverage (review #8)
               "Ending Clients", "Avg AUM per Client", "Total Fees", "Net Flows",
               "Top 10 Client Share"]
    for y in range(DATE_MIN.year, DATE_MAX.year + 1):
        for m in by_year:
            out.append((m, f"Year {y}", *Y(y), None))
    by_tier = ["Ending AUM", "Avg AUM per Client", "Ending AUM LY", "AUM YoY %", "Fee Yield (bps)",
               "Organic Growth Rate", "AUM-Weighted Alpha", "Alpha Signal", "Top 10 Client Share"]
    for tr in TIERS:
        for m in by_tier:
            out.append((m, f"2024 {tr}", *Y(2024), tr))
    # measure 5 by month: Dec 2024 (required), Mar 2024 (PM = Feb, a short month) and
    # Jan 2020 (no prior month, so PM and MoM must be blank) - review #6
    for lbl, (y, mo) in {"Dec 2024": (2024, 12), "Mar 2024": (2024, 3), "Jan 2020": (2020, 1)}.items():
        for m in ["Ending AUM", "Ending AUM PM", "AUM MoM %"]:
            out.append((m, lbl, *M(y, mo), None))
    # Top 10 by advisor in 2023: the slice that broke Claude's first draft (review #7)
    snap23 = snap[snap["snapshot_date"].dt.year == 2023]
    for a in sorted(snap23["advisor_id"].unique()):
        for m in ["Ending AUM", "Top 10 Client Share"]:
            out.append((m, f"2023 Advisor {a}", *Y(2023), ("advisor", a)))
    return out


# Rows that are allowed to be blank in both tools (review #2). Any other blank is a failure.
ALLOWED_BLANK = {
    ("Ending AUM LY", "Year 2020"), ("AUM YoY %", "Year 2020"),
    ("Organic Growth Rate", "Year 2020"),
    ("Ending AUM PM", "Jan 2020"), ("AUM MoM %", "Jan 2020"),
}


def build_pandas():
    rows = []
    for m, label, start, end, grp in build_slices():
        fn, kind = MEASURES[m]
        rows.append({"measure": m, "slice": label, "pandas_value": fn(start, end, grp), "kind": kind})
    return pd.DataFrame(rows)


def values_match(pv, qv, kind):
    """Assignment tolerance (0.01 currency, 0.0001 ratio) PLUS a relative check, so a small
    ratio such as 0.001 can't pass while being 10% off (review #1)."""
    diff = abs(pv - qv)
    if kind == "count":
        return diff, diff == 0
    if kind == "currency":
        return diff, diff <= 0.01
    return diff, diff <= 0.0001 and math.isclose(pv, qv, rel_tol=1e-6, abs_tol=1e-12)


# ------------------------------------------------------------------ compare with Power BI
def main():
    pandas_df = build_pandas()
    REPORTS.mkdir(exist_ok=True)
    # always written, so it never goes stale (review #9)
    pandas_df.drop(columns="kind").to_csv(REPORTS / "pandas_values.csv", index=False)

    pbi_path = REPORTS / "powerbi_values.csv"
    if not pbi_path.exists():
        print(f"No {pbi_path.name} yet - wrote pandas_values.csv only ({len(pandas_df)} rows).")
        return 1

    pbi = pd.read_csv(pbi_path, keep_default_na=False).rename(columns={"value": "powerbi_value"})

    # structure checks (review #3): duplicates, and rows only one side has
    problems = []
    dups = pbi[pbi.duplicated(["measure", "slice"], keep=False)]
    if not dups.empty:
        problems.append(f"{len(dups)} duplicate (measure, slice) rows in {pbi_path.name}")
    merged = pandas_df.merge(pbi, on=["measure", "slice"], how="outer", indicator=True)
    extra = merged[merged["_merge"] == "right_only"]
    if not extra.empty:
        problems.append(f"{len(extra)} rows in {pbi_path.name} that the script does not compute: "
                        + ", ".join(extra["measure"] + " / " + extra["slice"]))

    out = []
    for _, r in merged[merged["_merge"] != "right_only"].iterrows():
        pv, qv, kind = r["powerbi_value"], r["pandas_value"], r["kind"]
        key = (r["measure"], r["slice"])
        if r["_merge"] == "left_only":           # missing from Power BI export
            out.append([*key, "", qv, "", False])
            continue
        if kind == "text":
            ok = str(pv) == str(qv) and (pv != "" or key in ALLOWED_BLANK)
            out.append([*key, pv, qv, "", ok])
            continue
        p_blank = str(pv).strip() == ""
        q_blank = pd.isna(qv)
        if p_blank or q_blank:
            ok = p_blank and q_blank and key in ALLOWED_BLANK
            out.append([*key, pv, "" if q_blank else qv, "", ok])
            continue
        diff, ok = values_match(float(pv), float(qv), kind)
        out.append([*key, float(pv), qv, diff, ok])

    rec = pd.DataFrame(out, columns=["measure", "slice", "powerbi_value", "pandas_value",
                                     "abs_diff", "match"])
    rec.to_csv(REPORTS / "measure_reconciliation.csv", index=False)
    n_bad = int((~rec["match"]).sum())
    print(f"{len(rec)} rows compared, {len(rec) - n_bad} match, {n_bad} do not.")
    if n_bad:
        print(rec[~rec["match"]].to_string(index=False))
    for p_ in problems:
        print("PROBLEM:", p_)
    return 1 if (n_bad or problems) else 0


if __name__ == "__main__":
    sys.exit(main())
