"""
Runs every source in sources.py, merges the results into one snapshot,
writes data/snapshot.json (overwritten each run) and appends one row to
data/history.csv (so the dashboard can eventually plot real trend lines
instead of single-day numbers).

Usage: python3 src/fetch_all.py
"""
import csv
import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

import sources

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
SNAPSHOT_PATH = os.path.join(DATA_DIR, "snapshot.json")
HISTORY_PATH = os.path.join(DATA_DIR, "history.csv")


def main():
    load_dotenv(os.path.join(ROOT, ".env"))
    os.makedirs(DATA_DIR, exist_ok=True)

    print("Fetching Treasury yield curve...")
    treasury = sources.treasury_yield_curve()

    print("Fetching FRED series (VIX, Fed funds, OAS spreads, CPI, PCE, GDP)...")
    fred = sources.fred_all()

    print("Fetching EIA oil prices...")
    eia = sources.eia_oil_prices()

    print("Fetching bitcoin price...")
    btc = sources.coingecko_bitcoin()

    print("Fetching equity index closes...")
    indices = sources.equity_indices()

    print("Fetching sector ETF performance...")
    sectors = sources.sector_performance()

    snapshot = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "treasury_yield_curve": treasury,
        "fred": fred,
        "oil": eia,
        "bitcoin": btc,
        "equity_indices": indices,
        "sector_performance": sectors,
    }

    with open(SNAPSHOT_PATH, "w") as f:
        json.dump(snapshot, f, indent=2)
    print(f"Wrote {SNAPSHOT_PATH}")

    _append_history_row(snapshot)
    print(f"Appended a row to {HISTORY_PATH}")

    errors = _collect_errors(snapshot)
    if errors:
        print("\nSources that failed or need a key:")
        for path, msg in errors:
            print(f"  {path}: {msg}")


def _collect_errors(snapshot, prefix=""):
    found = []
    if isinstance(snapshot, dict):
        if "error" in snapshot and len(snapshot) == 1:
            found.append((prefix, snapshot["error"]))
        else:
            for k, v in snapshot.items():
                found.extend(_collect_errors(v, f"{prefix}.{k}" if prefix else k))
    return found


def _append_history_row(snapshot):
    """One flat row per day: date, 10yr yield, fed funds, VIX, HY OAS, BTC,
    S&P close, the fields most useful for a trend chart. Extend as needed."""
    exists = os.path.exists(HISTORY_PATH)
    ten_yr = _safe(lambda: snapshot["treasury_yield_curve"]["10_yr"])
    fed_funds = _safe(
        lambda: snapshot["fred"]["fed_funds_effective"]["observations"][0]["value"]
    )
    vix = _safe(lambda: snapshot["fred"]["vix"]["observations"][0]["value"])
    hy_oas = _safe(lambda: snapshot["fred"]["hy_oas"]["observations"][0]["value"])
    btc = _safe(lambda: snapshot["bitcoin"]["usd"])
    sp500 = _safe(lambda: snapshot["equity_indices"]["^GSPC"]["price"])

    row = {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "ten_yr_yield": ten_yr,
        "fed_funds_effective": fed_funds,
        "vix": vix,
        "hy_oas": hy_oas,
        "bitcoin_usd": btc,
        "sp500_close": sp500,
    }

    with open(HISTORY_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def _safe(fn):
    try:
        return fn()
    except Exception:
        return None


if __name__ == "__main__":
    main()
