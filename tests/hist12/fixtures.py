"""HIST-12: write the SYNTHETIC fixture set for the browser acceptance (private output directory; never inside the repository or any public asset directory)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from etl import hist_model as hm
from etl import hist_publication as hp
from tests.hist12 import synthetic as sy


def _bless(doc):
    series = [hm.series_from_dict(s) for s in doc["series"]]
    doc["release"]["release_sha256"] = hm.release_hash(series)
    return doc


def build(out_dir) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    payload, _, _ = sy.make_world(comparison=True)
    base = json.loads(hm.canonical_json(payload))
    fx = {"valid": hm.canonical_json(base)}
    fx["valid_nocmp"] = hp.serialize(sy.make_world(comparison=False)[0])
    # pinned in the TEST build, but structurally invalid: the structural gate (not only the hash pin) must refuse each of them
    def variant(mutate, bless=True):
        d = copy.deepcopy(base)
        mutate(d)
        return hm.canonical_json(_bless(d) if bless else d)
    fx["pinned_extra_series"] = variant(lambda d: d["series"].append({**copy.deepcopy(d["series"][0]), "series_id": "hist_gold_grams_h"}), bless=False)
    fx["pinned_missing_period"] = variant(lambda d: d["series"][0]["points"].pop(9))
    fx["pinned_extra_period"] = variant(lambda d: d["series"][0]["points"].append({"period": "2001-H1", "value": "9", "quality": "CONFIRMED", "flags": ["SYNTHETIC_TEST_ONLY"]}))
    fx["pinned_no_provenance"] = variant(lambda d: d.update(provenance={"method_ids": [], "sources": []}))
    fx["pinned_wrong_unit"] = variant(lambda d: d["series"][0].update(unit="USD"))
    fx["pinned_median_as_mean"] = variant(lambda d: next(s for s in d["series"] if s["series_id"] == "hist_cbs_avg_eur_m").update(kind="median_price"))
    fx["pinned_bad_scope"] = variant(lambda d: d["comparison"].update(last="1999-H2"), bless=False)
    fx["pinned_no_quality"] = variant(lambda d: d["series"][2]["points"][3].pop("quality"), bless=False)
    fx["pinned_no_marker"] = json.dumps(base).replace("SYNTHETIC_TEST_ONLY", "NOT_MARKED").replace("synthetic_test_only", "not_marked").encode()
    fx["pinned_eur_mismatch"] = variant(lambda d: next(s for s in d["series"] if s["series_id"] == "hist_nvm_median_eur_retro_h")["points"][5].update(value="1234"))
    fx["pinned_wrong_frequency"] = variant(lambda d: d["series"][0].update(frequency="monthly"), bless=False)
    fx["pinned_unresolved_quality"] = variant(lambda d: d["series"][3]["points"][2].update(quality="UNRESOLVED"), bless=False)
    fx["pinned_unauthorized_release"] = variant(lambda d: d["release"].update(publication_authorized=False), bless=False)
    # NOT pinned: valid in every respect, but not the approved bytes
    fx["unpinned_tampered"] = fx["valid"].replace(b"5555", b"5556", 1)
    fx["unpinned_other_release"] = hm.canonical_json(_bless(json.loads(hm.canonical_json({**base, "release": {**base["release"], "id": "SYN-OTHER-RELEASE"}}))))
    fx["malformed"] = b"{this is not json"
    fx["schema2"] = variant(lambda d: d.update(schema="hist-publication/2"), bless=False)
    shas = {}
    for name, blob in fx.items():
        (out / f"{name}.json").write_bytes(blob)
        shas[name] = hp.payload_sha256(blob)
    pinned = sorted({shas[n] for n in fx if n in ("valid", "valid_nocmp") or n.startswith("pinned_") or n == "schema2" or n == "malformed"})
    return {"shas": shas, "pinned": pinned, "valid": shas["valid"]}
