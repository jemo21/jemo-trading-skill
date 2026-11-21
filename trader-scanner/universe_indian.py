#!/usr/bin/env python3
"""Indian Universe Builder for trader-scanner. Standard library only.

Builds trader/universe.txt from every NSE stock that has futures listed (the
same list the swing picker screens, from Kite's public instruments file),
keeping only halal companies (halal.py): banks, lenders, insurers, alcohol and
gambling companies are left out, and so are the indices. About 160 stocks.

    python trader-scanner/universe_indian.py [OUT_PATH]

If the instruments file cannot be downloaded, the short list of NIFTY 50
heavyweights below is used instead, also halal only.
Outputs in the exact format expected by trader-scanner: SYMBOL.NS|Company Name
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
import halal

DEFAULT_OUT = os.path.join(ROOT, "trader", "universe.txt")

# Fallback only: high-liquidity NIFTY 50 constituents, used when Kite's list is unreachable
INDIAN_STOCKS = [
    # Top Index Heavyweights
    ("RELIANCE.NS", "Reliance Industries Ltd"),
    ("HDFCBANK.NS", "HDFC Bank Ltd"),
    ("ICICIBANK.NS", "ICICI Bank Ltd"),
    ("INFY.NS", "Infosys Ltd"),
    ("TCS.NS", "Tata Consultancy Services Ltd"),
    ("ITC.NS", "ITC Ltd"),
    ("LT.NS", "Larsen & Toubro Ltd"),
    ("SBIN.NS", "State Bank of India"),
    ("BHARTIARTL.NS", "Bharti Airtel Ltd"),
    ("KOTAKBANK.NS", "Kotak Mahindra Bank Ltd"),
    ("AXISBANK.NS", "Axis Bank Ltd"),
    ("HINDUNILVR.NS", "Hindustan Unilever Ltd"),
    ("BAJFINANCE.NS", "Bajaj Finance Ltd"),
    ("MARUTI.NS", "Maruti Suzuki India Ltd"),
    ("TATAMOTORS.NS", "Tata Motors Ltd"),
    ("SUNPHARMA.NS", "Sun Pharmaceutical Industries Ltd"),
    ("TITAN.NS", "Titan Company Ltd"),
    ("NTPC.NS", "NTPC Ltd"),
    ("POWERGRID.NS", "Power Grid Corporation of India Ltd"),
    ("TATASTEEL.NS", "Tata Steel Ltd"),
    ("ASIANPAINT.NS", "Asian Paints Ltd"),
    ("M&M.NS", "Mahindra & Mahindra Ltd"),
    ("ADANIENT.NS", "Adani Enterprises Ltd"),
    ("ADANIPORTS.NS", "Adani Ports and SEZ Ltd"),
    ("COALINDIA.NS", "Coal India Ltd"),
    ("BAJAJFINSV.NS", "Bajaj Finserv Ltd"),
    ("ONGC.NS", "Oil & Natural Gas Corporation Ltd"),
    ("JSWSTEEL.NS", "JSW Steel Ltd"),
    ("WIPRO.NS", "Wipro Ltd"),
    ("HCLTECH.NS", "HCL Technologies Ltd")
]

def halal_stocks():
    """INDIAN_STOCKS with the non-halal names removed: (kept, [(item, reason)])."""
    return halal.filter_symbols(INDIAN_STOCKS)


def fno_halal_stocks(rows=None):
    """Every halal NSE stock with futures: ([(SYMBOL.NS, name)], total before the screen)."""
    import swing_indian
    rows = swing_indian._instrument_rows() if rows is None else rows
    every = swing_indian.build_universe(rows, halal_only=False)
    kept, _ = halal.filter_symbols(every)
    return [(u["symbol"] + ".NS", u["name"]) for u in kept], len(every)


def build_universe(out_path=DEFAULT_OUT, rows=None):
    """Write the universe file. Returns the (symbol, name) pairs written."""
    try:
        kept, total = fno_halal_stocks(rows)
        source = "NSE stocks with futures"
    except Exception as exc:  # no network, or Kite's file changed shape
        print(f"Could not load Kite's instruments list ({exc}); using the built-in NIFTY 50 list.",
              file=sys.stderr)
        kept, _ = halal_stocks()
        total, source = len(INDIAN_STOCKS), "built-in NIFTY 50 list"
    if not kept:
        raise SystemExit("universe_indian.py: no stocks to write")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for sym, name in kept:
            f.write(f"{sym}|{name}\n")
    print(f"✅ {len(kept)} of {total} {source} pass the halal screen; written to {out_path}")
    return kept

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    out = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT
    build_universe(out)
