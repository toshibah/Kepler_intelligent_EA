"""
news_bridge.py
TBAN Trading Bot - News Signal Bridge
Kepler Camp Codes (ENB Fluid Solutions) | jamenya1988@gmail.com

Polls Forex Factory for high-impact events and writes STOP/GO
to MT5 Common Files so TBAN_EA.mq5 can pause trading.
"""
import logging
import importlib
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    forexfactory = importlib.import_module("forexfactory")
except ImportError:
    forexfactory = None

# ============================================================
# CONFIGURATION
# ============================================================
CURRENCIES = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]
IMPACTS = ["high"]
BLOCK_MINUTES_BEFORE = 30
BLOCK_MINUTES_AFTER  = 30
POLL_INTERVAL_SEC    = 300

MT5_COMMON = Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal" / "Common" / "Files"
SIGNAL_FILE = MT5_COMMON / "news_signal.txt"
LOG_FILE = MT5_COMMON / "news_bridge.log"

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("TBAN_news_bridge")


def write_signal(stop: bool) -> None:
    try:
        MT5_COMMON.mkdir(parents=True, exist_ok=True)
        tmp = SIGNAL_FILE.with_suffix(".tmp")
        tmp.write_text("STOP" if stop else "GO", encoding="utf-8")
        tmp.replace(SIGNAL_FILE)
    except Exception as e:
        log.error("Failed to write signal file: %s", e)


def check_news() -> bool:
    if forexfactory is None:
        log.error("The 'forexfactory' package is unavailable; blocking trading until it is installed.")
        return True

    now = datetime.now(timezone.utc)
    start_month = (now - timedelta(days=1)).strftime("%Y-%m")
    end_month = (now + timedelta(days=1)).strftime("%Y-%m")

    try:
        df = forexfactory.read(
            currencies=CURRENCIES,
            impacts=IMPACTS,
            start=start_month,
            end=end_month,
        )
    except Exception as e:
        log.error("forexfactory.read() failed: %s", e)
        return False

    if df is None or df.empty:
        log.info("No high-impact events found.")
        return False

    for idx, row in df.iterrows():
        event_time = idx
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)

        diff_min = (event_time - now).total_seconds() / 60.0

        if -BLOCK_MINUTES_AFTER < diff_min < BLOCK_MINUTES_BEFORE:
            log.warning(
                "BLACKOUT: %s | %s | %s | at %s UTC (%.1f min)",
                row.get("currency", "?"),
                row.get("event", "?"),
                row.get("impact", "?"),
                event_time.strftime("%Y-%m-%d %H:%M"),
                diff_min,
            )
            return True

    log.info("No blackout events within +/-%d/%d min.",
             BLOCK_MINUTES_BEFORE, BLOCK_MINUTES_AFTER)
    return False


def main():
    log.info("TBAN news_bridge started (Kepler Camp Codes).")
    log.info("Signal file: %s", SIGNAL_FILE)
    log.info("Currencies: %s | Impacts: %s", CURRENCIES, IMPACTS)

    while True:
        try:
            stop = check_news()
            write_signal(stop)
        except Exception as e:
            log.exception("Unexpected error in main loop: %s", e)
        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()