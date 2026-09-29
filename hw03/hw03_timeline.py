"""
HW3 Part 4 - Corporate Events Timeline
MIS3060 Business Intelligence with AI | Villanova University

Joins the executive events table to the earnings table: for each executive
event, finds the nearest earnings filing for the same company, measures the
gap in days, and labels the event as before earnings, after earnings, or in
the same week. Saves hw03/corporate_events_timeline.csv and prints a summary.

Run from the repo root or hw03 folder:  python hw03/hw03_timeline.py
"""

import os

import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EARNINGS_CSV = os.path.join(SCRIPT_DIR, "earnings_history.csv")
EVENTS_CSV = os.path.join(SCRIPT_DIR, "executive_events.csv")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "corporate_events_timeline.csv")

SAME_WEEK_DAYS = 7

# Read everything as text so values like "NOT_FOUND" and CIKs with leading zeros stay intact.
earnings = pd.read_csv(EARNINGS_CSV, dtype=str)
events = pd.read_csv(EVENTS_CSV, dtype=str)

earnings["filing_date_dt"] = pd.to_datetime(earnings["filing_date"])
events["filing_date_dt"] = pd.to_datetime(events["filing_date"])

# Earnings columns get an "earnings_" prefix where they would clash with event columns.
EARNINGS_COLS = {
    "filing_date": "earnings_filing_date",
    "period": "earnings_period",
    "revenue_reported": "revenue_reported",
    "eps_diluted": "eps_diluted",
    "net_income": "net_income",
}


def timing_label(days):
    """
    days = earnings filing date minus executive event filing date.
    Positive -> the event was filed BEFORE the nearest earnings filing.
    Negative -> the event was filed AFTER it.
    """
    if pd.isna(days):
        return "no earnings data"
    if abs(days) <= SAME_WEEK_DAYS:
        return "same week"
    return "before earnings" if days > 0 else "after earnings"


rows = []
for _, event in events.iterrows():
    row = event.drop(labels=["filing_date_dt"]).to_dict()
    company_earnings = earnings[earnings["ticker"] == event["ticker"]]

    if company_earnings.empty:
        for col in EARNINGS_COLS.values():
            row[col] = "NOT_FOUND"
        row["days_to_nearest_earnings"] = None
    else:
        gaps = (company_earnings["filing_date_dt"] - event["filing_date_dt"]).dt.days
        nearest_idx = gaps.abs().idxmin()
        nearest = company_earnings.loc[nearest_idx]
        for src, dest in EARNINGS_COLS.items():
            row[dest] = nearest[src]
        row["days_to_nearest_earnings"] = int(gaps.loc[nearest_idx])

    row["event_timing"] = timing_label(row["days_to_nearest_earnings"])
    rows.append(row)

columns = (["company", "ticker", "cik", "filing_date", "event_type", "person_name",
            "title", "effective_date"] + list(EARNINGS_COLS.values())
           + ["days_to_nearest_earnings", "event_timing"])
timeline = pd.DataFrame(rows, columns=columns)
timeline["days_to_nearest_earnings"] = timeline["days_to_nearest_earnings"].astype("Int64")
timeline.to_csv(OUTPUT_CSV, index=False)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("CORPORATE EVENTS TIMELINE")
print("days_to_nearest_earnings = earnings filing date minus event filing date")
print("(positive = event came before earnings, negative = after)\n")

if timeline.empty:
    print("No executive events found for any company in the past 12 months.")
else:
    for ticker in earnings["ticker"].drop_duplicates():
        company_rows = timeline[timeline["ticker"] == ticker]
        name = earnings.loc[earnings["ticker"] == ticker, "company"].iloc[0]
        print(f"=== {name} ({ticker}) ===")
        if company_rows.empty:
            print("  No executive events in past 12 months\n")
            continue
        for _, r in company_rows.iterrows():
            days = r["days_to_nearest_earnings"]
            gap = f"{abs(days)} days {'before' if days > 0 else 'after'}" if pd.notna(days) else "n/a"
            print(f"  {r['filing_date']} | {r['event_type']:<11} | {r['person_name']:<22} | "
                  f"{r['event_timing']:<15} ({gap} earnings filed {r['earnings_filing_date']})")
        print()

print("=== ACROSS ALL FIVE COMPANIES ===")
counts = timeline["event_timing"].value_counts()
for label in ["before earnings", "after earnings", "same week", "no earnings data"]:
    if counts.get(label, 0):
        print(f"  {label:<16}: {counts.get(label, 0)}")
print(f"  {'total events':<16}: {len(timeline)}")

# Count by filing (one 8-K can report several people), so a single
# announcement with 5 names doesn't count 5 times.
filings = timeline.drop_duplicates(subset=["ticker", "filing_date"])
print("\n  Counted by 8-K filing instead of by person:")
for label, n in filings["event_timing"].value_counts().items():
    print(f"  {label:<16}: {n}")
print(f"  {'total filings':<16}: {len(filings)}")

print(f"\nSaved {len(timeline)} rows to {OUTPUT_CSV}")
