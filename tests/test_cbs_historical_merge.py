"""Synthetic, offline regression suite for CBS-02-I2A candidate migration."""
import csv
import hashlib
import io
import json
from pathlib import Path

import pytest

from etl.cbs_historical_fixture import EXPECTED, SOURCES, VERSION as I1_VERSION
from etl.cbs_historical_merge import (FIELDS, GOLD, digest, make_candidate, verify_fixture,
                                      write_candidates, BASELINE_CSV_SHA256, BASELINE_JSON_SHA256,
                                      FIXTURE_SHA256)
from etl.static_export import build
from etl.data_quality import validate


def inputs():
    records = [{"date": month, "series": "nl_house_avg_eur", "value": 90000 + i} for i, month in enumerate(EXPECTED)]
    fixture = (json.dumps({"data": records}, separators=(",", ":")) + "\n").encode()
    provenance = {"converter_version": I1_VERSION, "observations": 60,
                  "period_start": EXPECTED[0], "period_end": EXPECTED[-1],
                  "output_sha256": digest(fixture),
                  "sources": [{"table_id": k, "filename": SOURCES[k][0], "sha256": SOURCES[k][1],
                               "period_column": "Perioden", "price_column": "Gemiddelde verkoopprijs (euro)"}
                              for k in ("85773NED", "83906NED")]}
    csv_raw = b"date,series,value\r\n2000-01,nl_house_avg_eur,150000.0\r\n2000-01,nl_hpi,80.0\r\n2000-02,nl_house_avg_eur,155000.0\r\n2000-02,nl_hpi,88.0\r\n"
    with __import__("tempfile").TemporaryDirectory() as d:
        p = Path(d) / "source.csv"
        p.write_bytes(csv_raw)
        json_raw = (json.dumps(build(p), separators=(",", ":")) + "\n").encode()
    return fixture, (json.dumps(provenance) + "\n").encode(), csv_raw, json_raw


def migrate(parts=None):
    a, b, c, d = parts or inputs()
    return make_candidate(a, b, c, d, fixture_hash=digest(a), csv_hash=digest(c), json_hash=digest(d))


def test_t01_t13_candidate_integrity_determinism_and_rollback(tmp_path):
    parts = inputs()
    c, j, m = migrate(parts)
    assert (c, j, m) == migrate(parts)
    rows = json.loads(j)["data"]
    assert len(rows) == 62 and len(rows[:60]) == 60
    assert [r["period"] for r in rows[:60]] == list(EXPECTED)
    assert rows[59]["period"] == "1999-12" and rows[60]["period"] == "2000-01"
    assert rows[60]["hpi_index"] == 100 and rows[61]["hpi_index"] == 110
    assert all(set(r) == FIELDS for r in rows)
    assert all(r["hpi"] is None and r["hpi_index"] is None and all(r[k] is None for k in GOLD) for r in rows[:60])
    assert all(all(r[k] is None for k in GOLD) for r in rows)
    assert rows[60:] == json.loads(parts[3])["data"]
    assert c.split(b"2000-01", 1)[1] == parts[2].split(b"2000-01", 1)[1]
    assert [r["house_eur"] for r in rows[:60]] == [90000 + i for i in range(60)]
    assert [r["period"] for r in rows] == sorted(r["period"] for r in rows)
    assert json.loads(m)["publication_authorized"] is False
    assert json.loads(m)["candidate_csv_sha256"] == digest(c)
    paths = [tmp_path / f for f in ("candidate.csv", "candidate.json", "manifest.json")]
    write_candidates(list(zip(paths, (c, j, m))))
    assert [p.read_bytes() for p in paths] == [c, j, m]
    assert validate(paths[0], paths[1]) == 62
    # Rollback: originals remain untouched, preserving exact byte hashes.
    assert digest(parts[2]) == digest(inputs()[2])
    assert digest(parts[3]) == digest(inputs()[3])


@pytest.mark.parametrize("mutation,reason", [
    (lambda a,b,c,d: (a, b"", c, d), "provenance"),
    (lambda a,b,c,d: (a.replace(b"90000", b"90001"),b,c,d), "fixture SHA"),
    (lambda a,b,c,d: (a,b,c.replace(b"150000.0",b"150001.0"),d), "baseline SHA"),
    (lambda a,b,c,d: (a,b,c.replace(b"80.0",b"81.0"),d), "baseline SHA"),
    (lambda a,b,c,d: (a,b,c,d.replace(b"100.0",b"101.0")), "baseline SHA"),
    (lambda a,b,c,d: (a,b,c.replace(b"2000-01",b"1999-12"),d), "baseline SHA"),
])
def test_negative_hash_provenance_and_existing_data(mutation, reason):
    with pytest.raises((ValueError, json.JSONDecodeError), match=reason):
        migrate(mutation(*inputs()))


def test_invalid_fixture_rows_even_if_rehashed():
    a,b,c,d = inputs()
    for mutation in ("duplicate", "missing", "zero", "negative", "string", "reorder"):
        data = json.loads(a)
        if mutation == "duplicate":
            data["data"][1]["date"] = "1995-01"
        elif mutation == "missing":
            data["data"].pop()
        elif mutation == "zero":
            data["data"][0]["value"] = 0
        elif mutation == "negative":
            data["data"][0]["value"] = -5
        elif mutation == "string":
            data["data"][0]["value"] = "90000"
        else:
            data["data"].reverse()
        altered = (json.dumps(data, separators=(",", ":")) + "\n").encode()
        provenance = json.loads(b)
        provenance["output_sha256"] = digest(altered)
        with pytest.raises(ValueError):
            verify_fixture(altered, json.dumps(provenance).encode(), expected_fixture_hash=digest(altered))


def test_rejects_second_migration():
    c,j,_ = migrate()
    a,b,_,_ = inputs()
    with pytest.raises(ValueError, match="already extended|baseline SHA"):
        make_candidate(a,b,c,j,fixture_hash=digest(a),csv_hash=digest(c),json_hash=digest(j))


def test_rejects_public_output_and_existing_candidate(tmp_path):
    from etl.cbs_historical_merge import _check_output
    root = Path(__file__).resolve().parents[1]
    with pytest.raises(ValueError, match="production/public"):
        _check_output(root / "frontend/public/data/unsafe.json")
    with pytest.raises(ValueError, match="production/public"):
        _check_output(root / "data/unsafe.csv")
    path = tmp_path / "existing"
    path.write_text("unchanged")
    with pytest.raises(ValueError, match="overwrite"):
        write_candidates([(path,b"changed")])
    assert path.read_text() == "unchanged"


def test_static_export_rejects_hpi_before_2000_and_missing_hpi_after(tmp_path):
    c,_,_ = migrate()
    p = tmp_path / "c.csv"
    p.write_bytes(c)
    assert len(build(p)["data"]) == 62
    p.write_bytes(c.replace(b"1995-01,nl_house_avg_eur,90000\r\n",
                            b"1995-01,nl_house_avg_eur,90000\r\n1995-01,nl_hpi,1\r\n"))
    with pytest.raises(ValueError, match="Missing housing series"):
        build(p)
    p.write_bytes(c.replace(b"2000-01,nl_hpi,80.0\r\n",b""))
    with pytest.raises(ValueError, match="Missing housing series"):
        build(p)


def test_pinned_production_hashes_and_i1_fixture():
    assert BASELINE_CSV_SHA256 == "ad98bba942b0bc0c43ff142c7972c3e2742f53088398edb3ccde4ff422bbd8f6"
    assert BASELINE_JSON_SHA256 == "bc15f3bd1c2101df6fd6a8e18b60f62ff2fc3032eb0b71009bb6b44704c5c78e"
    assert FIXTURE_SHA256 == "0a557dd16fe85e40952dd97edd492d5b3f985f64930d19d960b14307d725c543"
