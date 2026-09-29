"""
HW3 Part 2 - Earnings Pipeline (SEC 8-K Item 2.02)
MIS3060 Business Intelligence with AI | Villanova University

For five companies, finds the four most recent 8-K filings that report
earnings (Item 2.02), downloads the earnings press release (Exhibit 99.1),
extracts revenue, diluted EPS, net income and the reporting period, and
saves the results to hw03/earnings_history.csv.

Run from the repo root:  python hw03/hw03_earnings.py
"""

import csv
import json
import os
import re
import time

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# SEC requires a User-Agent that identifies who is making the request.
HEADERS = {"User-Agent": "MIS3060 Villanova dkline04@villanova.edu"}

# SEC allows at most 10 requests per second; pause between every request.
REQUEST_PAUSE_SECONDS = 0.2

FILINGS_PER_COMPANY = 4
NOT_FOUND = "NOT_FOUND"

COMPANIES = [
    {"company": "Apple Inc.",            "ticker": "AAPL", "cik": "0000320193"},
    {"company": "Microsoft Corporation", "ticker": "MSFT", "cik": "0000789019"},
    {"company": "NVIDIA Corporation",    "ticker": "NVDA", "cik": "0001045810"},
    {"company": "JPMorgan Chase & Co.",  "ticker": "JPM",  "cik": "0000019617"},
    {"company": "Walmart Inc.",          "ticker": "WMT",  "cik": "0000104169"},
]

# Save the CSV next to this script (hw03/), no matter where it is run from.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "earnings_history.csv")

CSV_COLUMNS = ["company", "ticker", "cik", "filing_date", "period",
               "revenue_reported", "eps_diluted", "net_income"]

# The headline numbers appear near the top of a press release. Searching only
# this many characters first avoids picking up year-to-date or prior-year
# figures that appear later in the document.
HEADLINE_CHARS = 8000


# ---------------------------------------------------------------------------
# HTTP helper - the ONLY place requests.get() is called, so the User-Agent
# header and the rate-limit pause are applied to every single request.
# ---------------------------------------------------------------------------

def sec_get(url):
    time.sleep(REQUEST_PAUSE_SECONDS)
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response


# ---------------------------------------------------------------------------
# Step 2-3: find the most recent Item 2.02 8-K filings
# ---------------------------------------------------------------------------

def get_earnings_filings(cik):
    """Return the most recent 8-K filings whose items include 2.02, newest first."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    data = json.loads(sec_get(url).text)
    recent = data["filings"]["recent"]

    # The fields are parallel lists: position i in each list is the same filing.
    matches = []
    for i in range(len(recent["form"])):
        form = recent["form"][i]
        items = recent["items"][i] or ""
        if form == "8-K" and "2.02" in items:
            matches.append({
                "filing_date": recent["filingDate"][i],
                "accession": recent["accessionNumber"][i],
                "primary_doc": recent["primaryDocument"][i],
            })

    matches.sort(key=lambda f: f["filing_date"], reverse=True)
    return matches[:FILINGS_PER_COMPANY]


# ---------------------------------------------------------------------------
# Step 4: locate and download the press release exhibit
# ---------------------------------------------------------------------------

def filing_folder_url(cik, accession):
    return (f"https://www.sec.gov/Archives/edgar/data/"
            f"{int(cik)}/{accession.replace('-', '')}/")


def exhibit_991_from_index_page(cik, filing):
    """
    Read the filing's index page, which lists every document with its official
    exhibit Type (e.g. EX-99.1 = press release, EX-99.2 = presentation), and
    return the URL of the EX-99.1 document, or None.
    """
    folder = filing_folder_url(cik, filing["accession"])
    index_url = folder + filing["accession"] + "-index.htm"
    soup = BeautifulSoup(sec_get(index_url).text, "html.parser")
    for row in soup.select("table.tableFile tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        doc_type = cells[3].get_text(strip=True).upper()
        link = cells[2].find("a")
        if link is None:
            continue
        name = link.get_text(strip=True)
        if doc_type.startswith("EX-99.1") and not doc_type.startswith("EX-99.10") \
                and name.lower().endswith((".htm", ".html")):
            return folder + name
    return None


def find_press_release(cik, filing):
    """Return the URL of the earnings press release (.htm) in a filing, or None."""
    # Best source: the official exhibit type on the filing index page.
    try:
        url = exhibit_991_from_index_page(cik, filing)
        if url:
            return url
    except Exception as e:
        print(f"  note: could not read filing index page ({e}); guessing from file names")

    # Fallback: guess from the file names in the filing folder.
    folder = filing_folder_url(cik, filing["accession"])
    listing = json.loads(sec_get(folder + "index.json").text)
    files = listing.get("directory", {}).get("item", [])

    htm_files = []
    for f in files:
        name = f.get("name", "")
        lower = name.lower()
        if not lower.endswith((".htm", ".html")):
            continue
        if "index" in lower or re.fullmatch(r"r\d+\.htm", lower):
            continue  # skip EDGAR index pages and XBRL viewer pages
        if name == filing["primary_doc"]:
            continue  # the main 8-K is usually just a cover page
        try:
            size = int(f.get("size") or 0)
        except ValueError:
            size = 0
        htm_files.append((name, size))

    if not htm_files:
        return None

    # 1st choice: a file named like exhibit 99.1
    for name, _ in htm_files:
        if re.search(r"ex-?_?99[-_.]?0?1|exhibit-?_?99[-_.]?0?1|991", name.lower()):
            return folder + name
    # 2nd choice: any exhibit 99 file
    for name, _ in htm_files:
        if re.search(r"ex-?_?99|exhibit-?_?99", name.lower()):
            return folder + name
    # 3rd choice: a file that looks like a press release
    for name, _ in htm_files:
        if re.search(r"press|pr\.htm|release", name.lower()):
            return folder + name
    # Last resort: the largest remaining .htm file
    htm_files.sort(key=lambda x: x[1], reverse=True)
    return folder + htm_files[0][0]


def html_to_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(" ")
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Step 5: extract fields with regular expressions
# ---------------------------------------------------------------------------

# Words that mean a number is NOT the reported (GAAP) figure.
NON_GAAP_WORDS = ("adjusted", "non-gaap", "non gaap", "managed", "core")


def is_non_gaap(text, match_start):
    """True if the same sentence, just before a match, mentions adjusted / non-GAAP."""
    before = text[max(0, match_start - 60):match_start].lower()
    # Only look within the current sentence, not the one before it.
    for sep in (". ", "; ", "\u2022"):   # sentence end, semicolon, bullet point
        if sep in before:
            before = before.rsplit(sep, 1)[1]
    return any(re.search(r"\b" + re.escape(word) + r"\b", before)
               for word in NON_GAAP_WORDS)


def first_match(patterns, text, skip_non_gaap=True):
    """Try each pattern in order; return the first good match object or None."""
    for pattern in patterns:
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            if skip_non_gaap and is_non_gaap(text, m.start()):
                continue
            return m
    return None


def units_word(raw):
    return raw.lower() if raw else ""


def extract_period(text):
    """
    Find the reporting period. Every pattern is tried and the match that appears
    EARLIEST in the document wins, because the headline period comes first and
    later mentions are usually comparisons ("compared to the fourth quarter 2024")
    or outlook ("outlook for the first quarter of fiscal 2027").
    """
    head = text[:HEADLINE_CHARS]
    q = r"(first|second|third|fourth)"
    month_date = r"([A-Z][a-z]+ \d{1,2}, \d{4})"
    candidates = []  # (position, period text)

    # "fourth quarter fiscal 2025", "third-quarter 2025", "first quarter of fiscal year 2026",
    # "Fourth Quarter and Fiscal 2026" (NVIDIA Q4), "fourth quarter and full-year 2025"
    for m in re.finditer(q + r"[- ]quarter (?:and (?:full[- ]year )?)?(?:of )?(fiscal (?:year )?)?(\d{4})",
                         head, re.IGNORECASE):
        fiscal = "fiscal " if m.group(2) else ""
        candidates.append((m.start(), f"{m.group(1).lower()} quarter {fiscal}{m.group(3)}"))
        break

    # "fiscal 2025 fourth quarter" (Apple style)
    m = re.search(r"fiscal (?:year )?(\d{4}) " + q + r"[- ]quarter", head, re.IGNORECASE)
    if m:
        candidates.append((m.start(), f"{m.group(2).lower()} quarter fiscal {m.group(1)}"))

    # "Q2 FY26", "Q4 and FY26" (Walmart style)
    m = re.search(r"\bQ([1-4])\s?(?:and (?:full[- ]year )?)?(?:FY|fiscal year |fiscal )\s?'?(\d{2,4})\b",
                  head, re.IGNORECASE)
    if m:
        candidates.append((m.start(), f"Q{m.group(1)} FY{m.group(2)}"))

    # "second quarter ended July 27, 2025"
    m = re.search(q + r"[- ]quarter (?:ended|ending) " + month_date, head, re.IGNORECASE)
    if m:
        candidates.append((m.start(), f"{m.group(1).lower()} quarter ended {m.group(2)}"))

    # "quarter ended September 30, 2025" (Microsoft style) - only if nothing better was found
    if not candidates:
        m = re.search(r"quarter (?:ended|ending) " + month_date, head, re.IGNORECASE)
        if m:
            candidates.append((m.start(), f"quarter ended {m.group(1)}"))

    # Ignore periods mentioned as outlook / guidance ("provides outlook for Q1 and FY27").
    candidates = [c for c in candidates
                  if not re.search(r"(outlook|guidance|expect\w*|forecast)\W+(?:\w+\W+){0,2}$",
                                   head[max(0, c[0] - 40):c[0]], re.IGNORECASE)]
    candidates.sort()

    # Headline with no year, e.g. "Walmart reports Q4 results": combine the quarter
    # with the date in the income statement ("Three Months Ended January 31, 2026").
    headline = re.search(r"reports? (?:" + q + r"[- ]quarter|Q([1-4])) results", head, re.IGNORECASE)
    if headline and (not candidates or candidates[0][0] > 1000):
        ordinal = headline.group(1) or ["first", "second", "third", "fourth"][int(headline.group(2)) - 1]
        ended = re.search(r"Three Months Ended " + month_date, text, re.IGNORECASE)
        if ended:
            return f"{ordinal.lower()} quarter ended {ended.group(1)}"

    if not candidates:
        return NOT_FOUND
    return candidates[0][1]


def extract_revenue(text):
    head = text[:HEADLINE_CHARS]
    patterns = [
        # "quarterly revenue of $102.5 billion", "Revenue was $77.7 billion",
        # "revenue for the second quarter ended July 27, 2025, of $46.7 billion",
        # "Consolidated revenue of $179.5 billion", "net sales of $..."
        r"(?:revenue|net sales|total net revenue)[^$]{0,120}?\$\s?([\d,]+(?:\.\d+)?)\s?(billion|million)",
    ]
    m = first_match(patterns, head)
    if m:
        return f"{m.group(1)} {units_word(m.group(2))}"
    return NOT_FOUND


def extract_eps(text):
    head = text[:HEADLINE_CHARS]
    headline_patterns = [
        # "GAAP EPS of $0.88" (Walmart)
        r"GAAP (?:diluted )?EPS (?:of|was|were)\s?\$\s?(\d+\.\d{2})",
        # "diluted earnings per share of $1.85", "Diluted earnings per share was $3.72"
        r"diluted earnings per (?:common )?share[^$]{0,80}?\$\s?(\d+\.\d{2})",
        # "earnings per diluted share for the quarter were $1.08" (NVIDIA)
        r"earnings per diluted (?:common )?share[^$]{0,80}?\$\s?(\d+\.\d{2})",
        # "($5.07 per share)" / "EPS of $5.07" (JPMorgan)
        r"\(\$\s?(\d+\.\d{2}) per share\)",
        r"\bEPS (?:of|was|were)\s?\$\s?(\d+\.\d{2})",
    ]
    m = first_match(headline_patterns, head)
    if m:
        return m.group(1)

    # Fallback: the income statement table, e.g. "Diluted $ 1.85 $ 1.64"
    m = first_match([r"\bDiluted\s?\$\s?(\d+\.\d{2})"], text)
    if m:
        return m.group(1)
    return NOT_FOUND


def extract_net_income(text):
    head = text[:HEADLINE_CHARS]
    headline_patterns = [
        # "Net income was $27.7 billion", "net income of $14.4 billion"
        r"net income (?:attributable to [A-Za-z.,& ]{1,40} )?(?:was|of|were|totaled)\s?\$\s?([\d,]+(?:\.\d+)?)\s?(billion|million)",
    ]
    m = first_match(headline_patterns, head)
    if m:
        return f"{m.group(1)} {units_word(m.group(2))}"

    # Fallback: the income statement table, e.g. "Net income $ 27,466"
    # (first column in the table is the current quarter).
    m = first_match(
        [r"\bNet income(?: attributable to [A-Za-z.,& ]{1,40}?)?\s?\$\s?([\d,]+(?:\.\d+)?)\b"],
        text)
    if m:
        units = "million" if re.search(r"in millions", text, re.IGNORECASE) else ""
        return f"{m.group(1)} {units}".strip()
    return NOT_FOUND


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def dollars(value):
    return value if value == NOT_FOUND else f"${value}"


def print_row(row):
    print(f"{row['ticker']} | {row['period']} | "
          f"Revenue: {dollars(row['revenue_reported'])} | "
          f"EPS: {dollars(row['eps_diluted'])} | "
          f"Net Income: {dollars(row['net_income'])}")


def empty_row(company, filing_date):
    return {
        "company": company["company"],
        "ticker": company["ticker"],
        "cik": company["cik"],
        "filing_date": filing_date,
        "period": NOT_FOUND,
        "revenue_reported": NOT_FOUND,
        "eps_diluted": NOT_FOUND,
        "net_income": NOT_FOUND,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    rows = []

    for company in COMPANIES:
        ticker = company["ticker"]
        print(f"\n=== {company['company']} ({ticker}) ===")

        try:
            filings = get_earnings_filings(company["cik"])
        except Exception as e:
            print(f"WARNING: {ticker}: could not load filing list ({e}). Skipping company.")
            continue

        if not filings:
            print(f"WARNING: {ticker}: no Item 2.02 8-K filings found.")
            continue

        for filing in filings:
            row = empty_row(company, filing["filing_date"])
            try:
                pr_url = find_press_release(company["cik"], filing)
                if pr_url is None:
                    print(f"WARNING: {ticker} {filing['filing_date']}: press release "
                          f"exhibit not found. Storing NOT_FOUND and continuing.")
                    rows.append(row)
                    continue

                text = html_to_text(sec_get(pr_url).text)
                row["period"] = extract_period(text)
                row["revenue_reported"] = extract_revenue(text)
                row["eps_diluted"] = extract_eps(text)
                row["net_income"] = extract_net_income(text)

            except Exception as e:
                print(f"WARNING: {ticker} {filing['filing_date']}: could not process "
                      f"filing ({e}). Storing NOT_FOUND and continuing.")

            rows.append(row)
            print_row(row)

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
