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
import hashlib
import json
import os
import re
import subprocess
import sys
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
TIME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})T00:00:00(?:\.0+)?Z$")
INDEPENDENT_MONTHS = ("2010-08", "2011-06", "2013-01", "2014-02", "2016-05", "2017-12")
RETRIES, RETRY_STATUS = 5, {429, 500, 502, 503, 504}


class Btc04eError(hm.ModelError):
    """Input or consistency defect: fail closed."""


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
    url, params, rows, pages, seen = BASE_URL, query(start, end), [], [], set()
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
            "first": lo, "last": hi, "n": len(daily), "provider_gaps": gaps, "daily": daily}


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
            "unexpected_sample": unexpected[:10], "unexpected_by_month": by_month}


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
                  "release_eligibility": "RESEARCH_ONLY_HOLD" if exc else "RESEARCH_ONLY"}
    return out


def chart_segments(built: dict) -> list:
    """Contiguous runs of months with a value. Split at every null and at every HOLD month (which is excluded): never connect across."""
    pts = built["cbs_btc_per_house_cm_c1"].points
    segs, cur = [], []
    for p in pts:
        usable = p.value is not None and p.period not in EXCEPTIONS
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
            "ecb": {"raw_sha256": ecb_raw_sha, "first": min(ecb_daily), "last": max(ecb_daily), "n": len(ecb_daily),
                    "canonical_daily_sha256": canonical_daily_sha256(ecb_daily)},
            "source_windows": windows, "derived_values_sha256": derived_hash,
            "note": "raw hashes identify the bytes of this run, they are not an archive; exact replay needs the private snapshot"}


def write_snapshot(directory, daily_by_name: dict, man: dict) -> None:
    """PRIVATE replay snapshot (canonical 'day:value' lines + manifest with file hashes). Never committed or uploaded."""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, daily in daily_by_name.items():
        body = "".join(f"{k}:{hm.dec_str(v)}\n" for k, v in sorted(daily.items()))
        (d / f"{name}.txt").write_text(body, encoding="utf-8")
        files[name] = {"file": f"{name}.txt", "sha256": hashlib.sha256(body.encode()).hexdigest(), "n": len(daily)}
    (d / "snapshot_manifest.json").write_bytes(hm.canonical_json({"files": files, "manifest": man}))


def read_snapshot(directory) -> tuple:
    """Fail closed on a missing, truncated, corrupted or inconsistent snapshot."""
    d = Path(directory)
    try:
        doc = json.loads((d / "snapshot_manifest.json").read_text(encoding="utf-8"))
        out = {}
        for name, meta in doc["files"].items():
            body = (d / meta["file"]).read_text(encoding="utf-8")
            if hashlib.sha256(body.encode()).hexdigest() != meta["sha256"]:
                raise Btc04eError(f"snapshot {name}: hash mismatch")
            daily = {}
            for line in body.splitlines():
                day, _, raw = line.partition(":")
                if day in daily:
                    raise Btc04eError(f"snapshot {name}: duplicate day {day}")
                daily[day] = parse_price(raw, day)
            if len(daily) != meta["n"]:
                raise Btc04eError(f"snapshot {name}: observation count mismatch")
            out[name] = daily
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise Btc04eError(f"snapshot unreadable: {type(exc).__name__}") from None
    return out, doc["manifest"]


def build_from_daily(cm_daily: dict, ecb_daily: dict, house: hm.Series, acquired_at: str, cm_raw="0" * 64, ecb_raw="0" * 64) -> dict:
    return build(cm_daily_series(cm_daily, cm_raw, acquired_at), ecb_series(ecb_daily, ecb_raw, acquired_at), house)


def replay(directory, house: hm.Series) -> dict:
    """Rebuild from the private snapshot and compare with the recorded derived-values hash."""
    daily, man = read_snapshot(directory)
    built = build_from_daily(daily["cm_priceusd_daily"], daily["ecb_usd_per_eur_daily"], house, man["coinmetrics"]["retrieved_at_utc"])
    got = derived_values_sha256(built)
    return {"status": "IDENTICAL" if got == man["derived_values_sha256"] else "DIFFERENT", "derived_values_sha256": got}


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
    pins = json.loads(Path(args.pins).read_text(encoding="utf-8")) if args.pins else None
    man = manifest(acq, ecb_raw, ecb_daily, derived_hash, windows, git_commit())
    R = {"caveat": "research only; method conditionally accepted for research; nothing published; rights UNVERIFIED; no raw data stored",
         "method_id": METHOD_ID, "missing_sources": [], "acquisition": {k: v for k, v in acq.items() if k != "daily"},
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
    # private replay check: the snapshot lives in a runner temp directory, is never uploaded and is removed with the runner
    snap = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "btc-04e-private-snapshot"
    write_snapshot(snap, {"cm_priceusd_daily": cm_daily, "ecb_usd_per_eur_daily": ecb_daily}, man)
    R["replay_from_private_snapshot"] = replay(snap, house)
    R["replay_limit"] = ("Exact replay of this run is possible only with the private snapshot; the repository keeps window hashes and the derived hash, "
                         "so a later run can detect revisions but cannot reconstruct the original bytes.")
    R["status"] = "COMPLETE_RESEARCH"
    R["source_notes"] = [ln[:200] for ln in notes.getvalue().splitlines() if ln.strip()][:12]
    return R


def main(argv=None):
    ap = argparse.ArgumentParser(description="BTC-04E Coin Metrics validation (research only)")
    ap.add_argument("--cbs-csv")
    ap.add_argument("--pins")
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
    if not (a.summary_out and a.cbs_csv):
        ap.error("--summary-out and --cbs-csv are required")
    out = Path(a.summary_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        R = run(a)
    except (hm.ModelError, Btc04eError, H.HistoryError) as exc:
        out.write_text(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}: {str(exc)[:400]}"}, indent=1) + "\n")
        print("DEFECT", type(exc).__name__, str(exc)[:400])
        return 1
    out.write_text(json.dumps(R, indent=1, sort_keys=True, default=str) + "\n")
    print("STATUS", R["status"], "missing", R["missing_sources"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
