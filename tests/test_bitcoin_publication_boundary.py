"""Publication boundary for Bitcoin: copy may be visible, data may not (GOLD-04 closure).

Bitcoin/satoshi is not authorized for publication (ADR-004 BTC, ADR-007, ADR-008 are PROPOSED). These tests keep
unpublished BTC data out of the public JSON, out of the frontend bundle sources and out of every selectable control,
and make a future refactor that exposes it fail loudly. The registry gate itself is covered in
test_frontend_series.py / test_frontend_dashboard.py; the rendered DOM is covered by tools/gold_04_live_browser.mjs.
"""
import json
import re
from pathlib import Path

from etl.static_export import build

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "src"
MONTHLY = ROOT / "frontend" / "public" / "data" / "monthly.json"
CSV = ROOT / "data" / "cbs-housing.csv"
EXPECTED_FIELDS = ["period", "gold_eur_oz", "house_eur", "hpi", "gold_grams_per_house", "gold_index", "hpi_index"]
BTC = re.compile(r"bitcoin|\bbtc|satoshi|\bsats?\b|\bsat_", re.I)


# ---- forbidden: public data ----
def test_public_json_has_exactly_the_approved_fields_and_no_btc_text():
    raw = MONTHLY.read_text(encoding="utf-8")
    assert not BTC.search(raw), "BTC/satoshi text found in the public JSON"
    for row in json.loads(raw)["data"]:
        assert list(row) == EXPECTED_FIELDS


def test_exporter_cannot_emit_btc_fields_even_with_gold_approved():
    for row in build(CSV)["data"]:
        assert list(row) == EXPECTED_FIELDS
    assert not BTC.search((ROOT / "etl" / "static_export.py").read_text(encoding="utf-8"))


def test_only_the_gold_json_is_served_from_public():
    files = sorted(p.relative_to(ROOT / "frontend" / "public").as_posix() for p in (ROOT / "frontend" / "public").rglob("*") if p.is_file())
    assert files == ["data/monthly.json"]


# ---- forbidden: frontend sources ----
# BTC-07B: all Bitcoin logic, texts and the (empty) approval pin live in frontend/src/btc.ts. Everything else may mention Bitcoin only
# through the lines below or through identifiers of that module.
ALLOWED_SOURCE_LINES = {
    ("series.ts", r"^export type SeriesKey="),
    ("series.ts", r"^export type Point="),
    ("series.ts", r"^export type Kind="),
    ("series.ts", r"^import type \{BtcMeta\} from './btc';"),
    ("series.ts", r"^ (btc|sat)_per_house:\{.*publication:'pinned'"),
    ("series.ts", r"^export const METHODOLOGY_URL='https://github\.com/storagebirddrop/Goud-btc-dashboard/"),
    ("main.tsx", r"^function fmt\(kind:Kind"),
    ("main.tsx", r"^function Tip\(|\(s\.kind==='btc'\|\|s\.kind==='sat'\)&&q"),   # generic kind check for the quality label in the tooltip
    ("main.tsx", r"<YAxis width=\{kind==='eur'"),                                       # generic kind check for the axis width/format
    ("main.tsx", r"^ const missing=\['reële EUR',\.\.\.\(hasGold\?\[\]:\['goud'\]\),\.\.\.\(btc\?\[\]:\['Bitcoin'\]\)\]\.join"),
}
BTC_MODULE_FILES = {"btc.ts"}
MAIN_BTC_TOKENS = re.compile(r"\b(btc|setBtc|BtcRoot|BtcSources|activateBtc|applyBtc|btcDefaultFrom|btcQualitiesIn|btcMissingSummary|isBtcView|btcCols|btcNote|data-btc-note|BTC_[A-Z_]+|"
                             r"btc_per_house|sat_per_house|btc_meta|data-btc-release|btc-src|btc-quality|btc-gaps|h-btc-src|\./btc)\b|btc-src|btc-quality|btc-gaps|h-btc-src|data-btc-release|data-btc-note")


def test_every_bitcoin_mention_in_frontend_sources_is_an_approved_one():
    unexpected = []
    for path in sorted(SRC.glob("*.ts*")):
        if path.name in BTC_MODULE_FILES:
            continue
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("//"):
                continue  # comments are never rendered
            if not BTC.search(line) or any(path.name == f and re.search(rx, line) for f, rx in ALLOWED_SOURCE_LINES):
                continue
            if path.name == "main.tsx" and not BTC.search(MAIN_BTC_TOKENS.sub("", line)):
                continue  # only identifiers imported from btc.ts, no literal Bitcoin text
            unexpected.append(f"{path.name}:{no}: {line.strip()[:100]}")
    assert not unexpected, "new Bitcoin/satoshi mention in the frontend; review the publication gate first:\n" + "\n".join(unexpected)


def test_bitcoin_registry_entries_are_pinned_and_never_cards():
    text = (SRC / "series.ts").read_text(encoding="utf-8")
    block = text[text.index("export const SERIES"):text.index("export const CATEGORIES")]
    btc_entries = [l for l in block.splitlines() if BTC.search(l) and l.strip().startswith(("btc_per_house", "sat_per_house"))]
    assert len(btc_entries) == 2 and all("publication:'pinned'" in l for l in btc_entries)
    assert "CARD_KEYS:SeriesKey[]=['house_eur','hpi','gold_index','gold_grams_per_house']" in text


def test_frontend_has_no_other_data_source_and_no_url_or_storage_state():
    main = (SRC / "main.tsx").read_text(encoding="utf-8")
    assert re.findall(r"fetch\(([^)]*)\)", main) == ["'/data/monthly.json'"]
    for provider in ("coingecko", "coinmetrics", "bitstamp", "kraken", "yahoo", "binance", "coinbase", "api."):
        assert provider not in main.lower(), provider
    # no URL/storage driven series selection, so a link or stored state cannot activate a withheld series
    for api in ("location.search", "location.hash", "URLSearchParams", "history.pushState", "localStorage", "sessionStorage"):
        assert api not in main, api


# ---- permitted ----
def test_static_bitcoin_copy_and_gold_sources_remain_available():
    main = (SRC / "main.tsx").read_text(encoding="utf-8")
    assert "Nog niet beschikbaar: {missing}." in main
    for needle in ("GoldSources", "GOLD_SOURCE_LINKS", "GOLD_BREAK_TEXT", "Peildatum bronstand"):
        assert needle in main


# ---- BTC-07B: Bitcoin is shown only for exactly approved bytes ----
def test_the_approval_pin_is_empty_and_main_has_no_other_activation_path():
    btc = (SRC / "btc.ts").read_text(encoding="utf-8")
    assert "export const BTC_APPROVED_COMPOSITE_SHA256:readonly string[]=[];" in btc
    main = (SRC / "main.tsx").read_text(encoding="utf-8")
    assert "activateBtc(sha,j)" in main and "import.meta.env" not in main and "process.env" not in main
    series = (SRC / "series.ts").read_text(encoding="utf-8")
    assert "import.meta.env" not in series and "import.meta.env" not in btc
    assert "visibleKeys(data,!!btc)" in main


def test_btc_data_in_loaded_json_never_makes_a_series_visible_without_the_pin():
    from _node_ts import run_modules
    res = run_modules("""
const row=(o)=>({period:'2020-01',gold_eur_oz:null,house_eur:1,hpi:1,gold_grams_per_house:null,gold_index:null,hpi_index:1,...o});
const meta={quality:'Q1_CANDIDATE',status:'PUBLISHED',missing_reason:null,flags:[]};
const root={contract_version:'btc-monthly/1',coverage:{supported_from:'2010-08',default_from:'2014-02',authorized_from:'2014-02',authorized_through:'2026-08',early_history_authorized:false},
 release:{id:'R',decision_ref:'D',publication_authorized:true},rights:{review_ref:'x',conflicting_contract_check:'VERIFIED'}};
const raw=[row({sat_per_house:1e9,btc_per_house:10,btc_meta:meta,publication_authorized:true})];
const sha='a'.repeat(64);
const doc={data:raw,btc:root};
const noPin=B.activateBtc(sha,doc);               // production pins: empty
const wrongPin=B.activateBtc(sha,doc,['b'.repeat(64)]);
const poisoned=B.applyBtc(raw,noPin);
console.log(JSON.stringify({pinsEmpty:B.BTC_APPROVED_COMPOSITE_SHA256.length,noPin,wrongPin,vis:S.visibleKeys(poisoned,false),visPinned:S.visibleKeys(poisoned,true),
 views:S.chartViews(S.visibleKeys(poisoned,!!noPin)).map(v=>v.id),vals:[poisoned[0].btc_per_house,poisoned[0].sat_per_house],
 nullSha:B.activateBtc(null,doc,[sha]),badJson:B.activateBtc(sha,{data:raw},[sha]),noFlag:B.activateBtc(sha,{...doc,btc:{...root,release:{...root.release,publication_authorized:false}}},[sha])}));
""")
    assert res["pinsEmpty"] == 0 and res["noPin"] is None and res["wrongPin"] is None
    assert res["vis"] == ["house_eur", "hpi", "hpi_index"] and res["visPinned"] == ["house_eur", "hpi", "hpi_index"]
    assert all("sat" not in v and "btc" not in v for v in res["views"]) and res["vals"] == [None, None]
    assert res["nullSha"] is None and res["badJson"] is None and res["noFlag"] is None
