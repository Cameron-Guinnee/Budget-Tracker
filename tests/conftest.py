"""Shared fixtures and helpers for the Ledgerline test suite."""

import pandas as pd
import pytest


def make_portfolio_df(rows: list[dict]) -> pd.DataFrame:
    """Build a prepped portfolio DataFrame (matching prep_portfolio_df output)."""
    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"])
    df["Shares"] = df["Shares"].astype(float)
    df["Price Per Share"] = df["Price Per Share"].astype(float)
    df["Total"] = df["Total"].astype(float)
    if "Notes" not in df.columns:
        df["Notes"] = ""
    return df


def make_ledger_df(rows: list[dict]) -> pd.DataFrame:
    """Build a prepped ledger DataFrame."""
    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"])
    df["Price"] = df["Price"].astype(float)
    return df


@pytest.fixture
def minimal_secrets_toml(tmp_path):
    """Return a factory that writes a secrets.toml to tmp_path and returns its path."""
    def _factory(content: str) -> str:
        p = tmp_path / "secrets.toml"
        p.write_text(content, encoding="utf-8")
        return str(p)
    return _factory
