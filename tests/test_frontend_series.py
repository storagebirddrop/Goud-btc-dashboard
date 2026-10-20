"""Regression guards for the dashboard series registry (frontend/src/series.ts).

The registry decides which series the public interface may show: a series is visible only when its
publication is not 'withheld' AND the loaded JSON holds finite values. Neither a label nor a value alone
authorizes publication. These tests parse the registry source (one entry per line) and, where Node can run
TypeScript directly, execute the visibility gate itself.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERIES_TS = ROOT / "frontend" / "src" / "series.ts"
MAIN_TSX = ROOT / "frontend" / "src" / "main.tsx"
MONTHLY = ROOT / "frontend" / "public" / "data" / "monthly.json"

EXPECTED = {
    # key: (category, kind, publication, base, unit)
    "house_eur": ("nominal", "eur", "open", None, "EUR"),
    "hpi": ("index", "index", "open", "2020", "indexpunten, 2020 = 100"),
    "hpi_index": ("index", "index", "open", "2000", "indexpunten, januari 2000 = 100"),
    "gold_index": ("index", "index", "gated", "2000", "indexpunten, januari 2000 = 100"),
    "gold_grams_per_house": ("alternative", "gram", "gated", None, "gram"),
    "sat_per_house": ("alternative", "sat", "withheld", None, "satoshi"),
}


def _registry():
    text = SERIES_TS.read_text(encoding="utf-8")
    block = text[text.index("export const SERIES"):text.index("export const CATEGORIES")]
    entries = {}
    for m in re.finditer(r"^ (\w+):\{(.*)\},?$", block, re.M):
        entries[m.group(1)] = dict(re.findall(r"(\w+):'([^']*)'", m.group(2)))
    return entries


def _type_union(name):
    text = SERIES_TS.read_text(encoding="utf-8")
    m = re.search(rf"export type {name}=([^;]+);", text)
    assert m, name
    return set(re.findall(r"'([^']+)'", m.group(1)))


def test_registry_has_exactly_the_declared_keys():
    assert set(_registry()) == _type_union("SeriesKey") == set(EXPECTED)


@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_category_kind_publication_base_and_unit(key):
    category, kind, publication, base, unit = EXPECTED[key]
    e = _registry()[key]
    assert (e["category"], e["kind"], e["publication"], e.get("base"), e["unit"]) == (category, kind, publication, base, unit)
    assert e["source"]


def test_index_series_always_state_their_base_and_levels_never_do():
    for key, e in _registry().items():
        if e["kind"] == "index":
            assert e.get("base") in {"2000", "2020"}, key
            assert e["category"] == "index", key
            assert re.search(r"(2000|2020) = 100", e["unit"]), key
        else:
            assert "base" not in e, key


def test_index_base_matches_the_unit_text():
    for key, e in _registry().items():
        if e["kind"] == "index":
            expected = "2020 = 100" if e["base"] == "2020" else "januari 2000 = 100"
            assert expected in e["unit"], key


def test_withheld_series_is_never_offered_in_cards():
    text = SERIES_TS.read_text(encoding="utf-8")
    withheld = {k for k, e in _registry().items() if e["publication"] == "withheld"}
    assert withheld == {"sat_per_house"}
    for const in ("CARD_KEYS",):
        line = re.search(rf"export const {const}:SeriesKey\[\]=\[([^\]]*)\]", text).group(1)
        assert not withheld & set(re.findall(r"'(\w+)'", line)), const
    assert "isWithheld(k)" in text and "!isWithheld(k)&&" in text, "visibleKeys must exclude withheld series"


def test_sat_per_house_is_not_in_the_public_json_contract():
    rows = json.loads(MONTHLY.read_text(encoding="utf-8"))["data"]
    assert all("sat_per_house" not in r for r in rows)
    assert "sat_per_house" not in (ROOT / "etl" / "static_export.py").read_text(encoding="utf-8")


def test_registry_keys_match_the_json_columns_and_raw_gold_is_not_registered():
    row = json.loads(MONTHLY.read_text(encoding="utf-8"))["data"][0]
    registered = set(_registry()) - {"sat_per_house"}
    assert registered <= set(row)
    assert "gold_eur_oz" not in _registry()
    assert "gold_eur_oz" not in MAIN_TSX.read_text(encoding="utf-8").replace("gold_eur_oz:number|null", "")


def test_public_data_still_carries_no_gold_and_no_historic_rows():
    rows = json.loads(MONTHLY.read_text(encoding="utf-8"))["data"]
    assert len(rows) == 320 and rows[0]["period"] == "2000-01"
    for r in rows:
        assert r["gold_eur_oz"] is None and r["gold_index"] is None and r["gold_grams_per_house"] is None
    # the gated gold series therefore cannot be visible with the committed data
    gated = [k for k, e in _registry().items() if e["publication"] == "gated"]
    assert all(r[k] is None for r in rows for k in gated)


def test_research_artifacts_stay_out_of_the_frontend():
    for path in (ROOT / "frontend" / "src").rglob("*"):
        if path.suffix in {".ts", ".tsx"}:
            text = path.read_text(encoding="utf-8")
            assert not re.search(r"hist_0|HIST-0|docs/research|1995|NLG", text), path.name
    assert not list((ROOT / "frontend" / "public").rglob("*hist*"))


def test_main_uses_the_registry_and_keeps_its_functionality():
    text = MAIN_TSX.read_text(encoding="utf-8")
    assert "from './series'" in text and "visibleKeys(data)" in text
    assert "const SERIES" not in text, "the registry lives in series.ts only"
    for needle in ("id=\"h-cards\"", "id=\"h-chart\"", "Bronnen &amp; methode", "Toon als tabel",
                   "'Alles'", "'Sinds 2008'", "'Laatste 10 jaar'", "<Chart", "<Card", "baseLine={curView.baseLine} annotate",
                   "jun 2025: bronwijziging goud", "fetch('/data/monthly.json')"):
        assert needle in text, needle
    for cat in ("nominal", "index", "alternative"):
        assert f"id:'{cat}'" in SERIES_TS.read_text(encoding="utf-8")


def _node_can_strip_types():
    node = shutil.which("node")
    if not node:
        return None
    v = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip().lstrip("v").split(".")
    return node if (int(v[0]), int(v[1])) >= (22, 6) else None


@pytest.mark.skipif(_node_can_strip_types() is None, reason="needs Node >= 22.6 to run TypeScript directly")
def test_visibility_gate_executes_as_documented():
    script = f"""
import {{visibleKeys,BASES}} from {json.dumps(SERIES_TS.as_uri())};
const row=(o)=>({{period:'2000-01',gold_eur_oz:null,house_eur:null,hpi:null,gold_grams_per_house:null,gold_index:null,hpi_index:null,...o}});
const out={{
 empty:visibleKeys([]),
 cbs:visibleKeys([row({{house_eur:100,hpi:90,hpi_index:100}})]),
 gold:visibleKeys([row({{gold_index:100,gold_grams_per_house:5}})]),
 nan:visibleKeys([row({{house_eur:NaN,hpi:Infinity,gold_index:null}})]),
 sat:visibleKeys([row({{house_eur:1,sat_per_house:123456}})]),
 raw:visibleKeys([row({{gold_eur_oz:2000}})]),
 bases:BASES.map(b=>[b.id,b.keys]),
}};
console.log(JSON.stringify(out));
"""
    res = subprocess.run([_node_can_strip_types(), "--experimental-strip-types", "--no-warnings", "--input-type=module", "-e", script],
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout.strip().splitlines()[-1])
    assert out["empty"] == []
    assert out["cbs"] == ["house_eur", "hpi", "hpi_index"]
    assert out["gold"] == ["gold_index", "gold_grams_per_house"]  # data present and not withheld
    assert out["nan"] == []  # non-finite values never count
    assert out["sat"] == ["house_eur"]  # finite sat data stays hidden: a withheld series is never shown
    assert out["raw"] == []  # raw gold EUR/oz is not a series
    assert out["bases"] == [["2000", ["hpi_index", "gold_index"]], ["2020", ["hpi"]]]
