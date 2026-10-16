"""Live CBS contract checks. Run only in dedicated network-enabled CI workflow."""
import re
import requests
from etl.sources.cbs import BASE, resolve_fields, parse_rows

def get_json(endpoint, params=None):
    response = requests.get(
        f"{BASE}/{endpoint}", params=params,
        headers={"Accept": "application/json"}, timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    assert isinstance(body.get("value"), list), "CBS response missing OData value array"
    return body["value"]

def test_live_metadata_fields():
    fields = resolve_fields(get_json("DataProperties"))
    assert set(fields) == {"nl_hpi", "nl_house_avg_eur"}
    assert all(re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", key) for key in fields.values())

def test_live_monthly_2000_contract():
    fields = resolve_fields(get_json("DataProperties"))
    rows = get_json("TypedDataSet", {
        "$filter": "Perioden ge '2000MM01' and Perioden le '2000MM12'",
        "$top": "30",
    })
    assert rows, "CBS returned no rows for 2000"
    observations = parse_rows(rows, fields)
    assert ("2000-01", "nl_hpi") in {(d, s) for d, s, _ in observations}
    assert ("2000-01", "nl_house_avg_eur") in {(d, s) for d, s, _ in observations}
    assert len(observations) >= 24, "Expected both series for all twelve months in 2000"
