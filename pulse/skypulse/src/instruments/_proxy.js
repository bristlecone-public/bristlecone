// Read an upstream payload that a homelab job parked in KV, falling back to
// fetching it directly.
//
// WHY: a few upstreams refuse Cloudflare's egress. Kalshi answers 429 to this
// Worker at a 6h cadence — eight requests a day, so it is not our volume; Workers
// leave through a shared IP pool and we are in someone else's rate-limit bucket.
// CelesTrak answers 522. Both serve the same URLs fine from a residential IP.
//
// So a job on the pipeline host fetches them and PUTs the response under
// `proxy:<key>` in this app's SNAPSHOTS namespace, and the instrument reads that
// instead. It is a change of vantage point, not a way around anything: same
// public endpoints, same 6h cadence, a contactable User-Agent.
//
// FALLBACK IS THE POINT. If no fresh proxy entry exists the instrument fetches
// the upstream itself, so this repository still works for anyone who clones it
// without a homelab — they simply get whatever their own IP is entitled to. The
// freshness bound matters too: a stale proxy entry must not quietly pin the card
// to an old reading, so past maxAge we prefer a live attempt even if it fails.
export async function viaProxy({ env, http, key, url, maxAgeMs = 24 * 36e5 }) {
  try {
    const parked = await env?.SNAPSHOTS?.get(`proxy:${key}`, 'json');
    if (parked?.fetchedAt && parked.body !== undefined) {
      const age = Date.now() - Date.parse(parked.fetchedAt);
      if (Number.isFinite(age) && age >= 0 && age < maxAgeMs) return parked.body;
    }
  } catch {
    // A KV hiccup must never be worse than not having the proxy at all.
  }
  return http.json(url);
}
