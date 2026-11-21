#!/usr/bin/env python3
"""Autonomous Indian Market Trading Bot Runner.
Checks market calendar, evaluates opening-range breakouts on a few halal NSE
stocks (long only: no index, no options, no short sales; see halal.py),
and sends instant signals via Telegram. The morning bell still reports the
index levels, as information only.
"""

import datetime
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "trader-broker"))
sys.path.insert(0, os.path.join(ROOT, "trader-entry"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from market_calendar_indian import to_ist, is_market_open
from telegram_bot.notifier import send_morning_bell_alert, send_orb_alert, send_squareoff_reminder
from kite import KiteError, _load_kite
from entry_indian import evaluate_orb_entry
import halal

INDICES = {
    "NIFTY": "NSE:NIFTY 50",
    "BANKNIFTY": "NSE:NIFTY BANK",
    "SENSEX": "BSE:SENSEX",
}

# Halal stocks watched for an opening-range break, with their Yahoo chart symbols.
# Anything that fails the halal screen is skipped, even if it is added here.
ORB_SYMBOLS = {"RELIANCE": "RELIANCE.NS", "TCS": "TCS.NS", "INFY": "INFY.NS"}
ORB_DIRECTION = "long"  # buying only: a short sale sells shares you do not own
# A break is only worth an alert while it is fresh. The schedule runs every
# 15 minutes and GitHub often starts a run late, so allow a little more.
FRESH_MINUTES = 20
REWARD_TO_RISK = 1.5


def orb_alert_plan(result, now_ist):
    """Turn a TRIGGERED entry result into alert levels, or None if it is stale."""
    if result.get("status") != "TRIGGERED":
        return None
    hour, minute = (int(x) for x in result["bar_time"].split(":"))
    closed = now_ist.replace(hour=hour, minute=minute, second=0, microsecond=0) + datetime.timedelta(minutes=5)
    if not datetime.timedelta(0) <= now_ist - closed <= datetime.timedelta(minutes=FRESH_MINUTES):
        return None
    sign = 1 if result["side"] == "long" else -1
    entry = result["trigger_price"]
    stop = (result["or_high"] + result["or_low"]) / 2.0
    risk = (entry - stop) * sign
    if risk <= 0:
        return None
    return {"side": result["side"], "bar_time": result["bar_time"], "spot": entry,
            "range_high": result["or_high"], "range_low": result["or_low"],
            "stop": round(stop, 2), "target": round(entry + sign * REWARD_TO_RISK * risk, 2)}


def check_breakouts(now_ist):
    sent = 0
    rules = halal.load_settings()
    for name, symbol in ORB_SYMBOLS.items():
        ok, why = halal.screen(symbol, settings=rules)
        if not ok:
            print(f"{name}: skipped, {why}")
            continue
        result = evaluate_orb_entry(symbol, ORB_DIRECTION if rules["enabled"] else "both", now_ist=now_ist)
        plan = orb_alert_plan(result, now_ist)
        if plan is not None and plan["side"] != "long" and rules["enabled"]:
            print(f"{name}: breakdown ignored, {halal.short_sale_reason(rules)}")
            continue
        if plan is None:
            print(f"{name}: {result.get('status')} - {result.get('reason')}")
            continue
        if send_orb_alert(name, **plan):
            sent += 1
            print(f"{name}: sent {plan['side']} opening-range alert to Telegram.")
        else:
            print(f"{name}: opening-range break found but Telegram delivery failed.")
    return sent

def get_kite_client():
    try:
        session_path = os.path.join(ROOT, "trader", "state", "kite_session.json")
        return _load_kite(session_path=session_path)
    except KiteError as e:
        print(f"Kite connection unavailable: {e}")
        return None

def fetch_quotes():
    kite = get_kite_client()
    if not kite:
        return {}
    instruments = list(INDICES.values())
    try:
        response = kite.ltp(instruments)
        return {
            symbol: float(response[instrument]["last_price"])
            for symbol, instrument in INDICES.items()
            if instrument in response
        }
    except Exception as e:
        print(f"Kite quote request failed: {e}")
        return {}

def run_market_check():
    now_ist = to_ist()
    curr_time = now_ist.strftime("%H:%M")
    open_status, reason = is_market_open(now_ist)

    print(f"[{curr_time} IST] Checking Indian Market. Status: {reason}")
    if not open_status:
        print("Market is closed. No signals to check.")
        return

    if "15:05" <= curr_time <= "15:25":
        send_squareoff_reminder()
        print("Sent Square-off reminder to Telegram.")
        return

    if "09:30" <= curr_time <= "14:45":
        check_breakouts(now_ist)
        return

    if "09:15" <= curr_time <= "09:29":
        quotes = fetch_quotes()
        if not all(symbol in quotes for symbol in INDICES):
            print("Skipped market-bell alert because Kite did not return every index quote.")
            return
        send_morning_bell_alert(quotes["NIFTY"], quotes["BANKNIFTY"], quotes["SENSEX"])
        print("Sent Morning Bell alert to Telegram.")

if __name__ == "__main__":
    run_market_check()
