"""
01_profile.py  -  HW4 Part A: audit every Wildcat Capital table.

Two layers:
  1. profile_table(df)  - GENERIC. Works on any CSV read as text. No column names
     are hard-coded: it infers each column's type from the values themselves and
     reports blanks, distinct values, value shapes, parse failures, whitespace,
     mixed formats and numeric min/max.
  2. Data-quality checks in four groups, driven by the table metadata in
     wildcat_config.py (keys, allowed values, ranges, relationships, rules):
        1 column level | 2 single-table | 3 referential integrity | 4 cross-table
     Each finding is tagged ERROR / WARN / INFO (PASS when nothing failed).

Usage (from the hw04 folder):
    python scripts/01_profile.py              # audits the raw files
    python scripts/01_profile.py --stage clean

Outputs: reports/profile_<stage>.csv and reports/dq_summary_<stage>.csv
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wildcat_config as cfg  # noqa: E402


# ===========================================================================
# 1. GENERIC COLUMN PROFILE
# ===========================================================================
def value_shape(v: str) -> str:
    """'2023-06-01' -> '9-9-9', 'Roth IRA' -> 'a a', '9.28%' -> '9.9%'."""
    s = re.sub(r"[A-Za-z]+", "a", v)
    s = re.sub(r"\d+", "9", s)
    return s if s else "<blank>"


def format_class(v: str) -> str:
    """Finer label used to spot mixed formats inside one column."""
    if v == "":
        return "blank"
    if re.fullmatch(r"-?\d+", v):
        return "integer"
    if re.fullmatch(r"-?\d+\.0+", v):
        return "integer-as-decimal (e.g. 45.0)"
    if re.fullmatch(r"-?\d+\.\d+", v):
        return "decimal"
    if re.fullmatch(r"-?\d+(\.\d+)?[eE][-+]?\d+", v):
        return "scientific notation"
    if re.fullmatch(r"-?\d+(\.\d+)?%", v):
        return "percent string"
    if re.fullmatch(r"-?\$[\d,]+(\.\d+)?", v):
        return "currency string"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return "date ISO"
    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{2,4}", v):
        return "date US"
    if v in ("True", "False", "true", "false", "TRUE", "FALSE"):
        return "boolean"
    if v.isupper() and v.isalpha() and len(v) <= 3:
        return "code (upper)"
    return "text"


def infer_type(values: pd.Series, col_name: str) -> str:
    """Pick the strictest type that at least 95% of non-blank values satisfy.
    Columns named *_id are expected to be whole-number keys."""
    v = values[values.str.strip() != ""].str.strip()
    if v.empty:
        return "empty"
    share = lambda m: m.mean()
    if col_name.endswith("_id") and share(v.str.match(r"^-?\d+(\.0+)?$")) >= 0.95:
        return "int"
    if share(v.isin(["True", "False"])) >= 0.95:
        return "bool"
    if share(v.str.match(cfg.DATE_RE)) >= 0.95:
        return "date"
    if share(v.str.match(cfg.INT_RE)) >= 0.95:
        return "int"
    if share(v.str.match(cfg.FLOAT_RE)) >= 0.95:
        return "float"
    return "text"


def profile_table(df: pd.DataFrame, table: str) -> pd.DataFrame:
    rows = []
    n = len(df)
    for col in df.columns:
        s = df[col].astype(str)
        stripped = s.str.strip()
        blank = stripped == ""
        nonblank = stripped[~blank]
        typ = infer_type(s, col)

        shapes = nonblank.map(value_shape).value_counts()
        top_shapes = "; ".join(f"{k} ({v / max(len(nonblank), 1):.1%})" for k, v in shapes.head(3).items())

        fmts = nonblank.map(format_class).value_counts()
        mixed = ""
        if len(fmts) > 1:
            mixed = "; ".join(f"{k}: {v}" for k, v in fmts.items())

        # parse failures against the inferred type
        if typ == "int":
            ok = nonblank.str.match(cfg.INT_RE)
        elif typ == "float":
            ok = nonblank.str.match(cfg.FLOAT_RE)
        elif typ == "date":
            ok = nonblank.str.match(cfg.DATE_RE) & cfg.dt(nonblank).notna()
        elif typ == "bool":
            ok = nonblank.isin(["True", "False"])
        else:
            ok = pd.Series(True, index=nonblank.index)
        fail = int((~ok).sum())
        fail_examples = ", ".join(nonblank[~ok].unique()[:3])

        numeric = pd.to_numeric(nonblank, errors="coerce")
        has_num = typ in ("int", "float") and numeric.notna().any()
        ws = int(((s != stripped) | s.str.contains(r"\s{2,}")).sum())

        rows.append({
            "table": table, "column": col, "rows": n,
            "inferred_type": typ,
            "blank_count": int(blank.sum()), "blank_pct": round(blank.mean() * 100, 3),
            "distinct_count": int(nonblank.nunique()),
            "top_shapes": top_shapes,
            "parse_fail_count": fail,
            "parse_fail_pct": round(fail / max(len(nonblank), 1) * 100, 3),
            "parse_fail_examples": fail_examples,
            "whitespace_issues": ws,
            "n_formats": int(len(fmts)),
            "mixed_formats": mixed,
            # dates: min/max of the parsed dates, not of the text (text order breaks on 6/1/2023)
            "min": numeric.min() if has_num else (cfg.dt(nonblank).min().date() if typ == "date" and cfg.dt(nonblank).notna().any() else ""),
            "max": numeric.max() if has_num else (cfg.dt(nonblank).max().date() if typ == "date" and cfg.dt(nonblank).notna().any() else ""),
            "top_values": "; ".join(f"{k} ({v})" for k, v in nonblank.value_counts().head(5).items()),
        })
    return pd.DataFrame(rows)


# ===========================================================================
# 2. DATA-QUALITY CHECKS
# ===========================================================================
FINDINGS = []


def add(group, severity, table, column, check, dimension, checked, failed, example="", note=""):
    FINDINGS.append({
        "check_group": group,
        "severity": severity if failed else "PASS",
        "table": table, "column": column, "check": check, "dimension": dimension,
        "rows_checked": int(checked), "rows_failed": int(failed),
        "pct_failed": round(failed / checked * 100, 3) if checked else 0.0,
        "example": example, "note": note,
    })


def examples(df, mask, cols, k=3):
    cols = list(dict.fromkeys(cols))
    sub = df.loc[mask.fillna(False).astype(bool), cols].head(k)
    return " | ".join(", ".join(f"{c}={r[c]}" for c in cols) for _, r in sub.iterrows())


def group1_column_checks(T):
    g = "1 column"
    for table, meta in cfg.SCHEMA.items():
        d = T[table]
        pk = meta["pk"]
        # key uniqueness + null keys
        dup = d.duplicated(pk, keep=False)
        add(g, "ERROR", table, ",".join(pk), "primary key unique", "Uniqueness", len(d), dup.sum(),
            examples(d, dup, pk))
        nullk = d[pk].apply(cfg.is_blank).any(axis=1)
        add(g, "ERROR", table, ",".join(pk), "primary key not blank", "Completeness", len(d), nullk.sum())
        # expected types
        for col, typ in meta.get("types", {}).items():
            ok = cfg.valid_type(d[col], typ)
            bad = ok == False  # noqa: E712
            sev = "ERROR"
            add(g, sev, table, col, f"values parse as {typ}", "Validity", ok.notna().sum(), bad.sum(),
                examples(d, bad, pk + [col]))
        # allowed values
        for col, allowed in meta.get("allowed", {}).items():
            nb = ~cfg.is_blank(d[col])
            bad = nb & ~d[col].isin(allowed)
            vals = ", ".join(d.loc[bad, col].value_counts().head(5).index)
            add(g, "ERROR", table, col, "value in allowed list", "Validity", nb.sum(), bad.sum(),
                vals, f"allowed: {', '.join(map(str, allowed[:12]))}{'...' if len(allowed) > 12 else ''}")
        # ranges
        for col, (lo, hi) in meta.get("ranges", {}).items():
            x = cfg.num(d[col])
            bad = pd.Series(False, index=d.index)
            if lo is not None:
                bad |= x < lo
            if hi is not None:
                bad |= x > hi
            add(g, "ERROR", table, col, f"within range [{lo}, {hi}]", "Validity", x.notna().sum(), bad.sum(),
                examples(d, bad, pk + [col]))
        # required columns
        req = list(d.columns) if meta.get("required") == "all" else meta.get("required", [])
        for col in req:
            b = cfg.is_blank(d[col])
            add(g, "ERROR", table, col, "required value present", "Completeness", len(d), b.sum(),
                examples(d, b, pk))
        # conditionally required (structural blanks are legitimate)
        for col, cond in meta.get("conditional_required", []):
            need = cond(d)
            b = need & cfg.is_blank(d[col])
            add(g, "ERROR", table, col, "present where business logic requires it", "Completeness",
                need.sum(), b.sum(), examples(d, b, pk),
                f"{(~need & cfg.is_blank(d[col])).sum()} rows are blank by design (not required)")
        # whitespace on every column
        for col in d.columns:
            s = d[col]
            ws = (s != s.str.strip()) | s.str.contains(r"\s{2,}")
            if ws.any():
                add(g, "WARN", table, col, "no leading/trailing/double spaces", "Validity", len(d), ws.sum())
        # mixed number formats: judged against the type the metadata expects
        for col, typ in meta.get("types", {}).items():
            if typ not in ("int", "float"):
                continue
            v = d[col].str.strip()
            fmts = v[v != ""].map(format_class)
            normal = {"integer"} if typ == "int" else {"integer", "decimal", "integer-as-decimal (e.g. 45.0)"}
            for fmt, cnt in fmts[~fmts.isin(normal)].value_counts().items():
                sev = "INFO" if fmt == "scientific notation" else "ERROR"
                note = ("valid number, parses fine; just a different text format"
                        if sev == "INFO" else "will fail or change meaning when the column is typed")
                add(g, sev, table, col, f"one number format per column ({fmt})", "Consistency",
                    len(fmts), cnt, ", ".join(v[fmts.index][fmts == fmt].unique()[:3]), note)


def group2_single_table(T):
    g = "2 single-table"
    for table, meta in cfg.SCHEMA.items():
        d = T[table]
        pk = meta["pk"]
        non_key = [c for c in d.columns if c not in pk]
        dup = d.duplicated(non_key, keep=False)
        add(g, "ERROR", table, "(all non-key)", "no exact duplicate rows under different ids", "Uniqueness",
            len(d), dup.sum(), examples(d, dup, pk))
        if "business_key" in meta:
            bk = meta["business_key"]
            dupb = d.duplicated(bk, keep=False)
            add(g, "ERROR", table, ",".join(bk), "business key unique", "Uniqueness", len(d), dupb.sum(),
                examples(d, dupb, pk + bk[:2]))
        if "near_dup" in meta:
            nd = meta["near_dup"]
            fz = nd["fuzzy"]
            grp = d.groupby(nd["match_on"])
            hits = []
            for _, sub in grp:
                if len(sub) < 2:
                    continue
                names = sub[fz].str.lower().tolist()
                for i, (idx, nm) in enumerate(zip(sub.index, names)):
                    for jdx, other in zip(sub.index, names):
                        if idx != jdx and nm != other and (other.startswith(nm) or nm.startswith(other)):
                            hits.append(idx)
            m = d.index.isin(hits)
            add(g, "ERROR", table, fz, f"rows in near-duplicate pairs (same {', '.join(nd['match_on'][:4])}..., "
                f"{fz} differs only by a prefix)", "Uniqueness", len(d), m.sum(),
                examples(d, pd.Series(m, index=d.index), pk + [fz], k=4), f"{m.sum() // 2} pairs")
    for table, name, grp, sev, dim, fn in cfg.ROW_RULES:
        if not grp.startswith("1") and not grp.startswith("2"):
            continue
        r = fn(T)
        bad = r == False  # noqa: E712
        add(grp, sev, table, "", name, dim, r.notna().sum(), bad.sum(),
            examples(T[table], bad, cfg.SCHEMA[table]["pk"]))


def group3_referential(T):
    g = "3 referential"
    for child, fk, parent, pkey in cfg.RELATIONSHIPS:
        c = T[child][fk]
        nb = ~cfg.is_blank(c)
        exact = nb & ~c.isin(set(T[parent][pkey]))
        norm = nb & ~cfg.key_norm(c).isin(set(cfg.key_norm(T[parent][pkey])))
        rel = f"{child}.{fk} -> {parent}.{pkey}"
        if exact.sum() != norm.sum():
            add(g, "ERROR", child, fk, f"{rel}: key text matches parent key text", "Referential Integrity",
                nb.sum(), exact.sum(), ", ".join(c[exact].unique()[:3]),
                "Different text for the same key (e.g. '45.0' vs '45') breaks a join on text keys")
        add(g, "ERROR", child, fk, f"{rel}: every FK exists in parent", "Referential Integrity",
            nb.sum(), norm.sum(), ", ".join(c[norm].unique()[:5]),
            f"{c[norm].nunique()} distinct orphan keys; {(~nb).sum()} blank FKs")
    # unused dimension members (INFO)
    for parent, pkey, users in [
        ("dim_client", "client_id", [("fact_fees", "client_id"), ("fact_portfolio_snapshot", "client_id"),
                                     ("fact_transactions", "client_id")]),
        ("dim_benchmark", "benchmark_id", [("dim_security", "benchmark_id"),
                                           ("fact_portfolio_snapshot", "benchmark_id")]),
        ("dim_security", "security_id", [("fact_transactions", "security_id")]),
    ]:
        used = set()
        for t, c in users:
            used |= set(cfg.key_norm(T[t][c]))
        unused = ~cfg.key_norm(T[parent][pkey]).isin(used)
        add(g, "INFO", parent, pkey, "dimension members never referenced by any fact", "Referential Integrity",
            len(T[parent]), unused.sum(), ", ".join(T[parent].loc[unused, pkey].head(5)))


def group4_cross_table(T):
    g = "4 cross-table"
    for table, name, grp, sev, dim, fn in cfg.ROW_RULES:
        if not grp.startswith("4"):
            continue
        r = fn(T)
        bad = r == False  # noqa: E712
        add(g, sev, table, "", name, dim, r.notna().sum(), bad.sum(),
            examples(T[table], bad, cfg.SCHEMA[table]["pk"] + ["client_id"]))

    # --- informational context checks (not row rules) ---
    t, f, s, c, dd = (T["fact_transactions"], T["fact_fees"], T["fact_portfolio_snapshot"],
                      T["dim_client"], T["dim_date"])
    since = c.drop_duplicates("client_id").set_index("client_id")["client_since"]
    for tbl, dcol in [("fact_fees", "fee_date"), ("fact_portfolio_snapshot", "snapshot_date")]:
        x = T[tbl]; sc = x["client_id"].map(since)
        # compare real dates; blank or unparseable dates are not counted as "early"
        early = cfg.dt(sc).notna() & cfg.dt(x[dcol]).notna() & (cfg.dt(x[dcol]) < cfg.dt(sc))
        same_month = early & (x[dcol].str[:7] == sc.str[:7])
        add(g, "INFO", tbl, dcol, f"{dcol} before client_since", "Plausibility", sc.notna().sum(), early.sum(),
            examples(x, early, ["client_id", dcol]),
            f"{same_month.sum()} of these are the month-start record of the onboarding month")
    trading = t["txn_date"].map(dd.drop_duplicates("date").set_index("date")["is_trading_day"])
    wk = t["txn_type"].isin(cfg.TRADE_TYPES) & (trading == "0")
    add(g, "WARN", "fact_transactions", "txn_date", "Buy/Sell/Dividend dated on a non-trading day (dim_date)",
        "Plausibility", t["txn_type"].isin(cfg.TRADE_TYPES).sum(), wk.sum(), examples(t, wk, ["txn_id", "txn_date"]))
    keys = set(zip(f["client_id"], f["fee_date"]))
    nofee = pd.Series([k not in keys for k in zip(s["client_id"], s["snapshot_date"])], index=s.index)
    add(g, "INFO", "fact_portfolio_snapshot", "", "snapshot month has no fee row", "Completeness",
        len(s), nofee.sum(), examples(s, nofee, ["client_id", "snapshot_date"]))
    # cash fee debits vs fee accruals (two systems)
    ft = cfg.num(t.loc[t["txn_type"] == "Advisory Fee", "amount"]).groupby(t["client_id"]).sum()
    ff = cfg.num(f["amount"]).groupby(f["client_id"]).sum()
    # Compared with ALL fact_fees types on purpose: the cash debit is one payment for the whole bill.
    # A client with fees but no debits (or the reverse) counts as 0 on that side, so it is not skipped.
    j = pd.concat([ft.rename("txn"), ff.rename("fee")], axis=1).fillna(0)
    off = ((j["txn"] - j["fee"]).abs() > 0.05 * j["fee"].abs()) | ((j["fee"] == 0) & (j["txn"] != 0))
    add(g, "INFO", "fact_transactions", "amount",
        "client total 'Advisory Fee' cash debits within 5% of fact_fees total", "Consistency",
        len(j), off.sum(), "", f"txn total {ft.sum():,.2f} vs fact_fees total (all fee types) {ff.sum():,.2f}; "
        f"{(j['txn'] == 0).sum()} clients have fees but no fee debits")
    # initial_aum vs first snapshot
    first = s.sort_values("snapshot_date").groupby("client_id")["aum"].first()
    ia = cfg.num(c.drop_duplicates("client_id").set_index("client_id")["initial_aum"])
    ratio = (cfg.num(first) / ia.reindex(first.index))
    off = (ratio - 1).abs() > 0.25
    add(g, "INFO", "dim_client", "initial_aum", "first snapshot aum within 25% of initial_aum", "Consistency",
        ratio.notna().sum(), off.sum(), ", ".join(off[off].index[:5]))


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="raw", choices=["raw", "clean"])
    args = ap.parse_args()
    cfg.REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    T = cfg.read_all(args.stage)
    print(f"Loaded {args.stage} tables:")
    for k, v in T.items():
        print(f"  {k:<26} {len(v):>8,} rows x {v.shape[1]} cols")

    profile = pd.concat([profile_table(df, name) for name, df in T.items()], ignore_index=True)
    profile.to_csv(cfg.REPORTS_DIR / f"profile_{args.stage}.csv", index=False)

    FINDINGS.clear()
    group1_column_checks(T)
    group2_single_table(T)
    group3_referential(T)
    group4_cross_table(T)
    dq = pd.DataFrame(FINDINGS)
    order = {"ERROR": 0, "WARN": 1, "INFO": 2, "PASS": 3}
    dq = dq.sort_values(["severity", "check_group", "table"], key=lambda s: s.map(order) if s.name == "severity" else s)
    dq.to_csv(cfg.REPORTS_DIR / f"dq_summary_{args.stage}.csv", index=False)

    print(f"\nProfile: {len(profile)} columns -> reports/profile_{args.stage}.csv")
    print(f"Checks:  {len(dq)} -> reports/dq_summary_{args.stage}.csv")
    print(dq["severity"].value_counts().to_string())
    print("\nFindings (non-PASS):")
    show = dq[dq.severity != "PASS"][["severity", "check_group", "table", "column", "check", "rows_failed"]]
    with pd.option_context("display.max_rows", 200, "display.width", 200, "display.max_colwidth", 70):
        print(show.to_string(index=False))


if __name__ == "__main__":
    main()
