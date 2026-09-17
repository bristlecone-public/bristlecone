import pandas as pd

from cohort_trace.engine import trace


def _rows(year, unit, sex, age_bin, count):
    return {"year": year, "unit": unit, "sex": sex,
            "age_bin": age_bin, "count": count}


def test_residual_recovers_known_migration():
    # Two counties, one cohort. Nationally the 20-24 cohort of 2000 survives
    # at 0.9 into 30-34 of 2010. County A loses 100 people to county B.
    df = pd.DataFrame([
        _rows(2000, "A", "M", "20-24", 1000),
        _rows(2000, "B", "M", "20-24", 1000),
        _rows(2010, "A", "M", "30-34", 800),   # 900 expected - 100 moved
        _rows(2010, "B", "M", "30-34", 1000),  # 900 expected + 100 moved
    ])
    out = trace(df, 2000, 2010)
    row_a = out[(out["unit"] == "A") & (out["cohort_age_at_t0"] == "20-24")].iloc[0]
    row_b = out[(out["unit"] == "B") & (out["cohort_age_at_t0"] == "20-24")].iloc[0]

    assert row_a["national_ratio"] == 0.9
    assert row_a["net_residual"] == -100
    assert row_b["net_residual"] == 100
    assert abs(row_a["net_migration_rate"] + 100 / 900) < 1e-9
    assert row_a["birth_years"] == "1975-1980"


def test_residuals_sum_to_zero_nationally():
    df = pd.DataFrame([
        _rows(2000, u, s, b, c)
        for u, s, b, c in [("A", "M", "10-14", 500), ("B", "M", "10-14", 700),
                           ("C", "M", "10-14", 300)]
    ] + [
        _rows(2010, u, s, b, c)
        for u, s, b, c in [("A", "M", "20-24", 450), ("B", "M", "20-24", 800),
                           ("C", "M", "20-24", 200)]
    ])
    out = trace(df, 2000, 2010)
    cohort = out[out["cohort_age_at_t0"] == "10-14"]
    assert abs(cohort["net_residual"].sum()) < 1e-9


def test_oldest_closed_bins_combine_into_open_bin():
    df = pd.DataFrame([
        _rows(2000, "A", "F", "75-79", 100),
        _rows(2000, "A", "F", "80-84", 50),
        _rows(2010, "A", "F", "85+", 60),
    ])
    out = trace(df, 2000, 2010)
    row = out[out["cohort_age_at_t0"] == "75-84"].iloc[0]
    assert row["count_t0"] == 150
    assert row["count_t1"] == 60
    # Single unit == the nation, so the residual must be exactly zero.
    assert row["net_residual"] == 0


def test_small_expected_flagged_low_reliability():
    df = pd.DataFrame([
        _rows(2000, "A", "M", "40-44", 50),
        _rows(2000, "B", "M", "40-44", 5000),
        _rows(2010, "A", "M", "50-54", 48),
        _rows(2010, "B", "M", "50-54", 4800),
    ])
    out = trace(df, 2000, 2010)
    by_unit = out.set_index("unit")
    assert by_unit.loc["A", "reliability"] == "low"
    assert by_unit.loc["B", "reliability"] == "ok"


def _gq_rows(year, unit, sex, age_bin, count, gq):
    return {"year": year, "unit": unit, "sex": sex,
            "age_bin": age_bin, "count": count, "gq_count": gq}


def test_household_basis_removes_college_artifact():
    # County A gains 600 dorm residents in the cohort's destination bin.
    # On a household basis nobody migrated; on a total basis A looks like a
    # big importer.
    df = pd.DataFrame([
        _gq_rows(2010, "A", "M", "10-14", 1000, 0),
        _gq_rows(2010, "B", "M", "10-14", 1000, 0),
        _gq_rows(2020, "A", "M", "20-24", 1500, 600),
        _gq_rows(2020, "B", "M", "20-24", 900, 0),
    ])
    household = trace(df, 2010, 2020, basis="household")
    row_a = household[household["unit"] == "A"].iloc[0]
    row_b = household[household["unit"] == "B"].iloc[0]
    assert row_a["net_residual"] == 0
    assert row_b["net_residual"] == 0
    assert row_a["basis"] == "household"

    total = trace(df, 2010, 2020, basis="total")
    assert total[total["unit"] == "A"].iloc[0]["net_residual"] == 300
    assert total[total["unit"] == "B"].iloc[0]["net_residual"] == -300


def test_household_basis_requires_gq_column():
    df = pd.DataFrame([
        _rows(2000, "A", "M", "20-24", 1000),
        _rows(2010, "A", "M", "30-34", 900),
    ])
    import pytest
    with pytest.raises(ValueError):
        trace(df, 2000, 2010, basis="household")

def test_specs_adapt_to_coarse_historical_bins():
    from cohort_trace.bins import NHGIS_YEAR_BINS, STD_BINS
    from cohort_trace.engine import specs_for

    full = set(STD_BINS)
    # both ends full-resolution -> 16 specs, last is 75-79+80-84 -> 85+
    specs = specs_for(full, full)
    assert len(specs) == 16
    assert specs[-1] == ("75-84", ["75-79", "80-84"], "85+")

    # 1950 -> 1960: source publishes a merged 75-84
    specs = specs_for(set(NHGIS_YEAR_BINS[1950]), full)
    assert ("75-84", ["75-84"], "85+") in specs
    assert len(specs) == 16

    # 1970 -> 1980: destination has no 75-79/80-84 split
    specs = specs_for(full, set(NHGIS_YEAR_BINS[1980]))
    labels = [s[0] for s in specs]
    assert "65-69" not in labels and "70-74" not in labels
    assert ("65-74", ["65-69", "70-74"], "75-84") in specs
    assert ("75-84", ["75-79", "80-84"], "85+") in specs
    # 60-64 -> 70-74 still traces fine
    assert ("60-64", ["60-64"], "70-74") in specs


def test_units_absent_from_one_endpoint_are_dropped():
    # "PR" exists only at t1 (e.g. a geography the t0 source doesn't cover):
    # it must not appear as a fabricated 100% in-migration flow.
    df = pd.DataFrame([
        _rows(1990, "A", "M", "10-14", 500),
        _rows(1990, "B", "M", "10-14", 500),
        _rows(2000, "A", "M", "20-24", 450),
        _rows(2000, "B", "M", "20-24", 550),
        _rows(2000, "PR", "M", "20-24", 900),
    ])
    out = trace(df, 1990, 2000)
    assert "PR" not in set(out["unit"])
    cohort = out[out["cohort_age_at_t0"] == "10-14"]
    assert abs(cohort["net_residual"].sum()) < 1e-9
