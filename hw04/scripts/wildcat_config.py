"""
wildcat_config.py
Shared settings for HW4 (MIS3060): file locations, table metadata, and the
data-quality rules used by 01_profile.py and 03_validate.py.

Keeping the rules here (instead of copy-pasting them in each script) means the
raw audit and the clean validation are measured with exactly the same ruler.

Every table is read as TEXT (dtype=str, keep_default_na=False) and converted
column by column on purpose.
"""
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent          # the hw04/ folder
CLEAN_DIR = ROOT / "data" / "clean"
AUDIT_DIR = ROOT / "data" / "audit"
REPORTS_DIR = ROOT / "reports"

TABLE_NAMES = [
    "dim_advisor", "dim_benchmark", "dim_client", "dim_date", "dim_security",
    "fact_fees", "fact_portfolio_snapshot", "fact_transactions",
]

# Some downloads rename a file (e.g. "fact_transactions(2).csv"). Accept both.
RAW_FILE_ALIASES = {"fact_transactions": ["fact_transactions.csv", "fact_transactions(2).csv"]}


def find_raw_dir() -> Path:
    """Raw files may sit in data/raw/, 'Wildcat Capital/', or the hw04 root."""
    for cand in [ROOT / "data" / "raw", ROOT / "Wildcat Capital", ROOT]:
        if (cand / "dim_client.csv").exists():
            return cand
    raise FileNotFoundError("Could not find the raw Wildcat Capital CSV files.")


def raw_path(name: str) -> Path:
    raw_dir = find_raw_dir()
    found = [raw_dir / f for f in RAW_FILE_ALIASES.get(name, [f"{name}.csv"]) if (raw_dir / f).exists()]
    if len(found) > 1:
        raise FileExistsError(f"More than one raw file for {name}: {[p.name for p in found]} - keep only one")
    if found:
        return found[0]
    raise FileNotFoundError(f"Raw file for {name} not found in {raw_dir}")


def read_csv_text(path) -> pd.DataFrame:
    """The assignment rule: read everything as text, nothing becomes NaN.
    utf-8-sig removes an invisible byte-order mark if a file has one."""
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def read_table(name: str, stage: str = "raw") -> pd.DataFrame:
    if stage not in ("raw", "clean"):
        raise ValueError(f"stage must be 'raw' or 'clean', not {stage!r}")
    path = raw_path(name) if stage == "raw" else CLEAN_DIR / f"{name}.csv"
    return read_csv_text(path)


# Thresholds shared by 02_clean.py and the rules below, so both use the same values
AMOUNT_TOL = 0.011             # $ tolerance when recomputing an amount rounded to cents
PCT_TEXT_TOL = 0.00005 + 1e-9  # '9.28%' has 2 dp of a percent -> off by at most 0.00005
ALPHA_TOL = 2e-6               # return - benchmark - alpha (values stored to 6 dp)
RETURN_PLAUSIBLE_MAX = 1.0     # |return_ytd| above 100% is flagged
AUM_FLOOR = 1000.0             # AUM value the source system seems to use as a minimum


def read_all(stage: str = "raw") -> dict:
    return {n: read_table(n, stage) for n in TABLE_NAMES}


# ---------------------------------------------------------------------------
# Small typed helpers (text in -> typed out, failures become NaN/NaT)
# ---------------------------------------------------------------------------
def is_blank(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip() == ""


def num(s: pd.Series) -> pd.Series:
    x = pd.to_numeric(s.astype(str).str.strip().replace("", np.nan), errors="coerce")
    return x.where(np.isfinite(x))  # 'inf' / '-inf' text is not a valid number


def dt(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.astype(str).str.strip().replace("", np.nan), format="%Y-%m-%d", errors="coerce")


INT_RE = r"^-?\d+$"
FLOAT_RE = r"^-?\d+(\.\d+)?([eE][-+]?\d+)?$"
DATE_RE = r"^\d{4}-\d{2}-\d{2}$"


def valid_type(s: pd.Series, typ: str) -> pd.Series:
    """True if a non-blank value is valid for the expected type (blank -> NA)."""
    v = s.astype(str).str.strip()
    if typ == "int":
        ok = v.str.match(INT_RE)
    elif typ == "float":
        ok = v.str.match(FLOAT_RE)
    elif typ == "date":
        ok = v.str.match(DATE_RE) & dt(v).notna()
    elif typ == "bool":
        ok = v.isin(["True", "False"])
    elif typ == "flag01":
        ok = v.isin(["0", "1"])
    else:  # text
        ok = pd.Series(True, index=s.index)
    return ok.astype("boolean").mask(v == "")


# ---------------------------------------------------------------------------
# Table metadata: keys, expected types, allowed values
# ---------------------------------------------------------------------------
US_STATES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
    "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
    "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH",
    "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
    "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
    "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN",
    "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY", "District of Columbia": "DC",
}
STATE_CODES = set(US_STATES.values())

TRADE_TYPES = ["Buy", "Sell", "Dividend"]           # need security_id, shares, price
CASH_TYPES = ["Deposit", "Withdrawal", "Advisory Fee"]  # must NOT have them

# Benchmark assigned to a snapshot follows the client's risk profile
RISK_TO_BENCHMARK = {
    "Aggressive": "1", "Moderately Aggressive": "1",
    "Balanced": "3",
    "Moderately Conservative": "8", "Conservative": "8",
}

SCHEMA = {
    "dim_advisor": {
        "pk": ["advisor_id"],
        "types": {"advisor_id": "int", "years_experience": "int", "aum_target_mm": "int"},
        "allowed": {
            "region": ["Northeast", "Mid-Atlantic", "Southeast", "Midwest", "West"],
            # "None" is a real answer here (advisor holds no certification), not a missing value
            "certifications": ["None", "CFA", "CFP", "CFP, CFA", "CFP, CIMA", "CIMA", "CFA, CIMA"],
        },
        "ranges": {"years_experience": (0, 60), "aum_target_mm": (1, 10000)},
        "required": ["advisor_id", "first_name", "last_name", "region", "years_experience",
                     "aum_target_mm", "certifications"],
    },
    "dim_benchmark": {
        "pk": ["benchmark_id"],
        "business_key": ["ticker_proxy"],
        "types": {"benchmark_id": "int"},
        "required": ["benchmark_id", "name", "asset_class", "ticker_proxy"],
    },
    "dim_client": {
        "pk": ["client_id"],
        # same person keyed twice: everything identical except the surrogate id / name spelling
        "business_key": ["first_name", "age", "city", "zip_code", "initial_aum", "client_since"],
        "near_dup": {"match_on": ["first_name", "age", "city", "zip_code", "initial_aum",
                                  "client_since", "advisor_id"], "fuzzy": "last_name"},
        "types": {"client_id": "int", "age": "int", "initial_aum": "float",
                  "client_since": "date", "advisor_id": "int", "is_active": "bool"},
        "allowed": {
            "risk_profile": list(RISK_TO_BENCHMARK),
            "client_tier": ["Retail", "HNW", "UHNW"],
            "primary_account_type": ["Taxable", "IRA", "Roth IRA", "Trust", "529"],
            "state": sorted(STATE_CODES),
        },
        "ranges": {"age": (18, 110), "initial_aum": (0.01, None)},
        "required": ["client_id", "first_name", "last_name", "age", "city", "state", "zip_code",
                     "risk_profile", "client_tier", "primary_account_type", "initial_aum",
                     "client_since", "advisor_id", "is_active"],
    },
    "dim_date": {
        "pk": ["date_id"],
        "business_key": ["date"],
        "types": {"date_id": "int", "date": "date", "year": "int", "quarter": "int", "month": "int",
                  "week_of_year": "int", "is_month_end": "flag01", "is_quarter_end": "flag01",
                  "is_year_end": "flag01", "is_trading_day": "flag01"},
        "ranges": {"year": (2020, 2024), "quarter": (1, 4), "month": (1, 12), "week_of_year": (1, 53)},
        "required": "all",
    },
    "dim_security": {
        "pk": ["security_id"],
        "business_key": ["ticker"],
        "types": {"security_id": "int", "benchmark_id": "int", "is_etf": "bool",
                  "expense_ratio_bps": "float"},
        "allowed": {"asset_class": ["Equity", "Fixed Income", "Alternative", "Cash Equivalent"]},
        "ranges": {"expense_ratio_bps": (0, 300)},
        # sector only exists for single stocks; expense ratio only exists for ETFs
        "required": ["security_id", "ticker", "name", "asset_class", "benchmark_id", "is_etf"],
        "conditional_required": [
            ("sector", lambda d: d["is_etf"] == "False"),
            ("expense_ratio_bps", lambda d: d["is_etf"] == "True"),
        ],
    },
    "fact_fees": {
        "pk": ["fee_id"],
        "business_key": ["client_id", "fee_date", "fee_type"],
        "types": {"fee_id": "int", "client_id": "int", "advisor_id": "int", "fee_date": "date",
                  "aum_basis": "float", "bps_charged": "float", "amount": "float"},
        "allowed": {"fee_type": ["Management", "Advisory", "Custodial", "Performance"]},
        "ranges": {"aum_basis": (0.01, None), "bps_charged": (0, 300), "amount": (0.01, None)},
        "required": "all",
    },
    "fact_portfolio_snapshot": {
        "pk": ["snapshot_id"],
        "business_key": ["client_id", "snapshot_date"],
        "types": {"snapshot_id": "int", "client_id": "int", "advisor_id": "int",
                  "benchmark_id": "int", "snapshot_date": "date", "year": "int", "month": "int",
                  "aum": "float", "return_ytd": "float", "benchmark_return_ytd": "float",
                  "active_alpha_ytd": "float", "cash_pct": "float"},
        "allowed": {"account_type": ["Taxable", "IRA", "Roth IRA", "Trust", "529"]},
        "ranges": {"aum": (0.01, None), "cash_pct": (0, 1), "return_ytd": (-1, None),
                   "month": (1, 12), "year": (2020, 2024)},
        "required": "all",
    },
    "fact_transactions": {
        "pk": ["txn_id"],
        "types": {"txn_id": "int", "client_id": "int", "advisor_id": "int", "security_id": "int",
                  "txn_date": "date", "shares": "float", "price": "float", "amount": "float"},
        "allowed": {"txn_type": TRADE_TYPES + CASH_TYPES},
        "ranges": {"shares": (0.0001, None), "price": (0.01, None), "amount": (0.01, None)},
        "required": ["txn_id", "client_id", "advisor_id", "txn_date", "txn_type", "amount"],
        "conditional_required": [
            ("security_id", lambda d: d["txn_type"].isin(TRADE_TYPES)),
            ("shares", lambda d: d["txn_type"].isin(TRADE_TYPES)),
            ("price", lambda d: d["txn_type"].isin(TRADE_TYPES)),
        ],
    },
}

# Flag columns that 02_clean.py adds (not part of the raw layout)
FLAG_COLUMNS = {
    "dim_client": ["flag_risk_profile_missing"],
    "fact_portfolio_snapshot": ["flag_return_implausible", "flag_aum_at_floor"],
    "fact_transactions": ["flag_after_account_close"],
}

# ---------------------------------------------------------------------------
# Relationships: 10 ID-based + 3 date-based
# (fact/child table, fk column, dim/parent table, key column)
# ---------------------------------------------------------------------------
RELATIONSHIPS = [
    ("dim_client", "advisor_id", "dim_advisor", "advisor_id"),
    ("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_fees", "client_id", "dim_client", "client_id"),
    ("fact_fees", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "client_id", "dim_client", "client_id"),
    ("fact_portfolio_snapshot", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_transactions", "client_id", "dim_client", "client_id"),
    ("fact_transactions", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_transactions", "security_id", "dim_security", "security_id"),
    ("fact_fees", "fee_date", "dim_date", "date"),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date"),
    ("fact_transactions", "txn_date", "dim_date", "date"),
]


def key_norm(s: pd.Series) -> pd.Series:
    """Compare keys the way a BI tool would after typing them as whole numbers.
    '45.0' and '45' are the same key once typed, so normalise before matching."""
    v = s.astype(str).str.strip()
    n = pd.to_numeric(v, errors="coerce")
    whole = n.notna() & (n % 1 == 0)
    return v.where(~whole, n.where(whole).astype("Int64").astype(str))


# ---------------------------------------------------------------------------
# Row rules (single-table) and cross-table business rules.
# Each rule returns a boolean Series aligned to the table: True = pass,
# False = fail, <NA> = rule does not apply to that row.
# ---------------------------------------------------------------------------
def _applies(mask, ok):
    # build on mask.index so a filtered table can never be lined up against the wrong rows
    return pd.Series(np.asarray(ok), index=mask.index, dtype="boolean").where(np.asarray(mask), pd.NA)


def _client_lookup(T, col):
    c = T["dim_client"].drop_duplicates("client_id").set_index("client_id")[col]
    return c


def rule_tier_matches_aum(T):
    d = T["dim_client"]; a = num(d["initial_aum"])
    exp = np.select([a < 500_000, a < 5_000_000], ["Retail", "HNW"], "UHNW")
    return _applies(a.notna(), d["client_tier"] == exp)


def rule_state_code(T):
    d = T["dim_client"]
    return _applies(~is_blank(d["state"]), d["state"].isin(STATE_CODES))


def rule_zip5(T):
    d = T["dim_client"]
    return _applies(~is_blank(d["zip_code"]), d["zip_code"].str.match(r"^\d{5}$"))


def rule_date_attributes(T):
    d = T["dim_date"]; x = dt(d["date"])
    ok = ((d["year"] == x.dt.year.astype("Int64").astype(str))
          & (d["quarter"] == x.dt.quarter.astype("Int64").astype(str))
          & (d["month"] == x.dt.month.astype("Int64").astype(str))
          & (d["month_name"] == x.dt.month_name())
          & (d["day_of_week"] == x.dt.day_name())
          & (d["is_month_end"] == x.dt.is_month_end.astype(int).astype(str))
          & (d["is_quarter_end"] == x.dt.is_quarter_end.astype(int).astype(str))
          & (d["is_year_end"] == x.dt.is_year_end.astype(int).astype(str))
          & (d["is_trading_day"] == (x.dt.dayofweek < 5).astype(int).astype(str)))
    return _applies(x.notna(), ok)


def rule_etf_sector(T):
    d = T["dim_security"]
    ok = np.where(d["is_etf"] == "True", is_blank(d["sector"]), ~is_blank(d["sector"]))
    return _applies(d["is_etf"].isin(["True", "False"]), ok)


def rule_etf_expense(T):
    d = T["dim_security"]
    ok = np.where(d["is_etf"] == "True", ~is_blank(d["expense_ratio_bps"]), is_blank(d["expense_ratio_bps"]))
    return _applies(d["is_etf"].isin(["True", "False"]), ok)


def rule_fee_amount(T):
    d = T["fact_fees"]
    re = (num(d["aum_basis"]) * num(d["bps_charged"]) / 10000 / 12).round(2)
    a = num(d["amount"])
    return _applies(re.notna() & a.notna(), (a - re).abs() <= AMOUNT_TOL)


def rule_fee_first_of_month(T):
    d = T["fact_fees"]
    return _applies(~is_blank(d["fee_date"]), d["fee_date"].str.endswith("-01"))


def rule_snap_alpha(T):
    d = T["fact_portfolio_snapshot"]
    r, b, a = num(d["return_ytd"]), num(d["benchmark_return_ytd"]), num(d["active_alpha_ytd"])
    return _applies(b.notna() & a.notna(), (r - b - a).abs() <= ALPHA_TOL)


def rule_snap_year_month(T):
    d = T["fact_portfolio_snapshot"]; x = dt(d["snapshot_date"])
    ok = (num(d["year"]) == x.dt.year) & (num(d["month"]) == x.dt.month)
    return _applies(x.notna(), ok)


def rule_snap_return_plausible(T):
    d = T["fact_portfolio_snapshot"]; r = num(d["return_ytd"])
    return _applies(r.notna(), r.abs() <= RETURN_PLAUSIBLE_MAX)


def rule_snap_aum_floor(T):
    d = T["fact_portfolio_snapshot"]; a = num(d["aum"])
    return _applies(a.notna(), a != AUM_FLOOR)  # same test as the D10 flag


def rule_txn_security_presence(T):
    d = T["fact_transactions"]
    trade = d["txn_type"].isin(TRADE_TYPES)
    has = ~is_blank(d["security_id"]) & ~is_blank(d["shares"]) & ~is_blank(d["price"])
    none = is_blank(d["security_id"]) & is_blank(d["shares"]) & is_blank(d["price"])
    return _applies(d["txn_type"].isin(TRADE_TYPES + CASH_TYPES), np.where(trade, has, none))


def rule_txn_amount(T):
    d = T["fact_transactions"]
    re = (num(d["shares"]).abs() * num(d["price"])).round(2)
    a = num(d["amount"])
    return _applies(re.notna() & a.notna(), (a - re).abs() <= AMOUNT_TOL)


def rule_txn_shares_positive(T):
    d = T["fact_transactions"]; s = num(d["shares"])
    return _applies(s.notna(), s > 0)


# ---- cross-table --------------------------------------------------------
def rule_fee_aum_matches_snapshot(T):
    f, s = T["fact_fees"], T["fact_portfolio_snapshot"]
    look = s.drop_duplicates(["client_id", "snapshot_date"]).set_index(["client_id", "snapshot_date"])["aum"]
    idx = pd.MultiIndex.from_arrays([f["client_id"], f["fee_date"]])
    snap_aum = pd.Series(look.reindex(idx).values, index=f.index)
    ok = (num(snap_aum) - num(f["aum_basis"])).abs() <= 0.0051  # half a cent, plus float slack
    return _applies(snap_aum.notna(), ok)


def rule_fee_has_snapshot(T):
    f, s = T["fact_fees"], T["fact_portfolio_snapshot"]
    keys = set(zip(s["client_id"], s["snapshot_date"]))
    return pd.Series([k in keys for k in zip(f["client_id"], f["fee_date"])], index=f.index, dtype="boolean")


def _advisor_matches(T, table):
    f = T[table]; adv = _client_lookup(T, "advisor_id")
    exp = f["client_id"].map(adv)
    return _applies(exp.notna(), f["advisor_id"] == exp)


def rule_fee_advisor(T): return _advisor_matches(T, "fact_fees")
def rule_snap_advisor(T): return _advisor_matches(T, "fact_portfolio_snapshot")
def rule_txn_advisor(T): return _advisor_matches(T, "fact_transactions")


def rule_snap_account_type(T):
    s = T["fact_portfolio_snapshot"]; exp = s["client_id"].map(_client_lookup(T, "primary_account_type"))
    return _applies(exp.notna(), s["account_type"] == exp)


def rule_snap_benchmark_risk(T):
    s = T["fact_portfolio_snapshot"]
    risk = s["client_id"].map(_client_lookup(T, "risk_profile"))
    exp = risk.map(RISK_TO_BENCHMARK)
    return _applies(exp.notna(), s["benchmark_id"] == exp)


def rule_snap_benchmark_return_consistent(T):
    s = T["fact_portfolio_snapshot"]
    # compare as numbers, so '0.05' and '0.050' count as the same return
    n = num(s["benchmark_return_ytd"]).groupby([s["benchmark_id"], s["snapshot_date"]]).transform("nunique")
    return pd.Series(n == 1, dtype="boolean")


def rule_txn_after_client_since(T):
    t = T["fact_transactions"]; since = t["client_id"].map(_client_lookup(T, "client_since"))
    return _applies(since.notna(), t["txn_date"] >= since)


def rule_txn_not_after_close(T):
    """Inactive clients stop getting snapshots; activity after the last snapshot month is suspicious."""
    t, s = T["fact_transactions"], T["fact_portfolio_snapshot"]
    last = s.groupby("client_id")["snapshot_date"].max().str[:7]
    active = t["client_id"].map(_client_lookup(T, "is_active"))
    lastm = t["client_id"].map(last)
    applies = (active == "False") & lastm.notna()
    return _applies(applies, t["txn_date"].str[:7] <= lastm)


# (table, rule name, check group, severity, dimension, function)
ROW_RULES = [
    ("dim_client", "client_tier consistent with initial_aum bands", "2 single-table", "WARN", "Consistency", rule_tier_matches_aum),
    ("dim_client", "state is a 2-letter USPS code", "1 column", "ERROR", "Consistency", rule_state_code),
    ("dim_client", "zip_code is 5 digits (leading zeros kept)", "1 column", "ERROR", "Validity", rule_zip5),
    ("dim_date", "calendar attributes agree with date", "2 single-table", "ERROR", "Consistency", rule_date_attributes),
    ("dim_security", "sector blank only for ETFs", "2 single-table", "WARN", "Consistency", rule_etf_sector),
    ("dim_security", "expense_ratio present only for ETFs", "2 single-table", "WARN", "Consistency", rule_etf_expense),
    ("fact_fees", "amount = aum_basis x bps / 10000 / 12", "2 single-table", "ERROR", "Accuracy", rule_fee_amount),
    ("fact_fees", "fee_date is first of month", "2 single-table", "WARN", "Validity", rule_fee_first_of_month),
    ("fact_portfolio_snapshot", "active_alpha = return_ytd - benchmark_return_ytd", "2 single-table", "ERROR", "Accuracy", rule_snap_alpha),
    ("fact_portfolio_snapshot", "year/month agree with snapshot_date", "2 single-table", "ERROR", "Consistency", rule_snap_year_month),
    ("fact_portfolio_snapshot", "|return_ytd| <= 100%", "2 single-table", "WARN", "Plausibility", rule_snap_return_plausible),
    ("fact_portfolio_snapshot", "aum not at the 1,000.00 floor value", "2 single-table", "WARN", "Plausibility", rule_snap_aum_floor),
    ("fact_transactions", "security/shares/price present only for Buy/Sell/Dividend", "2 single-table", "ERROR", "Consistency", rule_txn_security_presence),
    ("fact_transactions", "amount = |shares| x price", "2 single-table", "ERROR", "Accuracy", rule_txn_amount),
    ("fact_transactions", "shares > 0 (direction is in txn_type)", "1 column", "ERROR", "Validity", rule_txn_shares_positive),
    ("fact_fees", "aum_basis = snapshot aum (same client, month)", "4 cross-table", "ERROR", "Consistency", rule_fee_aum_matches_snapshot),
    ("fact_fees", "fee has a matching monthly snapshot", "4 cross-table", "WARN", "Consistency", rule_fee_has_snapshot),
    ("fact_fees", "advisor_id = client's advisor", "4 cross-table", "ERROR", "Consistency", rule_fee_advisor),
    ("fact_portfolio_snapshot", "advisor_id = client's advisor", "4 cross-table", "ERROR", "Consistency", rule_snap_advisor),
    ("fact_transactions", "advisor_id = client's advisor", "4 cross-table", "ERROR", "Consistency", rule_txn_advisor),
    ("fact_portfolio_snapshot", "account_type = client's primary_account_type", "4 cross-table", "WARN", "Consistency", rule_snap_account_type),
    ("fact_portfolio_snapshot", "benchmark matches client's risk profile", "4 cross-table", "WARN", "Consistency", rule_snap_benchmark_risk),
    ("fact_portfolio_snapshot", "one benchmark return per benchmark per month", "4 cross-table", "ERROR", "Consistency", rule_snap_benchmark_return_consistent),
    ("fact_transactions", "txn_date >= client_since", "4 cross-table", "ERROR", "Plausibility", rule_txn_after_client_since),
    ("fact_transactions", "inactive client: no activity after last snapshot month", "4 cross-table", "WARN", "Plausibility", rule_txn_not_after_close),
]
