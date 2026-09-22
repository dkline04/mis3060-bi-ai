### 2A — Known-Answer Benchmarks (8 points)

| Check | Expected | Your Script Produced | Match? | Notes |
|---|---|---|---|---|
| Dataset shape | (298772, 9) | (298772, 9) | Yes | |
| Null count — `security_id` | 101,597 | 101,597 | Yes | |
| Null count — `amount` | 0 | 0 | Yes | |
| Unique `txn_type` values | 6 | 6 | Yes | Buy, Sell, Dividend, Deposit, Advisory Fee, Withdrawal |
| Count of `Buy` transactions | 83,556 | 83,556 | Yes | |
| `txn_date` data type | object | str | No | Same underlying meaning (unconverted text column) — pandas version difference (recent pandas reports string columns as `str` instead of the older `object` label) |
| Earliest `txn_date` | 2020-01-01 | 2020-01-01 | Yes | |
| Latest `txn_date` | 2024-12-30 | 2024-12-30 | Yes | |
| Duplicate `txn_id` count | 0 | 0 | Yes | |
| Mean `amount` | $54,075.17 | $54,075.17 | Yes | |
| Median `amount` | $41,220.48 | $41,220.49 | No | Raw median is $41,220.485 — a rounding tie-break; benchmark rounded down, script's `:.2f` formatting rounded up. Same underlying value. |
| Skewness of `amount` | 1.15 | 1.15 | Yes | |
| Correlation `shares`–`amount` | 0.65 | 0.65 | Yes | |
| Correlation `price`–`amount` | 0.64 | 0.64 | Yes | |
| Correlation `shares`–`price` | 0.00 | 0.00 | Yes | |
| Negative `shares` count (Buy only) | 836 | 836 | Yes | All 836 confirmed Buy-only |
| Profile file created | Yes | Yes | Yes | |
| Chart files created (3) | Yes | Yes | Yes | Minor matplotlib UserWarning on scatter legend — cosmetic, didn't block the save |

For any row where Match = No: describe the discrepancy and paste the Claude Cowork conversation you used to investigate it.
Investigating discrepancies — Claude Cowork conversation

Delia: My benchmark table says txn_date should be type object, but my script printed str. Is that a real problem with my data?

Claude: No — they describe the same thing. txn_date is still an unconverted text column either way; it was never parsed into a real datetime. The label difference comes from which pandas version you're running. Older pandas has always displayed plain text columns as dtype object. Newer pandas versions (2.x, with the "future string" behavior) can report the same kind of column as str instead. You can confirm which one you're on by running:

python -c "import pandas; print(pandas.__version__)"

Either label means the same thing for your analysis: txn_date needs to be explicitly converted with pd.to_datetime() before doing any time-based calculations — the benchmark's underlying point (that this column isn't a real date type yet) still holds.

Delia: What about the median amount? My script says $41,220.49, but the benchmark says $41,220.48.

Claude: Look at the raw, unrounded value in your descriptive-statistics output — the 50th percentile row shows 41220.485000. That's sitting exactly on a rounding boundary between $41,220.48 and $41,220.49. Your script formats it with Python's :.2f, which rounds that boundary value up to .49. Whoever produced the official benchmark likely rounded the same number down to .48, either by using a different rounding rule (round-half-to-even vs. round-half-up) or by truncating instead of rounding.

To confirm this is just a display/rounding artifact and not a real calculation error, you can print the unrounded value directly:

python
print(df["amount"].median())

If that returns 41220.485 (or something extremely close, accounting for floating-point representation), it confirms the underlying statistic matches the benchmark and the one-cent gap is purely how the two rounded it, not a difference in the data or the calculation.

Delia: So neither of these means anything is actually wrong with my script or my data?

Claude: Correct. Both are surface-level differences — one from a pandas version's display convention, one from a rounding tie-break — not data quality issues or bugs in your EDA logic. Worth noting in your validation write-up so a reader knows you checked rather than assumed.

### 2B — Explain the Code and Output (16 points)


1. Did Claude's predicted outputs (Prompt 1) match what you saw in the terminal?

Mostly yes, at the structural level — every section it described (shape, dtypes, missing values, descriptive stats, grouped amounts, correlation matrix, three charts) matched what the script actually printed and saved. Claude correctly predicted that amount would be right-skewed with mean > median, and that shares↔amount and price↔amount would be the strongest correlations. It couldn't predict exact numbers up front since it didn't have the real CSV.

One prediction was actually wrong: in the Prompt 1 response, Claude guessed that negative share counts would "often" appear on Sell transactions (position going down). The real data showed the opposite — all 836 negative-share rows are on Buy transactions. That mismatch is exactly what Prompt 2's review flagged as the top thing worth investigating.

2. What did Claude flag as unexpected or worth investigating (Prompt 2)?

Two real issues:

Negative shares only on Buy transactions (836 rows) — backwards from the usual convention, with no obvious business meaning on its face.
Advisory Fee's mean ($7,375) is ~8.5x its median ($859) — far more skewed than any other txn_type, suggesting either a mix of fee structures or a few extreme outliers pulling the mean up.

It also called out lower-risk items: txn_date stored as str (fine for now since ISO dates happen to sort correctly as strings, but will break real date math later), and confirmed the nulls are "missing by design," not a data problem.

3. Did Claude mention the 101,597 nulls in security_id? What explanation did it give?

Yes. It explained the null count isn't random — it lines up exactly with Deposit (35,981) + Withdrawal (29,850) + Advisory Fee (35,766) = 101,597. Those transaction types don't involve buying or selling a security, so there's nothing to populate in security_id, shares, or price for them. It explicitly called this "missing by design," not a data quality issue.

4. Did Claude flag txn_date as a concern? Why would that matter for time-series analysis?

Yes. It's stored as str, not a real datetime. Claude noted the min/max values shown (2020-01-01 to 2024-12-30) happen to be correct only because ISO-format dates (YYYY-MM-DD) sort correctly as plain text — but that's coincidental. Any actual time-series work — computing durations between transactions, resampling by month/quarter, filtering date ranges, sorting by true chronological order — would fail or silently produce wrong results until the column is converted with pd.to_datetime().

5. Do the chart images match Claude's explanation of that section?

Histogram (hist_amount.png) — Matches cleanly. Clear right-skew with a long tail out past $200K, and the mean line (red, ~$54,075) sits to the right of the median line (green, ~$41,220), exactly as predicted.

Box plot (box_amount_by_type.png) — Matches, and adds a visual to the Advisory Fee anomaly Claude flagged in Prompt 2. Advisory Fee's box is tiny and pinned near $0, with a massive stream of outlier dots stretching out past $140,000 — visually confirming the "8.5x mean/median gap" observation. The other five types show wider, more normal-looking boxes with only Sell, Dividend, and Buy having a handful of high-end outliers.

Scatter plot (scatter_shares_amount.png) — This is where there's a real discrepancy worth writing up. The legend lists all six transaction types, but the plot only visibly shows two colors: orange (Buy) on the negative-shares side, and purple (Sell) on the positive-shares side. Dividend also has non-null shares/price (53,864 rows), and the ~82,720 Buy transactions with positive shares should appear on the right side too — but neither is visible.

6. Follow up question: Should I drop the 836 negative-share Buy transactions before analysis, or keep them?

Don't drop them outright — at 0.28% of the data the stakes are low, but deleting rows is irreversible and you don't yet know if this is a data error or an intentional convention. Investigate first: look at the actual rows (do amount/price look normal?), check whether they cluster by client or advisor, and check the assignment's data dictionary in case it's intentional. If it stays unresolved, the safer default is to keep the rows in the dataset but exclude/flag them in any calculation where the sign matters, noting the reasoning in your write-up.

### 2C — Business Check & Cross-Validation (16 points)
1. `security_id`, `shares`, and `price` are all null in exactly 101,597 rows. Looking at the `txn_type` value counts, which three transaction types would you expect to have no security — and why? Do the counts add up to 101,597?

Deposit, withdrawal, and advisory fee are the three transaction types I would expect to have no security because they move cash in or out of an account or charge a fee. Since none of them involve buying ot selling a security there is no security_id to attach, or shares/price to reord. Adding their counts 35,981+29,850+35,766 = 101,597 which matches perfectly.

2. There are 83,556 Buy transactions and 59,755 Sell transactions. What does it mean for a wealth management firm to have significantly more Buys than Sells over a five-year period?

When a wealth management firm has a significantly higher buy than sell count over a five-year period it likely indicates that the firm is growing by bringing in new clients/new assets and clients are making more regular contributions. 

3. The `txn_date` column is stored as a string (type `object`) rather than a date. If Claude Cowork generated code to compute the average number of days between transactions, what would go wrong if the dates remained as strings?

If txn_date stays a string, computing the average days between transactions would either fail or produce an incorrect answer. There would be a TypeError becuase it is not a valid operation in python to subtract two strings, so a formula such as date2-date1 would not work. 

4. Wildcat Capital has 2,700 clients served by 25 advisors. Is that ratio — roughly 108 clients per advisor — plausible for a registered investment advisory firm?

I think having 108 clients served by 25 advisors could be possible for a registered investment advisory firm. These advisors could be supported by many junior staff members on the relationships with their clients so that they can ensure each individual gets attention while also maintaining a large book of business. With this being said if these clients are very complex and need a lot of financial assistance than maybe the firm is understaffed. 

5. 836 `Buy` transactions have negative `shares` values (as low as −499.63), while every other transaction type in the dataset has only positive share values. What are two plausible business explanations for a negative share count on a Buy transaction (for example, a data-entry sign error versus a legitimate correction or reversal entry), and what would you do next to determine which explanation is more likely?

One possible explanation is a data-entry error where a Buy is recorded with the share count was entered as negative by mistake when it should have been positive. Annother possibility is a legitimate correction/reversal entry where the negative-share Buy is used to reverse an earlier mistake Buy transaction. To determine which is more likely I would look at the actual rows and check whether the amount and price on these rows look normal or if they are unusual such as negative or out of the typical range. I would also check to see if each negative-share Buy has a matching original transaction it appears to reverse with similiar dates, share magnitude, and the same client. If they cluster near a specific client_id or advisor_id it may suggest a data entry issue while if they are more spread evenly throughout it could be a better indicator of convention designed to reverse entries. 

6. What did each script return?

The first script returned- Buy count (direct filter): 83556
The second script returned- Total rows: 298772 Non-Buy rows: 215216 Buy count (by subtraction): 83556

7. Do the results agree? If not, which one is wrong and why?
Yes, the results agree.


8. Why is it useful to verify a count using subtraction rather than direct filtering?
Subtraction and direct filtering use completely different logic to reach the same number. If they agree, it's strong evidence the count is correct, since it's unlikely two independent methods would both be wrong in exactly the same way. If they disagree, it  flags a potential issue like a typo in a category name or a missed transaction type that a single filter alone would never reveal, since one wrong but possible number gives no hint that anything's off.