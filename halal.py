#!/usr/bin/env python3
"""Halal (Shariah) stock screen shared by every trader skill. Standard library only.

Keeps the tools to companies that are not in a prohibited business:

  riba      banks, lenders and other interest-based finance: NBFCs, housing
            finance, gold loans, credit cards, insurance, brokers that lend on
            margin, asset managers and exchanges
  alcohol   breweries, distilleries, spirits and wine
  gambling  casinos, betting, lotteries and real-money gaming

Also never halal here: index trading (NIFTY, BANK NIFTY, SENSEX hold banks and
insurers), futures and options contracts, and short sales.

How a stock is judged:
  1. A symbol on the curated list for its market (NSE, or US) is excluded,
     with the reason.
  2. Otherwise the company name is checked for words like BANK, FINANCE,
     INSURANCE, BREWERIES, DISTILLERIES, CASINO.
  3. "halal" in config_indian.json can add symbols ("exclude") or clear a
     wrongly flagged one ("allow"). "enabled": false switches the screen off.

What this does NOT check: the financial ratios that full Shariah screens also
apply (interest-bearing debt, cash and interest income under about a third of
market cap or a twentieth of revenue). A company in a permitted business can
still fail those. Cross-check a stock against a published Shariah index such as
NIFTY50 Shariah or NIFTY500 Shariah before you buy it.

  python halal.py check TCS HDFCBANK UBL       is each one halal, and why not
  python halal.py universe                     screen the NSE stocks that have futures
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(ROOT, "config_indian.json")

RIBA, ALCOHOL, GAMBLING = "riba", "alcohol", "gambling"
INDEX, DERIVATIVE, SHORT = "index", "derivative", "short sale"

_WHY = {
    RIBA: "riba: interest-based finance (bank, lender, insurer, broker or exchange)",
    ALCOHOL: "alcohol",
    GAMBLING: "gambling",
    INDEX: "an index holds banks and insurers",
    DERIVATIVE: "futures and options are not ownership of a halal company",
    SHORT: "a short sale sells shares you do not own",
}

# NSE symbols, by the business that rules them out.
NSE_EXCLUDED = {
    RIBA: (
        # banks
        "AUBANK AXISBANK BANDHANBNK BANKBARODA BANKINDIA CANBK CENTRALBK CSBBANK CUB DCBBANK "
        "EQUITASBNK ESAFSFB FEDERALBNK HDFCBANK ICICIBANK IDBI IDFCFIRSTB INDIANB INDUSINDBK IOB "
        "J&KBANK KARURVYSYA KOTAKBANK KTKBANK MAHABANK PNB PSB RBLBANK SBIN SOUTHBANK SURYODAY "
        "TMB UCOBANK UJJIVANSFB UNIONBANK UTKARSHBNK YESBANK "
        # lenders, housing finance, gold loans, cards
        "AAVAS ABCAPITAL APTUS BAJAJFINSV BAJAJHFL BAJFINANCE CANFINHOME CHOLAFIN CREDITACC "
        "FIVESTAR HOMEFIRST HUDCO IIFL IREDA IRFC JIOFIN LICHSGFIN LTF M&MFIN MANAPPURAM "
        "MUTHOOTFIN PEL PFC PIRAMALFIN PNBHOUSING POONAWALLA RECLTD SAMMAANCAP SBICARD "
        "SHRIRAMFIN SUNDARMFIN "
        # insurance
        "GICRE HDFCLIFE ICICIGI ICICIPRULI LICI MFSL NIACL POLICYBZR SBILIFE STARHEALTH "
        # brokers, asset managers, exchanges and depositories
        "360ONE ANANDRATHI ANGELONE BSE CAMS CDSL HDFCAMC KFINTECH MCX MOTILALOFS NAM-INDIA "
        "NUVAMA PAYTM UTIAMC"
    ).split(),
    ALCOHOL: "ABDL GLOBUSSPR PICCADIL RADICO SDBL TI UBL UNITDSPR MCDOWELL-N".split(),
    GAMBLING: "DELTACORP NAZARA".split(),
}

# US tickers (Nasdaq and NYSE), for the US skills.
US_EXCLUDED = {
    RIBA: (
        "JPM BAC WFC C GS MS USB PNC TFC COF SCHW AXP BK STT MTB FITB HBAN RF KEY CFG ALLY "
        "SOFI UPST AFRM LC HOOD IBKR SYF DFS V MA PYPL BLK TROW BEN IVZ ICE CME NDAQ CBOE "
        "AIG MET PRU ALL TRV PGR CB AFL HIG LNC UNM CINF L BRK.A BRK.B"
    ).split(),
    ALCOHOL: "BUD STZ DEO TAP SAM BF.A BF.B MGPI".split(),
    GAMBLING: "MGM LVS WYNN CZR PENN DKNG FLUT BYD RSI CHDN GDEN MCRI IGT EVRI".split(),
    # Broad and bank index funds hold banks and insurers; leveraged and inverse ones borrow or short.
    INDEX: "SPY VOO IVV VTI QQQ DIA IWM RSP XLF KRE KBE VFH TQQQ SQQQ SPXL SPXU SH PSQ UPRO SDS QID".split(),
}

# Words in a company name that rule it out. Whole words only, so a name like
# "Bankim Steel" is not caught by BANK.
NAME_RULES = (
    (RIBA, r"\bbank(s|ing)?\b|\bbancorp\b|\bfinance\b|\bfinancial\b|\bfinserv\b|\bfincorp\b"
           r"|\bcredit\b|\blending\b|\bloans?\b|\bhousing fin|\binsurance\b|\bassurance\b"
           r"|\breinsurance\b|\basset management\b|\bcapital markets?\b|\bstock exchange\b"
           r"|\bsecurities\b|\bmortgage\b"),
    (ALCOHOL, r"\bbrewer(y|ies)\b|\bbrewing\b|\bdistiller(y|ies)\b|\bdistilling\b|\bspirits\b"
              r"|\bwines?\b|\bwinery\b|\bliquors?\b|\bbeers?\b"),
    (GAMBLING, r"\bcasinos?\b|\bgaming\b|\bbetting\b|\blotter(y|ies)\b|\bgambling\b|\bsportsbook\b"),
)
_NAME_RULES = [(cat, re.compile(rx, re.I)) for cat, rx in NAME_RULES]

INDEX_SYMBOLS = {"NIFTY", "NIFTY50", "NIFTY 50", "BANKNIFTY", "NIFTYBANK", "NIFTY BANK", "SENSEX",
                 "FINNIFTY", "MIDCPNIFTY", "BANKEX", "^NSEI", "^NSEBANK", "^BSESN", "^CNXFIN"}
# Option and future contracts: 'NIFTY26NOV24500CE', 'RELIANCE26NOVFUT', 'TCS26N2000PE'.
_CONTRACT = re.compile(r"^[A-Z&-]+\d{2}[A-Z0-9]{1,4}(\d+(\.\d+)?(CE|PE)|FUT)$")


def load_settings(path=None):
    """The "halal" block of config_indian.json, with defaults."""
    try:
        with open(path or CONFIG_PATH, encoding="utf-8") as fh:
            cfg = json.load(fh).get("halal") or {}
    except (OSError, ValueError, AttributeError):
        cfg = {}
    return {"enabled": cfg.get("enabled", True) is not False,
            "exclude": {_clean(s) for s in cfg.get("exclude") or []},
            "allow": {_clean(s) for s in cfg.get("allow") or []}}


def _clean(symbol):
    """'NSE:HDFCBANK', 'hdfcbank.ns', 'HDFCBANK-EQ' -> 'HDFCBANK'."""
    s = str(symbol or "").strip().upper()
    if ":" in s:
        s = s.split(":", 1)[1]
    for suffix in (".NS", ".BO", "-EQ", "-BE"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    return s


def _lookup(table):
    return {sym: cat for cat, syms in table.items() for sym in syms}


_NSE = _lookup(NSE_EXCLUDED)
_US = _lookup(US_EXCLUDED)


def is_index(symbol):
    s = str(symbol or "").strip().upper()
    return s in INDEX_SYMBOLS or _clean(s) in INDEX_SYMBOLS or s.startswith("^")


def is_contract(symbol):
    return bool(_CONTRACT.match(_clean(symbol).replace(" ", "")))


def screen(symbol, name="", market="NSE", settings=None):
    """(True, "") if the stock is halal by business activity, else (False, reason)."""
    settings = settings if settings is not None else load_settings()
    if not settings["enabled"]:
        return True, ""
    sym = _clean(symbol)
    if is_index(symbol):
        return False, "%s: not halal, %s" % (sym, _WHY[INDEX])
    if is_contract(symbol):
        return False, "%s: not halal, %s" % (sym, _WHY[DERIVATIVE])
    if sym in settings["exclude"]:
        return False, "%s: not halal, on your exclude list in config_indian.json" % sym
    if sym in settings["allow"]:
        return True, ""
    cat = (_US if str(market).upper() == "US" else _NSE).get(sym)
    if cat:
        return False, "%s: not halal, %s" % (sym, _WHY[cat])
    for cat, rx in _NAME_RULES:
        if name and rx.search(str(name)):
            return False, "%s (%s): not halal, %s" % (sym, name, _WHY[cat])
    return True, ""


def is_halal(symbol, name="", market="NSE", settings=None):
    return screen(symbol, name, market, settings)[0]


def short_sale_reason(settings=None):
    """The reason a short sale is refused, or "" when the screen is off."""
    settings = settings if settings is not None else load_settings()
    return "SHORT: not halal, %s" % _WHY[SHORT] if settings["enabled"] else ""


def filter_symbols(items, market="NSE", settings=None, symbol_key="symbol", name_key="name"):
    """Split a universe into (kept, dropped). Items are dicts, (symbol, name) pairs or bare symbols.
    dropped is a list of (item, reason)."""
    settings = settings if settings is not None else load_settings()
    kept, dropped = [], []
    for item in items:
        if isinstance(item, dict):
            sym, name = item.get(symbol_key, ""), item.get(name_key, "")
        elif isinstance(item, (tuple, list)):
            sym, name = item[0], (item[1] if len(item) > 1 else "")
        else:
            sym, name = item, ""
        ok, why = screen(sym, name, market, settings)
        if ok:
            kept.append(item)
        else:
            dropped.append((item, why))
    return kept, dropped


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("check", "universe"):
        print(__doc__.strip())
        return 2
    market = "NSE"
    if "--us" in argv:
        argv.remove("--us")
        market = "US"
    if argv[0] == "check":
        if len(argv) < 2:
            print("usage: python halal.py check SYMBOL [SYMBOL ...] [--us]")
            return 2
        bad = 0
        for sym in argv[1:]:
            ok, why = screen(sym, market=market)
            print(("HALAL      %s" % _clean(sym)) if ok else ("NOT HALAL  %s" % why))
            bad += not ok
        return 1 if bad else 0
    sys.path.insert(0, os.path.join(ROOT, "trader-scanner"))
    import swing_indian
    universe = swing_indian.build_universe(swing_indian._instrument_rows(), halal_only=False)
    kept, dropped = filter_symbols(universe)
    for item, why in dropped:
        print("NOT HALAL  " + why)
    print("\n%d of %d NSE stocks with futures pass the halal screen; %d excluded."
          % (len(kept), len(universe), len(dropped)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
