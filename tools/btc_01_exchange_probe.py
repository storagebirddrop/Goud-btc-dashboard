"""BTC-01: read-only measurement of public exchange daily BTC/EUR candles (Bitstamp).

Research only; nothing is written or published. Prints the first available day, number of daily candles,
missing UTC days, complete calendar months and the response sha256 per page, so BTC-02 can pin and compare.
Daily candle = Bitstamp OHLC step 86400 (UTC day); the close is the last trade of the UTC day.
"""
import calendar
import hashlib
import json
from datetime import datetime, timezone

import requests

URL = "https://www.bitstamp.net/api/v2/ohlc/{pair}/"


def fetch(session, pair, start_ts, end_ts):
    rows, cursor, digests = {}, start_ts, []
    while cursor < end_ts:
        r = session.get(URL.format(pair=pair), params={"step": 86400, "limit": 1000, "start": cursor}, timeout=60)
        if r.status_code >= 400:
            print(f"HTTP {r.status_code} {r.url}: {r.text[:300]}")
            break
        digests.append(hashlib.sha256(r.content).hexdigest())
        data = json.loads(r.content).get("data", {}).get("ohlc", [])
        if not data:
            break
        for c in data:
            day = datetime.fromtimestamp(int(c["timestamp"]), tz=timezone.utc).strftime("%Y-%m-%d")
            rows[day] = float(c["close"])
        nxt = int(data[-1]["timestamp"]) + 86400
        if nxt <= cursor:
            break
        cursor = nxt
    return rows, digests


def main():
    s = requests.Session()
    s.headers["User-Agent"] = "btc-01-exchange-probe/1 (read-only research)"
    now = int(datetime.now(timezone.utc).timestamp())
    for pair in ("btceur", "btcusd"):
        rows, digests = {}, []
        # The API returns nothing when `start` precedes the pair's first candle: try later starts until data appears.
        for year in (2011, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020):
            rows, digests = fetch(s, pair, int(datetime(year, 1, 1, tzinfo=timezone.utc).timestamp()), now)
            print(f"{pair}: start {year}-01-01 -> {len(rows)} candles")
            if rows:
                break
        if not rows:
            print(f"{pair}: no candles")
            continue
        days = sorted(rows)
        print(f"{pair}: first {days[0]}, last {days[-1]}, candles {len(rows)}, pages {len(digests)}, "
              f"page sha256 {digests[:2]}...")
        y, m = int(days[0][:4]), int(days[0][5:7])
        ly, lm = int(days[-1][:4]), int(days[-1][5:7])
        full, partial = 0, []
        while (y, m) < (ly, lm):
            n = calendar.monthrange(y, m)[1]
            have = sum(1 for d in range(1, n + 1) if f"{y:04d}-{m:02d}-{d:02d}" in rows)
            if have == n:
                full += 1
            else:
                partial.append((f"{y:04d}-{m:02d}", have, n))
            m += 1
            if m > 12:
                y, m = y + 1, 1
        print(f"{pair}: complete months {full}; incomplete months {len(partial)}: {partial[:10]}")
        print(f"{pair}: non-positive closes {sum(1 for v in rows.values() if v <= 0)}")
        for mo in ("2014-10", "2016-01", "2020-01", "2024-01", "2026-09"):
            vals = [v for d, v in rows.items() if d.startswith(mo)]
            if vals:
                print(f"  {pair} {mo}: days {len(vals)}, mean close {sum(vals) / len(vals):.2f}")
    print("done")


if __name__ == "__main__":
    main()
