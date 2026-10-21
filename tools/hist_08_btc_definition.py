"""HIST-08 BTC monthly price definition research (read-only, no publication).

Pure functions (tested offline in tests/test_hist_08_btc_definition.py) plus CI probes that print
AGGREGATES ONLY. Raw third-party bytes and daily prices are never written to disk or uploaded.
Reuses the BTC-02 registered sources and helpers (tools.btc_02_history / tools.btc_02_probe);
no existing file is changed. Nothing here authorizes Bitcoin publication; `request_publication`
(BTC-02) is not wired up and no export path exists.

Rules: Decimal only (no float), no interpolation, no forward fill of missing values, no FX carry
forward, no automatic splice between segments, a month is complete only when every UTC calendar day
has an observation. TWAP "hold last trade" is the DEFINITION of a time-weighted mean inside a
complete month (every day has trades); it is never used to fill a missing day.

Monthly price definitions compared (per complete calendar month, UTC):
  A1 arithmetic mean of daily UTC closes (last trade of each UTC day)
  A2 monthly close (last trade / last daily close of the month)
  A3 intraday trade average (simple mean of all trade prices)
  A3V volume-weighted trade average (VWAP)
  A4 true time-weighted average price (price held until the next trade, over the whole month)
USD to EUR constructions (daily ECB EXR.D.USD.EUR.SP00.A = USD per EUR, no weekend/holiday rate):
  C1 ratio of monthly means: mean(all USD closes) / mean(valid ECB days)
  C2 matched-day: mean over days with both of (usd_close / ecb)
  C3 matched-day ratio of means: mean(usd on matched days) / mean(ecb on matched days)
"""
import calendar
import csv
import sys
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from tools import btc_02_history as H

HistoryError = H.HistoryError
EPOCH = date(1970, 1, 1)
SECONDS_PER_DAY = 86400
SATS_PER_BTC = H.SATS_PER_BTC
DEFINITIONS = ("a2", "a3", "a3v", "a4")  # compared against reference a1
CONVERSIONS = ("C1", "C2", "C3")


def utc_day_from_ts(ts):
    """UTC calendar day of a unix timestamp (integer seconds). 86399 -> 1970-01-01, 86400 -> 1970-01-02."""
    if isinstance(ts, bool) or not isinstance(ts, int):
        raise HistoryError("timestamp must be an int (seconds)")
    if ts < 0:
        raise HistoryError("negative timestamp")
    return (EPOCH + timedelta(days=ts // SECONDS_PER_DAY)).isoformat()


def month_start_ts(month):
    y, m = int(month[:4]), int(month[5:7])
    return (date(y, m, 1) - EPOCH).days * SECONDS_PER_DAY


def next_month(month):
    y, m = int(month[:4]), int(month[5:7])
    return f"{y + (m == 12):04d}-{1 if m == 12 else m + 1:02d}"


def month_seconds(month):
    return H.days_in_month(month) * SECONDS_PER_DAY


class TradeMonthAggregator:
    """Streaming aggregation of time-ordered (unix_ts:int, price, amount) trades into per-month definitions.

    Trades with non-positive price or negative amount are dropped and counted (as in BTC-02).
    Out-of-order timestamps: strict=True raises; strict=False counts and skips the trade (nothing is
    reordered or repaired). Day and month are UTC.
    """

    def __init__(self, strict=True):
        self.strict = strict
        self.anomalies = {"rows": 0, "bad_price": 0, "bad_amount": 0, "unordered": 0}
        self._prev_ts = None
        self._prev_p = None
        self._days = {}  # day -> [last_ts, close]
        self._m = {}  # month -> dict of running sums
        self._tw = {}  # month -> [integral, seconds]
        self._cur = None  # (key, start_ts, end_ts) cache
        self._daynames = {}

    def _bounds(self, ts):
        c = self._cur
        if c is not None and c[1] <= ts < c[2]:
            return c
        day = utc_day_from_ts(ts)
        key = day[:7]
        c = (key, month_start_ts(key), month_start_ts(next_month(key)))
        self._cur = c
        return c

    def _integrate(self, p, t0, t1):
        while t0 < t1:
            key, _, end = self._bounds(t0)
            stop = min(end, t1)
            cell = self._tw.setdefault(key, [Decimal(0), 0])
            cell[0] += p * (stop - t0)
            cell[1] += stop - t0
            t0 = stop

    def add(self, ts, price, amount):
        self.anomalies["rows"] += 1
        if isinstance(ts, bool) or not isinstance(ts, int) or ts < 0:
            raise HistoryError("bad timestamp")
        p, a = H._to_decimal(price, "price"), H._to_decimal(amount, "amount")
        if p <= 0:
            self.anomalies["bad_price"] += 1
            return
        if a < 0:
            self.anomalies["bad_amount"] += 1
            return
        if self._prev_ts is not None and ts < self._prev_ts:
            self.anomalies["unordered"] += 1
            if self.strict:
                raise HistoryError(f"unordered trade ts={ts} after {self._prev_ts}")
            return
        key, _, _ = self._bounds(ts)
        m = self._m.get(key)
        if m is None:
            m = self._m[key] = {"n": 0, "sum_p": Decimal(0), "sum_pv": Decimal(0), "sum_v": Decimal(0),
                                "last_ts": -1, "last_p": None, "max_gap": 0}
        m["n"] += 1
        m["sum_p"] += p
        m["sum_pv"] += p * a
        m["sum_v"] += a
        if ts >= m["last_ts"]:
            m["last_ts"], m["last_p"] = ts, p
        if self._prev_ts is not None:
            gap = ts - self._prev_ts
            if gap > m["max_gap"]:
                m["max_gap"] = gap
            self._integrate(self._prev_p, self._prev_ts, ts)
        day = self._daynames.get(ts // SECONDS_PER_DAY)
        if day is None:
            day = self._daynames[ts // SECONDS_PER_DAY] = utc_day_from_ts(ts)
        d = self._days.get(day)
        if d is None:
            self._days[day] = [ts, p]
        elif ts >= d[0]:
            d[0], d[1] = ts, p
        self._prev_ts, self._prev_p = ts, p

    def daily_closes(self):
        return {d: v[1] for d, v in sorted(self._days.items())}

    def finalize(self):
        """{month: row}. Row value fields are None (with a reason) unless the month is complete (every UTC
        calendar day has at least one trade). TWAP additionally needs the window to be fully covered by
        trades before/inside/after it (first and last month of a file are not)."""
        per_day = {}
        for day, (_, close) in self._days.items():
            per_day.setdefault(day[:7], []).append(close)
        out = {}
        for month, m in sorted(self._m.items()):
            closes = per_day.get(month, [])
            cal = H.days_in_month(month)
            row = {"month": month, "days": len(closes), "calendar_days": cal, "trades": m["n"],
                   "max_gap_s": m["max_gap"], "complete": len(closes) == cal,
                   "a1": None, "a2": None, "a3": None, "a3v": None, "a4": None, "reason": None, "twap_reason": None}
            if not row["complete"]:
                row["reason"] = "PARTIAL_MONTH"
                row["twap_reason"] = "PARTIAL_MONTH"
            else:
                row["a1"] = sum(closes) / len(closes)
                row["a2"] = m["last_p"]
                row["a3"] = m["sum_p"] / m["n"]
                row["a3v"] = m["sum_pv"] / m["sum_v"] if m["sum_v"] > 0 else None
                integral, secs = self._tw.get(month, [Decimal(0), 0])
                if secs == month_seconds(month):
                    row["a4"] = integral / secs
                else:
                    row["twap_reason"] = "WINDOW_NOT_COVERED"
            out[month] = row
        return out


def aggregate_trades_monthly(trades, strict=True):
    agg = TradeMonthAggregator(strict=strict)
    for ts, price, amount in trades:
        agg.add(ts, price, amount)
    return agg.finalize(), agg.anomalies, agg.daily_closes()


def daily_definitions(series):
    """A1 and A2 from a DailySeries (no intraday data): {month: {a1, a2, days, complete}} for complete months.
    A2 is the close of the last calendar day of the month."""
    d = series.as_dict()
    out = {}
    for month, s in H.monthly_stats(d).items():
        if s["complete"]:
            out[month] = {"a1": s["mean"], "a2": d[f"{month}-{s['calendar_days']:02d}"], "days": s["days"]}
    return out


def column(rows, key):
    """{month: value} of non-None entries of one definition."""
    return {m: r[key] for m, r in rows.items() if r.get(key) is not None}


def convert_usd_to_eur(usd, fx, method):
    """{month: {value, usd_days, fx_days, matched_days}} for COMPLETE USD months only. Missing FX days stay
    missing (no weekend/holiday carry-forward). A month without any usable FX is absent."""
    if usd.currency != "USD" or fx.currency != "USD":
        raise HistoryError("conversion needs USD price and USD-per-EUR FX (USD/EUR confusion refused)")
    if method not in CONVERSIONS:
        raise HistoryError(f"unknown conversion {method!r}")
    ud, fd = usd.as_dict(), fx.as_dict()
    ustats = H.monthly_stats(ud)
    fxm = {}
    for day, r in fd.items():
        fxm.setdefault(H.month_of(day), []).append(r)
    matched = {}
    for day in set(ud) & set(fd):
        matched.setdefault(H.month_of(day), []).append(day)
    out = {}
    for month, s in ustats.items():
        if not s["complete"] or month not in fxm:
            continue
        md = sorted(matched.get(month, []))
        if method == "C1":
            value = s["mean"] / (sum(fxm[month]) / len(fxm[month]))
        elif not md:
            continue
        elif method == "C2":
            value = sum(ud[x] / fd[x] for x in md) / len(md)
        else:
            value = (sum(ud[x] for x in md) / len(md)) / (sum(fd[x] for x in md) / len(md))
        out[month] = {"value": value, "usd_days": s["days"], "fx_days": len(fxm[month]), "matched_days": len(md)}
    return out


def values(conv):
    return {m: r["value"] for m, r in conv.items()}


def diff_stats(a, b):
    """Differences a vs reference b over months present in both: absolute (quote currency) and relative
    |a-b|/b plus signed mean relative (a-b)/b. Returns None when there is no overlap."""
    ms = [m for m in sorted(set(a) & set(b)) if a[m] is not None and b[m] is not None]
    if not ms:
        return None
    absd, rel, signed = {}, {}, []
    for m in ms:
        if b[m] <= 0:
            raise HistoryError("non-positive reference")
        absd[m] = abs(a[m] - b[m])
        rel[m] = absd[m] / b[m]
        signed.append((a[m] - b[m]) / b[m])
    n = len(ms)
    mx_abs = max(ms, key=lambda m: (absd[m], m))
    mx_rel = max(ms, key=lambda m: (rel[m], m))
    srt = sorted(rel.values())
    return {"n": n, "mean_abs": sum(absd.values()) / n, "max_abs": absd[mx_abs], "max_abs_month": mx_abs,
            "mean_rel": sum(rel.values()) / n, "max_rel": rel[mx_rel], "max_rel_month": mx_rel,
            "signed_mean_rel": sum(signed) / n, "p50": H.percentile(srt, 50), "p90": H.percentile(srt, 90),
            "p99": H.percentile(srt, 99)}


def diff_by_year(a, b):
    """{year: diff_stats} plus 'ALL'. Years are taken from the month key (UTC calendar)."""
    out = {}
    years = sorted({m[:4] for m in set(a) & set(b)})
    for y in years:
        st = diff_stats({m: v for m, v in a.items() if m[:4] == y}, {m: v for m, v in b.items() if m[:4] == y})
        if st:
            out[y] = st
    allst = diff_stats(a, b)
    if allst:
        out["ALL"] = allst
    return out


def window(d, first=None, last=None):
    return {m: v for m, v in d.items() if (first is None or m >= first) and (last is None or m <= last)}


def btc_per_house(house_eur, btc_eur):
    return H.btc_per_house(house_eur, btc_eur)


def sat_per_house(house_eur, btc_eur):
    return H.sat_per_house(H.btc_per_house(house_eur, btc_eur))


def sat_effect(house, price_a, price_b):
    """Relative change in sat_per_house when price definition a replaces b: |sat_a - sat_b| / sat_b per month.
    Exactly |b - a| / a. Months lacking house price or either price are skipped (never filled)."""
    out = {}
    for m in sorted(set(price_a) & set(price_b) & set(house)):
        sa, sb = sat_per_house(house[m], price_a[m]), sat_per_house(house[m], price_b[m])
        out[m] = abs(sa - sb) / sb
    return out


def load_houses(path):
    houses = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row["series"] == "nl_house_avg_eur":
                houses[row["date"][:7]] = Decimal(row["value"])
    return houses


# ------------------------------------------------------------------ reporting (CI logs, aggregates only)

def pct(x):
    return f"{float(x) * 100:.3f}%"


def fmt(x):
    return format(x, ".6g")


def print_diff_table(label, a, b, abs_unit=""):
    tab = diff_by_year(a, b)
    if not tab:
        print(f"DIFF {label}: no overlap")
        return tab
    al = tab["ALL"]
    print(f"DIFF {label}: n={al['n']} mean_rel={pct(al['mean_rel'])} p50={pct(al['p50'])} p90={pct(al['p90'])} "
          f"p99={pct(al['p99'])} max_rel={pct(al['max_rel'])}@{al['max_rel_month']} signed_mean={pct(al['signed_mean_rel'])} "
          f"mean_abs={fmt(al['mean_abs'])}{abs_unit} max_abs={fmt(al['max_abs'])}{abs_unit}@{al['max_abs_month']}")
    print("  by_year " + " | ".join(
        f"{y}:n{s['n']} mean_rel{pct(s['mean_rel'])} max_rel{pct(s['max_rel'])} signed{pct(s['signed_mean_rel'])} "
        f"mean_abs{fmt(s['mean_abs'])} max_abs{fmt(s['max_abs'])}" for y, s in tab.items() if y != "ALL"))
    return tab


def _fetch_daily():
    from tools import btc_02_probe as P
    ecb = P.fetch_ecb()
    bsu, bsu_vol = P.fetch_bitstamp("btcusd", "USD")
    bse, bse_vol = P.fetch_bitstamp("btceur", "EUR")
    return P, ecb, bsu, bse


def job_daily(houses_path):
    P, ecb, bsu, bse = _fetch_daily()
    cb_u, _ = P.fetch_coinbase("BTC-USD", "USD")
    cb_e, _ = P.fetch_coinbase("BTC-EUR", "EUR")
    bf_u, _ = P.fetch_bitfinex("tBTCUSD", "USD")
    bf_e, _ = P.fetch_bitfinex("tBTCEUR", "EUR")
    if not (ecb and bsu and bse):
        print("FATAL missing reference series")
        sys.exit(1)
    print("== D1 price definitions on daily closes: A2 monthly close vs A1 mean of daily closes (reference A1)")
    defs = {}
    for name, s in (("Bitstamp USD", bsu), ("Bitstamp EUR", bse), ("Coinbase USD", cb_u), ("Coinbase EUR", cb_e)):
        if s:
            defs[name] = daily_definitions(s)
            print_diff_table(f"{name} A2 vs A1", column(defs[name], "a2"), column(defs[name], "a1"))
    print("== D2 USD->EUR constructions vs EUR-native A1 of the SAME venue (shared complete months)")
    pairs = [("Bitstamp", bsu, bse), ("Coinbase", cb_u, cb_e), ("Bitfinex", bf_u, bf_e)]
    convs = {}
    for venue, u, e in pairs:
        if not (u and e):
            print(f"  {venue}: series missing")
            continue
        native = column(daily_definitions(e), "a1")
        for c in CONVERSIONS:
            cv = convert_usd_to_eur(u, ecb, c)
            convs[(venue, c)] = cv
            win = [m for m in native if m in cv]
            md = [cv[m]["matched_days"] for m in win]
            fd = [cv[m]["fx_days"] for m in win]
            print(f"  {venue} {c}: shared_months={len(win)} matched_days min/mean/max={min(md)}/{sum(md) / len(md):.2f}/{max(md)} "
                  f"fx_days min/max={min(fd)}/{max(fd)}")
            print_diff_table(f"{venue} {c}(USD)+ECB vs {venue} EUR native A1", values(cv), native, " EUR")
        for a, b in (("C1", "C2"), ("C1", "C3"), ("C2", "C3")):
            print_diff_table(f"{venue} {a} vs {b} (USD-derived only)", values(convs[(venue, a)]), values(convs[(venue, b)]), " EUR")
    print("== D3 pre-2016-05 window: Bitstamp USD constructions vs Coinbase EUR A1 (2015-05..2016-04, thin EUR book)")
    if cb_e:
        nat = window(column(daily_definitions(cb_e), "a1"), "2015-05", "2016-04")
        for c in CONVERSIONS:
            print_diff_table(f"Bitstamp {c} vs Coinbase EUR A1", window(values(convs[("Bitstamp", c)]), "2015-05", "2016-04"), nat, " EUR")
    print("== D4 transition basis break at 2016-05 (Bitstamp USD constructions vs Bitstamp EUR A1, first 12 months)")
    nat = column(daily_definitions(bse), "a1")
    for c in CONVERSIONS:
        print_diff_table(f"{c} 2016-05..2017-04", window(values(convs[("Bitstamp", c)]), "2016-05", "2017-04"),
                         window(nat, "2016-05", "2017-04"), " EUR")
    print("== D5 BTC and satoshi per house: effect of price definition (Bitstamp EUR, months with CBS house price)")
    houses = load_houses(houses_path)
    dd = daily_definitions(bse)
    a1, a2 = column(dd, "a1"), column(dd, "a2")
    c1 = values(convs[("Bitstamp", "C1")])
    for lab, x in (("A2 vs A1", a2), ("C1(USD)+ECB vs A1", {m: v for m, v in c1.items() if m in a1})):
        eff = sat_effect(houses, x, a1)
        ys = {}
        for m, v in eff.items():
            ys.setdefault(m[:4], []).append(v)
        print(f"  sat_per_house relative change {lab}: n={len(eff)} mean={pct(sum(eff.values()) / len(eff))} "
              f"max={pct(max(eff.values()))}@{max(eff, key=lambda k: (eff[k], k))} by_year " +
              " ".join(f"{y}:{pct(sum(v) / len(v))}/{pct(max(v))}" for y, v in sorted(ys.items())))
    joined = [m for m in sorted(a1) if m in houses]
    print(f"  months with Bitstamp EUR A1 and house price: {len(joined)} first={joined[0]} last={joined[-1]}")
    for m in ("2016-05", "2017-12", "2020-12", "2021-11", "2024-01", "2026-08"):
        if m in a1 and m in houses:
            print(f"  SAMPLE {m} house_eur={houses[m]} btc_eur_A1={fmt(a1[m])} btc_per_house={fmt(btc_per_house(houses[m], a1[m]))} "
                  f"sat_per_house={fmt(sat_per_house(houses[m], a1[m]))} sat_A2_over_A1={fmt(sat_per_house(houses[m], a2[m]) / sat_per_house(houses[m], a1[m]))}")
    print("done (research only; nothing published)")


def acquire_trades(P, name):
    """Stream a bitcoincharts trade file via the newest working Internet Archive capture (same registration as
    BTC-02: tools.btc_02_probe). Returns (trades_generator, run) or (None, run). Bytes stay in memory."""
    origin = f"api.bitcoincharts.com/v1/csv/{name}.csv.gz"
    cr = P.get(P.Run("cdx", "x"), "https://web.archive.org/cdx/search/cdx",
               {"url": origin, "output": "json", "filter": "statuscode:200", "fl": "timestamp,length,digest", "limit": 40},
               tries=2, timeout=40)
    caps = []
    if cr is not None:
        try:
            caps = cr.json()[1:]
        except Exception:
            caps = []
    print(f"CDX {name}: captures={len(caps)} newest={caps[-1] if caps else None}")
    for ts, _, _ in list(reversed(caps))[:4]:
        url = f"https://web.archive.org/web/{ts}id_/http://{origin}"
        for attempt in range(3):  # transient 5xx from the Internet Archive: retry the SAME capture first
            run = P.Run(f"bitcoincharts {name}", url)
            try:
                gen, info = P.stream_trades(run, url)
            except Exception as e:
                print(f"ARCHIVE {name} {url} ERROR {type(e).__name__} {str(e)[:120]}")
                gen, info = None, {"status": 0}
            if gen is not None:
                return gen, run, info
            print(f"ARCHIVE {name} {url} attempt={attempt + 1} -> {info}")
            if info.get("status", 0) and info["status"] < 500:
                break
            time.sleep(5 * (attempt + 1))
    return None, None, None


DAILY = {}  # archive name -> {day: close}; in memory only, never written


def load_archive(P, name):
    gen, run, info = acquire_trades(P, name)
    if gen is None:
        print(f"ARCHIVE {name} UNAVAILABLE")
        return None
    agg = TradeMonthAggregator(strict=False)
    try:
        for ts, price, amount in gen:
            agg.add(ts, price, amount)
    except Exception as e:
        print(f"ARCHIVE {name} ERROR {type(e).__name__} {str(e)[:120]} bytes_read={run.bytes}")
        return None
    rows = agg.finalize()
    DAILY[name] = agg.daily_closes()
    comp = [m for m, r in rows.items() if r["complete"]]
    tw = [m for m in comp if rows[m]["a4"] is not None]
    print(f"ARCHIVE {name} {info} anomalies={agg.anomalies}")
    print(f"  PROV {run.prov()}")
    print(f"  months_seen={len(rows)} complete={len(comp)} first_complete={comp[0] if comp else None} "
          f"last_complete={comp[-1] if comp else None} twap_months={len(tw)} (nothing stored)")
    return rows


def print_definition_tables(name, rows):
    ref = column(rows, "a1")
    for k, lab in (("a2", "A2 month close"), ("a3", "A3 trade mean"), ("a3v", "A3V VWAP"), ("a4", "A4 TWAP")):
        print_diff_table(f"{name} {lab} vs A1", column(rows, k), ref)
    gaps = sorted((r["max_gap_s"], m) for m, r in rows.items() if r["complete"])
    print(f"  {name} max inter-trade gap in complete months: top3={gaps[-3:]}")
    ty = {}
    for m, r in rows.items():
        if r["complete"]:
            ty.setdefault(m[:4], []).append(r["trades"] / r["calendar_days"])
    print(f"  {name} mean trades/day by year: " + " ".join(f"{y}:{sum(v) / len(v):.1f}" for y, v in sorted(ty.items())))


def job_usd_archives():
    from tools import btc_02_probe as P
    mg = load_archive(P, "mtgoxUSD")
    bs = load_archive(P, "bitstampUSD")
    bsu, _ = P.fetch_bitstamp("btcusd", "USD")
    if mg:
        print("== U1 Mt. Gox USD (segment 2010-08..2014-01): definitions vs A1")
        print_definition_tables("MtGox", mg)
        early = [m for m in sorted(mg) if mg[m]["complete"] and m <= "2011-12"]
        print("  MtGox early months (ratio to A1): " + " ".join(
            f"{m}:A2 {fmt(mg[m]['a2'] / mg[m]['a1'])} A3 {fmt(mg[m]['a3'] / mg[m]['a1'])} A4 "
            f"{fmt(mg[m]['a4'] / mg[m]['a1']) if mg[m]['a4'] is not None else None}" for m in early))
    if bs:
        print("== U2 Bitstamp USD trade archive (2011-09..2023-07): definitions vs A1")
        print_definition_tables("BitstampArchive", bs)
        if bsu:
            api = column(daily_definitions(bsu), "a1")
            print_diff_table("Bitstamp archive A1 vs Bitstamp API A1 (fidelity)", column(bs, "a1"), api)
    if mg and bs:
        print("== U3 segment transition Mt. Gox vs Bitstamp (archive), shared complete months, each definition")
        for k, lab in (("a1", "A1"), ("a2", "A2"), ("a3", "A3"), ("a3v", "A3V"), ("a4", "A4")):
            print_diff_table(f"MtGox {lab} vs Bitstamp {lab}", column(mg, k), column(bs, k))
    print("done (research only; nothing published)")


def job_eur_archives(houses_path):
    from tools import btc_02_probe as P
    ecb = P.fetch_ecb()
    bsu, _ = P.fetch_bitstamp("btcusd", "USD")
    bse, _ = P.fetch_bitstamp("btceur", "EUR")
    ke = load_archive(P, "krakenEUR")
    ku = load_archive(P, "krakenUSD")
    if not (ecb and bsu and bse):
        print("FATAL missing reference series")
        sys.exit(1)
    api_e = column(daily_definitions(bse), "a1")
    if ke:
        print("== E1 Kraken EUR trade archive (2014-02..2021-05): definitions vs A1")
        print_definition_tables("KrakenEUR", ke)
        print("== E2 Kraken EUR definitions (each) vs Bitstamp EUR API A1 (cross venue, 2016-05..2021-05)")
        for k, lab in (("a1", "A1"), ("a2", "A2"), ("a3", "A3"), ("a3v", "A3V"), ("a4", "A4")):
            print_diff_table(f"KrakenEUR {lab} vs Bitstamp EUR A1", column(ke, k), api_e)
        print("== E3 Q2 window: Bitstamp USD + ECB constructions vs Kraken EUR A1 (2014-02..2016-04, cross venue)")
        for c in CONVERSIONS:
            cv = values(convert_usd_to_eur(bsu, ecb, c))
            print_diff_table(f"Bitstamp {c} vs KrakenEUR A1", window(cv, "2014-02", "2016-04"), column(ke, "a1"), " EUR")
    if ke and ku:
        print("== E4 SAME-venue conversion test: Kraken USD archive + ECB vs Kraken EUR archive A1")
        usd_s = H.parse_daily(list(DAILY["krakenUSD"].items()), source="krakenUSD", currency="USD")
        for c in CONVERSIONS:
            cv = values(convert_usd_to_eur(usd_s, ecb, c))
            print_diff_table(f"KrakenUSD {c} vs KrakenEUR A1", cv, column(ke, "a1"), " EUR")
    print("== E5 sat/BTC per house effect of price definition (Kraken EUR archive months with house price)")
    houses = load_houses(houses_path)
    if ke:
        for k in ("a2", "a3", "a3v", "a4"):
            eff = sat_effect(houses, column(ke, k), column(ke, "a1"))
            if eff:
                print(f"  sat_per_house change {k} vs a1: n={len(eff)} mean={pct(sum(eff.values()) / len(eff))} max={pct(max(eff.values()))}")
    print("done (research only; nothing published)")


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    arg = argv[2] if len(argv) > 2 else None  # read-only CBS house CSV (never written)
    if cmd == "daily" and arg:
        job_daily(arg)
    elif cmd == "eur-archives" and arg:
        job_eur_archives(arg)
    elif cmd == "usd-archives":
        job_usd_archives()
    else:
        print("usage: hist_08_btc_definition.py daily <house.csv> | eur-archives <house.csv> | usd-archives")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
