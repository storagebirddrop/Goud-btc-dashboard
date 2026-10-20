"""DASH-02 guards: chart views, period selection and the single-source-of-truth wiring of the dashboard.

Pure view and period logic lives in frontend/src/series.ts and is executed with Node's built-in TypeScript
stripping (Node >= 22.6; skipped otherwise). The rest checks that main.tsx wires the controls to that logic
without duplicating them.
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
CSS = ROOT / "frontend" / "src" / "style.css"


def _node():
    node = shutil.which("node")
    if not node:
        return None
    v = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip().lstrip("v").split(".")
    return node if (int(v[0]), int(v[1])) >= (22, 6) else None


def _run(body):
    script = f"import * as S from {json.dumps(SERIES_TS.as_uri())};\n{body}"
    res = subprocess.run([_node(), "--experimental-strip-types", "--no-warnings", "--input-type=module", "-e", script],
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout.strip().splitlines()[-1])


needs_node = pytest.mark.skipif(_node() is None, reason="needs Node >= 22.6 to run TypeScript directly")

MONTHS = "const months=(a,b)=>{const o=[];for(let y=a;y<=b;y++)for(let m=1;m<=12;m++)o.push(`${y}-${String(m).padStart(2,'0')}`);return o};"


@needs_node
def test_views_follow_the_visible_series_and_keep_the_three_categories_apart():
    out = _run("""
const v=(ks)=>S.chartViews(ks).map(x=>[x.id,x.category,x.keys,x.unit,x.baseLine]);
console.log(JSON.stringify({
 cbs:v(['house_eur','hpi','hpi_index']),
 gold:v(['house_eur','hpi','hpi_index','gold_index','gold_grams_per_house']),
 none:v([]),
}));
""")
    assert out["cbs"] == [
        ["house_eur", "nominal", ["house_eur"], "EUR", False],
        ["index-2000", "index", ["hpi_index"], "indexpunten, januari 2000 = 100", True],
        ["index-2020", "index", ["hpi"], "indexpunten, 2020 = 100 (CBS-basis)", True],
    ]
    cats = [(x[0], x[1]) for x in out["gold"]]
    assert cats == [("house_eur", "nominal"), ("index-2000", "index"), ("index-2020", "index"), ("gold_grams_per_house", "alternative")]
    assert ["hpi_index", "gold_index"] == out["gold"][1][2]
    assert out["none"] == []


@needs_node
def test_withheld_series_never_become_a_chart_view():
    out = _run("""
const data=[{period:'2000-01',gold_eur_oz:null,house_eur:1,hpi:1,hpi_index:100,gold_index:null,gold_grams_per_house:null,sat_per_house:123456}];
console.log(JSON.stringify(S.chartViews(S.visibleKeys(data)).map(v=>v.id)));
""")
    assert "sat_per_house" not in out and out == ["house_eur", "index-2000", "index-2020"]


@needs_node
def test_presets_cover_the_expected_ranges():
    out = _run(MONTHS + """
const p=months(2000,2026).slice(0,320);
const r=(id)=>S.presetRange(id,p);
console.log(JSON.stringify({all:r('all'),y2008:r('2008'),y10:r('10y'),short:S.presetRange('2008',months(2010,2011)),none:S.presetRange('all',[]),n:p.length}));
""")
    assert out["n"] == 320
    assert out["all"] == {"from": "2000-01", "to": "2026-08"}
    assert out["y2008"] == {"from": "2008-01", "to": "2026-08"}
    assert out["y10"] == {"from": "2016-09", "to": "2026-08"}  # 120 months ending 2026-08
    assert out["short"] == {"from": "2010-01", "to": "2011-12"}  # data starts after 2008: no invented months
    assert out["none"] is None


@needs_node
def test_free_month_selection_is_clamped_and_never_inverted():
    out = _run(MONTHS + """
const p=months(2000,2026).slice(0,320);
const c=(f,t)=>S.clampRange({from:f,to:t},p);
console.log(JSON.stringify({
 ok:c('2010-03','2012-06'),
 before:c('1990-01','2001-01'),
 after:c('2020-01','2099-12'),
 inverted:c('2015-05','2012-01'),
 garbage:c('abc','2012-13'),
 single:c('2012-06','2012-06'),
 empty:S.clampRange({from:'2010-01',to:'2011-01'},[]),
}));
""")
    assert out["ok"] == {"from": "2010-03", "to": "2012-06"}
    assert out["before"] == {"from": "2000-01", "to": "2001-01"}
    assert out["after"] == {"from": "2020-01", "to": "2026-08"}
    assert out["inverted"]["from"] <= out["inverted"]["to"]
    assert out["garbage"] == {"from": "2000-01", "to": "2026-08"}
    assert out["single"] == {"from": "2012-06", "to": "2012-06"}
    assert out["empty"] is None


@needs_node
def test_slice_range_is_inclusive_and_does_not_fill_gaps():
    out = _run("""
const d=[{period:'2000-01',x:1},{period:'2000-03',x:3},{period:'2000-04',x:4}];
console.log(JSON.stringify(S.sliceRange(d,{from:'2000-02',to:'2000-04'}).map(r=>r.period)));
""")
    assert out == ["2000-03", "2000-04"]


@needs_node
def test_index_bases_stay_separate_views():
    out = _run("console.log(JSON.stringify(S.BASES.map(b=>[b.id,b.caption,b.keys])));")
    assert out == [["2000", "januari 2000 = 100", ["hpi_index", "gold_index"]], ["2020", "2020 = 100 (CBS-basis)", ["hpi"]]]


def test_main_uses_the_shared_logic_and_has_one_period_control_set():
    text = MAIN_TSX.read_text(encoding="utf-8")
    for fn in ("chartViews(", "presetRange(", "clampRange(", "sliceRange("):
        assert fn in text, fn
    # the period state is one range; no second preset/base state that could contradict it
    assert text.count("useState<Range|null>") == 1
    assert "useState<Preset>" not in text and "baseId" not in text and "LEVEL_KEYS" not in text
    # one chart panel instead of two competing ones
    assert text.count("<Chart ") == 1 and "id=\"h-level\"" not in text and "id=\"h-idx\"" not in text
    # the view list comes from the registry-driven visible keys only
    assert "chartViews([...avail])" in text


def test_controls_are_labelled_and_accessible():
    text = MAIN_TSX.read_text(encoding="utf-8")
    for needle in ('aria-label="Periode"', 'aria-label="Soort weergave"', "aria-pressed=", 'role="status" aria-live="polite"',
                   "accessibilityLayer", "<label className=\"field\" htmlFor={id}>", "type=\"month\""):
        assert needle in text, needle
    css = CSS.read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in css and "pointer:coarse" in css and "max-width:560px" in css
    assert re.search(r"height=\{narrow\?\d+:\d+\}", text), "chart height must adapt to narrow screens"


def test_no_new_frontend_dependencies_or_data_paths():
    pkg = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    assert set(pkg["dependencies"]) == {"react", "react-dom", "recharts"}
    assert set(pkg["devDependencies"]) == {"@types/react", "@types/react-dom", "typescript", "vite"}
