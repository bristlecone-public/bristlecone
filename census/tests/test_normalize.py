from cohort_trace.fetch import _p12_vars, var_map
from cohort_trace.normalize import normalize_year


def _fake_raw(year):
    """One county where every published age category has count 1."""
    variables = _p12_vars(year)
    header = ["NAME"] + variables + ["state", "county"]
    row = ["Test County"] + ["1"] * len(variables) + ["06", "037"]
    return [header, row]


def test_variable_order_maps_male_then_female():
    vm = var_map(2010)
    assert vm["P012003"] == ("M", "0-4")
    assert vm["P012025"] == ("M", "85+")
    assert vm["P012027"] == ("F", "0-4")
    assert vm["P012049"] == ("F", "85+")
    vm2020 = var_map(2020)
    assert vm2020["P12_003N"] == ("M", "0-4")
    assert vm2020["P12_049N"] == ("F", "85+")


def test_sub_bins_collapse_into_standard_bins():
    df = normalize_year(_fake_raw(2010), 2010)
    male = df[df["sex"] == "M"].set_index("age_bin")["count"]
    # 15-17 + 18-19 -> 15-19; 20 + 21 + 22-24 -> 20-24; etc.
    assert male["15-19"] == 2
    assert male["20-24"] == 3
    assert male["60-64"] == 2
    assert male["65-69"] == 2
    assert male["0-4"] == 1
    assert male["85+"] == 1
    assert male.sum() == 23  # all published categories accounted for
    assert df["geoid"].iloc[0] == "06037"


def test_2020_layout_normalizes_identically():
    df = normalize_year(_fake_raw(2020), 2020)
    assert df[df["sex"] == "F"].set_index("age_bin")["count"]["20-24"] == 3
