import unittest
from decimal import Decimal as D

from tools import hist_04_fx as fx

FED = (b'"Series Description","Netherlands -- Spot Exchange rate, guilder/US$"\n"Unit:","Currency:_Per_US$"\n'
       b'"Multiplier:","1"\n"Currency:","NLG"\n"Unique Identifier:","G5/G5/RXI_N.B.NL"\n'
       b'"Time Period","RXI_N.B.NL"\n"1998-12-28","1.8800"\n"1998-12-29","ND"\n"1998-12-30","1.9000"\n')
ECB = (b"KEY,FREQ,CURRENCY,CURRENCY_DENOM,TIME_PERIOD,OBS_VALUE,OBS_STATUS\n"
       b"EXR.D.USD.EUR.SP00.A,D,USD,EUR,1999-01-04,1.1789,A\nEXR.D.USD.EUR.SP00.A,D,USD,EUR,1999-01-05,1.1790,A\n")


class Hist04FxTests(unittest.TestCase):
    def test_fed_parse_nd_stays_absent(self):
        p = fx.parse_fed_g5(FED, "D")
        self.assertEqual(p["nd"], 1)
        self.assertEqual(sorted(p["points"]), ["1998-12-28", "1998-12-30"])
        self.assertNotIn("1998-12-29", p["points"])
        fx.assert_fed_nlg_direction(p["meta"])

    def test_fed_direction_and_multiplier_fail_closed(self):
        with self.assertRaises(fx.FxError):
            fx.assert_fed_nlg_direction({"Currency": "NLG", "Unit": "Currency:_Per_NLG"})
        with self.assertRaises(fx.FxError):
            fx.assert_fed_nlg_direction({"Currency": "NLG", "Unit": "Per_US$", "Multiplier": "100"})
        with self.assertRaises(fx.FxError):
            fx.assert_fed_nlg_direction({"Currency": "EUR", "Unit": "Per_US$"})

    def test_fed_fail_closed(self):
        for bad in (b'"Time Period","X"\n"1998-12-28","1.9"\n"1998-12-28","1.8"\n',
                    b'"Time Period","X"\n"1998-12-28","ND"\n"1998-12-28","1.8"\n',
                    b'"Time Period","X"\n"1998-12-28","abc"\n', b'"Time Period","X"\n"1998-12-28","-1"\n',
                    b'"Time Period","X"\n"98-12-28","1.9"\n', b'"Time Period","X"\n"1998-12-28","ND"\n',
                    b'"a","b"\n"1998-12-28","1.9"\n', b'"Time Period","X"\n"1998-12-28","1.9","x"\n'):
            with self.assertRaises(fx.FxError, msg=bad):
                fx.parse_fed_g5(bad, "D")

    def test_ecb_parse_and_failures(self):
        p = fx.parse_ecb_csv(ECB, "D")
        self.assertEqual(p["points"]["1999-01-04"], D("1.1789"))
        with self.assertRaises(fx.FxError):
            fx.parse_ecb_csv(ECB.replace(b",USD,EUR,", b",EUR,USD,"), "D")
        with self.assertRaises(fx.FxError):
            fx.parse_ecb_csv(ECB + b"EXR.D.USD.EUR.SP00.A,D,USD,EUR,1999-01-04,1.1,A\n", "D")
        with self.assertRaises(fx.FxError):
            fx.parse_ecb_csv(b"A,B\n1,2\n", "D")
        with self.assertRaises(fx.FxError):
            fx.parse_ecb_csv(ECB.replace(b"1.1789", b"x"), "D")

    def test_decimal_exact_chain(self):
        self.assertEqual(fx.gold_nlg_per_oz(D("400"), D("1.9")), D("760.0"))
        self.assertEqual(fx.gold_eur_per_oz(D("400"), D("1.25")), D("320"))
        self.assertEqual(fx.nlg_to_eur(D("2.20371")), D("1"))
        self.assertEqual(fx.implied_usd_per_eur(D("2.20371")), D("1"))
        self.assertEqual(fx.implied_usd_per_eur(D("1.9")), D("1.159847368421052631578947368421053"))

    def test_direction_matters_not_symmetric(self):
        # multiplying USD/oz by USD_PER_EUR would be a direction error; show it differs materially
        self.assertNotEqual(fx.gold_eur_per_oz(D("400"), D("1.2")), D("400") * D("1.2"))

    def test_monthly_mean_of_quoted_direction_and_jensen(self):
        s = fx.monthly_stats({"1999-01-04": D("1.0"), "1999-01-05": D("2.0"), "1999-02-01": D("1.5")})
        self.assertEqual(s["1999-01"]["n"], 2)
        self.assertEqual(s["1999-01"]["mean"], D("1.5"))
        self.assertEqual(s["1999-01"]["mean_of_reciprocals"], D("0.75"))
        self.assertAlmostEqual(float(s["1999-01"]["reciprocal_of_mean"]), 2 / 3, places=12)
        self.assertGreater(s["1999-01"]["jensen_gap_rel"], 0)
        self.assertEqual(s["1999-02"]["jensen_gap_rel"], 0)
        j = fx.jensen_summary(s)
        self.assertTrue(j["all_non_negative"])
        self.assertEqual(j["max_gap_month"], "1999-01")

    def test_coverage_lists_gaps_without_filling(self):
        c = fx.coverage(["1998-10", "1998-12"])
        self.assertEqual(c["missing_months"], ["1998-11"])
        self.assertEqual(c["present"], 2)

    def test_transition_no_overlap_and_overlap(self):
        t = fx.transition_report({"1998-12-30": D("1.9")}, {"1999-01-04": D("1.1789")})
        self.assertEqual(t["overlap_days"], 0)
        self.assertEqual(t["fed_last_day"], "1998-12-30")
        t = fx.transition_report({"1999-01-04": D("1.869")}, {"1999-01-04": D("1.1789")})
        self.assertEqual(t["overlap_days"], 1)
        self.assertIn("overlap_max_rel_dev", t)

    def test_provider_vs_own(self):
        own = fx.monthly_stats({"1999-01-04": D("1.0"), "1999-01-05": D("2.0")})
        r = fx.provider_vs_own({"1999-01": D("1.5"), "1999-02": D("1.0")}, own)
        self.assertEqual(r["common_months"], 1)
        self.assertEqual(r["months_dev_gt_1e-4"], 0)

    def test_discovery_requires_netherlands_context(self):
        h1, h2 = "a" * 32, "b" * 32
        html = f'<a href="x?series={h1}">Netherlands -- Spot Exchange rate</a> <a href="x?series={h2}">Japan</a>'
        self.assertEqual([h for h, _ in fx.discover_series(html, width=60)], [h1])

    def test_extract_links_filters_and_dedupes(self):
        html = '<a href="/datadownload/Choose.aspx?rel=G5">a</a><a href="/about.htm">b</a><a href="/datadownload/Choose.aspx?rel=G5">c</a>'
        self.assertEqual(fx.extract_links(html), ["/datadownload/Choose.aspx?rel=G5"])

    def test_url_allowlist_registered(self):
        from tools import hist_02_acquire as a
        self.assertIn(fx.ECB_DAILY, a.SOURCES)
        with self.assertRaises(a.AcquisitionError):
            a.validate_url(fx.ECB_DAILY, "https://example.com/EXR/D.USD.EUR.SP00.A?format=csvdata")


if __name__ == "__main__":
    unittest.main()
