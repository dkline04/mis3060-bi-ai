"""
HW3 Part 3 - Executive Events Pipeline (SEC 8-K Item 5.02)
MIS3060 Business Intelligence with AI | Villanova University

For five companies, finds every 8-K filed in the past 12 months that reports
a change in directors or officers (Item 5.02), reads the Item 5.02 section,
and extracts one row per event: departure / appointment, person, title and
effective date. Saves the results to hw03/executive_events.csv.

Run from the repo root:  python hw03/hw03_executives.py
"""

import csv
import json
import os
import re
import time
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

HEADERS = {"User-Agent": "MIS3060 Villanova dkline04@villanova.edu"}
REQUEST_PAUSE_SECONDS = 0.2   # stay under SEC's 10 requests/second limit
LOOKBACK_DAYS = 365           # "past 12 months", measured from the day the script runs
NOT_FOUND = "NOT_FOUND"

COMPANIES = [
    {"company": "Apple Inc.",            "ticker": "AAPL", "cik": "0000320193"},
    {"company": "Microsoft Corporation", "ticker": "MSFT", "cik": "0000789019"},
    {"company": "NVIDIA Corporation",    "ticker": "NVDA", "cik": "0001045810"},
    {"company": "JPMorgan Chase & Co.",  "ticker": "JPM",  "cik": "0000019617"},
    {"company": "Walmart Inc.",          "ticker": "WMT",  "cik": "0000104169"},
]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "executive_events.csv")

CSV_COLUMNS = ["company", "ticker", "cik", "filing_date", "event_type",
               "person_name", "title", "effective_date"]


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
# Step 2: find Item 5.02 8-K filings from the past 12 months
# ---------------------------------------------------------------------------

def get_executive_filings(cik):
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    data = json.loads(sec_get(url).text)
    recent = data["filings"]["recent"]
    cutoff = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()

    # Parallel lists: position i in each list describes the same filing.
    matches = []
    for i in range(len(recent["form"])):
        items = recent["items"][i] or ""
        if (recent["form"][i] == "8-K" and "5.02" in items
                and recent["filingDate"][i] >= cutoff):
            matches.append({
                "filing_date": recent["filingDate"][i],
                "accession": recent["accessionNumber"][i],
                "primary_doc": recent["primaryDocument"][i],
            })
    matches.sort(key=lambda f: f["filing_date"], reverse=True)
    return matches


# ---------------------------------------------------------------------------
# Step 3: download the 8-K and isolate the Item 5.02 section
# ---------------------------------------------------------------------------

def document_url(cik, filing):
    return (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
            f"{filing['accession'].replace('-', '')}/{filing['primary_doc']}")


def html_to_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(" ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def item_502_section(text):
    """Text from 'Item 5.02' up to the next 'Item X.XX' heading or the signature block."""
    start = None
    for m in re.finditer(r"Item\s*5\.02", text, re.IGNORECASE):
        start = m.end()
        break
    if start is None:
        return text  # fall back to the whole document
    rest = text[start:]
    # Remove the standard item heading so its words ("Departure ... Appointment ...")
    # don't get mistaken for an actual event.
    rest = re.sub(r"^[\s.:]*Departure of Directors.{0,200}?Certain Officers\.?"
                  r"(?:\s*;?\s*Compensatory Arrangements of Certain Officers\.?)?",
                  " ", rest, flags=re.IGNORECASE)
    end = re.search(r"Item\s*\d{1,2}\.\d{2}|SIGNATURES?\b", rest)
    return rest[:end.start()] if end else rest[:8000]


# ---------------------------------------------------------------------------
# Step 4: extract events
# ---------------------------------------------------------------------------

DEPARTURE_WORDS = r"(resign\w*|retire\w*|retirement|step(?:s|ped|ping)? down|depart\w*|" \
                  r"will not stand for re-?election|not to stand for re-?election|" \
                  r"terminat\w*|leav(?:e|es|ing) the Company|separat\w*|" \
                  r"transition\w* (?:from|out of)|no longer serv\w*)"
APPOINTMENT_WORDS = r"(appoint\w*|(?<![-\w])elect(?:s|ed)?\b|named(?! executive officer)|" \
                    r"nominat\w*|promot\w*|succe(?:ed|eds|eding)|(?<!his )(?<!her )successor|hired|" \
                    r"join(?:s|ed|ing)?\b|will (?:become|serve as|assume))"

# Capitalized words that are never part of a person's name in these filings.
NOT_NAME_WORDS = set("""
Board Directors Director Company Inc Corporation Corp Co Chief Executive Officer Officers
Financial Operating Vice President Senior Chairman Chair Committee Compensation Nominating
Governance Audit General Counsel Item Form Section Exhibit Agreement Plan Annual Meeting
Shareholders Shareholder Stockholders Stockholder The On In As At By For With Effective
Following Accordingly Also Pursuant Registrant Report Current Signature Signatures
January February March April May June July August September October November December
Apple Microsoft NVIDIA Nvidia JPMorgan Chase Walmart Wal-Mart Sam's Club
United States Securities Exchange Commission Human Resources Technology Global
International Group Americas Bank Holdings Legal Retail Operations Worldwide Marketing
Services Cloud Treasurer Secretary Controller Accounting Principal Lead Independent
Commercial Consumer Community Banking Investment Asset Wealth Management Corporate Risk
Strategy Product Products Hardware Software Engineering Division Business Office Mr Ms
Mrs Dr His Her Their There This That These Upon During Prior After Before Under
Departure Election Appointment Certain Officers Arrangements Compensatory Directors
Restricted Stock Units Award Awards Letter Offer Base Salary Bonus Incentive Long-Term
Term Transition Advisor Special Development Research Supply Chain Information Security
Regulation S-K Proxy Statement Fiscal Year Separation Date Covenant Not Release Policy
Code Conduct Clawback Quarterly Proposal Proposals Vote Votes CEO CFO COO CTO CAO
PLC LLC LLP Ltd Limited Partners Capital Foundation University School
""".split())

# Words that mark an organization rather than a person.
ORG_SUFFIXES = {"PLC", "LLC", "LLP", "Ltd", "Limited", "Inc", "Corp", "Co", "Group",
                "Holdings", "Partners", "Capital", "Foundation", "University"}

NAME_TOKEN = r"(?:[A-Z][a-zA-Z'\-]+|[A-Z]\.)"
NAME_RE = re.compile(rf"\b{NAME_TOKEN}(?: {NAME_TOKEN}){{1,3}}\b")

TITLE_PATTERNS = [
    # "Senior Vice President and Chief Financial Officer", "Chief Human Resources Officer"
    r"(?:(?:Executive|Senior|Corporate) )?(?:Vice President|President)(?:,| and| &)? "
    r"(?:(?:Chief|General|Principal) [A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+){0,3} (?:Officer|Counsel))",
    r"(?:Principal |Chief |General )[A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+){0,3} (?:Officer|Counsel)",
    r"(?:Chief Executive Officer|General Counsel|Corporate Secretary|Controller|Treasurer)",
    r"(?:Executive |Senior )?Vice President(?:,? [A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z&]+){0,4})?",
    r"(?:Chairman|Chair) of the Board(?: of Directors)?",
    r"(?:Lead Independent Director)",
    r"(?:member of the Board(?: of Directors)?|(?<=as a )director|(?<=as an independent )director)",
    r"(?:Co-)?President(?: and Chief Executive Officer)?(?: of [A-Z][a-zA-Z']+(?: [A-Z][a-zA-Z']+){0,3})?",
    # Abbreviated titles: "VP and CAO", "CEO of CCB"
    r"(?-i:(?:(?:Senior |Executive )?VP (?:and|&) )?C[A-Z]{1,2}O(?: of (?:the )?[A-Z][A-Za-z&]*(?: [A-Z&][A-Za-z&]*){0,3})?)\b",
    r"(?-i:(?<=from the )Board of Directors)",
]

# A business unit written after the title: "..., Chief Executive Officer, Walmart U.S."
TITLE_SUFFIX = r"(?-i:,\s*[A-Z][\w'\u2019]+(?: [A-Z][\w'\u2019.]+){0,2})(?=\s*[,(]|\s*$)"
COMPANY_TAIL = (r"\s+of(?:\s+the)?(?:\s+(?:Company|Firm|NVIDIA(?: Corporation)?|Walmart Inc\.?"
                r"|Microsoft(?: Corporation)?|Apple(?: Inc\.?)?))?$")

DATE_RE = r"([A-Z][a-z]+ \d{1,2}, \d{4})"

ABBREVIATIONS = ["Mr.", "Ms.", "Mrs.", "Dr.", "Inc.", "Co.", "Corp.", "Jr.", "Sr.",
                 "U.S.", "No.", "St."]


def split_sentences(text):
    protected = text
    for i, abbr in enumerate(ABBREVIATIONS):
        protected = protected.replace(abbr, f"@@{i}@@")
    parts = re.split(r"(?<=[a-z0-9\)\"”%])\.\s+(?=[A-Z\"“(])", protected)
    sentences = []
    for part in parts:
        for i, abbr in enumerate(ABBREVIATIONS):
            part = part.replace(f"@@{i}@@", abbr)
        sentences.append(part.strip())
    return [s for s in sentences if s]


def find_names(sentence):
    """Return (name, start, end) for each person-like name in a sentence."""
    names = []
    for m in NAME_RE.finditer(sentence):
        tokens = m.group(0).split(" ")
        # Trim non-name words from either end, e.g. "Board appointed Jane Doe"
        while tokens and tokens[0].rstrip("'s") in NOT_NAME_WORDS:
            tokens.pop(0)
        while tokens and tokens[-1].rstrip("'s") in NOT_NAME_WORDS:
            tokens.pop()
        full_words = [t for t in tokens if not re.fullmatch(r"[A-Z]\.", t)]
        if len(full_words) < 2 or any(t in NOT_NAME_WORDS for t in tokens):
            continue
        if re.fullmatch(r"[A-Z]\.", tokens[-1]):
            continue
        name = " ".join(tokens)
        start = sentence.find(name, m.start())
        names.append((name, start, start + len(name)))
    return names


def looks_like_person(name, section, sentence="", start=0, end=0):
    """
    Keep a name only if there is evidence it is a person involved in a change:
      1. the filing refers back to them as "Mr. / Ms. <surname>", or
      2. an event word comes right after the name ("Tim Cook will transition from..."), or
      3. an event word comes right before it ("appointed Jane Doe", "succeed John Furner").
    This drops organizations from biographies, like "Tesco PLC" or "Dansk Supermarked".
    """
    if not re.search(r"\b(?:Mr|Ms|Mrs|Dr)\.", section):
        return True  # filing doesn't use honorifics; can't apply this check
    surname = name.split(" ")[-1]
    if re.search(r"\b(?:Mr|Ms|Mrs|Dr)\.\s+(?:[A-Z][a-zA-Z'\-]+\s+)?" + re.escape(surname) + r"\b",
                 section):
        return True
    after = sentence[end:end + 50]
    if re.search(DEPARTURE_WORDS + "|" + APPOINTMENT_WORDS, after, re.IGNORECASE):
        return True
    # 4. the name is followed by its title and the sentence describes a change
    #    ("Donald Robertson, Vice President and CAO, ... notified the Company of his intention to retire").
    if (re.match(r",\s*(?:the Company['\u2019]s\s+)?(?:" + "|".join(TITLE_PATTERNS) + ")",
                 sentence[end:], re.IGNORECASE)
            and re.search(DEPARTURE_WORDS + "|" + APPOINTMENT_WORDS, sentence, re.IGNORECASE)):
        return True
    before = sentence[max(0, start - 30):start]
    return re.search(r"(?:appoint\w*|elect\w*|named|succe\w*|replac\w*|from)\s*$",
                     before, re.IGNORECASE) is not None


def same_person(short, full):
    """'Di Sibio' / 'Nora Johnson' / 'John Furner' vs 'John R. Furner'."""
    if short == full:
        return True
    s_words, f_words = short.split(" "), full.split(" ")
    if " ".join(f_words[-len(s_words):]) == short:
        return True
    return s_words[0] == f_words[0] and s_words[-1] == f_words[-1]


def nearest(pattern_matches, pos_start, pos_end):
    """Pick the match closest to a name (by character distance)."""
    best, best_dist = None, None
    for m in pattern_matches:
        if m.start() >= pos_end:
            dist = m.start() - pos_end
        elif m.end() <= pos_start:
            dist = pos_start - m.end()
        else:
            continue  # overlaps the name itself
        if best_dist is None or dist < best_dist:
            best, best_dist = m, dist
    return best, best_dist


def classify(sentence, start, end, names_in_sentence=1):
    """Decide departure / appointment / both for the name at [start, end)."""
    # "succeeding Tom Brown" / "replacing Tom Brown": the named person is the one leaving.
    if re.search(r"(?:succeed\w*|replac\w*|successor to|(?:duties|responsibilities) from)\s*$",
                 sentence[max(0, start - 40):start],
                 re.IGNORECASE):
        return "departure"
    dep = list(re.finditer(DEPARTURE_WORDS, sentence, re.IGNORECASE))
    app = list(re.finditer(APPOINTMENT_WORDS, sentence, re.IGNORECASE))
    if not dep and not app:
        return None
    if dep and not app:
        # "X will transition from CEO to Executive Chair": leaves one role, takes another.
        if names_in_sentence == 1 and re.search(r"transition\w* from .{0,80}? to ", sentence):
            return "both"
        return "departure"
    if app and not dep:
        return "appointment"
    # Only one person, and the sentence describes both leaving and taking a role
    # (e.g. a promotion): that person's event is "both".
    if names_in_sentence == 1:
        return "both"
    # Both kinds of wording in one sentence: use the keyword nearest the name.
    d, d_dist = nearest(dep, start, end)
    a, a_dist = nearest(app, start, end)
    if d is None:
        return "appointment"
    if a is None:
        return "departure"
    return "departure" if d_dist <= a_dist else "appointment"


def clean_title(sentence, m):
    """Tidy a matched title: add a business unit written after it, drop 'of the Company'."""
    title = m.group(0).strip(" ,")
    unit = re.match(TITLE_SUFFIX, sentence[m.end():])
    if unit:
        title += unit.group(0).rstrip(" ,")
    return re.sub(COMPANY_TAIL, "", title).strip(" ,")


def find_title(sentence, start, end):
    # 1st choice: the NEW role, written as "... as <title>", "... become <title>" or
    # "was appointed <title>" after the name
    # ("appointed John Ternus, Senior VP of Hardware, as Chief Executive Officer").
    after = sentence[end:end + 250]
    lead_re = (r"\b(?:as|become|to|appointed|elected|named)\s+"
               r"(?:its\s+|the\s+|a\s+|an\s+|[A-Z]\w+['\u2019]s\s+)?")
    for lead in re.finditer(lead_re, after):
        rest = after[lead.end():]
        for pattern in TITLE_PATTERNS:
            m = re.match(pattern, rest, re.IGNORECASE)
            if m:
                return clean_title(rest, m)
    # Otherwise: the title mentioned closest to the name.
    matches = []
    for pattern in TITLE_PATTERNS:
        matches.extend(re.finditer(pattern, sentence, re.IGNORECASE))
    best, _ = nearest(matches, start, end)
    return clean_title(sentence, best) if best else NOT_FOUND


def defined_dates(section):
    """Dates the filing names once and then refers to by name, e.g.
    'effective September 1, 2026 (the "Transition Date")' -> {'Transition Date': 'September 1, 2026'}."""
    found = {}
    for m in re.finditer(DATE_RE + r"[^()]{0,40}?\(the [\"\u201c]([A-Z][a-z]+ Date)[\"\u201d]\)", section):
        found.setdefault(m.group(2), m.group(1))
    return found


def find_effective_date(sentence, section):
    m = re.search(r"effective (?:as of |on )?" + DATE_RE, sentence, re.IGNORECASE)
    if m:
        return m.group(1)
    # "effective on the Transition Date" - look up the date that term was defined as.
    m = re.search(r"effective (?:as of |on )?the ([A-Z][a-z]+ Date)", sentence)
    if m and m.group(1) in defined_dates(section):
        return defined_dates(section)[m.group(1)]
    m = re.search(r"(?:as of|on|from) " + DATE_RE, sentence)
    if m:
        return m.group(1)
    if re.search(r"effective immediately", sentence, re.IGNORECASE):
        return "immediately"
    m = re.search(DATE_RE, sentence)
    if m:
        return m.group(1)
    m = re.search(r"effective (?:as of |on )?" + DATE_RE, section, re.IGNORECASE)
    if m:
        return m.group(1)
    return NOT_FOUND


def extract_events(section):
    """
    Return a list of events: dicts with event_type, person_name, title, effective_date.
    One event per person. A person who both leaves one role and takes another
    (e.g. a promotion) is recorded as 'both'. Different people always get
    separate rows, so a filing with one departure and one appointment
    produces two rows.
    """
    people = {}   # name -> event dict (keeps first-mention order)

    for sentence in split_sentences(section):
        names = [n for n in find_names(sentence)
                 if looks_like_person(n[0], section, sentence, n[1], n[2])]
        for name, start, end in names:
            kind = classify(sentence, start, end, len(names))
            if kind is None:
                continue
            # Treat "Di Sibio" as the same person as "Carmine Di Sibio" seen earlier.
            existing = next((p for p in people if same_person(name, p) or same_person(p, name)), None)
            if existing is not None and len(name) > len(existing):
                people[name] = people.pop(existing)       # keep the longer, fuller name
                people[name]["person_name"] = name
                existing = name
            name = existing or name
            if name not in people:
                people[name] = {
                    "event_type": kind,
                    "person_name": name,
                    "title": find_title(sentence, start, end),
                    "effective_date": find_effective_date(sentence, section),
                }
            else:
                event = people[name]
                if event["event_type"] != kind:
                    event["event_type"] = "both"
                if event["title"] == NOT_FOUND:
                    event["title"] = find_title(sentence, start, end)
                if event["effective_date"] == NOT_FOUND:
                    event["effective_date"] = find_effective_date(sentence, section)

    # If no person joining or leaving was found, return no events. These are Item 5.02
    # filings about pay only (stock plans, bonus plans, CEO pay), and main() prints an
    # INFO line for them instead of creating an empty NOT_FOUND row.
    return list(people.values())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    rows = []

    for company in COMPANIES:
        ticker = company["ticker"]
        print(f"\n=== {company['company']} ({ticker}) ===")

        try:
            filings = get_executive_filings(company["cik"])
        except Exception as e:
            print(f"WARNING: {ticker}: could not load filing list ({e}). Skipping company.")
            continue

        if not filings:
            print(f"{ticker}: No executive events in past 12 months")
            continue

        for filing in filings:
            try:
                html = sec_get(document_url(company["cik"], filing)).text
                section = item_502_section(html_to_text(html))
                events = extract_events(section)
            except Exception as e:
                print(f"WARNING: {ticker} {filing['filing_date']}: could not process "
                      f"filing ({e}). Continuing.")
                continue

            if not events:
                print(f"INFO: {ticker} {filing['filing_date']}: Item 5.02 filing describes no "
                      f"departure or appointment (e.g. a compensation plan). No row created.")
                continue

            for event in events:
                row = {
                    "company": company["company"],
                    "ticker": ticker,
                    "cik": company["cik"],
                    "filing_date": filing["filing_date"],
                    **event,
                }
                rows.append(row)
                print(f"{ticker} | {row['filing_date']} | {row['event_type']} | "
                      f"{row['person_name']} | {row['title']}")

    # Always write the file with a header row, even if there are zero events.
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} events to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
