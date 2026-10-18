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
    assert [r["status"] for r in compare_samples(committed, live, ("2000-01",))] == ["VALUE_DIFFERENCE", "MISSING_LIVE"]


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


def test_complete_history_and_missing_month():
    from etl.cbs_source_spotcheck import compare_history
    committed = {("2000-01", "nl_hpi"): 80., ("2000-01", "nl_house_avg_eur"): 150000.,
                 ("2000-03", "nl_hpi"): 81., ("2000-03", "nl_house_avg_eur"): 151000.}
    live = [(m, s, v) for (m, s), v in committed.items()]
    result = compare_history(committed, live, "2000-01", "2000-03")
    assert result["checked_months"] == 3
    assert result["checked_observations"] == 6
    assert result["counts"]["MISSING_COMMITTED"] == 2
    assert result["complete"] is False


def test_rounding_difference_is_not_confirmed_revision():
    from etl.cbs_source_spotcheck import compare_history
    stored = {("2000-01", "nl_hpi"): 80., ("2000-01", "nl_house_avg_eur"): 150000.}
    live = [("2000-01", "nl_hpi", 80.02),
            ("2000-01", "nl_house_avg_eur", 150001.)]
    result = compare_history(stored, live, "2000-01", "2000-01")
    assert result["counts"]["ROUNDING_DIFFERENCE"] == 1
    assert result["counts"]["VALUE_DIFFERENCE"] == 1
    assert all(not item["revision_confirmed"] for item in result["differences"])


def test_duplicate_live_observation_rejected():
    from etl.cbs_source_spotcheck import compare_history
    with pytest.raises(ValueError, match="Duplicate live"):
        compare_history({("2000-01", "nl_hpi"): 80.},
                        [("2000-01", "nl_hpi", 80.), ("2000-01", "nl_hpi", 80.)],
                        "2000-01", "2000-01")


def test_empty_live_source_fails_closed():
    from etl.cbs_source_spotcheck import compare_history
    with pytest.raises(ValueError, match="no observations"):
        compare_history({("2000-01", "nl_hpi"): 80.}, [], "2000-01", "2000-01")


def test_coverage_month_order_and_gaps():
    from etl.cbs_source_spotcheck import inspect_coverage, month_range
    assert month_range("2000-12", "2001-02") == ["2000-12", "2001-01", "2001-02"]
    result = inspect_coverage({("2000-01", "nl_hpi"): 80.}, "2000-01", "2000-02")
    assert len(result["missing"]) == 3


def test_out_of_order_committed_rows_rejected(tmp_path):
    path = tmp_path / "source.csv"
    path.write_text("date,series,value\n2000-02,nl_hpi,81\n2000-01,nl_hpi,80\n")
    with pytest.raises(ValueError, match="Non-chronological"):
        read_committed(path)
