"""
Debug helper for HW3 Part 2 / Part 5A.
Saves the plain text of each earnings press release for the tickers given,
so the wording can be inspected and the regex patterns improved.

Usage (from the hw03 folder):
  python save_press_release_text.py WMT            earnings press releases
  python save_press_release_text.py --exec AAPL    Item 5.02 sections (executive filings)
Output: hw03/raw_text/<TICKER>_<filing date>.txt  (or <TICKER>_exec_<date>.txt)
"""
import os
import sys

import hw03_earnings as e

args = sys.argv[1:]
exec_mode = "--exec" in args
tickers = [t.upper() for t in args if t != "--exec"] or ["WMT"]
out_dir = os.path.join(e.SCRIPT_DIR, "raw_text")
os.makedirs(out_dir, exist_ok=True)

if exec_mode:
    import hw03_executives as x
    for company in x.COMPANIES:
        if company["ticker"] not in tickers:
            continue
        for filing in x.get_executive_filings(company["cik"]):
            text = x.html_to_text(x.sec_get(x.document_url(company["cik"], filing)).text)
            section = x.item_502_section(text)
            path = os.path.join(out_dir, f"{company['ticker']}_exec_{filing['filing_date']}.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(section)
            print(f"Saved {path} ({len(section):,} characters)")
    sys.exit(0)

for company in e.COMPANIES:
    if company["ticker"] not in tickers:
        continue
    for filing in e.get_earnings_filings(company["cik"]):
        url = e.find_press_release(company["cik"], filing)
        if url is None:
            print(f"{company['ticker']} {filing['filing_date']}: no press release found")
            continue
        text = e.html_to_text(e.sec_get(url).text)
        path = os.path.join(out_dir, f"{company['ticker']}_{filing['filing_date']}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(url + "\n\n" + text)
        print(f"Saved {path} ({len(text):,} characters)")
