"""GOLD-03 prep guards: the gold source block, the source reference date constant and the wording limits.

The block text lives in frontend/src/series.ts (pure, executable with Node); main.tsx only renders it for views
that contain a gold series. No claim about licence status, approval or endorsement may appear anywhere.
"""
import re
from pathlib import Path

from _node_ts import run_series

ROOT = Path(__file__).resolve().parents[1]
SERIES_TS = ROOT / "frontend" / "src" / "series.ts"
MAIN_TSX = ROOT / "frontend" / "src" / "main.tsx"

FORBIDDEN = ["goedgekeurd door", "gelicenseerd", "gelicentieerd", "licentie van", "in opdracht van", "met toestemming van",
             "officieel partner", "gesponsord", "geautoriseerd door", "endorsed by", "licensed by", "approved by"]

ALL_TEXT = ("S.GOLD_SOURCE_LINKS.map(l=>[l.name,l.detail,l.url,l.linkText].join(' ')).join(' ')+' '+S.GOLD_OWN_CALC_TEXT+' '"
            "+S.GOLD_METHOD_TEXT.join(' ')+' '+S.GOLD_BREAK_TEXT+' '+S.GOLD_SOURCE_ASOF.note")


def _block():
    main = MAIN_TSX.read_text(encoding="utf-8")
    return main[main.index("function GoldSources"):main.index("type TipProps")]


def test_source_block_is_rendered_only_for_views_with_a_gold_series():
    out = run_series("""
console.log(JSON.stringify({
 cbs:[['house_eur'],['hpi_index'],['hpi']].map(S.viewHasGold),
 gold:[['gold_index'],['gold_grams_per_house'],['hpi_index','gold_index']].map(S.viewHasGold),
 sat:S.viewHasGold(['sat_per_house']),
}));
""")
    assert out["cbs"] == [False, False, False] and out["gold"] == [True, True, True] and out["sat"] is False
    main = MAIN_TSX.read_text(encoding="utf-8")
    assert main.count("<GoldSources ") == 1
    assert "{viewHasGold(curView.keys)&&<GoldSources data={data} keys={curView.keys}/>}" in main
    # directly under the chart (before the footer status line) and never inside the collapsed <details>
    assert main.index("<GoldSources ") < main.index("Gebruik de pijltjestoetsen")
    assert main.index("<GoldSources ") < main.index("<details")
    assert "<details" not in _block()


def test_source_block_names_sources_links_series_and_statements():
    out = run_series(f"console.log(JSON.stringify({{links:S.GOLD_SOURCE_LINKS.map(l=>l.url),all:{ALL_TEXT},method:S.METHODOLOGY_URL}}));")
    assert out["links"] == ["https://www.worldbank.org/en/research/commodity-markets",
                            "https://data.ecb.europa.eu/data/datasets/EXR/EXR.D.USD.EUR.SP00.A",
                            "https://opendata.cbs.nl/CBS/nl/dataset/85773NED/table"]
    t = out["all"]
    for needle in ("World Bank Commodity Markets (Pink Sheet)", "GOLD", "USD per troy ounce", "EXR.D.USD.EUR.SP00.A", "USD per EUR",
                   "85773NED", "eigen berekeningen", "onderschrijft deze toepassing", "januari 2000 = 100", "31,1034768",
                   "maandgemiddelde", "gedeeld door", "London afternoon fixing", "juni 2025", "gemiddelde dagelijkse spotprijzen",
                   "niet volledig benchmarkhomogeen", "mei 2025"):
        assert needle in t, needle
    assert out["method"] == "https://github.com/storagebirddrop/Goud-btc-dashboard/blob/main/docs/governance/METHODOLOGY.md"
    block = _block()
    for needle in ("goldPeriod(data,keys)", "GOLD_SOURCE_ASOF.date", "Peildatum bronstand", "METHODOLOGY_URL", "GOLD_BREAK_TEXT",
                   "GOLD_OWN_CALC_TEXT", "GOLD_SOURCE_LINKS"):
        assert needle in block, needle


def test_collapsed_sources_section_is_consistent_with_the_block():
    main = MAIN_TSX.read_text(encoding="utf-8")
    sec = main[main.index("Bronnen &amp; methode</summary>"):main.index("Gegevens als tabel")]
    for needle in ("METHODOLOGY_URL", "asOfText()", "GOLD_BREAK_TEXT", "GOLD_METHOD_TEXT",
                   "geen bronorganisatie onderschrijft deze toepassing", "{hasGold&&"):
        assert needle in sec, needle


def test_source_asof_constant_is_a_valid_iso_date_and_used_in_the_rendered_text():
    out = run_series("""
console.log(JSON.stringify({d:S.GOLD_SOURCE_ASOF.date,note:S.GOLD_SOURCE_ASOF.note,ok:S.isIsoDate(S.GOLD_SOURCE_ASOF.date),
 bad:['2026-02-30','2026-13-01','20261020','2026-1-1','',' 2026-10-20'].map(S.isIsoDate)}));
""")
    assert out["ok"] is True and re.fullmatch(r"\d{4}-\d{2}-\d{2}", out["d"])
    assert out["bad"] == [False] * 6
    assert "release" in out["note"] and "bijwerken" in out["note"]
    main = MAIN_TSX.read_text(encoding="utf-8")
    assert main.count("asOfText()") >= 2 and "GOLD_SOURCE_ASOF.date.split('-')" in main
    assert "dateTime={GOLD_SOURCE_ASOF.date}" in main
    assert not re.search(r"20\d\d-\d\d-\d\d", main), "the date is defined once, in series.ts"
    assert len(re.findall(r"export const GOLD_SOURCE_ASOF", SERIES_TS.read_text(encoding="utf-8"))) == 1


def test_period_text_is_derived_from_the_data_not_hard_coded():
    out = run_series("""
const r=(p,o)=>({period:p,gold_eur_oz:null,house_eur:1,hpi:1,gold_grams_per_house:null,gold_index:null,hpi_index:1,...o});
const d=[r('2000-01'),r('2000-02',{gold_index:100}),r('2000-03',{gold_index:NaN,gold_grams_per_house:7}),r('2000-04',{gold_index:120}),r('2000-05')];
console.log(JSON.stringify({a:S.goldPeriod(d,['gold_index']),b:S.goldPeriod(d,['gold_grams_per_house']),both:S.goldPeriod(d,['hpi_index','gold_index','gold_grams_per_house']),
 cbs:S.goldPeriod(d,['hpi_index']),none:S.goldPeriod([r('2000-01')],['gold_index']),empty:S.goldPeriod([],['gold_index'])}));
""")
    assert out["a"] == {"from": "2000-02", "to": "2000-04", "months": 2}
    assert out["b"] == {"from": "2000-03", "to": "2000-03", "months": 1}
    assert out["both"] == {"from": "2000-02", "to": "2000-04", "months": 3}
    assert out["cbs"] is None and out["none"] is None and out["empty"] is None
    assert not re.search(r"20\d\d", _block()), "no hard-coded years in the block"


def test_no_licence_approval_or_endorsement_claims_in_the_ui_text():
    out = run_series(f"console.log(JSON.stringify({{t:{ALL_TEXT}}}));")
    haystacks = {"series-block-text": out["t"].lower(),
                 "main.tsx": MAIN_TSX.read_text(encoding="utf-8").lower(),
                 "series.ts": SERIES_TS.read_text(encoding="utf-8").lower()}
    for name, text in haystacks.items():
        for phrase in FORBIDDEN:
            assert phrase not in text, (name, phrase)
    # the only statement about the sources' stance is the negative one
    assert "Geen van de bronorganisaties onderschrijft deze toepassing" in out["t"]
    assert "satoshi" not in out["t"].lower() and "bitcoin" not in out["t"].lower()


def test_withheld_sat_and_raw_gold_stay_out_of_registry_views_and_block():
    out = run_series("""
const row=(o)=>({period:'2000-01',gold_eur_oz:2000,house_eur:1,hpi:1,hpi_index:100,gold_index:100,gold_grams_per_house:5,sat_per_house:99999,...o});
const vis=S.visibleKeys([row({})]);const views=S.chartViews(vis);
console.log(JSON.stringify({vis,ids:views.map(v=>v.id),keys:views.flatMap(v=>v.keys),reg:Object.keys(S.SERIES),card:S.CARD_KEYS}));
""")
    assert "sat_per_house" not in out["vis"] and "sat_per_house" not in out["keys"] and "sat_per_house" not in out["card"]
    assert "gold_eur_oz" not in out["reg"] and "gold_eur_oz" not in out["vis"]
    assert out["ids"] == ["house_eur", "index-2000", "index-2020", "gold_grams_per_house"]


def test_gold_cards_state_units_and_all_three_sources():
    out = run_series("console.log(JSON.stringify({g:S.SERIES.gold_grams_per_house,i:S.SERIES.gold_index}));")
    g, i = out["g"], out["i"]
    assert g["unit"] == "gram" and g["kind"] == "gram"
    assert "januari 2000 = 100" in i["unit"]
    for needle in ("World Bank", "ECB", "CBS", "eigen berekening"):
        assert needle in g["source"], needle
    for needle in ("World Bank", "ECB", "eigen berekening"):
        assert needle in i["source"], needle
    main = MAIN_TSX.read_text(encoding="utf-8")
    assert "Bron: {s.source}" in main and "s.kind==='eur'?'EUR, nominaal':s.unit" in main
