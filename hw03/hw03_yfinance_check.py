"""
HW3 Part 5C - Cross-validation with Yahoo Finance
Retrieves Apple's quarterly revenue and net income from yfinance to compare
against the figures extracted from the 8-K press release text.

Run from the hw03 folder:  python hw03_yfinance_check.py
"""
import yfinance as yf

TICKER = "AAPL"

income = yf.Ticker(TICKER).quarterly_income_stmt   # rows = line items, columns = quarter-end dates

print(f"{TICKER} quarterly figures from Yahoo Finance (most recent first)\n")
print(f"{'Quarter ended':<15}{'Total Revenue':>18}{'Net Income':>18}")
for quarter_end in income.columns[:4]:
    revenue = income.loc["Total Revenue", quarter_end]
    net_income = income.loc["Net Income", quarter_end]
    print(f"{str(quarter_end.date()):<15}{revenue/1e9:>16.2f} B{net_income/1e9:>16.2f} B")

latest = income.columns[0]
print(f"\nMost recent quarter: ended {latest.date()}")
print(f"  Revenue:    ${income.loc['Total Revenue', latest]:,.0f}")
print(f"  Net Income: ${income.loc['Net Income', latest]:,.0f}")
