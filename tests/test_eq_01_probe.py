import json
import unittest
from decimal import Decimal as D

from tools import eq_01_probe as eq


def S(name, kind, rt, freq, pts, cur="USD", basis="month_end", base=None):
    return eq.make_series(name, kind, rt, cur, freq, basis, [(p, D(str(v))) for p, v in pts], base)


EQ = [("2000-01", 100), ("2000-02", 110), ("2000-03", 121), ("2000-04", 100)]
HS = [("2000-01", 50), ("2000-02", 50), ("2000-03", 55), ("2000-04", 60)]


def hpi(pts=HS):
    return S("h", "housing", "housing_hpi", "monthly", pts, cur="idx", basis="n/a")


class Rebase(unittest.TestCase):
    def test_rebase_to_100_and_independent_formula(self):
        rel = eq.relative_to_housing(S("e", "equity", "price", "monthly", EQ), hpi(), "2000-02")
        got = dict(rel.points)
        for (p, ev), (_, hv) in zip(EQ, HS):  # independent: (e_t/e_base) / (h_t/h_base) * 100
            exp = (D(ev) / D(110)) / (D(hv) / D(50)) * 100
            self.assertEqual(got[p].quantize(D("1E-20")), exp.quantize(D("1E-20")))
        self.assertEqual(got["2000-02"], D(100))
        self.assertEqual(rel.index_base, "2000-02")

    def test_default_baseline_is_earliest_common(self):
        e = S("e", "equity", "price", "monthly", EQ[1:])
        self.assertEqual(eq.common_baseline([e, hpi()]), "2000-02")
        self.assertEqual(eq.relative_to_housing(e, hpi()).index_base, "2000-02")

    def test_base_period_must_exist_no_nearest(self):
        e = S("e", "equity", "price", "monthly", [("2000-01", 1), ("2000-03", 2)])
        with self.assertRaises(eq.EquityMethodError):
            eq.rebase(e, "2000-02")

    def test_double_rebase_rejected(self):
        e = eq.rebase(S("e", "equity", "price", "monthly", EQ), "2000-01")
        with self.assertRaises(eq.EquityMethodError):
            eq.rebase(e, "2000-02")

    def test_missing_period_is_not_filled(self):
        e = S("e", "equity", "price", "monthly", [("2000-01", 100), ("2000-03", 121)])
        rel = eq.relative_to_housing(e, hpi(), "2000-01")
        self.assertEqual([p for p, _ in rel.points], ["2000-01", "2000-03"])


class Negative(unittest.TestCase):
    def setUp(self):
        self.e = S("e", "equity", "price", "monthly", EQ)
        self.h = hpi()

    def test_different_base_dates_rejected(self):
        with self.assertRaisesRegex(eq.EquityMethodError, "DIFFERENT_BASE_DATES"):
            eq.relative_performance(eq.rebase(self.e, "2000-01"), eq.rebase(self.h, "2000-02"))

    def test_not_rebased_rejected(self):
        with self.assertRaisesRegex(eq.EquityMethodError, "NOT_REBASED"):
            eq.relative_performance(self.e, self.h)

    def test_price_vs_total_return_mixing_rejected(self):
        tr = S("tr", "equity", "total_gross", "monthly", EQ)
        with self.assertRaisesRegex(eq.EquityMethodError, "RETURN_TYPE_MIXING"):
            eq.relative_performance(eq.rebase(self.e, "2000-01"), eq.rebase(tr, "2000-01"))
        net = S("n", "equity", "total_net", "monthly", EQ)
        with self.assertRaises(eq.EquityMethodError):
            eq.relative_performance(eq.rebase(tr, "2000-01"), eq.rebase(net, "2000-01"))

    def test_currency_mixing_rejected(self):
        eur = S("e2", "equity", "price", "monthly", EQ, cur="EUR")
        with self.assertRaisesRegex(eq.EquityMethodError, "CURRENCY_MIXING"):
            eq.relative_performance(eq.rebase(self.e, "2000-01"), eq.rebase(eur, "2000-01"))

    def test_avg_price_vs_hpi_mixing_rejected(self):
        avg = S("avg", "housing", "housing_avg_price", "monthly", HS, cur="EUR", basis="n/a")
        with self.assertRaisesRegex(eq.EquityMethodError, "HOUSING_DEFINITION_MIXING"):
            eq.relative_performance(eq.rebase(avg, "2000-01"), eq.rebase(self.h, "2000-01"))

    def test_non_overlapping_ranges_rejected(self):
        late = S("late", "equity", "price", "monthly", [("2010-01", 1), ("2010-02", 2)])
        with self.assertRaisesRegex(eq.EquityMethodError, "NON_OVERLAPPING_RANGES"):
            eq.overlap_range(late, self.h)
        with self.assertRaisesRegex(eq.EquityMethodError, "NO_COMMON_OBSERVATION"):
            eq.common_baseline([late, self.h])

    def test_interleaved_ranges_without_common_observation_rejected(self):
        a = S("a", "equity", "price", "monthly", [("2000-01", 1), ("2000-03", 2)])
        b = hpi([("2000-02", 1), ("2000-04", 2)])
        self.assertEqual(eq.overlap_range(a, b), ("2000-02", "2000-03"))
        with self.assertRaises(eq.EquityMethodError):
            eq.common_baseline([a, b])

    def test_unordered_and_duplicate_periods(self):
        with self.assertRaisesRegex(eq.EquityMethodError, "UNORDERED_PERIOD"):
            S("x", "equity", "price", "monthly", [("2000-02", 1), ("2000-01", 1)])
        with self.assertRaisesRegex(eq.EquityMethodError, "DUPLICATE_PERIOD"):
            S("x", "equity", "price", "monthly", [("2000-01", 1), ("2000-01", 2)])

    def test_non_positive_and_bad_period_format(self):
        for bad in (0, -1):
            with self.assertRaises(eq.EquityMethodError):
                S("x", "equity", "price", "monthly", [("2000-01", bad)])
        with self.assertRaises(eq.EquityMethodError):
            eq.make_series("x", "equity", "price", "USD", "monthly", "close", [("2000-01", D("NaN"))])
        with self.assertRaises(eq.EquityMethodError):
            S("x", "equity", "price", "monthly", [("2000", 1)])

    def test_annual_to_monthly_forbidden(self):
        a = S("a", "housing", "housing_avg_price", "annual", [("2000", 1), ("2001", 2)], cur="EUR", basis="annual")
        with self.assertRaisesRegex(eq.EquityMethodError, "ANNUAL_TO_MONTHLY_FORBIDDEN"):
            eq.annual_to_monthly(a)
        with self.assertRaisesRegex(eq.EquityMethodError, "FREQUENCY_MISMATCH"):
            eq.common_baseline([a, self.e])
        with self.assertRaises(eq.EquityMethodError):
            eq.monthly_from_daily(a, "month_end")

    def test_splice_forbidden(self):
        with self.assertRaisesRegex(eq.EquityMethodError, "SPLICE_NOT_ALLOWED"):
            eq.chain(self.e, self.e)

    def test_valuation_ratio_with_index_points_forbidden(self):
        with self.assertRaisesRegex(eq.EquityMethodError, "INDEX_POINTS_ARE_NOT_PURCHASABLE_UNITS"):
            eq.houses_per_unit(D(400000), D(1500), "index_points")
        with self.assertRaises(eq.EquityMethodError):
            eq.houses_per_unit(D(400000), D(100), "investable_proxy")  # no proxy named
        self.assertEqual(eq.houses_per_unit(D(400000), D(100), "investable_proxy", "TR tracker"), D(4000))


class DailyToMonthlyAndFx(unittest.TestCase):
    DAILY = [("2000-01-03", 10), ("2000-01-31", 14), ("2000-03-01", 20), ("2000-03-02", 22)]

    def test_month_end_and_avg_no_fill(self):
        d = S("d", "equity", "price", "daily", self.DAILY, basis="close")
        me = eq.monthly_from_daily(d, "month_end")
        av = eq.monthly_from_daily(d, "month_avg")
        self.assertEqual(me.points, (("2000-01", D(14)), ("2000-03", D(22))))
        self.assertEqual(dict(av.points)["2000-01"], D(12))
        self.assertNotIn("2000-02", dict(me.points))
        self.assertEqual(eq.monthly_gaps([p for p, _ in me.points]), 1)

    def test_daily_input_must_be_daily_and_basis_known(self):
        with self.assertRaises(eq.EquityMethodError):
            eq.monthly_from_daily(S("m", "equity", "price", "monthly", EQ), "month_end")
        d = S("d", "equity", "price", "daily", self.DAILY, basis="close")
        with self.assertRaises(eq.EquityMethodError):
            eq.monthly_from_daily(d, "median")

    def test_to_eur_same_basis_and_no_carry_forward(self):
        usd = S("u", "equity", "price", "monthly", [("2000-01", 110), ("2000-02", 120)], basis="month_avg")
        fx = S("fx", "fx", "fx", "monthly", [("2000-01", "1.1")], cur="USD_PER_EUR", basis="month_avg")
        out = eq.to_eur(usd, fx)
        self.assertEqual(out.points, (("2000-01", D(100)),))
        self.assertEqual(out.currency, "EUR")
        fx_end = S("fx", "fx", "fx", "monthly", [("2000-01", "1.1")], cur="USD_PER_EUR", basis="month_end")
        with self.assertRaisesRegex(eq.EquityMethodError, "BASIS_MISMATCH"):
            eq.to_eur(usd, fx_end)
        wrong = S("fx", "fx", "fx", "monthly", [("2000-01", "0.9")], cur="EUR_PER_USD", basis="month_avg")
        with self.assertRaises(eq.EquityMethodError):
            eq.to_eur(usd, wrong)

    def test_hash_is_deterministic_and_value_sensitive(self):
        a = S("a", "equity", "price", "monthly", EQ)
        b = S("b", "equity", "price", "monthly", EQ)
        self.assertEqual(eq.series_sha256(a), eq.series_sha256(b))
        c = S("c", "equity", "price", "monthly", EQ[:-1] + [("2000-04", 101)])
        self.assertNotEqual(eq.series_sha256(a), eq.series_sha256(c))


class Parsers(unittest.TestCase):
    def test_stooq_csv_and_apikey_text_rejected(self):
        raw = b"Date,Open,High,Low,Close,Volume\n2000-01-03,1,2,0.5,1.5,0\n2000-01-04,1,2,0.5,N/D,0\n"
        pts, missing = eq.parse_csv_close(raw, ("date",), ("close",))
        self.assertEqual((pts, missing), ([("2000-01-03", D("1.5"))], 1))
        with self.assertRaises(eq.SourceFormatError):
            eq.parse_csv_close(b"Get your apikey:\n1. Open https://stooq.com\n", ("date",), ("close",))

    def test_fred_dot_marker_stays_absent(self):
        raw = b"observation_date,SP500\n2020-01-01,.\n2020-01-02,3257.85\n"
        pts, missing = eq.parse_csv_close(raw, ("date", "observation_date"), ("sp500",))
        self.assertEqual((len(pts), missing), (1, 1))

    def test_yahoo_chart_nulls_counted(self):
        doc = {"chart": {"result": [{"meta": {"currency": "USD"}, "timestamp": [946857600, 946944000],
                                     "indicators": {"quote": [{"close": [1469.25, None]}]}}]}}
        pts, missing, meta = eq.parse_yahoo_chart(json.dumps(doc).encode())
        self.assertEqual((pts, missing, meta["currency"]), ([("2000-01-03", D("1469.25"))], 1, "USD"))
        with self.assertRaises(eq.SourceFormatError):
            eq.parse_yahoo_chart(b"{}")

    def test_shiller_dates(self):
        pts, _ = eq.parse_shiller_rows([(1871.01, 4.44), (1871.1, 4.5), (1871.12, 4.6)])
        self.assertEqual([p for p, _ in pts], ["1871-01", "1871-10", "1871-12"])
        with self.assertRaises(eq.SourceFormatError):
            eq.parse_shiller_rows([(1871.13, 4.4)])

    def test_coverage_summary_flags_duplicates(self):
        s = eq.coverage_summary([("2000-01-03", D(1)), ("2000-01-03", D(2))], "daily")
        self.assertEqual(s["duplicates"], 1)
        self.assertNotIn("sha256", s)

    def test_quotes_limited_to_25_words(self):
        text = "Intro. " + " ".join(["word"] * 40) + " launched 1957 here. Other."
        q = eq.quotes(text, ["1957"])
        self.assertTrue(q["1957"])
        self.assertTrue(all(len(x.split()) <= 25 for x in q["1957"]))

    def test_unavailable_source_is_a_finding(self):
        def fetcher(_sid):
            raise ValueError("HTTP down")
        self.assertEqual(eq.probe_data("fred-sp500", fetcher, {})["status"], "UNAVAILABLE")
        self.assertEqual(eq.probe_doc("euronext-aex-factsheet", fetcher)["status"], "UNAVAILABLE")

    def test_candidates_registered_with_exact_urls_only(self):
        from tools import hist_02_acquire
        eq.register(hist_02_acquire)
        for sid in list(eq.DATA_CANDIDATES) + list(eq.DOC_CANDIDATES):
            self.assertIn(sid, hist_02_acquire.SOURCES)
            self.assertTrue(hist_02_acquire.SOURCES[sid][0].startswith(("https://", "http://")))


if __name__ == "__main__":
    unittest.main()
