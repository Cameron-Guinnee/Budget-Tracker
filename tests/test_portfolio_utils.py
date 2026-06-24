"""Tests for portfolio_utils.py — position math and analytics."""

import sys
import pandas as pd
import pytest

from portfolio_utils import (
    compute_holdings,
    compute_tax_lots,
    compute_xirr,
    compute_portfolio_metrics,
    compute_drawdown_series,
    prep_portfolio_df,
)
from tests.conftest import make_portfolio_df

# pandas' datetime conversion crashes on Python 3.14 (access violation in
# _ensure_nanosecond_dtype). The production app targets Python ≤3.13.
_NEEDS_DATETIME = pytest.mark.skipif(
    sys.version_info >= (3, 14),
    reason="pandas datetime parsing crashes on Python 3.14 (target env is ≤3.13)",
)


# ── prep_portfolio_df ──────────────────────────────────────────────────────

@_NEEDS_DATETIME
class TestPrepPortfolioDf:
    def test_parses_dates(self):
        raw = pd.DataFrame([{
            "Date": "01/15/2024", "Symbol": "AAPL", "Asset Type": "Stock",
            "Transaction Type": "Buy", "Shares": "10", "Price Per Share": "150.00",
            "Total": "1500.00", "Notes": "",
        }])
        result = prep_portfolio_df(raw)
        assert result["Date"].iloc[0] == pd.Timestamp("2024-01-15")

    def test_coerces_numerics(self):
        raw = pd.DataFrame([{
            "Date": "01/15/2024", "Symbol": "AAPL", "Asset Type": "Stock",
            "Transaction Type": "Buy", "Shares": "5", "Price Per Share": "200",
            "Total": "1000", "Notes": "",
        }])
        result = prep_portfolio_df(raw)
        assert result["Shares"].iloc[0] == 5.0
        assert result["Price Per Share"].iloc[0] == 200.0
        assert result["Total"].iloc[0] == 1000.0

    def test_drops_unparseable_dates(self):
        raw = pd.DataFrame([
            {"Date": "01/15/2024", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Buy", "Shares": "5", "Price Per Share": "100",
             "Total": "500", "Notes": ""},
            {"Date": "not-a-date", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Buy", "Shares": "5", "Price Per Share": "100",
             "Total": "500", "Notes": ""},
        ])
        result = prep_portfolio_df(raw)
        assert len(result) == 1

    def test_fills_missing_numerics_with_zero(self):
        raw = pd.DataFrame([{
            "Date": "01/15/2024", "Symbol": "AAPL", "Asset Type": "Stock",
            "Transaction Type": "Buy", "Shares": "", "Price Per Share": "",
            "Total": "", "Notes": "",
        }])
        result = prep_portfolio_df(raw)
        assert result["Shares"].iloc[0] == 0.0


# ── compute_holdings ───────────────────────────────────────────────────────

@_NEEDS_DATETIME
class TestComputeHoldings:
    def test_empty_df_returns_empty(self):
        df = make_portfolio_df([])
        result = compute_holdings(df)
        assert result.empty
        assert list(result.columns) == [
            "Symbol", "Asset Type", "Shares", "Avg Cost",
            "Cost Basis", "Realized Gains", "Dividend Income",
        ]

    def test_single_buy(self):
        df = make_portfolio_df([{
            "Date": "2024-01-01", "Symbol": "AAPL", "Asset Type": "Stock",
            "Transaction Type": "Buy", "Shares": 10, "Price Per Share": 150, "Total": 1500,
        }])
        h = compute_holdings(df)
        row = h[h["Symbol"] == "AAPL"].iloc[0]
        assert row["Shares"] == 10
        assert row["Avg Cost"] == 150
        assert row["Cost Basis"] == 1500
        assert row["Realized Gains"] == 0
        assert row["Dividend Income"] == 0

    def test_multiple_buys_average_cost(self):
        df = make_portfolio_df([
            {"Date": "2024-01-01", "Symbol": "BTC", "Asset Type": "Crypto",
             "Transaction Type": "Buy", "Shares": 1, "Price Per Share": 40000, "Total": 40000},
            {"Date": "2024-02-01", "Symbol": "BTC", "Asset Type": "Crypto",
             "Transaction Type": "Buy", "Shares": 1, "Price Per Share": 60000, "Total": 60000},
        ])
        h = compute_holdings(df)
        row = h[h["Symbol"] == "BTC"].iloc[0]
        assert row["Shares"] == 2
        assert row["Avg Cost"] == 50000
        assert row["Cost Basis"] == 100000

    def test_partial_sell_realized_gain(self):
        df = make_portfolio_df([
            {"Date": "2024-01-01", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Buy", "Shares": 10, "Price Per Share": 100, "Total": 1000},
            {"Date": "2024-06-01", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Sell", "Shares": 4, "Price Per Share": 150, "Total": 600},
        ])
        h = compute_holdings(df)
        row = h[h["Symbol"] == "AAPL"].iloc[0]
        assert row["Shares"] == 6
        assert abs(row["Avg Cost"] - 100) < 0.01
        assert abs(row["Cost Basis"] - 600) < 0.01
        assert abs(row["Realized Gains"] - 200) < 0.01  # 4 * (150 - 100)

    def test_partial_sell_realized_loss(self):
        df = make_portfolio_df([
            {"Date": "2024-01-01", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Buy", "Shares": 10, "Price Per Share": 200, "Total": 2000},
            {"Date": "2024-06-01", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Sell", "Shares": 5, "Price Per Share": 150, "Total": 750},
        ])
        h = compute_holdings(df)
        row = h[h["Symbol"] == "AAPL"].iloc[0]
        assert abs(row["Realized Gains"] - (-250)) < 0.01  # 5 * (150 - 200)

    def test_full_sell_leaves_zero_shares(self):
        df = make_portfolio_df([
            {"Date": "2024-01-01", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Buy", "Shares": 10, "Price Per Share": 100, "Total": 1000},
            {"Date": "2024-06-01", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Sell", "Shares": 10, "Price Per Share": 120, "Total": 1200},
        ])
        h = compute_holdings(df)
        row = h[h["Symbol"] == "AAPL"].iloc[0]
        assert row["Shares"] == 0
        assert row["Cost Basis"] == 0
        assert abs(row["Realized Gains"] - 200) < 0.01

    def test_dividend_income_accumulated(self):
        df = make_portfolio_df([
            {"Date": "2024-01-01", "Symbol": "VYM", "Asset Type": "Stock",
             "Transaction Type": "Buy", "Shares": 100, "Price Per Share": 50, "Total": 5000},
            {"Date": "2024-03-01", "Symbol": "VYM", "Asset Type": "Stock",
             "Transaction Type": "Dividend", "Shares": 0, "Price Per Share": 0, "Total": 75},
            {"Date": "2024-06-01", "Symbol": "VYM", "Asset Type": "Stock",
             "Transaction Type": "Dividend", "Shares": 0, "Price Per Share": 0, "Total": 80},
        ])
        h = compute_holdings(df)
        row = h[h["Symbol"] == "VYM"].iloc[0]
        assert row["Shares"] == 100
        assert abs(row["Dividend Income"] - 155) < 0.01

    def test_multiple_symbols_independent(self):
        df = make_portfolio_df([
            {"Date": "2024-01-01", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Buy", "Shares": 10, "Price Per Share": 100, "Total": 1000},
            {"Date": "2024-01-01", "Symbol": "GOOG", "Asset Type": "Stock",
             "Transaction Type": "Buy", "Shares": 5, "Price Per Share": 200, "Total": 1000},
        ])
        h = compute_holdings(df)
        assert len(h) == 2
        assert h[h["Symbol"] == "AAPL"].iloc[0]["Shares"] == 10
        assert h[h["Symbol"] == "GOOG"].iloc[0]["Shares"] == 5

    def test_sell_without_position_is_ignored(self):
        df = make_portfolio_df([
            {"Date": "2024-06-01", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Sell", "Shares": 5, "Price Per Share": 150, "Total": 750},
        ])
        h = compute_holdings(df)
        row = h[h["Symbol"] == "AAPL"].iloc[0]
        assert row["Shares"] == 0
        assert row["Realized Gains"] == 0


# ── compute_tax_lots ───────────────────────────────────────────────────────

@_NEEDS_DATETIME
class TestComputeTaxLots:
    def test_empty_df_returns_empty(self):
        df = make_portfolio_df([])
        result = compute_tax_lots(df)
        assert result.empty

    def test_no_sells_returns_empty(self):
        df = make_portfolio_df([{
            "Date": "2024-01-01", "Symbol": "AAPL", "Asset Type": "Stock",
            "Transaction Type": "Buy", "Shares": 10, "Price Per Share": 100, "Total": 1000,
        }])
        result = compute_tax_lots(df)
        assert result.empty

    def test_short_term_lot(self):
        df = make_portfolio_df([
            {"Date": "2024-01-01", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Buy", "Shares": 10, "Price Per Share": 100, "Total": 1000},
            {"Date": "2024-06-01", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Sell", "Shares": 10, "Price Per Share": 150, "Total": 1500},
        ])
        lots = compute_tax_lots(df)
        assert len(lots) == 1
        assert lots.iloc[0]["Term"] == "Short-term"
        assert lots.iloc[0]["Days Held"] < 365
        assert abs(lots.iloc[0]["Gain/Loss"] - 500) < 0.01

    def test_long_term_lot(self):
        df = make_portfolio_df([
            {"Date": "2023-01-01", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Buy", "Shares": 10, "Price Per Share": 100, "Total": 1000},
            {"Date": "2024-02-01", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Sell", "Shares": 10, "Price Per Share": 130, "Total": 1300},
        ])
        lots = compute_tax_lots(df)
        assert len(lots) == 1
        assert lots.iloc[0]["Term"] == "Long-term"
        assert lots.iloc[0]["Days Held"] >= 365

    def test_fifo_ordering(self):
        """First buy consumed first when selling."""
        df = make_portfolio_df([
            {"Date": "2023-01-01", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Buy", "Shares": 5, "Price Per Share": 100, "Total": 500},
            {"Date": "2024-01-01", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Buy", "Shares": 5, "Price Per Share": 200, "Total": 1000},
            {"Date": "2024-06-01", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Sell", "Shares": 5, "Price Per Share": 250, "Total": 1250},
        ])
        lots = compute_tax_lots(df)
        assert len(lots) == 1
        assert abs(lots.iloc[0]["Cost Per Share"] - 100) < 0.01  # consumed the $100 lot
        assert lots.iloc[0]["Term"] == "Long-term"
        assert abs(lots.iloc[0]["Gain/Loss"] - 750) < 0.01  # 5 * (250 - 100)

    def test_partial_lot_split(self):
        """Selling 3 from a 5-share lot."""
        df = make_portfolio_df([
            {"Date": "2024-01-01", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Buy", "Shares": 5, "Price Per Share": 100, "Total": 500},
            {"Date": "2024-06-01", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Sell", "Shares": 3, "Price Per Share": 120, "Total": 360},
        ])
        lots = compute_tax_lots(df)
        assert len(lots) == 1
        assert lots.iloc[0]["Shares"] == 3
        assert abs(lots.iloc[0]["Gain/Loss"] - 60) < 0.01  # 3 * (120 - 100)

    def test_sell_spanning_two_lots(self):
        """Selling 8 shares consumes the 5-share lot and 3 from the next."""
        df = make_portfolio_df([
            {"Date": "2023-01-01", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Buy", "Shares": 5, "Price Per Share": 100, "Total": 500},
            {"Date": "2023-06-01", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Buy", "Shares": 5, "Price Per Share": 200, "Total": 1000},
            {"Date": "2024-06-01", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Sell", "Shares": 8, "Price Per Share": 250, "Total": 2000},
        ])
        lots = compute_tax_lots(df)
        assert len(lots) == 2
        assert lots.iloc[0]["Shares"] == 5
        assert lots.iloc[1]["Shares"] == 3

    def test_realized_loss(self):
        df = make_portfolio_df([
            {"Date": "2024-01-01", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Buy", "Shares": 10, "Price Per Share": 200, "Total": 2000},
            {"Date": "2024-06-01", "Symbol": "AAPL", "Asset Type": "Stock",
             "Transaction Type": "Sell", "Shares": 10, "Price Per Share": 150, "Total": 1500},
        ])
        lots = compute_tax_lots(df)
        assert lots.iloc[0]["Gain/Loss"] < 0
        assert abs(lots.iloc[0]["Gain/Loss"] - (-500)) < 0.01


# ── compute_xirr ───────────────────────────────────────────────────────────

@_NEEDS_DATETIME
class TestComputeXirr:
    def test_simple_10_percent_return(self):
        flows = [(pd.Timestamp("2024-01-01"), -1000.0)]
        result = compute_xirr(
            flows,
            terminal_value=1100.0,
            terminal_date=pd.Timestamp("2025-01-01"),
        )
        assert result is not None
        assert abs(result - 0.10) < 0.005

    def test_no_positive_flows_returns_none(self):
        flows = [(pd.Timestamp("2024-01-01"), -1000.0)]
        result = compute_xirr(flows, terminal_value=0.0)
        assert result is None

    def test_no_negative_flows_returns_none(self):
        flows = [(pd.Timestamp("2024-01-01"), 1000.0)]
        result = compute_xirr(flows)
        assert result is None

    def test_empty_flows_with_no_terminal_returns_none(self):
        result = compute_xirr([], terminal_value=0.0)
        assert result is None

    def test_negative_return(self):
        flows = [(pd.Timestamp("2024-01-01"), -1000.0)]
        result = compute_xirr(
            flows,
            terminal_value=800.0,
            terminal_date=pd.Timestamp("2025-01-01"),
        )
        assert result is not None
        assert result < 0

    def test_multiple_cashflows(self):
        flows = [
            (pd.Timestamp("2024-01-01"), -500.0),
            (pd.Timestamp("2024-07-01"), -500.0),
        ]
        result = compute_xirr(
            flows,
            terminal_value=1200.0,
            terminal_date=pd.Timestamp("2025-01-01"),
        )
        assert result is not None
        assert result > 0


# ── compute_portfolio_metrics ──────────────────────────────────────────────

class TestComputePortfolioMetrics:
    def test_flat_series_returns_none_metrics(self):
        series = pd.Series([100.0, 100.0, 100.0, 100.0, 100.0])
        metrics = compute_portfolio_metrics(series)
        assert metrics["sharpe"] is None
        assert metrics["max_drawdown"] is None
        assert metrics["volatility"] is None

    def test_too_short_returns_none_metrics(self):
        series = pd.Series([100.0])
        metrics = compute_portfolio_metrics(series)
        assert metrics["sharpe"] is None

    def test_growing_series_positive_sharpe(self):
        series = pd.Series(100.0 * (1.001 ** pd.RangeIndex(252)))
        metrics = compute_portfolio_metrics(series)
        assert metrics["sharpe"] is not None
        assert metrics["sharpe"] > 0

    def test_monotonically_growing_has_zero_drawdown(self):
        series = pd.Series(100.0 * (1.001 ** pd.RangeIndex(252)))
        metrics = compute_portfolio_metrics(series)
        assert metrics["max_drawdown"] is not None
        assert abs(metrics["max_drawdown"]) < 1e-9

    def test_drawdown_detected(self):
        series = pd.Series([100.0, 110.0, 80.0, 90.0, 95.0])
        metrics = compute_portfolio_metrics(series)
        assert metrics["max_drawdown"] is not None
        assert metrics["max_drawdown"] < 0

    def test_volatility_positive(self):
        series = pd.Series([100, 102, 99, 104, 101, 106, 103, 108])
        metrics = compute_portfolio_metrics(series)
        assert metrics["volatility"] is not None
        assert metrics["volatility"] > 0

    def test_returns_all_keys(self):
        series = pd.Series([100, 110, 105, 115, 112])
        metrics = compute_portfolio_metrics(series)
        assert set(metrics.keys()) == {"sharpe", "max_drawdown", "volatility"}


# ── compute_drawdown_series ────────────────────────────────────────────────

class TestComputeDrawdownSeries:
    def test_new_high_is_zero(self):
        series = pd.Series([100.0, 110.0, 120.0])
        dd = compute_drawdown_series(series)
        assert all(abs(v) < 1e-9 for v in dd)

    def test_drop_from_peak(self):
        series = pd.Series([100.0, 110.0, 88.0])
        dd = compute_drawdown_series(series)
        # At index 2: (88 - 110) / 110 * 100 = -20%
        assert abs(dd.iloc[2] - (-20.0)) < 0.01

    def test_recovery_partial(self):
        series = pd.Series([100.0, 80.0, 90.0])
        dd = compute_drawdown_series(series)
        assert abs(dd.iloc[1] - (-20.0)) < 0.01
        assert abs(dd.iloc[2] - (-10.0)) < 0.01

    def test_single_value_is_zero(self):
        series = pd.Series([100.0])
        dd = compute_drawdown_series(series)
        assert abs(dd.iloc[0]) < 1e-9
