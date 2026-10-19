import csv
import hashlib
import io
import json
import os
from pathlib import Path

import pytest

from etl.cbs_historical_fixture import EXPECTED, MONTHS, SOURCES, convert, parse_export, serialize


def source(*, bom=False, mutate=None):
    out = io.StringIO(newline="")
    writer = csv.writer(out, delimiter=";", lineterminator="\n")
    writer.writerow(["Perioden", "Gemiddelde verkoopprijs (euro)", "Extra"])
    names = list(MONTHS)
    for n, month in enumerate(EXPECTED):
        row = [f"{month[:4]} {names[int(month[5:])-1]}", str(90000 + n), "x"]
        if mutate:
            row = mutate(n, row)
        if row is not None:
            writer.writerow(row)
    return ("\ufeff" if bom else "").encode() + out.getvalue().encode()


def checked(raw):
    return parse_export(raw, expected_sha256=hashlib.sha256(raw).hexdigest())


def test_valid_60_months_and_boundaries():
    result = checked(source())
    assert len(result) == 60
    assert list(sorted(result)) == list(EXPECTED)
    assert result["1995-01"] == 90000 and result["1999-12"] == 90059


def test_bom():
    assert checked(source(bom=True))["1995-01"] == 90000


def test_unsorted_source_produces_sorted_deterministic_output():
    original = source().decode().splitlines()
    scrambled = ("\n".join([original[0], *reversed(original[1:])]) + "\n").encode()
    hashes = {"85773NED": hashlib.sha256(scrambled).hexdigest(), "83906NED": hashlib.sha256(source()).hexdigest()}
    rows = convert(scrambled, source(), hashes=hashes)
    assert [r["date"] for r in rows] == list(EXPECTED)
    assert serialize(rows) == serialize(convert(scrambled, source(), hashes=hashes))
    assert json.loads(serialize(rows))["data"][0]["series"] == "nl_house_avg_eur"


@pytest.mark.parametrize("mutation,error", [
    (lambda n, r: None if n == 3 else r, "coverage"),
    (lambda n, r: ["1995 januari", *r[1:]] if n == 1 else r, "Duplicate"),
    (lambda n, r: ["1995 onbestaand", *r[1:]] if n == 1 else r, "month"),
    (lambda n, r: [r[0], "0", r[2]] if n == 1 else r, "price"),
    (lambda n, r: [r[0], "-10", r[2]] if n == 1 else r, "price"),
    (lambda n, r: [r[0], "unknown", r[2]] if n == 1 else r, "price"),
    (lambda n, r: [r[0], r[1], r[2], "extra"] if n == 1 else r, "row width"),
])
def test_invalid_data(mutation, error):
    with pytest.raises(ValueError, match=error):
        checked(source(mutate=mutation))


def test_missing_price_column():
    with pytest.raises(ValueError, match="header"):
        checked(source().replace(b"Gemiddelde verkoopprijs (euro)", b"Other column"))


def test_bad_sha():
    with pytest.raises(ValueError, match="SHA-256"):
        parse_export(source(), expected_sha256="0" * 64)


def test_comparison_mismatch():
    a = source()
    b = source(mutate=lambda n, r: [r[0], "100001", r[2]] if n == 2 else r)
    hashes = {"85773NED": hashlib.sha256(a).hexdigest(), "83906NED": hashlib.sha256(b).hexdigest()}
    with pytest.raises(ValueError, match="source price mismatch"):
        convert(a, b, hashes=hashes)


def test_actual_cbs01_sources_if_present():
    base = Path(os.environ.get("CBS01_PRIVATE_SOURCE_DIR", "/nonexistent"))
    a, b = [base / SOURCES[k][0] for k in ("85773NED", "83906NED")]
    if not a.exists() or not b.exists():
        pytest.skip("Original private files are not required for CI")
    rows = convert(a.read_bytes(), b.read_bytes())
    assert len(rows) == 60
    assert rows[0]["value"] == 88991
    assert rows[-1]["value"] == 155389
