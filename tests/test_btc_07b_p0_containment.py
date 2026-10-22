"""BTC-07B P0: CI-output containment. Content-based canary tests.

The full BTC-04E research summary carries prices (`stale_runs[].value`, `independent.*`, June 2011 diagnostics). Public CI may only upload
or print the positive allowlist in `tools/btc_public_report.py`. These tests do not look at file names: they build a summary that
contains synthetic canary values in every sensitive section, run the real tool entry points, and search the ACTUALLY uploaded files and
the ACTUALLY printed stdout for those values. Synthetic data proves code, not data.
"""
import json
import re
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from tools import btc_03_housing as b3
from tools import btc_04e_cm_replay as c
from tools import btc_06c_candidate as cand
from tools import btc_public_report as pr
from tools import hist_08_bundle as hb

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/btc-04e-cm-replay.yml"
CSV = ROOT / "data/cbs-housing.csv"
CANARY_PRICE = "31415.926535"  # repeated daily price inside a flat run (stale_runs[].value)


def days(first, last):
    d, end = date.fromisoformat(first), date.fromisoformat(last)
    while d <= end:
        yield d.isoformat()
        d += timedelta(days=1)


def price(day):
    d = date.fromisoformat(day)
    return Decimal(20) + Decimal((d.year - 2010) * 37 + d.month * 5) + Decimal(d.day * 7 % 11) / Decimal(3)


def synthetic_summary():
    """The same sections `run()` fills, computed with the real functions on synthetic daily data that contain canary prices."""
    cm = {d: price(d) for d in days("2010-07-18", "2016-06-30")}
    for d in days("2012-03-01", "2012-03-10"):
        cm[d] = Decimal(CANARY_PRICE)
    for d in days("2011-06-01", "2011-06-30"):  # June 2011 diagnostic month with its own recognisable values
        cm[d] = Decimal("27182.818284")
    ecb = {d: Decimal("1.1") + Decimal(date.fromisoformat(d).day % 7) / Decimal(50) for d in days("2010-01-01", "2016-06-30")
           if date.fromisoformat(d).weekday() < 5}
    house = hb.cbs_2000_series(CSV)
    built = c.build_from_daily(cm, ecb, house, "2026-10-22T10:00:00+00:00")
    meta = c.month_metadata(built, cm, c.corroboration_flags(cm, cm, cm))
    R = {"method_id": c.METHOD_ID, "missing_sources": [], "mode": "validate", "status": "COMPLETE_RESEARCH", "failures": [],
         "acquisition": {"source": c.PROVIDER, "pages": 2, "page_sha256": ["a" * 64, "b" * 64], "response_sha256": "c" * 64, "first": "2010-07-18",
                         "last": "2016-06-30", "n": len(cm), "provider_gaps": [], "retrieved_at_utc": "2026-10-22T10:00:00+00:00"},
         "observations_used": {"first": "2010-07-18", "last": "2016-06-30", "n": len(cm), "missing_calendar_days": 0, "missing_sample": []},
         "rebuild_identical": True, "derived_values_sha256": "d" * 64,
         "vintage_check": {"status": "MATCH", "sources": {"cm_priceusd_daily": "MATCH"}},
         "pins_candidate": {"method_id": c.METHOD_ID, "parser_version": c.PARSER_VERSION, "exception_policy_version": c.EXCEPTION_POLICY_VERSION,
                            "quality_version": c.QUALITY_VERSION, "pinned_on": "2026-10-22",
                            "sources": {"cm_priceusd_daily": {"first": "2010-07-18", "last": "2016-04-30", "n": 5, "sha256": "e" * 64}},
                            "derived": {"values_sha256": "f" * 64, "cutoff": "2026-08"}},
         "coverage": {"cm_priceusd_monthly": {"first": "2010-08", "last": "2016-05", "n": 70, "n_null": 1, "null_sample": ["2011-06"]}},
         "quality_months": {"Q3": 41, "Q2": 27, "Q1_CANDIDATE": 2},
         "chart_segments": c.chart_segments(built),
         "june_2011": meta.get("2011-06"),
         "stale_runs": c.stale_runs(cm)[:25],
         "ecb_calendar": c.ecb_calendar_report(ecb),
         "independent": c.independent_check(cm, ecb, built, house, c.INDEPENDENT_MONTHS),
         "corroboration": c.corroboration(cm, ecb, cm, cm),
         "quality_metadata_sample": {m: meta[m] for m in ("2010-08", "2011-06", "2014-02", "2016-05") if m in meta},
         "snapshot": {"snapshot_id": "btc04e-snapshot/2:" + "1" * 64, "bytes": {"cm_daily.json": 164264, "manifest.json": 2433}, "total_bytes": 166697,
                      "location": "explicit path", "durable_storage": "OPEN"},
         "replay_from_private_snapshot": {"status": "IDENTICAL", "snapshot_id": "btc04e-snapshot/2:" + "1" * 64, "derived_values_sha256": "d" * 64,
                                          "raw_source_bytes": "RETAINED_AND_VERIFIED"},
         "source_notes": [f"provider echo {CANARY_PRICE}"],
         "manifest": {"note": "x"}, "caveat": "research"}
    return R


def forbidden_tokens(R):
    """Every price-bearing string of the PRIVATE summary: the canaries plus all numeric values of the sensitive sections."""
    tokens = {CANARY_PRICE, "27182.818284", "27182", "31415"}
    for run in R["stale_runs"]:
        tokens.add(run["value"])
    for month, v in R["independent"].items():
        for key in ("btc_eur", "btc_per_house_exact", "sats_per_house_exact"):
            if key in v:
                tokens.add(v[key])
    assert any(re.search(r"\d\.\d", t) for t in tokens)
    assert len(tokens) > 8, "the canary set must really contain derived values from several sections"
    return tokens


@pytest.fixture(scope="module")
def R():
    return synthetic_summary()


def assert_clean(text, tokens):
    for t in sorted(tokens):
        assert t not in text, f"forbidden value {t!r} leaked"


def test_the_private_summary_really_contains_the_canaries(R):
    text = json.dumps(R, default=str)
    assert CANARY_PRICE in text and "27182" in text
    assert R["stale_runs"] and "value" in R["stale_runs"][0] and R["independent"]["2011-06"]["status"] == "OK"
    assert "btc_per_house_exact" in R["independent"]["2011-06"]


def test_public_projection_contains_no_canary_and_no_decimal_number(R):
    tokens = forbidden_tokens(R)
    doc = pr.public_summary(R)
    text = json.dumps(doc, sort_keys=True)
    assert_clean(text, tokens)
    assert not re.search(r"\d[\d_,]*\.\d", text)  # no decimal number anywhere
    assert "value" not in {k for run in doc["stale_runs"] for k in run} and {"first": "2012-03-01", "last": "2012-03-10", "days": 10} in doc["stale_runs"]
    assert set(doc["independent"]["2011-06"]) == {"status", "btc_agrees", "sats_agrees"}
    assert doc["independent"]["2011-06"]["btc_agrees"] is True
    assert doc["june_2011"]["release_eligibility"] == "RESEARCH_ONLY_HOLD" and "value" not in doc["june_2011"]
    assert doc["source_notes"] == 1  # only the number of notes; the text may echo provider output
    assert doc["schema"] == pr.SCHEMA


def test_allowlist_is_positive_unreviewed_content_never_appears(R):
    R2 = dict(R, brand_new_section={"price": CANARY_PRICE, "nested": [{"value": "123456.789"}]}, stale_runs=[dict(R["stale_runs"][0], extra="999.5")])
    R2["acquisition"] = dict(R["acquisition"], extra_price="888.25")
    R2["coverage"] = {"cm_priceusd_monthly": dict(R["coverage"]["cm_priceusd_monthly"], last_price="777.75")}
    text = json.dumps(pr.public_summary(R2))
    for leaked in (CANARY_PRICE, "123456.789", "999.5", "888.25", "777.75", "brand_new_section"):
        assert leaked not in text


def _mut(path, value):
    def apply(doc):
        node = doc
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
    return apply


@pytest.mark.parametrize("mutate", [
    _mut(["stale_runs"], [{"first": "2012-03-01", "value": "1"}]), _mut(["coverage", "x"], {"n": 1.5}), _mut(["status"], "12345.67"),
    _mut(["status"], "1.2e-16"), _mut(["status"], "12345678"), _mut(["status"], "a" * 400), _mut(["status"], object()),
    _mut(["independent", "2011-06", "btc_per_house_exact"], "1"), _mut(["coverage", "12345.67"], {}), _mut(["quality_months", "sat_per_house"], 1)])
def test_backstop_refuses_values_even_if_the_projection_were_wrong(R, mutate):
    doc = pr.public_summary(R)
    mutate(doc)
    with pytest.raises(pr.PublicReportError):
        pr.assert_price_free(doc)


def test_backstop_requires_the_public_schema_and_known_top_level_keys(R):
    doc = pr.public_summary(R)
    for broken in ({"schema": "other"}, {"unreviewed": 1}):
        with pytest.raises(pr.PublicReportError):
            pr.assert_price_free({**doc, **broken})
    full_private = json.loads(json.dumps(R, default=str))
    with pytest.raises(pr.PublicReportError):
        pr.assert_price_free(full_private)


def test_hashes_with_long_digit_runs_are_not_mistaken_for_prices(R):
    doc = pr.public_summary(R)
    doc["derived_values_sha256"] = "1234567890" * 6 + "abcd"  # 64 hex chars, long digit run inside a hash
    pr.assert_price_free(doc)
    doc["replay_from_private_snapshot"]["status"] = "1234567890"
    with pytest.raises(pr.PublicReportError):
        pr.assert_price_free(doc)


def test_safe_text_removes_numbers_from_exception_messages():
    msg = pr.safe_text(f"bad price {CANARY_PRICE} and 1234567 and 2.5e-3 on 2012-03-04")
    assert "31415" not in msg and "1234567" not in msg and "2.5e-3" not in msg and "2012-03-04" in msg
    assert pr.safe_text("x" * 1000, 50) == "x" * 50


def test_main_writes_private_full_and_public_allowlisted_and_prints_only_public(R, monkeypatch, tmp_path, capsys):
    tokens = forbidden_tokens(R)
    monkeypatch.setattr(c, "run", lambda args: dict(R))
    private_dir, public_dir = tmp_path / "private", tmp_path / "public"
    rc = c.main(["--cbs-csv", "x.csv", "--summary-out", str(private_dir / "summary.json"), "--public-summary-out", str(public_dir / "summary.json")])
    out = capsys.readouterr().out
    assert rc == 0
    private_text = (private_dir / "summary.json").read_text()
    assert CANARY_PRICE in private_text, "the private summary keeps the diagnostics locally"
    uploaded = sorted(public_dir.rglob("*"))
    assert [p.name for p in uploaded] == ["summary.json"]
    for p in uploaded:  # content of every file that would be uploaded
        assert_clean(p.read_text(), tokens)
    assert_clean(out, tokens)
    # the print step of the workflow, with its exact default arguments
    rc = c.main(["--print-summary", str(public_dir / "summary.json")])
    printed = capsys.readouterr().out
    assert rc == 0 and "SUMMARY stale_runs" in printed and "SUMMARY independent" in printed
    assert_clean(printed, tokens)
    assert not re.search(r"\d[\d_,]*\.\d", printed)
    # an explicit key list cannot reach private content either
    rc = c.main(["--print-summary", str(public_dir / "summary.json"), "--keys", "stale_runs,independent,june_2011,quality_metadata_sample,corroboration"])
    assert_clean(capsys.readouterr().out, tokens)


def test_a_private_summary_cannot_be_printed(R, tmp_path, capsys):
    private = tmp_path / "summary.json"
    private.write_text(json.dumps(R, default=str))
    assert c.main(["--print-summary", str(private), "--keys", "stale_runs,independent"]) == 1
    out = capsys.readouterr().out
    assert_clean(out, forbidden_tokens(R)) and "SUMMARY stale_runs" not in out


def test_if_the_projection_refuses_nothing_public_is_written_and_the_run_fails(R, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(c, "run", lambda args: dict(R))

    def bad(_R):
        raise pr.PublicReportError("public summary: float at $.x")
    monkeypatch.setattr(pr, "public_summary", bad)
    public = tmp_path / "public" / "summary.json"
    rc = c.main(["--cbs-csv", "x.csv", "--summary-out", str(tmp_path / "p.json"), "--public-summary-out", str(public)])
    assert rc == 1 and not public.exists()


def test_failure_paths_print_and_upload_no_price(monkeypatch, tmp_path, capsys):
    def boom(args):
        raise c.Btc04eError(f"price {CANARY_PRICE} rejected at 2012-03-04; raw 27182.818284")
    monkeypatch.setattr(c, "run", boom)
    public = tmp_path / "public" / "summary.json"
    rc = c.main(["--cbs-csv", "x.csv", "--summary-out", str(tmp_path / "priv" / "s.json"), "--public-summary-out", str(public)])
    out = capsys.readouterr().out
    assert rc == 1
    for text in (out, public.read_text(), (tmp_path / "priv" / "s.json").read_text()):
        assert CANARY_PRICE not in text and "27182" not in text
    assert json.loads(public.read_text())["status"] == "FAILED"


def test_replay_defect_message_is_scrubbed(monkeypatch, capsys):
    def boom(*a, **k):
        raise c.Btc04eError(f"mismatch {CANARY_PRICE}")
    monkeypatch.setattr(c, "replay", boom)
    monkeypatch.setattr(c.hb, "cbs_2000_series", lambda p: None)
    assert c.main(["--replay-snapshot", "nowhere", "--cbs-csv", str(CSV)]) == 1
    assert CANARY_PRICE not in capsys.readouterr().out


def test_candidate_cli_refuses_to_print_a_summary_with_values(monkeypatch, capsys):
    summary = {"status": "OK", "months": 3, "note": f"first value {CANARY_PRICE}"}
    monkeypatch.setattr(cand, "build_candidate", lambda *a: ({}, {}, summary))
    assert cand.main(["--snapshot", "s", "--cbs-csv", "c", "--legacy-json", "l"]) == 1
    out = capsys.readouterr().out
    assert CANARY_PRICE not in out and "SUMMARY candidate" not in out
    monkeypatch.setattr(cand, "build_candidate", lambda *a: ({}, {}, {"status": "OK", "months": 3}))
    assert cand.main(["--snapshot", "s", "--cbs-csv", "c", "--legacy-json", "l"]) == 0
    assert "SUMMARY candidate" in capsys.readouterr().out


def test_candidate_defect_message_is_scrubbed(monkeypatch, capsys):
    def boom(*a):
        raise cand.CandidateError(f"value {CANARY_PRICE}")
    monkeypatch.setattr(cand, "build_candidate", boom)
    assert cand.main(["--snapshot", "s", "--cbs-csv", "c", "--legacy-json", "l"]) == 1
    assert CANARY_PRICE not in capsys.readouterr().out


# ------------------------------------------------------------------ the workflow: what is uploaded and printed
def steps():
    text = WORKFLOW.read_text()
    parts = re.split(r"\n      - ", text.split("    steps:\n", 1)[1])
    return text, parts


def test_workflow_uploads_only_the_public_directory_and_prints_only_the_public_file():
    text, parts = steps()
    uploads = [p for p in parts if "upload-artifact" in p]
    assert len(uploads) == 1
    path = re.search(r"path:\s*(.+)", uploads[0]).group(1).strip()
    assert path.endswith("/btc-04e-public/") and path.startswith("${{ runner.temp }}") and "private" not in path
    summary_out = re.search(r'--summary-out\s+"([^"]+)"', text).group(1)
    public_out = re.search(r'--public-summary-out\s+"([^"]+)"', text).group(1)
    assert "btc-04e-private" in summary_out and "btc-04e-public" in public_out
    assert not summary_out.startswith(path.replace("${{ runner.temp }}", "$RUNNER_TEMP")) and not public_out.startswith("$RUNNER_TEMP/btc-04e-private")
    prints = [p for p in parts if "--print-summary" in p]
    assert len(prints) == 1 and re.search(r'--print-summary "\$RUNNER_TEMP/btc-04e-public/summary\.json"', prints[0])
    assert "--keys" not in prints[0] and "btc-04e-private" not in prints[0] and "stale_runs" not in text and "independent" not in text.replace("independent_check", "")
    # nothing else uploads or prints the private directories
    assert text.count("upload-artifact") == 1 and "btc-06c-private" not in uploads[0] and "btc-04e-private-snapshot" not in uploads[0]
    for p in parts:
        if "upload-artifact" not in p:
            assert not re.search(r"\b(cat|echo|tail|head|ls|tar|zip)\b[^\n]*(btc-04e-private|btc-06c-private)", p)


def test_workflow_artifact_is_named_as_price_free_and_still_fails_closed():
    text, _ = steps()
    assert "btc-04e-public-summary-not-approved" in text and "btc-04e-summary-not-approved" not in text.replace("btc-04e-public-summary-not-approved", "")
    assert "continue-on-error" not in text and "|| true" not in text and "default: validate" in text
    assert "price-free" in text and "aggregates only; no raw price data" not in text  # the old claim is replaced by the enforced one


def test_workflow_triggers_cover_the_new_module_and_its_tests():
    text = WORKFLOW.read_text()
    assert "tools/btc_public_report.py" in text or "tools/btc_*.py" in text or "tools/btc_04e_*.py" in text
    assert "tests/test_btc_07b_*.py" in text and "tests/test_btc_07b_p0_containment.py" in text
