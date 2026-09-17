"""County comparability across the 2000, 2010, and 2020 censuses.

Counties are stable enough to compare by FIPS code across decades, with a
short list of exceptions. Two mechanisms handle them:

- RENAMES: 1:1 FIPS recodes (same territory, new code).
- MERGE_GROUPS: counties involved in splits, merges, or boundary transfers
  are combined into a single analysis unit across all years, so the unit's
  territory is constant even though its component counties are not.

Sources: Census Bureau county boundary change notices, 2000-2020.
"""

from __future__ import annotations

import pandas as pd

# Same territory, new FIPS code.
RENAMES = {
    "46113": "46102",  # Shannon County, SD -> Oglala Lakota County (2015)
    "02270": "02158",  # Wade Hampton, AK -> Kusilvak Census Area (2015)
    "12025": "12086",  # Dade County, FL -> Miami-Dade (1997 FIPS change)
    # Yellowstone National Park, MT (pop. 52 in 1990) was absorbed into
    # Gallatin (mostly) and Park in 1997; treated as a rename into Gallatin
    # rather than merging Gallatin with Park over <=52 people.
    "30113": "30031",
    "32025": "32510",  # Ormsby County, NV -> Carson City (consolidated 1969)
    "29193": "29186",  # Ste. Genevieve, MO (1979 FIPS change)
    "02140": "02188",  # Kobuk, AK -> Northwest Arctic Borough (1986)
    # Yellowstone NP's Wyoming county-equivalent (pop. ~400) went to Teton
    # (mostly) and Park in 1966; renamed into Teton.
    "56047": "56039",
}

# Units whose components changed between censuses; combined for all years.
MERGE_GROUPS = {
    # Southeast Alaska reorganizations 1990->2010: Skagway-Yakutat-Angoon
    # (02231, the 1990 unit) lost Yakutat (02282) in 1992, becoming
    # Skagway-Hoonah-Angoon (02232), which split into 02230 + 02105 in
    # 2007; Prince of Wales-Outer Ketchikan (02201) dissolved into
    # 02198/02130; Wrangell-Petersburg (02280) split into 02275 + 02195.
    "MG-AK-SOUTHEAST": {
        "02231",                            # 1990 code
        "02201", "02232", "02280", "02282",  # 2000 codes
        "02105", "02195", "02198", "02230", "02275",  # successor codes
        "02130",                            # Ketchikan Gateway (absorbed part of 02201)
    },
    # Denali Borough (02068) organized June 1990 -- after census day -- from
    # parts of Yukon-Koyukuk (02290) and Southeast Fairbanks (02240).
    "MG-AK-DENALI": {"02068", "02240", "02290"},
    # Valdez-Cordova (02261) split into Chugach (02063) + Copper River (02066), 2019.
    "MG-AK-VALDEZ-CORDOVA": {"02261", "02063", "02066"},
    # Broomfield County, CO (08014) was created 2001 from parts of Adams,
    # Boulder, Jefferson and Weld. It is NOT merged with its parents: merging
    # all four whole counties (~2M people) to keep one ~70k unit's territory
    # constant erased four distinct Denver-metro signals. Instead Broomfield is
    # traced standalone from 2000 on, its 4/1/2000 baseline reconstructed from
    # the Census Bureau's 2000-2010 intercensal county file (2010 boundaries,
    # Broomfield present and the parents already reduced); pre-2000 decades use
    # the parents' actual then-territory. See broomfield.py.
    # Alleghany County (51005) lost Covington city in 1952 and Clifton
    # Forge city (51560), which reverted into it in 2001.
    "MG-VA-ALLEGHANY": {"51560", "51005", "51580"},
    # Bedford city (51515) reverted into Bedford County (51019), 2013.
    "MG-VA-BEDFORD": {"51515", "51019"},
    # South Boston city (51780) reverted into Halifax County (51083), 1995.
    "MG-VA-HALIFAX": {"51780", "51083"},

    # --- 1950-1990 era (units verified against the NHGIS files) ---------
    # Aleutian Islands (02010) split into Aleutians East (02013) +
    # Aleutians West (02016), 1987.
    "MG-AK-ALEUTIANS": {"02010", "02013", "02016"},
    # Lake and Peninsula Borough (02164) carved from Dillingham (02070), 1989.
    "MG-AK-DILLINGHAM": {"02164", "02070"},
    # La Paz County (04012) carved from Yuma (04027), 1983.
    "MG-AZ-YUMA": {"04012", "04027"},
    # Kalawao's 1950 age table is folded into Maui (its administrator);
    # merged throughout (pop. < 350 all years).
    "MG-HI-MAUI": {"15005", "15009"},
    # Cibola County (35006) carved from Valencia (35061), 1981.
    "MG-NM-VALENCIA": {"35006", "35061"},
    # Armstrong County, SD (46001, unorganized) dissolved into Dewey
    # (46041), 1952.
    "MG-SD-DEWEY": {"46001", "46041"},
    # Washabaugh County (46131) merged into Jackson (46071), 1983.
    "MG-SD-JACKSON": {"46131", "46071"},
    # Menominee County (55078) created from Shawano (55115), 1961.
    "MG-WI-SHAWANO": {"55078", "55115"},

    # Virginia's independent-city era. Each group combines a city with the
    # county (or counties) whose territory it took, so the unit is constant
    # 1950-2020.
    # Hampton absorbed Elizabeth City County (+ Phoebus), 1952.
    "MG-VA-HAMPTON": {"51650", "51055"},
    # Newport News absorbed Warwick (county, then city), 1958.
    "MG-VA-NEWPORT-NEWS": {"51700", "51189"},
    # Virginia Beach city (independent 1952) consolidated with Princess
    # Anne County, 1963.
    "MG-VA-VIRGINIA-BEACH": {"51810", "51151"},
    # South Hampton Roads: Norfolk County (51129) was carved up by
    # Chesapeake (with South Norfolk city, 1963) and by Norfolk city and
    # Portsmouth annexations through the 1950s.
    "MG-VA-TIDEWATER": {"51550", "51129", "51785", "51710", "51740"},
    # Suffolk consolidated with Nansemond (county, then city), 1974.
    "MG-VA-SUFFOLK": {"51800", "51123"},
    # Covington city (independent 1952) joins the Alleghany group below.
    # Galax city (1954) took territory from both Carroll and Grayson.
    "MG-VA-GALAX": {"51640", "51035", "51077"},
    # Norton city (1954) from Wise County.
    "MG-VA-WISE": {"51720", "51195"},
    # Emporia city (1967) from Greensville County.
    "MG-VA-GREENSVILLE": {"51595", "51081"},
    # Fairfax city (1961) from Fairfax County.
    "MG-VA-FAIRFAX": {"51600", "51059"},
    # Franklin city (1961) from Southampton County.
    "MG-VA-SOUTHAMPTON": {"51620", "51175"},
    # Lexington city (1966) from Rockbridge County.
    "MG-VA-ROCKBRIDGE": {"51678", "51163"},
    # Roanoke Valley: Salem city (1968) from Roanoke County, which also
    # lost major territory to Roanoke city annexations (1949, 1976).
    "MG-VA-ROANOKE": {"51775", "51161", "51770"},
    # Manassas + Manassas Park (1975) from Prince William County.
    "MG-VA-PRINCE-WILLIAM": {"51683", "51685", "51153"},
    # Poquoson city (1975) from York County.
    "MG-VA-YORK": {"51735", "51199"},
    # Richmond's 1970 annexation moved ~47k people out of Chesterfield.
    "MG-VA-RICHMOND": {"51760", "51041"},
    # Lynchburg's 1976 annexation took a large part of Campbell County.
    "MG-VA-LYNCHBURG": {"51680", "51031"},
}

_MEMBER_TO_GROUP = {
    fips: group for group, members in MERGE_GROUPS.items() for fips in members
}


def canonical_unit(geoid: str) -> str:
    """Map a county FIPS to its constant-territory analysis unit."""
    geoid = RENAMES.get(geoid, geoid)
    return _MEMBER_TO_GROUP.get(geoid, geoid)


def apply_crosswalk(df: pd.DataFrame) -> pd.DataFrame:
    """Regroup a tidy county table onto constant analysis units.

    Input columns: year, geoid, name, sex, age_bin, count.
    Output columns: year, unit, name, sex, age_bin, count.
    """
    out = df.copy()
    out["unit"] = out["geoid"].map(canonical_unit)
    merged = out["unit"].str.startswith("MG-")
    out.loc[merged, "name"] = out.loc[merged, "unit"]
    aggs = {"count": ("count", "sum"), "name": ("name", "first")}
    if "gq_count" in out.columns:
        aggs["gq_count"] = ("gq_count", "sum")
    return (
        out.groupby(["year", "unit", "sex", "age_bin"], as_index=False)
        .agg(**aggs)
    )
