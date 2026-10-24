"""HIST-12: deterministic SYNTHETIC fixtures for the historical publication contract and the inert historical UI. Test directory only.

Every value is artificial and cannot be confused with an observation (NLG 7,777 + 11 per half-year; EUR 5,555 + 7 per month); every point carries the flag
SYNTHETIC_TEST_ONLY and every source id/title carries the marker. The fixtures prove code, not data."""
from __future__ import annotations

from decimal import Decimal

from etl import hist_model as hm
from etl import hist_publication as hp

M = hp.SYNTHETIC_MARKER
SRC_ID = "synthetic_test_only_source"
SRC_SHA = "ab" * 32
DEC = Decimal


def _halfyears(first, last):
    return hm.expected_periods(first, last, "semiannual")


def _months(first, last):
    return hm.expected_periods(first, last, "monthly")


def _pts(periods, values, extra=()):
    return tuple(hm.Point(p, DEC(v), "CONFIRMED", (M, *extra)) for p, v in zip(periods, values))


def _series(sid, periods, values, inputs, extra=()):
    spec = hp.APPROVED_SERIES[sid]
    return hm.Series(series_id=sid, layer=spec["layer"], asset_class="housing", frequency=spec["frequency"], currency=spec["currency"], unit=spec["unit"],
                     definition_id=spec["definition_id"], kind=spec["kind"], points=_pts(periods, values, tuple(sorted(set(extra) | set(spec["required_flags"])))),
                     inputs=tuple(inputs), transforms=({"op": "synthetic_fixture", "note": M},))


def make_series(nvm_offset=0):
    h = _halfyears("1975-H1", "2000-H2")
    nlg = [DEC(7777 + 11 * i + nvm_offset) for i in range(len(h))]
    eur = [(v / hp.NLG_PER_EUR).quantize(DEC("0.000001")) for v in nlg]
    m = _months("1995-01", "1999-12")
    cbs_m = [DEC(5555 + 7 * i) for i in range(len(m))]
    h2 = _halfyears("1995-H1", "2000-H2")
    cbs_h = [DEC(5700 + 9 * i) for i in range(len(h2))]
    src = [(SRC_ID, SRC_SHA)]
    s_nlg = _series("hist_nvm_median_nlg_h", h, nlg, src, ("VISUAL_P135_PER_PROJECT_CONTROL",))
    s_eur = _series("hist_nvm_median_eur_retro_h", h, eur, [("hist_nvm_median_nlg_h", hm.series_sha256(s_nlg))], ("VISUAL_P135_PER_PROJECT_CONTROL",))
    s_m = _series("hist_cbs_avg_eur_m", m, cbs_m, src)
    s_h = _series("hist_cbs_avg_eur_h", h2, cbs_h, [("hist_cbs_avg_eur_m", hm.series_sha256(s_m))])
    return [s_nlg, s_eur, s_m, s_h]


def make_provenance():
    return {"method_ids": [f"{M}_METHOD"], "sources": [{"id": SRC_ID, "title": f"{M} source", "rights_status": f"{M}_NOT_A_RIGHTS_STATEMENT", "sha256": SRC_SHA,
                                                         "vintage": f"{M}_VINTAGE", "acquired_at": "2000-01-01T00:00:00Z"}]}


def make_world(comparison=True, release_id="SYN-HIST-REL-1", nvm_offset=0):
    """(payload dict, ReleaseRecord, comparison_releases tuple). The record is EXTERNAL; the payload only claims it."""
    series = make_series(nvm_offset)
    sha = hm.release_hash(series)
    release = {"id": release_id, "release_sha256": sha, "authorizer": M, "authorized_on": "2000-01-01", "decision_ref": M,
               "series_ids": sorted(s.series_id for s in series), "publication_authorized": True, "comparison_authorized": comparison}
    cmp_block = {"authorized": comparison, "series": list(hp.COMPARISON_SERIES), "first": "1995-H1", "last": "2000-H2", "warning": hp.COMPARISON_WARNING}
    payload = hp.build_payload(series, release, make_provenance(), cmp_block)
    record = hp.release_record(release)
    return payload, record, ((release_id,) if comparison else ())


def make_blob(**kw):
    payload, record, cmp_ok = make_world(**kw)
    blob = hp.serialize(payload)
    return blob, record, cmp_ok


def verify(blob, record, cmp_ok, **over):
    kw = dict(pins=[hp.payload_sha256(blob)], records=[record], comparison_releases=cmp_ok, production=False)
    kw.update(over)
    return hp.verify_payload(blob, **kw)
