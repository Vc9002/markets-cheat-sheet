"""
One function per data source. Each returns a plain dict of {label: value}.
Every function is independent and defensive, if one source is down or a key
is missing, it returns {"error": "..."} instead of raising, so fetch_all.py
can keep going and report partial results rather than failing the whole run.
"""
import os
import requests

TIMEOUT = 10


def _get(url, **kwargs):
    r = requests.get(url, timeout=TIMEOUT, **kwargs)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Treasury par yield curve, pulled via FRED (mirrors Treasury's own data,
# one JSON call per tenor instead of parsing Treasury's CSV export, which
# sits behind bot protection that blocks plain server-to-server requests
# from some networks). Needs FRED_API_KEY, see fred_all() below.
#
# If you'd rather hit Treasury directly: the raw endpoint is
# https://home.treasury.gov/resource-center/data-chart-center/interest-rates/
# daily-treasury-rates.csv/all/all?type=daily_treasury_yield_curve&
# field_tdr_date_value=<year>&page&_format=csv — no key needed, but test it
# from wherever you're running this first, some networks get a 403.
# ---------------------------------------------------------------------------
YIELD_CURVE_SERIES = {
    "1_mo": "DGS1MO",
    "3_mo": "DGS3MO",
    "6_mo": "DGS6MO",
    "1_yr": "DGS1",
    "2_yr": "DGS2",
    "5_yr": "DGS5",
    "10_yr": "DGS10",
    "30_yr": "DGS30",
}


def treasury_yield_curve():
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        return {"error": "FRED_API_KEY not set"}
    curve = {}
    for tenor, series_id in YIELD_CURVE_SERIES.items():
        url = (
            "https://api.stlouisfed.org/fred/series/observations"
            f"?series_id={series_id}&api_key={api_key}&file_type=json"
            "&sort_order=desc&limit=1"
        )
        try:
            data = _get(url)
            obs = data.get("observations", [])
            curve[tenor] = obs[0]["value"] if obs else None
        except Exception as e:
            curve[tenor] = {"error": str(e)}
    return curve


# ---------------------------------------------------------------------------
# FRED API — free key required
# https://fred.stlouisfed.org/docs/api/fred/series_observations.html
# ---------------------------------------------------------------------------
FRED_SERIES = {
    "vix": "VIXCLS",
    "fed_funds_effective": "DFF",
    "hy_oas": "BAMLH0A0HYM2",
    "ig_oas": "BAMLC0A0CM",
    "cpi_headline_yoy": "CPIAUCSL",       # index level, compute YoY yourself
    "core_pce_yoy": "PCEPILFE",            # index level, compute YoY yourself
    "real_gdp": "GDPC1",                   # quarterly level
}
# Treasury tenor yields live in YIELD_CURVE_SERIES below, used by
# treasury_yield_curve() instead of duplicating them here.


def fred_series(series_key, limit=2):
    """Fetch the latest `limit` observations for one FRED series."""
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        return {"error": "FRED_API_KEY not set"}
    series_id = FRED_SERIES.get(series_key, series_key)
    url = (
        "https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={series_id}&api_key={api_key}&file_type=json"
        f"&sort_order=desc&limit={limit}"
    )
    try:
        data = _get(url)
        obs = data.get("observations", [])
        return {"series": series_id, "observations": obs}
    except Exception as e:
        return {"error": str(e)}


def fred_all():
    """Pull every series in FRED_SERIES in one pass."""
    out = {}
    for key in FRED_SERIES:
        out[key] = fred_series(key)
    return out


# ---------------------------------------------------------------------------
# EIA API — free key required
# https://www.eia.gov/opendata/documentation.php
# ---------------------------------------------------------------------------
def eia_oil_prices():
    api_key = os.environ.get("EIA_API_KEY")
    if not api_key:
        return {"error": "EIA_API_KEY not set"}
    # WTI and Brent spot prices, daily series
    url = (
        "https://api.eia.gov/v2/petroleum/pri/spt/data/"
        f"?api_key={api_key}&frequency=daily&data[0]=value"
        "&facets[series][]=RWTC&facets[series][]=RBRTE"
        "&sort[0][column]=period&sort[0][direction]=desc&length=10"
    )
    try:
        data = _get(url)
        rows = data.get("response", {}).get("data", [])
        return {"rows": rows}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# CoinGecko API — no key needed on the free tier
# https://www.coingecko.com/en/api/documentation
# ---------------------------------------------------------------------------
def coingecko_bitcoin():
    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=bitcoin&vs_currencies=usd&include_24hr_change=true"
    )
    try:
        data = _get(url)
        return data.get("bitcoin", {})
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# yfinance — no key needed, unofficial Yahoo Finance wrapper
# ---------------------------------------------------------------------------
INDEX_TICKERS = {
    "^GSPC": "S&P 500",
    "^DJI": "Dow",
    "^IXIC": "Nasdaq",
    "^RUT": "Russell 2000",
}

SECTOR_TICKERS = {
    "XLK": "Technology",
    "XLV": "Healthcare",
    "XLF": "Financials",
    "XLY": "Consumer Discretionary",
    "XLC": "Communication Services",
    "XLI": "Industrials",
    "XLP": "Consumer Staples",
    "XLE": "Energy",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
    "XLB": "Materials",
}


def yfinance_quotes(tickers):
    """Returns {ticker: {price, change_pct}} for a dict of {symbol: label}."""
    import yfinance as yf

    out = {}
    try:
        data = yf.download(
            list(tickers.keys()), period="2d", interval="1d",
            progress=False, group_by="ticker",
        )
        for symbol, label in tickers.items():
            try:
                closes = data[symbol]["Close"].dropna()
                if len(closes) >= 2:
                    prev, last = closes.iloc[-2], closes.iloc[-1]
                    pct = (last - prev) / prev * 100
                else:
                    last, pct = closes.iloc[-1], None
                out[symbol] = {"label": label, "price": round(float(last), 2),
                                "change_pct": round(float(pct), 2) if pct is not None else None}
            except Exception as e:
                out[symbol] = {"label": label, "error": str(e)}
    except Exception as e:
        return {"error": str(e)}
    return out


def equity_indices():
    return yfinance_quotes(INDEX_TICKERS)


def sector_performance():
    return yfinance_quotes(SECTOR_TICKERS)
