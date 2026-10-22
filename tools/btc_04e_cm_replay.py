"""BTC-04E research only: Coin Metrics Community PriceUSD x ECB x CBS, validation and deterministic replay. NOTHING IS PUBLISHED.

Method CM_PRICEUSD_MONTHMEAN_C1_V1 (conditionally accepted for research by Project Control, pending this validation):
  BTC_USD_month   = arithmetic mean of every daily PriceUSD of a COMPLETE UTC calendar month
  ECB_USD_EUR_mon = arithmetic mean of the valid ECB USD-per-EUR fixings of the month (no weekend/holiday carry-forward)
  BTC_EUR_equiv   = BTC_USD_month / ECB_USD_EUR_mon            (USD-derived EUR equivalent, not a native EUR price)
  BTC_per_house   = CBS mean house price EUR / BTC_EUR_equiv;   Sats_per_house = BTC_per_house x 1e8
PriceUSD is a provider reference price, not a Bitstamp close. This method is distinct from BTC-03 A1 and is never merged with it.
Raw third-party prices are read in memory (and optionally written to a PRIVATE runner directory for the replay check) and are
never committed or uploaded. Offline tests use synthetic data and prove code, not data. Missing stays null: no fill, no fallback.
"""
import argparse
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from etl import hist_model as hm  # noqa: E402
from tools import btc_02_history as H  # noqa: E402
from tools import btc_03_housing as b3  # noqa: E402
from tools import hist_08_bundle as hb  # noqa: E402
from tools import hist_10_gold_housing as h10  # noqa: E402

METHOD_ID = "CM_PRICEUSD_MONTHMEAN_C1_V1"
PARSER_VERSION = "cm-priceusd-parser/1"
EXCEPTION_POLICY_VERSION = "CM_EXC_V1"
QUALITY_VERSION = "CM_Q_V1"
METHOD_FLAG = f"METHOD:{METHOD_ID}"
RESEARCH_FLAG = "BITCOIN_RESEARCH_ONLY"
COND_FLAG = "CONDITIONALLY_ACCEPTED_RESEARCH_METHOD"
PROVIDER, ASSET, METRIC = "Coin Metrics Community", "btc", "PriceUSD"
BASE_URL = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
HOST = "community-api.coinmetrics.io"
FIRST_SUPPORTED_MONTH = "2010-08"  # first complete month; the series starts 2010-07-18 (partial July is null)
RESEARCH_CUTOFF = "2026-08"  # last CBS month; derived pins stop here
SATS = H.SATS_PER_BTC
MIN_FX_COVERAGE = Decimal("0.5")
PIN_WINDOWS = {"cm_priceusd_daily": ("2010-07-18", "2026-08-31"), "ecb_usd_per_eur_daily": ("1999-01-04", "2026-08-31")}
EXCEPTIONS = {"2011-06": "HOLD_2011_06"}  # research-only/HOLD: no published value, no connection across it
STALE_MIN_RUN = 5
MODES = ("validate", "bootstrap")  # normal pinned validation fails closed; pin generation needs the explicit bootstrap mode
OK_STATUSES = ("COMPLETE_RESEARCH", "BOOTSTRAP_PINS_CANDIDATE")
ELIGIBILITY = ("RESEARCH_ONLY", "RESEARCH_ONLY_HOLD", "RELEASE_ELIGIBLE")
RELEASE_APPROVALS = frozenset()  # months a future Project Control release record approves; empty: nothing is publishable
TIME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})T00:00:00(?:\.0+)?Z$")
INDEPENDENT_MONTHS = ("2010-08", "2011-06", "2013-01", "2014-02", "2016-05", "2017-12")
RETRIES, RETRY_STATUS = 5, {429, 500, 502, 503, 504}
SNAPSHOT_FORMAT = "btc04e-snapshot/2"
SNAPSHOT_MANIFEST = "snapshot_manifest.json"
CM_FILE, ECB_FILE = "cm_priceusd_daily", "ecb_usd_per_eur_daily"


class Btc04eError(hm.ModelError):
    """Input or consistency defect: fail closed."""


class SnapshotError(Btc04eError):
    """Stored vintage cannot be trusted. `code`: MISSING, CORRUPT, SOURCE_HASH_MISMATCH, NORMALIZED_HASH_MISMATCH, METHOD_CHANGED, EXISTS."""

    def __init__(self, code, message):
        super().__init__(f"{code}: {message}")
        self.code = code


# ------------------------------------------------------------------ adapter: strict parsing
def parse_day(timestamp) -> str:
    m = TIME_RE.match(timestamp) if isinstance(timestamp, str) else None
    if not m:
        raise Btc04eError(f"timestamp is not a UTC midnight: {timestamp!r}")
    try:
        if date.fromisoformat(m.group(1)).isoformat() != m.group(1):
            raise ValueError
    except ValueError:
        raise Btc04eError(f"invalid calendar date in {timestamp!r}") from None
    return m.group(1)


def parse_price(raw, day="") -> Decimal:
    """Canonical decimal from the provider's string. Floats, booleans, non-finite and non-positive values are refused."""
    if isinstance(raw, (float, bool)) or not isinstance(raw, (str, int)):
        raise Btc04eError(f"{day}: PriceUSD must be a decimal string, got {type(raw).__name__}")
    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        raise Btc04eError(f"{day}: PriceUSD is not a decimal: {raw!r}") from None
    if not value.is_finite() or value <= 0:
        raise Btc04eError(f"{day}: PriceUSD must be finite and positive, got {raw!r}")
    return value


def parse_page(payload) -> tuple:
    """-> (rows [(day, Decimal|None)], next_url|None). A missing PriceUSD field is a provider gap (None), never a price."""
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise Btc04eError("malformed Coin Metrics response")
    rows = []
    for e in payload["data"]:
        if not isinstance(e, dict) or e.get("asset") != ASSET:
            raise Btc04eError("unexpected asset in Coin Metrics response")
        day = parse_day(e.get("time"))
        rows.append((day, parse_price(e[METRIC], day) if e.get(METRIC) is not None else None))
    url, token = payload.get("next_page_url"), payload.get("next_page_token")
    if url is not None:
        u = urlparse(url) if isinstance(url, str) else None
        if not u or u.scheme != "https" or u.netloc != HOST:
            raise Btc04eError("pagination URL leaves the official HTTPS endpoint")
    elif token is not None and (not isinstance(token, str) or not token):
        raise Btc04eError("invalid pagination token")
    return rows, url


def merge_rows(rows) -> tuple:
    """-> (daily {day: Decimal}, provider_gaps [day]). Identical duplicates are collapsed; conflicting ones fail closed."""
    daily, gaps = {}, set()
    for day, value in rows:
        if value is None:
            gaps.add(day)
            continue
        if day in daily and daily[day] != value:
            raise Btc04eError(f"conflicting PriceUSD records for {day}: {daily[day]} vs {value}")
        daily[day] = value
    clash = gaps & set(daily)
    if clash:
        raise Btc04eError(f"contradictory records (value and gap) for {sorted(clash)[:3]}")
    return daily, sorted(gaps)


def query(start, end) -> dict:
    return {"assets": ASSET, "metrics": METRIC, "frequency": "1d", "start_time": start, "end_time": end, "page_size": 10000}


def fetch_priceusd(session, *, start, end, sleep=time.sleep, now=lambda: datetime.now(timezone.utc), max_pages=50) -> dict:
    """Paginated fetch with bounded retries and Retry-After handling. Returns acquisition record + daily dict."""
    for d in (start, end):
        if date.fromisoformat(d).isoformat() != d:
            raise Btc04eError(f"invalid date {d!r}")
    if start > end:
        raise Btc04eError("start after end")
    url, params, rows, pages, raw_pages, seen = BASE_URL, query(start, end), [], [], [], set()
    for _ in range(max_pages):
        for attempt in range(RETRIES + 1):
            r = session.get(url, params=params, timeout=60)
            if r.status_code in RETRY_STATUS and attempt < RETRIES:
                wait = r.headers.get("Retry-After", "") if getattr(r, "headers", None) else ""
                sleep(min(float(wait), 60) if wait.replace(".", "", 1).isdigit() else min(2 ** attempt, 30))
                continue
            break
        if r.status_code != 200:
            raise Btc04eError(f"Coin Metrics HTTP {r.status_code}")
        pages.append(hashlib.sha256(r.content).hexdigest())
        raw_pages.append(bytes(r.content))
        page, nxt = parse_page(r.json())
        rows.extend(page)
        if nxt is None:
            break
        if nxt in seen:
            raise Btc04eError("repeated pagination URL")
        seen.add(nxt)
        url, params = nxt, None
        sleep(0.7)  # Community API: stay below the published request rate
    else:
        raise Btc04eError("pagination exceeded the page limit")
    daily, gaps = merge_rows(rows)
    if not daily:
        raise Btc04eError("Coin Metrics returned no PriceUSD observations")
    lo, hi = min(daily), max(daily)
    if lo < start or hi > end:
        raise Btc04eError("observations outside the requested range")
    return {"source": PROVIDER, "metric": METRIC, "url": BASE_URL, "query": query(start, end), "retrieved_at_utc": now().replace(microsecond=0).isoformat(),
            "pages": len(pages), "page_sha256": pages, "response_sha256": hashlib.sha256("".join(pages).encode()).hexdigest(),
            "first": lo, "last": hi, "n": len(daily), "provider_gaps": gaps, "daily": daily, "raw_pages": raw_pages}


# ------------------------------------------------------------------ validation (never fills)
def expected_days(first: str, last: str) -> list:
    d, end, out = date.fromisoformat(first), date.fromisoformat(last), []
    while d <= end:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def missing_days(daily: dict, last_day: str) -> list:
    have = set(daily)
    return [d for d in expected_days(min(daily), last_day) if d not in have]


def cut_to_complete(daily: dict, as_of: str) -> dict:
    """Drop the current (partial) UTC day and everything after: a candle is complete only strictly before `as_of`."""
    return {d: v for d, v in daily.items() if d < as_of}


def stale_runs(daily: dict, min_len=STALE_MIN_RUN) -> list:
    """Runs of identical consecutive daily values (informational: a flat price is not automatically invalid)."""
    out, prev, start, n = [], None, None, 0
    for d in sorted(daily):
        if daily[d] == prev and (date.fromisoformat(d) - date.fromisoformat(last)).days == 1:
            n += 1
        else:
            if n >= min_len:
                out.append({"first": start, "last": last, "days": n, "value": hm.dec_str(prev)})
            start, n = d, 1
        prev, last = daily[d], d
    if n >= min_len:
        out.append({"first": start, "last": last, "days": n, "value": hm.dec_str(prev)})
    return out


def quality_of_month(month: str) -> str:
    """Provisional research quality (QUALITY_VERSION): Q3 2010-08..2014-01, Q2 2014-02..2016-04, Q1 candidate from 2016-05."""
    if month < FIRST_SUPPORTED_MONTH:
        raise Btc04eError(f"{month}: before the first supported month {FIRST_SUPPORTED_MONTH}")
    return "Q3" if month <= "2014-01" else "Q2" if month <= "2016-04" else "Q1_CANDIDATE"


def target_holidays(year: int) -> set:
    """TARGET closing days (no ECB fixing): 1 Jan, Good Friday, Easter Monday, 1 May, 25/26 Dec (+31 Dec 1999-2001)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e, f = b // 4, b % 4, (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    el = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * el) // 451
    month, day = divmod(h + el - 7 * m + 114, 31)
    easter = date(year, month, day + 1)
    out = {date(year, 1, 1), easter - timedelta(days=2), easter + timedelta(days=1), date(year, 5, 1), date(year, 12, 25), date(year, 12, 26)}
    if year <= 2001:
        out.add(date(year, 12, 31))
    return out


def ecb_calendar_report(ecb: dict) -> dict:
    """Weekend fixings, TARGET holidays and UNEXPECTED missing business days in the ECB series (reported, never filled)."""
    first, last = date.fromisoformat(min(ecb)), date.fromisoformat(max(ecb))
    holidays = set().union(*(target_holidays(y) for y in range(first.year, last.year + 1)))
    weekend = sorted(d for d in ecb if date.fromisoformat(d).weekday() >= 5)
    unexpected, closed, cur = [], 0, first
    while cur <= last:
        if cur.weekday() < 5 and cur.isoformat() not in ecb:
            if cur in holidays:
                closed += 1
            else:
                unexpected.append(cur.isoformat())
        cur += timedelta(days=1)
    by_month = {}
    for d in unexpected:
        by_month[d[:7]] = by_month.get(d[:7], 0) + 1
    return {"weekend_days_with_rate": len(weekend), "target_holidays_missing": closed, "unexpected_missing_business_days": len(unexpected),
            "unexpected_in_validation_window": sum(n for m, n in by_month.items() if m <= RESEARCH_CUTOFF),
            "unexpected_sample": unexpected[:10], "unexpected_by_month": by_month}


def blocked_ecb_months(ecb: dict) -> list:
    """Months with at least one UNEXPECTED missing ECB business day: no complete-month FX mean may be formed for them."""
    return sorted(ecb_calendar_report(ecb)["unexpected_by_month"])


# ------------------------------------------------------------------ model construction
def cm_daily_series(daily: dict, raw_sha: str, acquired_at: str) -> hm.Series:
    if not daily:
        raise Btc04eError("no observations")
    rows = []
    for day in sorted(daily):
        v = daily[day]
        if isinstance(v, (float, bool)) or not isinstance(v, Decimal) or not v.is_finite() or v <= 0:
            raise Btc04eError(f"{day}: invalid PriceUSD value")
        if parse_day(day + "T00:00:00Z") != day:
            raise Btc04eError(f"noncanonical day {day!r}")
        flags = [METHOD_FLAG, COND_FLAG, RESEARCH_FLAG]
        if day[:7] >= FIRST_SUPPORTED_MONTH:
            flags.append(f"CM_{quality_of_month(day[:7])}")
        if day[:7] in EXCEPTIONS:
            flags.append(f"EXC:{EXCEPTIONS[day[:7]]}")
        rows.append(hm.Observation("cm_priceusd_daily", day, v, "USD", "USD_per_BTC", "coinmetrics_priceusd_daily_utc",
                                   "coinmetrics_community_priceusd", raw_sha, acquired_at, f"sha:{raw_sha[:12]}", "PROPOSED", tuple(flags)))
    s = hm.Series("cm_priceusd_daily", "source", "bitcoin", "daily", "USD", "USD_per_BTC", "coinmetrics_priceusd_daily_utc", "spot_price",
                  "nominal", None, (), tuple(rows))
    hm.validate_series(s)
    return s


def ecb_series(daily: dict, raw_sha: str, acquired_at: str) -> hm.Series:
    if not daily:
        raise Btc04eError("ecb: no observations")
    rows = tuple(hm.Observation("ecb_usd_per_eur_daily", d, v, "USD", "USD_per_EUR", "ecb_ref_usd_per_eur_daily", "ecb_exr_d_usd", raw_sha,
                                acquired_at, f"sha:{raw_sha[:12]}", "CONFIRMED", (METHOD_FLAG,)) for d, v in sorted(daily.items()))
    s = hm.Series("ecb_usd_per_eur_daily", "source", "fx", "daily", "USD", "USD_per_EUR", "ecb_ref_usd_per_eur_daily", "fx_rate", "nominal",
                  None, (), rows)
    hm.validate_series(s)
    return s


def build(cm: hm.Series, ecb: hm.Series, house: hm.Series) -> dict:
    """Monthly means (complete months only), USD-derived EUR equivalent (C1) and BTC/satoshi per house. All separate from BTC-03."""
    if house.kind != "average_price":
        raise Btc04eError(f"{house.series_id}: only the CBS mean house price is allowed (got {house.kind})")
    out = {"cm_priceusd_daily": cm, "ecb_usd_per_eur_daily": ecb}
    out["ecb_usd_per_eur_monthly"] = hm.monthly_mean(ecb, min_coverage=MIN_FX_COVERAGE, series_id="ecb_usd_per_eur_monthly",
                                                     complete_final_month=True)
    out["cm_priceusd_monthly"] = hm.monthly_mean(cm, min_coverage=Decimal(1), series_id="cm_priceusd_monthly")
    out["cm_btc_eur_equivalent_c1"] = hm.convert_currency(out["cm_priceusd_monthly"], out["ecb_usd_per_eur_monthly"], to_currency="EUR",
                                                          series_id="cm_btc_eur_equivalent_c1")
    out["cbs_btc_per_house_cm_c1"] = hm.btc_per_house(house, out["cm_btc_eur_equivalent_c1"], series_id="cbs_btc_per_house_cm_c1")
    out["cbs_sats_per_house_cm_c1"] = hm.sats_per_house(house, out["cm_btc_eur_equivalent_c1"], series_id="cbs_sats_per_house_cm_c1")
    return out


def month_eligibility(month: str, approvals=None) -> str:
    """Explicit month-level release eligibility. HOLD wins over everything; RELEASE_ELIGIBLE needs an explicit approval record."""
    approvals = RELEASE_APPROVALS if approvals is None else frozenset(approvals)
    if month in EXCEPTIONS:
        return "RESEARCH_ONLY_HOLD"
    if month < FIRST_SUPPORTED_MONTH:
        return "NONE"
    return "RELEASE_ELIGIBLE" if month in approvals else "RESEARCH_ONLY"


def candidate_values(built: dict, approved=None, series_id="cbs_btc_per_house_cm_c1") -> dict:
    """The ONLY export selector for public-candidate values: {month: value} for explicitly approved months.

    Nothing is selected by default. An approved month must have a value and must not be HOLD; June 2011 can never pass,
    whatever an approval list says. Research diagnostics read the series directly and never go through this boundary.
    """
    approved = RELEASE_APPROVALS if approved is None else frozenset(approved)
    values = {p.period: p.value for p in built[series_id].points if p.value is not None}
    out = {}
    for m in sorted(approved):
        if month_eligibility(m, approved) == "RESEARCH_ONLY_HOLD":
            raise Btc04eError(f"{m}: RESEARCH_ONLY_HOLD month cannot be a release candidate")
        if m not in values:
            raise Btc04eError(f"{m}: approved month has no value")
        out[m] = values[m]
    return out


def month_metadata(built: dict, daily: dict, corroboration: dict | None = None) -> dict:
    """Per-month research metadata: quality, completeness, stale runs, exception, corroboration availability, eligibility."""
    stats = H.monthly_stats(daily)
    flat = stale_runs(daily)
    stale_by_month = {}
    for run in flat:
        for d in expected_days(run["first"], run["last"]):
            stale_by_month[d[:7]] = max(stale_by_month.get(d[:7], 0), 0) + 1
    eur = {p.period: p.value for p in built["cm_btc_eur_equivalent_c1"].points}
    out = {}
    for m, st in stats.items():
        if m < FIRST_SUPPORTED_MONTH:
            out[m] = {"status": "UNSUPPORTED_EARLY_PERIOD", "daily_complete": False, "days": st["days"], "value": None,
                      "release_eligibility": "NONE"}
            continue
        exc = EXCEPTIONS.get(m)
        q = quality_of_month(m)
        value = eur.get(m)
        out[m] = {"quality": q, "source": f"{PROVIDER} {METRIC}", "native_quote": "USD", "usd_derived_eur_equivalent": True,
                  "daily_complete": st["complete"], "days": st["days"], "calendar_days": st["calendar_days"],
                  "stale_days": stale_by_month.get(m, 0), "exception": exc, "has_value": value is not None,
                  "corroboration": (corroboration or {}).get(m, {}),
                  "provider_methodology": "UNCERTAIN: PriceUSD is a provider reference price; its early-history construction is undocumented here",
                  "release_eligibility": month_eligibility(m)}
    return out


def chart_segments(built: dict) -> list:
    """Contiguous runs of months with a value. Split at every null and at every HOLD month (which is excluded): never connect across."""
    pts = built["cbs_btc_per_house_cm_c1"].points
    segs, cur = [], []
    for p in pts:
        usable = p.value is not None and month_eligibility(p.period) != "RESEARCH_ONLY_HOLD"
        if usable and cur and not _next_month(cur[-1], p.period):
            segs.append(cur)
            cur = []
        if usable:
            cur.append(p.period)
        elif cur:
            segs.append(cur)
            cur = []
    if cur:
        segs.append(cur)
    return [{"first": s[0], "last": s[-1], "n": len(s)} for s in segs]


def _next_month(a: str, b: str) -> bool:
    y, m = int(a[:4]), int(a[5:])
    return b == (f"{y + 1}-01" if m == 12 else f"{y}-{m + 1:02d}")


# ------------------------------------------------------------------ vintage pins, snapshot, replay
def derived_values_sha256(built: dict, cutoff=RESEARCH_CUTOFF) -> str:
    names = ("cm_priceusd_monthly", "ecb_usd_per_eur_monthly", "cm_btc_eur_equivalent_c1", "cbs_btc_per_house_cm_c1", "cbs_sats_per_house_cm_c1")
    lines = "".join(f"{n}|{p.period}|{'' if p.value is None else hm.dec_str(p.value)}\n" for n in names for p in built[n].points
                    if p.period <= cutoff)
    return hashlib.sha256(lines.encode()).hexdigest()


def source_windows(daily: dict) -> dict:
    return {n: h10.window_hash(daily[n], *PIN_WINDOWS[n]) for n in PIN_WINDOWS if n in daily}


def canonical_daily_sha256(daily: dict) -> str:
    return hashlib.sha256("".join(f"{d}:{hm.dec_str(v)}\n" for d, v in sorted(daily.items())).encode()).hexdigest()


def check_pins(current: dict, derived_hash: str, pins) -> dict:
    """MATCH / SOURCE_REVISED / DEFECT_DERIVED_DRIFT / METHOD_CHANGED / UNPINNED."""
    if not pins:
        return {"status": "UNPINNED", "sources": {k: "UNPINNED" for k in current}}
    versions = {"method_id": METHOD_ID, "parser_version": PARSER_VERSION, "exception_policy_version": EXCEPTION_POLICY_VERSION,
                "quality_version": QUALITY_VERSION}
    changed = {k: [pins.get(k), v] for k, v in versions.items() if pins.get(k) != v}
    if changed:
        return {"status": "METHOD_CHANGED", "changed": changed}
    per = {}
    for name, cur in current.items():
        pin = pins.get("sources", {}).get(name)
        per[name] = "UNPINNED" if not pin else "MATCH" if (pin["sha256"], pin["n"], pin["first"], pin["last"]) == (
            cur["sha256"], cur["n"], cur["first"], cur["last"]) else "REVISED"
    if "REVISED" in per.values() or "UNPINNED" in per.values():
        return {"status": "SOURCE_REVISED" if "REVISED" in per.values() else "UNPINNED", "sources": per}
    return {"status": "MATCH" if pins.get("derived", {}).get("values_sha256") == derived_hash else "DEFECT_DERIVED_DRIFT", "sources": per}


def load_pins(path):
    """Pin file or None. A missing file means UNPINNED (the first run creates the candidate); a corrupt file fails closed."""
    if not path or not Path(path).exists():
        return None
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Btc04eError(f"pin file unreadable: {type(exc).__name__}") from None
    if not isinstance(doc, dict):
        raise Btc04eError("pin file is not an object")
    return doc


def git_commit() -> str:
    env = os.environ.get("GITHUB_SHA")
    if env:
        return env
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def manifest(acq: dict, ecb_raw_sha: str, ecb_daily: dict, derived_hash: str, windows: dict, commit: str) -> dict:
    return {"method_id": METHOD_ID, "parser_version": PARSER_VERSION, "exception_policy_version": EXCEPTION_POLICY_VERSION,
            "quality_version": QUALITY_VERSION, "git_commit": commit, "status": "RESEARCH ONLY; conditionally accepted method; rights UNVERIFIED",
            "coinmetrics": {k: acq[k] for k in ("source", "metric", "url", "query", "retrieved_at_utc", "pages", "page_sha256", "response_sha256",
                                                "first", "last", "n", "provider_gaps")} | {"canonical_daily_sha256": canonical_daily_sha256(acq["daily"])},
            "ecb": {"observation_ref_sha256": ecb_raw_sha, "first": min(ecb_daily), "last": max(ecb_daily), "n": len(ecb_daily),
                    "canonical_daily_sha256": canonical_daily_sha256(ecb_daily)},
            "source_windows": windows, "derived_values_sha256": derived_hash,
            "note": "raw hashes identify the bytes of this run, they are not an archive; exact replay needs the private snapshot"}


def _normalized(daily: dict) -> str:
    return "".join(f"{k}:{hm.dec_str(v)}\n" for k, v in sorted(daily.items()))


def snapshot_id(man: dict, cut_before, derived_cutoff) -> str:
    """Identity of a vintage: method/parser/policy versions, both canonical input hashes and the derived hash. Not timestamps."""
    ident = {"method_id": man["method_id"], "parser_version": man["parser_version"], "exception_policy_version": man["exception_policy_version"],
             "quality_version": man["quality_version"], "cm": man["coinmetrics"]["canonical_daily_sha256"], "ecb": man["ecb"]["canonical_daily_sha256"],
             "derived": man["derived_values_sha256"], "cut_before": cut_before, "derived_cutoff": derived_cutoff}
    return "btc04e-" + hashlib.sha256(hm.canonical_json(ident)).hexdigest()[:16]


def export_snapshot(directory, *, cm_daily: dict, ecb_daily: dict, man: dict, raw_pages=None, cut_before=None,
                    derived_cutoff=RESEARCH_CUTOFF, cbs_input_sha256=None) -> dict:
    """Write a LOCAL vintage snapshot to an explicitly chosen directory. No upload, no network, never overwrites a snapshot.

    Layout: two normalized 'day:value' files, optional original CM response pages (gzip, mtime 0) and one manifest. The ECB response
    bytes are not retained by the acquisition code (only normalized values), which the manifest states. Never committed or uploaded.
    """
    d = Path(directory)
    if (d / SNAPSHOT_MANIFEST).exists():
        raise SnapshotError("EXISTS", f"{d} already holds a snapshot; choose a new directory")
    d.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, daily in ((CM_FILE, cm_daily), (ECB_FILE, ecb_daily)):
        body = _normalized(daily)
        (d / f"{name}.txt").write_text(body, encoding="utf-8")
        files[name] = {"file": f"{name}.txt", "sha256": hashlib.sha256(body.encode()).hexdigest(), "n": len(daily)}
    raw = {"cm_priceusd": [], "ecb": "NOT_RETAINED"}
    if raw_pages:
        (d / "raw").mkdir(exist_ok=True)
        for i, blob in enumerate(raw_pages):
            name = f"raw/cm_priceusd_page_{i:03d}.json.gz"
            (d / name).write_bytes(gzip.compress(blob, mtime=0))
            raw["cm_priceusd"].append({"file": name, "raw_sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob)})
    sid = snapshot_id(man, cut_before, derived_cutoff)
    doc = {"format": SNAPSHOT_FORMAT, "snapshot_id": sid, "files": files, "raw": raw, "cut_before": cut_before, "derived_cutoff": derived_cutoff,
           "cbs_input_sha256": cbs_input_sha256, "manifest": man}
    (d / SNAPSHOT_MANIFEST).write_bytes(hm.canonical_json(doc))
    return {"snapshot_id": sid, "bytes": {str(f.relative_to(d)): f.stat().st_size for f in sorted(d.rglob("*")) if f.is_file()}}


def write_snapshot(directory, daily_by_name: dict, man: dict, **options) -> dict:
    """Compatibility wrapper for the BTC-04E call style."""
    return export_snapshot(directory, cm_daily=daily_by_name[CM_FILE], ecb_daily=daily_by_name[ECB_FILE], man=man, **options)


def load_snapshot(directory) -> dict:
    """Import and verify a local snapshot. Any defect raises SnapshotError: there is never a fallback to live acquisition.

    Checks: manifest present/well-formed; code/method/parser/policy versions equal the running code; normalized files hash and count;
    canonical daily hashes vs manifest; original response pages hash, ordering and response id; raw pages re-parsed with the current parser
    must reproduce the normalized CM values; snapshot id recomputed.
    """
    d = Path(directory)
    try:
        doc = json.loads((d / SNAPSHOT_MANIFEST).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SnapshotError("MISSING", f"no {SNAPSHOT_MANIFEST} in {d}") from None
    except (OSError, ValueError) as exc:
        raise SnapshotError("CORRUPT", f"manifest unreadable ({type(exc).__name__})") from None
    try:
        if doc["format"] != SNAPSHOT_FORMAT:
            raise SnapshotError("CORRUPT", f"unknown snapshot format {doc['format']!r}")
        man = doc["manifest"]
        for key, now in (("method_id", METHOD_ID), ("parser_version", PARSER_VERSION), ("exception_policy_version", EXCEPTION_POLICY_VERSION),
                         ("quality_version", QUALITY_VERSION)):
            if man[key] != now:
                raise SnapshotError("METHOD_CHANGED", f"{key}: snapshot {man[key]!r}, code {now!r}")
        daily = {}
        for name, meta in doc["files"].items():
            try:
                body = (d / meta["file"]).read_text(encoding="utf-8")
            except FileNotFoundError:
                raise SnapshotError("MISSING", f"{meta['file']} is missing") from None
            if hashlib.sha256(body.encode()).hexdigest() != meta["sha256"]:
                raise SnapshotError("NORMALIZED_HASH_MISMATCH", f"{name}: file hash differs from the manifest")
            vals = {}
            for line in body.splitlines():
                day, _, rawv = line.partition(":")
                if day in vals:
                    raise SnapshotError("CORRUPT", f"{name}: duplicate day {day}")
                vals[day] = parse_price(rawv, day)
            if len(vals) != meta["n"]:
                raise SnapshotError("CORRUPT", f"{name}: observation count differs")
            daily[name] = vals
        for name, key in ((CM_FILE, "coinmetrics"), (ECB_FILE, "ecb")):
            if canonical_daily_sha256(daily[name]) != man[key]["canonical_daily_sha256"]:
                raise SnapshotError("NORMALIZED_HASH_MISMATCH", f"{name}: canonical daily hash differs from the manifest")
        pages = []
        entries = doc["raw"]["cm_priceusd"]
        if entries:
            hashes = []
            for e in entries:
                try:
                    blob = gzip.decompress((d / e["file"]).read_bytes())
                except FileNotFoundError:
                    raise SnapshotError("MISSING", f"{e['file']} is missing") from None
                except (OSError, EOFError, ValueError):
                    raise SnapshotError("CORRUPT", f"{e['file']} is not a valid gzip stream") from None
                if hashlib.sha256(blob).hexdigest() != e["raw_sha256"]:
                    raise SnapshotError("SOURCE_HASH_MISMATCH", f"{e['file']}: response bytes differ from the recorded hash")
                hashes.append(e["raw_sha256"])
                pages.append(blob)
            if hashes != man["coinmetrics"]["page_sha256"] or hashlib.sha256("".join(hashes).encode()).hexdigest() != man["coinmetrics"]["response_sha256"]:
                raise SnapshotError("SOURCE_HASH_MISMATCH", "response pages differ from the acquisition record")
            try:
                parsed, gaps = merge_rows([r for blob in pages for r in parse_page(json.loads(blob))[0]])
            except (ValueError, Btc04eError) as exc:
                raise SnapshotError("CORRUPT", f"raw pages do not parse: {str(exc)[:120]}") from None
            if doc["cut_before"]:
                parsed = cut_to_complete(parsed, doc["cut_before"])
            if parsed != daily[CM_FILE]:
                raise SnapshotError("NORMALIZED_HASH_MISMATCH", "normalized CM values are not what the stored response bytes produce")
        if snapshot_id(man, doc["cut_before"], doc["derived_cutoff"]) != doc["snapshot_id"]:
            raise SnapshotError("CORRUPT", "snapshot id does not match its content")
    except SnapshotError:
        raise
    except (KeyError, TypeError, AttributeError) as exc:
        raise SnapshotError("CORRUPT", f"manifest incomplete ({type(exc).__name__})") from None
    return {"cm_daily": daily[CM_FILE], "ecb_daily": daily[ECB_FILE], "man": man, "raw_pages": pages or None, "cut_before": doc["cut_before"],
            "derived_cutoff": doc["derived_cutoff"], "cbs_input_sha256": doc["cbs_input_sha256"], "snapshot_id": doc["snapshot_id"]}


def read_snapshot(directory) -> tuple:
    """BTC-04E call style: ({name: daily}, manifest), fully verified by load_snapshot."""
    snap = load_snapshot(directory)
    return {CM_FILE: snap["cm_daily"], ECB_FILE: snap["ecb_daily"]}, snap["man"]


def build_from_daily(cm_daily: dict, ecb_daily: dict, house: hm.Series, acquired_at: str, cm_raw="0" * 64, ecb_raw="0" * 64) -> dict:
    """Months with an unexpected missing ECB business day get no FX mean (null), never a mean of the remaining days."""
    blocked = set(blocked_ecb_months(ecb_daily))
    usable = {d: v for d, v in ecb_daily.items() if d[:7] not in blocked}
    return build(cm_daily_series(cm_daily, cm_raw, acquired_at), ecb_series(usable, ecb_raw, acquired_at), house)


def replay(directory, house: hm.Series, cbs_input_sha256=None) -> dict:
    """OFFLINE historical vintage replay: rebuild from the stored snapshot only (no provider request, no live fallback).

    IDENTICAL means the stored inputs reproduce the recorded derived hash. If the CBS input hash is given and differs from the one
    recorded at export, the result is CBS_INPUT_DIFFERS, never IDENTICAL.
    """
    snap = load_snapshot(directory)
    built = build_from_daily(snap["cm_daily"], snap["ecb_daily"], house, snap["man"]["coinmetrics"]["retrieved_at_utc"])
    got = derived_values_sha256(built, snap["derived_cutoff"])
    if cbs_input_sha256 is not None and snap["cbs_input_sha256"] not in (None, cbs_input_sha256):
        status = "CBS_INPUT_DIFFERS"
    else:
        status = "IDENTICAL" if got == snap["man"]["derived_values_sha256"] else "DIFFERENT"
    return {"status": status, "snapshot_id": snap["snapshot_id"], "derived_values_sha256": got,
            "raw_source_bytes": "RETAINED_AND_VERIFIED" if snap["raw_pages"] else "NOT_RETAINED"}


# ------------------------------------------------------------------ revision detection and monthly update (against a stored vintage)
def revision_report(old: dict, new: dict) -> dict:
    """Compare freshly acquired daily values with a stored vintage. The stored values are never replaced; only days are reported.

    UNCHANGED_HISTORY, NEW_OBSERVATIONS_ONLY (days after the stored window), HISTORICAL_REVISION (a stored day changed, or a day
    inside the stored window appeared that was not stored), MISSING_HISTORICAL (a stored day is absent now; wins over a revision).
    """
    if not old:
        raise Btc04eError("empty stored vintage")
    first, last = min(old), max(old)
    revised = sorted(d for d in old if d in new and new[d] != old[d])
    missing = sorted(d for d in old if d not in new)
    inserted = sorted(d for d in new if first <= d <= last and d not in old)
    after = sorted(d for d in new if d > last)
    status = ("MISSING_HISTORICAL" if missing else "HISTORICAL_REVISION" if (revised or inserted)
              else "NEW_OBSERVATIONS_ONLY" if after else "UNCHANGED_HISTORY")
    return {"status": status, "window": [first, last], "unchanged": len(old) - len(revised) - len(missing), "revised": len(revised),
            "missing": len(missing), "inserted_in_window": len(inserted), "new_after_window": len(after),
            "revised_days": revised[:10], "missing_days": missing[:10], "inserted_days": inserted[:10]}


def monthly_update_plan(old: dict, new: dict) -> dict:
    """Which COMPLETE calendar months a monthly update may add, given an unchanged history. Pins and the release gate are not touched."""
    rep = revision_report(old, new)
    base_complete = [m for m, st in H.monthly_stats(old).items() if st["complete"]]
    last_old = max(base_complete) if base_complete else None
    ok = rep["status"] in ("UNCHANGED_HISTORY", "NEW_OBSERVATIONS_ONLY")
    added = sorted(m for m, st in H.monthly_stats(new).items() if st["complete"] and (last_old is None or m > last_old)) if ok else []
    return {"history": rep["status"], "baseline_last_complete_month": last_old, "months_added": added,
            "processed": ok, "note": "" if ok else "history changed: no month is added until Project Control approves a new vintage",
            "pins": "UNCHANGED (this tool never writes pins)", "release_gate": "CLOSED" if not RELEASE_APPROVALS else "OPEN"}


# ------------------------------------------------------------------ independent numerical checks (exact Fractions)
def fr(x) -> Fraction:
    return Fraction(x) if not isinstance(x, Fraction) else x


def exact_month(cm_daily: dict, ecb_daily: dict, house_eur, month: str) -> dict:
    """Separate arithmetic path (Fraction, no Decimal context): plain sums over the raw dicts."""
    n = H.days_in_month(month)
    days = [f"{month}-{i:02d}" for i in range(1, n + 1)]
    if any(d not in cm_daily for d in days):
        return {"status": "NULL_INCOMPLETE_BTC_MONTH"}
    fx = [fr(v) for d, v in ecb_daily.items() if d[:7] == month]
    if not fx or Fraction(len(fx), n) < Fraction(MIN_FX_COVERAGE):
        return {"status": "NULL_FX_COVERAGE"}
    usd = sum(fr(cm_daily[d]) for d in days) / n
    eur = usd / (sum(fx) / len(fx))
    btc = fr(house_eur) / eur
    return {"status": "OK", "btc_usd_month": usd, "btc_eur": eur, "btc_per_house": btc, "sats_per_house": btc * int(SATS)}


def independent_check(cm_daily, ecb_daily, built: dict, house: hm.Series, months) -> dict:
    hv = {o.period: o.value for o in house.observations}
    model = {k: {p.period: p.value for p in built[k].points} for k in ("cm_btc_eur_equivalent_c1", "cbs_btc_per_house_cm_c1", "cbs_sats_per_house_cm_c1")}
    out = {}
    for m in months:
        if m not in hv:
            out[m] = {"status": "NO_CBS_MONTH"}
            continue
        ex = exact_month(cm_daily, ecb_daily, hv[m], m)
        if ex["status"] != "OK":
            out[m] = {"status": ex["status"], "model_value": None if model["cbs_btc_per_house_cm_c1"].get(m) is None else "UNEXPECTED_VALUE"}
            continue
        mb, ms = model["cbs_btc_per_house_cm_c1"].get(m), model["cbs_sats_per_house_cm_c1"].get(m)
        rel = lambda a, b: "None" if a is None else f"{float(abs(fr(a) / b - 1)):.3e}"  # noqa: E731
        out[m] = {"status": "OK", "btc_eur": f"{float(ex['btc_eur']):.4f}", "house_eur": str(hv[m]),
                  "btc_per_house_exact": f"{float(ex['btc_per_house']):.10f}", "sats_per_house_exact": f"{float(ex['sats_per_house']):.4f}",
                  "btc_rel_diff": rel(mb, ex["btc_per_house"]), "sats_rel_diff": rel(ms, ex["sats_per_house"]),
                  "note": "same input bytes: arithmetic check only, not market-price validation"}
    return out


# ------------------------------------------------------------------ corroboration against Bitstamp (small, live) and BTC-03 evidence
def corroboration(cm_daily, ecb_daily, bsu, bse) -> dict:
    cm_usd = b3.a1_months(cm_daily)
    c1 = b3.c1_months(cm_daily, ecb_daily)
    res = {"cm_priceusd_vs_bitstamp_usd_a1": b3.rel_stats(cm_usd, b3.a1_months(bsu)),
           "cm_c1_vs_bitstamp_eur_native": b3.rel_stats(c1, b3.a1_months(bse))}
    for label, lo, hi in (("q3_2011-09_2014-01", "2011-09", "2014-01"), ("q2_2014-02_2016-04", "2014-02", "2016-04"), ("q1c_2016-05_on", "2016-05", "2099-12")):
        res[f"usd_{label}"] = b3.rel_stats({m: v for m, v in cm_usd.items() if lo <= m <= hi}, {m: v for m, v in b3.a1_months(bsu).items() if lo <= m <= hi})
    over = {}
    ref = b3.a1_months(bsu)
    for m in sorted(set(cm_usd) & set(ref)):
        dev = abs(cm_usd[m] / ref[m] - 1)
        if dev > Fraction(1, 100):
            over[m] = f"{float(dev * 100):.2f}"
    res["usd_months_over_1pct"] = {"n": len(over), "over_5pct": [m for m, v in over.items() if float(v) > 5], "sample": dict(list(over.items())[:12])}
    res["independence_note"] = ("Bitstamp USD/EUR and Coin Metrics may share underlying exchange data; both derived series use the same ECB fixings; "
                                "Mt. Gox/Kraken corroboration is NOT re-run here and stays as recorded in BTC-02/BTC-03.")
    return res


def corroboration_flags(cm_daily, bsu, bse) -> dict:
    a, u, e = set(b3.a1_months(cm_daily)), set(b3.a1_months(bsu)), set(b3.a1_months(bse))
    return {m: {"bitstamp_usd": m in u, "bitstamp_eur_native": m in e} for m in a}


# ------------------------------------------------------------------ real-data run (GitHub Actions only)
def run(args):  # noqa: C901
    import requests
    from tools import btc_02_probe as P
    import contextlib
    import io
    baseline = load_snapshot(args.baseline_snapshot) if args.baseline_snapshot else None  # a bad baseline stops the run before any request
    notes = io.StringIO()
    now = datetime.now(timezone.utc)
    as_of = now.date().isoformat()
    end = (now.date() - timedelta(days=1)).isoformat()
    s = requests.Session()
    s.headers["User-Agent"] = "btc-04e-validation/1 (read-only research)"
    acq = fetch_priceusd(s, start="2010-07-18", end=end)
    cm_daily = cut_to_complete(acq["daily"], as_of)
    with contextlib.redirect_stdout(notes):
        ecb = P.fetch_ecb()
        usd, _ = P.fetch_bitstamp("btcusd", "USD")
        eur, _ = P.fetch_bitstamp("btceur", "EUR")
    if ecb is None or usd is None or eur is None:
        return {"status": "INCOMPLETE", "missing_sources": [n for n, v in (("ecb", ecb), ("bitstamp_usd", usd), ("bitstamp_eur", eur)) if v is None],
                "method_id": METHOD_ID}
    ecb_daily, bsu, bse = ecb.as_dict(), usd.as_dict(), eur.as_dict()
    ecb_raw = hashlib.sha256(canonical_daily_sha256(ecb_daily).encode()).hexdigest()
    acquired_at = acq["retrieved_at_utc"]
    house = hb.cbs_2000_series(args.cbs_csv)
    gaps = missing_days(cm_daily, max(cm_daily))
    built = build_from_daily(cm_daily, ecb_daily, house, acquired_at, acq["response_sha256"], ecb_raw)
    again = build_from_daily(cm_daily, ecb_daily, house, acquired_at, acq["response_sha256"], ecb_raw)
    derived_hash = derived_values_sha256(built)
    windows = source_windows({"cm_priceusd_daily": cm_daily, "ecb_usd_per_eur_daily": ecb_daily})
    pins = load_pins(args.pins)
    man = manifest(acq, ecb_raw, ecb_daily, derived_hash, windows, git_commit())
    R = {"caveat": "research only; method conditionally accepted for research; nothing published; rights UNVERIFIED; no raw data stored",
         "method_id": METHOD_ID, "missing_sources": [], "acquisition": {k: v for k, v in acq.items() if k not in ("daily", "raw_pages")},
         "observations_used": {"first": min(cm_daily), "last": max(cm_daily), "n": len(cm_daily), "missing_calendar_days": len(gaps), "missing_sample": gaps[:10]},
         "rebuild_identical": derived_values_sha256(again) == derived_hash, "derived_values_sha256": derived_hash,
         "vintage_check": check_pins(windows, derived_hash, pins), "pins_candidate": {
             "method_id": METHOD_ID, "parser_version": PARSER_VERSION, "exception_policy_version": EXCEPTION_POLICY_VERSION,
             "quality_version": QUALITY_VERSION, "pinned_on": as_of, "sources": windows,
             "derived": {"values_sha256": derived_hash, "cutoff": RESEARCH_CUTOFF}}, "manifest": man}
    coverage = {n: {"first": next((p.period for p in built[n].points if p.value is not None), None),
                    "last": next((p.period for p in reversed(built[n].points) if p.value is not None), None),
                    "n": sum(1 for p in built[n].points if p.value is not None), "n_null": sum(1 for p in built[n].points if p.value is None),
                    "null_sample": [p.period for p in built[n].points if p.value is None][:8]}
                for n in ("cm_priceusd_monthly", "ecb_usd_per_eur_monthly", "cm_btc_eur_equivalent_c1", "cbs_btc_per_house_cm_c1", "cbs_sats_per_house_cm_c1")}
    R["coverage"] = coverage
    R["quality_months"] = {q: sum(1 for p in built["cbs_btc_per_house_cm_c1"].points if p.value is not None and quality_of_month(p.period) == q)
                           for q in ("Q3", "Q2", "Q1_CANDIDATE")}
    R["chart_segments"] = chart_segments(built)
    R["june_2011"] = month_metadata(built, cm_daily).get("2011-06")
    R["stale_runs"] = stale_runs(cm_daily)[:25]
    R["ecb_calendar"] = ecb_calendar_report(ecb_daily)
    latest = max((p.period for p in built["cbs_btc_per_house_cm_c1"].points if p.value is not None), default=None)
    R["independent"] = independent_check(cm_daily, ecb_daily, built, house, INDEPENDENT_MONTHS + ((latest,) if latest else ()))
    R["corroboration"] = corroboration(cm_daily, ecb_daily, bsu, bse)
    meta = month_metadata(built, cm_daily, corroboration_flags(cm_daily, bsu, bse))
    R["quality_metadata_sample"] = {m: meta[m] for m in ("2010-08", "2011-06", "2014-02", "2016-05") if m in meta}
    # local snapshot: explicit path, or a private temp directory on the runner that is never uploaded and disappears with it
    cbs_sha = hashlib.sha256(Path(args.cbs_csv).read_bytes()).hexdigest()
    snap = Path(args.export_snapshot) if args.export_snapshot else Path(tempfile.mkdtemp(prefix="btc-04e-private-snapshot-", dir=os.environ.get("RUNNER_TEMP")))
    exported = export_snapshot(snap, cm_daily=cm_daily, ecb_daily=ecb_daily, man=man, raw_pages=acq["raw_pages"], cut_before=as_of,
                               derived_cutoff=RESEARCH_CUTOFF, cbs_input_sha256=cbs_sha)
    R["snapshot"] = {"snapshot_id": exported["snapshot_id"], "bytes": exported["bytes"], "total_bytes": sum(exported["bytes"].values()),
                     "location": "explicit path" if args.export_snapshot else "private runner temp (not uploaded)", "durable_storage": "OPEN"}
    R["replay_from_private_snapshot"] = replay(snap, house, cbs_sha)
    R["replay_limit"] = ("Historical vintage replay needs the stored snapshot. The repository keeps window hashes and the derived hash only: they "
                         "detect a revision but cannot reconstruct the original bytes. Durable private storage is OPEN.")
    if baseline:
        R["revision_detection"] = revision_report(baseline["cm_daily"], cm_daily)
        R["monthly_update"] = monthly_update_plan(baseline["cm_daily"], cm_daily) | {"baseline_snapshot_id": baseline["snapshot_id"],
                                                                                       "new_vintage_snapshot_id": exported["snapshot_id"]}
    R["source_notes"] = [ln[:200] for ln in notes.getvalue().splitlines() if ln.strip()][:12]
    return R  # main() applies finalize(): status and exit code are decided in one place


def finalize(R: dict, mode: str) -> dict:
    """Decide the run status. Normal validation fails closed on any vintage status except MATCH; bootstrap is explicit."""
    if mode not in MODES:
        raise Btc04eError(f"unknown mode {mode!r}")
    failures = []
    vintage = (R.get("vintage_check") or {}).get("status")
    if mode == "validate" and vintage != "MATCH":
        failures.append(f"vintage_check {vintage} (normal validation requires MATCH)")
    if (R.get("replay_from_private_snapshot") or {}).get("status") != "IDENTICAL":
        failures.append("private-snapshot replay is not IDENTICAL")
    if R.get("rebuild_identical") is not True:
        failures.append("rebuild is not identical")
    rev = (R.get("revision_detection") or {}).get("status")
    if mode == "validate" and rev in ("HISTORICAL_REVISION", "MISSING_HISTORICAL"):
        failures.append(f"revision_detection {rev}: stored history is never replaced automatically")
    cal = R.get("ecb_calendar") or {}
    if cal.get("unexpected_in_validation_window", 1) != 0:
        failures.append(f"unexpected missing ECB business days in the validation window: {cal.get('unexpected_in_validation_window')}")
    if cal.get("weekend_days_with_rate", 1) != 0:
        failures.append(f"ECB fixings on weekend days: {cal.get('weekend_days_with_rate')}")
    R["mode"], R["failures"] = mode, failures
    R["status"] = "VALIDATION_FAILED" if failures else ("COMPLETE_RESEARCH" if mode == "validate" else "BOOTSTRAP_PINS_CANDIDATE")
    return R


def main(argv=None):
    ap = argparse.ArgumentParser(description="BTC-04E Coin Metrics validation (research only)")
    ap.add_argument("--cbs-csv")
    ap.add_argument("--pins")
    ap.add_argument("--mode", choices=MODES, default="validate",
                    help="validate (default): fail closed unless the pins MATCH; bootstrap: explicit research mode for generating pins")
    ap.add_argument("--export-snapshot", help="explicit new directory for the local vintage snapshot (never uploaded, never overwritten)")
    ap.add_argument("--baseline-snapshot", help="stored vintage to compare against (revision detection and monthly update plan)")
    ap.add_argument("--replay-snapshot", help="OFFLINE replay of a stored vintage: no provider request, no live fallback")
    ap.add_argument("--summary-out")
    ap.add_argument("--print-summary")
    ap.add_argument("--keys", default="")
    a = ap.parse_args(argv)
    if a.print_summary:
        S = json.loads(Path(a.print_summary).read_text())
        for key in [k for k in a.keys.split(",") if k]:
            node = S
            for part in key.split("."):
                node = node.get(part) if isinstance(node, dict) else None
            print("SUMMARY", key, json.dumps(node, sort_keys=True, default=str)[:7000])
        return 0
    if a.replay_snapshot:
        if not a.cbs_csv:
            ap.error("--replay-snapshot needs --cbs-csv")
        try:
            res = replay(a.replay_snapshot, hb.cbs_2000_series(a.cbs_csv), hashlib.sha256(Path(a.cbs_csv).read_bytes()).hexdigest())
        except (hm.ModelError, Btc04eError, OSError) as exc:
            print("DEFECT", type(exc).__name__, str(exc)[:300])
            return 1
        print("REPLAY", json.dumps(res, sort_keys=True))
        return 0 if res["status"] == "IDENTICAL" else 1
    if not (a.summary_out and a.cbs_csv):
        ap.error("--summary-out and --cbs-csv are required")
    out = Path(a.summary_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        R = run(a)
    except (hm.ModelError, Btc04eError, H.HistoryError, OSError) as exc:
        out.write_text(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}: {str(exc)[:400]}"}, indent=1) + "\n")
        print("DEFECT", type(exc).__name__, str(exc)[:400])
        return 1
    if R.get("status") != "INCOMPLETE":
        R = finalize(R, a.mode)
    out.write_text(json.dumps(R, indent=1, sort_keys=True, default=str) + "\n")
    print("STATUS", R["status"], "mode", R.get("mode"), "failures", R.get("failures"), "missing", R.get("missing_sources"))
    return 0 if R["status"] in OK_STATUSES else 1


if __name__ == "__main__":
    sys.exit(main())
