import unittest
from decimal import Decimal as D
from etl.gold_monthly import build_candidate
from etl.static_export import build
class GoldPublicationGateTests(unittest.TestCase):
    def test_gold_publication_blocked(self):
        self.assertTrue(all(row["gold_index"] is None for row in build("data/cbs-housing.csv",gold_candidate={"data":[]})["data"]))
    def test_explicit_flag_does_not_bypass_review(self):
        self.assertTrue(all(row["gold_index"] is None for row in build("data/cbs-housing.csv",gold_publication_approved=True)["data"]))
    def test_candidate_rejects_historic_gap(self):
        with self.assertRaisesRegex(ValueError,"Historical source month gap"):
            build_candidate({"2000-01":D(100),"2000-03":D(120)},{"2000-01":D(1),"2000-02":D(1),"2000-03":D(1)},{"2000-01":D(1000),"2000-02":D(1000),"2000-03":D(1000)},{"2000-01":1,"2000-02":1,"2000-03":1})
    def test_candidate_preserves_trailing_publication_lag(self):
        c=build_candidate({"2000-01":D(100),"2000-02":D(120)},{"2000-01":D(1),"2000-02":D(1)},{"2000-01":D(1000)},{"2000-01":1,"2000-02":1})
        self.assertEqual(len(c["data"]),1)
        self.assertEqual(c["coverage"][-1]["status"],"pending_publication")
        self.assertFalse(c["publication_authorized"])
