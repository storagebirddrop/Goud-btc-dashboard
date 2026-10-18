import csv
import json
from pathlib import Path
import pytest
from etl.static_export import build

ROWS = [
    ["2000-01", "nl_hpi", "80"],
    ["2000-01", "nl_house_avg_eur", "150000"],
    ["2000-02", "nl_hpi", "88"],
    ["2000-02", "nl_house_avg_eur", "155000"],
]

def fixture(tmp_path, rows=ROWS):
    p = tmp_path / "history.csv"
    with p.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "series", "value"])
        writer.writerows(rows)
    return p

def test_export_shape_and_index(tmp_path):
    result = build(fixture(tmp_path))
    assert [r["period"] for r in result["data"]] == ["2000-01", "2000-02"]
    assert [r["hpi_index"] for r in result["data"]] == [100, 110]
    assert result["data"][0]["house_eur"] == 150000
    assert result["data"][0]["gold_eur_oz"] is None
    json.dumps(result, allow_nan=False)

@pytest.mark.parametrize("rows", [
    ROWS[:-1],
    ROWS + [ROWS[0]],
    ROWS[:2] + [["2000-03", "nl_hpi", "90"], ["2000-03", "nl_house_avg_eur", "160000"]],
    ROWS[:1] + [["2000-01", "nl_house_avg_eur", "nan"]] + ROWS[2:],
    ROWS[:1] + [["2000-01", "gold_eur_oz", "300"]] + ROWS[1:],
])
def test_rejects_invalid_history(tmp_path, rows):
    with pytest.raises(ValueError):
        build(fixture(tmp_path, rows))


@pytest.mark.parametrize("bad_row", [
    "2000-02,nl_hpi,88,unexpected",
    "2000-02,nl_hpi",
    "2000-02,nl_hpi,88,",
])
def test_rejects_malformed_csv_row_width(tmp_path, bad_row):
    source = fixture(tmp_path)
    original = source.read_text(encoding="utf-8")
    source.write_text(original.replace("2000-02,nl_hpi,88", bad_row), encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed CSV row"):
        build(source)
