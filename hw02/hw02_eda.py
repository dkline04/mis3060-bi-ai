"""
Script:  hw02_eda.py
Purpose: Exploratory data analysis on Wildcat Capital's five-year client
         transaction history. Validates that the dataset loaded correctly
         and characterizes its shape, missingness, distributions, and
         key relationships before any downstream analysis is built on it.
Dataset: Data/raw/fact_transactions.csv
Author:  Delia Kline
Generated: 2026-09-21
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# ---------------------------------------------------------------------------
# Paths (script is run from the repo root: `python hw02/hw02_eda.py`)
# ---------------------------------------------------------------------------
DATA_PATH = Path("Data/raw/fact_transactions.csv")
CHARTS_DIR = Path("hw02/charts")
PROFILE_PATH = Path("hw02/hw02_profile.txt")
EXPECTED_SHAPE = (298772, 9)

CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# Collects every line we print to the terminal so we can also save it
# to hw02_profile.txt (item 16) without duplicating the logic.
profile_lines = []


def emit(text=""):
    """Print to the terminal and also record it for the profile file."""
    print(text)
    profile_lines.append(str(text))


# ---------------------------------------------------------------------------
# 1. Load the data
# ---------------------------------------------------------------------------
if not DATA_PATH.exists():
    print(f"ERROR: could not find {DATA_PATH}. Check the file location and re-run.")
    sys.exit(1)

df = pd.read_csv(DATA_PATH)

# ---------------------------------------------------------------------------
# 2. Shape
# ---------------------------------------------------------------------------
emit("=" * 70)
emit("1. DATASET SHAPE")
emit("=" * 70)
emit(f"Rows: {df.shape[0]:,}   Columns: {df.shape[1]}")
emit(f"Shape: {df.shape}")
emit("")

# ---------------------------------------------------------------------------
# 3. Column names and data types
# ---------------------------------------------------------------------------
emit("=" * 70)
emit("2. COLUMN NAMES AND DATA TYPES")
emit("=" * 70)
emit(df.dtypes.to_string())
emit("")

# ---------------------------------------------------------------------------
# 4. Missing values per column
# ---------------------------------------------------------------------------
emit("=" * 70)
emit("3. MISSING VALUE COUNTS")
emit("=" * 70)
emit(df.isnull().sum().to_string())
emit("")

# ---------------------------------------------------------------------------
# 5. Descriptive statistics for numeric columns
# ---------------------------------------------------------------------------
emit("=" * 70)
emit("4. DESCRIPTIVE STATISTICS (NUMERIC COLUMNS)")
emit("=" * 70)
emit(df.describe().to_string())
emit("")

# ---------------------------------------------------------------------------
# 6. txn_type value counts and percentages
# ---------------------------------------------------------------------------
emit("=" * 70)
emit("5. TXN_TYPE VALUE COUNTS (MOST TO LEAST FREQUENT)")
emit("=" * 70)
txn_counts = df["txn_type"].value_counts()
txn_pct = df["txn_type"].value_counts(normalize=True) * 100
txn_summary = pd.DataFrame({"count": txn_counts, "percent": txn_pct.round(2)})
emit(txn_summary.to_string())
emit("")

# ---------------------------------------------------------------------------
# 7. Unique clients, advisors, securities
# ---------------------------------------------------------------------------
emit("=" * 70)
emit("6. UNIQUE ENTITY COUNTS")
emit("=" * 70)
emit(f"Unique clients:    {df['client_id'].nunique():,}")
emit(f"Unique advisors:   {df['advisor_id'].nunique():,}")
emit(f"Unique securities: {df['security_id'].nunique():,}")
emit("")

# ---------------------------------------------------------------------------
# 8. Date range
# ---------------------------------------------------------------------------
emit("=" * 70)
emit("7. TXN_DATE RANGE")
emit("=" * 70)
emit(f"Earliest txn_date: {df['txn_date'].min()}")
emit(f"Latest txn_date:   {df['txn_date'].max()}")
emit(f"(txn_date is stored as: {df['txn_date'].dtype})")
emit("")

# ---------------------------------------------------------------------------
# 9. Duplicate txn_id check
# ---------------------------------------------------------------------------
emit("=" * 70)
emit("8. DUPLICATE TXN_ID CHECK")
emit("=" * 70)
dup_count = df["txn_id"].duplicated().sum()
emit(f"Duplicate txn_id count: {dup_count}")
emit("")

# ---------------------------------------------------------------------------
# 10. Mean, median, skewness of amount
# ---------------------------------------------------------------------------
emit("=" * 70)
emit("9. AMOUNT: MEAN, MEDIAN, SKEWNESS")
emit("=" * 70)
amount_mean = df["amount"].mean()
amount_median = df["amount"].median()
amount_skew = df["amount"].skew()
emit(f"Mean amount:     ${amount_mean:,.2f}")
emit(f"Median amount:   ${amount_median:,.2f}")
emit(f"Skewness:        {amount_skew:.2f}  "
     f"({'right' if amount_skew > 0 else 'left'}-skewed)")
emit("")

# ---------------------------------------------------------------------------
# 11. Group by txn_type: count, mean, median amount (sorted desc by mean)
# ---------------------------------------------------------------------------
emit("=" * 70)
emit("10. AMOUNT BY TXN_TYPE (COUNT, MEAN, MEDIAN)")
emit("=" * 70)
grouped = (
    df.groupby("txn_type")["amount"]
    .agg(count="count", mean_amount="mean", median_amount="median")
    .round(2)
    .sort_values("mean_amount", ascending=False)
)
emit(grouped.to_string())
emit("")

# ---------------------------------------------------------------------------
# 12. Correlation matrix: shares, price, amount
# ---------------------------------------------------------------------------
emit("=" * 70)
emit("11. CORRELATION MATRIX (SHARES, PRICE, AMOUNT)")
emit("=" * 70)
corr_matrix = df[["shares", "price", "amount"]].corr().round(2)
emit(corr_matrix.to_string())
emit("")

# Find the three strongest correlations, excluding self-correlation (1.0)
pairs = []
cols = corr_matrix.columns.tolist()
for i in range(len(cols)):
    for j in range(i + 1, len(cols)):
        pairs.append((cols[i], cols[j], corr_matrix.iloc[i, j]))
pairs_sorted = sorted(pairs, key=lambda x: abs(x[2]), reverse=True)

emit("Three strongest correlations (excluding self-correlation):")
for a, b, val in pairs_sorted[:3]:
    emit(f"  {a} <-> {b}: {val:.2f}")
emit("")

# ---------------------------------------------------------------------------
# 13. Negative shares by txn_type
# ---------------------------------------------------------------------------
emit("=" * 70)
emit("12. NEGATIVE SHARES BY TXN_TYPE")
emit("=" * 70)
neg_shares = df[df["shares"] < 0]
emit(f"Overall shares — min: {df['shares'].min()}, max: {df['shares'].max()}")
emit(f"Total negative shares rows: {len(neg_shares)}")
emit("")
emit("Negative shares broken out by txn_type:")
if len(neg_shares) > 0:
    neg_by_type = neg_shares.groupby("txn_type")["shares"].agg(
        min_shares="min", max_shares="max", count="count"
    )
    emit(neg_by_type.to_string())
else:
    emit("No negative shares values found.")
emit("")

# ---------------------------------------------------------------------------
# 14. Shape warning
# ---------------------------------------------------------------------------
emit("=" * 70)
emit("13. SHAPE CHECK")
emit("=" * 70)
if df.shape != EXPECTED_SHAPE:
    emit(f"WARNING: expected shape {EXPECTED_SHAPE}, but got {df.shape}. "
         f"Investigate before using this data for analysis.")
else:
    emit(f"Shape matches expected {EXPECTED_SHAPE}. OK.")
emit("")

# ---------------------------------------------------------------------------
# 15. Charts
# ---------------------------------------------------------------------------
# Histogram of amount with mean/median lines
plt.figure(figsize=(10, 6))
plt.hist(df["amount"], bins=60, color="#4C72B0", edgecolor="white")
plt.axvline(amount_mean, color="red", linestyle="--", linewidth=2,
            label=f"Mean: ${amount_mean:,.2f}")
plt.axvline(amount_median, color="green", linestyle="--", linewidth=2,
            label=f"Median: ${amount_median:,.2f}")
plt.title("Distribution of Transaction Amount")
plt.xlabel("Amount ($)")
plt.ylabel("Frequency")
plt.legend()
plt.tight_layout()
plt.savefig(CHARTS_DIR / "hist_amount.png", dpi=150)
plt.close()

# Horizontal box plot of amount by txn_type
plt.figure(figsize=(10, 6))
df.boxplot(column="amount", by="txn_type", vert=False, grid=False)
plt.title("Amount by Transaction Type")
plt.suptitle("")
plt.xlabel("Amount ($)")
plt.ylabel("Transaction Type")
plt.tight_layout()
plt.savefig(CHARTS_DIR / "box_amount_by_type.png", dpi=150)
plt.close()

# Scatter plot: shares (x) vs amount (y), colored by txn_type
plt.figure(figsize=(10, 6))
for txn_type, group in df.groupby("txn_type"):
    plt.scatter(group["shares"], group["amount"], label=txn_type, alpha=0.4, s=10)
plt.title("Shares vs. Amount by Transaction Type")
plt.xlabel("Shares")
plt.ylabel("Amount ($)")
plt.legend(markerscale=2)
plt.tight_layout()
plt.savefig(CHARTS_DIR / "scatter_shares_amount.png", dpi=150)
plt.close()

emit("=" * 70)
emit("14. CHARTS SAVED")
emit("=" * 70)
emit(f"Saved: {CHARTS_DIR / 'hist_amount.png'}")
emit(f"Saved: {CHARTS_DIR / 'box_amount_by_type.png'}")
emit(f"Saved: {CHARTS_DIR / 'scatter_shares_amount.png'}")
emit("")

# ---------------------------------------------------------------------------
# 16. Save plain-text profile summary (items 2-13)
# ---------------------------------------------------------------------------
with open(PROFILE_PATH, "w") as f:
    f.write("\n".join(profile_lines))

print("=" * 70)
print(f"Profile summary saved to: {PROFILE_PATH}")
print("=" * 70)