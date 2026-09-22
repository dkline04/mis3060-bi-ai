## I need

I need a single Python script — not multiple files, one script that runs start to finish — that analyzes the file `Data/raw/fact_transactions.csv`. This file contains five years of client transaction history for Wildcat Capital: every Buy, Sell, Deposit, Withdrawal, Dividend payment, and Advisory Fee charge recorded in the portfolio system from January 2020 through December 2024.

The goal is to validate that the data loaded correctly and to understand its shape, quality, and key patterns before anyone tries to build analysis on top of it — not to answer a specific business question yet.

## The script should

1. Load `Data/raw/fact_transactions.csv` into a pandas DataFrame.
2. Print the shape of the DataFrame (number of rows and columns).
3. Print every column name along with its data type.
4. Print the count of missing (null) values for each column.
5. Print descriptive statistics — count, mean, standard deviation, minimum, 25th percentile, median, 75th percentile, and maximum — for every numeric column.
6. Print value counts and percentages for the `txn_type` column, sorted from the most frequent transaction type to the least frequent.
7. Print the number of unique clients, the number of unique advisors, and the number of unique securities referenced in the file.
8. Print the earliest and latest `txn_date` in the dataset, so I know the actual date range covered.
9. Check for duplicate rows based on `txn_id` and print how many duplicates exist.
10. Print the mean, median, and skewness of the `amount` column.
11. Group the data by `txn_type` and, for each type, print the row count and the mean and median `amount` (rounded to two decimal places). Sort this by mean amount, highest to lowest.
12. Compute the correlation matrix for the `shares`, `price`, and `amount` columns (rounded to two decimal places), print the matrix, and call out the three strongest correlations — excluding a variable's correlation with itself.
13. Print the minimum, maximum, and count of negative values in the `shares` column, broken out by `txn_type`.
14. If the DataFrame's shape is not exactly (298772, 9), print a clear warning saying so.
15. Create and save three charts to a `hw02/charts/` folder:
    - A histogram of the `amount` column with vertical lines marking the mean and the median, each clearly labeled.
    - A horizontal box plot of `amount` broken out by `txn_type`.
    - A scatter plot with `shares` on the x-axis and `amount` on the y-axis, with points colored by `txn_type`.
16. Save a plain-text summary covering everything printed in steps 2 through 13 to `hw02/hw02_profile.txt`.
17. Include a comment block at the very top of the script identifying the script's purpose, the dataset it analyzes, the author (Delia Kline), and the date it was generated.

## Constraints

- This must be **one script**, not a series of separate scripts — all 17 items need to run together in a single execution.
- I need the raw values printed to the terminal as the script runs, not just written to the output files, so I can see everything happen as it executes.
- Please don't skip the shape-check warning in step 14 even if the shape does match — the check itself should always run.
- Use pandas, matplotlib (or seaborn), and scipy as needed. Keep the code readable, since I'll need to explain what each section does afterward.
