import unittest
from datetime import date, timedelta
from decimal import Decimal as D

from tools import btc_02_history as H


def days(first, n):
    d = date.fromisoformat(first)
    return [(d + timedelta(days=i)).isoformat() for i in range(n)]


def series(first, n, price, ccy="USD", source="t"):
    return H.parse_daily([(d, str(price)) for d in days(first, n)], source=source, currency=ccy)


def month_series(month, price, ccy="USD", skip=()):
    n = H.days_in_month(month)
    rows = [(f"{month}-{i:02d}", str(price)) for i in range(1, n + 1) if i not in skip]
    return H.parse_daily(rows, source="t", currency=ccy)


class ParseTests(unittest.TestCase):
    def test_duplicate_day_refused(self):
        with self.assertRaisesRegex(H.HistoryError, "duplicate"):
            H.parse_daily([("2020-01-01", "1"), ("2020-01-01", "2")], source="t", currency="USD")

    def test_unordered_refused(self):
        with self.assertRaisesRegex(H.HistoryError, "unordered"):
            H.parse_daily([("2020-01-02", "1"), ("2020-01-01", "2")], source="t", currency="USD")

    def test_non_positive_and_nonfinite_refused(self):
        for bad in ("0", "-1", "NaN", "Infinity", "abc"):
            with self.assertRaises(H.HistoryError):
                H.parse_daily([("2020-01-01", bad)], source="t", currency="USD")

    def test_float_input_refused(self):
        with self.assertRaises(H.HistoryError):
            H.parse_daily([("2020-01-01", 1.5)], source="t", currency="USD")

    def test_noncanonical_date_refused(self):
        for bad in ("2020-1-1", "20200101", "2020-02-30"):
            with self.assertRaises(H.HistoryError):
                H.parse_daily([(bad, "1")], source="t", currency="USD")

    def test_empty_and_unknown_currency_refused(self):
        with self.assertRaises(H.HistoryError):
            H.parse_daily([], source="t", currency="USD")
        with self.assertRaises(H.HistoryError):
            H.parse_daily([("2020-01-01", "1")], source="t", currency="GBP")

    def test_hash_mismatch(self):
        import hashlib
        raw = b"abc"
        self.assertEqual(H.verify_sha256(raw, hashlib.sha256(raw).hexdigest()), hashlib.sha256(raw).hexdigest())
        with self.assertRaises(H.HashMismatch):
            H.verify_sha256(raw, "0" * 64)


class MonthTests(unittest.TestCase):
    def test_missing_day_stays_missing_and_month_incomplete(self):
        s = month_series("2020-02", 100, skip=(10,))
        st = H.monthly_stats(s.as_dict())["2020-02"]
        self.assertFalse(st["complete"])
        self.assertEqual(st["days"], 28)
        self.assertEqual(H.complete_monthly_mean(s), {})
        self.assertEqual(H.missing_days(list(s.as_dict())), ["2020-02-10"])

    def test_no_forward_fill_in_mean(self):
        s = H.parse_daily([("2020-02-01", "100"), ("2020-02-03", "300")], source="t", currency="USD")
        self.assertEqual(H.monthly_stats(s.as_dict())["2020-02"]["mean"], D(200))  # mean of 2 obs, not 3 filled
        self.assertEqual(H.missing_days(list(s.as_dict())), ["2020-02-02"])

    def test_partial_month_never_complete_even_if_mean_present(self):
        s = series("2020-03-17", 15, 50)  # 2020-03-17..31 complete tail, month partial
        self.assertFalse(H.monthly_stats(s.as_dict())["2020-03"]["complete"])
        e = H.v3_native_eur(H.parse_daily([(d, "50") for d in days("2020-03-17", 31)], source="t", currency="EUR"))
        self.assertEqual({r["month"]: r["reason"] for r in e}["2020-03"], "PARTIAL_MONTH")
        self.assertIsNone(e[0]["value"])

    def test_leap_february_complete(self):
        self.assertTrue(H.monthly_stats(month_series("2020-02", 1).as_dict())["2020-02"]["complete"])
        self.assertEqual(H.days_in_month("2021-02"), 28)


class FxVariantTests(unittest.TestCase):
    def fx(self, month, rate, skip_weekends=True):
        rows = []
        for i in range(1, H.days_in_month(month) + 1):
            d = date.fromisoformat(f"{month}-{i:02d}")
            if skip_weekends and d.weekday() >= 5:
                continue
            rows.append((d.isoformat(), str(rate)))
        return H.parse_daily(rows, source="ecb", currency="USD")

    def test_v1_ratio_of_means(self):
        usd = month_series("2020-01", 1200)
        r = H.v1_ratio_of_means(usd, self.fx("2020-01", "1.2"))[0]
        self.assertEqual(r["value"], D(1000))
        self.assertEqual(r["fx_days"], 23)

    def test_v1_requires_usd_series_not_eur(self):
        eur = month_series("2020-01", 1000, ccy="EUR")
        with self.assertRaisesRegex(H.HistoryError, "USD/EUR confusion"):
            H.v1_ratio_of_means(eur, self.fx("2020-01", "1.2"))

    def test_fx_must_be_tagged_usd(self):
        bad_fx = H.parse_daily([("2020-01-01", "1.2")], source="x", currency="EUR")
        with self.assertRaises(H.HistoryError):
            H.v1_ratio_of_means(month_series("2020-01", 1200), bad_fx)

    def test_v3_requires_eur(self):
        with self.assertRaises(H.HistoryError):
            H.v3_native_eur(month_series("2020-01", 1000, ccy="USD"))

    def test_v1_no_fx_month_is_null_not_carried(self):
        usd = H.parse_daily([(f"2020-01-{i:02d}", "1200") for i in range(1, 32)] +
                            [(f"2020-02-{i:02d}", "1200") for i in range(1, 30)], source="t", currency="USD")
        rows = H.v1_ratio_of_means(usd, self.fx("2020-01", "1.2"))
        self.assertEqual(rows[1]["month"], "2020-02")
        self.assertIsNone(rows[1]["value"])
        self.assertEqual(rows[1]["reason"], "NO_FX")

    def test_v1_min_fx_days(self):
        fx = H.parse_daily([("2020-01-02", "1.2")], source="ecb", currency="USD")
        r = H.v1_ratio_of_means(month_series("2020-01", 1200), fx, min_fx_days=5)[0]
        self.assertIsNone(r["value"])
        self.assertEqual(r["reason"], "NO_FX")

    def test_v2_weekday_only_is_not_complete_and_labelled(self):
        usd = month_series("2020-01", 1200)
        r = H.v2_matched_day(usd, self.fx("2020-01", "1.2"))[0]
        self.assertEqual(r["value"], D(1000))
        self.assertEqual(r["matched_days"], 23)
        self.assertFalse(r["complete"])
        self.assertEqual(r["reason"], "MATCHED_DAYS_ONLY")

    def test_v2_without_overlap_is_null(self):
        fx = H.parse_daily([("2019-12-02", "1.2")], source="ecb", currency="USD")
        self.assertIsNone(H.v2_matched_day(month_series("2020-01", 1200), fx)[0]["value"])

    def test_v1_v2_differ_when_weekend_prices_differ(self):
        rows = []
        for i in range(1, 32):
            d = date.fromisoformat(f"2020-01-{i:02d}")
            rows.append((d.isoformat(), "2400" if d.weekday() >= 5 else "1200"))
        usd = H.parse_daily(rows, source="t", currency="USD")
        fx = self.fx("2020-01", "1.2")
        v1 = H.v1_ratio_of_means(usd, fx)[0]["value"]
        v2 = H.v2_matched_day(usd, fx)[0]["value"]
        self.assertEqual(v2, D(1000))
        self.assertGreater(v1, v2)


class QualityTests(unittest.TestCase):
    def test_levels(self):
        t = D(10) ** 6
        self.assertEqual(H.classify_quality(eur_native_complete=True, usd_derived_complete=True, mean_daily_usd_notional=t * 2), H.Q1)
        self.assertEqual(H.classify_quality(eur_native_complete=False, usd_derived_complete=True, mean_daily_usd_notional=t * 2), H.Q2)
        self.assertEqual(H.classify_quality(eur_native_complete=True, usd_derived_complete=True, mean_daily_usd_notional=t / 2), H.Q3)
        self.assertEqual(H.classify_quality(eur_native_complete=False, usd_derived_complete=True, mean_daily_usd_notional=None), H.Q3)
        self.assertEqual(H.classify_quality(eur_native_complete=False, usd_derived_complete=False, mean_daily_usd_notional=t * 9), H.Q0)

    def test_build_monthly_q0_is_null_with_reason(self):
        usd = H.parse_daily([("2020-01-15", "1")], source="t", currency="USD")
        fx = H.parse_daily([("2020-01-15", "1")], source="e", currency="USD")
        rows = H.build_monthly(None, H.v1_ratio_of_means(usd, fx), {})
        self.assertIsNone(rows[0]["btc_eur"])
        self.assertEqual(rows[0]["quality"], H.Q0)
        self.assertIn("PARTIAL_MONTH", rows[0]["reason"])

    def test_build_monthly_prefers_native_and_labels(self):
        eur = month_series("2020-01", 1000, ccy="EUR")
        usd = month_series("2020-01", 1200)
        fx = H.parse_daily([(f"2020-01-{i:02d}", "1.2") for i in range(1, 32)], source="e", currency="USD")
        rows = H.build_monthly(H.v3_native_eur(eur), H.v1_ratio_of_means(usd, fx), {"2020-01": D(10) ** 7})
        self.assertEqual((rows[0]["basis"], rows[0]["quality"], rows[0]["btc_eur"]), ("V3_EUR_NATIVE", H.Q1, D(1000)))

    def test_sustained_from(self):
        n = {"2020-01": D(5), "2020-02": D(1), "2020-03": D(5), "2020-04": D(6)}
        self.assertEqual(H.sustained_from(n, D(5)), "2020-03")
        self.assertIsNone(H.sustained_from({"2020-01": D(5), "2020-02": D(1)}, D(5)))


class SpliceTests(unittest.TestCase):
    A = {"2020-01": {"btc_eur": D(10), "quality": "Q1", "reason": None},
         "2020-02": {"btc_eur": None, "quality": "Q0", "reason": "NO_DATA"}}
    B = {"2020-01": {"btc_eur": D(99), "quality": "Q2", "reason": None},
         "2020-02": {"btc_eur": D(20), "quality": "Q2", "reason": None}}

    def test_no_plan_no_automatic_splice(self):
        with self.assertRaisesRegex(H.HistoryError, "automatic splicing"):
            H.assemble({"a": self.A, "b": self.B}, [])

    def test_planned_source_null_does_not_fall_back(self):
        out = H.assemble({"a": self.A, "b": self.B}, [("2020-01", "2020-02", "a")])
        self.assertEqual(out[0]["btc_eur"], D(10))
        self.assertIsNone(out[1]["btc_eur"])  # b has 20 but is NOT used
        self.assertEqual(out[1]["reason"], "NO_DATA")

    def test_overlapping_plan_refused_and_unknown_source(self):
        with self.assertRaises(H.HistoryError):
            H.assemble({"a": self.A, "b": self.B}, [("2020-01", "2020-02", "a"), ("2020-02", "2020-02", "b")])
        with self.assertRaises(H.HistoryError):
            H.assemble({"a": self.A}, [("2020-01", "2020-01", "zz")])

    def test_explicit_plan_with_break(self):
        out = H.assemble({"a": self.A, "b": self.B}, [("2020-01", "2020-01", "a"), ("2020-02", "2020-02", "b")])
        self.assertEqual([r["source"] for r in out], ["a", "b"])
        self.assertEqual(out[1]["btc_eur"], D(20))


class CompareTests(unittest.TestCase):
    def test_stats(self):
        a = {f"2020-{m:02d}": D(100 + m) for m in range(1, 11)}
        b = {f"2020-{m:02d}": D(100) for m in range(1, 11)}
        c = H.compare_monthly(a, b)
        self.assertEqual(c["n"], 10)
        self.assertEqual(c["max"], D("0.10"))
        self.assertEqual(c["max_month"], "2020-10")
        self.assertEqual(c["p50"], D("0.05"))
        self.assertEqual(c["over_5pct"], 5)
        self.assertEqual(c["over_1pct"], 9)

    def test_none_and_disjoint_months_ignored(self):
        self.assertEqual(H.compare_monthly({"2020-01": None}, {"2020-01": D(1)}), {"n": 0})
        self.assertEqual(H.compare_monthly({"2020-01": D(1)}, {"2020-02": D(1)}), {"n": 0})

    def test_nonpositive_reference_refused(self):
        with self.assertRaises(H.HistoryError):
            H.compare_monthly({"2020-01": D(1)}, {"2020-01": D(0)})

    def test_matched_day_means_min_days(self):
        a = {d: D(1) for d, _ in [(x, 0) for x in days("2020-01-01", 10)]}
        b = {d: D(2) for d in days("2020-01-06", 10)}
        ma, mb, cd = H.matched_day_means(a, b, min_days=5)
        self.assertEqual(cd["2020-01"], 5)
        self.assertEqual((ma["2020-01"], mb["2020-01"]), (D(1), D(2)))
        self.assertEqual(H.matched_day_means(a, b, min_days=6)[2], {})


class SatTests(unittest.TestCase):
    def test_sat_conversion_exact(self):
        bph = H.btc_per_house(D("400000"), D("40000"))
        self.assertEqual(bph, D(10))
        self.assertEqual(H.sat_per_house(bph), D(10) * 10 ** 8)

    def test_round_trip_reconstructs_price_exactly_enough(self):
        h, b = D("412345.67"), D("43210.987654")
        sat = H.sat_per_house(H.btc_per_house(h, b))
        self.assertLess(abs(h * 10 ** 8 / sat - b) / b, D("1e-24"))

    def test_usd_price_refused(self):
        with self.assertRaisesRegex(H.HistoryError, "USD/EUR confusion"):
            H.btc_per_house(D(1), D(1), currency="USD")

    def test_non_positive_and_float_refused(self):
        for h, b in ((0, 1), (1, 0), (-1, 1), (1, -5)):
            with self.assertRaises(H.HistoryError):
                H.btc_per_house(D(h), D(b))
        with self.assertRaises(H.HistoryError):
            H.btc_per_house(1.5, D(1))
        with self.assertRaises(H.HistoryError):
            H.sat_per_house(D(0))

    def test_house_join_no_extension(self):
        rows = [{"month": "1999-12", "btc_eur": None, "quality": "Q0", "basis": None, "reason": "NO_DATA"},
                {"month": "2020-01", "btc_eur": D(40000), "quality": "Q1", "basis": "x", "reason": None},
                {"month": "2026-09", "btc_eur": D(60000), "quality": "Q1", "basis": "x", "reason": None}]
        out = H.house_join(rows, {"2020-01": D(400000)})
        self.assertEqual(out[0]["join_reason"], "NO_BTC_PRICE")
        self.assertEqual(out[1]["sat_per_house"], D(10) * 10 ** 8)
        self.assertEqual(out[2]["join_reason"], "NO_HOUSE_PRICE")
        self.assertIsNone(out[2]["sat_per_house"])


class TradesTests(unittest.TestCase):
    def test_daily_aggregation_and_anomalies(self):
        t0 = 1_300_000_000 // 86400 * 86400
        trades = [(t0 + 10, "1.0", "2"), (t0 + 5, "2.0", "1"), (t0 + 20, "0", "1"), (t0 + 30, "3.0", "-1"),
                  (t0 + 86400 + 1, "5.0", "1")]
        days_, an = H.aggregate_trades(trades)
        d0 = days_[(date(1970, 1, 1) + timedelta(days=t0 // 86400)).isoformat()]
        self.assertEqual((d0["close"], d0["high"], d0["low"], d0["volume"], d0["count"]), (D("1.0"), D("2.0"), D("1.0"), D(3), 2))
        self.assertEqual((an["unordered"], an["bad_price"], an["bad_amount"]), (1, 1, 1))
        self.assertEqual(len(days_), 2)

    def test_top_jumps_do_not_bridge_gaps(self):
        d = {"2020-01-01": D(1), "2020-01-03": D(100), "2020-01-04": D(110)}
        self.assertEqual(H.top_jumps(d, 5), [("0.1", "2020-01-04")])


class DeterminismAndPublicationTests(unittest.TestCase):
    def test_canonical_hash_deterministic_and_order_independent(self):
        a = {"b": D("1.50"), "a": [D(2)]}
        b = {"a": [D(2)], "b": D("1.50")}
        self.assertEqual(H.sha256_canonical(a), H.sha256_canonical(b))
        self.assertNotEqual(H.sha256_canonical(a), H.sha256_canonical({"a": [D(3)], "b": D("1.50")}))
        self.assertEqual(len(H.sha256_canonical(a)), 64)

    def test_publication_always_refused(self):
        env = {"BTC_PUBLICATION_ENABLED": "true", "BTC_PUBLICATION_APPROVAL": "APPROVED"}
        for e, flag in ((None, False), ({}, True), (env, True)):
            with self.assertRaises(H.PublicationRefused):
                H.request_publication(e, flag)

    def test_percentile_nearest_rank(self):
        v = [D(i) for i in range(1, 11)]
        self.assertEqual(H.percentile(v, 50), D(5))
        self.assertEqual(H.percentile(v, 99), D(10))
        with self.assertRaises(H.HistoryError):
            H.percentile([], 50)


if __name__ == "__main__":
    unittest.main()
