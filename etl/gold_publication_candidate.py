"""GOLD-01 isolated, review-only two-indicator candidate builder.

Never writes raw gold prices or private source inputs to public paths.
"""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

from etl.gold_monthly import acquire, parse_ecb, parse_housing, build_candidate, ECB
from etl.sources.worldbank_gold import URL, parse_xlsx
from etl.static_export import build
from etl.gold_monthly import expected_months

APPROVED_CBS_SHA256 = "ad98bba942b0bc0c43ff142c7972c3e2742f53088398edb3ccde4ff422bbd8f6"
APPROVED_PUBLIC_JSON_SHA256 = "bc15f3bd1c2101df6fd6a8e18b60f62ff2fc3032eb0b71009bb6b44704c5c78e"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def render(housing_raw, baseline_json_raw, gold_candidate, *, housing_path,
           gold_source_sha256, ecb_source_sha256):
    if sha(housing_raw) != APPROVED_CBS_SHA256 or sha(baseline_json_raw) != APPROVED_PUBLIC_JSON_SHA256:
        raise ValueError("APPROVED_CBS_BASELINE_HASH_MISMATCH")
    baseline = json.loads(baseline_json_raw)
    previous = baseline["data"]
    periods = [row["period"] for row in previous]
    if periods != expected_months("2000-01", periods[-1]):
        raise ValueError("Approved CBS calendar invalid")
    coverage = gold_candidate["coverage"]
    if [row["month"] for row in coverage] != periods:
        raise ValueError("Gold coverage must include every approved CBS month")
    if any(row["status"] not in ("complete", "pending_publication") for row in coverage):
        raise ValueError("Historical gold source gap")
    # Missing recent months may only be a trailing source publication delay.
    pending = False
    for row in coverage:
        if row["status"] == "pending_publication":
            pending = True
        elif pending:
            raise ValueError("Non-trailing gold publication gap")
    if not gold_candidate["data"] or gold_candidate["data"][0]["month"] != "2000-01":
        raise ValueError("Gold index basis missing")
    previous_flags = {k: os.environ.get(k) for k in ("GOLD_PUBLICATION_ENABLED", "GOLD_PUBLICATION_APPROVAL")}
    try:
        os.environ["GOLD_PUBLICATION_ENABLED"] = "true"
        os.environ["GOLD_PUBLICATION_APPROVAL"] = "APPROVED"
        payload = build(housing_path, gold_candidate=gold_candidate, gold_publication_approved=True)
    finally:
        for key, old in previous_flags.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
    rows = payload["data"]
    if len(rows) != len(previous) or [r["period"] for r in rows] != periods:
        raise ValueError("Gold candidate changed CBS month coverage")
    for row, old in zip(rows, previous):
        if row["gold_eur_oz"] is not None:
            raise ValueError("EUR/oz must remain null")
        for field in ("house_eur", "hpi", "hpi_index"):
            if row[field] != old[field]:
                raise ValueError("Approved CBS series changed")
        if row["period"] < "2000-01" and any(row[k] is not None for k in
              ("gold_eur_oz", "gold_index", "gold_grams_per_house")):
            raise ValueError("Historical gold must remain null")
    if rows[0]["gold_index"] != 100:
        raise ValueError("January 2000 gold index basis must be 100")
    candidate_json = (json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode()
    manifest = {
        "status": "GOLD_01_REVIEW_ONLY_NOT_DEPLOYED",
        "publication_authorized": False,
        "source_world_bank_url": URL,
        "source_world_bank_sha256": gold_source_sha256,
        "source_ecb_series": "EXR.D.USD.EUR.SP00.A",
        "source_ecb_url": ECB,
        "source_ecb_sha256": ecb_source_sha256,
        "approved_cbs_csv_sha256": sha(housing_raw),
        "approved_public_json_sha256": sha(baseline_json_raw),
        "candidate_json_sha256": sha(candidate_json),
        "total_months": len(rows),
        "gold_complete_months": len(gold_candidate["data"]),
        "gold_pending_months": sum(x["status"] == "pending_publication" for x in coverage),
        "public_gold_fields": ["gold_index", "gold_grams_per_house"],
        "gold_eur_oz": "always_null",
        "benchmark_change": "2025-06",
    }
    return candidate_json, (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--housing", type=Path, default=Path("data/cbs-housing.csv"))
    parser.add_argument("--baseline-json", type=Path, default=Path("frontend/public/data/monthly.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    root = Path(__file__).resolve().parents[1]
    if any(output == forbidden or forbidden in output.parents for forbidden in
           (root / "data", root / "frontend", root / "etl")):
        raise ValueError("Refusing public or source output location")
    if output.exists():
        raise ValueError("Review output already exists")
    housing_raw = args.housing.read_bytes()
    baseline_raw = args.baseline_json.read_bytes()
    if sha(housing_raw) != APPROVED_CBS_SHA256 or sha(baseline_raw) != APPROVED_PUBLIC_JSON_SHA256:
        raise ValueError("APPROVED_CBS_BASELINE_HASH_MISMATCH")
    wb = acquire(URL)
    _, _, gold, invalid, duplicates, _ = parse_xlsx(wb)
    if invalid or duplicates or not gold:
        raise ValueError("World Bank GOLD invalid/duplicate")
    fx_raw = acquire(ECB)
    fx, counts, _ = parse_ecb(fx_raw)
    houses = parse_housing(housing_raw)
    candidate = build_candidate(gold, fx, houses, counts)
    payload, manifest = render(housing_raw, baseline_raw, candidate,
        housing_path=args.housing, gold_source_sha256=sha(wb), ecb_source_sha256=sha(fx_raw))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        stage = Path(tmp)
        (stage / "monthly.gold-review.json").write_bytes(payload)
        (stage / "manifest.json").write_bytes(manifest)
        os.rename(stage, output)
    print("GOLD_01_REVIEW_ONLY", output)
    print(manifest.decode())


if __name__ == "__main__":
    main()
