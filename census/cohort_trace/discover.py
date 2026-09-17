"""Runtime discovery of Census API table groups and label-driven variable maps.

The group-quarters sex-by-age table has a different name in each dataset
(2000 SF1 / 2010 SF1 / 2020 DHC), so instead of hardcoding variable IDs we
locate the table by its published description in groups.json and derive each
variable's (sex, age bin) from its label. Anything unexpected fails loudly.
"""

from __future__ import annotations

import re

from .bins import STD_BINS, std_bin

GQ_DESCRIPTION = "GROUP QUARTERS POPULATION BY SEX BY AGE"

# 2000 SF1 has no plain "GROUP QUARTERS POPULATION BY SEX BY AGE" table (the
# PCO1 series first appears in 2010). It only carries the group-quarters
# sex-by-age tables that add a group-quarters-*type* dimension (P038 / PCT017).
# Collapsing that type dimension recovers group quarters by sex by age -- but
# only across three coarse age bands (Under 18 / 18 to 64 / 65 and over), which
# is all 2000 SF1 tabulated. See recover_gq_by_type / gq_resolution below.
GQ_BYTYPE_DESCRIPTION = (
    "GROUP QUARTERS POPULATION BY SEX BY AGE BY GROUP QUARTERS TYPE"
)


def _normalize_description(text: str) -> str:
    """Upper-case a group description and drop a trailing cell-count suffix.

    2000 SF1 descriptions append the number of cells in brackets, e.g.
    "...BY GROUP QUARTERS TYPE [57]", while 2010 SF1 / 2020 DHC do not. The
    count is metadata, not part of the table's identity, so strip it before
    matching. Race-iterated variants keep their "(WHITE ALONE)" parenthetical,
    so they still fail an exact match and are skipped.
    """
    return re.sub(r"\s*\[\d+\]\s*$", "", text.strip()).upper()


def find_group(groups_json: dict, description: str = GQ_DESCRIPTION) -> str | None:
    """Find the table group whose description matches exactly.

    Exact matching skips race-iterated variants, whose descriptions append
    a parenthetical like "(WHITE ALONE)". Returns None if the dataset has
    no such table.
    """
    target = description.strip().upper()
    matches = [
        g["name"]
        for g in groups_json.get("groups", [])
        if _normalize_description(g.get("description", "")) == target
    ]
    if not matches:
        return None
    return sorted(matches, key=len)[0]


_STD_RANGES = []
for _bin in STD_BINS:
    if _bin.endswith("+"):
        _STD_RANGES.append((int(_bin[:-1]), 200, _bin))
    else:
        _lo, _hi = _bin.split("-")
        _STD_RANGES.append((int(_lo), int(_hi), _bin))


def _age_range(text: str) -> tuple[int, int] | None:
    t = text.lower().replace(",", "").strip()
    if m := re.match(r"under (\d+)", t):
        return 0, int(m.group(1)) - 1
    if m := re.match(r"(\d+) years? and (over|older)", t):
        return int(m.group(1)), 200
    if m := re.match(r"(\d+) (?:to|through) (\d+)", t):
        return int(m.group(1)), int(m.group(2))
    if m := re.match(r"(\d+) and (\d+) years", t):
        return int(m.group(1)), int(m.group(2))
    if m := re.match(r"(\d+) years?$", t):
        return int(m.group(1)), int(m.group(1))
    return None


def age_text_to_std_bin(text: str) -> str:
    """Map an age label like '62 to 64 years' to its standard 5-year bin.

    Raises ValueError if the text is unparseable or spans more than one
    standard bin (e.g. '18 to 64 years' from a coarse table) — a sign we
    discovered the wrong table.
    """
    rng = _age_range(text)
    if rng is None:
        raise ValueError(f"unparseable age text: {text!r}")
    lo, hi = rng
    for blo, bhi, name in _STD_RANGES:
        if blo <= lo and hi <= bhi:
            return std_bin(name)
    raise ValueError(f"age range {text!r} spans multiple standard bins")


def parse_label(label: str) -> tuple[str, str] | None:
    """Extract (sex, standard age bin) from a variable label.

    Labels look like 'Total!!Male!!Under 5 years' (2010) or
    ' !!Total:!!Female:!!85 years and over' (2020). Returns None for
    totals/subtotals that carry no sex or no age component; raises
    ValueError for an age component that doesn't fit a standard bin.
    """
    parts = [p.strip().rstrip(":").lower() for p in label.split("!!")]
    sex = None
    for p in parts:
        if p == "male":
            sex = "M"
        elif p == "female":
            sex = "F"
    age_text = next((p for p in parts if "year" in p), None)
    if sex is None or age_text is None:
        return None
    return sex, age_text_to_std_bin(age_text)


def build_var_map(group_variables: dict) -> dict[str, tuple[str, str]]:
    """Map each data variable in a discovered group to (sex, std age bin)."""
    out = {}
    for var, meta in group_variables.items():
        label = meta.get("label", "")
        if var in ("NAME", "GEO_ID") or not label:
            continue
        # 2020 DHC publishes an annotation twin per value variable
        # (PCO1_003NA next to PCO1_003N) whose cells are null strings.
        if (label.lower().startswith("annotation")
                or meta.get("predicateType") == "string"):
            continue
        try:
            parsed = parse_label(label)
        except ValueError as exc:
            raise RuntimeError(f"variable {var}: {exc}") from exc
        if parsed is not None:
            out[var] = parsed
    return out


# --- Group quarters recovered from the "by group quarters type" table --------
#
# 2000 SF1's only group-quarters sex-by-age tables (P038, PCT017) hang the
# counts under a group-quarters-type dimension. The marginal over that
# dimension -- i.e. the sex-by-age-band subtotal, the label with exactly
# "Total!!<sex>!!<age band>" -- is group quarters by sex by age with the type
# dimension summed out. We extract those subtotals rather than re-adding the
# leaves, and a test asserts the subtotal equals the sum of its type leaves.


def _label_parts(label: str) -> list[str]:
    return [p.strip().rstrip(":") for p in label.split("!!") if p.strip()]


def gq_bytype_var_map(group_variables: dict) -> dict[str, tuple[str, str]]:
    """Map the sex-by-age-band subtotal variables of a "...BY GROUP QUARTERS
    TYPE" table to (sex, raw age-band text).

    The subtotal (label depth 3: Total / <sex> / <age band>) is the group
    quarters count for that sex and age band summed over every group-quarters
    type -- exactly the "sum over the GQ-type dimension" the recovery needs.
    The age-band text is returned verbatim (e.g. '18 to 64 years'); callers
    use gq_resolution() to learn whether those bands are fine enough to trace.
    """
    out: dict[str, tuple[str, str]] = {}
    for var, meta in group_variables.items():
        if var in ("NAME", "GEO_ID"):
            continue
        label = meta.get("label", "")
        if (label.lower().startswith("annotation")
                or meta.get("predicateType") == "string"):
            continue
        parts = _label_parts(label)
        if len(parts) != 3:
            continue  # skip the grand total, sex subtotals, and type leaves
        sex = {"male": "M", "female": "F"}.get(parts[1].lower())
        if sex is None or "year" not in parts[2].lower():
            continue
        out[var] = (sex, parts[2])
    if not out:
        raise RuntimeError("no sex-by-age-band subtotals found in group")
    return out


def gq_resolution(band_texts) -> str:
    """Classify a set of age-band texts as 'fine' or 'coarse'.

    'fine' means every band maps cleanly to a single standard 5-year bin, so
    the recovered counts can feed the survival-ratio engine. 'coarse' means at
    least one band spans several standard bins (e.g. 2000's '18 to 64 years'),
    so the counts cannot be subtracted at 5-year resolution and the decade
    must stay on the total-population basis.
    """
    for text in band_texts:
        try:
            age_text_to_std_bin(text)
        except ValueError:
            return "coarse"
    return "fine"
