"""Age bin definitions for decennial sex-by-age tables.

The API censuses (2000 SF1, 2010 SF1, 2020 DHC) publish the same 23 age
categories per sex; 1990 STF1 publishes 31. Both collapse to standard 5-year
bins so that a decade shifts every cohort exactly two bins.
"""

# The 23 published age categories, in the order their variables appear in P12.
API_BINS = [
    "0-4", "5-9", "10-14", "15-17", "18-19", "20", "21", "22-24",
    "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59",
    "60-61", "62-64", "65-66", "67-69", "70-74", "75-79", "80-84", "85+",
]

# The 31 age categories of 1990 STF1 P12 (race by sex by age), in variable
# order within each sex block.
BINS_1990 = [
    "<1", "1-2", "3-4", "5", "6", "7-9", "10-11", "12-13", "14",
    "15", "16", "17", "18", "19", "20", "21", "22-24",
    "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59",
    "60-61", "62-64", "65-69", "70-74", "75-79", "80-84", "85+",
]

# 1990's categories never collide with the API ones (shared labels like
# "20" or "62-64" map identically), so one lookup serves every year.
_1990_TO_STD = {
    "<1": "0-4", "1-2": "0-4", "3-4": "0-4",
    "5": "5-9", "6": "5-9", "7-9": "5-9",
    "10-11": "10-14", "12-13": "10-14", "14": "10-14",
    "15": "15-19", "16": "15-19", "17": "15-19", "18": "15-19",
    "19": "15-19",
    "20": "20-24", "21": "20-24", "22-24": "20-24",
    "60-61": "60-64", "62-64": "60-64",
}

# Standard 5-year bins after collapsing.
STD_BINS = [
    "0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
    "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74",
    "75-79", "80-84", "85+",
]

_API_TO_STD = {
    "15-17": "15-19",
    "18-19": "15-19",
    "20": "20-24",
    "21": "20-24",
    "22-24": "20-24",
    "60-61": "60-64",
    "62-64": "60-64",
    "65-66": "65-69",
    "67-69": "65-69",
}


_TO_STD = {**_API_TO_STD, **_1990_TO_STD}


def std_bin(api_bin: str) -> str:
    """Map a published age category to its standard 5-year bin."""
    return _TO_STD.get(api_bin, api_bin)


# Bins each NHGIS-sourced year can deliver, already in standard form.
# 1950 publishes 75-84 merged; 1980 is single years to 74 (-> full 5-year
# bins to 70-74) plus 75-84/85+ taken from STF1. 1960 and 1970 (single
# years to 100+) cover the full standard list.
NHGIS_YEAR_BINS = {
    1950: STD_BINS[:15] + ["75-84", "85+"],
    1960: STD_BINS,
    1970: STD_BINS,
    1980: STD_BINS[:15] + ["75-84", "85+"],
}
