"""HIST-12: static guarantees of the inert historical frontend (source level; the browser behaviour is covered by tests/hist12/browser.py)."""
import re
from pathlib import Path

from tools import hist_publication as hp

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend/src"
HIST_TS = (SRC / "hist.ts").read_text(encoding="utf-8")
MAIN = (SRC / "main.tsx").read_text(encoding="utf-8")
VIEW = (SRC / "HistoricView.tsx").read_text(encoding="utf-8")


def test_the_pin_list_is_empty_and_synthetic_data_is_not_allowed_in_the_shipped_source():
    assert "export const HIST_APPROVED_PAYLOAD_SHA256:readonly string[]=[];" in HIST_TS
    assert "export const HIST_ALLOW_SYNTHETIC=false;" in HIST_TS


def test_the_typescript_specification_equals_the_python_contract():
    rows = re.findall(r"^ (hist_[a-z_]+):\{frequency:'(\w+)',currency:'(\w+)',unit:'(\w+)',kind:'(\w+)',definition_id:'(\w+)',layer:'(\w+)',first:'([^']+)',last:'([^']+)',count:(\d+),flags:\[([^\]]*)\]\}", HIST_TS, re.M)
    assert len(rows) == len(hp.APPROVED_SERIES) == 4
    for sid, freq, cur, unit, kind, definition, layer, first, last, count, flags in rows:
        spec = hp.APPROVED_SERIES[sid]
        assert (freq, cur, unit, kind, definition, layer, first, last, int(count)) == (
            spec["frequency"], spec["currency"], spec["unit"], spec["kind"], spec["definition_id"], spec["layer"], spec["first"], spec["last"], spec["count"])
        assert tuple(re.findall(r"'(\w+)'", flags)) == spec["required_flags"]
    assert f"HIST_NLG_PER_EUR={hp.NLG_PER_EUR}" in HIST_TS and f"'{hp.SYNTHETIC_MARKER}'" in HIST_TS
    assert "'STATISTICS_DIFFER'" in HIST_TS and hp.COMPARISON_WARNING == "STATISTICS_DIFFER"


LOAD = (SRC / "histLoad.ts").read_text(encoding="utf-8")
NAV = (SRC / "histNav.ts").read_text(encoding="utf-8")


def test_the_historical_file_is_requested_only_when_a_hash_is_pinned_and_nothing_else_can_authorize():
    assert re.findall(r"fetch\(\s*([^),]+)", LOAD) == ["'/data/historical.json'"] and "fetch(" not in MAIN.replace("fetch('/data/monthly.json')", "")
    assert "if(pins.length===0)return null;" in LOAD and "loadHist()" in MAIN
    for name in ("main.tsx", "hist.ts", "HistoricView.tsx", "histLoad.ts"):
        text = (SRC / name).read_text(encoding="utf-8")
        assert not re.search(r"localStorage|sessionStorage|indexedDB|document\.cookie|URLSearchParams|location\.(search|hash)|pushState", text), f"{name}: no browser state, query parameter or URL may influence the gate"
    # the hash may only choose the TAB, via one dedicated module, for the exact literal, and only after a payload has been authorized
    assert re.findall(r"window\.location\.hash", NAV) == ["window.location.hash"] and "const HASH='#historisch';" in NAV and "setHistHash" in MAIN
    assert "if(!hist){setView('actueel');return}" in MAIN and "const go=(v:'actueel'|'historisch')=>{if(!hist)return;" in MAIN
    assert "{hist&&<div className=\"segs\" role=\"tablist\"" in MAIN  # the tabs exist only for an authorized payload
    assert "activateHist(" not in MAIN and "HIST_ALLOW_SYNTHETIC" not in MAIN and "HIST_ALLOW_SYNTHETIC" not in LOAD


def test_failures_expose_no_payload_detail():
    assert "catch{return null}" in HIST_TS and "catch{return null}" in LOAD and "error" not in VIEW.lower().replace("terror", "")
    assert not re.search(r"setError\([^)]*hist", MAIN, re.I)


def test_the_view_holds_no_gold_index_cpi_bitcoin_or_interpolation():
    text = VIEW.lower().replace("niet aangevuld of geïnterpoleerd", "")
    for word in ("gold", "goud", "gram", "index", "cpi", "bitcoin", "btc", "brandstof", "aandeel"):
        assert not re.search(rf"\b{word}", text), word
    assert "connectNulls={false}" in VIEW and "smooth" not in VIEW.lower() and 'type="linear"' in VIEW
    assert "monotone" not in VIEW


def test_no_historical_file_or_fixture_ships_with_the_frontend():
    public = ROOT / "frontend/public"
    assert not list(public.rglob("*hist*")) and not (public / "data/historical.json").exists()
    assert "SYNTHETIC" not in "".join(p.read_text(encoding="utf-8") for p in (SRC / "main.tsx", SRC / "style.css")) 
