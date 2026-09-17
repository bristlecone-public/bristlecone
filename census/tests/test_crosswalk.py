import pandas as pd

from cohort_trace.crosswalk import apply_crosswalk, canonical_unit


def test_renames():
    assert canonical_unit("46113") == "46102"  # Shannon -> Oglala Lakota
    assert canonical_unit("02270") == "02158"  # Wade Hampton -> Kusilvak
    assert canonical_unit("12025") == "12086"  # Dade -> Miami-Dade
    assert canonical_unit("30113") == "30031"  # Yellowstone NP -> Gallatin


def test_merge_groups():
    assert canonical_unit("02261") == "MG-AK-VALDEZ-CORDOVA"
    assert canonical_unit("02063") == "MG-AK-VALDEZ-CORDOVA"
    assert canonical_unit("51515") == "MG-VA-BEDFORD"


def test_broomfield_not_merged():
    # Broomfield (08014) and its four parents are traced standalone; the 2000
    # baseline is reconstructed in broomfield.py, not merged here.
    assert canonical_unit("08014") == "08014"
    assert canonical_unit("08013") == "08013"
    assert canonical_unit("08001") == "08001"
    assert canonical_unit("08059") == "08059"
    assert canonical_unit("08123") == "08123"


def test_1990_era_merge_groups():
    # Skagway-Yakutat-Angoon (1990) and its successors share a unit
    assert canonical_unit("02231") == "MG-AK-SOUTHEAST"
    assert canonical_unit("02282") == "MG-AK-SOUTHEAST"
    assert canonical_unit("02232") == "MG-AK-SOUTHEAST"
    # Denali Borough didn't exist on 1990 census day
    assert canonical_unit("02068") == "MG-AK-DENALI"
    assert canonical_unit("02290") == "MG-AK-DENALI"
    # South Boston city reverted into Halifax County in 1995
    assert canonical_unit("51780") == "MG-VA-HALIFAX"
    assert canonical_unit("51083") == "MG-VA-HALIFAX"


def test_stable_counties_pass_through():
    assert canonical_unit("06037") == "06037"


def test_apply_crosswalk_aggregates_merged_units():
    df = pd.DataFrame([
        {"year": 2010, "geoid": "51515", "name": "Bedford city",
         "sex": "M", "age_bin": "20-24", "count": 100},
        {"year": 2010, "geoid": "51019", "name": "Bedford County",
         "sex": "M", "age_bin": "20-24", "count": 900},
        {"year": 2010, "geoid": "06037", "name": "Los Angeles County",
         "sex": "M", "age_bin": "20-24", "count": 5000},
    ])
    out = apply_crosswalk(df)
    bedford = out[out["unit"] == "MG-VA-BEDFORD"]
    assert len(bedford) == 1
    assert bedford["count"].iloc[0] == 1000
    la = out[out["unit"] == "06037"]
    assert la["name"].iloc[0] == "Los Angeles County"


def test_apply_crosswalk_aggregates_gq_counts():
    df = pd.DataFrame([
        {"year": 2010, "geoid": "51515", "name": "Bedford city",
         "sex": "M", "age_bin": "20-24", "count": 100, "gq_count": 10},
        {"year": 2010, "geoid": "51019", "name": "Bedford County",
         "sex": "M", "age_bin": "20-24", "count": 900, "gq_count": 40},
    ])
    out = apply_crosswalk(df)
    bedford = out[out["unit"] == "MG-VA-BEDFORD"].iloc[0]
    assert bedford["count"] == 1000
    assert bedford["gq_count"] == 50
