from scripts.check_governance_docs import check


def test_governance_inventory_and_links():
    assert check() == []
