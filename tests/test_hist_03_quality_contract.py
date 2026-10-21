"""HIST-03 offline quality/isolation contract tests (no network, no skips).

These tests guard the boundary between research-only historical tooling
(tools/hist_*) and the production pipeline / public data. Synthetic workbooks
prove validator behaviour only and say nothing about real World Bank data.
"""
import ast
import csv
import hashlib
import io
import json
import random
import re
import zipfile
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from tools.hist_03_worldbank_validate import (
    ValidationError, canonical_sha256, expected_months, validate)

ROOT = Path(__file__).resolve().parents[1]
HIST_TOOLS = sorted((ROOT / "tools").glob("hist_*.py"))
PROD_MODULES = sorted((ROOT / "etl").glob("*.py")) + sorted((ROOT / "etl" / "sources").glob("*.py"))
PUBLIC_JSON = ROOT / "frontend" / "public" / "data" / "monthly.json"
PUBLIC_CSV = ROOT / "data" / "cbs-housing.csv"
GOLD_FIELDS = ("gold_eur_oz", "gold_index", "gold_grams_per_house")


def _tree(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


# (a) isolation: production code never imports research tooling ---------------
def test_module_sets_not_empty():
    assert PROD_MODULES and HIST_TOOLS


def _hist_references(tree):
    bad = []
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""] + [f"{node.module}.{a.name}" for a in node.names]
        bad += [n for n in names if re.search(r"(^|\.)hist_\d+", n)]
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and re.search(r"hist_0\d", node.value):
            bad.append(node.value)  # dynamic import by string
    return bad


@pytest.mark.parametrize("path", PROD_MODULES, ids=lambda p: str(p.relative_to(ROOT)))
def test_production_never_imports_hist_tools(path):
    assert not _hist_references(_tree(path)), f"{path.name} references research tooling"


def test_isolation_detector_catches_violations():
    assert _hist_references(ast.parse("from tools.hist_03_worldbank_validate import parse"))
    assert _hist_references(ast.parse("import tools.hist_02_acquire"))
    assert _hist_references(ast.parse("from tools import hist_03_precision"))
    assert not _hist_references(ast.parse("import json\nfrom etl import static_export"))


# (b) frontend is unaware of historical research --------------------------------
def test_frontend_src_has_no_historical_references():
    files = [p for p in (ROOT / "frontend" / "src").rglob("*") if p.is_file()]
    assert files
    pattern = re.compile(r"hist[_-]0\d|HIST-0\d|1975M|fixtures|\b19\d\d(?:-\d\d)?\b|\b19\d\dM\d\d\b", re.I)
    hits = []
    for p in files:
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                hits.append(f"{p.name}:{i}")
    assert not hits, hits


# (c) committed public data stays 2000-01.., 320 months, gold null ---------------
def test_public_json_contract():
    doc = json.loads(PUBLIC_JSON.read_text(encoding="utf-8"))
    assert list(doc) == ["data"]
    rows = doc["data"]
    assert len(rows) == 320
    periods = [r["period"] for r in rows]
    assert periods == expected_months("2000-01", "2026-08")
    assert all(p >= "2000-01" for p in periods)
    # GOLD-03: raw gold_eur_oz stays null; the two derived indicators are published (see GOLD_03_RELEASE_NOTES.md).
    for r in rows:
        assert r["gold_eur_oz"] is None, r["period"]
        for f in ("gold_index", "gold_grams_per_house"):
            assert isinstance(r[f], float) and r[f] > 0, (r["period"], f)


def test_public_csv_contract():
    with PUBLIC_CSV.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows and list(rows[0]) == ["date", "series", "value"]
    dates = sorted({r["date"] for r in rows})
    assert len(dates) == 320 and dates[0] == "2000-01"
    assert {r["series"] for r in rows} == {"nl_hpi", "nl_house_avg_eur"}


# (d) hist tools never write to public data ---------------------------------------
FORBIDDEN_LITERALS = re.compile(r"frontend/public|cbs-housing\.csv|monthly\.json|(^|/)data/(?!fixtures)")


def _write_calls(tree):
    """Yield (call node, target expression) for every file-writing call."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if name in ("write_text", "write_bytes"):
            yield node, (fn.value if isinstance(fn, ast.Attribute) else None)
        elif name == "open":
            args = node.args if isinstance(fn, ast.Attribute) else node.args[1:]
            mode = args[0].value if args and isinstance(args[0], ast.Constant) else None
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = kw.value.value
            if isinstance(mode, str) and set(mode) & set("wax+"):
                yield node, (fn.value if isinstance(fn, ast.Attribute) else node.args[0])


@pytest.mark.parametrize("path", HIST_TOOLS, ids=lambda p: p.name)
def test_hist_tools_never_write_public_paths(path):
    tree = _tree(path)
    literals = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    # Remote source URLs (e.g. an API path containing /data/) are not repository paths; the
    # write-target check below still scans ALL literals, including https:// ones.
    assert not [s for s in literals if not s.startswith("https://") and FORBIDDEN_LITERALS.search(s)], "hist tool names a public data path"
    for call, target in _write_calls(tree):
        for sub in (ast.walk(target) if target is not None else []):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                assert not FORBIDDEN_LITERALS.search(sub.value), f"{path.name}:{call.lineno}"
    src = path.read_text(encoding="utf-8")
    assert not re.search(r"shutil\.(copy|move)|os\.(replace|rename)|git\s+(add|commit|push)", src)


def test_write_detector_catches_violations():
    t = ast.parse("open('data/cbs-housing.csv','w')\nPath('x').write_text('a')\np.open('wb')\nopen('r.csv')")
    assert len(list(_write_calls(t))) == 3
    assert FORBIDDEN_LITERALS.search("frontend/public/data/monthly.json")
    assert FORBIDDEN_LITERALS.search("data/cbs-housing.csv")
    # writes to a repo path and to an https URL target are still detected as write calls
    t2 = ast.parse("open('data/x.csv','w')\nopen('https://example.org/service/data/x','w')")
    targets = [tg.value for _, tg in _write_calls(t2)]
    assert targets == ["data/x.csv", "https://example.org/service/data/x"]
    assert FORBIDDEN_LITERALS.search(targets[0]) and FORBIDDEN_LITERALS.search(targets[1])


# (e) canonical series hash ---------------------------------------------------------
def _series(n=12):
    months = expected_months("1975-01", "1975-12")[:n]
    return months, {m: Decimal("100") + Decimal(i) for i, m in enumerate(months)}


def test_canonical_sha_deterministic_and_order_independent():
    months, s = _series()
    ref = canonical_sha256(s, months)
    assert len(ref) == 64 and ref == canonical_sha256(dict(s), list(months))
    items = list(s.items())
    random.Random(7).shuffle(items)
    assert canonical_sha256(dict(items), months) == ref


def test_canonical_sha_changes_with_value_or_month():
    months, s = _series()
    ref = canonical_sha256(s, months)
    s2 = dict(s)
    s2["1975-06"] += Decimal("1")
    assert canonical_sha256(s2, months) != ref
    assert canonical_sha256({**s, "1975-06": Decimal("105.0")}, months) != canonical_sha256({**s, "1975-06": Decimal("105")}, months)
    shifted = {m.replace("1975", "1976"): v for m, v in s.items()}
    assert canonical_sha256(shifted, sorted(shifted)) != ref
    assert canonical_sha256(s, months[:-1]) != ref


def test_canonical_sha_missing_month_fails_closed():
    months, s = _series()
    del s["1975-03"]
    with pytest.raises(KeyError):
        canonical_sha256(s, months)


# (g) precision: Decimal text stays exact ---------------------------------------------
def test_canonical_representation_is_exact():
    months = ["1975-01", "1975-02", "1975-03"]
    s = {"1975-01": Decimal("1234567890.123456789012345678"), "1975-02": Decimal("0.1"), "1975-03": Decimal("100")}
    expected = "1975-01,1234567890.123456789012345678\n1975-02,0.1\n1975-03,100\n"
    assert canonical_sha256(s, months) == hashlib.sha256(expected.encode()).hexdigest()


# workbook helpers (self-contained) -----------------------------------------------------
def _xlsx(rows, sheet="Monthly Prices"):
    xml_rows = []
    for r, row in enumerate(rows, 1):
        cells = ""
        for c, v in enumerate(row):
            if v is None:
                continue
            ref = f"{'ABCDEFGH'[c]}{r}"
            if isinstance(v, str):
                cells += f'<c r="{ref}" t="inlineStr"><is><t>{escape(v)}</t></is></c>'
            else:
                cells += f'<c r="{ref}"><v>{v}</v></c>'
        xml_rows.append(f'<row r="{r}">{cells}</row>')
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets><sheet name="{sheet}" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{ns}"><sheetData>{"".join(xml_rows)}</sheetData></worksheet>')
    return buf.getvalue()


def _book(skip=(), dup=None, two_gold=False, values=None, order=None):
    head = ["", "Crude", "Gold"] + (["Gold"] if two_gold else [])
    unit = [None, "($/bbl)", "($/troy oz)"] + (["($/troy oz)"] if two_gold else [])
    body = []
    for p in expected_months("1974-12", "2000-01"):
        if p in skip:
            continue
        v = (values or {}).get(p, 100.5)
        row = [f"{p[:4]}M{p[5:]}", 1.0, v] + ([v] if two_gold else [])
        body.append(row)
        if p == dup:
            body.append(list(row))
    if order:
        random.Random(order).shuffle(body)
    return _xlsx([["Title"], head, unit] + body)


def test_synthetic_baseline_validates_and_is_row_order_independent():
    a = validate(_book())
    b = validate(_book(order=3))
    assert a["status"] == "VALIDATED" and a["count_in_range"] == 300
    assert a["canonical_series_sha256"] == b["canonical_series_sha256"]


# (f) validator fails closed -------------------------------------------------------------
def test_validator_299_months_fails():
    s = validate(_book(skip={"1999-12"}))
    assert s["status"] == "FAILED" and s["count_in_range"] == 299 and "MISSING_MONTHS" in s["problems"]
    assert "canonical_series_sha256" not in s


def test_validator_missing_middle_month_fails():
    s = validate(_book(skip={"1987-06"}))
    assert s["status"] == "FAILED" and s["missing_months"] == ["1987-06"]
    assert "canonical_series_sha256" not in s


def test_validator_duplicate_fails():
    s = validate(_book(dup="1990-03"))
    assert s["status"] == "FAILED" and "DUPLICATE_MONTHS" in s["problems"]
    assert "canonical_series_sha256" not in s


def test_validator_two_gold_columns_raises():
    with pytest.raises(ValidationError, match="AMBIGUOUS_GOLD_COLUMN"):
        validate(_book(two_gold=True))


def test_validator_nonpositive_value_fails():
    s = validate(_book(values={"1980-01": 0}))
    assert s["status"] == "FAILED" and "INVALID_VALUES" in s["problems"]


def test_validator_never_authorizes_publication():
    s = validate(_book())
    assert s["publication_authorized"] is False and s["rights_status"] == "UNVERIFIED"


# (g) precision through the full parse path ---------------------------------------------------
def test_decimals_survive_parse_without_rounding():
    vals = {"1975-01": "1234.5678901234", "1975-02": "0.1", "1975-03": "300"}
    s = validate(_book(values=vals))
    assert s["status"] == "VALIDATED"
    assert s["non_integer_count_in_range"] >= 2
    assert s["decimal_places_histogram"]["in_range"].get("10") == 1
    assert s["max"] == "1234.5678901234"
