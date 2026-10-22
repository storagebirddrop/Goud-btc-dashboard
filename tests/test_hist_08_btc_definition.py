import socket
import unittest
from datetime import date, timedelta
from decimal import Decimal as D

from tools import btc_02_history as H
from tools import hist_08_btc_definition as T

DAY = 86400


def ts(y, m, d, hh=0, mm=0, ss=0):
    return (date(y, m, d) - date(1970, 1, 1)).days * DAY + hh * 3600 + mm * 60 + ss


def daily(month, price_fn, ccy="USD", skip=()):
    n = H.days_in_month(month)
    return H.parse_daily([(f"{month}-{i:02d}", str(price_fn(i))) for i in range(1, n + 1) if i not in skip],
                         source="t", currency=ccy)


def trades_for_month(y, m, price_fn, per_day=2):
    """Deterministic fixture: `per_day` trades each UTC day at 06:00 and 18:00, amount 1."""
    out = []
    for d in range(1, calendar_days(y, m) + 1):
        for k in range(per_day):
            out.append((ts(y, m, d, 6 + 12 * k), str(price_fn(d, k)), "1"))
    return out


def calendar_days(y, m):
    return H.days_in_month(f"{y:04d}-{m:02d}")


class NoNetworkTests(unittest.TestCase):
    def test_pure_functions_do_not_open_sockets(self):
        orig = socket.socket

        def boom(*a, **k):
            raise AssertionError("network used")

        socket.socket = boom
        try:
            T.aggregate_trades_monthly([(ts(2020, 1, 1), "1", "1")])
            T.diff_stats({"2020-01": D(1)}, {"2020-01": D(1)})
        finally:
            socket.socket = orig

    def test_no_publication_path(self):
        with self.assertRaises(H.PublicationRefused):
            H.request_publication({"BTC_PUBLICATION_ENABLED": "true"}, True)
        self.assertFalse(hasattr(T, "publish"))


class CalendarAlignmentTests(unittest.TestCase):
    def test_utc_day_boundaries(self):
        self.assertEqual(T.utc_day_from_ts(0), "1970-01-01")
        self.assertEqual(T.utc_day_from_ts(86399), "1970-01-01")
        self.assertEqual(T.utc_day_from_ts(86400), "1970-01-02")
        self.assertEqual(T.utc_day_from_ts(ts(2020, 1, 31, 23, 59, 59)), "2020-01-31")
        self.assertEqual(T.utc_day_from_ts(ts(2020, 2, 1)), "2020-02-01")

    def test_leap_february_and_month_seconds(self):
        self.assertEqual(T.month_seconds("2020-02"), 29 * DAY)
        self.assertEqual(T.month_seconds("2021-02"), 28 * DAY)
        self.assertEqual(T.month_start_ts("2020-03") - T.month_start_ts("2020-02"), 29 * DAY)
        self.assertEqual(T.next_month("2020-12"), "2021-01")

    def test_last_second_of_month_belongs_to_that_month(self):
        rows, _, _ = T.aggregate_trades_monthly([(ts(2020, 1, 31, 23, 59, 59), "5", "1"), (ts(2020, 2, 1), "7", "1")])
        self.assertEqual(rows["2020-01"]["trades"], 1)
        self.assertEqual(rows["2020-02"]["trades"], 1)

    def test_bad_timestamp_types_refused(self):
        for bad in (-1, 1.5, True, "5"):
            with self.assertRaises(H.HistoryError):
                T.utc_day_from_ts(bad)


class MonthCompletenessTests(unittest.TestCase):
    def test_missing_day_makes_month_incomplete_and_values_none(self):
        tr = [t for t in trades_for_month(2020, 1, lambda d, k: 100) if T.utc_day_from_ts(t[0]) != "2020-01-15"]
        rows, _, _ = T.aggregate_trades_monthly(tr)
        r = rows["2020-01"]
        self.assertFalse(r["complete"])
        self.assertEqual(r["days"], 30)
        for k in ("a1", "a2", "a3", "a3v", "a4"):
            self.assertIsNone(r[k])
        self.assertEqual(r["reason"], "PARTIAL_MONTH")

    def test_complete_month_has_all_definitions(self):
        rows, _, _ = T.aggregate_trades_monthly(
            trades_for_month(2019, 12, lambda d, k: 100) + trades_for_month(2020, 1, lambda d, k: 100)
            + trades_for_month(2020, 2, lambda d, k: 100))
        r = rows["2020-01"]
        self.assertTrue(r["complete"])
        self.assertEqual((r["a1"], r["a2"], r["a3"], r["a3v"], r["a4"]), (D(100),) * 5)

    def test_first_and_last_month_of_file_have_no_twap(self):
        rows, _, _ = T.aggregate_trades_monthly(trades_for_month(2020, 1, lambda d, k: 100))
        self.assertTrue(rows["2020-01"]["complete"])
        self.assertIsNone(rows["2020-01"]["a4"])
        self.assertEqual(rows["2020-01"]["twap_reason"], "WINDOW_NOT_COVERED")

    def test_daily_definitions_skip_partial_months(self):
        s = daily("2020-01", lambda i: 10, skip=(3,))
        self.assertEqual(T.daily_definitions(s), {})


class AggregationTests(unittest.TestCase):
    def setUp(self):
        # Dec 2019 and Feb 2020 complete flat 100 to bracket Jan 2020 (needed for TWAP head and tail).
        self.bracket = trades_for_month(2019, 12, lambda d, k: 100) + trades_for_month(2020, 2, lambda d, k: 100)

    def jan(self, price_fn):
        tr = trades_for_month(2019, 12, lambda d, k: 100) + trades_for_month(2020, 1, price_fn) + \
            trades_for_month(2020, 2, lambda d, k: 100)
        rows, an, daily_closes = T.aggregate_trades_monthly(tr)
        return rows["2020-01"], an, daily_closes

    def test_mean_of_daily_closes_uses_last_trade_of_day(self):
        r, _, dc = self.jan(lambda d, k: 100 if k == 0 else 200)
        self.assertEqual(r["a1"], D(200))
        self.assertEqual(dc["2020-01-10"], D(200))

    def test_trade_mean_is_count_weighted(self):
        # day 1: 3 trades; all other days 2 trades at 100 => weights differ from mean of closes
        tr = trades_for_month(2020, 1, lambda d, k: 100)
        tr = [(t, "100", "1") for t, _, _ in tr]
        extra = [(ts(2020, 1, 1, 7), "400", "1"), (ts(2020, 1, 1, 8), "400", "1"), (ts(2020, 1, 1, 9), "400", "1")]
        full = sorted(trades_for_month(2019, 12, lambda d, k: 100) + tr + extra + trades_for_month(2020, 2, lambda d, k: 100))
        rows, _, _ = T.aggregate_trades_monthly(full)
        r = rows["2020-01"]
        n = 62 + 3
        self.assertEqual(r["a3"], (D(100) * 62 + D(400) * 3) / n)
        self.assertEqual(r["a1"], D(100))  # day-1 close is the 18:00 trade at 100

    def test_vwap_weights_by_amount(self):
        tr = [(ts(2020, 1, d, 6), "100", "1") for d in range(1, 32)] + [(ts(2020, 1, d, 18), "200", "3") for d in range(1, 32)]
        rows, _, _ = T.aggregate_trades_monthly(sorted(tr))
        self.assertEqual(rows["2020-01"]["a3v"], (D(100) + D(600)) / 4)
        self.assertEqual(rows["2020-01"]["a3"], D(150))

    def test_vwap_none_when_total_volume_zero(self):
        tr = [(ts(2020, 1, d, 6), "100", "0") for d in range(1, 32)]
        rows, _, _ = T.aggregate_trades_monthly(tr)
        self.assertIsNone(rows["2020-01"]["a3v"])

    def test_month_close_is_last_trade_of_month(self):
        r, _, _ = self.jan(lambda d, k: 100 + (d if k == 1 else 0))
        self.assertEqual(r["a2"], D(131))

    def test_twap_exact_two_levels(self):
        # price 100 until 2020-01-16T00:00 then 200 until the end of the month; Feb trades continue at 200.
        tr = [(ts(2019, 12, 31, 12), "100", "1")]
        tr += [(ts(2020, 1, d, 12), "100", "1") for d in range(1, 16)]
        tr += [(ts(2020, 1, 16, 0), "200", "1")]
        tr += [(ts(2020, 1, d, 12), "200", "1") for d in range(16, 32)]
        tr += [(ts(2020, 2, 1, 12), "200", "1")]
        rows, _, _ = T.aggregate_trades_monthly(sorted(tr))
        r = rows["2020-01"]
        self.assertTrue(r["complete"])
        self.assertEqual(r["a4"], (D(100) * 15 * DAY + D(200) * 16 * DAY) / (31 * DAY))

    def test_twap_splits_a_segment_across_the_month_boundary(self):
        tr = [(ts(2019, 12, 31, 12), "100", "1")] + [(ts(2020, 1, d, 12), "100", "1") for d in range(1, 31)] + \
            [(ts(2020, 1, 31, 12), "100", "1"), (ts(2020, 2, 1, 12), "100", "1")]
        rows, _, _ = T.aggregate_trades_monthly(sorted(tr))
        self.assertEqual(rows["2020-01"]["a4"], D(100))

    def test_twap_differs_from_mean_when_trading_is_clustered(self):
        # price jumps late on each day: hold keeps the old price most of the day, trade mean sees both equally
        tr = []
        for y, m in ((2019, 12), (2020, 1), (2020, 2)):
            tr += trades_for_month(y, m, lambda d, k: 100 if k == 0 else 200)  # 06:00 -> 100, 18:00 -> 200
        rows, _, _ = T.aggregate_trades_monthly(sorted(tr))
        r = rows["2020-01"]
        self.assertEqual(r["a3"], D(150))
        # each day: 200 from 18:00 to 06:00 next day (12h), 100 from 06:00 to 18:00 (12h) => 150
        self.assertEqual(r["a4"], D(150))
        tr2 = []
        for y, m in ((2019, 12), (2020, 1), (2020, 2)):
            tr2 += [(ts(y, m, d, 1), "100", "1") for d in range(1, calendar_days(y, m) + 1)]
            tr2 += [(ts(y, m, d, 2), "200", "1") for d in range(1, calendar_days(y, m) + 1)]
        rows2, _, _ = T.aggregate_trades_monthly(sorted(tr2))
        r2 = rows2["2020-01"]
        self.assertEqual(r2["a3"], D(150))
        self.assertGreater(r2["a4"], D("190"))  # 200 held 23h of 24h

    def test_max_gap_reported(self):
        r, _, _ = self.jan(lambda d, k: 100)
        self.assertEqual(r["max_gap_s"], 12 * 3600)

    def test_decimal_exact_no_float(self):
        r, _, _ = self.jan(lambda d, k: "0.1")
        self.assertIsInstance(r["a1"], D)
        self.assertEqual(r["a1"], D("0.1"))
        with self.assertRaises(H.HistoryError):
            T.aggregate_trades_monthly([(ts(2020, 1, 1), 1.5, "1")])

    def test_daily_definitions_a1_a2(self):
        s = daily("2020-01", lambda i: i)
        d = T.daily_definitions(s)["2020-01"]
        self.assertEqual(d["a1"], D(16))
        self.assertEqual(d["a2"], D(31))
        self.assertEqual(T.column({"m": d}, "a2"), {"m": D(31)})


class CorruptedFixtureTests(unittest.TestCase):
    def test_unordered_trade_refused_in_strict_mode(self):
        with self.assertRaisesRegex(H.HistoryError, "unordered"):
            T.aggregate_trades_monthly([(ts(2020, 1, 2), "1", "1"), (ts(2020, 1, 1), "1", "1")])

    def test_unordered_trade_counted_and_skipped_not_repaired(self):
        rows, an, dc = T.aggregate_trades_monthly(
            [(ts(2020, 1, 2), "5", "1"), (ts(2020, 1, 1), "999", "1"), (ts(2020, 1, 3), "7", "1")], strict=False)
        self.assertEqual(an["unordered"], 1)
        self.assertNotIn("2020-01-01", dc)

    def test_bad_price_and_negative_amount_dropped_and_counted(self):
        rows, an, _ = T.aggregate_trades_monthly(
            [(ts(2020, 1, 1), "0", "1"), (ts(2020, 1, 1, 1), "-3", "1"), (ts(2020, 1, 1, 2), "5", "-1"), (ts(2020, 1, 1, 3), "9", "1")])
        self.assertEqual((an["bad_price"], an["bad_amount"], an["rows"]), (2, 1, 4))
        self.assertEqual(rows["2020-01"]["trades"], 1)

    def test_non_finite_and_garbage_refused(self):
        for bad in ("NaN", "Infinity", "abc", ""):
            with self.assertRaises(H.HistoryError):
                T.aggregate_trades_monthly([(ts(2020, 1, 1), bad, "1")])

    def test_duplicate_daily_day_refused(self):
        with self.assertRaisesRegex(H.HistoryError, "duplicate"):
            H.parse_daily([("2020-01-01", "1"), ("2020-01-01", "2")], source="t", currency="USD")

    def test_noncanonical_day_refused(self):
        with self.assertRaises(H.HistoryError):
            H.parse_daily([("2020-1-1", "1")], source="t", currency="USD")

    def test_same_timestamp_duplicate_trades_are_not_days_duplicates(self):
        rows, an, _ = T.aggregate_trades_monthly([(ts(2020, 1, 1), "5", "1"), (ts(2020, 1, 1), "6", "1")])
        self.assertEqual(an["unordered"], 0)
        self.assertEqual(rows["2020-01"]["trades"], 2)


class ConversionTests(unittest.TestCase):
    def fx_weekdays(self, month, rate_fn):
        n = H.days_in_month(month)
        rows = []
        for i in range(1, n + 1):
            if date.fromisoformat(f"{month}-{i:02d}").weekday() < 5:
                rows.append((f"{month}-{i:02d}", str(rate_fn(i))))
        return H.parse_daily(rows, source="ecb", currency="USD")

    def test_constant_inputs_all_constructions_agree(self):
        usd, fx = daily("2020-01", lambda i: 120), self.fx_weekdays("2020-01", lambda i: "1.2")
        for c in T.CONVERSIONS:
            self.assertEqual(T.convert_usd_to_eur(usd, fx, c)["2020-01"]["value"], D(100))

    def test_c1_ratio_of_means_hand_calculation(self):
        usd = daily("2020-01", lambda i: 100 + i)
        fx = self.fx_weekdays("2020-01", lambda i: "1.25")
        r = T.convert_usd_to_eur(usd, fx, "C1")["2020-01"]
        self.assertEqual(r["value"], D(116) / D("1.25"))
        self.assertEqual(r["fx_days"], 23)
        self.assertEqual(r["usd_days"], 31)

    def test_c2_c3_use_weekdays_only_and_differ_from_c1_with_weekend_effect(self):
        # USD price higher on weekends: matched-day variants omit the weekend premium
        def usd_price(i):
            return 130 if date(2020, 1, i).weekday() >= 5 else 100
        usd, fx = daily("2020-01", usd_price), self.fx_weekdays("2020-01", lambda i: "1")
        c1 = T.convert_usd_to_eur(usd, fx, "C1")["2020-01"]
        c2 = T.convert_usd_to_eur(usd, fx, "C2")["2020-01"]
        c3 = T.convert_usd_to_eur(usd, fx, "C3")["2020-01"]
        self.assertEqual(c2["matched_days"], 23)
        self.assertEqual(c2["value"], D(100))
        self.assertEqual(c3["value"], D(100))
        self.assertGreater(c1["value"], D(100))
        self.assertEqual(c1["value"], (D(100) * 23 + D(130) * 8) / 31)

    def test_c2_and_c3_differ_when_fx_varies(self):
        usd = daily("2020-01", lambda i: 100 + i)
        fx = self.fx_weekdays("2020-01", lambda i: "1.1" if i % 2 else "1.3")
        c2 = T.convert_usd_to_eur(usd, fx, "C2")["2020-01"]["value"]
        c3 = T.convert_usd_to_eur(usd, fx, "C3")["2020-01"]["value"]
        self.assertNotEqual(c2, c3)

    def test_partial_usd_month_is_absent_not_filled(self):
        usd, fx = daily("2020-01", lambda i: 100, skip=(10,)), self.fx_weekdays("2020-01", lambda i: "1")
        self.assertEqual(T.convert_usd_to_eur(usd, fx, "C1"), {})

    def test_month_without_fx_is_absent_no_carry_forward(self):
        usd = daily("2020-02", lambda i: 100)
        fx = self.fx_weekdays("2020-01", lambda i: "1")
        for c in T.CONVERSIONS:
            self.assertEqual(T.convert_usd_to_eur(usd, fx, c), {})

    def test_fx_missing_day_stays_missing(self):
        usd = daily("2020-01", lambda i: 100)
        fx = H.parse_daily([("2020-01-02", "1"), ("2020-01-03", "1")], source="ecb", currency="USD")
        r = T.convert_usd_to_eur(usd, fx, "C2")["2020-01"]
        self.assertEqual(r["matched_days"], 2)

    def test_currency_confusion_and_unknown_method_refused(self):
        eur = daily("2020-01", lambda i: 100, ccy="EUR")
        fx = self.fx_weekdays("2020-01", lambda i: "1")
        with self.assertRaises(H.HistoryError):
            T.convert_usd_to_eur(eur, fx, "C1")
        with self.assertRaises(H.HistoryError):
            T.convert_usd_to_eur(daily("2020-01", lambda i: 1), fx, "C9")

    def test_duplicate_fx_day_refused(self):
        with self.assertRaises(H.HistoryError):
            H.parse_daily([("2020-01-02", "1"), ("2020-01-02", "1.1")], source="ecb", currency="USD")


class DiffStatsTests(unittest.TestCase):
    def test_stats_and_signed_bias(self):
        a = {"2020-01": D(110), "2020-02": D(90), "2021-01": D(100)}
        b = {"2020-01": D(100), "2020-02": D(100), "2021-01": D(100), "2021-02": D(5)}
        t = T.diff_by_year(a, b)
        self.assertEqual(t["2020"]["n"], 2)
        self.assertEqual(t["2020"]["mean_rel"], D("0.1"))
        self.assertEqual(t["2020"]["signed_mean_rel"], D(0))
        self.assertEqual(t["2020"]["max_abs"], D(10))
        self.assertEqual(t["2021"]["max_rel"], D(0))
        self.assertEqual(t["ALL"]["n"], 3)

    def test_no_overlap_and_none_values(self):
        self.assertIsNone(T.diff_stats({"2020-01": D(1)}, {"2020-02": D(1)}))
        self.assertIsNone(T.diff_stats({"2020-01": None}, {"2020-01": D(1)}))

    def test_zero_reference_refused(self):
        with self.assertRaises(H.HistoryError):
            T.diff_stats({"2020-01": D(1)}, {"2020-01": D(0)})

    def test_window(self):
        self.assertEqual(T.window({"2020-01": 1, "2020-03": 2, "2020-06": 3}, "2020-02", "2020-05"), {"2020-03": 2})


class SatPerHouseTests(unittest.TestCase):
    def test_exact_units(self):
        self.assertEqual(T.btc_per_house(D(400000), D(40000)), D(10))
        self.assertEqual(T.sat_per_house(D(400000), D(40000)), D(10) * 10 ** 8)

    def test_sat_effect_equals_inverse_price_ratio_and_skips_missing(self):
        houses = {"2020-01": D(300000), "2020-02": D(300000)}
        a, b = {"2020-01": D(110), "2020-03": D(5)}, {"2020-01": D(100), "2020-03": D(5)}
        eff = T.sat_effect(houses, a, b)
        self.assertEqual(set(eff), {"2020-01"})
        self.assertLess(abs(eff["2020-01"] - D(10) / D(110)), D("1e-20"))

    def test_refuses_non_positive(self):
        with self.assertRaises(H.HistoryError):
            T.sat_per_house(D(1), D(0))

    def test_load_houses_reads_only_house_series(self):
        import tempfile, os
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write("date,series,value\n2000-01,nl_house_avg_eur,157270.0\n2000-01,nl_hpi,51.2\n")
        try:
            self.assertEqual(T.load_houses(f.name), {"2000-01": D("157270.0")})
        finally:
            os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
