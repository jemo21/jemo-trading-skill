import json
import os
import tempfile
import unittest
from unittest import mock

from _load import load

halal = load(".", "halal")
swing = load("trader-scanner", "swing_indian")
universe_indian = load("trader-scanner", "universe_indian")
monitor = load("trader-alerts", "swing_monitor")
scan_indian = load("trader-scanner", "scan_indian")

ON = {"enabled": True, "exclude": set(), "allow": set()}


class Screen(unittest.TestCase):
    def test_permitted_businesses_pass(self):
        for sym in ("TCS", "INFY", "RELIANCE", "BHEL", "SUNPHARMA", "MARUTI", "TCS.NS", "NSE:INFY", "LT-EQ"):
            self.assertTrue(halal.is_halal(sym, settings=ON), sym)

    def test_riba_alcohol_and_gambling_are_excluded_with_the_reason(self):
        cases = {"HDFCBANK": "riba", "SBIN.NS": "riba", "MAHABANK": "riba", "BAJFINANCE": "riba",
                 "MUTHOOTFIN": "riba", "HDFCLIFE": "riba", "MCX": "riba", "UBL": "alcohol",
                 "RADICO": "alcohol", "UNITDSPR": "alcohol", "DELTACORP": "gambling"}
        for sym, word in cases.items():
            ok, why = halal.screen(sym, settings=ON)
            self.assertFalse(ok, sym)
            self.assertIn(word, why, sym)

    def test_the_name_catches_companies_not_on_the_list(self):
        for name, word in (("Some New Small Finance Bank Ltd", "riba"), ("Acme Housing Finance", "riba"),
                           ("Deccan Breweries Ltd", "alcohol"), ("Goa Distilleries", "alcohol"),
                           ("Lucky Casinos Pvt", "gambling"), ("Fantasy Gaming Ltd", "gambling")):
            ok, why = halal.screen("NEWCO", name, settings=ON)
            self.assertFalse(ok, name)
            self.assertIn(word, why)
        # whole words only
        self.assertTrue(halal.is_halal("NEWCO", "Bankim Steel Ltd", settings=ON))
        self.assertTrue(halal.is_halal("NEWCO", "Tata Consultancy Services", settings=ON))

    def test_indices_and_derivatives_are_never_halal(self):
        for sym in ("NIFTY", "BANKNIFTY", "SENSEX", "^NSEI", "NSE:NIFTY 50", "NIFTY26NOV24500CE",
                    "BANKNIFTY26NOV52000PE", "RELIANCE26NOVFUT", "TCS26N2000CE"):
            self.assertFalse(halal.is_halal(sym, settings=ON), sym)

    def test_us_market_list(self):
        for sym in ("JPM", "BAC", "BUD", "DKNG", "SPY", "BRK.B"):
            self.assertFalse(halal.is_halal(sym, market="US", settings=ON), sym)
        for sym in ("AAPL", "MSFT", "TSLA", "KO"):
            self.assertTrue(halal.is_halal(sym, market="US", settings=ON), sym)

    def test_config_exclude_allow_and_off_switch(self):
        rules = {"enabled": True, "exclude": {"TCS"}, "allow": {"NEWCO"}}
        self.assertFalse(halal.is_halal("TCS", settings=rules))
        self.assertTrue(halal.is_halal("NEWCO", "Newco Finance Ltd", settings=rules))
        self.assertFalse(halal.is_halal("NIFTY", settings=rules))  # allow never clears an index
        off = {"enabled": False, "exclude": set(), "allow": set()}
        self.assertTrue(halal.is_halal("HDFCBANK", settings=off))
        self.assertEqual(halal.short_sale_reason(off), "")

    def test_load_settings_reads_the_halal_block(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"halal": {"exclude": ["itc.ns"], "allow": ["NSE:FOO"]}}, fh)
            rules = halal.load_settings(path)
            self.assertEqual((rules["enabled"], rules["exclude"], rules["allow"]), (True, {"ITC"}, {"FOO"}))
            self.assertTrue(halal.load_settings(os.path.join(d, "missing.json"))["enabled"])

    def test_filter_symbols_takes_dicts_pairs_and_bare_symbols(self):
        kept, dropped = halal.filter_symbols([{"symbol": "TCS", "name": "TCS"}, ("UBL", "United Breweries"),
                                              "SBIN", "INFY"], settings=ON)
        self.assertEqual(kept, [{"symbol": "TCS", "name": "TCS"}, "INFY"])
        self.assertEqual([why.split(":")[0] for _, why in dropped], ["UBL", "SBIN"])


class Universes(unittest.TestCase):
    ROWS = [
        {"exchange": "NSE", "segment": "NSE", "instrument_type": "EQ", "tradingsymbol": s,
         "instrument_token": str(i), "name": n}
        for i, (s, n) in enumerate([("TCS", "TATA CONSULTANCY SERV LT"), ("HDFCBANK", "HDFC BANK"),
                                    ("UBL", "UNITED BREWERIES"), ("BHEL", "BHEL"),
                                    ("NEWFIN", "NEW AGE FINANCE"), ("NOFUT", "NO FUTURES LTD")], 1)
    ] + [{"segment": "NFO-FUT", "name": s} for s in ("TCS", "HDFCBANK", "UBL", "BHEL", "NEWFIN")]

    def test_swing_universe_is_halal_by_default(self):
        self.assertEqual([u["symbol"] for u in swing.build_universe(self.ROWS)], ["BHEL", "TCS"])
        self.assertEqual(len(swing.build_universe(self.ROWS, halal_only=False)), 5)

    def test_day_trading_universe_has_no_banks_or_lenders(self):
        kept, dropped = universe_indian.halal_stocks()
        symbols = {s for s, _ in kept}
        for bank in ("HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS", "BAJFINANCE.NS"):
            self.assertNotIn(bank, symbols)
        self.assertIn("TCS.NS", symbols)
        self.assertEqual(len(kept) + len(dropped), len(universe_indian.INDIAN_STOCKS))

    def test_universe_file_is_every_halal_stock_with_futures(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "universe.txt")
            kept = universe_indian.build_universe(out, rows=self.ROWS)
            with open(out, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        self.assertEqual(lines, ["BHEL.NS|BHEL", "TCS.NS|TATA CONSULTANCY SERV LT"])
        self.assertEqual(len(kept), 2)

    def test_universe_falls_back_to_the_built_in_list_offline(self):
        def offline(rows=None):
            raise OSError("no network")
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(universe_indian, "fno_halal_stocks", side_effect=offline):
            kept = universe_indian.build_universe(os.path.join(d, "u.txt"))
        self.assertIn(("TCS.NS", "Tata Consultancy Services Ltd"), kept)
        self.assertNotIn("HDFCBANK.NS", [s for s, _ in kept])

    def test_indian_scanner_reads_the_universe_and_ignores_us_symbols(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "universe.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("TCS.NS|TCS\nBHEL.NS|BHEL\nAAPL|Apple Inc.\n")
            self.assertEqual(scan_indian.load_universe(path), ["TCS.NS", "BHEL.NS"])
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("AAPL|Apple Inc.\n")  # written by the US scanner: fall back
            self.assertEqual(scan_indian.load_universe(path), scan_indian.DEFAULT_SYMBOLS)
            self.assertEqual(scan_indian.load_universe(os.path.join(d, "missing.txt")),
                             scan_indian.DEFAULT_SYMBOLS)

    def test_committed_universe_file_is_halal(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trader", "universe.txt")
        with open(path, encoding="utf-8") as fh:
            lines = [ln.split("|") for ln in fh.read().splitlines() if ln.strip()]
        for sym, name in lines:
            self.assertTrue(halal.is_halal(sym, name), sym)


class SwingMonitor(unittest.TestCase):
    def test_a_new_watch_list_skips_picks_that_are_not_halal(self):
        def pick(sym):
            return {"symbol": sym, "name": sym, "setup": "momentum", "grade": "MODEST", "qty": 5,
                    "close": 100.0, "stop": 80.0}
        doc = {"signal_date": "2026-11-20", "momentum_buy_date": "2026-11-23", "momentum_sell_date": "2026-12-21",
               "picks": [pick("MCX"), pick("TCS"), pick("MAHABANK"), pick("BHEL")]}
        watch = monitor.build_watch(doc, top=10)
        self.assertEqual([p["symbol"] for p in watch["positions"]], ["TCS", "BHEL"])


if __name__ == "__main__":
    unittest.main()
