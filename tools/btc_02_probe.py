"""BTC-02 read-only probes (run in GitHub Actions; the sandbox has no network).

Subcommands: exchanges | archives | aggregators | terms | yahoo <history.csv>.
Prints compact aggregates only: URL, retrieval time, sha256 of the raw bytes (pages concatenated in request
order), row count, first/last day, completeness, deviation statistics. Raw third-party bytes and daily prices
are never written to disk or uploaded. Fail-closed: any parse refusal is printed as REFUSED and the source is
excluded from comparisons (nothing is repaired). No publication path exists.
"""
import csv
import gzip
import hashlib
import io
import json
import re
import sys
import time
import zlib
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
from pathlib import Path

import requests

from tools import btc_02_history as H

UA = {"User-Agent": "goud-btc-dashboard btc-02 read-only research"}
NOW = datetime.now(timezone.utc)
TODAY = NOW.date().isoformat()
S = requests.Session()
S.headers.update(UA)


def utc_day(ts):
    return (date(1970, 1, 1) + timedelta(days=int(ts) // 86400)).isoformat()


class Run:
    """Provenance of one source series: url, retrieval time, sha256 over raw bytes, pages, bytes."""

    def __init__(self, name, url):
        self.name, self.url, self.h, self.pages, self.bytes, self.http = name, url, hashlib.sha256(), 0, 0, []
        self.t = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def feed(self, raw, status=200):
        self.h.update(raw)
        self.pages += 1
        self.bytes += len(raw)
        if status not in self.http:
            self.http.append(status)

    def prov(self):
        return (f"url={self.url} t={self.t} http={self.http} pages={self.pages} bytes={self.bytes} "
                f"sha256={self.h.hexdigest()}")


def get(run, url, params=None, tries=3, timeout=60):
    last = None
    for i in range(tries):
        try:
            r = S.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                run.feed(r.content, r.status_code)
                return r
            run.http.append(r.status_code) if r.status_code not in run.http else None
            last = f"HTTP {r.status_code} {r.text[:120]!r}"
            if r.status_code in (400, 401, 403, 404, 410, 451):
                break
        except requests.RequestException as e:
            last = f"{type(e).__name__} {str(e)[:120]}"
        time.sleep(1 + 2 * i)
    print(f"  FETCH_FAIL {run.name}: {last}")
    return None


def pct(x):
    return f"{float(x) * 100:.3f}%"


def summarize(run, rows_dict, currency, extra=""):
    """Print a one-line provenance + completeness summary and return a DailySeries (or None if refused)."""
    try:
        series = H.parse_daily(sorted(rows_dict.items()), source=run.name, currency=currency)
    except H.HistoryError as e:
        print(f"SRC {run.name} REFUSED {e} | {run.prov()}")
        return None
    d = series.as_dict()
    days = sorted(d)
    miss = H.missing_days(days)
    stats = H.monthly_stats(d)
    comp = [m for m, s in stats.items() if s["complete"]]
    print(f"SRC {run.name} [{currency}] rows={len(d)} first={days[0]} last={days[-1]} missing_in_span={len(miss)} "
          f"complete_months={len(comp)} first_complete={comp[0] if comp else None} {extra}")
    print(f"  PROV {run.prov()}")
    if miss:
        print(f"  GAPS {_ranges(miss)[:8]}")
    return series


def _ranges(days):
    out, start, prev = [], None, None
    for d in sorted(days):
        dt = date.fromisoformat(d)
        if prev is not None and dt - prev == timedelta(days=1):
            prev = dt
            continue
        if start is not None:
            out.append(f"{start}..{prev}" if start != prev else str(start))
        start = prev = dt
    if start is not None:
        out.append(f"{start}..{prev}" if start != prev else str(start))
    return out


def cmp_print(label, a, b, by_year=False):
    c = H.compare_monthly(a, b)
    if not c["n"]:
        print(f"CMP {label}: no overlap")
        return c
    print(f"CMP {label}: n={c['n']} mean={pct(c['mean'])} p50={pct(c['p50'])} p90={pct(c['p90'])} "
          f"p95={pct(c['p95'])} p99={pct(c['p99'])} max={pct(c['max'])}@{c['max_month']} "
          f">1%:{c['over_1pct']} >5%:{c['over_5pct']}")
    if by_year:
        ys = {}
        for m, v in c["deviations"].items():
            ys.setdefault(m[:4], []).append(v)
        print("  by_year " + " ".join(f"{y}:n{len(v)}/mean{pct(sum(v) / len(v))}/max{pct(max(v))}" for y, v in sorted(ys.items())))
    return c


def cmp_matched(label, da, db, min_days=20, by_year=True):
    ma, mb, cd = H.matched_day_means(da, db, min_days=min_days)
    return cmp_print(label + f" (matched days>={min_days})", ma, mb, by_year=by_year)


# ---------------------------------------------------------------- fetchers

def fetch_ecb():
    run = Run("ECB EXR.D.USD.EUR.SP00.A", "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?startPeriod=1999-01-01&format=csvdata")
    r = get(run, "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A",
            params={"startPeriod": "1999-01-01", "format": "csvdata"})
    if r is None:
        return None
    rows = {}
    reader = csv.DictReader(io.StringIO(r.content.decode("utf-8-sig")))
    for row in reader:
        if row.get("KEY") != "EXR.D.USD.EUR.SP00.A" or not row.get("OBS_VALUE"):
            continue
        rows[row["TIME_PERIOD"]] = Decimal(row["OBS_VALUE"])
    s = summarize(run, rows, "USD")
    if s:
        d = s.as_dict()
        wk = sum(date.fromisoformat(x).weekday() >= 5 for x in d)
        miss = H.missing_days(list(d))
        wd_miss = [x for x in miss if date.fromisoformat(x).weekday() < 5]
        by_m = H.monthly_stats(d)
        low = sorted((v["days"], m) for m, v in by_m.items() if v["days"] < 19)[:6]
        print(f"  ECB weekend_days_with_rate={wk} calendar_gaps={len(miss)} weekday_gaps(holidays)={len(wd_miss)} "
              f"months={len(by_m)} min_days_in_month={min(v['days'] for v in by_m.values())} lowest={low}")
        s0 = H.DailySeries(s.source, "USD", s.rows)
        return s0
    return None


def fetch_bitstamp(pair, currency):
    run = Run(f"Bitstamp {pair}", f"https://www.bitstamp.net/api/v2/ohlc/{pair}/?step=86400&limit=1000")
    closes, vols, odd, dup = {}, {}, 0, 0
    now = int(NOW.timestamp())
    got = False
    for year in (2011, 2012, 2013, 2014, 2015, 2016, 2017):
        cursor = int(datetime(year, 1, 1, tzinfo=timezone.utc).timestamp())
        while cursor < now:
            r = get(run, f"https://www.bitstamp.net/api/v2/ohlc/{pair}/", {"step": 86400, "limit": 1000, "start": cursor})
            if r is None:
                break
            data = r.json().get("data", {}).get("ohlc", [])
            if not data:
                break
            got = True
            for c in data:
                ts = int(c["timestamp"])
                if ts % 86400:
                    odd += 1
                day = utc_day(ts)
                if day in closes:
                    dup += 1
                closes[day] = Decimal(c["close"])
                vols[day] = Decimal(c["volume"])
            nxt = int(data[-1]["timestamp"]) + 86400
            if nxt <= cursor:
                break
            cursor = nxt
            time.sleep(0.2)
        if got:
            break
    closes.pop(TODAY, None)
    vols.pop(TODAY, None)
    s = summarize(run, closes, currency, f"non_midnight_ts={odd} dup_days={dup} (today's partial candle dropped)")
    return s, vols


def fetch_kraken(pair, currency):
    run = Run(f"Kraken {pair} REST OHLC", f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval=1440")
    r = get(run, "https://api.kraken.com/0/public/OHLC", {"pair": pair, "interval": 1440})
    first = None
    r2 = get(Run(f"Kraken {pair} first trade", "x"), "https://api.kraken.com/0/public/Trades", {"pair": pair, "since": 0, "count": 1})
    if r2 is not None:
        res = r2.json().get("result", {})
        for k, v in res.items():
            if k != "last" and v:
                first = utc_day(int(float(v[0][2])))
    print(f"  Kraken {pair} first trade in API (since=0): {first}")
    if r is None:
        return None, {}
    res = r.json().get("result", {})
    key = next((k for k in res if k != "last"), None)
    closes, vols = {}, {}
    for c in res.get(key, []):
        day = utc_day(c[0])
        if day >= TODAY:
            continue
        closes[day], vols[day] = Decimal(c[4]), Decimal(c[6])
    return summarize(run, closes, currency, "(REST window only, today dropped)"), vols


def fetch_coinbase(product, currency):
    run = Run(f"Coinbase {product}", f"https://api.exchange.coinbase.com/products/{product}/candles?granularity=86400")
    closes, vols = {}, {}
    cur = datetime(2014, 12, 1, tzinfo=timezone.utc)
    end_all = NOW
    while cur < end_all:
        end = min(cur + timedelta(days=299), end_all)
        r = get(run, f"https://api.exchange.coinbase.com/products/{product}/candles",
                {"granularity": 86400, "start": cur.strftime("%Y-%m-%dT%H:%M:%SZ"), "end": end.strftime("%Y-%m-%dT%H:%M:%SZ")})
        if r is None:
            break
        for c in sorted(r.json()):
            day = utc_day(c[0])
            if day < TODAY:
                closes[day], vols[day] = Decimal(str(c[4])), Decimal(str(c[5]))
        cur = end + timedelta(days=1)
        time.sleep(0.4)
    return summarize(run, closes, currency), vols


def fetch_bitfinex(sym, currency):
    run = Run(f"Bitfinex {sym}", f"https://api-pub.bitfinex.com/v2/candles/trade:1D:{sym}/hist?start=0&limit=10000&sort=1")
    r = get(run, f"https://api-pub.bitfinex.com/v2/candles/trade:1D:{sym}/hist", {"start": 0, "limit": 10000, "sort": 1})
    if r is None:
        return None, {}
    closes, vols = {}, {}
    for c in r.json():
        day = utc_day(c[0] // 1000)
        if day < TODAY:
            closes[day], vols[day] = Decimal(str(c[2])), Decimal(str(c[5]))
    return summarize(run, closes, currency), vols


def fetch_binance(symbol, currency):
    for host in ("https://api.binance.com", "https://data-api.binance.vision"):
        run = Run(f"Binance {symbol}", f"{host}/api/v3/klines?symbol={symbol}&interval=1d")
        closes, vols, start, ok = {}, {}, 0, True
        while True:
            r = get(run, f"{host}/api/v3/klines", {"symbol": symbol, "interval": "1d", "startTime": start, "limit": 1000}, tries=1)
            if r is None:
                ok = False
                break
            data = r.json()
            if not data:
                break
            for c in data:
                day = utc_day(c[0] // 1000)
                if day < TODAY:
                    closes[day], vols[day] = Decimal(c[4]), Decimal(c[5])
            if len(data) < 1000:
                break
            start = data[-1][0] + 86400000
        if ok and closes:
            return summarize(run, closes, currency), vols
    return None, {}


# ---------------------------------------------------------------- exchanges job

def month_end_gap(series):
    d = series.as_dict()
    st = H.monthly_stats(d)
    devs = {}
    for m, s in st.items():
        if s["complete"]:
            last = d[f"{m}-{s['calendar_days']:02d}"]
            devs[m] = last
    mean = {m: st[m]["mean"] for m in devs}
    return H.compare_monthly(devs, mean)


def job_exchanges():
    ecb = fetch_ecb()
    usd, usd_vol = fetch_bitstamp("btcusd", "USD")
    eur, eur_vol = fetch_bitstamp("btceur", "EUR")
    others = {"Kraken": (fetch_kraken("XBTUSD", "USD"), fetch_kraken("XBTEUR", "EUR")),
              "Coinbase": (fetch_coinbase("BTC-USD", "USD"), fetch_coinbase("BTC-EUR", "EUR")),
              "Bitfinex": (fetch_bitfinex("tBTCUSD", "USD"), fetch_bitfinex("tBTCEUR", "EUR"))}
    bn = fetch_binance("BTCEUR", "EUR")
    if not (ecb and usd and eur):
        print("FATAL missing reference series")
        sys.exit(1)
    mu, me = H.complete_monthly_mean(usd), H.complete_monthly_mean(eur)
    v1 = H.v1_ratio_of_means(usd, ecb)
    v2 = H.v2_matched_day(usd, ecb)
    v1m = {r["month"]: r["value"] for r in v1 if r["value"] is not None}
    v2m = {r["month"]: r["value"] for r in v2 if r["value"] is not None}
    print("== V1/V2 vs Bitstamp EUR-native (same venue; complete months)")
    cmp_print("V1 ratio-of-means vs EUR-native", v1m, me, by_year=True)
    cmp_print("V2 matched-day (weekdays only) vs EUR-native", v2m, me, by_year=True)
    cmp_print("V1 vs V2", v1m, v2m)
    print("== month-end close vs month mean (Bitstamp EUR / USD), relative gap")
    for nm, s in (("EUR", eur), ("USD", usd)):
        c = month_end_gap(s)
        print(f"  {nm}: n={c['n']} mean={pct(c['mean'])} p50={pct(c['p50'])} p90={pct(c['p90'])} p99={pct(c['p99'])} max={pct(c['max'])}@{c['max_month']}")
    print("== cross-venue (complete months in both)")
    for name, ((ou, _), (oe, _)) in others.items():
        if ou:
            cmp_print(f"{name} USD vs Bitstamp USD", H.complete_monthly_mean(ou), mu)
            cmp_matched(f"{name} USD vs Bitstamp USD", ou.as_dict(), usd.as_dict(), by_year=False)
            v1o = {r["month"]: r["value"] for r in H.v1_ratio_of_means(ou, ecb) if r["value"] is not None}
        if oe:
            cmp_print(f"{name} EUR vs Bitstamp EUR", H.complete_monthly_mean(oe), me)
            cmp_matched(f"{name} EUR vs Bitstamp EUR", oe.as_dict(), eur.as_dict(), by_year=False)
        if ou and oe:
            cmp_print(f"{name} V1(own USD) vs own EUR", v1o, H.complete_monthly_mean(oe))
    cb_eur = others["Coinbase"][1]
    if cb_eur[0]:
        print("== Coinbase BTC-EUR (from 2015) vs Bitstamp-USD V1 over 2015-05..2016-04 (before Bitstamp EUR exists)")
        cmp_print("Coinbase EUR vs V1(Bitstamp USD) all overlap", H.complete_monthly_mean(cb_eur[0]), v1m, by_year=True)
        ne_cb = H.monthly_notional(cb_eur[0].as_dict(), cb_eur[1])
        print("  Coinbase EUR notional/day by month 2015-05..2016-06: " + " ".join(f"{m[2:]}:{float(v):.2g}" for m, v in sorted(ne_cb.items()) if "2015-05" <= m <= "2016-06"))
    if bn[0]:
        cmp_print("Binance EUR vs Bitstamp EUR", H.complete_monthly_mean(bn[0]), me)
        cmp_matched("Binance EUR vs Bitstamp EUR", bn[0].as_dict(), eur.as_dict(), by_year=False)
    print("== liquidity (Bitstamp)")
    nu = H.monthly_notional(usd.as_dict(), usd_vol)
    ne = H.monthly_notional(eur.as_dict(), eur_vol)
    for lab, n in (("USD pair, USD/day", nu), ("EUR pair, EUR/day", ne)):
        print(f"  {lab}: sustained>=1e5 from {H.sustained_from(n, Decimal(10) ** 5)}; >=1e6 from "
              f"{H.sustained_from(n, Decimal(10) ** 6)}; >=1e7 from {H.sustained_from(n, Decimal(10) ** 7)}")
    yrs = {}
    for m, v in nu.items():
        yrs.setdefault(m[:4], []).append(v)
    print("  USD notional/day mean by year: " + " ".join(f"{y}:{float(sum(v) / len(v)):.3g}" for y, v in sorted(yrs.items())))
    vy = {}
    for day, v in usd_vol.items():
        vy.setdefault(day[:4], []).append(v)
    print("  BTC volume/day mean by year (USD pair): " + " ".join(f"{y}:{float(sum(v) / len(v)):.4g}" for y, v in sorted(vy.items())))
    print("== quality levels (Bitstamp only; V3 native EUR preferred, else V1; threshold 1e6 USD notional/day)")
    rows = H.build_monthly(H.v3_native_eur(eur), v1, nu)
    first = {}
    counts = {}
    for r in rows:
        counts[r["quality"]] = counts.get(r["quality"], 0) + 1
        first.setdefault(r["quality"], r["month"])
    print(f"  months {rows[0]['month']}..{rows[-1]['month']} counts={counts} first_month_by_level={first}")
    runs, cur = [], None
    for r in rows:
        key = (r["quality"], r["basis"])
        if cur and cur[0] == key:
            cur[2] = r["month"]
        else:
            cur = [key, r["month"], r["month"]]
            runs.append(cur)
    print("  runs: " + " ".join(f"{k[0]}/{(k[1] or '-')[:2]}:{a}..{b}" for k, a, b in runs))
    print(f"  null reasons: {sorted({r['reason'] for r in rows if r['reason']})}")
    houses = {}
    for row in csv.DictReader(open("data/cbs-housing.csv")):
        if row["series"] == "nl_house_avg_eur":
            houses[row["date"][:7]] = Decimal(row["value"])
    joined = H.house_join(rows, houses)
    ok = [r for r in joined if r["sat_per_house"] is not None]
    print(f"  house join: months_with_btc_and_house={len(ok)} first={ok[0]['month']} last={ok[-1]['month']} "
          f"no_house={sum(r['join_reason'] == 'NO_HOUSE_PRICE' for r in joined)} no_btc={sum(r['join_reason'] == 'NO_BTC_PRICE' for r in joined)}")
    for r in joined:
        if r["month"] in ("2011-09", "2014-10", "2016-05", "2020-01", "2024-01", "2026-08"):
            print(f"  SAMPLE {r['month']} q={r['quality']} basis={r['basis']} btc_eur={r['btc_eur']} house={r['house_eur']} sat={r['sat_per_house']}")
    print(f"  research candidate sha256 (canonical, Bitstamp-only, unpublished) = {H.sha256_canonical(joined)}")
    print("== jumps (Bitstamp EUR / USD top 3 day-over-day)")
    print("  EUR", H.top_jumps(eur.as_dict(), 3), "USD", H.top_jumps(usd.as_dict(), 3))


# ---------------------------------------------------------------- archives job

ARCHIVES = ["mtgoxUSD", "mtgoxEUR", "krakenEUR", "krakenUSD", "bitstampEUR"]
MAX_ARCHIVE_BYTES = 700_000_000


def stream_trades(run, url):
    r = S.get(url, stream=True, timeout=(10, 120))
    run.http.append(r.status_code)
    info = {"status": r.status_code, "len": r.headers.get("Content-Length"), "lm": r.headers.get("Last-Modified")}
    if r.status_code != 200:
        return None, info
    dec = zlib.decompressobj(16 + zlib.MAX_WBITS)
    buf = b""

    def gen():
        nonlocal buf
        for chunk in r.iter_content(1 << 20):
            run.feed(chunk)
            if run.bytes > MAX_ARCHIVE_BYTES:
                raise RuntimeError("archive too large")
            buf += dec.decompress(chunk)
            *lines, buf = buf.split(b"\n")
            for ln in lines:
                p = ln.split(b",")
                if len(p) >= 3 and p[0].isdigit():
                    yield int(p[0]), p[1].decode(), p[2].decode()
        buf += dec.flush()
        for ln in buf.split(b"\n"):
            p = ln.split(b",")
            if len(p) >= 3 and p[0].isdigit():
                yield int(p[0]), p[1].decode(), p[2].decode()
    return gen(), info


def job_archives(ref_usd=None):
    usd, usd_vol = fetch_bitstamp("btcusd", "USD")
    eur_ref, _ = fetch_bitstamp("btceur", "EUR")
    ecb = fetch_ecb()
    v1ref = {r["month"]: r["value"] for r in H.v1_ratio_of_means(usd, ecb) if r["value"] is not None}
    ref = usd.as_dict() if usd else {}
    for name in ARCHIVES:
        origin = f"api.bitcoincharts.com/v1/csv/{name}.csv.gz"
        cands = [f"https://{origin}"]
        cr = get(Run("cdx", "x"), "https://web.archive.org/cdx/search/cdx",
                 {"url": origin, "output": "json", "filter": "statuscode:200", "fl": "timestamp,length,digest", "limit": 40}, tries=2, timeout=40)
        caps = []
        if cr is not None:
            try:
                caps = cr.json()[1:]
            except Exception:
                caps = []
        print(f"CDX {name}: captures={len(caps)} newest={caps[-1] if caps else None} oldest={caps[0] if caps else None}")
        for ts, length, digest in list(reversed(caps))[:4]:
            cands.append(f"https://web.archive.org/web/{ts}id_/http://{origin}")
        for url in cands:
            run = Run(f"bitcoincharts {name}", url)
            try:
                gen, info = stream_trades(run, url)
                if gen is None:
                    print(f"ARCHIVE {name} {url} -> {info}")
                    continue
                days, an = H.aggregate_trades(gen)
            except Exception as e:
                print(f"ARCHIVE {name} {url} ERROR {type(e).__name__} {str(e)[:150]} bytes_read={run.bytes}")
                continue
            print(f"ARCHIVE {name} {info} trades={an['rows']} anomalies={an}")
            if not days:
                break
            closes = {d: v["close"] for d, v in days.items()}
            vols = {d: v["volume"] for d, v in days.items()}
            ccy = "EUR" if name.endswith("EUR") else "USD"
            s = summarize(run, closes, ccy)
            first_ts = min(v["first_ts"] for v in days.values())
            print(f"  first trade UTC {datetime.fromtimestamp(first_ts, timezone.utc).isoformat()} "
                  f"last day {max(days)}; days_with_trades={len(days)}")
            yr = {}
            for d, v in days.items():
                a = yr.setdefault(d[:4], [0, Decimal(0)])
                a[0] += v["count"]
                a[1] += v["volume"]
            print("  trades/BTC by year: " + " ".join(f"{y}:{a[0]}/{float(a[1]):.4g}" for y, a in sorted(yr.items())))
            if s:
                n = H.monthly_notional(closes, vols)
                print(f"  notional/day({ccy}) sustained>=1e5 from {H.sustained_from(n, Decimal(10) ** 5)}; >=1e6 from "
                      f"{H.sustained_from(n, Decimal(10) ** 6)}; max month notional {float(max(n.values())):.3g}")
                print(f"  top jumps {H.top_jumps(closes, 4)}")
                if ccy == "EUR":
                    cmp_print(f"{name} vs Bitstamp EUR (complete months in both)", H.complete_monthly_mean(s), H.complete_monthly_mean(eur_ref), by_year=True)
                    cmp_print(f"{name} vs V1(Bitstamp USD)", H.complete_monthly_mean(s), v1ref, by_year=True)
                if ccy == "USD" and ref:
                    cmp_print(f"{name} vs Bitstamp USD (complete months in both)", H.complete_monthly_mean(s), H.complete_monthly_mean(usd), by_year=True)
                    cmp_matched(f"{name} vs Bitstamp USD", closes, ref)
            break
    # Internet Archive availability (metadata only)
    for target in ("api.bitcoincharts.com/v1/csv/mtgoxUSD.csv.gz", "api.bitcoincharts.com/v1/csv/"):
        run = Run("wayback", "x")
        r = get(run, "https://archive.org/wayback/available", {"url": target}, tries=2)
        if r is not None:
            snap = r.json().get("archived_snapshots", {})
            print(f"WAYBACK {target}: {json.dumps(snap)[:220]}")
    run = Run("ia-search", "x")
    r = get(run, "https://archive.org/advancedsearch.php", {"q": "mtgox OR mt.gox trades OR bitcoin price history", "fl[]": ["identifier", "title"], "rows": 12, "output": "json"}, tries=2)
    if r is not None:
        docs = r.json().get("response", {}).get("docs", [])
        print("IA_SEARCH " + " | ".join(f"{d.get('identifier')}" for d in docs))


# ---------------------------------------------------------------- aggregators job

def fetch_blockchain():
    run = Run("Blockchain.com market-price", "https://api.blockchain.info/charts/market-price?timespan=all&sampled=false&format=json")
    r = get(run, "https://api.blockchain.info/charts/market-price", {"timespan": "all", "sampled": "false", "format": "json", "cors": "true"})
    if r is None:
        return None
    pts, dup, zero = {}, 0, 0
    for p in json.loads(r.content, parse_float=Decimal)["values"]:
        day = utc_day(p["x"])
        if p["y"] <= 0:
            zero += 1
            continue
        if day in pts:
            dup += 1
        pts[day] = Decimal(str(p["y"]))
    pts.pop(TODAY, None)
    return summarize(run, pts, "USD", f"zero_price_points_skipped={zero} multi_point_days={dup} unit={json.loads(r.content).get('unit')!r} period={json.loads(r.content).get('period')!r}")


def fetch_cryptocompare(tsym, extra=None):
    label = f"CryptoCompare histoday BTC/{tsym}" + (f" e={extra}" if extra else "")
    run = Run(label, "https://min-api.cryptocompare.com/data/v2/histoday")
    params = {"fsym": "BTC", "tsym": tsym, "allData": "true"}
    if extra:
        params["e"] = extra
    r = get(run, "https://min-api.cryptocompare.com/data/v2/histoday", params)
    if r is None:
        return None
    j = json.loads(r.content, parse_float=Decimal)
    if j.get("Response") != "Success":
        print(f"  {label}: {str(j)[:200]}")
        return None
    rows, zero = {}, 0
    for c in j["Data"]["Data"]:
        if c["close"] <= 0:
            zero += 1
            continue
        day = utc_day(c["time"])
        if day < TODAY:
            rows[day] = Decimal(str(c["close"]))
    return summarize(run, rows, tsym, f"zero_close_days_skipped={zero}")


def fetch_coindesk_bpi(currency):
    run = Run(f"CoinDesk BPI legacy {currency}", "https://api.coindesk.com/v1/bpi/historical/close.json")
    r = get(run, "https://api.coindesk.com/v1/bpi/historical/close.json", {"start": "2010-07-17", "end": (NOW - timedelta(days=1)).date().isoformat(), "currency": currency}, tries=1)
    if r is None:
        return None
    try:
        bpi = json.loads(r.content, parse_float=Decimal)["bpi"]
    except Exception as e:
        print(f"  BPI parse fail {r.text[:150]!r}")
        return None
    return summarize(run, {d: Decimal(str(v)) for d, v in bpi.items()}, currency)


def fetch_cm_priceusd():
    run = Run("CoinMetrics community PriceUSD 1d", "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics")
    url, params, rows = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics", {"assets": "btc", "metrics": "PriceUSD", "frequency": "1d", "start_time": "2009-01-01", "page_size": 10000}, {}
    while url:
        r = get(run, url, params, tries=2)
        if r is None:
            break
        j = r.json()
        for d in j.get("data", []):
            if d.get("PriceUSD"):
                rows[d["time"][:10]] = Decimal(d["PriceUSD"])
        url, params = j.get("next_page_url"), None
    rows.pop(TODAY, None)
    if not rows:
        print("  CM PriceUSD: no rows")
        return None
    return summarize(run, rows, "USD")


def fetch_coingecko():
    run = Run("CoinGecko public market_chart eur days=max", "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart")
    for days in ("max", "365"):
        r = get(run, "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart", {"vs_currency": "eur", "days": days, "interval": "daily"}, tries=1)
        if r is not None:
            pr = r.json().get("prices", [])
            print(f"  CoinGecko days={days}: points={len(pr)} first={utc_day(pr[0][0] // 1000) if pr else None} last={utc_day(pr[-1][0] // 1000) if pr else None}")
            return
    print("  CoinGecko: no access without key")


def job_aggregators():
    usd, _ = fetch_bitstamp("btcusd", "USD")
    eur, _ = fetch_bitstamp("btceur", "EUR")
    ref_u, ref_e = usd.as_dict(), eur.as_dict()
    ecb = fetch_ecb()
    for fn in (fetch_blockchain, lambda: fetch_cryptocompare("USD"), lambda: fetch_cryptocompare("USD", "Bitstamp"),
               lambda: fetch_cryptocompare("USD", "mtgox"), lambda: fetch_cryptocompare("EUR"),
               lambda: fetch_coindesk_bpi("USD"), lambda: fetch_coindesk_bpi("EUR"), fetch_cm_priceusd):
        try:
            s = fn()
        except Exception as e:
            print(f"  ERROR {type(e).__name__} {str(e)[:150]}")
            continue
        if s:
            ref, refm = (ref_e, H.complete_monthly_mean(eur)) if s.currency == "EUR" else (ref_u, H.complete_monthly_mean(usd))
            cmp_print(f"{s.source} vs Bitstamp {s.currency} (complete months)", H.complete_monthly_mean(s), refm, by_year=True)
            cmp_matched(f"{s.source} vs Bitstamp {s.currency}", s.as_dict(), ref, by_year=False)
            if s.currency == "USD" and ecb:
                v1x = {r["month"]: r["value"] for r in H.v1_ratio_of_means(s, ecb) if r["value"] is not None}
                print(f"  V1({s.source}) months={len(v1x)} first={min(v1x) if v1x else None}")
                cmp_print(f"V1({s.source}) vs Bitstamp EUR-native", v1x, H.complete_monthly_mean(eur), by_year=False)
    fetch_coingecko()


# ---------------------------------------------------------------- yahoo (trading repo) job

def job_yahoo(path):
    run = Run("Trading repo history.csv BTC-USD 1d (Yahoo via yfinance)", "storagebirddrop/script-trading-anlytics@master:data/history.csv")
    raw = Path(path).read_bytes()
    run.feed(raw)
    rows = {}
    dup = 0
    for row in csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))):
        if row.get("Asset") == "BTC" and row.get("Timeframe") == "1d":
            if row["Date"] in rows:
                dup += 1
            rows[row["Date"]] = Decimal(row["Price"])
    s = summarize(run, rows, "USD", f"dup_days={dup}")
    usd, _ = fetch_bitstamp("btcusd", "USD")
    if s and usd:
        cmp_print("Yahoo BTC-USD vs Bitstamp USD (complete months)", H.complete_monthly_mean(s), H.complete_monthly_mean(usd), by_year=True)
        cmp_matched("Yahoo BTC-USD vs Bitstamp USD", s.as_dict(), usd.as_dict(), by_year=False)
        c = H.compare_monthly(H.complete_monthly_mean(s), H.complete_monthly_mean(usd))
        top = sorted(c["deviations"].items(), key=lambda kv: -kv[1])[:5]
        print("  top deviating months " + " ".join(f"{m}:{pct(v)}" for m, v in top))
        d, rd = s.as_dict(), usd.as_dict()
        diffs = sorted(abs(d[x] - rd[x]) / rd[x] for x in set(d) & set(rd))
        print(f"  daily close rel diff vs Bitstamp: n={len(diffs)} p50={pct(H.percentile(diffs, 50))} p90={pct(H.percentile(diffs, 90))} p99={pct(H.percentile(diffs, 99))} max={pct(diffs[-1])}")


# ---------------------------------------------------------------- terms job

TERMS = {
    "tradingview-btc-index-help": "https://www.tradingview.com/support/solutions/43000659124-how-is-the-btc-index-being-calculated/",
    "tradingview-terms": "https://www.tradingview.com/policies/",
    "bitstamp-api": "https://www.bitstamp.net/api/",
    "kraken-api-intro": "https://docs.kraken.com/api/docs/guides/global-intro/",
    "kraken-api-legacy": "https://docs-legacy.kraken.com/api/docs/guides/global-intro/",
    "kraken-ohlcvt-support": "https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data",
    "coinbase-market-data": "https://www.coinbase.com/legal/market_data",
    "bitcoincharts-api": "https://bitcoincharts.com/about/markets-api/",
    "blockchain-charts-api": "https://www.blockchain.com/explorer/api/charts_api",
    "coinmetrics-community": "https://docs.coinmetrics.io/packages/coin-metrics-community-data",
    "coindesk-data-terms": "https://developers.coindesk.com/documentation/legacy/Historical/dataDay",
    "coingecko-api-terms": "https://www.coingecko.com/en/api_terms",
    "yahoo-terms": "https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html",
    "bitfinex-terms": "https://www.bitfinex.com/legal/terms/",
    "binance-api-terms": "https://www.binance.com/en/about-legal/api",
    "ecb-copyright": "https://www.ecb.europa.eu/services/disclaimer/html/index.en.html",
}
KEYS = re.compile(r"redistribut|republish|commercial|scrap|reproduc|licen[cs]|derivative|attribution|display|index composition|mt\.? ?gox|average", re.I)


STRONG = re.compile(r"redistribut|republish|non-commercial|commercial use|commercial purpose|scrap|reproduc|derivative|data licen", re.I)


def job_terms():
    for key, url in TERMS.items():
        run = Run(key, url)
        r = get(run, url, tries=2, timeout=45)
        if r is None:
            print(f"TERMS {key} UNREACHABLE {url}")
            continue
        html = r.text
        txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", html)))
        sents = [s.strip() for s in re.split(r"(?<=[.!?]) ", txt) if KEYS.search(s) and 30 < len(s) < 400]
        sents.sort(key=lambda x: 0 if STRONG.search(x) else 1)
        print(f"TERMS {key} {url} t={run.t} bytes={run.bytes} sha256={run.h.hexdigest()[:16]} text_chars={len(txt)} hits={len(sents)}")
        for s in sents[:4]:
            print(f"   > {s[:260]}")


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    jobs = {"exchanges": job_exchanges, "archives": job_archives, "aggregators": job_aggregators, "terms": job_terms}
    if cmd == "yahoo" and len(argv) > 2:
        job_yahoo(argv[2])
    elif cmd in jobs:
        jobs[cmd]()
    else:
        print("usage: btc_02_probe.py exchanges|archives|aggregators|terms|yahoo <history.csv>")
        return 2
    print("done (research only; nothing published)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
