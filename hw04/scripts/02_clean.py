"""
02_clean.py  -  HW4 Part C: clean the eight Wildcat Capital tables.

Reads the raw files (never modifies them) and writes:
  data/clean/<table>.csv                 same names, same columns (+ 0/1 flag columns)
  data/audit/cleaning_log.csv            table, issue, action, rows affected, note
  data/audit/value_changes.csv           table, key column, key, column, old value, new value
  data/audit/quarantine_<set>.csv        every removed row, with the reason

One transformation at a time. After each one the script prints rows affected and a
before/after check, and ASSERTS the after-state, so it stops if a fix did not do
what the decision log claims. Step ids (D01...) refer to decision_log.md.

Order (defended in decision_log.md):
  1 load as text -> 2 type/format repairs -> 3 dimension de-dup
  -> 4 fact referential quarantine -> 5 flags -> 6 write + reconcile row counts

Usage (from the hw04 folder):  python scripts/02_clean.py
"""
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wildcat_config as cfg  # noqa: E402

LOG, CHANGES, QUARANTINE = [], [], {}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def banner(step, text):
    print(f"\n[{step}] {text}")


def log(table, issue, action, rows, note=""):
    LOG.append({"step": len(LOG) + 1, "table": table, "issue": issue, "action": action,
                "rows_affected": int(rows), "note": note})
    print(f"    -> {action}: {rows:,} rows. {note}")


def change(T, table, mask, col, new_values):
    """Apply a cell-level change and record old -> new for every changed cell."""
    d = T[table]
    key = cfg.SCHEMA[table]["pk"][0]
    mask = mask.fillna(False).astype(bool)
    if isinstance(new_values, pd.Series):
        new_values = new_values.reindex(d.index)[mask]
    else:
        new_values = pd.Series(new_values, index=d.index[mask])
    old = d.loc[mask, col]
    really = old != new_values
    CHANGES.append(pd.DataFrame({
        "table": table, "key_column": key, "key": d.loc[mask, key][really].values,
        "column": col, "old_value": old[really].values, "new_value": new_values[really].values,
    }))
    d.loc[mask, col] = new_values
    return int(really.sum())


def quarantine(T, table, mask, set_name, reason, extra=None):
    d = T[table]
    mask = mask.fillna(False).astype(bool)
    q = d.loc[mask].copy()
    if extra is not None:
        for c, v in extra.items():
            q[c] = v
    q["quarantine_reason"] = reason
    assert set_name not in QUARANTINE, f"quarantine set '{set_name}' used twice - rows would be lost"
    QUARANTINE[set_name] = (table, q)
    T[table] = d.loc[~mask].reset_index(drop=True)
    return len(q)


# ---------------------------------------------------------------------------
def main():
    cfg.CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    cfg.AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    # ---- STEP 0 / D07: load everything as text ---------------------------
    banner("D07", "Load raw tables as text (dtype=str, keep_default_na=False)")
    raw_paths = {n: cfg.raw_path(n) for n in cfg.TABLE_NAMES}
    raw_hash = {n: md5(p) for n, p in raw_paths.items()}
    T = {n: cfg.read_csv_text(p) for n, p in raw_paths.items()}
    raw_rows = {n: len(d) for n, d in T.items()}
    raw_cols = {n: list(d.columns) for n, d in T.items()}
    for n, p in raw_paths.items():
        print(f"    {n:<26} {raw_rows[n]:>8,} rows  <- {p.name}")
    log("fact_transactions", f"raw file arrived as '{raw_paths['fact_transactions'].name}'",
        "standardize file name (clean file written as fact_transactions.csv)", 0,
        f"read from {raw_paths['fact_transactions'].name}; raw file not renamed")

    # ---- D04: security_id '45.0' -> '45' ---------------------------------
    banner("D04", "fact_transactions.security_id stored as decimal text")
    tx = T["fact_transactions"]
    nb = ~cfg.is_blank(tx["security_id"])
    before_match = tx.loc[nb, "security_id"].isin(set(T["dim_security"]["security_id"])).mean()
    # every value must be a whole number, written either '45' or '45.0' (never '45.5')
    assert tx.loc[nb, "security_id"].str.strip().str.match(r"^\d+(\.0+)?$").all(), "found a non-whole security_id"
    new = tx.loc[nb, "security_id"].str.strip().str.replace(r"\.0+$", "", regex=True)
    n = change(T, "fact_transactions", nb, "security_id", new)
    tx = T["fact_transactions"]
    after_match = tx.loc[nb, "security_id"].isin(set(T["dim_security"]["security_id"])).mean()
    print(f"    before: text match to dim_security = {before_match:.1%}   after: {after_match:.1%}")
    assert tx.loc[nb, "security_id"].str.match(cfg.INT_RE).all()
    assert after_match == 1.0, "some converted security_id values have no security"
    assert (cfg.num(tx.loc[nb, "security_id"]) == cfg.num(new)).all()
    log("fact_transactions", "security_id stored as '45.0' (0% text join to dim_security)",
        "convert to whole-number text", n, "verified: 100% of converted keys exist in dim_security")

    # ---- D02: state full names -> USPS codes -----------------------------
    banner("D02", "dim_client.state full names")
    cl = T["dim_client"]
    # match full names whatever the case/spacing ('pennsylvania', ' Pennsylvania')
    lookup = {k.lower(): v for k, v in cfg.US_STATES.items()}
    key = cl["state"].str.strip().str.lower()
    m = key.isin(lookup.keys())
    pa_before = (cl["state"] == "PA").sum()
    pa_expected = pa_before + int((key[m] == "pennsylvania").sum())
    print(f"    before: {m.sum()} full names; {cl['state'].nunique()} distinct values; PA = {pa_before}")
    n = change(T, "dim_client", m, "state", key[m].map(lookup))
    cl = T["dim_client"]
    print(f"    after:  {cl['state'].nunique()} distinct values; PA = {(cl['state'] == 'PA').sum()}")
    assert cl["state"].isin(cfg.STATE_CODES).all(), "a state is still not a USPS code"
    assert (cl["state"] == "PA").sum() == pa_expected
    log("dim_client", "state written as full name (e.g. 'Pennsylvania')", "standardize to USPS code", n)

    # ---- D03: return_ytd percent strings ---------------------------------
    banner("D03", "fact_portfolio_snapshot.return_ytd stored as '9.28%'")
    sn = T["fact_portfolio_snapshot"]
    m = sn["return_ytd"].str.strip().str.endswith("%")
    pct = pd.to_numeric(sn.loc[m, "return_ytd"].str.strip().str.rstrip("%"), errors="coerce") / 100
    recomputed = (cfg.num(sn.loc[m, "benchmark_return_ytd"]) + cfg.num(sn.loc[m, "active_alpha_ytd"])).round(6)
    gap = (pct - recomputed).abs()
    print(f"    before: {m.sum()} percent strings; max |pct/100 - (benchmark + alpha)| = {gap.max():.7f}")
    assert pct.notna().all()
    # the text has 2 decimals of a percent, so it can be off by at most half of 0.01% = 0.00005
    assert (gap <= cfg.PCT_TEXT_TOL).all(), "percent value does not reconcile with benchmark + alpha"
    n = change(T, "fact_portfolio_snapshot", m, "return_ytd", recomputed.map(lambda x: f"{x:.6f}"))
    sn = T["fact_portfolio_snapshot"]
    alpha_ok = cfg.rule_snap_alpha(T)
    print(f"    after:  unparseable return_ytd = {cfg.num(sn['return_ytd']).isna().sum()}; "
          f"alpha rule pass = {alpha_ok.mean():.4%}")
    assert cfg.num(sn["return_ytd"]).notna().all()
    assert alpha_ok.all(), "alpha = return - benchmark still fails somewhere"
    log("fact_portfolio_snapshot", "return_ytd stored as percent text (e.g. '9.28%')",
        "convert to decimal = benchmark_return_ytd + active_alpha_ytd", n,
        f"reconciled to percent text within {gap.max():.7f} on every row")

    # ---- D05: negative shares on Buy rows --------------------------------
    banner("D05", "fact_transactions: Buy rows with negative shares")
    tx = T["fact_transactions"]
    sh = cfg.num(tx["shares"])
    m = sh < 0
    types = tx.loc[m, "txn_type"].unique().tolist()
    amt_ok = ((sh[m].abs() * cfg.num(tx.loc[m, "price"])).round(2) - cfg.num(tx.loc[m, "amount"])).abs() <= cfg.AMOUNT_TOL
    print(f"    before: {m.sum()} negative-share rows, types = {types}; "
          f"amount = |shares| x price on {amt_ok.mean() if m.any() else 1:.1%}")
    assert set(types) <= {"Buy"}, "negative shares on a type other than Buy - review by hand"
    assert amt_ok.all(), "a negative-share row does not reconcile to amount"
    # drop the minus sign from the text itself, so the stored precision is kept exactly
    n = change(T, "fact_transactions", m, "shares", tx.loc[m, "shares"].str.strip().str.replace(r"^-", "", regex=True))
    tx = T["fact_transactions"]
    print(f"    after:  negative shares = {(cfg.num(tx['shares']) < 0).sum()}; "
          f"amount rule pass on trades = {cfg.rule_txn_amount(T).mean():.4%}")
    assert (cfg.num(tx["shares"]).dropna() > 0).all()
    assert cfg.rule_txn_amount(T).all()
    log("fact_transactions", "Buy rows with negative shares (amount positive)",
        "convert shares to absolute value", n, "verified amount = |shares| x price for all affected rows")

    # ---- D01: near-duplicate clients -> quarantine -----------------------
    banner("D01", "dim_client near-duplicates (mis-keyed last_name)")
    cl = T["dim_client"]
    nd = cfg.SCHEMA["dim_client"]["near_dup"]
    used = set(T["fact_fees"]["client_id"]) | set(T["fact_portfolio_snapshot"]["client_id"]) | set(T["fact_transactions"]["client_id"])
    dup_to_orig = {}
    for _, grp in cl.groupby(nd["match_on"]):
        if len(grp) < 2:
            continue
        assert len(grp) == 2, "more than two copies of one client - review by hand"
        n1, n2 = grp["last_name"].str.lower().tolist()
        assert n1.startswith(n2) or n2.startswith(n1), "same client details but unrelated last names"
        # Which row is the copy? Reconcile with the facts instead of guessing from the
        # spelling: the real client has fee/snapshot/transaction history, the copy has none.
        has_facts = grp["client_id"].isin(used)
        assert has_facts.sum() == 1, "cannot tell original from copy using the fact tables"
        dup_to_orig[grp.loc[~has_facts, "client_id"].iloc[0]] = grp.loc[has_facts, "client_id"].iloc[0]
    dups = pd.Series(dup_to_orig)
    print(f"    found {len(dups)} pairs; e.g. " + ", ".join(
        f"{d} '{cl.set_index('client_id').at[d, 'last_name']}' = {o} '{cl.set_index('client_id').at[o, 'last_name']}'"
        for d, o in list(dup_to_orig.items())[:3]))
    m = cl["client_id"].isin(dups.index)
    print(f"    before: {len(cl):,} clients; business-key duplicates = "
          f"{cl.duplicated(cfg.SCHEMA['dim_client']['business_key'], keep=False).sum()}")
    # verify: every other column identical to the original; no fact activity
    other = [c for c in cl.columns if c not in ("client_id", "last_name")]
    a = cl.set_index("client_id").loc[dups.index, other]
    b = cl.set_index("client_id").loc[dups.values, other]
    assert (a.values == b.values).all(), "a near-duplicate differs from its original beyond last_name"
    assert not (set(dups.index) & used), "a near-duplicate client has fact rows - cannot quarantine safely"
    assert set(dups.values) <= used
    n = quarantine(T, "dim_client", m, "dim_client_near_duplicates",
                   "near-duplicate of matched_client_id (last_name mis-keyed; all other columns identical; no fact rows)",
                   extra={"matched_client_id": cl.loc[m, "client_id"].map(dups).values})
    cl = T["dim_client"]
    print(f"    after:  {len(cl):,} clients; business-key duplicates = "
          f"{cl.duplicated(cfg.SCHEMA['dim_client']['business_key'], keep=False).sum()}")
    assert len(cl) == raw_rows["dim_client"] - n
    assert not cl.duplicated(cfg.SCHEMA["dim_client"]["business_key"]).any()
    assert cl["client_id"].is_unique
    log("dim_client", "near-duplicate clients (same person, mis-keyed last_name)", "quarantine", n,
        (f"{len(dups)} ids from {min(dups.index, key=int)} to {max(dups.index, key=int)}; "
         "0 fact rows reference them") if len(dups) else "no near-duplicates found")

    # ---- D06: transactions with unknown client -> quarantine -------------
    banner("D06", "fact_transactions with client_id not in dim_client")
    tx = T["fact_transactions"]
    m = ~tx["client_id"].isin(set(T["dim_client"]["client_id"]))
    amt = cfg.num(tx.loc[m, "amount"]).sum()
    n_ids = tx.loc[m, "client_id"].nunique()
    rows_before = len(tx)
    print(f"    before: {m.sum()} orphan rows, {n_ids} distinct ids, amount {amt:,.2f}")
    n = quarantine(T, "fact_transactions", m, "fact_transactions_orphan_client",
                   "client_id not found in dim_client (no way to recover the right client)")
    tx = T["fact_transactions"]
    print(f"    after:  orphan rows = {(~tx['client_id'].isin(set(T['dim_client']['client_id']))).sum()}")
    assert tx["client_id"].isin(set(T["dim_client"]["client_id"])).all()
    assert len(tx) == rows_before - n, "row count after quarantine does not add up"
    log("fact_transactions", "client_id has no matching client", "quarantine", n,
        f"{n_ids} distinct client_ids; amount {amt:,.2f}")

    # ---- Flags (D08-D11) --------------------------------------------------
    # Each flag is checked on the column actually written: only "0"/"1",
    # and the count of "1" equals the rows the condition selects.
    def check_flag(df, col, expected_mask):
        assert set(df[col].unique()) <= {"0", "1"}, f"{col} has values other than 0/1"
        assert (df[col] == "1").sum() == int(expected_mask.fillna(False).sum()), f"{col} count is wrong"
        assert (df.loc[expected_mask.fillna(False).astype(bool), col] == "1").all(), f"{col} missed a row"

    banner("D08", "flag missing risk_profile")
    cl = T["dim_client"]
    blank = cfg.is_blank(cl["risk_profile"])
    cl["flag_risk_profile_missing"] = blank.astype(int).astype(str)
    check_flag(cl, "flag_risk_profile_missing", blank)
    # verify the claim in the decision log: every snapshot of these clients uses benchmark 3
    snaps = T["fact_portfolio_snapshot"]
    bench = snaps.loc[snaps["client_id"].isin(set(cl.loc[blank, "client_id"])), "benchmark_id"].unique().tolist()
    print(f"    blank risk_profile: {blank.sum()} clients; their snapshot benchmarks = {bench}")
    assert bench == ["3"], "clients with a blank risk profile are not all on benchmark 3"
    log("dim_client", "risk_profile blank (cannot infer a suitability record)", "flag (value left blank)", blank.sum(),
        "verified: all their snapshots use benchmark 3 - noted, not used to fill")

    banner("D09", "flag implausible return_ytd (|r| > 100%)")
    sn = T["fact_portfolio_snapshot"]
    cond = cfg.num(sn["return_ytd"]).abs() > cfg.RETURN_PLAUSIBLE_MAX
    sn["flag_return_implausible"] = cond.astype(int).astype(str)
    check_flag(sn, "flag_return_implausible", cond)
    log("fact_portfolio_snapshot", "|return_ytd| > 100% (small accounts, AUM jumps)", "flag (value kept)", cond.sum(),
        f"{sn.loc[cond, 'client_id'].nunique()} clients")

    banner("D10", "flag AUM at the 1,000.00 floor")
    cond = cfg.num(sn["aum"]) == cfg.AUM_FLOOR
    sn["flag_aum_at_floor"] = cond.astype(int).astype(str)
    check_flag(sn, "flag_aum_at_floor", cond)
    assert not (cfg.num(sn["aum"]) < cfg.AUM_FLOOR).any(), "AUM below the floor exists - floor logic needs review"
    log("fact_portfolio_snapshot", "aum exactly 1,000.00 (looks like a system floor)", "flag (value kept)", cond.sum(),
        f"{sn.loc[cond, 'client_id'].nunique()} clients")

    banner("D11", "flag activity after an inactive client's last snapshot")
    tx = T["fact_transactions"]
    cond = (cfg.rule_txn_not_after_close(T) == False).fillna(False)  # noqa: E712
    tx["flag_after_account_close"] = cond.astype(int).astype(str)
    check_flag(tx, "flag_after_account_close", cond)
    # edge case: an inactive client with no snapshots at all could never be flagged
    inactive = set(T["dim_client"].loc[T["dim_client"]["is_active"] == "False", "client_id"])
    no_snap = inactive - set(sn["client_id"])
    assert not (set(tx["client_id"]) & no_snap), "inactive client with transactions but no snapshots - review by hand"
    log("fact_transactions", "inactive client has transactions after last snapshot month", "flag (row kept)",
        cond.sum(), f"{tx.loc[cond, 'client_id'].nunique()} clients")

    # ---- Final checks -----------------------------------------------------
    banner("CHECK", "column layout, referential integrity, row reconciliation")
    for name in cfg.TABLE_NAMES:
        cols = list(T[name].columns)
        expected = raw_cols[name] + cfg.FLAG_COLUMNS.get(name, [])
        assert cols == expected, f"{name}: columns changed"
    for child, fk, parent, key in cfg.RELATIONSHIPS:
        c = T[child][fk]
        nbk = ~cfg.is_blank(c)
        assert c[nbk].isin(set(T[parent][key])).all(), f"orphans remain: {child}.{fk}"
    print("    every FK in every relationship matches its parent key (text match)")

    q_rows = {n: 0 for n in cfg.TABLE_NAMES}
    for set_name, (table, q) in QUARANTINE.items():
        q_rows[table] += len(q)
    recon = []
    for name in cfg.TABLE_NAMES:
        clean_n = len(T[name])
        ok = raw_rows[name] == clean_n + q_rows[name]
        recon.append((name, raw_rows[name], clean_n, q_rows[name], ok))
        print(f"    {name:<26} raw {raw_rows[name]:>8,} = clean {clean_n:>8,} + quarantined {q_rows[name]:>4}  {'OK' if ok else 'FAIL'}")
        assert ok, f"{name}: rows do not reconcile"

    # ---- Write ------------------------------------------------------------
    for name in cfg.TABLE_NAMES:
        T[name].to_csv(cfg.CLEAN_DIR / f"{name}.csv", index=False)
    for set_name, (table, q) in QUARANTINE.items():
        q.to_csv(cfg.AUDIT_DIR / f"quarantine_{set_name}.csv", index=False)
    for name, raw_n, clean_n, q_n, _ in recon:
        LOG.append({"step": len(LOG) + 1, "table": name, "issue": "row reconciliation",
                    "action": "assert raw = clean + quarantined", "rows_affected": q_n,
                    "note": f"raw {raw_n} = clean {clean_n} + quarantined {q_n}"})
    pd.DataFrame(LOG).to_csv(cfg.AUDIT_DIR / "cleaning_log.csv", index=False)
    vc = pd.concat(CHANGES, ignore_index=True)
    vc.to_csv(cfg.AUDIT_DIR / "value_changes.csv", index=False)

    # re-read what was written: same rows, raw files untouched
    for name in cfg.TABLE_NAMES:
        back = cfg.read_table(name, "clean")
        assert back.equals(T[name].reset_index(drop=True)), f"{name}: file on disk differs from what was cleaned"
        assert md5(raw_paths[name]) == raw_hash[name], f"raw file {name} was modified!"
    print(f"\nWrote {len(cfg.TABLE_NAMES)} clean tables to {cfg.CLEAN_DIR}")
    print(f"Audit: cleaning_log.csv ({len(LOG)} rows), value_changes.csv ({len(vc):,} rows), "
          f"{len(QUARANTINE)} quarantine files")
    print(vc.groupby(["table", "column"]).size().to_string())
    print("Raw files verified unchanged (MD5).")


if __name__ == "__main__":
    main()
