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
    """
    records = []
    for symbol, group in df.groupby("Symbol"):
        asset_type = group["Asset Type"].iloc[0]
        buys = group[group["Transaction Type"] == "Buy"]
        sells = group[group["Transaction Type"] == "Sell"]
        dividends = group[group["Transaction Type"] == "Dividend"]

        total_bought = buys["Shares"].sum()
        total_sold = sells["Shares"].sum()
        shares_held = total_bought - total_sold

        total_cost_of_buys = buys["Total"].sum()
        avg_cost = (total_cost_of_buys / total_bought) if total_bought > 0 else 0.0

        sell_proceeds = sells["Total"].sum()
        cost_of_sold = total_sold * avg_cost
        realized_gains = sell_proceeds - cost_of_sold

        dividend_income = dividends["Total"].sum()

        records.append({
            "Symbol": symbol,
            "Asset Type": asset_type,
            "Shares": shares_held,
            "Avg Cost": avg_cost,
            "Cost Basis": shares_held * avg_cost,
            "Realized Gains": realized_gains,
            "Dividend Income": dividend_income,
        })

    return pd.DataFrame(records) if records else pd.DataFrame(
        columns=["Symbol", "Asset Type", "Shares", "Avg Cost", "Cost Basis", "Realized Gains", "Dividend Income"]
    )


# ── Market data ────────────────────────────────────────────────────────────

def fetch_live_prices(symbols: list[str]) -> dict[str, float]:
    """Return {symbol: last_price}. Missing symbols get NaN."""
    prices: dict[str, float] = {}
    for sym in symbols:
        try:
            prices[sym] = float(yf.Ticker(sym).fast_info.last_price)
        except Exception:
            logging.warning("Could not fetch live price for %s", sym)
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

    for sym in symbols:
        try:
            hist = yf.Ticker(sym).history(
                start=start_date,
                end=end_date + pd.Timedelta(days=1),
            )["Close"]
            hist.index = hist.index.normalize().tz_localize(None)
        except Exception:
            logging.warning("Could not fetch history for %s", sym)
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

        prices = hist.reindex(date_index).ffill()
        portfolio_value += (cumulative_shares * prices).fillna(0.0)

    return (
        portfolio_value
        .reset_index()
        .rename(columns={"index": "Date", 0: "Total Value"})
    )
