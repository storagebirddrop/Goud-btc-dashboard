"""HIST-13: PRIVATE historical release candidate (`hist-publication/1`, approved HD2 scope) from the pinned HIST-09/HIST-10 inputs.

Builds the nominal NVM (1975-H1..2000-H2, 52 half-years, NLG original + retrospective euro), the CBS monthly average (1995-01..1999-12, 60 months, retrospective euro) and
the CBS half-year mean (1995-H1..2000-H2, 12) for the separate comparison panel. No live or revised data is used: the inputs are the hash-pinned HIST-09 package. Nothing
here publishes, pins, registers or deploys; the output directory must lie OUTSIDE the repository and holds real historical values (private).

Documents written (private): historical.candidate.json (release block PENDING and unauthorized: it can never pass the gate), historical.provenance.json,
historical.manifest.json, historical.release-record.template.json (price-free), historical.validation-report.json (price-free). In-memory only (never persisted unless
`--write-preflight`, private directory): preflight payloads with a temporary non-owner authorization, used to prove the contract and the private browser run.

Usage: python -m tools.hist_13_candidate --inputs data/fixtures/hist09 --out-dir NEW_PRIVATE_DIR [--production-csv PATH] [--write-preflight]
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
import subprocess
import sys
import zipfile
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl import hist_model as hm  # noqa: E402
from tools import hist_09_bundle as hb9  # noqa: E402
from tools import hist_publication as hp  # noqa: E402

PROPOSED_RELEASE_ID = "HIST-REL-2026-10-001"  # PROPOSED, not owner-approved
PENDING = "PENDING"
NVM_SRC, CBS_SRC = "otb_2001_table_b3_8_csv", "cbs_85773ned_export_zip"
KEEP_FLAGS = hp.FLAGS  # only the documented contract flags travel; internal source/review flags stay in the provenance
METHODS = ["HIST09_BUNDLE_V1", "HIST12_CONTRACT_V1", "HIST10_HALF_YEAR_WEIGHTED_MEAN_V1"]
PREFLIGHT = {"authorizer": "HIST13-PREFLIGHT-NOT-AN-OWNER", "authorized_on": "1970-01-01", "decision_ref": "HIST13-PREFLIGHT-NOT-A-DECISION"}


class CandidateError(Exception):
    pass


def _flags(point_flags, required=()):
    kept = tuple(sorted(set(point_flags) & KEEP_FLAGS))
    if not set(required) <= set(kept):
        raise CandidateError(f"required flag missing: {sorted(set(required) - set(kept))}")
    return kept


def _series(sid, points, inputs, transform):
    spec = hp.APPROVED_SERIES[sid]
    return hm.Series(series_id=sid, layer=spec["layer"], asset_class="housing", frequency=spec["frequency"], currency=spec["currency"], unit=spec["unit"],
                     definition_id=spec["definition_id"], kind=spec["kind"], points=tuple(points), inputs=tuple(inputs), transforms=(transform,))


def build_series(inputs):
    """The four approved contract series from the verified HIST-09 model series. Raises on any integrity defect."""
    allseries, _ = hb9.build_all(inputs)
    nvm_src = allseries["nvm_median_nlg_halfyear"]
    nlg_points = [hm.Point(o.period, o.value, o.quality, _flags(o.flags)) for o in nvm_src.observations]
    s_nlg = _series("hist_nvm_median_nlg_h", nlg_points, [(NVM_SRC, hb9.NVM_CSV_SHA256)],
                    {"op": "transcription", "note": "nominal median, existing homes, NLG; half-year; values as in the pinned HIST-09 csv"})
    eur = allseries["nvm_median_eur_halfyear"]
    eur_points = [hm.Point(p.period, p.value, p.quality, _flags(p.flags, ("RETROSPECTIVE_EUR",))) for p in eur.points]
    s_eur = _series("hist_nvm_median_eur_retro_h", eur_points, [("hist_nvm_median_nlg_h", hm.series_sha256(s_nlg))],
                    {"op": "redenominate", "formula": "eur = nlg / 2.20371", "constant": "2.20371", "applied": 1})
    cbs = allseries["cbs_avg_price_1995_2000"]
    m_points = [hm.Point(o.period, o.value, o.quality, _flags(o.flags, ("RETROSPECTIVE_EUR",))) for o in cbs.observations if o.period <= "1999-12"]
    s_m = _series("hist_cbs_avg_eur_m", m_points, [(CBS_SRC, hb9.CBS_ZIP_SHA256)],
                  {"op": "select", "note": "monthly average, 1995-01..1999-12, as published (retrospective euro); 2000 months stay in the current dataset"})
    half = allseries["cbs_avg_price_eur_halfyear"]
    h_points = [hm.Point(p.period, p.value, p.quality, _flags(p.flags, ("RETROSPECTIVE_EUR",)) + ("HALF_YEAR_WEIGHTED",)) for p in half.points]
    s_h = _series("hist_cbs_avg_eur_h", h_points, [(CBS_SRC, hb9.CBS_ZIP_SHA256)],
                  {"op": "weighted_half_year_mean", "weights": "registered sales per month", "rule": "all six months present, otherwise null", "note": "mean, not median"})
    series = [s_nlg, s_eur, s_m, s_h]
    for s in series:
        hm.validate_series(s)
    return series


def provenance():
    return {"method_ids": list(METHODS), "sources": [
        {"id": NVM_SRC, "title": "OTB 2001 Table B3.8 (NVM median, half-year; HIST-09 csv)", "rights_status": "UNVERIFIED", "sha256": hb9.NVM_CSV_SHA256,
         "vintage": f"csv:{hb9.NVM_CSV_SHA256[:12]}", "acquired_at": hb9.NVM_RETRIEVED},
        {"id": CBS_SRC, "title": "CBS StatLine 85773NED export (owner supplied)", "rights_status": "CC BY 4.0 catalogue licence (read in the export)",
         "sha256": hb9.CBS_ZIP_SHA256, "vintage": f"zip:{hb9.CBS_ZIP_SHA256[:12]}", "acquired_at": hb9.CBS_EXPORTED}]}


def comparison_block(authorized=False):
    return {"authorized": authorized, "series": list(hp.COMPARISON_SERIES), "first": "1995-H1", "last": "2000-H2", "warning": hp.COMPARISON_WARNING}


def release_block(series, authorized=False, comparison=False, release_id=PROPOSED_RELEASE_ID, fields=None):
    f = fields or {"authorizer": PENDING, "authorized_on": PENDING, "decision_ref": PENDING}
    return {"id": release_id, "release_sha256": hm.release_hash(series), "series_ids": sorted(s.series_id for s in series), "publication_authorized": authorized,
            "comparison_authorized": comparison, **f}


def candidate_payload(series):
    return hp.build_payload(series, release_block(series), provenance(), comparison_block(False))


def preflight_payload(series, comparison):
    """The candidate with a TEMPORARY non-owner authorization, for in-memory verification and the private browser run only. Never an approved release."""
    return hp.build_payload(series, release_block(series, True, comparison, fields=PREFLIGHT), provenance(), comparison_block(comparison))


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def independent_check(inputs, doc, production_csv=None) -> dict:
    """Recalculate the candidate from the RAW pinned inputs (csv/zip/Fraction), without hist_model, hist_09_bundle or hist_publication."""
    d = Path(inputs)
    by = {s["series_id"]: {p["period"]: Fraction(Decimal(p["value"])) for p in s["points"]} for s in doc["series"]}
    out = {"nvm_nlg_equal": False, "nvm_eur_equal": False, "cbs_months_equal": False, "cbs_half_equal": False, "periods_aligned": False, "mean_median_separate": False, "production_2000_equal": None}
    rows = list(csv.DictReader((d / "HIST09_NVM_1975_2000_RESEARCH.csv").open(encoding="utf-8-sig", newline="")))
    nvm = {f"{int(r['year'])}-H{int(r['halfyear'])}": Fraction(int(r["nvm_median_nlg"])) for r in rows}
    out["nvm_nlg_equal"] = len(nvm) == 52 and nvm == by["hist_nvm_median_nlg_h"]
    rate = Fraction("2.20371")
    out["nvm_eur_equal"] = all(abs(by["hist_nvm_median_eur_retro_h"][p] - nvm[p] / rate) <= Fraction(1, 10 ** 30) * nvm[p] / rate for p in nvm) and len(by["hist_nvm_median_eur_retro_h"]) == 52
    with zipfile.ZipFile(d / hb9.CBS_ZIP_NAME) as z:
        measures = {r["Identifier"]: r["Title"] for r in csv.DictReader(io.StringIO(z.read("MeasureCodes.csv").decode("utf-8-sig")), delimiter=";")}
        obs = list(csv.DictReader(io.StringIO(z.read("Observations.csv").decode("utf-8-sig")), delimiter=";"))
    price_id = next(k for k, v in measures.items() if v == "Gemiddelde verkoopprijs")
    count_id = next(k for k, v in measures.items() if v == "Verkochte woningen")
    def val(t):
        return Fraction(t.replace(".", "").replace(",", "."))
    price, count = {}, {}
    for r in obs:
        per = r["Perioden"]
        if "MM" in per and "1995" <= per[:4] <= "2000":
            month = f"{per[:4]}-{per[6:]}"
            if r["Measure"] == price_id:
                price[month] = val(r["Value"])
            elif r["Measure"] == count_id:
                count[month] = val(r["Value"])
    months = [m for m in sorted(price) if m <= "1999-12"]
    out["cbs_months_equal"] = len(months) == 60 and {m: price[m] for m in months} == by["hist_cbs_avg_eur_m"]
    ok = len(by["hist_cbs_avg_eur_h"]) == 12
    for hy in by["hist_cbs_avg_eur_h"]:
        y, h = int(hy[:4]), int(hy[6])
        ms = [f"{y}-{m:02d}" for m in range(1 + 6 * (h - 1), 7 + 6 * (h - 1))]
        want = sum(price[m] * count[m] for m in ms) / sum(count[m] for m in ms)
        ok = ok and abs(by["hist_cbs_avg_eur_h"][hy] - want) <= Fraction(1, 10 ** 30) * want
    out["cbs_half_equal"] = ok
    out["periods_aligned"] = (list(by["hist_nvm_median_nlg_h"]) == list(by["hist_nvm_median_eur_retro_h"]) and
                              [p for p in by["hist_nvm_median_eur_retro_h"] if p >= "1995-H1"] == list(by["hist_cbs_avg_eur_h"]))
    out["mean_median_separate"] = all(next(s for s in doc["series"] if s["series_id"] == i)["kind"] == k for i, k in
                                      (("hist_nvm_median_nlg_h", "median_price"), ("hist_nvm_median_eur_retro_h", "median_price"), ("hist_cbs_avg_eur_m", "average_price"), ("hist_cbs_avg_eur_h", "average_price")))
    if production_csv is not None:
        prod = {}
        for line in Path(production_csv).read_text(encoding="utf-8").splitlines()[1:]:
            date, series, value = line.split(",")
            if series == "nl_house_avg_eur" and date.startswith("2000-"):
                prod[date] = Fraction(value)
        out["production_2000_equal"] = len(prod) == 12 and all(prod[m] == price[m] for m in prod)
    out["ok"] = all(v for k, v in out.items() if k != "production_2000_equal") and out["production_2000_equal"] in (None, True)
    return out


def _verify(blob, record, comparison_releases=(), pins=None):
    return hp.verify_payload(blob, pins=[sha(blob)] if pins is None else pins, records=[record], comparison_releases=comparison_releases, production=True)


def contract_validation(series, cand_blob) -> dict:
    """Candidate must be refused (closed); the preflight payloads must pass with an IN-MEMORY authorization; every negative case must be refused."""
    res = {}
    cand_doc = json.loads(cand_blob)
    try:
        _verify(cand_blob, hp.release_record(cand_doc["release"]))
        res["candidate_is_refused_as_unauthorized"] = False
    except (hp.HistPublicationDenied, hm.PublicationDenied, ValueError, KeyError):
        res["candidate_is_refused_as_unauthorized"] = True
    res["candidate_without_pin_or_record_refused"] = _refused(lambda: hp.verify_payload(cand_blob, pins=[], records=[]))
    on = hp.serialize(preflight_payload(series, True))
    off = hp.serialize(preflight_payload(series, False))
    rec = hp.release_record(json.loads(on)["release"])
    res["preflight_comparison_off_passes"] = _passes(lambda: _verify(off, hp.release_record(json.loads(off)["release"])))
    res["preflight_comparison_on_passes_only_with_external_hp3"] = _passes(lambda: _verify(on, rec, (rec.release_id,))) and _refused(lambda: _verify(on, rec, ()))
    neg = {}
    doc = json.loads(on)
    res["negative_harness_control_noop_mutation_passes"] = None  # set below, after remake exists
    def remake(mutate, bless=True):
        d = copy.deepcopy(doc)
        mutate(d)
        if bless:
            try:
                ser = [hm.series_from_dict(s) for s in d["series"]]
                d["release"]["release_sha256"] = hm.release_hash(ser)
            except (hm.ModelError, KeyError, TypeError, ValueError):
                pass
        b = hm.canonical_json(d)
        return b, hp.release_record(d["release"])
    def find(d, sid):
        return next(s for s in d["series"] if s["series_id"] == sid)
    res["negative_harness_control_noop_mutation_passes"] = _passes(lambda: _verify(*remake(lambda d: None), (rec.release_id,)))  # the mutation harness itself is not what refuses
    cases = {
        "wrong_pin": lambda: _verify(on, rec, (rec.release_id,), pins=["0" * 64]),
        "one_changed_byte": lambda: _verify(on.replace(b'"CONFIRMED"', b'"CONFIRMEE"', 1), rec, (rec.release_id,), pins=[sha(on)]),
        "no_external_record": lambda: hp.verify_payload(on, pins=[sha(on)], records=[], comparison_releases=(rec.release_id,)),
        "self_authorization_default_allowlist": lambda: hp.verify_payload(on, pins=[sha(on)]),
        "wrong_release_hash_in_record": lambda: _verify(on, hm.ReleaseRecord(rec.release_id, "0" * 64, rec.authorizer, rec.authorized_on, rec.decision_ref, rec.series_ids), (rec.release_id,)),
        "extra_series": lambda: _verify(*remake(lambda d: d["series"].append({**copy.deepcopy(d["series"][0]), "series_id": "hist_gold_grams_h"}), bless=False), (rec.release_id,)),
        "missing_half_year": lambda: _verify(*remake(lambda d: find(d, "hist_nvm_median_nlg_h")["points"].pop(10)), (rec.release_id,)),
        "extra_month_2000": lambda: _verify(*remake(lambda d: find(d, "hist_cbs_avg_eur_m")["points"].append({"period": "2000-01", "value": "1", "quality": "CONFIRMED", "flags": ["RETROSPECTIVE_EUR"]})), (rec.release_id,)),
        "currency_swapped": lambda: _verify(*remake(lambda d: find(d, "hist_nvm_median_nlg_h").update(currency="EUR")), (rec.release_id,)),
        "mean_labelled_median": lambda: _verify(*remake(lambda d: find(d, "hist_cbs_avg_eur_m").update(kind="median_price")), (rec.release_id,)),
        "median_definition_on_mean": lambda: _verify(*remake(lambda d: find(d, "hist_cbs_avg_eur_h").update(definition_id="nvm_median_existing_homes_nominal")), (rec.release_id,)),
        "euro_not_guilder_over_rate": lambda: _verify(*remake(lambda d: find(d, "hist_nvm_median_eur_retro_h")["points"][3].update(value="1")), (rec.release_id,)),
        "missing_quality": lambda: _verify(*remake(lambda d: find(d, "hist_cbs_avg_eur_m")["points"][4].pop("quality")), (rec.release_id,)),
        "unresolved_quality": lambda: _verify(*remake(lambda d: find(d, "hist_cbs_avg_eur_m")["points"][4].update(quality="UNRESOLVED")), (rec.release_id,)),
        "undocumented_flag": lambda: _verify(*remake(lambda d: find(d, "hist_cbs_avg_eur_m")["points"][4]["flags"].append("MADE_UP")), (rec.release_id,)),
        "missing_provenance": lambda: _verify(*remake(lambda d: d.update(provenance={"method_ids": [], "sources": []})), (rec.release_id,)),
        "source_hash_mismatch": lambda: _verify(*remake(lambda d: d["provenance"]["sources"][0].update(sha256="12" * 32)), (rec.release_id,)),
        "synthetic_marker_in_production": lambda: _verify(*remake(lambda d: d["provenance"]["sources"][0].update(title="SYNTHETIC_TEST_ONLY")), (rec.release_id,)),
        "comparison_scope_changed": lambda: _verify(*remake(lambda d: d["comparison"].update(last="1999-H2"), bless=False), (rec.release_id,)),
        "comparison_enabled_without_hp3": lambda: _verify(on, rec, ()),
        "release_not_authorized": lambda: _verify(*remake(lambda d: d["release"].update(publication_authorized=False), bless=False), (rec.release_id,)),
    }
    for name, fn in cases.items():
        neg[name] = _refused(fn)
    res["negative_cases"] = neg
    res["negative_passed"] = sum(neg.values())
    res["negative_total"] = len(neg)
    res["ok"] = (res["negative_harness_control_noop_mutation_passes"] and res["candidate_is_refused_as_unauthorized"] and res["candidate_without_pin_or_record_refused"] and res["preflight_comparison_off_passes"]
                 and res["preflight_comparison_on_passes_only_with_external_hp3"] and res["negative_passed"] == res["negative_total"])
    return res, on, off


def _refused(fn):
    try:
        fn()
    except (hp.HistPublicationDenied, hm.PublicationDenied):
        return True
    return False


def _passes(fn):
    try:
        fn()
        return True
    except (hp.HistPublicationDenied, hm.PublicationDenied):
        return False


def build_all(inputs, production_csv=None):
    """Everything in memory: (files dict name->bytes, private extras dict, price-free report dict)."""
    series = build_series(inputs)
    cand = candidate_payload(series)
    cand_blob = hp.serialize(cand)
    doc = json.loads(cand_blob)
    validation, on, off = contract_validation(series, cand_blob)
    independent = independent_check(inputs, doc, production_csv)
    prov = provenance()
    per_series = {s.series_id: {"sha256": hm.series_sha256(s), "periods": len(s.points), "first": s.points[0].period, "last": s.points[-1].period, "frequency": s.frequency,
                                "currency": s.currency, "kind": s.kind, "definition_id": s.definition_id, "quality": sorted({p.quality for p in s.points}),
                                "flag_counts": {f: sum(1 for p in s.points if f in p.flags) for f in sorted({f for p in s.points for f in p.flags})}} for s in series}
    cand_sha = sha(cand_blob)
    manifest = {"schema": "hist13-manifest/1", "status": "PRIVATE CANDIDATE - NOT AUTHORIZED FOR PUBLICATION", "contract": hp.SCHEMA, "proposed_release_id": PROPOSED_RELEASE_ID,
                "candidate_sha256": cand_sha, "release_sha256": cand["release"]["release_sha256"], "series": per_series, "provenance_sha256": sha(hp.serialize(prov)),
                "inputs": {s["id"]: {"sha256": s["sha256"], "vintage": s["vintage"], "rights_status": s["rights_status"]} for s in prov["sources"]},
                "note": "the final payload hash exists only after the owner supplies authorizer, date and decision reference (assembled privately); it is NOT AVAILABLE here"}
    template = {"schema": "hist13-release-record/1", "owner_approval": PENDING, "approved_by": PENDING, "approved_on": PENDING, "decision_ref": PENDING, "release_id": PROPOSED_RELEASE_ID + " (PROPOSED)",
                "candidate_sha256": cand_sha, "release_sha256": cand["release"]["release_sha256"], "contract": hp.SCHEMA, "series_ids": cand["release"]["series_ids"],
                "coverage": {sid: [v["first"], v["last"], v["periods"], v["frequency"]] for sid, v in per_series.items()}, "method_ids": prov["method_ids"],
                "sources": manifest["inputs"], "quality_limitations": ["NVM: 41 values (1975-H1..1995-H1) rely on Project Control's page-135 verification (flag kept)",
                                                                       "retrospective euro is a denomination, not an observed euro price",
                                                                       "NVM median and CBS mean are different statistics; never joined"],
                "comparison_authorized": False, "comparison_note": "HP3 undecided; enabled only by an external COMPARISON_RELEASES entry", "rollback_target": "no historical payload served; HIST_APPROVED_PAYLOAD_SHA256 = []; the current public dataset is unchanged",
                "frontend_pin": PENDING, "allowlist_entry": PENDING}
    report = {"schema": "hist13-validation/1", "note": "price-free: hashes, counts, booleans", "candidate_sha256": cand_sha, "release_sha256": manifest["release_sha256"],
              "counts": {"nvm_half_years": per_series["hist_nvm_median_nlg_h"]["periods"], "cbs_months": per_series["hist_cbs_avg_eur_m"]["periods"], "comparison_half_years": per_series["hist_cbs_avg_eur_h"]["periods"]},
              "independent_recalculation": independent, "contract": {k: v for k, v in validation.items() if k != "negative_cases"}, "negative_cases": validation["negative_cases"],
              "preflight_payload_sha256": {"comparison_off": sha(off), "comparison_on": sha(on)}}
    report["ok"] = independent["ok"] and validation["ok"] and report["counts"] == {"nvm_half_years": 52, "cbs_months": 60, "comparison_half_years": 12}
    files = {"historical.candidate.json": cand_blob, "historical.provenance.json": hp.serialize({"provenance": prov, "series_sha256": {k: v["sha256"] for k, v in per_series.items()}}),
             "historical.manifest.json": json.dumps(manifest, indent=1, sort_keys=True).encode() + b"\n",
             "historical.release-record.template.json": json.dumps(template, indent=1, sort_keys=True).encode() + b"\n",
             "historical.validation-report.json": json.dumps(report, indent=1, sort_keys=True).encode() + b"\n"}
    return files, {"preflight_on": on, "preflight_off": off}, report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="HIST-13 private historical release candidate")
    ap.add_argument("--inputs", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--production-csv", help="read-only reconciliation of the 2000 months with the current dataset")
    ap.add_argument("--write-preflight", action="store_true", help="also write the two preflight payloads (private; temporary non-owner authorization)")
    a = ap.parse_args(argv)
    out = Path(a.out_dir).resolve()
    if ROOT in (out, *out.parents) or any(part in ("public", "dist") for part in out.parts):
        raise SystemExit("the output directory must be outside the repository and outside every served directory")
    if out.exists() and any(out.iterdir()):
        raise SystemExit("the output directory must be new or empty")
    files, extra, report = build_all(a.inputs, a.production_csv)
    out.mkdir(parents=True, exist_ok=True)
    for name, blob in files.items():
        with open(out / name, "xb") as fh:
            fh.write(blob)
    if a.write_preflight:
        for name, blob in extra.items():
            with open(out / f"{name}.json", "xb") as fh:
                fh.write(blob)
    hashes = {n: sha(b) for n, b in files.items()}
    print("SUMMARY hist13", json.dumps({"ok": report["ok"], "candidate_sha256": report["candidate_sha256"], "release_sha256": report["release_sha256"], "files": hashes}, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
