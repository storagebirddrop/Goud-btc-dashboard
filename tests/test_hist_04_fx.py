import json
import tempfile
import unittest
from decimal import Decimal as D
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

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

    def _zip(self, xml):
        import io
        import zipfile
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            z.writestr("data.xml", xml)
        return b.getvalue()

    def test_fed_xml_zip_nl_series_nd_and_other_series_ignored(self):
        xml = ('<root><Series CURRENCY="NLG" FREQ="9" SERIES_NAME="RXI_N.B.NL">'
               '<Obs TIME_PERIOD="1998-12-30" OBS_VALUE="1.9000"/><Obs TIME_PERIOD="1998-12-31" OBS_VALUE="ND"/></Series>'
               '<Series CURRENCY="JPY" SERIES_NAME="RXI_N.B.JA"><Obs TIME_PERIOD="1998-12-30" OBS_VALUE="115"/></Series></root>')
        r = fx.parse_fed_xml_zip(self._zip(xml))
        self.assertEqual(len(r["nl_series"]), 1)
        n = r["nl_series"][0]
        self.assertEqual(n["points"], {"1998-12-30": D("1.9000")})
        self.assertEqual(n["nd"], 1)
        self.assertEqual(r["attribute_values"]["CURRENCY"], ["JPY", "NLG"])

    def test_fed_xml_zip_fail_closed(self):
        with self.assertRaises(fx.FxError):
            fx.parse_fed_xml_zip(b"not a zip")
        with self.assertRaises(fx.FxError):
            fx.parse_fed_xml_zip(self._zip('<!DOCTYPE x [<!ENTITY a "b">]><x/>'))
        dup = ('<r><S CURRENCY="NLG"><O TIME_PERIOD="1998-12-30" OBS_VALUE="1.9"/>'
               '<O TIME_PERIOD="1998-12-30" OBS_VALUE="1.8"/></S></r>')
        with self.assertRaises(fx.FxError):
            fx.parse_fed_xml_zip(self._zip(dup))
        with self.assertRaises(fx.FxError):
            fx.parse_fed_xml_zip(self._zip('<r><S CURRENCY="NLG"><O TIME_PERIOD="1998-12-30" OBS_VALUE="-1"/></S></r>'))

    def test_jsonstat_and_snippets(self):
        j = b'{"value":{"0":1.1,"2":1.2},"dimension":{"time":{"category":{"index":{"1999M01":0,"1999M02":1,"1999M03":2}}}}}'
        r = fx.jsonstat_summary(j)
        self.assertEqual((r["time_first"], r["time_last"], r["values"]), ("1999M01", "1999M03", 2))
        self.assertEqual(fx.status_snippets("<p>The series was discontinued when the euro replaced the guilder.</p>")[0][:10], "The series")

    def test_jsonstat_series_and_compare(self):
        j = (b'{"value":{"0":1.1,"2":1.2},"dimension":{"time":{"category":{"index":{"1999-01":0,"1999-02":1,"1999-03":2}}}}}')
        s = fx.jsonstat_series(j)
        self.assertEqual(s, {"1999-01": D("1.1"), "1999-03": D("1.2")})  # null month stays absent
        self.assertEqual(fx.compare_monthly(s, {"1999-01": D("1.1")})["months_dev_gt_1e-4"], 0)
        with self.assertRaises(fx.FxError):
            fx.jsonstat_series(j.replace(b"1.1", b"-1.1"))

    def test_extract_links_filters_and_dedupes(self):
        html = '<a href="/datadownload/Choose.aspx?rel=G5">a</a><a href="/about.htm">b</a><a href="/datadownload/Choose.aspx?rel=G5">c</a>'
        self.assertEqual(fx.extract_links(html), ["/datadownload/Choose.aspx?rel=G5"])

    def test_url_allowlist_registered(self):
        from tools import hist_02_acquire as a
        self.assertIn(fx.ECB_DAILY, a.SOURCES)
        with self.assertRaises(a.AcquisitionError):
            a.validate_url(fx.ECB_DAILY, "https://example.com/EXR/D.USD.EUR.SP00.A?format=csvdata")


ECB_M = (b"KEY,FREQ,CURRENCY,CURRENCY_DENOM,TIME_PERIOD,OBS_VALUE,OBS_STATUS\n"
         b"EXR.M.USD.EUR.SP00.A,M,USD,EUR,1999-01,1.1789,A\n")
REC = {"sha256": "0" * 64, "bytes": 1}
ROOT = Path(__file__).resolve().parents[1]


def http_error(code):
    acq = fx.hist_02_acquire.AcquisitionError("HTTP_STATUS_ERROR source=x phase=response_headers elapsed_seconds=0.1")
    acq.__cause__ = HTTPError("https://x", code, "err", {}, None)
    return acq


class Hist04CiSemanticsTests(unittest.TestCase):
    def run_main(self, overrides=None, default=None):
        """Run main() offline: ECB OK, everything else raises `default` (HTTP 404) unless overridden per source."""
        overrides = overrides or {}
        default = default or http_error(404)

        def fake_fetch(sid):
            if sid in overrides:
                v = overrides[sid]
                if isinstance(v, BaseException):
                    raise v
                return v, dict(REC)
            if sid == fx.ECB_DAILY:
                return ECB, dict(REC)
            if sid == fx.ECB_MONTHLY:
                return ECB_M, dict(REC)
            raise default

        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(fx.hist_02_acquire, "fetch", fake_fetch), \
                mock.patch.object(fx, "probe_status", lambda u: {"status": 0}), \
                mock.patch("sys.stdout"):
            out = Path(d) / "s.json"
            rc = fx.main(["--summary-out", str(out)])
            return rc, json.loads(out.read_text())

    def test_missing_fed_is_partial_exit_0_and_listed(self):
        rc, s = self.run_main()
        self.assertEqual(rc, 0)
        self.assertEqual(s["status"], "PARTIAL")
        ids = {m["source_id"]: m for m in s["missing_sources"]}
        self.assertEqual(ids[fx.FED_ZIP]["reason_class"], "HTTP_404")
        self.assertTrue(all({"source_id", "reason_class", "detail"} <= set(m) for m in s["missing_sources"]))
        names = {a["analysis"] for a in s["analyses_not_performed"]}
        self.assertTrue({"transition_check_1998-12_1999-01", "nlg_jensen_gap", "nlg_chain"} <= names)
        self.assertIn("NOT methodological", s["ci_status_note"])
        self.assertIn("not approved", s["ci_status_note"])

    def test_everything_missing_is_incomplete_exit_0(self):
        rc, s = self.run_main({fx.ECB_DAILY: fx.hist_02_acquire.AcquisitionError("NETWORK_TIMEOUT source=a"),
                               fx.ECB_MONTHLY: fx.hist_02_acquire.AcquisitionError("EMPTY_SOURCE")})
        self.assertEqual((rc, s["status"]), (0, "INCOMPLETE"))
        classes = {m["source_id"]: m["reason_class"] for m in s["missing_sources"]}
        self.assertEqual(classes[fx.ECB_DAILY], "TIMEOUT")
        self.assertEqual(classes[fx.ECB_MONTHLY], "EMPTY_RESPONSE")

    def test_fed_package_without_nlg_is_not_found_not_error(self):
        import io
        import zipfile
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            z.writestr("d.xml", '<r><S CURRENCY="JPY" SERIES_NAME="RXI_N.B.JA"><O TIME_PERIOD="1998-12-30" OBS_VALUE="115"/></S></r>')
        rc, s = self.run_main({fx.FED_ZIP: b.getvalue()})
        self.assertEqual(rc, 0)
        self.assertIn("NOT_FOUND", {m["reason_class"] for m in s["missing_sources"] if m["source_id"] == fx.FED_ZIP})

    def assert_hard(self, overrides):
        rc, s = self.run_main(overrides)
        self.assertEqual(rc, 1)
        self.assertEqual(s["status"], "FAILED_HARD")
        return s

    def test_hard_parse_and_numeric_defects(self):
        dup = ECB + b"EXR.D.USD.EUR.SP00.A,D,USD,EUR,1999-01-04,1.1,A\n"
        self.assert_hard({fx.ECB_DAILY: dup})
        self.assert_hard({fx.ECB_DAILY: ECB.replace(b"1.1789", b"nan")})
        self.assert_hard({fx.ECB_DAILY: ECB.replace(b"1.1789", b"-1.1789")})
        self.assert_hard({fx.ECB_DAILY: ECB.replace(b"1.1789", b"Infinity")})
        self.assert_hard({fx.ECB_DAILY: ECB.replace(b"1.1789", b"0")})
        self.assert_hard({fx.ECB_DAILY: ECB.replace(b",USD,EUR,", b",EUR,USD,")})  # wrong direction

    def test_hard_wrong_fed_direction(self):
        import io
        import zipfile
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            z.writestr("d.xml", '<r><S CURRENCY="NLG" FREQ="D" UNIT="Per_NLG" SERIES_NAME="RXI_N.B.NL">'
                                '<O TIME_PERIOD="1998-12-30" OBS_VALUE="1.9"/></S></r>')
        s = self.assert_hard({fx.FED_ZIP: b.getvalue()})
        self.assertIn("hard_error", s)

    def test_hard_integrity_acquisition_errors(self):
        A = fx.hist_02_acquire.AcquisitionError
        for msg in ("SOURCE_TOO_LARGE", "INVALID_CONTENT_LENGTH", "UNAUTHORIZED_ENDPOINT_OR_REDIRECT", "UNAPPROVED_SOURCE",
                    "READBACK_HASH_MISMATCH", "TLS_ERROR source=x", "UNEXPECTED_HTTP_STATUS", "SOMETHING_NEW"):
            self.assert_hard({fx.ECB_DAILY: A(msg)})
        self.assert_hard({fx.FED_ZIP: A("HTTP_STATUS_ERROR source=x")})  # no HTTP code => unclassified => hard

    def test_hard_unknown_exception(self):
        self.assert_hard({fx.ECB_DAILY: RuntimeError("boom")})

    def test_classifier(self):
        c = fx.classify_acquisition_error
        self.assertIsInstance(c("s", http_error(503)), fx.SourceUnavailable)
        self.assertEqual(c("s", http_error(404)).reason_class, "HTTP_404")
        self.assertIsInstance(c("s", http_error(304)), fx.DataIntegrityError)
        self.assertEqual(c("s", fx.hist_02_acquire.AcquisitionError("DNS_ERROR source=s")).reason_class, "UNREACHABLE")
        self.assertIsInstance(c("s", fx.hist_02_acquire.AcquisitionError("")), fx.DataIntegrityError)

    def test_workflow_has_no_continue_on_error(self):
        self.assertNotIn("continue-on-error", (ROOT / ".github/workflows/hist-04-fx.yml").read_text())


if __name__ == "__main__":
    unittest.main()
