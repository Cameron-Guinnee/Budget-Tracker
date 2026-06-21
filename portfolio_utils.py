"""Portfolio utilities: Google Sheet access, position math, live/historical prices."""

import logging
from pathlib import Path
import toml
import pandas as pd
import streamlit as st
import yfinance as yf
from gspread import service_account_from_dict

PORTFOLIO_CONNECTION_KEY = "portfolio_gsheets"

TRANSACTION_COLS = [
    "Date", "Symbol", "Asset Type", "Transaction Type",
    "Shares", "Price Per Share", "Total", "Notes",
]

ASSET_TYPES = ["Stock", "Crypto"]
TRANSACTION_TYPES = ["Buy", "Sell", "Dividend"]


# ── Sheet helpers ──────────────────────────────────────────────────────────

def _read_secrets(config_file_path: str = ".streamlit/secrets.toml") -> dict:
    try:
        return toml.loads(Path(config_file_path).read_text(encoding="utf-8"))
    except (FileNotFoundError, toml.decoder.TomlDecodeError):
        return {}


def _get_portfolio_config(config_file_path: str = ".streamlit/secrets.toml") -> dict | None:
    secrets = _read_secrets(config_file_path)
    try:
        return secrets["connections"][PORTFOLIO_CONNECTION_KEY]
    except KeyError:
        return None


def get_portfolio_spreadsheet(config_file_path: str = ".streamlit/secrets.toml"):
    config = _get_portfolio_config(config_file_path)
    if not config:
        return None
    try:
        client = service_account_from_dict(config)
        return client.open_by_url(config["spreadsheet"])
    except Exception:
        logging.exception("Failed to open portfolio spreadsheet")
        return None


def get_portfolio_worksheet(config_file_path: str = ".streamlit/secrets.toml"):
    config = _get_portfolio_config(config_file_path)
    if not config:
        return None
    spreadsheet = get_portfolio_spreadsheet(config_file_path)
    if not spreadsheet:
        return None
    try:
        worksheet_id = config.get("worksheet", 0)
        if isinstance(worksheet_id, int):
            return spreadsheet.get_worksheet(worksheet_id)
        return spreadsheet.worksheet(str(worksheet_id))
    except Exception:
        logging.exception("Failed to open portfolio worksheet")
        return None


def get_portfolio_sheet_url(config_file_path: str = ".streamlit/secrets.toml") -> str | None:
    config = _get_portfolio_config(config_file_path)
    if config:
        return config.get("spreadsheet")
    return None


def load_portfolio_df(config_file_path: str = ".streamlit/secrets.toml") -> pd.DataFrame | None:
    ws = get_portfolio_worksheet(config_file_path)
    if ws is None:
        return None
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame(columns=TRANSACTION_COLS)
    header, *rows = values
    rows = [r for r in rows if any(c.strip() for c in r)]
    return pd.DataFrame(rows, columns=header) if rows else pd.DataFrame(columns=header)


def append_portfolio_transaction(row: list, config_file_path: str = ".streamlit/secrets.toml") -> bool:
    ws = get_portfolio_worksheet(config_file_path)
    if ws is None:
        return False
    try:
        ws.append_row(row, value_input_option="USER_ENTERED")
        return True
    except Exception:
        logging.exception("Failed to append portfolio transaction")
        return False


# ── Data prep ──────────────────────────────────────────────────────────────

def prep_portfolio_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y", errors="coerce")
    df["Shares"] = pd.to_numeric(df["Shares"], errors="coerce").fillna(0.0)
    df["Price Per Share"] = pd.to_numeric(df["Price Per Share"], errors="coerce").fillna(0.0)
    df["Total"] = pd.to_numeric(df["Total"], errors="coerce").fillna(0.0)
    return df.dropna(subset=["Date"])


# ── Position math ──────────────────────────────────────────────────────────

def compute_holdings(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute current open positions from a prepped transaction DataFrame.
    Returns one row per symbol with cost basis and realized gain columns.
    Uses a running average cost basis computed in date order to avoid
    blending in future purchases when valuing past sales.
    """
    records = []
    for symbol, group in df.groupby("Symbol"):
        asset_type = group["Asset Type"].iloc[0]
        running_shares = 0.0
        running_cost = 0.0
        realized_gains = 0.0
        dividend_income = 0.0

        for _, txn in group.sort_values("Date").iterrows():
            txn_type = txn["Transaction Type"]
            if txn_type == "Buy":
                running_shares += txn["Shares"]
                running_cost += txn["Total"]
            elif txn_type == "Sell" and running_shares > 0:
                avg = running_cost / running_shares
                realized_gains += txn["Total"] - txn["Shares"] * avg
                running_shares -= txn["Shares"]
                running_cost = running_shares * avg
            elif txn_type == "Dividend":
                dividend_income += txn["Total"]

        avg_cost = (running_cost / running_shares) if running_shares > 0 else 0.0

        records.append({
            "Symbol": symbol,
            "Asset Type": asset_type,
            "Shares": running_shares,
            "Avg Cost": avg_cost,
            "Cost Basis": running_cost,
            "Realized Gains": realized_gains,
            "Dividend Income": dividend_income,
        })

    return pd.DataFrame(records) if records else pd.DataFrame(
        columns=["Symbol", "Asset Type", "Shares", "Avg Cost", "Cost Basis", "Realized Gains", "Dividend Income"]
    )


# ── Market data ────────────────────────────────────────────────────────────

def fetch_live_prices(symbols: list[str]) -> dict[str, float]:
    """Return {symbol: last_price}. Missing symbols get NaN. Batches via yf.Tickers."""
    prices: dict[str, float] = {}
    if not symbols:
        return prices
    try:
        tickers = yf.Tickers(" ".join(symbols))
        for sym in symbols:
            try:
                prices[sym] = float(tickers.tickers[sym].fast_info.last_price)
            except Exception:
                logging.warning("Could not fetch live price for %s", sym)
                prices[sym] = float("nan")
    except Exception:
        logging.warning("Batch price fetch failed, falling back to per-ticker")
        for sym in symbols:
            try:
                prices[sym] = float(yf.Ticker(sym).fast_info.last_price)
            except Exception:
                prices[sym] = float("nan")
    return prices


@st.cache_data(ttl=300, show_spinner="Fetching live prices…")
def cached_live_prices(symbols: tuple[str, ...]) -> dict[str, float]:
    return fetch_live_prices(list(symbols))


def compute_portfolio_value_over_time(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reconstruct daily total portfolio value using yfinance historical closes.
    Returns DataFrame with columns [Date, Total Value].
    """
    if df.empty:
        return pd.DataFrame(columns=["Date", "Total Value"])

    symbols = df["Symbol"].unique().tolist()
    start_date = df["Date"].min()
    end_date = pd.Timestamp.today().normalize()
    date_index = pd.date_range(start=start_date, end=end_date, freq="D")

    portfolio_value = pd.Series(0.0, index=date_index)

    try:
        raw = yf.download(
            symbols,
            start=start_date,
            end=end_date + pd.Timedelta(days=1),
            auto_adjust=True,
            progress=False,
        )["Close"]
        # yf.download returns a Series (not DataFrame) when there's only one ticker
        if isinstance(raw, pd.Series):
            raw = raw.to_frame(name=symbols[0])
        raw.index = raw.index.normalize().tz_localize(None)
        all_hist = raw.reindex(date_index).ffill()
    except Exception:
        logging.warning("Batch history download failed; falling back to per-ticker")
        all_hist = pd.DataFrame(index=date_index)
        for sym in symbols:
            try:
                hist = yf.Ticker(sym).history(
                    start=start_date,
                    end=end_date + pd.Timedelta(days=1),
                )["Close"]
                hist.index = hist.index.normalize().tz_localize(None)
                all_hist[sym] = hist.reindex(date_index).ffill()
            except Exception:
                logging.warning("Could not fetch history for %s", sym)

    for sym in symbols:
        if sym not in all_hist.columns:
            continue

        sym_txns = df[df["Symbol"] == sym].copy()
        sym_txns["Signed Shares"] = sym_txns.apply(
            lambda r: r["Shares"] if r["Transaction Type"] == "Buy"
                      else -r["Shares"] if r["Transaction Type"] == "Sell"
                      else 0.0,
            axis=1,
        )
        daily_delta = sym_txns.groupby("Date")["Signed Shares"].sum()
        daily_delta = daily_delta.reindex(date_index, fill_value=0.0)
        cumulative_shares = daily_delta.cumsum()

        portfolio_value += (cumulative_shares * all_hist[sym]).fillna(0.0)

    return (
        portfolio_value
        .reset_index()
        .rename(columns={"index": "Date", 0: "Total Value"})
    )


# ── Analytics ──────────────────────────────────────────────────────────────

def compute_portfolio_metrics(value_series: pd.Series) -> dict:
    """Sharpe ratio (0% RFR), max drawdown, and annualized volatility from daily values."""
    returns = value_series.pct_change().dropna()
    if len(returns) < 2 or returns.std() == 0:
        return {"sharpe": None, "max_drawdown": None, "volatility": None}
    volatility = float(returns.std() * (252 ** 0.5))
    sharpe = float(returns.mean() / returns.std() * (252 ** 0.5))
    rolling_max = value_series.expanding().max()
    max_drawdown = float(((value_series - rolling_max) / rolling_max).min())
    return {"sharpe": sharpe, "max_drawdown": max_drawdown, "volatility": volatility}


def compute_drawdown_series(value_series: pd.Series) -> pd.Series:
    rolling_max = value_series.expanding().max()
    return (value_series - rolling_max) / rolling_max * 100


def compute_xirr(cashflows: list[tuple], terminal_value: float = 0.0,
                  terminal_date: pd.Timestamp | None = None) -> float | None:
    """
    Money-weighted annualized return (XIRR).
    cashflows: list of (date, amount) — negative for outflows (buys), positive for inflows.
    terminal_value added as a positive cashflow at terminal_date (today if None).
    Returns None if scipy is unavailable or if the NPV function has no root.
    """
    try:
        from scipy.optimize import brentq
    except ImportError:
        return None

    all_flows = list(cashflows)
    if terminal_value > 0:
        td = terminal_date or pd.Timestamp.today()
        all_flows.append((td, terminal_value))

    if not any(cf[1] > 0 for cf in all_flows) or not any(cf[1] < 0 for cf in all_flows):
        return None

    t0 = min(cf[0] for cf in all_flows)
    years = [(cf[0] - t0).days / 365.25 for cf in all_flows]
    amounts = [cf[1] for cf in all_flows]

    def npv(rate):
        return sum(a / (1 + rate) ** t for a, t in zip(amounts, years))

    try:
        return float(brentq(npv, -0.9999, 1000.0, maxiter=1000))
    except Exception:
        return None


def compute_tax_lots(df: pd.DataFrame) -> pd.DataFrame:
    """
    FIFO tax-lot matching. Returns one row per realized lot with Term = Short-term / Long-term.
    Short-term: held < 365 days; Long-term: held >= 365 days.
    """
    records = []
    for symbol, group in df.groupby("Symbol"):
        lots: list[dict] = []
        for _, txn in group.sort_values("Date").iterrows():
            if txn["Transaction Type"] == "Buy":
                lots.append({
                    "date": txn["Date"],
                    "shares": float(txn["Shares"]),
                    "cost_per_share": float(txn["Price Per Share"]),
                })
            elif txn["Transaction Type"] == "Sell":
                remaining = float(txn["Shares"])
                sell_date = txn["Date"]
                proceeds_per_share = float(txn["Price Per Share"])
                while remaining > 1e-9 and lots:
                    lot = lots[0]
                    sold = min(remaining, lot["shares"])
                    days_held = (sell_date - lot["date"]).days
                    records.append({
                        "Symbol": symbol,
                        "Buy Date": lot["date"],
                        "Sell Date": sell_date,
                        "Shares": sold,
                        "Cost Per Share": lot["cost_per_share"],
                        "Cost Basis": round(sold * lot["cost_per_share"], 4),
                        "Proceeds": round(sold * proceeds_per_share, 4),
                        "Gain/Loss": round(sold * (proceeds_per_share - lot["cost_per_share"]), 4),
                        "Days Held": days_held,
                        "Term": "Long-term" if days_held >= 365 else "Short-term",
                    })
                    lot["shares"] -= sold
                    remaining -= sold
                    if lot["shares"] <= 1e-9:
                        lots.pop(0)

    cols = ["Symbol", "Buy Date", "Sell Date", "Shares", "Cost Per Share",
            "Cost Basis", "Proceeds", "Gain/Loss", "Days Held", "Term"]
    return pd.DataFrame(records, columns=cols) if records else pd.DataFrame(columns=cols)


# ── External data (cached) ─────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner="Fetching sector data…")
def cached_sector_info(symbols: tuple[str, ...]) -> dict[str, str]:
    result = {}
    for sym in symbols:
        try:
            info = yf.Ticker(sym).info
            result[sym] = info.get("sector") or info.get("quoteType") or "Unknown"
        except Exception:
            result[sym] = "Unknown"
    return result


@st.cache_data(ttl=3600, show_spinner="Fetching dividend data…")
def cached_dividend_info(symbols: tuple[str, ...]) -> dict[str, dict]:
    result = {}
    for sym in symbols:
        try:
            info = yf.Ticker(sym).info
            result[sym] = {
                "rate": info.get("dividendRate"),
                "yield_pct": (info.get("dividendYield") or 0.0) * 100,
                "ex_date": info.get("exDividendDate"),
            }
        except Exception:
            result[sym] = {"rate": None, "yield_pct": 0.0, "ex_date": None}
    return result


@st.cache_data(ttl=3600, show_spinner="Fetching benchmark data…")
def fetch_benchmark_history(symbol: str, start: pd.Timestamp,
                             end: pd.Timestamp) -> pd.Series:
    try:
        raw = yf.download(symbol, start=start, end=end + pd.Timedelta(days=1),
                          auto_adjust=True, progress=False)["Close"]
        if isinstance(raw, pd.DataFrame):
            raw = raw.iloc[:, 0]
        raw.index = raw.index.normalize().tz_localize(None)
        date_index = pd.date_range(start=start, end=end, freq="D")
        return raw.reindex(date_index).ffill().bfill()
    except Exception:
        logging.warning("Could not fetch benchmark history for %s", symbol)
        return pd.Series(dtype=float)
