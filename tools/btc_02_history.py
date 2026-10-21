"""BTC-02: pure, testable reconstruction and validation of a monthly BTC/EUR research series.

RESEARCH ONLY. Nothing here publishes anything; `request_publication` always refuses.
Rules (see docs/research/BTC_02_HISTORY.md): Decimal arithmetic, no float, no forward fill, no interpolation,
no automatic splice between sources, missing market history stays None with a reason, a month is "complete"
only when every calendar day of that month has an observation, display rounding is not done here.
"""
import calendar
import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, getcontext

getcontext().prec = 28
SATS_PER_BTC = Decimal(10) ** 8
CURRENCIES = ("USD", "EUR")

# Quality levels (PROPOSED, see the report). Thresholds are parameters, never hidden constants in logic.
Q1, Q2, Q3, Q0 = "Q1", "Q2", "Q3", "Q0"
DEFAULT_LIQUID_USD_NOTIONAL_PER_DAY = Decimal("1000000")


class HistoryError(ValueError):
    """Any validation failure; the CLI fails closed on it."""


class HashMismatch(HistoryError):
    pass


class PublicationRefused(HistoryError):
    pass


@dataclass(frozen=True)
class DailySeries:
    """Daily observations of one pair at one source. `currency` is the quote currency of the BTC price."""
    source: str
    currency: str
    rows: tuple  # ((YYYY-MM-DD, Decimal), ...) strictly ascending

    def as_dict(self):
        return dict(self.rows)


def _to_decimal(value, what):
    if isinstance(value, (float, bool)):
        raise HistoryError(f"{what}: float/bool input refused, pass str or Decimal")
    try:
        d = Decimal(value if isinstance(value, Decimal) else str(value))
    except InvalidOperation:
        raise HistoryError(f"{what}: not a number: {value!r}")
    if not d.is_finite():
        raise HistoryError(f"{what}: not finite")
    return d


def _canonical_day(day):
    try:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError
    except (ValueError, TypeError):
        raise HistoryError(f"noncanonical date: {day!r}")
    return day


def parse_daily(rows, *, source, currency):
    """Validate (day, price) pairs in input order: canonical dates, strictly ascending (so no duplicates,
    no unordered input), positive finite prices. Returns a DailySeries. Never sorts, dedups or repairs."""
    if currency not in CURRENCIES:
        raise HistoryError(f"unknown currency {currency!r}")
    out, prev = [], None
    for day, price in rows:
        day = _canonical_day(day)
        if prev is not None and day == prev:
            raise HistoryError(f"duplicate day {day}")
        if prev is not None and day < prev:
            raise HistoryError(f"unordered day {day} after {prev}")
        value = _to_decimal(price, f"{source} {day}")
        if value <= 0:
            raise HistoryError(f"non-positive price on {day}")
        out.append((day, value))
        prev = day
    if not out:
        raise HistoryError(f"{source}: no observations")
    return DailySeries(source, currency, tuple(out))


def verify_sha256(raw, expected):
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise HashMismatch(f"sha256 mismatch: expected {expected}, got {actual}")
    return actual


def month_of(day):
    return day[:7]


def days_in_month(month):
    y, m = int(month[:4]), int(month[5:7])
    return calendar.monthrange(y, m)[1]


def months_between(first, last):
    y, m = int(first[:4]), int(first[5:7])
    ly, lm = int(last[:4]), int(last[5:7])
    out = []
    while (y, m) <= (ly, lm):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def missing_days(days, first=None, last=None):
    """Calendar days absent between first and last (default: the span of `days`). Reported, never filled."""
    days = sorted(days)
    if not days:
        return []
    lo, hi = date.fromisoformat(first or days[0]), date.fromisoformat(last or days[-1])
    have = set(days)
    out, cur = [], lo
    while cur <= hi:
        if cur.isoformat() not in have:
            out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def monthly_stats(daily):
    """Per month: observed days, calendar days, complete (all calendar days present), mean of the observed
    values (Decimal, unrounded). A partial month is never complete. `daily` is dict day->Decimal."""
    groups = {}
    for day, value in daily.items():
        groups.setdefault(month_of(day), []).append(value)
    return {m: {"days": len(v), "calendar_days": days_in_month(m), "complete": len(v) == days_in_month(m),
                "mean": sum(v) / len(v)} for m, v in sorted(groups.items())}


def complete_monthly_mean(series):
    """{month: mean of daily closes} for complete months only; others are absent (callers record a reason)."""
    return {m: s["mean"] for m, s in monthly_stats(series.as_dict()).items() if s["complete"]}


def _row(month, variant, value, reason, **extra):
    r = {"month": month, "variant": variant, "value": value, "reason": reason}
    r.update(extra)
    return r


def v3_native_eur(eur):
    """V3: mean of daily EUR-native closes in complete months. EUR input required."""
    if eur.currency != "EUR":
        raise HistoryError("V3 needs an EUR-quoted series")
    stats = monthly_stats(eur.as_dict())
    first, last = min(stats), max(stats)
    return [_row(m, "V3", stats[m]["mean"] if m in stats and stats[m]["complete"] else None,
                 None if m in stats and stats[m]["complete"] else
                 ("PARTIAL_MONTH" if m in stats else "NO_DATA"),
                 days=stats.get(m, {}).get("days", 0)) for m in months_between(first, last)]


def _fx_monthly(fx):
    """Mean of valid ECB USD-per-EUR days per month and their count. Missing ECB days stay missing."""
    groups = {}
    for day, rate in fx.rows:
        groups.setdefault(month_of(day), []).append(rate)
    return {m: (sum(v) / len(v), len(v)) for m, v in groups.items()}


def v1_ratio_of_means(usd, fx, *, min_fx_days=1):
    """V1 (ADR-004 style): complete-month mean of USD closes / mean of valid ECB USD-per-EUR days.
    USD input required; fx is USD per EUR. Months with no complete USD month or too few FX days -> None."""
    if usd.currency != "USD":
        raise HistoryError("V1 needs a USD-quoted series (USD/EUR confusion refused)")
    if fx.currency != "USD":
        raise HistoryError("FX must be USD per EUR (currency tag USD)")
    stats, fxm = monthly_stats(usd.as_dict()), _fx_monthly(fx)
    out = []
    for m in months_between(min(stats), max(stats)):
        s = stats.get(m)
        if s is None:
            out.append(_row(m, "V1", None, "NO_DATA"))
        elif not s["complete"]:
            out.append(_row(m, "V1", None, "PARTIAL_MONTH", days=s["days"]))
        elif m not in fxm or fxm[m][1] < min_fx_days:
            out.append(_row(m, "V1", None, "NO_FX", days=s["days"]))
        else:
            out.append(_row(m, "V1", s["mean"] / fxm[m][0], None, days=s["days"], fx_days=fxm[m][1]))
    return out


def v2_matched_day(usd, fx):
    """V2: mean of daily usd/fx on days where BOTH exist (no carry-forward). It silently covers weekdays only,
    so `complete` is True only if every calendar day matched (practically never); value is still reported
    as a research variant with its coverage."""
    if usd.currency != "USD" or fx.currency != "USD":
        raise HistoryError("V2 needs USD price and USD-per-EUR FX")
    ud, fd = usd.as_dict(), fx.as_dict()
    groups = {}
    for day in sorted(set(ud) & set(fd)):
        groups.setdefault(month_of(day), []).append(ud[day] / fd[day])
    ustats = monthly_stats(ud)
    out = []
    for m in months_between(min(ustats), max(ustats)):
        v = groups.get(m)
        if not v:
            out.append(_row(m, "V2", None, "NO_MATCHED_DAYS"))
        else:
            cal = days_in_month(m)
            out.append(_row(m, "V2", sum(v) / len(v), None if len(v) == cal else "MATCHED_DAYS_ONLY",
                            matched_days=len(v), calendar_days=cal, complete=len(v) == cal))
    return out


def classify_quality(*, eur_native_complete, usd_derived_complete, mean_daily_usd_notional,
                     liquid_threshold=DEFAULT_LIQUID_USD_NOTIONAL_PER_DAY):
    """PROPOSED levels. Q1 EUR-native complete month and liquid; Q2 USD-derived (V1) complete and liquid;
    Q3 any complete month but thin (or notional unknown): research only; Q0 nothing complete -> value null.
    A native complete month that is thin is Q3, not Q1."""
    if not (eur_native_complete or usd_derived_complete):
        return Q0
    liquid = mean_daily_usd_notional is not None and mean_daily_usd_notional >= liquid_threshold
    if not liquid:
        return Q3
    return Q1 if eur_native_complete else Q2


def build_monthly(eur_native, usd_v1, notional, *, liquid_threshold=DEFAULT_LIQUID_USD_NOTIONAL_PER_DAY):
    """Combine per-month candidates of ONE explicit source pair into rows with a quality level. Both inputs are
    row lists from v3_native_eur / v1_ratio_of_means. The EUR-native value is preferred where complete;
    otherwise the V1 value is used and labelled. No other source is consulted: no splice, no fill."""
    nat = {r["month"]: r for r in (eur_native or [])}
    der = {r["month"]: r for r in (usd_v1 or [])}
    months = sorted(set(nat) | set(der))
    if not months:
        raise HistoryError("no months")
    out = []
    for m in months_between(months[0], months[-1]):
        n, d = nat.get(m), der.get(m)
        n_ok = bool(n and n["value"] is not None)
        d_ok = bool(d and d["value"] is not None)
        q = classify_quality(eur_native_complete=n_ok, usd_derived_complete=d_ok,
                             mean_daily_usd_notional=notional.get(m), liquid_threshold=liquid_threshold)
        if q == Q0:
            reasons = sorted({x["reason"] for x in (n, d) if x and x["reason"]}) or ["NO_DATA"]
            out.append({"month": m, "btc_eur": None, "basis": None, "quality": Q0, "reason": "+".join(reasons)})
        else:
            out.append({"month": m, "btc_eur": n["value"] if n_ok else d["value"],
                        "basis": "V3_EUR_NATIVE" if n_ok else "V1_USD_RATIO_OF_MEANS",
                        "quality": q, "reason": None})
    return out


def assemble(monthly_by_source, plan):
    """Explicit owner plan only: plan = [(first_month, last_month, source)]. The value of a month is taken
    from its planned source ONLY; if that source is null the month is null (no fallback to another source).
    Without a plan, or with overlapping plan ranges, this refuses: there is no automatic splice."""
    if not plan:
        raise HistoryError("no splice plan: automatic splicing is refused")
    covered = {}
    for first, last, source in plan:
        if source not in monthly_by_source:
            raise HistoryError(f"unknown source in plan: {source}")
        for m in months_between(first, last):
            if m in covered:
                raise HistoryError(f"overlapping plan ranges at {m}")
            covered[m] = source
    out = []
    for m in sorted(covered):
        src = covered[m]
        row = monthly_by_source[src].get(m)
        if row is None or row.get("btc_eur") is None:
            out.append({"month": m, "btc_eur": None, "source": src, "quality": Q0,
                        "reason": (row or {}).get("reason") or "NO_DATA_IN_PLANNED_SOURCE"})
        else:
            out.append({"month": m, "btc_eur": row["btc_eur"], "source": src, "quality": row["quality"],
                        "reason": None})
    return out


def matched_day_means(a, b, *, min_days):
    """Monthly means of two dict day->Decimal computed over the days present in BOTH (no fill). Months with
    fewer than `min_days` common days are dropped. Returns (mean_a, mean_b, common_days)."""
    groups = {}
    for day in sorted(set(a) & set(b)):
        groups.setdefault(month_of(day), []).append(day)
    ma, mb, cd = {}, {}, {}
    for m, ds in groups.items():
        if len(ds) >= min_days:
            ma[m] = sum(a[d] for d in ds) / len(ds)
            mb[m] = sum(b[d] for d in ds) / len(ds)
            cd[m] = len(ds)
    return ma, mb, cd


def percentile(sorted_values, p):
    """Nearest-rank percentile (deterministic, no interpolation). p in (0, 100]."""
    if not sorted_values:
        raise HistoryError("empty sample")
    k = max(1, -(-len(sorted_values) * p // 100))
    return sorted_values[int(k) - 1]


def compare_monthly(a, b):
    """Relative deviation |a-b|/b over months present (non-None) in both dicts month->Decimal.
    Returns {n, max, max_month, mean, p50, p90, p95, p99, over_1pct, over_5pct, deviations}."""
    devs = {}
    for m in sorted(set(a) & set(b)):
        if a[m] is None or b[m] is None:
            continue
        if b[m] <= 0:
            raise HistoryError("non-positive reference")
        devs[m] = abs(a[m] - b[m]) / b[m]
    if not devs:
        return {"n": 0}
    vals = sorted(devs.values())
    worst = max(devs, key=lambda k: (devs[k], k))
    return {"n": len(vals), "max": vals[-1], "max_month": worst, "mean": sum(vals) / len(vals),
            "p50": percentile(vals, 50), "p90": percentile(vals, 90), "p95": percentile(vals, 95),
            "p99": percentile(vals, 99), "over_1pct": sum(v > Decimal("0.01") for v in vals),
            "over_5pct": sum(v > Decimal("0.05") for v in vals), "deviations": devs}


def btc_per_house(house_eur, btc_eur, *, currency="EUR"):
    """btc_per_house = house_eur / btc_eur (EUR / EUR-per-BTC). Refuses non-EUR price and non-positive input."""
    if currency != "EUR":
        raise HistoryError("btc_per_house needs a EUR price per BTC (USD/EUR confusion refused)")
    h, b = _to_decimal(house_eur, "house_eur"), _to_decimal(btc_eur, "btc_eur")
    if h <= 0 or b <= 0:
        raise HistoryError("non-positive input")
    return h / b


def sat_per_house(btc_per_house_value):
    """Exact Decimal conversion, no rounding."""
    v = _to_decimal(btc_per_house_value, "btc_per_house")
    if v <= 0:
        raise HistoryError("non-positive btc_per_house")
    return v * SATS_PER_BTC


def house_join(monthly_rows, houses):
    """Join to CBS house_eur (dict month->Decimal). No house price -> reason NO_HOUSE_PRICE (not extended);
    no BTC price -> null. Never fabricates a value."""
    out = []
    for r in monthly_rows:
        h = houses.get(r["month"])
        row = dict(r, house_eur=h, btc_per_house=None, sat_per_house=None)
        if r["btc_eur"] is None:
            row["join_reason"] = "NO_BTC_PRICE"
        elif h is None:
            row["join_reason"] = "NO_HOUSE_PRICE"
        else:
            bph = btc_per_house(h, r["btc_eur"])
            row.update(btc_per_house=bph, sat_per_house=sat_per_house(bph), join_reason=None)
        out.append(row)
    return out


def aggregate_trades(trades):
    """Streaming daily aggregation of (unix_ts:int, price:str, amount:str). Day = UTC date. Returns
    ({day: {first_ts, last_ts, close, high, low, volume, count}}, anomalies). Counts, does not repair,
    out-of-order timestamps; trades with non-positive price or negative amount are dropped and counted."""
    days, anomalies, prev_ts = {}, {"unordered": 0, "bad_price": 0, "bad_amount": 0, "rows": 0}, None
    for ts, price, amount in trades:
        anomalies["rows"] += 1
        p, a = _to_decimal(price, "price"), _to_decimal(amount, "amount")
        if p <= 0:
            anomalies["bad_price"] += 1
            continue
        if a < 0:
            anomalies["bad_amount"] += 1
            continue
        if prev_ts is not None and ts < prev_ts:
            anomalies["unordered"] += 1
        prev_ts = ts
        day = (date(1970, 1, 1) + timedelta(days=ts // 86400)).isoformat()
        d = days.get(day)
        if d is None:
            days[day] = {"first_ts": ts, "last_ts": ts, "close": p, "high": p, "low": p, "volume": a, "count": 1}
        else:
            if ts >= d["last_ts"]:
                d["last_ts"], d["close"] = ts, p
            d["first_ts"] = min(d["first_ts"], ts)
            d["high"], d["low"] = max(d["high"], p), min(d["low"], p)
            d["volume"] += a
            d["count"] += 1
    return days, anomalies


def monthly_notional(close_by_day, volume_by_day):
    """Mean over observed days of close*volume (quote-currency notional per day), per month. Needs both."""
    groups = {}
    for day, c in close_by_day.items():
        v = volume_by_day.get(day)
        if v is not None:
            groups.setdefault(month_of(day), []).append(c * v)
    return {m: sum(x) / len(x) for m, x in groups.items()}


def sustained_from(values_by_month, threshold):
    """First month from which EVERY later month is >= threshold (None if the last month is below)."""
    months = sorted(values_by_month)
    start = None
    for m in months:
        if values_by_month[m] >= threshold:
            start = start or m
        else:
            start = None
    return start


def top_jumps(daily, n=5):
    """Largest day-over-day relative changes between consecutive CALENDAR days (gaps are not bridged)."""
    out = []
    for day, v in daily.items():
        prev = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
        if prev in daily:
            out.append((abs(v - daily[prev]) / daily[prev], day))
    return [(str(r), d) for r, d in sorted(out, reverse=True)[:n]]


def canonical_json(obj):
    def default(o):
        if isinstance(o, Decimal):
            return format(o, "f")
        raise TypeError(type(o))
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=default, ensure_ascii=True)


def sha256_canonical(obj):
    return hashlib.sha256(canonical_json(obj).encode("ascii")).hexdigest()


def request_publication(env=None, approve_flag=False):
    """BTC-02 is research only. Every publication attempt is refused, approved or not."""
    raise PublicationRefused("BTC-02 never publishes: Bitcoin stays withheld until an owner decision and a "
                             "separate release task (BTC_PUBLICATION_* gate does not exist in this module)")
