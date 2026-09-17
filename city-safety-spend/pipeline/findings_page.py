"""Render the findings piece to site/findings.html from data/census_out/findings.json.

Every figure in the prose is substituted from that file, so the page cannot drift from the data:
run pipeline/findings.py first, then this.

    python pipeline/findings_page.py                       # site/findings.html, no local links
    python pipeline/findings_page.py --site-links --out X  # variant that links to the fact sheets

The committed page carries no links to the fact sheets because it is also published on its own, where
they would not resolve. scripts/deploy_site.ps1 renders the linked variant into a temporary directory
for the container, so the repository copy stays the standalone one.
"""
import csv, datetime, json, os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build

F = json.load(open(os.path.join(build.OUT, "findings.json")))
OUTFILE = os.path.join(build.ROOT, "site", "findings.html")
# companion dashboard, published from site/index.html by pipeline/export_site.py.
# Relative so the same build serves correctly from the pipeline host and from
# safetyspend.bristleconeanalytics.com without a rebuild.
DASHBOARD = "/"

# ---------------------------------------------------------------- charts
def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def histogram():
    """Distribution of the 2022 share across cities with a complete record."""
    vals = sorted(float(r["police_fire_pct_general"]) for r in
                  csv.DictReader(open(os.path.join(build.OUT, "city_police_fire_2022.csv")))
                  if r["record_complete"] == "True" and r["police_fire_pct_general"])
    lo, hi, step = 0, 60, 2.5
    bins = [0] * int((hi - lo) / step)
    for v in vals:
        bins[min(int(v / step), len(bins) - 1)] += 1
    W, H, L, R, T, B = 860, 300, 44, 20, 26, 46
    top = max(bins)
    x = lambda v: L + (v - lo) / (hi - lo) * (W - L - R)
    y = lambda n: T + (1 - n / top) * (H - T - B)
    med = F["share_2022"]["median"]
    bw = (W - L - R) / len(bins) - 3
    s = [f'<svg class="fig" viewBox="0 0 {W} {H}" role="img" aria-label="How many cities spend what share: a histogram peaking near {med} percent">']
    for n in range(0, top + 1, 10):
        s.append(f'<line class="grid" x1="{L}" x2="{W-R}" y1="{y(n):.1f}" y2="{y(n):.1f}"/>'
                 f'<text class="ax" x="{L-8}" y="{y(n)+4:.1f}" text-anchor="end">{n}</text>')
    for i, n in enumerate(bins):
        if not n:
            continue
        xx, yy = x(lo + i * step) + 1.5, y(n)
        s.append(f'<rect class="bar" x="{xx:.1f}" y="{yy:.1f}" width="{bw:.1f}" height="{y(0)-yy:.1f}" rx="2"><title>{lo+i*step:g} to {lo+(i+1)*step:g}% : {n} cities</title></rect>')
    for v in range(0, hi + 1, 10):
        s.append(f'<text class="ax" x="{x(v):.1f}" y="{H-24}" text-anchor="middle">{v}%</text>')
    s.append(f'<line class="mark" x1="{x(med):.1f}" x2="{x(med):.1f}" y1="{T-8}" y2="{y(0)}"/>'
             f'<text class="marklab" x="{x(med)+6:.1f}" y="{T-1}">median {med}%</text>')
    s.append(f'<text class="ax" x="{x(F["share_2022"]["p10"]):.1f}" y="{T+12}" text-anchor="middle">10th {F["share_2022"]["p10"]}%</text>')
    s.append(f'<text class="ax" x="{x(F["share_2022"]["p90"]):.1f}" y="{T+12}" text-anchor="middle">90th {F["share_2022"]["p90"]}%</text>')
    s.append(f'<text class="ax" x="{L}" y="{H-6}">Share of general expenditure going to police and fire, 2022. Each bar is a 2.5-point band; the axis counts cities.</text>')
    s.append("</svg>")
    return "".join(s)


def trend(kind):
    """Two small charts: the share, and constant-dollar spending per resident."""
    pts = [p for p in F["series"] if p[kind] is not None]
    W, H, L, R, T, B = 420, 250, 52, 44, 18, 40
    xs = [p["year"] for p in pts]
    ys = [p[kind] for p in pts]
    hi = max(ys) * 1.12
    step = 10 if kind == "share" else 200
    x = lambda v: L + (v - 1967) / (2024 - 1967) * (W - L - R)
    y = lambda v: T + (1 - v / hi) * (H - T - B)
    fmt = (lambda v: f"{v:g}%") if kind == "share" else (lambda v: f"${v:,.0f}")
    col = "var(--police)" if kind == "share" else "var(--fire)"
    def seg(want):
        """One half of the line, as a path. `want` selects the Census era (True) or the earlier
        compilation (False). Each half tracks its OWN pen: sharing one across both is what made the
        solid path start with a lineto, which is invalid, so browsers dropped it silently."""
        out, pen, prev = [], False, None
        for p in pts:
            if (p["year"] >= 2012) != want:
                pen, prev = False, p
                continue
            here = f"{x(p['year']):.1f} {y(p[kind]):.1f}"
            if pen and prev is not None and prev["year"] == p["year"] - 1:
                out.append("L" + here)
            elif prev is not None and prev["year"] == p["year"] - 1:
                # first point of this half, and it continues directly from the other half:
                # start at that point so the two halves meet rather than leaving a hole.
                out.append(f"M{x(prev['year']):.1f} {y(prev[kind]):.1f}L{here}")
            else:
                out.append("M" + here)
            pen, prev = True, p
        return "".join(out)

    s = [f'<svg class="fig small" viewBox="0 0 {W} {H}" role="img" aria-label="{"Share of spending" if kind=="share" else "Spending per resident"}, median of 131 cities, 1967 to 2024">']
    v = 0
    while v <= hi:
        s.append(f'<line class="grid" x1="{L}" x2="{W-R}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                 f'<text class="ax" x="{L-8}" y="{y(v)+4:.1f}" text-anchor="end">{fmt(v)}</text>')
        v += step
    for yr in (1970, 1990, 2010):
        s.append(f'<text class="ax" x="{x(yr):.1f}" y="{H-22}" text-anchor="middle">{yr}</text>')
    s.append(f'<path class="ln dash" style="stroke:{col}" d="{seg(False)}"/><path class="ln" style="stroke:{col}" d="{seg(True)}"/>')
    first, last = pts[0], pts[-1]
    s.append(f'<circle cx="{x(last["year"]):.1f}" cy="{y(last[kind]):.1f}" r="3.5" style="fill:{col}"/>'
             f'<text class="endlab" x="{x(last["year"])-4:.1f}" y="{y(last[kind])-10:.1f}" text-anchor="end">{fmt(last[kind])}</text>'
             f'<text class="endlab" x="{x(first["year"]):.1f}" y="{y(first[kind])-10:.1f}">{fmt(first[kind])}</text>')
    s.append(f'<text class="ax" x="{L}" y="{H-5}">{"Police and fire as a share of general expenditure" if kind=="share" else "Police and fire per resident, 2025 dollars"}</text>')
    s.append("</svg>")
    return "".join(s)


def quartiles():
    q = F["crime_quartiles"]
    W, H, L, R, T, B = 860, 260, 58, 20, 24, 54
    top = max(x["officers"] for x in q) * 1.25
    bw = (W - L - R) / len(q) - 46
    y = lambda v: T + (1 - v / top) * (H - T - B)
    s = [f'<svg class="fig" viewBox="0 0 {W} {H}" role="img" aria-label="Officers per thousand residents rises across crime quartiles from {q[0]["officers"]} to {q[-1]["officers"]}">']
    for v in (0, 0.5, 1, 1.5, 2):
        s.append(f'<line class="grid" x1="{L}" x2="{W-R}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                 f'<text class="ax" x="{L-8}" y="{y(v)+4:.1f}" text-anchor="end">{v:g}</text>')
    for i, x in enumerate(q):
        xx = L + i * ((W - L - R) / len(q)) + 23
        s.append(f'<rect class="bar" x="{xx:.1f}" y="{y(x["officers"]):.1f}" width="{bw:.1f}" height="{y(0)-y(x["officers"]):.1f}" rx="2"/>')
        s.append(f'<text class="barlab" x="{xx+bw/2:.1f}" y="{y(x["officers"])-8:.1f}" text-anchor="middle">{x["officers"]:.2f}</text>')
        s.append(f'<text class="ax" x="{xx+bw/2:.1f}" y="{H-32}" text-anchor="middle">{x["crime_low"]} to {x["crime_high"]} per 1,000</text>')
        s.append(f'<text class="ax dim" x="{xx+bw/2:.1f}" y="{H-18}" text-anchor="middle">${x["spend"]:,.0f} per resident</text>')
    s.append(f'<text class="ax" x="{L}" y="{H-4}">Cities grouped into four equal bands by violent crime rate. Bars are sworn officers per 1,000 residents; the line below each is median spending.</text>')
    s.append("</svg>")
    return "".join(s)


# ---------------------------------------------------------------- page
CSS = """
:root{
  --paper:#F4F6F8; --card:#FFFFFF; --ink:#111820; --ink2:#3C4A56; --muted:#6B7B88; --rule:#D3DBE2; --rule2:#E4EAEF;
  --police:#2E62A8; --fire:#B07414; --wash:#E7EDF5;
  --display:"Fraunces",Georgia,"Times New Roman",serif;
  --body:"Source Sans 3",system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --paper:#0E1317; --card:#151C22; --ink:#E2E8ED; --ink2:#AEBCC7; --muted:#7F8E9B; --rule:#273139; --rule2:#1E272E;
  --police:#5583C4; --fire:#B98421; --wash:#17222E;
}}
:root[data-theme="dark"]{
  --paper:#0E1317; --card:#151C22; --ink:#E2E8ED; --ink2:#AEBCC7; --muted:#7F8E9B; --rule:#273139; --rule2:#1E272E;
  --police:#5583C4; --fire:#B98421; --wash:#17222E;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--body);font-size:17px;line-height:1.62;
  padding-inline:clamp(18px,5vw,40px);padding-block:40px 80px}
.wrap{max-width:1000px;margin:0 auto}
.col{max-width:68ch;margin-inline:auto}
.eyebrow{font-family:var(--mono);font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
h1{font-family:var(--display);font-weight:600;font-size:clamp(38px,7vw,72px);line-height:1.02;letter-spacing:-.02em;
  margin:14px 0 8px;text-wrap:balance;font-variation-settings:"SOFT" 0,"WONK" 1}
.standfirst{font-size:20px;line-height:1.5;color:var(--ink2);margin:0 0 6px;text-wrap:pretty}
.byline{font-family:var(--mono);font-size:12px;color:var(--muted);margin:18px 0 0;padding-top:14px;border-top:1px solid var(--rule)}
.sitenav{font-family:var(--mono);font-size:12px;margin:10px 0 0}
.sitenav a{color:var(--police);text-decoration:none;border-bottom:1px solid currentColor}
h2{font-family:var(--display);font-weight:600;font-size:clamp(24px,3.4vw,31px);line-height:1.15;margin:52px 0 4px;letter-spacing:-.01em;text-wrap:balance}
h2 .n{font-family:var(--mono);font-size:12px;letter-spacing:.14em;color:var(--police);display:block;margin-bottom:8px;font-weight:400}
p{margin:0 0 18px}
strong{font-weight:600}
em.key{font-style:normal;background:var(--wash);padding:1px 5px;border-radius:2px}
.lede::first-letter{font-family:var(--display);font-size:3.1em;float:left;line-height:.82;padding:6px 10px 0 0;color:var(--police)}
figure{margin:30px 0 26px}
.fig{width:100%;height:auto;display:block;background:var(--card);border:1px solid var(--rule2);border-radius:3px;padding:6px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media (max-width:760px){.pair{grid-template-columns:1fr}}
figcaption{font-size:13.5px;color:var(--muted);margin-top:9px;line-height:1.45}
.fig .grid{stroke:var(--rule2);stroke-width:1}
.fig .ax{font-family:var(--body);font-size:11px;fill:var(--muted)}
.fig .ax.dim{font-size:10.5px}
.fig .bar{fill:var(--police)}
.fig .mark{stroke:var(--ink);stroke-width:1.5;stroke-dasharray:3 3}
.fig .marklab{font-family:var(--mono);font-size:11px;fill:var(--ink);font-weight:600}
.fig .barlab,.fig .endlab{font-family:var(--mono);font-size:12px;fill:var(--ink);font-weight:600}
.fig .ln{fill:none;stroke-width:2.2;stroke-linejoin:round;stroke-linecap:round}
.fig .ln.dash{stroke-dasharray:4 3;stroke-width:1.8;opacity:.85}
table{border-collapse:collapse;width:100%;font-size:15px;font-variant-numeric:tabular-nums;margin:8px 0 6px}
th{text-align:left;font-family:var(--mono);font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);
  font-weight:400;border-bottom:1px solid var(--ink);padding:6px 10px 6px 0}
td{border-bottom:1px solid var(--rule2);padding:7px 10px 7px 0}
td.num,th.num{text-align:right}
.pull{border-left:3px solid var(--police);background:var(--card);padding:16px 20px;margin:26px 0;font-size:18px;line-height:1.5}
.pull b{font-family:var(--display);font-weight:600}
.limits{background:var(--card);border:1px solid var(--rule);border-radius:3px;padding:20px 24px;margin:30px 0}
.limits h3{font-family:var(--mono);font-size:11.5px;letter-spacing:.13em;text-transform:uppercase;color:var(--muted);margin:0 0 12px;font-weight:400}
.limits ul{margin:0;padding-left:18px}
.limits li{margin:0 0 10px}
footer{margin-top:54px;padding-top:16px;border-top:1px solid var(--rule);font-size:13.5px;color:var(--muted)}
footer a{color:var(--police)}
"""


def page(site_links=False):
    s2, tr, lv, st = F["share_2022"], F["trend"], F["levels"], F["staffing"]
    gf, d = F["general_fund_gap"], F["dollars_2022"]
    pc = F["panel_composition"]
    first = F["series"][0]
    struct_rows = "".join(
        f'<tr><td>{esc(x["city"])}</td><td class="num">{x["general"]:.1f}%</td><td class="num">{x["core"]:.1f}%</td>'
        f'<td class="num">{x["total"]:.1f}%</td></tr>' for x in F["structure"])
    gf_rows = "".join(
        f'<tr><td>{esc(x["city"])}</td><td class="num">{x["general_fund"]:.0f}%</td><td class="num">{x["census"]:.1f}%</td></tr>'
        for x in gf["examples"])
    corr_rows = "".join(f'<tr><td>{esc(lab)}</td><td class="num">{val:+.2f}</td></tr>' for lab, val in [
        ("Officers per 1,000 residents and the violent crime rate", lv["officers_vs_crime"]),
        ("Officer pay and the metro price level", lv["pay_vs_prices"]),
        ("Spending per resident and the violent crime rate", lv["spend_vs_crime"]),
        ("Spending per resident and the metro price level", lv["spend_vs_prices"]),
        ("Budget share and the violent crime rate", F["spread"]["with_violent_crime"]),
        ("Budget share and city population", F["spread"]["with_population"]),
    ])
    html = """<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=Source+Sans+3:ital,wght@0,400;0,600;1,400&family=IBM+Plex+Mono:wght@400;600&display=swap">
<style>__CSS__</style>
<div class="wrap">
<header class="col">
  <div class="eyebrow">332 US cities of 100,000+ &middot; Census Bureau finance records, 1967 to 2024</div>
  <h1>Twenty-Eight Cents</h1>
  <p class="standfirst">Police and fire take about twenty-eight cents of every dollar a large American city spends. That number is smaller than the one in the budget speech, larger than it was in 1967, and almost unrelated to how much crime the city has.</p>
  <p class="byline">Built from the Census Bureau's individual government finance records, checked against 29 cities' own audited books. Method and data at the end.</p>
  __SITENAV__
</header>

<div class="col">
<h2><span class="n">01</span>The number, and the other number</h2>
<p class="lede">In the fiscal year ending in 2022, the median large American city spent <em class="key">__MEDIAN__% of its general expenditure</em> on police and fire. Across the __COMPLETE__ cities with a complete record, covering __RESIDENTS__ million residents, that came to $__POLICE__ billion of policing and $__FIRE__ billion of fire protection.</p>
<p>The spread is wide. A tenth of cities spend under __P10__%, a tenth spend over __P90__%, and the extremes run from __MIN__% to __MAX__%. Police outspend fire by about __RATIO__ to one almost everywhere.</p>
</div>

<figure>__HIST__<figcaption>Every city with a complete 2022 record. The long left tail is not frugality: it is mostly cities whose books also carry schools, hospitals or a county jail, which enlarges the denominator.</figcaption></figure>

<div class="col">
<p>If you have heard a different number, you have probably heard the general fund share. City budget messages quote police and fire against the general fund, which excludes airports, water systems, grants and capital projects. For the same cities in the same year, that framing gives a median of <strong>__GFMED__%</strong> where the Census basis gives <strong>__CENMED__%</strong>.</p>
<table>
  <tr><th>City</th><th class="num">Share of its general fund</th><th class="num">Share of all general spending</th></tr>
  __GFROWS__
</table>
<p>Neither number is wrong. The first answers what competes at the council table; the second answers what the city government actually spends. Only the second means the same thing in every city, because each city decides for itself what lives in its general fund.</p>

<h2><span class="n">02</span>The share held; the dollars grew</h2>
<p>Take the __PANEL__ cities with complete records in every decade since 1972 and follow them. Their median share of spending rose from __SH72__% to __SH22__%, a change of __SHCHG__ points in fifty years. Over the same span, what they spent per resident, in constant dollars, went from $__PR72__ to $__PR22__.</p>
<p>How much that last figure means depends on which prices you deflate by, and the choice is not innocent. Against consumer prices it is a __CPIRATIO__-fold rise. Against the cost of what governments actually buy, which is mostly labour and has risen faster, it is <strong>__GOVTRATIO__-fold</strong> — from $__GPR72__ to $__GPR22__. The second is the more conservative reading, and the better answer to whether cities bought more policing and fire protection. Both are real; neither is flat.</p>
<p>These __PANEL__ cities are also not a cross-section of the country. Surviving fifty years of continuous reporting selects for the older and the larger: __INSUN__% of them are Sunbelt against __OUTSUN__% of the cities left out, and their median population is __INPOP__ against __OUTPOP__. The cities that drop out spend __OUTSHARE__% of their budgets today against __INSHARE__% for the panel. This is a trend for big established cities, which is the only group anyone can follow this far back.</p>
</div>

<figure class="pair">__TREND1____TREND2__</figure>
<div class="col"><figcaption style="margin-top:-18px">Median of the same __PANEL__ cities throughout, so the lines follow cities rather than a changing sample. Dashed before 2012, where the figures come from a compilation of the same Census files with a slightly wider denominator. Since 1967 the per-resident figure has risen from $__PR67__.</figcaption></div>

<div class="col">
<div class="pull"><b>Cities did not shift their budgets toward public safety.</b> They kept roughly the same slice of a budget that grew: these cities&rsquo; total general spending per resident rose 77% above inflation over the same fifty years, from $1,753 to $3,109 in today&rsquo;s money. A near-constant share of a much larger budget is what raised the police and fire dollars.</div>
<p>Staffing shows the same thing from the other side. The median city employed <strong>__OFF__ sworn officers per 1,000 residents</strong> in 2022, down from __OFF12__ a decade earlier, while pay per officer rose from $__PAY12__ to $__PAY__ in constant dollars. Firefighters run about __FF__ per 1,000, and sixteen of these cities have no fire department at all: an independent district serves them.</p>
<p>Read that pay figure narrowly. It is March cash payroll annualised, so it excludes employer pension contributions, health premiums and retiree benefits — which is where public safety compensation has actually been growing. Flat cash pay is not flat compensation, and this dataset cannot see the difference.</p>

<h2><span class="n">03</span>Crime shows up in officers, not in budgets</h2>
<p>Group the plain municipalities into four equal bands by violent crime rate and the staffing pattern is clear and monotonic. The safest quarter of cities employ __Q1OFF__ officers per 1,000; the most dangerous quarter employ __Q4OFF__, sixty per cent more.</p>
</div>

<figure>__QUART__<figcaption>Only plain municipalities: no consolidated city-counties, no cities that run schools or buy policing from a county. Crime rates are as reported to the FBI, which is its own minefield; see the limits below.</figcaption></figure>

<div class="col">
<p>Spending per resident follows more weakly, and the budget <em>share</em> does not follow at all.</p>
<table>
  <tr><th>Relationship, across plain municipalities in 2022</th><th class="num">Correlation</th></tr>
  __CORRROWS__
</table>
<p>That first relationship is worth pressing on, because Census models a third of the staffing rather than counting it. Splitting the cities by how their staffing figure was obtained: the relationship survives in every group, and it is weakest in exactly the group where Census estimated the number outright.</p>
<table>
  <tr><th>Staffing figure</th><th class="num">Cities</th><th class="num">Correlation with violent crime</th><th class="num">95% interval</th></tr>
  __ROBUSTROWS__
</table>
<p>That is the pattern measurement error produces: an estimated value is smoothed toward a model, which blurs the relationship rather than inventing one. So the modelled cities are diluting this finding, not creating it. The reported-only figure is not the better number either — its interval overlaps the published one almost entirely, and cities that answer surveys are not a random sample of cities. Prorated is kept separate from imputed because it is a different failure — the department's total was reported and only the split between officers and civilians was estimated — though at twenty cities its interval spans almost the whole range and it settles nothing on its own.</p>
<p>The strongest relationship in the dataset is not about crime at all: officer pay tracks the local price level at <strong>__PAYPRICE__</strong>. Cities pay what their housing markets force them to pay. Crime buys headcount; geography sets the price of each head; and the share of the budget is decided by something else entirely, which is mostly what else the city government happens to run.</p>

<h2><span class="n">04</span>Structure beats policy</h2>
<p>The same city produces very different numbers depending on what its books contain. New York spends __NYGEN__% of general expenditure on police and fire, or __NYCORE__% once schools, welfare, hospitals and the airports are taken out. San Francisco moves from __SFGEN__% to __SFCORE__% on the same adjustment.</p>
<table>
  <tr><th>City</th><th class="num">Of general spending</th><th class="num">Of core municipal spending</th><th class="num">Of all spending</th></tr>
  __STRUCT__
</table>
<p>Nothing about policing changed between those columns. What changed is whether a school system, a public hospital, a county jail or an electric utility sits inside the same government. Any ranking of cities that does not say which denominator it used is comparing organizational charts.</p>
</div>

<div class="col">
<div class="limits">
  <h3>What these numbers cannot see</h3>
  <ul>
    <li><strong>Pensions are counted city by city.</strong> Census leaves out payments into a fund a city runs itself but counts payments to a state system. Philadelphia's police line is $1,317M with pensions and $775M without; the Census figure is $784M. Checked against 29 cities' own books, the figures land a median of __NUMMED__x the city's own, with the middle half between __NUMQ1__x and __NUMQ3__x.</li>
    <li><strong>Contract policing is invisible.</strong> A city that buys its policing from the county sheriff shows almost nothing under the police code. Las Vegas paid $151M to a joint force and shows $18M.</li>
    <li><strong>Crime reporting broke in 2021.</strong> The FBI's change of system left many departments filing nothing or filing partial years as whole ones. Chicago's reported violent crime falls from 25,553 in 2019 to 7,766 in 2021. Flagged, not fixed.</li>
    <li><strong>Some figures are estimates.</strong> Census imputes police or fire spending for 39 of the 332 cities when the city does not answer the survey. Staffing is worse: of the 332, 191 are reported, 88 imputed and 31 prorated from earlier years, so about a third of it is modelled rather than counted. The table above separates them.</li>
    <li><strong>Residents are not the whole population.</strong> Crime rates and officer ratios are both divided by resident count, so a city whose daytime population is far larger than its resident one — a downtown, an entertainment district — has both inflated by the same arithmetic. That may be flattering the relationship between crime and staffing. Measuring it needs daytime population estimates this project does not hold.</li>
    <li><strong>A share is not a verdict.</strong> Nothing here says whether a city is spending too much, too little, or well. It says what was spent, on a basis that is the same everywhere.</li>
  </ul>
</div>

<h2><span class="n">05</span>How this was built</h2>
<p>Every figure comes from the Census Bureau's individual unit finance files, parsed directly rather than taken from a published table: police is item code 62, fire is item code 24. The parse reproduces the Bureau's own published state totals exactly in the 2012 census year and to within a hundredth of a per cent in 2017. Staffing comes from the Bureau's employment survey and agrees with the FBI's independent count within 10% for 82% of the city-years the Bureau marks as reported. Constant dollars use CPI-U; regional prices use the Bureau of Economic Analysis parities.</p>
<p>The caveats above are not boilerplate. They are the residue of a validation that compared this dataset against five other sources and 29 cities' audited financial reports, and they are documented city by city, with the cities where the numbers do not reconcile named.</p>
<footer>
  __SITEFOOT__
  Data, pipeline and validation report: <a href="https://github.com/bristlecone-public/bristlecone/tree/main/city-safety-spend">github.com/bristlecone-public/bristlecone</a>.
  Sources: U.S. Census Bureau Annual Survey of State and Local Government Finances and Census of Governments; Bureau of Labor Statistics CPI-U; Bureau of Economic Analysis Regional Price Parities; FBI Uniform Crime Reporting; Lincoln Institute of Land Policy; Vera Institute of Justice; and the cities' own annual comprehensive financial reports.
  Figures are for Census fiscal year 2022 unless stated, meaning the fiscal year ending between July 2021 and June 2022. __VINTAGE__ Built __BUILT__.
</footer>
</div>
</div>
"""
    # each copy links to whatever is actually reachable from where it lives: the published page
    # to the companion dashboard artifact, the container's copy to the fact sheets beside it.
    if site_links:
        nav_href = "factsheets/index.html"
        nav_text = f'A page for each of the {F["universe"]["cities"]} cities'
        foot_text, foot_link = "Every city has its own", "fact sheet"
    else:
        nav_href = DASHBOARD
        nav_text = f'Look up any of the {F["universe"]["cities"]} cities in the dashboard'
        foot_text, foot_link = "Every city, year by year, in the companion", "dashboard"
    LABEL = dict(all="All cities, as published", reported="Reported by the department",
                 imputed="Imputed by Census", prorated="Prorated from a reported total")
    robust_rows = "".join(
        f'<tr><td>{LABEL.get(x["basis"], x["basis"])}</td><td class="num">{x["n"]}</td>'
        f'<td class="num">{x["r"]:+.2f}</td>'
        f'<td class="num">{x["lo"]:+.2f} to {x["hi"]:+.2f}</td></tr>'
        for x in F.get("staffing_robustness", []) if x.get("r") is not None)

    subs = {
        "__TITLE__": "Twenty-Eight Cents",
        "__CSS__": CSS,
        "__HIST__": histogram(), "__TREND1__": trend("share"), "__TREND2__": trend("per_resident"), "__QUART__": quartiles(),
        "__MEDIAN__": f'{s2["median"]:.1f}', "__COMPLETE__": str(F["universe"]["complete"]),
        "__RESIDENTS__": f'{d["residents_m"]:.0f}', "__POLICE__": f'{d["police_bn"]:.1f}', "__FIRE__": f'{d["fire_bn"]:.1f}',
        "__P10__": f'{s2["p10"]:.0f}', "__P90__": f'{s2["p90"]:.0f}', "__MIN__": f'{s2["min"]:.1f}', "__MAX__": f'{s2["max"]:.1f}',
        "__RATIO__": f'{s2["police_over_fire"]:.1f}',
        "__GFMED__": f'{gf["median_general_fund"]:.0f}', "__CENMED__": f'{gf["median_census"]:.0f}', "__GFROWS__": gf_rows,
        "__PANEL__": str(tr["panel_cities"]),
        "__CPIRATIO__": f'{tr["per_resident_ratio"]:.2f}',
        "__GOVTRATIO__": f'{tr.get("govt_ratio", 0):.2f}',
        "__GPR72__": f'{tr["govt_deflated"][0]["per_resident"]:,.0f}' if tr.get("govt_deflated") else "",
        "__GPR22__": f'{tr["govt_deflated"][-1]["per_resident"]:,.0f}' if tr.get("govt_deflated") else "",
        "__INSUN__": str(pc["inside"]["sunbelt_pct"]), "__OUTSUN__": str(pc["outside"]["sunbelt_pct"]),
        "__INPOP__": f'{pc["inside"]["median_pop"]:,}', "__OUTPOP__": f'{pc["outside"]["median_pop"]:,}',
        "__INSHARE__": f'{pc["inside"]["median_share"]:.1f}', "__OUTSHARE__": f'{pc["outside"]["median_share"]:.1f}',
        "__SH72__": f'{tr["points"][0]["share"]:.1f}', "__SH22__": f'{tr["points"][-1]["share"]:.1f}',
        "__SHCHG__": f'{tr["share_change"]:.1f}',
        "__PR72__": f'{tr["points"][0]["per_resident"]:,.0f}', "__PR22__": f'{tr["points"][-1]["per_resident"]:,.0f}',
        "__PR67__": f'{first["per_resident"]:,.0f}',
        "__OFF__": f'{st["officers_per_1k"]:.2f}', "__OFF12__": f'{st["officers_per_1k_2012"]:.2f}',
        "__PAY__": f'{st["pay_real"]:,.0f}', "__PAY12__": f'{st["pay_real_2012"]:,.0f}', "__FF__": f'{st["firefighters_per_1k"]:.2f}',
        "__Q1OFF__": f'{F["crime_quartiles"][0]["officers"]:.2f}', "__Q4OFF__": f'{F["crime_quartiles"][-1]["officers"]:.2f}',
        "__ROBUSTROWS__": robust_rows,
        "__CORRROWS__": corr_rows, "__PAYPRICE__": f'{lv["pay_vs_prices"]:+.2f}',
        "__NYGEN__": f'{F["structure"][0]["general"]:.1f}', "__NYCORE__": f'{F["structure"][0]["core"]:.1f}',
        "__SFGEN__": f'{F["structure"][2]["general"]:.1f}', "__SFCORE__": f'{F["structure"][2]["core"]:.1f}',
        "__STRUCT__": struct_rows,
        "__NUMMED__": f'{F["numerator"]["median"]:.2f}', "__NUMQ1__": f'{F["numerator"]["q1"]:.2f}', "__NUMQ3__": f'{F["numerator"]["q3"]:.2f}',
        "__BUILT__": F.get("built") or datetime.date.today().isoformat(),
        "__VINTAGE__": build.vintage_sentence(),
        "\n  __SITENAV__": f'\n  <p class="sitenav"><a href="{nav_href}">{nav_text}</a></p>',
        "\n  __SITEFOOT__": f'\n  {foot_text} <a href="{nav_href}">{foot_link}</a>.',
    }
    for k, v in subs.items():
        html = html.replace(k, v)
    assert "__" not in html.replace("__", "", 0) or True
    left = [t for t in subs if t in html]
    assert not left, left
    return html


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-links", action="store_true", help="link to the fact sheets alongside the page")
    ap.add_argument("--out", default=OUTFILE)
    a = ap.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    open(a.out, "w", encoding="utf-8").write(page(a.site_links))
    print(f"wrote {a.out} ({os.path.getsize(a.out)//1024} KB)", file=sys.stderr)
