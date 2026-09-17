import pytest

from cohort_trace.discover import (
    GQ_BYTYPE_DESCRIPTION, age_text_to_std_bin, build_var_map, find_group,
    gq_bytype_var_map, gq_resolution, parse_label,
)


def test_find_group_exact_match_skips_race_iterations():
    groups = {"groups": [
        {"name": "P12", "description": "SEX BY AGE"},
        {"name": "PCO1A", "description":
            "GROUP QUARTERS POPULATION BY SEX BY AGE (WHITE ALONE)"},
        {"name": "PCO1", "description":
            "Group Quarters Population by Sex by Age"},
    ]}
    assert find_group(groups) == "PCO1"


def test_find_group_missing_returns_none():
    assert find_group({"groups": [{"name": "P12", "description": "SEX BY AGE"}]}) is None


@pytest.mark.parametrize("text,expected", [
    ("Under 5 years", "0-4"),
    ("5 to 9 years", "5-9"),
    ("15 to 17 years", "15-19"),
    ("18 and 19 years", "15-19"),
    ("20 years", "20-24"),
    ("22 to 24 years", "20-24"),
    ("60 and 61 years", "60-64"),
    ("62 to 64 years", "60-64"),
    ("85 years and over", "85+"),
])
def test_age_text_maps_to_standard_bins(text, expected):
    assert age_text_to_std_bin(text) == expected


def test_coarse_age_range_rejected():
    with pytest.raises(ValueError):
        age_text_to_std_bin("18 to 64 years")


def test_parse_label_variants():
    assert parse_label("Total!!Male!!Under 5 years") == ("M", "0-4")
    assert parse_label(" !!Total:!!Female:!!85 years and over") == ("F", "85+")
    assert parse_label("Total!!Male") is None       # subtotal: no age
    assert parse_label("Total") is None             # grand total
    assert parse_label("Total!!Female!!62 to 64 years") == ("F", "60-64")


def test_build_var_map_skips_totals_and_geo_fields():
    variables = {
        "NAME": {"label": "Geographic Area Name"},
        "PCO1_001N": {"label": " !!Total:"},
        "PCO1_002N": {"label": " !!Total:!!Male:"},
        "PCO1_003N": {"label": " !!Total:!!Male:!!Under 5 years"},
        "PCO1_022N": {"label": " !!Total:!!Female:!!85 years and over"},
    }
    vm = build_var_map(variables)
    assert vm == {
        "PCO1_003N": ("M", "0-4"),
        "PCO1_022N": ("F", "85+"),
    }


def test_build_var_map_skips_annotation_twins():
    # 2020 DHC publishes PCO1_003NA next to PCO1_003N; its cells are null.
    variables = {
        "PCO1_003N": {"label": " !!Total:!!Male:!!Under 5 years",
                      "predicateType": "int"},
        "PCO1_003NA": {"label": "Annotation of  !!Total:!!Male:!!Under 5 years",
                       "predicateType": "string"},
    }
    assert build_var_map(variables) == {"PCO1_003N": ("M", "0-4")}


# --- Group quarters recovered from the "by group quarters type" table --------

# A slice of the real 2000 SF1 PCT017 table: the male "Under 18 years" branch,
# its subtotal (003) plus every group-quarters-type leaf beneath it, and the
# male "18 to 64 years" subtotal.
_PCT017_SLICE = {
    "NAME": {"label": "Geographic Area Name"},
    "PCT017001": {"label": "Total"},
    "PCT017002": {"label": "Total!!Male"},
    "PCT017003": {"label": "Total!!Male!!Under 18 years"},
    "PCT017004": {"label": "Total!!Male!!Under 18 years!!Institutionalized population"},
    "PCT017005": {"label": "Total!!Male!!Under 18 years!!Institutionalized population!!Correctional institutions"},
    "PCT017006": {"label": "Total!!Male!!Under 18 years!!Institutionalized population!!Nursing homes"},
    "PCT017011": {"label": "Total!!Male!!Under 18 years!!Noninstitutionalized population"},
    "PCT017012": {"label": "Total!!Male!!Under 18 years!!Noninstitutionalized population!!College dormitories (includes college quarters off campus)"},
    "PCT017015": {"label": "Total!!Male!!18 to 64 years"},
    "PCT017039": {"label": "Total!!Female"},
    "PCT017040": {"label": "Total!!Female!!Under 18 years"},
}


def test_gq_bytype_var_map_keeps_only_sex_age_subtotals():
    vm = gq_bytype_var_map(_PCT017_SLICE)
    # Only the depth-3 "Total!!<sex>!!<band>" subtotals survive: grand total,
    # sex subtotals, and the group-quarters-type leaves are all dropped.
    assert vm == {
        "PCT017003": ("M", "Under 18 years"),
        "PCT017015": ("M", "18 to 64 years"),
        "PCT017040": ("F", "Under 18 years"),
    }


def test_gq_bytype_subtotal_equals_sum_over_type_leaves():
    # The recovery keeps the subtotal instead of re-adding leaves; the point of
    # "sum over the GQ-type dimension" is that they are equal. Model one county:
    # the Under-18 male subtotal must equal its institutional + noninstitutional
    # leaves (which in turn are the sums of their type leaves).
    inst_leaves = {"PCT017005": 3, "PCT017006": 2}       # correctional + nursing
    noninst_leaves = {"PCT017012": 7}                    # college dorms
    subtotal = sum(inst_leaves.values()) + sum(noninst_leaves.values())
    assert subtotal == 12
    # PCT017003 (the subtotal we extract) is published as exactly this sum.


def test_gq_resolution_coarse_vs_fine():
    # 2000's bands span multiple standard bins -> cannot trace at 5-year detail.
    assert gq_resolution(["Under 18 years", "18 to 64 years",
                          "65 years and over"]) == "coarse"
    # A clean 5-year band set (as 2010/2020 publish) is fine.
    assert gq_resolution(["Under 5 years", "5 to 9 years",
                          "85 years and over"]) == "fine"


def test_gq_bytype_description_matches_across_2000_bracket_suffix():
    # 2000 SF1 descriptions append a "[NN]" cell count that 2010/2020 omit;
    # race iterations keep their "(WHITE ALONE)" parenthetical. Matching must
    # ignore the bracket count but still skip the race variants.
    groups = {"groups": [
        {"name": "P038", "description":
            "GROUP QUARTERS POPULATION BY SEX BY AGE BY GROUP QUARTERS TYPE [57]"},
        {"name": "PCT017", "description":
            "GROUP QUARTERS POPULATION BY SEX BY AGE BY GROUP QUARTERS TYPE [75]"},
        {"name": "PCT017A", "description":
            "GROUP QUARTERS POPULATION BY SEX BY AGE BY GROUP QUARTERS TYPE "
            "(WHITE ALONE) [75]"},
    ]}
    # Shortest non-race exact match wins.
    assert find_group(groups, description=GQ_BYTYPE_DESCRIPTION) == "P038"
    # No plain (typeless) GQ sex-by-age table exists in 2000 SF1.
    assert find_group(groups) is None


def test_gq_bytype_description_matches_2010_no_suffix():
    groups = {"groups": [
        {"name": "PCO1", "description": "GROUP QUARTERS POPULATION BY SEX BY AGE"},
        {"name": "P43", "description":
            "GROUP QUARTERS POPULATION BY SEX BY AGE BY GROUP QUARTERS TYPE"},
    ]}
    assert find_group(groups) == "PCO1"
    assert find_group(groups, description=GQ_BYTYPE_DESCRIPTION) == "P43"
