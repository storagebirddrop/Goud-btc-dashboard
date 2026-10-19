"""Offline fail-closed CBS update regression tests (no live network required)."""
import csv
import io
import json
from pathlib import Path

import pytest

from etl.cbs_historical_update import generate, SourceRevision, IntegrityError
import hashlib
sha = lambda raw: hashlib.sha256(raw).hexdigest()
HEADER = b"date,series,value\r\n"
from etl.cbs_historical_fixture import EXPECTED, SOURCES, VERSION
from etl.cbs_historical_merge import FIXTURE_SHA256
from etl.static_export import build


def synthetic(tmp_path):
    # A real I1 fixture is independently checked by the pinned hash in production.
    prices = [100000 + i for i in range(60)]
    rows = [{"date": month, "series": "nl_house_avg_eur", "value": price}
            for month, price in zip(EXPECTED, prices)]
    fixture = (json.dumps({"data": rows}, separators=(",", ":")) + "\n").encode()
    provenance = {
        "converter_version": VERSION, "observations": 60,
        "period_start": "1995-01", "period_end": "1999-12",
        "output_sha256": sha(fixture),
        "sources": [{"table_id": k, "filename": SOURCES[k][0], "sha256": SOURCES[k][1],
                     "period_column": "Perioden", "price_column": "Gemiddelde verkoopprijs (euro)"}
                    for k in ("85773NED", "83906NED")],
    }
    baseline_csv = HEADER + (
        b"2000-01,nl_house_avg_eur,157270.0\r\n2000-01,nl_hpi,80.0\r\n"
        b"2000-02,nl_house_avg_eur,158000.0\r\n2000-02,nl_hpi,88.0\r\n"
    )
    source = tmp_path / "baseline.csv"
    source.write_bytes(baseline_csv)
    baseline_json = (json.dumps(build(source), separators=(",", ":")) + "\n").encode()
    return fixture, (json.dumps(provenance) + "\n").encode(), baseline_csv, baseline_json


def run(tmp_path, *, extra=b"", change=None):
    parts = synthetic(tmp_path)
    live = parts[2]
    if change:
        live = live.replace(*change)
    return generate(*parts, live + extra, baseline_csv_hash=sha(parts[2]), baseline_json_hash=sha(parts[3]), fixture_hash=sha(parts[0]))


def test_historical_retention_and_determinism(tmp_path, monkeypatch):
    fixture, provenance, baseline_csv, baseline_json = synthetic(tmp_path)
    import etl.cbs_historical_update as module
    monkeypatch.setattr(module, "FIXTURE_SHA256", sha(fixture))
    first = generate(fixture, provenance, baseline_csv, baseline_json, baseline_csv, baseline_csv_hash=sha(baseline_csv), baseline_json_hash=sha(baseline_json), fixture_hash=sha(fixture))
    assert first == generate(fixture, provenance, baseline_csv, baseline_json, baseline_csv, baseline_csv_hash=sha(baseline_csv), baseline_json_hash=sha(baseline_json), fixture_hash=sha(fixture))
    c, j, m = first
    rows = json.loads(j)["data"]
    assert len(rows) == 62
    assert [r["period"] for r in rows[:60]] == list(EXPECTED)
    assert rows[60:] == json.loads(baseline_json)["data"]
    assert rows[60]["hpi_index"] == 100
    assert c.endswith(baseline_csv[len(HEADER):])
    assert all(r["hpi"] is None and r["hpi_index"] is None and
               r["gold_index"] is None for r in rows[:60])
    manifest = json.loads(m)
    assert manifest["publication_authorized"] is False
    assert manifest["candidate_csv_sha256"] == sha(c)
    assert manifest["candidate_json_sha256"] == sha(j)


def test_new_month_is_appended_without_revising_existing(tmp_path, monkeypatch):
    parts = synthetic(tmp_path)
    import etl.cbs_historical_update as module
    monkeypatch.setattr(module, "FIXTURE_SHA256", sha(parts[0]))
    live = parts[2] + b"2000-03,nl_house_avg_eur,159000.0\r\n2000-03,nl_hpi,90.0\r\n"
    c, j, m = generate(*parts, live, baseline_csv_hash=sha(parts[2]), baseline_json_hash=sha(parts[3]), fixture_hash=sha(parts[0]))
    rows = json.loads(j)["data"]
    assert len(rows) == 63 and rows[-1]["period"] == "2000-03"
    assert rows[60:62] == json.loads(parts[3])["data"]
    assert json.loads(m)["new_months"] == 1


@pytest.mark.parametrize("change,extra,reason", [
    ((b"157270.0", b"157271.0"), b"", "CBS_REVISION_REVIEW_REQUIRED"),
    ((b"80.0", b"81.0"), b"", "CBS_REVISION_REVIEW_REQUIRED"),
    (None, b"2000-02,nl_hpi,88.0\r\n", "Duplicate"),
    (None, b"2000-04,nl_house_avg_eur,160000.0\r\n2000-04,nl_hpi,91.0\r\n", "Missing"),
    (None, b"2000-03,nl_house_avg_eur,0\r\n2000-03,nl_hpi,90.0\r\n", "Invalid"),
])
def test_fail_closed_live_inputs(tmp_path, monkeypatch, change, extra, reason):
    parts = synthetic(tmp_path)
    import etl.cbs_historical_update as module
    monkeypatch.setattr(module, "FIXTURE_SHA256", sha(parts[0]))
    live = parts[2].replace(*change) if change else parts[2]
    with pytest.raises(ValueError, match=reason):
        generate(*parts, live + extra, baseline_csv_hash=sha(parts[2]), baseline_json_hash=sha(parts[3]), fixture_hash=sha(parts[0]))


def test_missing_or_modified_fixture_rejected(tmp_path):
    parts = synthetic(tmp_path)
    with pytest.raises(ValueError, match="fixture SHA"):
        generate(parts[0] + b"tampered", parts[1], parts[2], parts[3], parts[2], baseline_csv_hash=sha(parts[2]), baseline_json_hash=sha(parts[3]), fixture_hash=sha(parts[0]))


def test_actual_pinned_fixture_in_repository():
    fixture = Path("data/fixtures/cbs-1995-1999-i1.json").read_bytes()
    provenance = Path("data/fixtures/cbs-1995-1999-i1.provenance.json").read_bytes()
    from etl.cbs_historical_merge import verify_fixture
    assert sha(fixture) == FIXTURE_SHA256
    assert len(verify_fixture(fixture, provenance)) == 60


def test_e2e_real_fixture_against_committed_baseline():
    fixture = Path("data/fixtures/cbs-1995-1999-i1.json").read_bytes()
    provenance = Path("data/fixtures/cbs-1995-1999-i1.provenance.json").read_bytes()
    csv_raw = Path("data/cbs-housing.csv").read_bytes()
    json_raw = Path("frontend/public/data/monthly.json").read_bytes()
    c, j, manifest_raw = generate(fixture, provenance, csv_raw, json_raw, csv_raw)
    rows = json.loads(j)["data"]
    assert len(rows) == 380
    assert len(json.loads(json_raw)["data"]) == 320
    assert rows[59]["period"] == "1999-12"
    assert rows[59]["house_eur"] == 155389
    assert rows[60]["period"] == "2000-01"
    assert rows[60]["house_eur"] == 157270
    assert rows[60]["hpi_index"] == 100
    assert rows[60:] == json.loads(json_raw)["data"]
    assert c.endswith(csv_raw[len(HEADER):])
    assert all(r["hpi"] is None and r["hpi_index"] is None for r in rows[:60])
    manifest = json.loads(manifest_raw)
    assert manifest["historical_months"] == 60
    assert manifest["approved_months_unchanged"] == 320
    assert manifest["new_months"] == 0
    assert manifest["candidate_csv_sha256"] == sha(c)
    assert manifest["candidate_json_sha256"] == sha(j)
    assert (c, j, manifest_raw) == generate(fixture, provenance, csv_raw, json_raw, csv_raw)


def test_baseline_hash_mismatch(tmp_path, monkeypatch):
    parts = synthetic(tmp_path)
    import etl.cbs_historical_update as module
    monkeypatch.setattr(module, "FIXTURE_SHA256", sha(parts[0]))
    with pytest.raises(ValueError, match="Approved production baseline SHA-256 mismatch"):
        generate(*parts, parts[2], fixture_hash=sha(parts[0]))


def test_unknown_series_rejected(tmp_path, monkeypatch):
    parts = synthetic(tmp_path)
    import etl.cbs_historical_update as module
    monkeypatch.setattr(module, "FIXTURE_SHA256", sha(parts[0]))
    live = parts[2] + b"2000-02,unknown,4.0\r\n"
    with pytest.raises(ValueError, match="Invalid month/series"):
        generate(*parts, live, baseline_csv_hash=sha(parts[2]), baseline_json_hash=sha(parts[3]), fixture_hash=sha(parts[0]))


def test_revision_report_deterministic(tmp_path, monkeypatch):
    parts = synthetic(tmp_path)
    import etl.cbs_historical_update as module
    monkeypatch.setattr(module, "FIXTURE_SHA256", sha(parts[0]))
    live = parts[2].replace(b"157270.0", b"157271.0")
    reports = []
    for _ in range(2):
        with pytest.raises(module.SourceRevision) as exc:
            generate(*parts, live, baseline_csv_hash=sha(parts[2]), baseline_json_hash=sha(parts[3]), fixture_hash=sha(parts[0]))
        reports.append(json.dumps(exc.value.report, sort_keys=True))
    assert reports[0] == reports[1]
    assert json.loads(reports[0])["revisions"][0]["period"] == "2000-01"
