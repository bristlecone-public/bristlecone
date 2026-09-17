"""Extract agency-level police operating expenditure from the BJS LEMAS
"Data for Individual State and Local Agencies with 100 or More Officers" volumes.

These are the only BJS publications that print per-agency operating budgets and
that can be downloaded from bjs.ojp.gov without an ICPSR/NACJD login.

    1993  NCJ-148825  bjs_lemas93.pdf  Table 7a (local) / Table 1a (personnel)
    1997  NCJ 171681  bjs_lemas97.pdf  Table 6a (local) / Table 1a (personnel)
    2000  NCJ 203350  bjs_lemas00.pdf  Table 5a (local) / Table 1a (personnel)

Output: data/bjs/bjs_police_budgets.csv, restricted to municipal police
departments serving a city population of 100,000 or more.

Usage:  python data/bjs/extract_bjs_lemas.py
Requires: pdfplumber
"""

import csv
import os
import re
import sys

import pdfplumber

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
OUT = os.path.join(HERE, "bjs_police_budgets.csv")
RETRIEVED = "2026-09-14"

VOLUMES = [
    {
        "year": 1993,
        "pdf": "bjs_lemas93.pdf",
        "exp_table": "Table 7a",
        "ncj": "NCJ-148825",
        "url": "https://bjs.ojp.gov/content/pub/pdf/lemas93.pdf",
    },
    {
        "year": 1997,
        "pdf": "bjs_lemas97.pdf",
        "exp_table": "Table 6a",
        "ncj": "NCJ 171681",
        "url": "https://bjs.ojp.gov/content/pub/pdf/lemas97.pdf",
    },
    {
        "year": 2000,
        "pdf": "bjs_lemas00.pdf",
        "exp_table": "Table 5a",
        "ncj": "NCJ 203350",
        "url": "https://bjs.ojp.gov/content/pub/pdf/lemas00.pdf",
    },
]

STATES = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
    "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE",
    "DISTRICT OF COLUMBIA": "DC", "FLORIDA": "FL", "GEORGIA": "GA",
    "HAWAII": "HI", "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN",
    "IOWA": "IA", "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA",
    "MAINE": "ME", "MARYLAND": "MD", "MASSACHUSETTS": "MA", "MICHIGAN": "MI",
    "MINNESOTA": "MN", "MISSISSIPPI": "MS", "MISSOURI": "MO", "MONTANA": "MT",
    "NEBRASKA": "NE", "NEVADA": "NV", "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ", "NEW MEXICO": "NM", "NEW YORK": "NY",
    "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND", "OHIO": "OH",
    "OKLAHOMA": "OK", "OREGON": "OR", "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD",
    "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT",
    "VIRGINIA": "VA", "WASHINGTON": "WA", "WEST VIRGINIA": "WV",
    "WISCONSIN": "WI", "WYOMING": "WY",
}

# Agencies that are not general-purpose municipal police departments.
NON_MUNICIPAL = re.compile(
    r"\b(Sheriff|County Police|State Police|Highway Patrol|Airport|Transit|"
    r"Housing|Port |Park |Parks |Univ|University|College|School|Campus|"
    r"Capitol|Marshal|Constable|Bureau of|Department of|Division of|Tribal|"
    r"Public Safety Department|Toll|Turnpike|Harbor|Hospital|Medical|"
    r"Metro-Dade|Miami-Dade)\b",  # Metro-/Miami-Dade Police is a county force
    re.I,
)

# Agencies whose name is not simply "<city> Police".
CITY_ALIASES = {
    ("NY", "New York City"): "New York",
    ("NC", "Charlotte-Mecklenburg"): "Charlotte",
    ("NC", "Charlotte-Mecklenberg"): "Charlotte",
    ("VA", "Richmond City"): "Richmond",
}

NUM = re.compile(r"^\(?\$?-?[\d,]+\)?%?$")


def lines_from_page(page):
    """Return [(y, [word dicts sorted by x0])] for one page."""
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    rows = {}
    for w in words:
        key = round(w["top"] / 3.0)
        rows.setdefault(key, []).append(w)
    out = []
    for key in sorted(rows):
        ws = sorted(rows[key], key=lambda w: w["x0"])
        out.append((ws[0]["top"], ws))
    return out


def agency_col_x(page_lines):
    """x0 of the 'Name of agency' column header on this page."""
    for _, ws in page_lines:
        texts = [w["text"] for w in ws]
        if "County" in texts and "Name" in texts and "agency" in texts:
            i_c = texts.index("County")
            for w, t in zip(ws, texts):
                if t == "Name" and w["x0"] > ws[i_c]["x0"]:
                    return w["x0"] - 2
    return None


def split_row(ws, acol):
    """Split a data row into (county, agency, [numeric tokens])."""
    texts = [w["text"] for w in ws]
    # drop trailing footnote markers (BJS uses 'x', '*', '/a' etc.)
    while texts and texts[-1] in ("x", "*", "/a", "/b", "†", "‡"):
        texts = texts[:-1]
        ws = ws[:-1]
    # trailing run of numeric-ish tokens
    i = len(texts)
    while i > 0:
        t = texts[i - 1]
        if NUM.match(t) or t in ("---", "--", "-", "%", "$"):
            i -= 1
        else:
            break
    head, nums = ws[:i], [w["text"] for w in ws[i:]]
    county = [w["text"] for w in head if w["x0"] < acol]
    agency = [w["text"] for w in head if w["x0"] >= acol]
    return " ".join(county), " ".join(agency), nums


def clean_money(tok):
    tok = tok.replace("$", "").replace(",", "")
    if tok.startswith("(") and tok.endswith(")"):
        tok = "-" + tok[1:-1]
    try:
        return int(tok)
    except ValueError:
        return None


def merge_pct(nums):
    """Collapse standalone '%' tokens onto the preceding number."""
    out = []
    for t in nums:
        if t == "%" and out:
            out[-1] = out[-1] + "%"
        else:
            out.append(t)
    return out


def parse_table(pdf, table_label, want_local_only=True):
    """Yield (state, county, agency, [numeric tokens]) for the named table."""
    for page in pdf.pages:
        text = page.extract_text() or ""
        if not text.lstrip().startswith(table_label):
            continue
        # the 'b' tables (state agencies) have their own label, so a page that
        # starts with e.g. 'Table 5a' is always the local-agency table
        plines = lines_from_page(page)
        acol = agency_col_x(plines)
        if acol is None:
            continue
        state = None
        started = False
        for _, ws in plines:
            texts = [w["text"] for w in ws]
            line = " ".join(texts)
            if "Name" in texts and "agency" in texts and "County" in texts:
                started = True
                continue
            if not started:
                continue
            bare = re.sub(r"\(cont(inued)?\)", "", line).strip()
            if bare.upper() == bare and bare in STATES:
                state = STATES[bare]
                continue
            if state is None:
                continue
            county, agency, nums = split_row(ws, acol)
            nums = merge_pct(nums)
            if not agency or not nums:
                continue
            yield state, county, agency, nums


def key(state, county, agency):
    """Join key tolerant of 'St.'/'St', 'Mt.'/'Mt' and spacing differences
    between the personnel table and the expenditure table."""
    def norm(s):
        return re.sub(r"\s+", " ", s.replace(".", "").replace("'", "")).strip().lower()
    return (state, norm(county), norm(agency))


def city_from_agency(name):
    n = name
    n = re.sub(r"\s+(Police Department|Police Dept\.?|Police)$", "", n, flags=re.I)
    # 'Nashville Metropolitan', 'Louisville Metro' -> city name.
    # Do NOT strip a trailing 'City': Kansas City, Oklahoma City, Jersey City,
    # Salt Lake City and Daly City are the city names.
    n = re.sub(r"\s+(Metropolitan|Metro)$", "", n, flags=re.I)
    return n.strip()


# --------------------------------------------------------------------------
# FY1990 wave: BJS, Police Departments in Large Cities, 1990-2000 (NCJ 175703),
# appendix table C. Printed in constant 2000 dollars; BJS states (p. 15) that
# all monetary data were converted by multiplying by 1.3393, so nominal FY1990
# dollars are recovered by dividing by that factor.
# --------------------------------------------------------------------------
PDLC_PDF = "bjs_police_departments_large_cities_1990-2000.pdf"
PDLC_URL = "https://bjs.ojp.gov/content/pub/pdf/pdlc00.pdf"
CPI_1990_TO_2000 = 1.3393
PDLC_ROW = re.compile(r"^(.+?)\s+\(([A-Z]{2})\)\s+(.*)$")
# Appendix table C prints only the city. Where the city's police agency does not
# appear in any LEMAS volume under a "<city> Police" name, name it correctly here.
PDLC_AGENCY_NAMES = {
    # consolidated city-county; the police function is the sheriff's office
    ("FL", "Jacksonville"): "Jacksonville Sheriff's Office",
}


def parse_pdlc_appendix_c(path):
    """Yield dicts for appendix table C (62 cities of 250,000+)."""
    pdf = pdfplumber.open(path)
    out = []
    for page in pdf.pages:
        text = page.extract_text() or ""
        if "Appendix table C" not in text:
            continue
        for line in text.split("\n"):
            m = PDLC_ROW.match(line.strip())
            if not m:
                continue
            city, state, rest = m.group(1), m.group(2), m.group(3)
            toks = [t for t in rest.replace("%", "").split() if t]
            vals = []
            for t in toks:
                v = clean_money(t.replace("$", ""))
                if v is None:
                    try:
                        v = float(t)
                    except ValueError:
                        v = None
                vals.append(v)
            if len(vals) < 9 or vals[0] is None or vals[6] is None:
                continue
            total90_2000d = vals[0]
            per_sworn90_2000d = vals[6]
            out.append({
                "city": city.strip(),
                "state": state,
                "total_1990_nominal": round(total90_2000d / CPI_1990_TO_2000),
                "sworn": round(total90_2000d / per_sworn90_2000d)
                if per_sworn90_2000d else None,
                "total_2000_nominal": vals[1],
            })
    pdf.close()
    return out


def main():
    rows = []
    for vol in VOLUMES:
        path = os.path.join(RAW, vol["pdf"])
        if not os.path.exists(path):
            sys.exit("missing raw file: %s" % path)
        pdf = pdfplumber.open(path)

        # ---- personnel table (population served + full-time sworn) ----
        personnel = {}
        for state, county, agency, nums in parse_table(pdf, "Table 1a"):
            # Total | Sworn Number | Sworn Percent | Respond Number | Respond Percent
            # | population | officers per 10,000 | %chg total | %chg sworn | %chg civ
            vals = [n for n in nums]
            if len(vals) < 7:
                continue
            total_ft = clean_money(vals[0])
            sworn = clean_money(vals[1])
            pop = clean_money(vals[5])
            if sworn is None:
                continue
            personnel[key(state, county, agency)] = (sworn, pop, total_ft)

        # ---- expenditure table ----
        for state, county, agency, nums in parse_table(pdf, vol["exp_table"]):
            if not nums or not nums[0].startswith("$"):
                continue
            total = clean_money(nums[0])
            per_res = clean_money(nums[3]) if len(nums) > 3 else None
            if total is None:
                continue
            if NON_MUNICIPAL.search(agency):
                continue
            if not re.search(r"\bPolice\b", agency, re.I):
                continue
            sworn, pop, _ = personnel.get(key(state, county, agency),
                                          (None, None, None))
            if pop is None and per_res:
                pop = round(total / per_res)
            if pop is None or pop < 100000:
                continue
            rows.append({
                "agency_name": agency,
                "city": CITY_ALIASES.get((state, city_from_agency(agency)),
                                         city_from_agency(agency)),
                "state": state,
                "fiscal_year": vol["year"],
                "operating_budget_usd": total,
                "sworn_officers": sworn if sworn is not None else "",
                "source": "BJS LEMAS %d, Data for Individual State and Local "
                          "Agencies with 100 or More Officers (%s), %s"
                          % (vol["year"], vol["ncj"], vol["exp_table"]),
                "source_url": vol["url"],
                "retrieved": RETRIEVED,
            })
        pdf.close()

    # ---- FY1990 wave ----
    pdlc_path = os.path.join(RAW, PDLC_PDF)
    checks = []
    if os.path.exists(pdlc_path):
        by2000 = {(r["city"], r["state"]): r["operating_budget_usd"]
                  for r in rows if r["fiscal_year"] == 2000}
        # reuse the agency name this city's department carries in the LEMAS
        # volumes, so a city has one agency label across all four waves
        names = {}
        for r in rows:
            names.setdefault((r["city"], r["state"]), r["agency_name"])
        for rec in parse_pdlc_appendix_c(pdlc_path):
            city = CITY_ALIASES.get((rec["state"], rec["city"]), rec["city"])
            rows.append({
                "agency_name": names.get(
                    (city, rec["state"]),
                    PDLC_AGENCY_NAMES.get((rec["state"], city),
                                          "%s Police" % city)),
                "city": city,
                "state": rec["state"],
                "fiscal_year": 1990,
                "operating_budget_usd": rec["total_1990_nominal"],
                "sworn_officers": rec["sworn"] if rec["sworn"] else "",
                "source": "BJS, Police Departments in Large Cities, 1990-2000 "
                          "(NCJ 175703), appendix table C. Printed in constant "
                          "2000 dollars; converted to nominal FY1990 dollars by "
                          "dividing by BJS's stated CPI factor 1.3393. The table "
                          "prints only the city; agency name %s."
                          % ("carried over from the LEMAS volumes"
                             if (city, rec["state"]) in names
                             else "constructed"),
                "source_url": PDLC_URL,
                "retrieved": RETRIEVED,
            })
            ref = by2000.get((city, rec["state"]))
            if ref is not None and rec["total_2000_nominal"]:
                checks.append((rec["city"], rec["state"], ref,
                               rec["total_2000_nominal"]))

    rows.sort(key=lambda r: (r["state"], r["city"], r["fiscal_year"]))
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "agency_name", "city", "state", "fiscal_year",
            "operating_budget_usd", "sworn_officers",
            "source", "source_url", "retrieved"])
        w.writeheader()
        w.writerows(rows)
    print("wrote %d rows to %s" % (len(rows), OUT))
    for y in (1990, 1993, 1997, 2000):
        print("  %d: %d agencies" % (y, sum(1 for r in rows if r["fiscal_year"] == y)))
    # cross-check: the FY2000 column of appendix table C should reproduce the
    # FY2000 figures parsed independently out of the LEMAS 2000 volume
    bad = [c for c in checks if c[2] != c[3]]
    print("FY2000 cross-check vs NCJ 175703 appendix C: %d/%d matched"
          % (len(checks) - len(bad), len(checks)))
    for c in bad:
        print("   MISMATCH %s (%s): lemas00=%s  pdlc00=%s" % c)


if __name__ == "__main__":
    main()
