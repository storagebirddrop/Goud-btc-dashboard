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
ALLOWED_SOURCE_LINES = {
    # series.ts: type unions and the WITHHELD registry entry (publication:'withheld'), plus the repo URL
    ("series.ts", r"^export type SeriesKey="),
    ("series.ts", r"^export type Point="),
    ("series.ts", r"^export type Kind="),
    ("series.ts", r"^ sat_per_house:\{.*publication:'withheld'"),
    ("series.ts", r"^export const METHODOLOGY_URL='https://github\.com/storagebirddrop/Goud-btc-dashboard/"),
    # main.tsx: number formatting for the 'sat' kind and the static "not yet available" copy
    ("main.tsx", r"^function fmt\(kind:Kind"),
    ("main.tsx", r"^ const missing=\['reële EUR',\.\.\.\(hasGold\?\[\]:\['goud'\]\),'Bitcoin'\]\.join"),
}


def test_every_bitcoin_mention_in_frontend_sources_is_an_approved_one():
    unexpected = []
    for path in sorted(SRC.glob("*.ts*")):
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("//"):
                continue  # comments are never rendered
            if BTC.search(line) and not any(path.name == f and re.search(rx, line) for f, rx in ALLOWED_SOURCE_LINES):
                unexpected.append(f"{path.name}:{no}: {line.strip()[:100]}")
    assert not unexpected, "new Bitcoin/satoshi mention in the frontend; review the publication gate first:\n" + "\n".join(unexpected)


def test_withheld_sat_entry_is_the_only_registry_entry_with_btc_semantics():
    text = (SRC / "series.ts").read_text(encoding="utf-8")
    block = text[text.index("export const SERIES"):text.index("export const CATEGORIES")]
    btc_entries = [l for l in block.splitlines() if BTC.search(l)]
    assert len(btc_entries) == 1 and "publication:'withheld'" in btc_entries[0]
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
