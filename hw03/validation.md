# HW3 Part 5: Validation

## 5A: Known-Answer Check (Earnings)

**Company / quarter checked:** Apple Inc. (AAPL), third quarter fiscal 2026 (quarter ended June 27, 2026; results released July 30, 2026)

| Check | Official Source | Your CSV | Match? |
|---|---|---|---|
| Apple Q3 FY2026 Revenue | $109.4 billion ([Apple Newsroom, July 30, 2026](https://www.apple.com/newsroom/2026/07/apple-reports-third-quarter-results/)) | 109.4 billion | ✅ Yes |
| Apple Q3 FY2026 EPS Diluted | $2.02 ([Apple Newsroom, July 30, 2026](https://www.apple.com/newsroom/2026/07/apple-reports-third-quarter-results/)) | 2.02 | ✅ Yes |

Both values match exactly, so no regex change was needed for Apple.

**Discrepancy found and fixed elsewhere: Walmart.** On the first run, all four Walmart rows had `eps_diluted = NOT_FOUND`, and the revenue and net income were wrong (for example, $674.5 billion "revenue" and about $20 billion quarterly net income, when Walmart's quarterly net income is about $4–7 billion). After saving the raw text of the documents, I found three causes:

| Problem | Before | After | Fixed? |
|---|---|---|---|
| Wrong document | The press release was picked by file name; the word `earnings` matched Walmart's investor **presentation** (Exhibit 99.2), whose first numbers are guidance and prior-year figures | The exhibit is picked by its official type (`EX-99.1`) from the SEC filing index page | ✅ Yes |
| EPS not found | `GAAP EPS of $0.80` was skipped because the "adjusted / non-GAAP" check looked back 60 characters, crossing into the previous bullet ("...up 17.4% adjusted") | The look-back stops at the start of the current sentence *or bullet point* (`•`) | ✅ Yes |
| Period mislabeled | Headline "Walmart reports Q4 results" has no year, so the script used "outlook for Q1 and FY27" | Outlook/guidance mentions are ignored; a yearless headline is combined with the "Three Months Ended [date]" table heading | ✅ Yes |

Walmart after the fix: Q2 FY27 (quarter ended July 31, 2026) = revenue $187.9 billion, GAAP EPS $0.80, net income $6,366 million.

## 5B: Known-Answer Check (Executive Events)

**Event checked:** Apple, filed 2026-04-20: `both | Tim Cook | Chief Executive Officer | September 1, 2026`

| Check | News Source Confirms? | Notes |
|---|---|---|
| Person name and title | ✅ Yes | Tim Cook, Chief Executive Officer. Apple's announcement confirms he moves from CEO to Executive Chairman of the Board ([Apple Newsroom, April 20, 2026](https://www.apple.com/newsroom/2026/04/tim-cook-to-become-apple-executive-chairman-john-ternus-to-become-apple-ceo/)). The CSV title is the role he is leaving. |
| Event type (departure/appointment) | ✅ Yes | `both` is correct: he departs as CEO and is appointed Executive Chair. The same 8-K appoints John Ternus as CEO, which the pipeline captured as a separate appointment row (effective September 1, 2026) ([9to5Mac](https://9to5mac.com/2026/04/20/apple-ceo-tim-cook-stepping-down-john-ternus-confirmed-as-new-apple-ceo/)). |
| Effective date | ✅ Yes | September 1, 2026, per Apple's announcement. |

## 5C: Cross-Validation (Yahoo Finance)

Company and quarter: Apple, quarter ended June 27, 2026 (Q3 FY2026). Script: `hw03_yfinance_check.py`

| Metric | From 8-K text extraction | From yfinance | Match? |
|---|---|---|---|
| Revenue | $109.4 billion | $109,417,000,000 ($109.42 billion) | ✅ Yes (the press release rounds to one decimal) |
| Net Income | $29,789 million | $29,789,000,000 | ✅ Yes (exact) |

The two sources agree. The only difference is a labeling one: yfinance labels the quarter **2026-06-30** (calendar month-end), while Apple's fiscal quarter actually ended **June 27, 2026** (Apple's fiscal quarters end on the last Saturday of the quarter). yfinance also matched the other three Apple quarters in `earnings_history.csv`: $111.18B / $29.58B, $143.76B / $42.10B and $102.47B / $27.47B match the extracted $111.2B / $29,578M, $143.8B / $42,097M and $102.5B / $27,466M.

## 5D: Pipeline Integrity Checks

| Check | Expected | Actual | Pass/Fail |
|---|---|---|---|
| `earnings_history.csv` row count | Up to 20 (5 companies × 4 quarters) | 20 | ✅ Pass |
| `executive_events.csv` row count | At least 0 (document actual) | 29 | ✅ Pass |
| `corporate_events_timeline.csv` created | Yes | Yes (29 rows, one per executive event) | ✅ Pass |
| Rows with all three fields `"NOT_FOUND"` | 0 (investigate if > 0) | 0 | ✅ Pass |

**Spot-check of the executive events against the raw text.** I saved the Item 5.02 text for all 19 filings (`save_press_release_text.py --exec`, files in `raw_text/`) and compared them to the CSV. This found problems that the row counts didn't show, so I fixed the script and reran it (the earlier run had 31 rows):

| Problem found | Fix | Result |
|---|---|---|
| 3 rows with `person_name = NOT_FOUND` (Microsoft 2025-12-08, NVIDIA 2026-03-06, JPMorgan 2026-01-22) | Reading the text showed these filings are only about pay: Microsoft's 2026 Stock Plan, NVIDIA's FY2027 bonus plan, and Jamie Dimon's 2025 compensation. No one joins or leaves. The script now prints an `INFO` line for these instead of making a row | Removed (not real executive changes) |
| NVIDIA CAO Donald Robertson's retirement (2026-04-27) was missed | A name followed by its title ("Donald Robertson, Vice President ... and Chief Accounting Officer") now counts as a person when the sentence has an event word | Added as a departure |
| John Ternus's effective date was "April 17, 2026" (the day the board voted) | "effective on the Transition Date" is now looked up as the date defined earlier (September 1, 2026) | Fixed |
| Walmart titles were cut off (Guggina was just "President"; Nicholas and Watkins had the same generic title and a Jan 16 date) | Titles now keep the business unit (Walmart U.S., Walmart International, Sam's Club U.S.), and "the Effective Date" is looked up (February 1, 2026) | Fixed |
| Missing or messy titles: Gawel, Drell, Lake (`NOT_FOUND`), Petno and Rohrbaugh ("President"), Parker ("...of the") | Added abbreviated titles (VP and CAO, CEO of CCB), Co-President, "Board of Directors", and removed trailing "of the Company" | Fixed |
| Ajay Puri was `both` because "his successor" counted as an appointment word | "his/her successor" no longer counts as an appointment | Now `departure` |

Remaining known limitations: Puri's effective date is the day he gave notice (June 28, 2026), because his retirement takes effect "upon the employment commencement date of his successor" rather than on a specific date. Marianne Lake's effective date is `NOT_FOUND` because the filing doesn't give one. John Furner appears twice, which is correct: the 2025-11-14 filing announces his promotion to Walmart Inc. CEO, and the 2026-01-16 filing reports him leaving the Walmart U.S. CEO role.
