"""Peer-city matching (Phase 2, item 4A).

For every city, the 8 most similar other cities on the things that make police and fire shares comparable,
in this order of weight:

  structure   +1.5 for each mismatch in: consolidated or independent city, runs its own schools,
              fire provided by an outside district, police bought from another government;
              +1.0 for a mismatch in the data-driven county-function flag
  size        |log2(population ratio)|   (a city twice or half the size adds 1.0)
  prices      |regional price parity difference| / 10   (10 points apart adds 1.0; 2022 metro RPP)

Candidates must have a complete 2022 record. Each group gets a quality label from the median distance of its
8 peers: "close" under 1.5, "loose" under 3.0, and "weak" at 3.0 or more OR whenever every one of the 8 differs
on at least one structural flag (a city with no structural match, such as New York or a contract-police city,
still gets 8 peers, but the label says they are not like it). Weights are judgment calls, stated here and in METHODOLOGY
so anyone can re-run with different ones; the ranking is not sensitive to modest changes (see --sensitivity).

Output: data/census_out/peer_groups.csv
"""
import csv, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build

N_PEERS = 8
W_STRUCT = {"consolidated_or_independent": 1.5, "runs_schools": 1.5, "fire_external": 1.5, "police_contracted": 1.5, "county_like_functions": 1.0}
W_SIZE, RPP_SCALE = 1.0, 10.0


def load():
    fin = {r["pid"]: r for r in csv.DictReader(open(os.path.join(build.OUT, "city_police_fire_2022.csv")))}
    flags = {r["pid"]: r for r in csv.DictReader(open(os.path.join(build.OUT, "city_flags.csv")))}
    rpp = {r["pid"]: r for r in csv.DictReader(open(os.path.join(build.OUT, "city_rpp.csv")))}
    cities = []
    for pid, r in fin.items():
        f = flags[pid]
        cities.append(dict(pid=pid, city=r["city"], state=r["state"], pop=int(r["population"]), complete=r["record_complete"] == "True",
                           rpp=float(rpp[pid]["rpp_2022"]) if rpp.get(pid) and rpp[pid]["rpp_2022"] else None,
                           cbsa=rpp.get(pid, {}).get("cbsa_title", ""),
                           **{k: f[k] == "True" for k in W_STRUCT}))
    return cities


def distance(a, b, w_struct=W_STRUCT, w_size=W_SIZE, rpp_scale=RPP_SCALE):
    mism = [k for k in w_struct if a[k] != b[k]]
    d_struct = sum(w_struct[k] for k in mism)
    d_size = w_size * abs(math.log2(b["pop"] / a["pop"]))
    d_rpp = abs(a["rpp"] - b["rpp"]) / rpp_scale if (a["rpp"] and b["rpp"]) else 1.0
    return d_struct + d_size + d_rpp, mism, d_size, d_rpp


def peers_for(a, cities, **kw):
    cand = [b for b in cities if b["pid"] != a["pid"] and b["complete"]]
    scored = sorted(((distance(a, b, **kw), b) for b in cand), key=lambda x: x[0][0])
    return scored[:N_PEERS]


def main():
    cities = load()
    rows = []
    for a in sorted(cities, key=lambda c: -c["pop"]):
        group = peers_for(a, cities)
        med = sorted(x[0][0] for x in group)[len(group) // 2]
        all_mismatched = all(x[0][1] for x in group)      # every peer differs on at least one structural flag
        quality = "weak" if (med >= 3.0 or all_mismatched) else "close" if med < 1.5 else "loose"
        for rank, ((d, mism, ds, dr), b) in enumerate(group, 1):
            rows.append(dict(pid=a["pid"], city=a["city"], state=a["state"], rank=rank, peer_pid=b["pid"], peer_city=b["city"], peer_state=b["state"],
                             distance=round(d, 3), structure_mismatches="|".join(mism), size_component=round(ds, 3), price_component=round(dr, 3),
                             population=a["pop"], peer_population=b["pop"], rpp_2022=a["rpp"], peer_rpp_2022=b["rpp"], group_quality=quality))
    with open(os.path.join(build.OUT, "peer_groups.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    import collections
    q = collections.Counter(r["group_quality"] for r in rows if r["rank"] == 1)
    print(f"{len(rows)} peer links for {len(cities)} cities; group quality {dict(q)}; weak: {[r['city']+' '+r['state'] for r in rows if r['rank']==1 and r['group_quality']=='weak']}", file=sys.stderr)
    if "--sensitivity" in sys.argv:
        base = {a["pid"]: {b["pid"] for _, b in peers_for(a, cities)} for a in cities}
        for label, kw in (("structure weights x0.67", dict(w_struct={k: v * 0.67 for k, v in W_STRUCT.items()})),
                          ("structure weights x1.5", dict(w_struct={k: v * 1.5 for k, v in W_STRUCT.items()})),
                          ("price scale 5", dict(rpp_scale=5.0)), ("price scale 20", dict(rpp_scale=20.0)),
                          ("size weight 0.5", dict(w_size=0.5)), ("size weight 2", dict(w_size=2.0))):
            overlap = [len(base[a["pid"]] & {b["pid"] for _, b in peers_for(a, cities, **kw)}) / N_PEERS for a in cities]
            print(f"  {label:<26} median overlap with default peer set {sorted(overlap)[len(overlap)//2]:.0%}, mean {sum(overlap)/len(overlap):.0%}", file=sys.stderr)


if __name__ == "__main__":
    main()
