"""DASH-02 guards: chart views, period selection and the single-source-of-truth wiring of the dashboard.

Pure view and period logic lives in frontend/src/series.ts and is executed with Node's built-in TypeScript
stripping (Node >= 22.6; skipped otherwise). The rest checks that main.tsx wires the controls to that logic
without duplicating them.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERIES_TS = ROOT / "frontend" / "src" / "series.ts"
MAIN_TSX = ROOT / "frontend" / "src" / "main.tsx"
CSS = ROOT / "frontend" / "src" / "style.css"


from _node_ts import run_series as _run


MONTHS = "const months=(a,b)=>{const o=[];for(let y=a;y<=b;y++)for(let m=1;m<=12;m++)o.push(`${y}-${String(m).padStart(2,'0')}`);return o};"


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


def test_withheld_series_never_become_a_chart_view():
    out = _run("""
const data=[{period:'2000-01',gold_eur_oz:null,house_eur:1,hpi:1,hpi_index:100,gold_index:null,gold_grams_per_house:null,sat_per_house:123456}];
console.log(JSON.stringify(S.chartViews(S.visibleKeys(data)).map(v=>v.id)));
""")
    assert "sat_per_house" not in out and out == ["house_eur", "index-2000", "index-2020"]


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


def test_slice_range_is_inclusive_and_does_not_fill_gaps():
    out = _run("""
const d=[{period:'2000-01',x:1},{period:'2000-03',x:3},{period:'2000-04',x:4}];
console.log(JSON.stringify(S.sliceRange(d,{from:'2000-02',to:'2000-04'}).map(r=>r.period)));
""")
    assert out == ["2000-03", "2000-04"]


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


def test_table_follows_the_selected_period_and_never_fills_months():
    text = MAIN_TSX.read_text(encoding="utf-8")
    assert "<tbody>{rows.map(p=>" in text and "data.map(p=><tr" not in text
    assert "dezelfde periode als de grafiek" in text  # caption names the shown range
    # the same `rows` feed chart, cards and table; a missing month is simply absent, never invented
    assert text.count("sliceRange(data,eff)") == 1


def test_annotation_text_lives_in_the_registry_not_in_the_view_code():
    main = MAIN_TSX.read_text(encoding="utf-8")
    assert "2025-06" not in main and "jun 2025" not in main
    assert "viewAnnotations(keys,rows)" in main and "annotate" not in main
    series = SERIES_TS.read_text(encoding="utf-8")
    reg = {m.group(1): m.group(2) for m in re.finditer(r"^ (\w+):\{(.*)\},?$", series, re.M)}
    with_notes = {k for k, v in reg.items() if "annotations:" in v}
    assert with_notes == {"gold_index", "gold_grams_per_house"}, "only the World Bank gold series carry the June 2025 break"
    for k in ("house_eur", "hpi", "hpi_index", "sat_per_house"):
        assert "annotations:" not in reg[k], k


def test_annotations_are_series_specific_and_need_data_on_both_sides():
    out = _run("""
const row=(p,o)=>({period:p,gold_eur_oz:null,house_eur:null,hpi:null,gold_grams_per_house:null,gold_index:null,hpi_index:null,...o});
const periods=['2025-04','2025-05','2025-06','2025-07'];
const withGold=periods.map((p,i)=>row(p,{gold_index:100+i,gold_grams_per_house:50+i,house_eur:1,hpi:1,hpi_index:1}));
const onlyBefore=periods.map((p,i)=>row(p,{gold_index:i<2?100:null,house_eur:1,hpi:1,hpi_index:1}));
const noBreakRow=periods.filter(p=>p!=='2025-06').map((p,i)=>row(p,{gold_index:100+i}));
const labels=(keys,rows)=>S.viewAnnotations(keys,rows).map(a=>a.period+'|'+a.label);
console.log(JSON.stringify({
 gold:labels(['gold_index'],withGold),
 grams:labels(['gold_grams_per_house'],withGold),
 both:labels(['hpi_index','gold_index'],withGold),
 cbsOnly:labels(['house_eur'],withGold),
 hpiOnly:labels(['hpi_index'],withGold),
 satFuture:labels(['sat_per_house'],withGold),
 beforeOnly:labels(['gold_index'],onlyBefore),
 missingMonth:labels(['gold_index'],noBreakRow),
 rangeAfter:labels(['gold_index'],withGold.slice(2)),
}));
""")
    note = ["2025-06|jun 2025: bronwijziging goud"]
    assert out["gold"] == note and out["grams"] == note and out["both"] == note
    assert out["cbsOnly"] == [] and out["hpiOnly"] == [] and out["satFuture"] == []
    assert out["beforeOnly"] == [] and out["missingMonth"] == [] and out["rangeAfter"] == []
