"""Numbers for the findings piece. Every figure the write-up quotes is computed here, so the piece can
be re-derived rather than trusted. Writes data/census_out/findings.json and prints the same to stderr.

Trend figures use a BALANCED PANEL: only cities with a complete record in every decade year shown, so a
change in the line is a change in cities, not a change in which cities are in the file.
"""
import csv, datetime, json, math, os, sys, statistics, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build, cpi

OUT = build.OUT
DECADES = [1972, 1982, 1992, 2002, 2012, 2022]


def rd(p):
    return list(csv.DictReader(open(os.path.join(build.ROOT, p), encoding="utf-8-sig")))


def med(xs):
    return round(statistics.median(xs), 2) if xs else None


def main():
    F = {}
    wide = rd("data/census_out/city_police_fire_2022.csv")
    flags = {r["pid"]: r for r in rd("data/census_out/city_flags.csv")}
    emp = {(r["pid"], int(r["year"])): r for r in rd("data/census_out/city_employment_all_years.csv")}
    crime = {(r["pid"], int(r["year"])): r for r in rd("data/census_out/city_crime.csv")}
    rpp = {r["pid"]: r for r in rd("data/census_out/city_rpp.csv")}
    longs = collections.defaultdict(dict)
    for r in rd("data/census_out/city_police_fire_1967_2024_long.csv"):
        longs[r["place_geoid"]][int(r["fiscal_year"])] = r

    ok = [r for r in wide if r["record_complete"] == "True" and r["police_fire_pct_general"]]
    plain = [r for r in ok if not any(flags[r["pid"]][k] == "True" for k in
             ("runs_schools", "county_like_functions", "fire_external", "police_contracted", "consolidated_or_independent"))]
    F["universe"] = dict(cities=len(wide), complete=len(ok), plain=len(plain))

    # --- 1. the 2022 distribution
    sh = sorted(float(r["police_fire_pct_general"]) for r in ok)
    q = statistics.quantiles(sh, n=10)
    F["share_2022"] = dict(median=med(sh), p10=round(q[0], 1), p90=round(q[8], 1), min=round(sh[0], 1), max=round(sh[-1], 1),
                           plain_median=med([float(r["police_fire_pct_general"]) for r in plain]))
    pol = sorted(float(r["police_pct_general"]) for r in ok if r["police_pct_general"])
    fir = sorted(float(r["fire_pct_general"]) for r in ok if r["fire_pct_general"])
    F["share_2022"].update(police_median=med(pol), fire_median=med(fir))
    F["share_2022"]["police_over_fire"] = round(statistics.median(pol) / statistics.median(fir), 2)

    # dollars
    tot_p = sum(int(r["police_usd"]) for r in ok); tot_f = sum(int(r["fire_usd"]) for r in ok)
    F["dollars_2022"] = dict(police_bn=round(tot_p / 1e9, 1), fire_bn=round(tot_f / 1e9, 1),
                             residents_m=round(sum(int(r["population"]) for r in ok) / 1e6, 1))

    # --- 2. the general-fund gap, from the spot checks
    sc = rd("validation/spotcheck_vs_census.csv")
    gaps = []
    for r in sc:
        if r["framing"].startswith("general_fund") and r["doc_police_fire_pct_of_its_denominator"] and r["census_police_fire_pct_general"]:
            gaps.append((r["city"], float(r["doc_police_fire_pct_of_its_denominator"]), float(r["census_police_fire_pct_general"])))
    F["general_fund_gap"] = dict(n=len(gaps), median_general_fund=med([g[1] for g in gaps]), median_census=med([g[2] for g in gaps]),
                                 examples=[dict(city=c, general_fund=gf, census=cs) for c, gf, cs in
                                           sorted(gaps, key=lambda g: -g[1])[:4]])

    # --- 3. the long trend on a balanced panel
    panel = [g for g, ys in longs.items() if all(y in ys and ys[y]["police_fire_pct_general"] and ys[y]["police_fire_real_per_resident"] for y in DECADES)]
    trend = []
    for y in DECADES:
        shares = [float(longs[g][y]["police_fire_pct_general"]) for g in panel]
        perres = [float(longs[g][y]["police_fire_real_per_resident"]) for g in panel]
        pol_s = [float(longs[g][y]["police_pct_general"]) for g in panel if longs[g][y]["police_pct_general"]]
        fir_s = [float(longs[g][y]["fire_pct_general"]) for g in panel if longs[g][y]["fire_pct_general"]]
        trend.append(dict(year=y, share=med(shares), per_resident=med(perres), police_share=med(pol_s), fire_share=med(fir_s)))
    F["trend"] = dict(panel_cities=len(panel), base_year=cpi.base_year(), points=trend)

    # The same panel re-deflated by government costs rather than consumer prices. CPI-U measures what
    # households buy; a city budget is overwhelmingly labour, and the two indices diverge by enough to
    # decide whether "doubled" is the right word. Raised by the adversarial audit, section 2C.
    sl = {}
    dfl = os.path.join(build.ROOT, "data", "deflator", "bea_state_local_deflator.csv")
    if os.path.exists(dfl):
        for row in list(csv.reader(open(dfl)))[1:]:
            if len(row) > 1 and row[1] not in (".", ""):
                sl[int(row[0][:4])] = float(row[1])
    if sl:
        base_sl = sl.get(cpi.base_year()) or sl[max(sl)]
        govt = []
        for y in DECADES:
            nom = [(int(longs[g][y]["police_usd"]) + int(longs[g][y]["fire_usd"])) / float(longs[g][y]["population"])
                   for g in panel if longs[g][y]["population"] and float(longs[g][y]["population"]) > 0]
            idx = sl.get(y - 1) or sl.get(y)
            govt.append(dict(year=y, per_resident=med([v * base_sl / idx for v in nom])))
        F["trend"]["govt_deflated"] = govt
        F["trend"]["govt_ratio"] = round(govt[-1]["per_resident"] / govt[0]["per_resident"], 2)

    # Who is actually in the panel. A balanced panel is the right instrument for a trend, but it is
    # not a cross-section of American cities, and the piece was generalising it.
    inv_ = {v: k for k, v in build.FIPS_STATE.items()}
    SUNBELT = {"TX","FL","AZ","NV","GA","NC","SC","TN","CA","NM","AL","MS","LA","OK","AR","UT","ID"}
    pset = set(panel)
    ins, outs = [], []
    for r in ok:
        g = inv_[r["state"]] + r["fips_place"].zfill(5)
        (ins if g in pset else outs).append(r)
    def summarise(rows):
        return dict(n=len(rows),
                    sunbelt_pct=round(100 * sum(1 for r in rows if r["state"] in SUNBELT) / len(rows)),
                    median_pop=int(statistics.median(int(r["population"]) for r in rows)),
                    median_share=med([float(r["police_fire_pct_general"]) for r in rows]))
    F["panel_composition"] = dict(inside=summarise(ins), outside=summarise(outs))
    F["trend"]["share_change"] = round(trend[-1]["share"] - trend[0]["share"], 1)
    F["trend"]["per_resident_ratio"] = round(trend[-1]["per_resident"] / trend[0]["per_resident"], 2)

    # every year, for the chart
    series = []
    for y in range(1967, 2025):
        xs = [float(longs[g][y]["police_fire_pct_general"]) for g in panel if y in longs[g] and longs[g][y]["police_fire_pct_general"]]
        ps = [float(longs[g][y]["police_fire_real_per_resident"]) for g in panel if y in longs[g] and longs[g][y]["police_fire_real_per_resident"]]
        if len(xs) > len(panel) * 0.8:
            series.append(dict(year=y, share=med(xs), per_resident=med(ps), n=len(xs)))
    F["series"] = series

    # --- 4. what explains the spread in 2022
    def corr(pairs):
        xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
        return round(statistics.correlation(xs, ys), 2) if len(pairs) > 30 else None
    rows = [r for r in plain]
    F["spread"] = {}
    pairs = [(float(rpp[r["pid"]]["rpp_2022"]), float(r["police_fire_pct_general"])) for r in rows if rpp.get(r["pid"], {}).get("rpp_2022")]
    F["spread"]["with_metro_prices"] = corr(pairs)
    pairs = [(int(r["population"]), float(r["police_fire_pct_general"])) for r in rows]
    F["spread"]["with_population"] = corr([(__import__("math").log10(a), b) for a, b in pairs])
    pairs = [(float(crime[(r["pid"], 2022)]["violent_per_1k"]), float(r["police_fire_pct_general"]))
             for r in rows if crime.get((r["pid"], 2022), {}).get("violent_per_1k")]
    F["spread"]["with_violent_crime"] = corr(pairs)
    F["spread"]["crime_n"] = len(pairs)
    pairs = [(float(emp[(r["pid"], 2022)]["sworn_per_1k"]), float(r["police_fire_pct_general"]))
             for r in rows if emp.get((r["pid"], 2022), {}).get("sworn_per_1k")]
    F["spread"]["with_officers_per_1k"] = corr(pairs)

    # levels, not shares: does spending track demand?
    import math
    lv = []
    inv = {v: k for k, v in build.FIPS_STATE.items()}
    for r in rows:
        g = inv[r["state"]] + r["fips_place"].zfill(5)
        lr = longs.get(g, {}).get(2022)
        if not lr or not lr["police_fire_real_per_resident"]:
            continue
        e, c = emp.get((r["pid"], 2022), {}), crime.get((r["pid"], 2022), {})
        lv.append(dict(spend=float(lr["police_fire_real_per_resident"]),
                       spend_rpp=float(lr["police_fire_real_rpp_per_resident"]) if lr["police_fire_real_rpp_per_resident"] else None,
                       crime=float(c["violent_per_1k"]) if c.get("violent_per_1k") else None,
                       sworn=float(e["sworn_per_1k"]) if e.get("sworn_per_1k") else None,
                       pay=float(e["sworn_pay_annualized_real_usd"]) if e.get("sworn_pay_annualized_real_usd") else None,
                       rpp=float(rpp[r["pid"]]["rpp_2022"]) if rpp.get(r["pid"], {}).get("rpp_2022") else None))
    pair = lambda a, b: [(x[a], x[b]) for x in lv if x[a] is not None and x[b] is not None]
    F["levels"] = dict(n=len(lv),
                       spend_vs_crime=corr(pair("crime", "spend")),
                       spend_vs_crime_price_adjusted=corr(pair("crime", "spend_rpp")),
                       officers_vs_crime=corr(pair("crime", "sworn")),
                       spend_vs_officers=corr(pair("sworn", "spend")),
                       spend_vs_prices=corr(pair("rpp", "spend")),
                       pay_vs_prices=corr(pair("rpp", "pay")))
    withc = sorted([x for x in lv if x["crime"] and x["sworn"]], key=lambda x: x["crime"])
    qsize = len(withc) // 4
    # Does the crime-to-staffing relationship depend on Census having modelled the staffing?
    # Reported / imputed / prorated are kept apart deliberately: imputation estimates a value the
    # agency never gave, proration splits a total it did give. Confidence intervals included because
    # the subsets are small and the point estimates alone would invite over-reading.
    def fisher_ci(r, n):
        if n < 10 or abs(r) >= 1:
            return None, None
        z, se = 0.5 * math.log((1 + r) / (1 - r)), 1 / math.sqrt(n - 3)
        return round(math.tanh(z - 1.96 * se), 2), round(math.tanh(z + 1.96 * se), 2)

    F["staffing_robustness"] = []
    for label in ("all", "reported", "imputed", "prorated"):
        pts = []
        for r in rows:
            e, c = emp.get((r["pid"], 2022), {}), crime.get((r["pid"], 2022), {})
            if label != "all" and e.get("police_flag_class") != label:
                continue
            if e.get("sworn_per_1k") and c.get("violent_per_1k"):
                pts.append((float(c["violent_per_1k"]), float(e["sworn_per_1k"])))
        if len(pts) < 10:
            F["staffing_robustness"].append(dict(basis=label, n=len(pts), r=None, lo=None, hi=None))
            continue
        rr = statistics.correlation([p[0] for p in pts], [p[1] for p in pts])
        lo, hi = fisher_ci(rr, len(pts))
        F["staffing_robustness"].append(dict(basis=label, n=len(pts), r=round(rr, 2), lo=lo, hi=hi))

    F["crime_quartiles"] = []
    for i in range(4):
        qq = withc[i * qsize:(i + 1) * qsize] if i < 3 else withc[3 * qsize:]
        F["crime_quartiles"].append(dict(quartile=i + 1, crime_low=round(qq[0]["crime"], 1), crime_high=round(qq[-1]["crime"], 1),
                                         spend=med([x["spend"] for x in qq]), officers=med([x["sworn"] for x in qq]), n=len(qq)))

    # by state, where we have at least 6 plain cities
    by_state = collections.defaultdict(list)
    for r in rows:
        by_state[r["state"]].append(float(r["police_fire_pct_general"]))
    st = sorted(((s, med(v), len(v)) for s, v in by_state.items() if len(v) >= 6), key=lambda x: -x[1])
    F["by_state"] = [dict(state=s, median=m, n=n) for s, m, n in st]

    # --- 5. staffing
    e22 = [emp[(r["pid"], 2022)] for r in ok if (r["pid"], 2022) in emp]
    F["staffing"] = dict(
        officers_per_1k=med([float(e["sworn_per_1k"]) for e in e22 if e["sworn_per_1k"]]),
        firefighters_per_1k=med([float(e["firefighters_per_1k"]) for e in e22 if e["firefighters_per_1k"] and float(e["firefighters_per_1k"]) > 0]),
        pay_real=med([float(e["sworn_pay_annualized_real_usd"]) for e in e22 if e["sworn_pay_annualized_real_usd"]]),
        no_fire_department=sum(1 for r in wide if flags[r["pid"]]["fire_external"] == "True"))
    e12 = [emp[(r["pid"], 2012)] for r in ok if (r["pid"], 2012) in emp]
    F["staffing"]["officers_per_1k_2012"] = med([float(e["sworn_per_1k"]) for e in e12 if e["sworn_per_1k"]])
    F["staffing"]["pay_real_2012"] = med([float(e["sworn_pay_annualized_real_usd"]) for e in e12 if e["sworn_pay_annualized_real_usd"]])

    # --- 6. how uniform the numerator is (from the spot checks)
    best = {}
    for r in sc:
        if r["ratio_police"] and r["framing"].startswith(("general_fund", "all_funds")):
            best.setdefault(r["city"], r)
    ratios = sorted(float(r["census_police_fire_usd"]) / (int(r["doc_police_usd"]) + int(r["doc_fire_usd"]))
                    for r in best.values() if r["doc_police_usd"] and r["doc_fire_usd"])
    qq = statistics.quantiles(ratios, n=4)
    F["numerator"] = dict(n=len(ratios), median=round(statistics.median(ratios), 2), q1=round(qq[0], 2), q3=round(qq[2], 2),
                          within_20pct=sum(1 for x in ratios if abs(x - 1) <= .2))

    # --- 7. structure: what the denominators do to the same city
    F["structure"] = []
    for name in ("New York", "Philadelphia", "San Francisco And County", "Houston", "Phoenix", "Plano"):
        r = next((x for x in wide if x["city"] == name), None)
        if r:
            F["structure"].append(dict(city=name.replace(" And County", ""), general=float(r["police_fire_pct_general"]),
                                       core=float(r["police_fire_pct_core"]), total=float(r["police_fire_pct_total"])))
    # The stamp belongs to the computation, not to whoever last ran a renderer. The deploy
    # re-renders the page to add its fact-sheet links; without this the deployed copy would
    # claim a later build date than the committed and published ones, which it did.
    F["built"] = datetime.date.today().isoformat()
    json.dump(F, open(os.path.join(OUT, "findings.json"), "w"), indent=1)
    print(json.dumps(F, indent=1)[:4000], file=sys.stderr)


if __name__ == "__main__":
    main()
