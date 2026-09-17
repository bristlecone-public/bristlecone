import struct

import pytest

from cohort_trace.bins import BINS_1990, STD_BINS, std_bin
from cohort_trace.fetch import var_map
from cohort_trace.fetch1990 import (
    N_AGE, N_RACES, P12_VARS, _accumulate, _cells, _read_dbf,
)


def make_dbf(fields: list[tuple[str, int]], rows: list[list[str]]) -> bytes:
    """Build a minimal dBase III file: char fields, given rows."""
    header_size = 32 + 32 * len(fields) + 1
    record_size = 1 + sum(w for _, w in fields)
    out = bytearray(32)
    out[0] = 0x03
    struct.pack_into("<IHH", out, 4, len(rows), header_size, record_size)
    for name, width in fields:
        desc = bytearray(32)
        desc[0:len(name)] = name.encode()
        desc[11] = ord("C")
        desc[16] = width
        out += desc
    out += b"\x0d"
    for row in rows:
        out += b" "  # not deleted
        for (name, width), val in zip(fields, row):
            out += val.ljust(width).encode()
    return bytes(out)


def test_read_dbf_picks_ids_and_prefix_fields():
    fields = [("SUMLEV", 3), ("STATEFP", 2), ("CNTY", 3),
              ("P0110001", 9), ("P0120001", 9)]
    rows = [["050", "01", "001", "      77", "     1234"],
            ["040", "01", "", "       0", "     9999"]]
    recs = _read_dbf(make_dbf(fields, rows), {"SUMLEV", "STATEFP", "CNTY"},
                     prefix="P012")
    assert recs == [
        {"SUMLEV": "050", "STATEFP": "01", "CNTY": "001", "P0120001": "1234"},
        {"SUMLEV": "040", "STATEFP": "01", "CNTY": "", "P0120001": "9999"},
    ]


def test_read_dbf_missing_id_field_raises():
    with pytest.raises(RuntimeError, match="missing id fields"):
        _read_dbf(make_dbf([("SUMLEV", 3)], []), {"SUMLEV", "CNTY"}, "P012")


def test_accumulate_and_cells_collapse_races():
    # All 310 variables set to 1 across two "segments" -> every one of the
    # 62 sex-by-age cells sums the 5 races to 5.
    acc = {}
    half = P12_VARS // 2
    rec_a = {"SUMLEV": "050", "STATEFP": "01", "CNTY": "001"}
    rec_a.update({f"P012{n:04d}": "1" for n in range(1, half + 1)})
    rec_b = {"SUMLEV": "050", "STATEFP": "01", "CNTY": "001"}
    rec_b.update({f"P012{n:04d}": "1" for n in range(half + 1, P12_VARS + 1)})
    state_row = dict(rec_a, SUMLEV="040")
    _accumulate([rec_a, state_row], acc)
    _accumulate([rec_b], acc)
    assert list(acc) == [("01", "001")]
    cells = _cells(acc[("01", "001")])
    assert cells == [N_RACES] * (2 * N_AGE)


def test_cells_requires_complete_p12():
    with pytest.raises(RuntimeError, match="expected 310"):
        _cells({"P0120001": 1})


def test_1990_var_map_categories_reach_standard_bins():
    vm = var_map(1990)
    assert len(vm) == 62
    assert vm["M01"] == ("M", "<1")
    assert vm["F31"] == ("F", "85+")
    # every 1990 category lands in a standard 5-year bin
    assert {std_bin(cat) for cat in BINS_1990} <= set(STD_BINS)
    assert std_bin("<1") == "0-4"
    assert std_bin("14") == "10-14"
    assert std_bin("65-69") == "65-69"
