# HW3 Specifications
MIS3060 Business Intelligence with AI | Delia Kline

---

## Specification A: Earnings Pipeline (Item 2.02)

Write a Python script saved as `hw03/hw03_earnings.py` that builds a table of quarterly earnings figures from SEC 8-K earnings press releases. Use only the `requests`, `beautifulsoup4`, `re`, `csv`, `time`, and `json` libraries.

**Companies.** Process these five companies, using these CIK numbers exactly as written:

| Company | Ticker | CIK |
|---|---|---|
| Apple Inc. | AAPL | 0000320193 |
| Microsoft Corporation | MSFT | 0000789019 |
| NVIDIA Corporation | NVDA | 0001045810 |
| JPMorgan Chase & Co. | JPM | 0000019617 |
| Walmart Inc. | WMT | 0000104169 |

**1. Identify yourself to the SEC.** Every HTTP request must send the header `User-Agent: MIS3060 Villanova dkline04@villanova.edu`. Put the headers in one variable and pass it on *every* `requests.get()` call, not just the first. Wait at least 0.2 seconds between requests to stay under the SEC's limit of 10 requests per second.

**2. Find the earnings filings.** For each company, download `https://data.sec.gov/submissions/CIK{cik}.json`, using the 10-digit CIK with leading zeros. The filings are under `filings.recent` as parallel lists (`form`, `filingDate`, `accessionNumber`, `items`, `primaryDocument`): the same position in each list describes the same filing. Keep only filings where `form` is `"8-K"` and the `items` text *contains* `"2.02"`. The field can hold several items, such as `"2.02,9.01"`, so don't test for an exact match.

**3. Take the four most recent.** Sort the matching filings newest first by `filingDate` and keep the first four, one per quarter.

**4. Find and download the press release.** For each filing, build the filing folder URL:
`https://www.sec.gov/Archives/edgar/data/{cik without leading zeros}/{accession number without dashes}/`
Get the list of files in that filing, for example from `index.json` in that folder. The press release is usually a separate exhibit (Exhibit 99.1), not the main 8-K document. Pick the `.htm` file whose name suggests exhibit 99.1 (for example, it contains `ex99`, `ex-99`, `exhibit99`, or `991`). If no such file exists, fall back to the largest `.htm` file that is not the main 8-K document. Download it and use BeautifulSoup to convert the HTML to plain text, collapsing extra whitespace.

**5. Extract the numbers.** Use regular expressions on the plain text to extract:
- `period`: the reporting period in words, such as "fourth quarter fiscal 2024" or "second quarter 2025"
- `revenue_reported`: quarterly revenue (or "net sales" or "total net revenue"), keeping the units as written, for example `"$94.9 billion"` or `"$24,050 million"`
- `eps_diluted`: diluted earnings per share, for example `"1.64"`
- `net_income`: net income for the quarter, keeping units

Companies word these differently. Try several patterns per field, in order, and use the first match. Only search the first part of the document, where the headline figures appear, so year-to-date or prior-year numbers aren't picked up by mistake.

**6. Print progress.** After each filing, print one line in this format:
`[Ticker] | [Period] | Revenue: $X | EPS: $X | Net Income: $X`

**7. Save the results.** Write all rows to `hw03/earnings_history.csv` with these columns, in this order:
`company, ticker, cik, filing_date, period, revenue_reported, eps_diluted, net_income`
When finished, print a confirmation with the number of rows saved.

**8. Handle missing data and errors without crashing.**
- If a field can't be extracted (the regex finds no match), store the text `"NOT_FOUND"`. Never use `None` or leave the cell blank: a blank cell and data we looked for but couldn't find are two different things.
- If a filing's press release can't be found or downloaded, print a warning naming the ticker and filing date, then continue to the next filing. Don't stop the script.
- Wrap each company and each filing in error handling so one failure never ends the whole run.

---

## Specification B: Executive Events Pipeline (Item 5.02)

Write a Python script saved as `hw03/hw03_executives.py` that builds a table of executive and director departures and appointments from SEC 8-K filings. Use only the `requests`, `beautifulsoup4`, `re`, `csv`, `time`, `json`, and `datetime` libraries.

**Companies.** The same five companies and CIK numbers as Specification A: AAPL 0000320193, MSFT 0000789019, NVDA 0001045810, JPM 0000019617, WMT 0000104169.

**1. Identify yourself to the SEC.** Send `User-Agent: MIS3060 Villanova dkline04@villanova.edu` on every request, using one shared headers variable. Wait at least 0.2 seconds between requests.

**2. Find the executive-change filings.** For each company, download `https://data.sec.gov/submissions/CIK{cik}.json` and read the parallel lists under `filings.recent`. Keep filings where `form` is `"8-K"`, the `items` text contains `"5.02"`, and `filingDate` falls within the 12 months before the day the script runs. Calculate that date with `datetime`; don't hard-code it.

**3. Download and read each filing.** Build the document URL:
`https://www.sec.gov/Archives/edgar/data/{cik without leading zeros}/{accession number without dashes}/{primaryDocument}`
Item 5.02 information is normally in the main 8-K document itself. Download it and convert the HTML to plain text with BeautifulSoup. Focus on the section that starts at "Item 5.02" and ends at the next "Item" heading.

**4. Extract each event.** From that section, extract:
- `event_type`: `"departure"` (wording such as resign, retire, step down, depart, will not stand for re-election), `"appointment"` (wording such as appoint, elect, named, promote, succeed), or `"both"` if the text describes a change but the departure and appointment can't be separated into distinct people
- `person_name`: the person's full name
- `title`: their title or role (for example, "Chief Financial Officer" or "member of the Board of Directors")
- `effective_date`: the date the change takes effect, as written in the text

If a field can't be extracted, store `"NOT_FOUND"`, never blank or `None`.

**5. One row per event.** If a filing describes more than one event (for example, one person leaving and another appointed to replace them), create a **separate row for each person and event**. A filing with both a departure and an appointment must produce two rows.

**6. Print progress.** For each event, print:
`[Ticker] | [Date] | [Event Type] | [Name] | [Title]`

**7. Companies with no events.** If a company has no Item 5.02 filings in the past 12 months, print `[Ticker]: No executive events in past 12 months` and move on. This is valid data, not an error, and must not crash the script.

**8. Save the results.** Write all events to `hw03/executive_events.csv` with these columns, in this order:
`company, ticker, cik, filing_date, event_type, person_name, title, effective_date`
Always create the file with a header row, even if there are zero events. When finished, print a confirmation with the number of events saved.

**9. Error handling.** If one filing can't be downloaded or parsed, print a warning and continue. One bad filing must never stop the script.
.\.venv\Scripts\Activate.ps1