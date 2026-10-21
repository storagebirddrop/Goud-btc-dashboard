"""GOLD-04: unit tests of the pure Bitcoin-boundary classifier used by the production browser check.

Invariant: Bitcoin-related COPY may be visible; Bitcoin/satoshi DATA (values, series, charts, controls) may not.
The classifier lives in tools/gold_04_boundary.mjs (no DOM access) and is executed with Node.
"""
import json
import subprocess
from pathlib import Path

from _node_ts import need_node

MODULE = Path(__file__).resolve().parents[1] / "tools" / "gold_04_boundary.mjs"

NOTE = {"tag": "P", "cls": "muted", "ancestors": ["HEADER", "MAIN", "DIV", "BODY", "HTML"],
        "text": "Nog niet beschikbaar: reële EUR en Bitcoin.", "inControl": False, "inSvg": False}


def run(payload):
    script = f"import {{scan}} from {json.dumps(MODULE.as_uri())};\nconsole.log(JSON.stringify(scan({json.dumps(payload)})));"
    res = subprocess.run([need_node(), "--no-warnings", "--input-type=module", "-e", script],
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout.strip().splitlines()[-1])


# ---- permitted ----
def test_the_approved_not_yet_available_note_is_allowed_copy():
    out = run({"leaves": [NOTE]})
    assert out["violations"] == [] and out["allowed"] == ["Nog niet beschikbaar: reële EUR en Bitcoin."]


def test_note_with_gold_missing_variant_is_allowed():
    note = {**NOTE, "text": "Nog niet beschikbaar: reële EUR, goud en Bitcoin."}
    assert run({"leaves": [note]})["violations"] == []


def test_pages_without_any_bitcoin_mention_pass():
    assert run({"leaves": [], "controls": [{"kind": "BUTTON/text", "label": "Gram goud per woning"}],
                "svgTexts": ["2000 2010 2020 Goudprijsindex jun 2025: bronwijziging goud"]}) == {"allowed": [], "violations": []}


# ---- forbidden ----
def test_a_value_next_to_bitcoin_is_a_violation():
    leaf = {**NOTE, "text": "Nog niet beschikbaar: reële EUR en Bitcoin 0,85."}
    assert len(run({"leaves": [leaf]})["violations"]) == 1


def test_bitcoin_copy_elsewhere_is_not_silently_allowed():
    for override in ({"tag": "SPAN"}, {"cls": "card"}, {"ancestors": ["MAIN"]}, {"inControl": True}, {"inSvg": True},
                     {"text": "Bitcoin per woning"}, {"text": "Satoshi per woning"}):
        assert run({"leaves": [{**NOTE, **override}]})["violations"], override


def test_selectable_bitcoin_series_controls_are_violations():
    out = run({"controls": [{"kind": "BUTTON/text", "label": "Satoshi per woning"},
                            {"kind": "OPTION/text", "label": "BTC per woning"},
                            {"kind": "A/aria-label", "label": "Sat per woning"}]})
    assert len(out["violations"]) == 3


def test_bitcoin_chart_texts_are_violations():
    assert len(run({"svgTexts": ["Satoshi per woning 1.234.567 sat", "gram goud"]})["violations"]) == 1
