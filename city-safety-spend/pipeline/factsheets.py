"""One-page fact sheet per city (Phase 2, item 4C).

The roadmap asked for a download button on the dashboard. The published-artifact sandbox blocks any
download a page starts itself, so instead: every city gets a static, self-contained HTML page here
(no script, inline CSS, prints cleanly), and the dashboard carries a print stylesheet so the selected
city prints as the same sheet.

Run: python pipeline/factsheets.py   ->  site/factsheets/index.html + one page per city
"""
import csv, datetime, html, os, re, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build, cpi
from compare_vera import norm

OUT = os.path.join(build.ROOT, "site", "factsheets")
HIST = (1972, 1982, 1992, 2002, 2012, 2017, 2022, 2024)
INV = {v: k for k, v in build.FIPS_STATE.items()}


def rd(name, out=True):
    p = os.path.join(build.OUT if out else os.path.join(build.ROOT, "data"), name)
    return list(csv.DictReader(open(p, encoding="utf-8-sig"))) if os.path.exists(p) else []


def fmt_money(v):
    if v in (None, "", 0):
        return "&ndash;" if v in (None, "") else "$0"
    v = float(v)
    return f"${v/1e9:,.2f}B" if abs(v) >= 1e9 else f"${v/1e6:,.0f}M" if abs(v) >= 1e6 else f"${v:,.0f}"


def pct(v, d=1):
    return "&ndash;" if v in (None, "") else f"{float(v):.{d}f}%"


def usd(v):
    return "&ndash;" if v in (None, "") else "$" + f"{float(v):,.0f}"


def per1k(rec, key):
    v = (rec or {}).get(key)
    return f"{float(v):.2f}" if v not in (None, "") else "&ndash;"


def slug(city, state):
    return re.sub(r"[^a-z0-9]+", "-", f"{state} {city}".lower()).strip("-")


CSS = """
:root{--ink:#1A2129;--ink2:#4B5560;--muted:#7C8792;--line:#D9DDD5;--surface:#fff;--bg:#F4F5F1;--police:#2E62A8;--fire:#B07414;--warn:#7A4E00;--warnbg:#FBEFD6}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 "Public Sans",system-ui,-apple-system,"Segoe UI",sans-serif;padding:28px 20px 60px}
.wrap{max-width:860px;margin:0 auto;background:var(--surface);border:1px solid var(--line);padding:28px 32px}
.eyebrow{font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);font-weight:700}
h1{font-family:Newsreader,Georgia,serif;font-weight:500;font-size:32px;margin:6px 0 2px;line-height:1.1}
h2{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:26px 0 8px;font-weight:700;border-top:1px solid var(--line);padding-top:10px}
p.sub{color:var(--muted);margin:0 0 4px}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;margin:0}
th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line);font-size:13px}
th{font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);font-weight:700}
td.num,th.num{text-align:right}
tr.me td{font-weight:700;background:#F0F4FA}
.cap{font-size:12px;color:var(--muted);margin:6px 0 0}
.warn{background:var(--warnbg);color:var(--warn);padding:9px 12px;font-size:12.5px;margin:10px 0 0;border-left:3px solid var(--warn)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:0 26px}
@media(max-width:700px){.two{grid-template-columns:1fr}}
a{color:var(--police)}
footer{margin-top:24px;border-top:1px solid var(--line);padding-top:10px;font-size:11.5px;color:var(--muted)}
.nav{font-size:12px;color:var(--muted);margin:0 0 14px}
.nav a{color:var(--police);text-decoration:none;border-bottom:1px solid #C9D6E8}
.nav a:hover{border-bottom-color:var(--police)}
@media print{.nav{display:none}}
@media print{body{padding:0;background:#fff}.wrap{border:0;padding:0;max-width:none}}
"""


def main():
    os.makedirs(OUT, exist_ok=True)
    wide = {r["pid"]: r for r in rd("city_police_fire_2022.csv")}
    flags = {r["pid"]: r for r in rd("city_flags.csv")}
    rpp = {r["pid"]: r for r in rd("city_rpp.csv")}
    emp = collections.defaultdict(dict)
    for r in rd("city_employment_all_years.csv"):
        emp[r["pid"]][int(r["year"])] = r
    crime = collections.defaultdict(dict)
    for r in rd("city_crime.csv"):
        crime[r["pid"]][int(r["year"])] = r
    alloc = {r["pid"]: r for r in rd("city_county_allocation.csv") if r["fiscal_year"] == "2022"}
    peers = collections.defaultdict(list)
    for r in rd("peer_groups.csv"):
        peers[r["pid"]].append(r)
    longs = collections.defaultdict(dict)
    for r in rd("city_police_fire_1967_2024_long.csv"):
        longs[r["place_geoid"]][int(r["fiscal_year"])] = r
    issues = collections.defaultdict(list)
    for r in rd("known_issues.csv", out=False):
        issues[r["pid"]].append(r)
    verified = {}
    sc = os.path.join(build.ROOT, "validation", "spotcheck_vs_census.csv")
    if os.path.exists(sc):
        for r in csv.DictReader(open(sc, encoding="utf-8-sig")):
            if r["ratio_police"] and r["framing"].startswith(("general_fund", "all_funds")):
                verified.setdefault((norm(r["city"]), r["state"]), r)
    base = cpi.base_year()
    index = []
    for pid, r in sorted(wide.items(), key=lambda kv: -int(kv[1]["population"])):
        city, state = r["city"], r["state"]
        gid = INV[state] + r["fips_place"].zfill(5)
        f, rp, a = flags.get(pid, {}), rpp.get(pid, {}), alloc.get(pid, {})
        L = longs.get(gid, {})
        e22, e25 = emp[pid].get(2022), emp[pid].get(max(emp[pid])) if emp[pid] else None
        h = []
        h.append('<p class="nav"><a href="../findings.html">What the numbers show</a> &middot; <a href="index.html">All cities</a></p>')
        h.append(f'<div class="eyebrow">City fact sheet &middot; police and fire spending</div>')
        h.append(f"<h1>{html.escape(city)}, {state}</h1>")
        h.append(f'<p class="sub">Population {int(r["population"]):,} &middot; Census fiscal year 2022 &middot; '
                 f'{html.escape(rp.get("cbsa_title",""))} &middot; metro price level {float(rp["rpp_2022"]):.1f} (U.S. = 100)</p>')

        # headline
        pf = int(r["police_usd"]) + int(r["fire_usd"])
        rows = [("Police (item 62)", fmt_money(r["police_usd"]), ""), ("Fire (item 24)", fmt_money(r["fire_usd"]), ""),
                ("Police + fire", fmt_money(pf), ""),
                ("Share of general expenditure", pct(r["police_fire_pct_general"]), fmt_money(r["general_expenditure_usd"])),
                ("Share of core municipal expenditure", pct(r["police_fire_pct_core"]), fmt_money(r["core_municipal_expenditure_usd"])),
                ("Share of general expenditure excluding education", pct(r["police_fire_pct_general_ex_edu"]), fmt_money(r["general_ex_education_usd"])),
                ("Share of total expenditure", pct(r["police_fire_pct_total"]), fmt_money(r["total_expenditure_usd"]))]
        l22 = L.get(2022, {})
        rows += [(f"Per resident, {base} dollars", usd(l22.get("police_fire_real_per_resident")), ""),
                 (f"Per resident, adjusted for regional prices", usd(l22.get("police_fire_real_rpp_per_resident")), "")]
        h.append("<h2>2022 at a glance</h2><table><tbody>" + "".join(
            f'<tr><td>{k}</td><td class="num">{v}</td><td class="num">{d}</td></tr>' for k, v, d in rows) + "</tbody></table>")
        h.append('<p class="cap">Denominators are defined in the methodology; none is the "general fund" share quoted in budget messages, '
                 'which is typically two to three times higher and is not comparable between cities.</p>')

        # data quality
        notes = []
        # the flags note repeats any known-issue text, which is rendered separately below
        flagnote = re.split(r";?\s*(?:verified|possible) issue:", f.get("note", ""))[0].strip(" ;")
        if flagnote:
            notes.append(html.escape(flagnote))
        v = verified.get((norm(city), state))
        if v:
            notes.append(f"Checked against the city's own FY2022 budget schedule: Census police is {float(v['ratio_police']):.2f} times "
                         f"and fire {float(v['ratio_fire']):.2f} times the department figures.")
        else:
            notes.append("This city is not in the 29-city check against cities' own budgets, so how closely Census tracks it is unverified.")
        for i in issues.get(pid, []):
            notes.append(("Verified issue: " if i["status"] == "verified" else "Possible issue: ") + html.escape(i["finding"]))
        h.append("<h2>Data quality</h2>" + "".join(f'<p class="warn">{n}</p>' for n in notes))
        h.append(f'<p class="cap">Census imputation flags for 2022: police <code>{r["police_flags"]}</code>, fire <code>{r["fire_flags"]}</code> '
                 "(R reported, I imputed, A analyst correction, S alternative source). Police and fire figures typically agree with a city's own "
                 "budget within about 7%, so a share of 25% carries roughly two points of uncertainty.</p>")

        h.append('<div class="two">')
        # staffing
        if e22:
            cols = [x for x in (e22, e25 if e25 and e25 is not e22 else None) if x]
            h.append("<div><h2>Staffing, full-time, March</h2><table><thead><tr><th></th>" +
                     "".join(f'<th class="num">{c["year"]}</th>' for c in cols) + "</tr></thead><tbody>" +
                     "".join(f'<tr><td>{lab}</td>' + "".join(f'<td class="num">{fn(c)}</td>' for c in cols) + "</tr>"
                             for lab, fn in (("Sworn officers", lambda c: f'{int(c["police_sworn_ft"]):,}'),
                                             ("Per 1,000 residents", lambda c: per1k(c, "sworn_per_1k")),
                                             ("Firefighters", lambda c: f'{int(c["fire_firefighters_ft"]):,}'),
                                             ("Per 1,000 residents", lambda c: per1k(c, "firefighters_per_1k")),
                                             (f"Officer pay, {base} dollars", lambda c: usd(c["sworn_pay_annualized_real_usd"])))) +
                     "</tbody></table><p class=\"cap\">Census employment survey. Pay is March gross payroll per officer times 12, including "
                     "overtime; it excludes pension and benefit costs.</p></div>")
        # crime
        cr = crime.get(pid, {})
        ys = [y for y in (2019, 2022, 2024) if y in cr]
        if ys:
            def cell(y, k):
                row = cr[y]
                if row["coverage"] == "missing": return "not reported"
                if row["coverage"] == "not_city": return "n/a"
                if row["coverage"] == "partial": return "partial"
                return (f'{float(row[k]):.1f}' if row[k] else "&ndash;") + ("*" if row[k] and row["consistency"] else "")
            h.append("<div><h2>Reported crime (FBI)</h2><table><thead><tr><th></th>" +
                     "".join(f'<th class="num">{y}</th>' for y in ys) + "</tr></thead><tbody>" +
                     f'<tr><td>Violent per 1,000</td>' + "".join(f'<td class="num">{cell(y,"violent_per_1k")}</td>' for y in ys) + "</tr>" +
                     f'<tr><td>Property per 1,000</td>' + "".join(f'<td class="num">{cell(y,"property_per_1k")}</td>' for y in ys) + "</tr>" +
                     f'<tr><td>Murders per 100,000</td>' + "".join(f'<td class="num">{cell(y,"murder_per_100k")}</td>' for y in ys) + "</tr>" +
                     "</tbody></table><p class=\"cap\">Offenses known to the city's police, per resident. "
                     "* breaks sharply from the city's own 2015-2019 level, which after the 2021 reporting change often means an incomplete "
                     "submission. Context beside spending, not a measure of whether spending works.</p></div>")
        h.append("</div>")

        # county justice
        if a:
            g = lambda k: float(a[k]) if a.get(k) not in ("", None) else None
            items = [("Police and fire (city)", g("police_usd") + g("fire_usd")), ("Jails and corrections (city)", g("own_corrections_usd")),
                     ("Courts and legal (city)", g("own_judicial_usd")), ("County jails, city's population share", g("county_corrections_alloc_usd")),
                     ("County courts, city's population share", g("county_judicial_alloc_usd"))]
            if g("county_police_contract_alloc_usd") is not None:
                items.append(("County police the city relies on", g("county_police_contract_alloc_usd")))
            h.append("<h2>With county jails and courts, 2022</h2><table><tbody>" +
                     "".join(f'<tr><td>{k}</td><td class="num">{fmt_money(v)}</td></tr>' for k, v in items) +
                     f'<tr class="me"><td>Total</td><td class="num">{fmt_money(g("public_safety_and_justice_usd"))}</td></tr>'
                     f'<tr><td>Per resident, {base} dollars</td><td class="num">{usd(a["public_safety_and_justice_real_per_resident"])}</td></tr>'
                     "</tbody></table>")
            h.append('<p class="cap">' + (f'Overlying counties and the city\'s share of each: {html.escape(a["overlying_counties"]).title()}. '
                     if a["has_county_government"] == "True" else "No separate county government sits over this city, so its own books already carry jail and court costs. ") +
                     "County sheriff patrol is excluded, except where the county force is the city's police.</p>")

        # trend
        h.append("<h2>Since 1967</h2><table><thead><tr><th>Census fiscal year</th><th class='num'>Police + fire share of general expenditure</th>"
                 f"<th class='num'>Per resident, {base} dollars</th><th>Source</th></tr></thead><tbody>")
        for y in HIST:
            row = L.get(y)
            if not row:
                continue
            h.append(f'<tr><td>{y}</td><td class="num">{pct(row["police_fire_pct_general"])}</td>'
                     f'<td class="num">{usd(row["police_fire_real_per_resident"])}</td>'
                     f'<td>{"Census unit file" if row["source"].startswith("census") else "Willamette compilation"}</td></tr>')
        h.append("</tbody></table><p class=\"cap\">Rows before 2012 come from the Willamette Government Finance Database, whose general-expenditure "
                 "denominator is slightly broader for cities that own utilities; police and fire dollars are identical.</p>")

        # peers
        pg = sorted(peers.get(pid, []), key=lambda x: int(x["rank"]))
        if pg:
            qual = pg[0]["group_quality"]
            share = lambda p: wide.get(p, {}).get("police_fire_pct_general")
            vals = sorted([float(share(x["peer_pid"])) for x in pg if share(x["peer_pid"])] + ([float(r["police_fire_pct_general"])] if r["police_fire_pct_general"] else []), reverse=True)
            # How many peers is this city actually distinguishable from? NOISE is the numerator
            # uncertainty published in the methodology: about two points on a 25% share.
            NOISE = 2.0
            mine = float(r["police_fire_pct_general"]) if r["police_fire_pct_general"] else None
            peer_shares = [float(share(x["peer_pid"])) for x in pg if share(x["peer_pid"])]
            below = sum(1 for v in peer_shares if mine - v > NOISE) if mine is not None else 0
            above = sum(1 for v in peer_shares if v - mine > NOISE) if mine is not None else 0
            tied = len(peer_shares) - below - above if mine is not None else 0
            h.append("<h2>Peer cities</h2><table><thead><tr><th>City</th><th class='num'>Police + fire share</th><th class='num'>Officers per 1,000</th></tr></thead><tbody>")
            h.append(f'<tr class="me"><td>{html.escape(city)}, {state}</td><td class="num">{pct(r["police_fire_pct_general"])}</td>'
                     f'<td class="num">{per1k(e22, "sworn_per_1k")}</td></tr>')
            for x in pg:
                pr = wide.get(x["peer_pid"], {})
                pe = emp.get(x["peer_pid"], {}).get(2022, {})
                h.append(f'<tr><td>{html.escape(x["peer_city"])}, {x["peer_state"]}</td><td class="num">{pct(pr.get("police_fire_pct_general"))}</td>'
                         f'<td class="num">{per1k(pe, "sworn_per_1k")}</td></tr>')
            h.append("</tbody></table>")
            if mine is None or not peer_shares:
                standing = ""
            elif not below and not above:
                standing = (f"Every one of these {len(peer_shares)} peers is within two points of this city, which is "
                            "about the measurement uncertainty, so this group has no meaningful ordering. ")
            else:
                parts = []
                if below:
                    parts.append(f"{below} have a clearly lower share")
                if above:
                    parts.append(f"{above} a clearly higher one" if below else
                                 f"{above} have a clearly higher share")
                rest = ("" if not tied else
                        ("; the remaining one is within two points, about the measurement uncertainty, "
                         "so that pairing should not be read as a difference"
                         if tied == 1 else
                         f"; the remaining {tied} are within two points, about the measurement "
                         "uncertainty, so their order should not be read"))
                standing = f"Of its {len(peer_shares)} peers, {' and '.join(parts)}{rest}. "
            h.append(f'<p class="cap">{standing}'
                     f'Match quality: {qual}{"; no city shares this one&rsquo;s structure, so the comparison is weak" if qual == "weak" else ""}. '
                     "Peers are the eight cities closest on structure, then population and regional prices.</p>")

        h.append('<footer>Sources: U.S. Census Bureau Annual Survey of State and Local Government Finances and Census of Governments (finance and '
                 'employment individual unit files); Bureau of Labor Statistics CPI-U; Bureau of Economic Analysis Regional Price Parities; FBI '
                 'Uniform Crime Reporting Return A and police employee data; Lincoln Institute of Land Policy Fiscally Standardized Cities. '
                 'Method and validation: the project README, docs/METHODOLOGY.md and validation/REPORT.md. '
                 f'{build.vintage_sentence()} '
                 f'Generated {datetime.date.today():%Y-%m-%d} from the committed pipeline.</footer>')
        page = f"<!doctype html><html lang=en><meta charset=utf-8><title>{html.escape(city)}, {state} &middot; police and fire spending</title>" \
               f"<meta name=viewport content=\"width=device-width,initial-scale=1\"><style>{CSS}</style><div class=wrap>{''.join(h)}</div></html>"
        fn = slug(city, state) + ".html"
        open(os.path.join(OUT, fn), "w", encoding="utf-8").write(page)
        index.append((int(r["population"]), city, state, fn, r["police_fire_pct_general"]))

    rows = "".join(f'<tr><td><a href="{fn}">{html.escape(c)}</a></td><td>{st}</td><td class="num">{p:,}</td><td class="num">{pct(s)}</td></tr>'
                   for p, c, st, fn, s in index)
    idx = f"<!doctype html><html lang=en><meta charset=utf-8><title>City fact sheets</title><meta name=viewport content=\"width=device-width,initial-scale=1\">" \
          f"<style>{CSS}</style><div class=wrap><p class=nav><a href=\"../findings.html\">What the numbers show</a></p><div class=eyebrow>Police and fire spending</div><h1>City fact sheets</h1>" \
          f"<p class=sub>{len(index)} US cities of 100,000 or more, Census fiscal year 2022.</p>" \
          f"<table><thead><tr><th>City</th><th>State</th><th class='num'>Population</th><th class='num'>Police + fire share of general expenditure</th></tr></thead>" \
          f"<tbody>{rows}</tbody></table></div></html>"
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(idx)
    total = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT))
    print(f"{len(index)} fact sheets + index, {total/1e6:.1f} MB total", file=sys.stderr)


if __name__ == "__main__":
    main()
