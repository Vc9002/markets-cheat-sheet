# markets-cheat-sheet

Pulls a daily IB-interview markets snapshot (rates, inflation, growth, credit
spreads, commodities, crypto, equity indices, sector performance) from free,
official, structured APIs instead of scraping HTML pages. Built to feed a
[Claude Artifact](https://claude.ai) markets dashboard, but the JSON output
is generic and works anywhere.

## Why this exists

Scraping CNBC/tradingeconomics/FRED's own web pages and having an LLM read
the HTML works, but it is slow, it is one extra point of failure per field,
and most of these sources also publish the same numbers as clean JSON for
free. This repo calls those JSON endpoints directly.

## Data sources

| Category | Source | Auth | Notes |
|---|---|---|---|
| Treasury yield curve | [Treasury Fiscal Data API](https://fiscaldata.treasury.gov/api-documentation/) | none | Official daily par yield curve |
| Fed funds, OAS spreads, CPI, core PCE, GDP, VIX | [FRED API](https://fred.stlouisfed.org/docs/api/fred/) | free key | St. Louis Fed, one call per series |
| Oil, gas, energy data | [EIA API](https://www.eia.gov/opendata/) | free key | US Energy Information Administration |
| Bitcoin price | [CoinGecko API](https://www.coingecko.com/en/api/documentation) | none (free tier) | |
| Index closes, sector ETFs | [yfinance](https://github.com/ranaroussi/yfinance) | none | Unofficial Yahoo Finance wrapper |

No free official API exists for the ISM Manufacturing PMI (ISM sells it) or
M&A league tables (Dealogic/Mergermarket are paid). Those stay as periodic
manual or search-based updates, both release on a slow enough cadence
(monthly, quarterly) that this doesn't matter much.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and add your free FRED and EIA keys
```

Get free keys at:
- FRED: https://fred.stlouisfed.org/docs/api/api_key.html
- EIA: https://www.eia.gov/opendata/register.php

Treasury and CoinGecko need no key.

## Usage

```bash
python3 src/fetch_all.py
```

Writes `data/snapshot.json` (today's numbers) and appends a row to
`data/history.csv` (for trend charts over time, since the artifact itself
has no memory between runs).

## Running it daily

Add to your crontab (`crontab -e`) to run every weekday morning:

```
30 9 * * 1-5 cd /path/to/markets-cheat-sheet && .venv/bin/python src/fetch_all.py >> logs/run.log 2>&1
```

## Files

- `src/sources.py` — one function per data source, each returns a plain dict
- `src/fetch_all.py` — runs all of them, merges into `data/snapshot.json`, appends to `data/history.csv`
- `data/snapshot.json` — latest pull (gitignored, generated)
- `data/history.csv` — append-only daily log (gitignored, generated)
