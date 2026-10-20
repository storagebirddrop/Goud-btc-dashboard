from unittest.mock import Mock, patch

from etl.coinmetrics_catalog import main


def test_catalog_requests_omit_unsupported_assets_parameter(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    response = Mock()
    response.ok = True
    response.json.return_value = {"data": []}
    with patch("etl.coinmetrics_catalog.requests.get", return_value=response) as get:
        try:
            main()
        except ValueError as exc:
            assert "unavailable" in str(exc)
        else:
            raise AssertionError("Empty catalog must not pass")
    assert get.call_count == 2
    for call in get.call_args_list:
        assert "assets" not in call.kwargs["params"]
        assert call.kwargs["params"]["metrics"] in ("ReferenceRateEUR", "ReferenceRateUSD")
