"""Tests for pure logic in ledger tab modules."""

import sys
import pandas as pd
import pytest

from tests.conftest import make_ledger_df

# pandas datetime conversion crashes on Python 3.14 — skip affected tests
_NEEDS_DATETIME = pytest.mark.skipif(
    sys.version_info >= (3, 14),
    reason="pandas datetime parsing crashes on Python 3.14 (target env is ≤3.13)",
)


# ── accounts_tab helpers ───────────────────────────────────────────────────

from tabs.accounts_tab import _ensure_account_and_signed_amount, _balance_timeseries


@_NEEDS_DATETIME
class TestEnsureAccountAndSignedAmount:
    def _make(self, rows):
        df = pd.DataFrame(rows)
        df["Date"] = pd.to_datetime(df["Date"])
        df["Price"] = df["Price"].astype(float)
        return df

    def test_income_is_positive(self):
        df = self._make([{
            "Date": "2024-01-15", "Account": "Checking",
            "Category": "Income", "Price": 3000,
        }])
        result = _ensure_account_and_signed_amount(df)
        assert result["Signed Amount"].iloc[0] == 3000

    def test_expense_is_negative(self):
        df = self._make([{
            "Date": "2024-01-20", "Account": "Checking",
            "Category": "Dining", "Price": 50,
        }])
        result = _ensure_account_and_signed_amount(df)
        assert result["Signed Amount"].iloc[0] == -50

    def test_transfer_in_is_positive(self):
        df = self._make([{
            "Date": "2024-01-10", "Account": "Savings",
            "Category": "Transfer In", "Price": 500,
        }])
        result = _ensure_account_and_signed_amount(df)
        assert result["Signed Amount"].iloc[0] == 500

    def test_missing_account_defaults_to_checking(self):
        df = pd.DataFrame([{"Category": "Income", "Price": 1000.0}])
        df["Date"] = pd.to_datetime(["2024-01-01"])
        result = _ensure_account_and_signed_amount(df)
        assert "Account" in result.columns
        assert result["Account"].iloc[0] == "Checking"

    def test_mixed_inflows_and_outflows(self):
        df = self._make([
            {"Date": "2024-01-01", "Account": "Checking", "Category": "Income", "Price": 5000},
            {"Date": "2024-01-05", "Account": "Checking", "Category": "Grocery", "Price": 200},
            {"Date": "2024-01-10", "Account": "Checking", "Category": "Transfer In", "Price": 1000},
        ])
        result = _ensure_account_and_signed_amount(df)
        assert result["Signed Amount"].tolist() == [5000, -200, 1000]


@_NEEDS_DATETIME
class TestBalanceTimeseries:
    def _prep(self, rows):
        df = pd.DataFrame(rows)
        df["Date"] = pd.to_datetime(df["Date"])
        df["Price"] = df["Price"].astype(float)
        return _ensure_account_and_signed_amount(df)

    def test_single_transaction_balance(self):
        df = self._prep([{
            "Date": "2024-01-15", "Account": "Checking",
            "Category": "Income", "Price": 1000,
        }])
        start = pd.Timestamp("2024-01-01")
        end = pd.Timestamp("2024-01-31")
        result = _balance_timeseries(df, start, end, freq="D")
        row_after = result[
            (result["Account"] == "Checking") &
            (result["Date"] == pd.Timestamp("2024-01-15"))
        ]
        assert float(row_after["Balance"].iloc[0]) == 1000

    def test_carry_in_before_start(self):
        df = self._prep([
            {"Date": "2023-12-01", "Account": "Checking", "Category": "Income", "Price": 5000},
            {"Date": "2024-01-15", "Account": "Checking", "Category": "Dining", "Price": 100},
        ])
        start = pd.Timestamp("2024-01-01")
        end = pd.Timestamp("2024-01-31")
        result = _balance_timeseries(df, start, end, freq="D")
        row_start = result[
            (result["Account"] == "Checking") & (result["Date"] == start)
        ]
        assert float(row_start["Balance"].iloc[0]) == 5000

    def test_multiple_accounts_independent(self):
        df = self._prep([
            {"Date": "2024-01-10", "Account": "Checking", "Category": "Income", "Price": 3000},
            {"Date": "2024-01-10", "Account": "Savings", "Category": "Income", "Price": 1000},
        ])
        start = pd.Timestamp("2024-01-01")
        end = pd.Timestamp("2024-01-31")
        result = _balance_timeseries(df, start, end, freq="D")
        checking = result[
            (result["Account"] == "Checking") & (result["Date"] == end)
        ]
        savings = result[
            (result["Account"] == "Savings") & (result["Date"] == end)
        ]
        assert float(checking["Balance"].iloc[0]) == 3000
        assert float(savings["Balance"].iloc[0]) == 1000

    def test_cumulative_over_time(self):
        df = self._prep([
            {"Date": "2024-01-05", "Account": "Checking", "Category": "Income", "Price": 1000},
            {"Date": "2024-01-10", "Account": "Checking", "Category": "Dining", "Price": 200},
            {"Date": "2024-01-20", "Account": "Checking", "Category": "Income", "Price": 500},
        ])
        start = pd.Timestamp("2024-01-01")
        end = pd.Timestamp("2024-01-31")
        result = _balance_timeseries(df, start, end, freq="D")
        final = result[(result["Account"] == "Checking") & (result["Date"] == end)]
        assert float(final["Balance"].iloc[0]) == pytest.approx(1300, abs=0.01)


# ── subscriptions_tab helpers ──────────────────────────────────────────────

from tabs.subscriptions_tab import _detect_subscriptions, _flag_anomalies


@_NEEDS_DATETIME
class TestDetectSubscriptions:
    def _make(self, rows):
        df = pd.DataFrame(rows)
        df["Date"] = pd.to_datetime(df["Date"])
        df["Price"] = df["Price"].astype(float)
        return df

    def test_detects_consistent_recurring_memo(self):
        rows = [
            {"Date": f"2024-{m:02d}-01", "Memo": "Netflix", "Category": "Entertainment", "Price": 15.99}
            for m in range(1, 5)
        ]
        df = self._make(rows)
        result = _detect_subscriptions(df)
        assert not result.empty
        assert "Netflix" in result["Memo"].values

    def test_requires_minimum_three_months(self):
        rows = [
            {"Date": f"2024-{m:02d}-01", "Memo": "Netflix", "Category": "Entertainment", "Price": 15.99}
            for m in range(1, 3)
        ]
        df = self._make(rows)
        result = _detect_subscriptions(df)
        assert result.empty

    def test_ignores_high_variance_memo(self):
        rows = [
            {"Date": "2024-01-01", "Memo": "Restaurant", "Category": "Dining", "Price": 10},
            {"Date": "2024-02-01", "Memo": "Restaurant", "Category": "Dining", "Price": 80},
            {"Date": "2024-03-01", "Memo": "Restaurant", "Category": "Dining", "Price": 5},
            {"Date": "2024-04-01", "Memo": "Restaurant", "Category": "Dining", "Price": 200},
        ]
        df = self._make(rows)
        result = _detect_subscriptions(df)
        assert result.empty

    def test_case_insensitive_memo_matching(self):
        rows = [
            {"Date": "2024-01-01", "Memo": "spotify", "Category": "Entertainment", "Price": 9.99},
            {"Date": "2024-02-01", "Memo": "Spotify", "Category": "Entertainment", "Price": 9.99},
            {"Date": "2024-03-01", "Memo": "SPOTIFY", "Category": "Entertainment", "Price": 9.99},
        ]
        df = self._make(rows)
        result = _detect_subscriptions(df)
        assert not result.empty

    def test_estimated_annual_cost(self):
        rows = [
            {"Date": f"2024-{m:02d}-01", "Memo": "Gym", "Category": "Health & Fitness", "Price": 50.0}
            for m in range(1, 5)
        ]
        df = self._make(rows)
        result = _detect_subscriptions(df)
        assert not result.empty
        assert abs(result.iloc[0]["Est. Annual Cost"] - 600.0) < 0.01

    def test_empty_df_returns_empty(self):
        df = self._make([])
        result = _detect_subscriptions(df)
        assert result.empty


@_NEEDS_DATETIME
class TestFlagAnomalies:
    def _make(self, rows):
        df = pd.DataFrame(rows)
        df["Date"] = pd.to_datetime(df["Date"])
        df["Price"] = df["Price"].astype(float)
        return df

    def test_flags_statistical_outlier(self):
        rows = (
            [{"Date": f"2024-01-{d:02d}", "Memo": "Grocery run", "Category": "Grocery", "Price": 80}
             for d in range(1, 6)]
            + [{"Date": "2024-01-20", "Memo": "Big shop", "Category": "Grocery", "Price": 1000}]
        )
        df = self._make(rows)
        result = _flag_anomalies(df, z_threshold=2.0)
        assert not result.empty
        assert "Big shop" in result["Memo"].values

    def test_no_anomalies_in_uniform_data(self):
        rows = [
            {"Date": f"2024-01-{d:02d}", "Memo": "Coffee", "Category": "Dining", "Price": 5.0}
            for d in range(1, 8)
        ]
        df = self._make(rows)
        result = _flag_anomalies(df, z_threshold=2.0)
        assert result.empty

    def test_skips_categories_with_fewer_than_5_transactions(self):
        rows = [
            {"Date": f"2024-01-{d:02d}", "Memo": "Something", "Category": "Rare", "Price": 100 * d}
            for d in range(1, 4)
        ]
        df = self._make(rows)
        result = _flag_anomalies(df, z_threshold=2.0)
        assert result.empty

    def test_higher_threshold_flags_fewer_anomalies(self):
        rows = (
            [{"Date": f"2024-01-{d:02d}", "Memo": "Groceries", "Category": "Grocery", "Price": 100}
             for d in range(1, 8)]
            + [{"Date": "2024-01-20", "Memo": "Big run", "Category": "Grocery", "Price": 500}]
        )
        df = self._make(rows)
        low = _flag_anomalies(df, z_threshold=1.0)
        high = _flag_anomalies(df, z_threshold=3.5)
        assert len(low) >= len(high)

    def test_result_contains_zscore_column(self):
        rows = (
            [{"Date": f"2024-01-{d:02d}", "Memo": "Grocery", "Category": "Grocery", "Price": 50}
             for d in range(1, 7)]
            + [{"Date": "2024-01-20", "Memo": "Huge", "Category": "Grocery", "Price": 2000}]
        )
        df = self._make(rows)
        result = _flag_anomalies(df, z_threshold=2.0)
        assert "Z-Score" in result.columns
        assert result["Z-Score"].iloc[0] > 0

    def test_empty_df_returns_empty(self):
        df = self._make([])
        result = _flag_anomalies(df, z_threshold=2.0)
        assert result.empty


# ── Ledger KPI helper ──────────────────────────────────────────────────────
# Mirror of the _kpis() function in pages/ledger.py.
# No datetime operations — runs on all Python versions.

NON_EXPENSE_CATS = {"Income", "Transfer In", "Transfer Out", "Savings"}


def _kpis(frame: pd.DataFrame):
    g = frame.groupby("Category", as_index=False)["Price"].sum()
    inc = g.loc[g["Category"] == "Income", "Price"].sum()
    exp = g.loc[~g["Category"].isin(NON_EXPENSE_CATS), "Price"].sum()
    sav = inc - exp
    rate = (sav / inc * 100) if inc else 0.0
    return inc, exp, sav, rate


class TestLedgerKpis:
    def _make(self, rows):
        if not rows:
            return pd.DataFrame(columns=["Category", "Price"])
        df = pd.DataFrame(rows)
        df = df.assign(Price=df["Price"].astype(float))
        return df

    def test_basic_income_and_expense(self):
        df = self._make([
            {"Category": "Income", "Price": 5000},
            {"Category": "Dining", "Price": 200},
            {"Category": "Grocery", "Price": 300},
        ])
        inc, exp, sav, rate = _kpis(df)
        assert inc == 5000
        assert exp == 500
        assert sav == 4500
        assert abs(rate - 90.0) < 0.01

    def test_transfers_excluded_from_expenses(self):
        df = self._make([
            {"Category": "Income", "Price": 3000},
            {"Category": "Transfer In", "Price": 1000},
            {"Category": "Transfer Out", "Price": 1000},
            {"Category": "Dining", "Price": 200},
        ])
        inc, exp, sav, rate = _kpis(df)
        assert inc == 3000
        assert exp == 200
        assert sav == 2800

    def test_savings_category_excluded_from_expenses(self):
        df = self._make([
            {"Category": "Income", "Price": 4000},
            {"Category": "Savings", "Price": 1000},
            {"Category": "Housing", "Price": 1500},
        ])
        inc, exp, sav, rate = _kpis(df)
        assert exp == 1500

    def test_zero_income_savings_rate_is_zero(self):
        df = self._make([{"Category": "Dining", "Price": 100}])
        inc, exp, sav, rate = _kpis(df)
        assert inc == 0
        assert rate == 0.0

    def test_negative_savings(self):
        df = self._make([
            {"Category": "Income", "Price": 1000},
            {"Category": "Dining", "Price": 1500},
        ])
        inc, exp, sav, rate = _kpis(df)
        assert sav == -500
        assert rate < 0

    def test_no_data_all_zeros(self):
        df = self._make([])
        inc, exp, sav, rate = _kpis(df)
        assert inc == 0
        assert exp == 0
        assert sav == 0
        assert rate == 0.0
