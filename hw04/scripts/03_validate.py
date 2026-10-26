"""
03_validate.py  -  HW4 Part D: referential integrity, rule checks, reconciliations,
outliers and a raw-vs-clean data quality scorecard.

Runs every check on BOTH stages (raw files, data/clean files) with the same rules.

Outputs (reports/):
  ri_results.csv                 13 relationships x 2 stages
  rule_results.csv               every business-bound rule x 2 stages
  reconciliations.csv            recomputed vs stored amounts x 2 stages
  outliers_iqr.csv               IQR summary for unbounded numeric columns
  data_quality_scorecard.csv     one row per table per stage

Usage (from the hw04 folder):  python scripts/03_validate.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wildcat_config as cfg  # noqa: E402


# ===========================================================================
# Reusable referential-integrity check  (keep for Assignment 5)
# ===========================================================================
def check_referential_integrity(fact_df, fact_key, dim_df, dim_key):
    """Check that every foreign key in fact_df[fact_key] exists in dim_df[dim_key].

    Keys are compared exactly as stored (text), the way a relationship in a BI
    tool would match them. Blank keys are counted separately and are NOT
    treated as orphans (a blank security_id on a cash deposit is legitimate).

    Returns a dict:
        match_rate            share of non-blank FKs found in the dimension (0-1)
        orphan_rows           DataFrame of the fact rows whose key is not found
        n_orphan_rows         number of those rows
        distinct_orphan_keys  number of distinct missing key values
        null_key_rate         share of fact rows with a blank FK (0-1)
        n_nonnull             number of fact rows with a non-blank FK
    """
    fk = fact_df[fact_key].astype(str).str.strip()
    valid_keys = set(dim_df[dim_key].astype(str).str.strip())
    is_null = fk == ""
    found = fk.isin(valid_keys)
    orphan_mask = ~is_null & ~found
    n_nonnull = int((~is_null).sum())
    return {
        "match_rate": float(found[~is_null].mean()) if n_nonnull else 1.0,
        "orphan_rows": fact_df.loc[orphan_mask],
        "n_orphan_rows": int(orphan_mask.sum()),
        "distinct_orphan_keys": int(fk[orphan_mask].nunique()),
        "null_key_rate": float(is_null.mean()) if len(fk) else 0.0,
        "n_nonnull": n_nonnull,
    }


# ===========================================================================
# Rule checks with a natural business bound
# ===========================================================================
def rule_checks(T):
    """Allowed lists, ranges, sign rules, type validity and the shared row rules.
    Returns one row per rule: evaluated, passed, failed."""
    out = []

    def rec(table, column, rule, kind, ok):
        ok = pd.Series(ok, dtype="boolean")
        ev = int(ok.notna().sum()); ps = int((ok == True).sum())  # noqa: E712
        out.append({"table": table, "column": column, "rule": rule, "kind": kind,
                    "evaluated": ev, "passed": ps, "failed": ev - ps,
                    "pass_pct": round(ps / ev * 100, 3) if ev else 100.0})

    for table, meta in cfg.SCHEMA.items():
        d = T[table]
        for col, allowed in meta.get("allowed", {}).items():
            nb = ~cfg.is_blank(d[col])
            rec(table, col, "value in allowed code list", "allowed list",
                pd.Series(d[col].isin(allowed), dtype="boolean").where(nb, pd.NA))
        for col, (lo, hi) in meta.get("ranges", {}).items():
            x = cfg.num(d[col])
            ok = pd.Series(True, index=d.index)
            if lo is not None:
                ok &= x >= lo
            if hi is not None:
                ok &= x <= hi
            kind = "sign rule" if (lo is not None and lo > 0 and hi is None) else "valid range"
            rec(table, col, f"between {lo} and {hi}", kind, pd.Series(ok, dtype="boolean").where(x.notna(), pd.NA))
    for table, name, grp, sev, dim, fn in cfg.ROW_RULES:
        rec(table, "", name, f"row rule ({grp})", fn(T))
    return pd.DataFrame(out)


# ===========================================================================
# Cross-table / recomputation reconciliations
# ===========================================================================
def reconciliations(T):
    out = []
    f = T["fact_fees"]
    stored = cfg.num(f["amount"])
    recomputed = (cfg.num(f["aum_basis"]) * cfg.num(f["bps_charged"]) / 10000 / 12).round(2)
    out.append({"reconciliation": "fee amount = aum_basis x bps / 10000 / 12", "table": "fact_fees",
                "rows": len(f), "rows_matching": int(((stored - recomputed).abs() <= 0.011).sum()),
                "stored_total": round(stored.sum(), 2), "recomputed_total": round(recomputed.sum(), 2)})

    t = T["fact_transactions"]
    tr = t["txn_type"].isin(cfg.TRADE_TYPES)
    stored = cfg.num(t.loc[tr, "amount"])
    signed = (cfg.num(t.loc[tr, "shares"]) * cfg.num(t.loc[tr, "price"])).round(2)
    out.append({"reconciliation": "trade amount = shares x price (shares as stored)", "table": "fact_transactions",
                "rows": int(tr.sum()), "rows_matching": int(((stored - signed).abs() <= 0.011).sum()),
                "stored_total": round(stored.sum(), 2), "recomputed_total": round(signed.sum(), 2)})

    s = T["fact_portfolio_snapshot"]
    look = s.drop_duplicates(["client_id", "snapshot_date"]).set_index(["client_id", "snapshot_date"])["aum"]
    snap_aum = cfg.num(pd.Series(look.reindex(pd.MultiIndex.from_arrays([f["client_id"], f["fee_date"]])).values,
                                 index=f.index))
    basis = cfg.num(f["aum_basis"])
    out.append({"reconciliation": "fee aum_basis = snapshot aum (same client, month)", "table": "fact_fees vs snapshot",
                "rows": len(f), "rows_matching": int(((snap_aum - basis).abs() <= 0.005).sum()),
                "stored_total": round(basis.sum(), 2), "recomputed_total": round(snap_aum.sum(), 2)})

    r = cfg.num(s["return_ytd"]); b = cfg.num(s["benchmark_return_ytd"]); a = cfg.num(s["active_alpha_ytd"])
    out.append({"reconciliation": "return_ytd = benchmark_return_ytd + active_alpha_ytd",
                "table": "fact_portfolio_snapshot", "rows": len(s),
                "rows_matching": int(((r - b - a).abs() <= 2e-6).sum()),
                "stored_total": round(r.sum(), 4), "recomputed_total": round((b + a).sum(), 4)})

    # client count: dimension vs clients that actually appear in the facts
    used = set(f["client_id"]) | set(s["client_id"]) | set(t["client_id"])
    cl = T["dim_client"]
    out.append({"reconciliation": "dim_client rows = distinct clients with activity",
                "table": "dim_client vs facts", "rows": len(cl),
                "rows_matching": int(cl["client_id"].isin(used).sum()),
                "stored_total": len(cl), "recomputed_total": len(used & set(cl["client_id"]))})
    df = pd.DataFrame(out)
    df["match_pct"] = (df["rows_matching"] / df["rows"] * 100).round(3)
    return df


# ===========================================================================
# IQR outliers on numeric columns with no natural upper bound
# ===========================================================================
IQR_COLUMNS = [("fact_portfolio_snapshot", "aum"), ("fact_transactions", "amount"), ("fact_fees", "amount")]
IQR_NOTE = ("Flagged does not mean wrong: AUM and dollar amounts are right-skewed by design "
            "(UHNW clients hold 100x a retail account), so IQR outliers mark big clients to review, "
            "not errors to delete. fact_transactions.amount mixes all transaction types "
            "(trades, deposits, withdrawals, fees) in one distribution.")


def iqr_outliers(T):
    out = []
    for table, col in IQR_COLUMNS:
        x = cfg.num(T[table][col]).dropna()
        q1, q3 = x.quantile(0.25), x.quantile(0.75)
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        out.append({"table": table, "column": col, "q1": round(q1, 2), "q3": round(q3, 2), "iqr": round(iqr, 2),
                    "lower_fence": round(lo, 2), "upper_fence": round(hi, 2),
                    "n_low": int((x < lo).sum()), "n_high": int((x > hi).sum()),
                    "pct_flagged": round(((x < lo) | (x > hi)).mean() * 100, 2), "note": IQR_NOTE})
    return pd.DataFrame(out)


# ===========================================================================
# Scorecard
# ===========================================================================
def scorecard(T, stage, ri, rules):
    rows = []
    for table, meta in cfg.SCHEMA.items():
        d = T[table]
        # completeness: required cells filled (structural blanks excluded by design)
        req = ([c for c in d.columns if c not in cfg.FLAG_COLUMNS.get(table, [])]
               if meta.get("required") == "all" else meta.get("required", []))
        needed = len(d) * len(req)
        filled = sum(int((~cfg.is_blank(d[c])).sum()) for c in req)
        for col, cond in meta.get("conditional_required", []):
            m = cond(d)
            needed += int(m.sum())
            filled += int((m & ~cfg.is_blank(d[col])).sum())
        # key uniqueness: primary key and business key must both be unique
        pk_u = 1 - d.duplicated(meta["pk"], keep=False).mean()
        bk_u = 1 - d.duplicated(meta["business_key"], keep=False).mean() if "business_key" in meta else 1.0
        # type validity
        ok_n = tot_n = 0
        for col, typ in meta.get("types", {}).items():
            v = cfg.valid_type(d[col], typ)
            ok_n += int((v == True).sum()); tot_n += int(v.notna().sum())  # noqa: E712
        # rule pass
        r = rules[(rules["stage"] == stage) & (rules["table"] == table)]
        rule_pass = r["passed"].sum() / r["evaluated"].sum() if r["evaluated"].sum() else 1.0
        # referential match (as child)
        x = ri[(ri["stage"] == stage) & (ri["child_table"] == table)]
        # numbers only in this column (blank when not applicable), so Excel/Power BI read it as a number
        ref_txt, ref_note = "", "no foreign keys"
        if len(x) and x["non_null_fk_rows"].sum():
            ref = (x["match_rate"] * x["non_null_fk_rows"]).sum() / x["non_null_fk_rows"].sum()
            ref_txt, ref_note = round(ref * 100, 3), f"{len(x)} relationship(s)"
        elif len(x):
            ref_note = "all foreign keys blank"
        rows.append({
            "table": table, "stage": stage, "rows": len(d),
            "pct_completeness": round(filled / needed * 100, 3) if needed else 100.0,
            "pct_key_uniqueness": round(min(pk_u, bk_u) * 100, 3),
            "pct_type_validity": round(ok_n / tot_n * 100, 3) if tot_n else 100.0,
            "pct_rule_pass": round(rule_pass * 100, 3),
            "pct_referential_match": ref_txt,
            "referential_note": ref_note,
        })
    return rows


# ===========================================================================
def main():
    cfg.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ri_all, rules_all, rec_all, iqr_all, score = [], [], [], [], []
    tables = {}
    for stage in ["raw", "clean"]:
        T = tables[stage] = cfg.read_all(stage)
        print(f"\n================ {stage.upper()} ================")

        print(f"Referential integrity ({len(cfg.RELATIONSHIPS)} relationships):")
        for child, fk, parent, key in cfg.RELATIONSHIPS:
            res = check_referential_integrity(T[child], fk, T[parent], key)
            ri_all.append({"stage": stage, "relationship": f"{child}.{fk} -> {parent}.{key}",
                           "child_table": child, "fk": fk, "parent_table": parent, "pk": key,
                           "child_rows": len(T[child]),
                           "non_null_fk_rows": res["n_nonnull"],
                           "match_rate": round(res["match_rate"], 6),
                           "orphan_rows": res["n_orphan_rows"],
                           "distinct_orphan_keys": res["distinct_orphan_keys"],
                           "null_key_rate": round(res["null_key_rate"], 6)})
            print(f"  {child + '.' + fk:<38} -> {parent:<14} match {res['match_rate']:>8.2%}  "
                  f"orphans {res['n_orphan_rows']:>7,}  distinct {res['distinct_orphan_keys']:>4}  "
                  f"null {res['null_key_rate']:.2%}")
            if stage == "clean":
                assert res["n_orphan_rows"] == 0, f"clean data still has orphans in {child}.{fk}"

        rules = rule_checks(T); rules.insert(0, "stage", stage); rules_all.append(rules)
        failed = rules[rules["failed"] > 0]
        print(f"Rule checks: {len(rules)} rules, {len(failed)} with failures")
        for _, r in failed.iterrows():
            print(f"  {r['table']:<24} {(r['column'] + ' ' + r['rule'])[:62]:<62} failed {r['failed']:>7,}")

        rec = reconciliations(T); rec.insert(0, "stage", stage); rec_all.append(rec)
        print("Reconciliations:")
        for _, r in rec.iterrows():
            print(f"  {r['reconciliation']:<52} {r['rows_matching']:>8,} / {r['rows']:>8,} ({r['match_pct']}%)")

        iq = iqr_outliers(T); iq.insert(0, "stage", stage); iqr_all.append(iq)

    ri_df = pd.DataFrame(ri_all)
    rules_df = pd.concat(rules_all, ignore_index=True)
    for stage in ["raw", "clean"]:
        score += scorecard(tables[stage], stage, ri_df, rules_df)
    sc = pd.DataFrame(score).sort_values(["table", "stage"], ascending=[True, False])

    ri_df.to_csv(cfg.REPORTS_DIR / "ri_results.csv", index=False)
    rules_df.to_csv(cfg.REPORTS_DIR / "rule_results.csv", index=False)
    pd.concat(rec_all, ignore_index=True).to_csv(cfg.REPORTS_DIR / "reconciliations.csv", index=False)
    pd.concat(iqr_all, ignore_index=True).to_csv(cfg.REPORTS_DIR / "outliers_iqr.csv", index=False)
    sc.to_csv(cfg.REPORTS_DIR / "data_quality_scorecard.csv", index=False)

    print("\nIQR outliers (clean):")
    print(pd.concat(iqr_all).query("stage == 'clean'")[["table", "column", "upper_fence", "n_high", "pct_flagged"]]
          .to_string(index=False))
    print(IQR_NOTE)
    print("\nData quality scorecard:")
    with pd.option_context("display.width", 200):
        print(sc.to_string(index=False))


if __name__ == "__main__":
    main()
