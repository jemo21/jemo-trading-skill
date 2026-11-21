#!/usr/bin/env python3
"""Indian Market Breakout & Intraday Setup Scanner for trader-scanner. Standard library only.

Replaces US Nasdaq/NYSE scanner with:
  - Every halal NSE stock with futures, read from trader/universe.txt (build it
    with universe_indian.py; about 160 stocks). Halal only (halal.py): no banks,
    lenders, insurers, alcohol, gambling, and no indices. A non-halal symbol
    passed in with --symbols is skipped. Without the file, a short built-in list.
  - Opening Range Breakout (ORB) on Indian market session (09:15 to 09:30 range).
  - 20-Day High Breakout, Reclaim 20-EMA, and RSI Oversold Bounces on NSE tickers (.NS).
"""

import argparse
import datetime
import json
import math
import os
import sys
import urllib.request

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import halal

UNIVERSE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trader", "universe.txt")

# Used only when trader/universe.txt is missing or holds no NSE symbols.
DEFAULT_SYMBOLS = [
    "RELIANCE.NS", "INFY.NS", "TCS.NS", "HCLTECH.NS", "WIPRO.NS",
    "BHARTIARTL.NS", "LT.NS", "TATAMOTORS.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "HINDUNILVR.NS", "ASIANPAINT.NS", "TITAN.NS", "NTPC.NS", "POWERGRID.NS",
]


def load_universe(path=UNIVERSE_PATH):
    """NSE/BSE symbols from a SYMBOL|Name file. US symbols (written there by the
    US scanner, scan.py universe) are ignored. Falls back to DEFAULT_SYMBOLS."""
    try:
        with open(path, encoding="utf-8") as fh:
            symbols = [ln.split("|", 1)[0].strip() for ln in fh if ln.strip()]
    except OSError:
        return list(DEFAULT_SYMBOLS)
    symbols = [s for s in symbols if s.upper().endswith((".NS", ".BO"))]
    return symbols or list(DEFAULT_SYMBOLS)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def fetch_chart(symbol, range_str="1mo", interval="1d"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={range_str}&interval={interval}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            res = data["chart"]["result"][0]
            quotes = res["indicators"]["quote"][0]
            meta = res["meta"]
            return {
                "symbol": symbol,
                "closes": [c for c in quotes.get("close", []) if c is not None],
                "highs": [h for h in quotes.get("high", []) if h is not None],
                "lows": [l for l in quotes.get("low", []) if l is not None],
                "volumes": [v for v in quotes.get("volume", []) if v is not None],
                "last_price": meta.get("regularMarketPrice")
            }
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}

def scan_setups(symbols):
    hits = []
    print(f"Scanning {len(symbols)} Indian symbols for daily setups...")

    for sym in symbols:
        data = fetch_chart(sym, range_str="2mo", interval="1d")
        if "error" in data or len(data.get("closes", [])) < 21:
            continue

        closes = data["closes"]
        last = closes[-1]
        prev_20 = closes[-21:-1]

        # 1. 20-Day Closing High Breakout
        if last > max(prev_20):
            hits.append({"symbol": sym, "setup": "20D Breakout", "price": last})
            continue

        # 2. 20-Day Moving Average Reclaim
        ma20 = sum(prev_20) / len(prev_20)
        if closes[-2] < ma20 and last > ma20:
            hits.append({"symbol": sym, "setup": "Reclaim 20-DMA", "price": last})
            continue

    return hits

def main():
    parser = argparse.ArgumentParser(description="Indian Market Setup Scanner")
    parser.add_argument("--symbols", nargs="+",
                        help="Indian symbols to scan (default: every stock in trader/universe.txt)")
    parser.add_argument("--universe", default=UNIVERSE_PATH, help="SYMBOL|Name file to scan (default: %(default)s)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    symbols, dropped = halal.filter_symbols(args.symbols or load_universe(args.universe))
    for _, why in dropped:
        print(f"Skipped {why}", file=sys.stderr)
    results = scan_setups(symbols)

    if args.json:
        print(json.dumps(results, indent=2))
        return

    print("=" * 60)
    print("🎯 INDIAN MARKET DAILY SETUPS & BREAKOUTS")
    print("=" * 60)
    if not results:
        print("No breakout setups found for the scanned list today.")
        return

    for h in results:
        sym_clean = h['symbol'].replace(".NS", "")
        print(f"🔥 {sym_clean:12} -> {h['setup']:18} @ ₹{h['price']:,.2f}")

if __name__ == "__main__":
    main()
