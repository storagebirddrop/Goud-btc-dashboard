import csv
import json

import pytest

from etl.data_quality import validate
from etl.static_export import build


def make_data(tmp_path):
    source = tmp_path / "housing.csv"
    with source.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "series", "value"])
        writer.writerows([
            ["2000-01", "nl_hpi", "50"],
            ["2000-01", "nl_house_avg_eur", "100000"],
            ["2000-02", "nl_hpi", "55"],
            ["2000-02", "nl_house_avg_eur", "105000"],
        ])
    target = tmp_path / "monthly.json"
    target.write_text(json.dumps(build(source)), encoding="utf-8")
    return source, target


def test_valid_source_matches_published_json(tmp_path):
    assert validate(*make_data(tmp_path)) == 2


@pytest.mark.parametrize("mutate", [
    lambda p: p["data"][0].update({"house_eur": 999999}),
    lambda p: p["data"][1].update({"hpi_index": 999}),
    lambda p: p["data"].pop(),
    lambda p: p["data"].append(dict(p["data"][-1])),
    lambda p: p["data"][0].update({"gold_eur_oz": 500}),
    lambda p: p.update({"unreviewed": True}),
])
def test_rejects_tampered_published_data(tmp_path, mutate):
    source, target = make_data(tmp_path)
    payload = json.loads(target.read_text())
    mutate(payload)
    target.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        validate(source, target)


def test_rejects_nonfinite_json(tmp_path):
    source, target = make_data(tmp_path)
    target.write_text(target.read_text().replace("100000.0", "NaN"))
    with pytest.raises(ValueError):
        validate(source, target)


def test_rejects_missing_month_in_source(tmp_path):
    source, target = make_data(tmp_path)
    source.write_text(source.read_text().replace("2000-02", "2000-03"))
    with pytest.raises(ValueError, match="Gaps"):
        validate(source, target)


def test_rejects_duplicate_observation_in_source(tmp_path):
    source, target = make_data(tmp_path)
    with source.open("a", encoding="utf-8") as f:
        f.write("2000-01,nl_hpi,50\\n".replace("\\n", "\n"))
    with pytest.raises(ValueError, match="Duplicate"):
        validate(source, target)
