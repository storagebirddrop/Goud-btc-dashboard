import unittest
from decimal import Decimal as D
from poc.gold_monthly_integration import parse_ecb,parse_housing,compute,GRAMS,classify_coverage
class GoldMonthlyTests(unittest.TestCase):
    def test_fx_direction_and_mean(self):
        raw=b"TIME_PERIOD,OBS_VALUE,CURRENCY,CURRENCY_DENOM\n2000-01-03,1.1,USD,EUR\n2000-01-04,1.3,USD,EUR\n"
        fx,counts,n=parse_ecb(raw)
        self.assertEqual(fx["2000-01"],D("1.2"))
        self.assertEqual(counts["2000-01"],2)
        self.assertEqual(n,2)
        result=compute({"2000-01":D("120")},fx,{"2000-01":D("1000")},counts)
        self.assertEqual(D(result[0]["gold_eur_oz"]),D("100"))
        self.assertEqual(D(result[0]["gold_index"]),D("100"))
    def test_wrong_fx_direction(self):
        with self.assertRaises(ValueError):
            parse_ecb(b"TIME_PERIOD,OBS_VALUE,CURRENCY,CURRENCY_DENOM\n2000-01-03,0.9,EUR,USD\n")
    def test_gram_and_house(self):
        out=compute({"2000-01":D("31.1034768")},{"2000-01":D("1")},{"2000-01":D("100")},{"2000-01":1})
        self.assertEqual(D(out[0]["gold_eur_gram"]),D("1"))
        self.assertEqual(D(out[0]["gold_grams_per_house"]),D("100"))
    def test_partial_updates_exact_join(self):
        gold={"2000-01":D("100"),"2000-02":D("110"),"2000-03":D("120")}
        fx={"2000-01":D("1"),"2000-02":D("1")}
        homes={"2000-01":D("1000"),"2000-03":D("1100")}
        out=compute(gold,fx,homes,{"2000-01":20,"2000-02":20})
        self.assertEqual([r["month"] for r in out],["2000-01"])
    def test_missing_basis(self):
        with self.assertRaisesRegex(ValueError,"Incomplete"):
            compute({"2000-01":D("100")},{"2000-01":D("1")},{},{"2000-01":1})
    def test_duplicate_fx(self):
        with self.assertRaises(ValueError):
            parse_ecb(b"TIME_PERIOD,OBS_VALUE\n2000-01-03,1\n2000-01-03,1\n")
    def test_invalid_fx(self):
        with self.assertRaises(ValueError):
            parse_ecb(b"TIME_PERIOD,OBS_VALUE\n2000-01-03,-1\n")
    def test_duplicate_cbs(self):
        with self.assertRaises(ValueError):
            parse_housing(b"date,series,value\n2000-01,nl_house_avg_eur,100\n2000-01,nl_house_avg_eur,101\n")
    def test_invalid_cbs(self):
        with self.assertRaises(ValueError):
            parse_housing(b"date,series,value\n2000-01,nl_house_avg_eur,NaN\n")
    def test_index_ratio(self):
        out=compute({"2000-01":D("100"),"2000-02":D("200")},{"2000-01":D("1"),"2000-02":D("2")},{"2000-01":D("1000"),"2000-02":D("1000")},{"2000-01":1,"2000-02":1})
        self.assertEqual(D(out[1]["gold_index"]),D("100"))
    def test_historical_gap_not_silently_dropped(self):
        g={"2000-01":D("100"),"2000-03":D("120")}
        f={"2000-01":D("1"),"2000-02":D("1"),"2000-03":D("1")}
        h={"2000-01":D("1000"),"2000-02":D("1000"),"2000-03":D("1000")}
        c=classify_coverage(g,f,h)
        self.assertEqual(c[1]["month"],"2000-02")
        self.assertEqual(c[1]["status"],"missing_historical")
        self.assertEqual(c[1]["missing_historical"],["worldbank"])
    def test_different_publication_dates(self):
        g={"2000-01":D("100"),"2000-02":D("110"),"2000-03":D("120")}
        f={"2000-01":D("1"),"2000-02":D("1"),"2000-03":D("1")}
        h={"2000-01":D("1000"),"2000-02":D("1000")}
        c=classify_coverage(g,f,h)
        self.assertEqual(c[-1]["status"],"pending_publication")
        self.assertEqual(c[-1]["pending_publication"],["cbs"])
    def test_mixed_historic_gap_and_lag(self):
        g={"2000-01":D("100"),"2000-03":D("120")}
        f={"2000-01":D("1"),"2000-02":D("1"),"2000-03":D("1")}
        h={"2000-01":D("1000"),"2000-02":D("1000")}
        c=classify_coverage(g,f,h)
        self.assertEqual(c[1]["status"],"missing_historical")
        self.assertEqual(c[2]["status"],"pending_publication")
if __name__=="__main__":unittest.main()
