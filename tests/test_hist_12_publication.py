"""HIST-12: the `hist-publication/1` contract (SYNTHETIC fixtures; proves code, not data). Every way the historical payload could widen, forge authority or
confuse statistics must fail closed. The release allowlist, the comparison allowlist and the production defaults stay empty."""
import copy
import json
import re
from pathlib import Path

import pytest

from etl import hist_model as hm
from tools import hist_publication as hp
from tests.hist12 import synthetic as sy

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def world():
    blob, record, cmp_ok = sy.make_blob()
    return {"blob": blob, "record": record, "cmp": cmp_ok, "doc": json.loads(blob)}


def ok(blob, record, cmp_ok=(), **over):
    return sy.verify(blob, record, cmp_ok, **over)


def denied(blob, record, cmp_ok=(), **over):
    with pytest.raises(hp.HistPublicationDenied):
        sy.verify(blob, record, cmp_ok, **over)


def remade(doc, bless=True, record_over=None, comparison=("SYN-HIST-REL-1",)):
    """Re-serialize a mutated document canonically and (optionally) re-bless the content hash, so that ONE specific rule is what must refuse it."""
    doc = copy.deepcopy(doc)
    if bless:
        try:
            series = [hm.series_from_dict(s) for s in doc["series"]]
            doc["release"]["release_sha256"] = hm.release_hash(series)
            doc["release"]["series_ids"] = sorted(s.series_id for s in series)
        except (hm.ModelError, KeyError, TypeError):
            pass
    record = hp.release_record(doc["release"]) if not record_over else record_over
    return hm.canonical_json(doc), record, comparison


# ---------------------------------------------------------------- the valid payload
def test_valid_synthetic_payload_is_accepted_and_serialization_is_deterministic(world):
    again, _, _ = sy.make_blob()
    assert again == world["blob"] and hp.payload_sha256(again) == hp.payload_sha256(world["blob"])
    doc = ok(world["blob"], world["record"], world["cmp"])
    assert doc["schema"] == hp.SCHEMA and set(s["series_id"] for s in doc["series"]) == set(hp.APPROVED_SERIES)


def test_the_approved_scope_is_exactly_the_hd2_series():
    assert {k: (v["frequency"], v["currency"], v["first"], v["last"], v["count"]) for k, v in hp.APPROVED_SERIES.items()} == {
        "hist_nvm_median_nlg_h": ("semiannual", "NLG", "1975-H1", "2000-H2", 52),
        "hist_nvm_median_eur_retro_h": ("semiannual", "EUR", "1975-H1", "2000-H2", 52),
        "hist_cbs_avg_eur_m": ("monthly", "EUR", "1995-01", "1999-12", 60),
        "hist_cbs_avg_eur_h": ("semiannual", "EUR", "1995-H1", "2000-H2", 12)}
    assert not any(re.search(r"gold|gram|index|cpi|btc|bitcoin|fuel|equity", k) for k in hp.APPROVED_SERIES)


# ---------------------------------------------------------------- authority: pin, record, defaults
def test_wrong_or_missing_pin_and_one_changed_byte_are_refused(world):
    denied(world["blob"], world["record"], world["cmp"], pins=[])
    denied(world["blob"], world["record"], world["cmp"], pins=["0" * 64])
    changed = world["blob"].replace(b"5555", b"5556", 1)
    assert changed != world["blob"]
    denied(changed, world["record"], world["cmp"], pins=[hp.payload_sha256(world["blob"])])  # hash differs by one byte


def test_production_defaults_authorize_nothing(world):
    assert hm.ALLOWLIST == () and hp.COMPARISON_RELEASES == ()
    with pytest.raises(hp.HistPublicationDenied):
        hp.verify_payload(world["blob"], pins=[hp.payload_sha256(world["blob"])])  # production mode, default (empty) allowlist
    denied(world["blob"], world["record"], world["cmp"], records=())  # no external record: the payload cannot authorize itself


def test_a_record_that_differs_from_the_claim_is_refused(world):
    rec = world["record"]
    for bad in (hm.ReleaseRecord(rec.release_id, "0" * 64, rec.authorizer, rec.authorized_on, rec.decision_ref, rec.series_ids),
                hm.ReleaseRecord("OTHER", rec.release_sha256, rec.authorizer, rec.authorized_on, rec.decision_ref, rec.series_ids),
                hm.ReleaseRecord(rec.release_id, rec.release_sha256, rec.authorizer, rec.authorized_on, rec.decision_ref, rec.series_ids[:-1])):
        denied(world["blob"], bad, world["cmp"])


def test_malformed_or_unapproved_release_blocks_are_refused(world):
    for mutate in (lambda d: d["release"].update(release_sha256="xyz"), lambda d: d["release"].update(authorizer=""), lambda d: d["release"].update(authorized_on="yesterday"),
                   lambda d: d["release"].update(publication_authorized=False), lambda d: d["release"].update(extra=1), lambda d: d["release"].pop("decision_ref"),
                   lambda d: d["release"].update(series_ids=d["release"]["series_ids"][:-1])):
        doc = copy.deepcopy(world["doc"])
        mutate(doc)
        blob, rec, cmp_ok = remade(doc, bless=False, record_over=world["record"])
        denied(blob, rec, cmp_ok)


def test_content_changed_but_hash_blessed_is_still_refused_by_the_external_record(world):
    doc = copy.deepcopy(world["doc"])
    doc["series"][0]["points"][3]["value"] = "9999"
    blob, rec, cmp_ok = remade(doc, bless=True)
    denied(blob, world["record"], cmp_ok, pins=[hp.payload_sha256(blob)])  # the external record still names the original content hash
    ok(blob, rec, cmp_ok)  # (a new, re-authorized record would be a new release decision, not a bypass)


# ---------------------------------------------------------------- scope: series, periods, frequency, currency, definitions
def test_extra_missing_or_unknown_series_are_refused(world):
    doc = copy.deepcopy(world["doc"])
    extra = copy.deepcopy(doc["series"][0])
    extra["series_id"] = "hist_gold_grams_h"
    doc["series"].append(extra)
    denied(*remade(doc))
    doc = copy.deepcopy(world["doc"])
    doc["series"] = doc["series"][:-1]
    denied(*remade(doc))
    doc = copy.deepcopy(world["doc"])
    doc["series"][0]["series_id"] = "hist_nvm_median_nlg_x"
    denied(*remade(doc))


@pytest.mark.parametrize("name,mutate", [
    ("extra_half_year", lambda s: s["points"].append({"period": "2001-H1", "value": "9", "quality": "CONFIRMED", "flags": ["SYNTHETIC_TEST_ONLY", "VISUAL_P135_PER_PROJECT_CONTROL"]})),
    ("missing_half_year", lambda s: s["points"].pop(10)),
    ("early_start", lambda s: s["points"].insert(0, {"period": "1974-H2", "value": "9", "quality": "CONFIRMED", "flags": ["SYNTHETIC_TEST_ONLY", "VISUAL_P135_PER_PROJECT_CONTROL"]})),
    ("null_value", lambda s: s["points"][5].update(value=None)),
    ("zero_value", lambda s: s["points"][5].update(value="0")),
    ("monthly_period_in_half_year_series", lambda s: s["points"][5].update(period="1977-07")),
])
def test_unauthorized_or_incomplete_periods_are_refused(world, name, mutate):
    doc = copy.deepcopy(world["doc"])
    mutate(next(s for s in doc["series"] if s["series_id"] == "hist_nvm_median_nlg_h"))
    denied(*remade(doc))


@pytest.mark.parametrize("name,field,value", [
    ("nvm_in_eur_without_conversion", "currency", "EUR"), ("nvm_as_monthly", "frequency", "monthly"), ("wrong_unit", "unit", "USD"),
    ("nvm_as_mean", "kind", "average_price"), ("other_definition", "definition_id", "cbs_average_price_existing_homes"), ("wrong_layer", "layer", "derived"),
    ("real_basis", "basis", "real"), ("index_currency", "currency", "INDEX")])
def test_invalid_currency_frequency_kind_definition_or_basis_is_refused(world, name, field, value):
    doc = copy.deepcopy(world["doc"])
    next(s for s in doc["series"] if s["series_id"] == "hist_nvm_median_nlg_h")[field] = value
    denied(*remade(doc))


def test_median_and_mean_cannot_be_confused(world):
    doc = copy.deepcopy(world["doc"])
    next(s for s in doc["series"] if s["series_id"] == "hist_cbs_avg_eur_m")["kind"] = "median_price"
    denied(*remade(doc))
    doc = copy.deepcopy(world["doc"])  # a mean series wearing the median definition id
    next(s for s in doc["series"] if s["series_id"] == "hist_cbs_avg_eur_h")["definition_id"] = "nvm_median_existing_homes_nominal"
    denied(*remade(doc))


def test_the_retrospective_euro_is_exactly_the_guilder_value_divided_by_2_20371(world):
    doc = copy.deepcopy(world["doc"])
    eur = next(s for s in doc["series"] if s["series_id"] == "hist_nvm_median_eur_retro_h")
    eur["points"][7]["value"] = str(float(eur["points"][7]["value"]) * 1.001)
    denied(*remade(doc))
    assert hp.NLG_PER_EUR == hm.to_decimal("2.20371")


# ---------------------------------------------------------------- quality, flags, provenance, lineage
def test_missing_or_undocumented_quality_and_flags_are_refused(world):
    for mutate in (lambda p: p.update(quality="UNRESOLVED"), lambda p: p.update(quality="INFERRED"), lambda p: p.pop("quality"), lambda p: p.update(flags=["SYNTHETIC_TEST_ONLY", "MADE_UP_FLAG"]),
                   lambda p: p.update(flags=["SYNTHETIC_TEST_ONLY"])):
        doc = copy.deepcopy(world["doc"])
        mutate(next(s for s in doc["series"] if s["series_id"] == "hist_cbs_avg_eur_m")["points"][4])
        denied(*remade(doc))


def test_missing_or_incomplete_provenance_and_unresolved_lineage_are_refused(world):
    for mutate in (lambda d: d.pop("provenance"), lambda d: d["provenance"].update(sources=[]), lambda d: d["provenance"]["sources"][0].pop("vintage"),
                   lambda d: d["provenance"]["sources"][0].update(sha256="12"), lambda d: d["provenance"].update(method_ids=[]),
                   lambda d: d["provenance"]["sources"][0].update(sha256="cd" * 32), lambda d: d["provenance"]["sources"].append(copy.deepcopy(d["provenance"]["sources"][0]))):
        doc = copy.deepcopy(world["doc"])
        mutate(doc)
        denied(*remade(doc))
    doc = copy.deepcopy(world["doc"])
    next(s for s in doc["series"] if s["series_id"] == "hist_cbs_avg_eur_h")["inputs"] = [["hist_unknown_series", "ef" * 32]]
    denied(*remade(doc))


# ---------------------------------------------------------------- comparison (HP3), synthetic marker, serialization
def test_the_comparison_needs_an_external_authorization_and_the_exact_scope(world):
    no_cmp_blob, no_cmp_rec, no_cmp = sy.make_blob(comparison=False)
    ok(no_cmp_blob, no_cmp_rec, no_cmp)  # disabled comparison is valid
    denied(world["blob"], world["record"], ())  # enabled in the payload but not authorized outside it
    denied(world["blob"], world["record"], ("OTHER-RELEASE",))
    for mutate in (lambda d: d["comparison"].update(last="1999-H2"), lambda d: d["comparison"].update(series=list(reversed(d["comparison"]["series"]))),
                   lambda d: d["comparison"].update(warning=""), lambda d: d["comparison"].update(authorized="yes"), lambda d: d["release"].update(comparison_authorized=False)):
        doc = copy.deepcopy(world["doc"])
        mutate(doc)
        blob, rec, cmp_ok = remade(doc, bless=False, record_over=world["record"])
        denied(blob, rec, cmp_ok)


def test_the_synthetic_marker_is_refused_in_production_and_required_in_test_mode(world):
    denied(world["blob"], world["record"], world["cmp"], production=True)  # production candidate carrying the marker
    doc = json.loads(world["blob"].decode().replace("SYNTHETIC_TEST_ONLY", "NOT_MARKED").replace("synthetic_test_only", "not_marked"))
    blob, rec, cmp_ok = remade(doc)
    denied(blob, rec, cmp_ok, production=False)  # test mode demands the marker


def test_non_canonical_floats_and_foreign_structures_are_refused(world):
    denied(world["blob"] + b"\n", world["record"], world["cmp"])
    pretty = json.dumps(json.loads(world["blob"]), indent=1).encode()
    denied(pretty, world["record"], world["cmp"], pins=[hp.payload_sha256(pretty)])
    doc = copy.deepcopy(world["doc"])
    doc["series"][0]["points"][0]["value"] = 7777.5  # a JSON number, not a Decimal string
    blob = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
    denied(blob, world["record"], world["cmp"], pins=[hp.payload_sha256(blob)])
    for junk in (b"", b"[]", b"null", b"{}", b'{"schema":"hist-publication/2"}'):
        denied(junk, world["record"], world["cmp"], pins=[hp.payload_sha256(junk)])
    doc = copy.deepcopy(world["doc"])
    doc["schema"] = "hist-publication/2"
    denied(*remade(doc))
    doc = copy.deepcopy(world["doc"])
    doc["extra"] = 1
    denied(*remade(doc))


# ---------------------------------------------------------------- production safeguards
def test_production_files_and_defaults_are_unchanged():
    from etl import btc_contract as bc
    assert bc.sha256((ROOT / "frontend/public/data/monthly.json").read_bytes()) == bc.LEGACY_PUBLIC_SHA256
    assert bc.ARTIFACT_RECORDS == () and hm.ALLOWLIST == () and hp.COMPARISON_RELEASES == ()
    assert "BTC_APPROVED_COMPOSITE_SHA256:readonly string[]=[];" in (ROOT / "frontend/src/btc.ts").read_text()
    assert not (ROOT / "frontend/public/data/historical.json").exists()
    assert not list((ROOT / "frontend/public").rglob("*hist*")) and not list((ROOT / "data").rglob("historical*"))
