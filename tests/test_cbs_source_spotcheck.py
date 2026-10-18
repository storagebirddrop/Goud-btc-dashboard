import pytest
from etl.cbs_source_spotcheck import compare_samples, read_committed, fetch_live_samples


def test_matching_independent_source_samples():
    committed = {("2000-01", "nl_hpi"): 80.0,
                 ("2000-01", "nl_house_avg_eur"): 150000.0}
    live = [("2000-01", "nl_hpi", 80.0),
            ("2000-01", "nl_house_avg_eur", 150000.0)]
    assert [r["status"] for r in compare_samples(committed, live, ("2000-01",))] == ["MATCH", "MATCH"]


def test_revision_and_missing_data_are_reported_without_imputation():
    committed = {("2000-01", "nl_hpi"): 80.0,
                 ("2000-01", "nl_house_avg_eur"): 150000.0}
    live = [("2000-01", "nl_hpi", 81.0)]
    assert [r["status"] for r in compare_samples(committed, live, ("2000-01",))] == ["DIFF", "MISSING_LIVE"]


@pytest.mark.parametrize("row", ["2000-01,nl_hpi,80,extra", "2000-01,nl_hpi", "2000-01,nl_hpi,80,"])
def test_bad_csv_row_shape_fails_closed(tmp_path, row):
    path = tmp_path / "source.csv"
    path.write_text("date,series,value\n" + row + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed"):
        read_committed(path)


def test_duplicate_committed_observation_rejected(tmp_path):
    path = tmp_path / "source.csv"
    path.write_text("date,series,value\n2000-01,nl_hpi,80\n2000-01,nl_hpi,81\n")
    with pytest.raises(ValueError, match="Duplicate"):
        read_committed(path)
