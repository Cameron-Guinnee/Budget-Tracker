import streamlit as st
import pandas as pd
import plotly.express as px
from portfolio_utils import compute_holdings, fetch_live_prices

ASSET_TYPE_COLORS = {"Stock": "#4169e1", "Crypto": "#f7931a"}


@st.cache_data(ttl=300, show_spinner="Fetching live prices…")
def _cached_live_prices(symbols: tuple[str, ...]) -> dict[str, float]:
    return fetch_live_prices(list(symbols))


def holdings_tab(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No portfolio transactions found. Add your first position in the **Add Transaction** tab.")
        return

    holdings = compute_holdings(df)
    open_positions = holdings[holdings["Shares"] > 0].copy()

    if open_positions.empty:
        st.info("No open positions.")
    else:
        symbols = tuple(open_positions["Symbol"].tolist())
        live_prices = _cached_live_prices(symbols)

        open_positions["Current Price"] = open_positions["Symbol"].map(live_prices)
        open_positions["Current Value"] = open_positions["Shares"] * open_positions["Current Price"]
        open_positions["Unrealized P&L"] = open_positions["Current Value"] - open_positions["Cost Basis"]
        open_positions["Unrealized P&L %"] = (
            open_positions["Unrealized P&L"] / open_positions["Cost Basis"] * 100
        ).where(open_positions["Cost Basis"] > 0)

        total_value = open_positions["Current Value"].sum()
        total_cost = open_positions["Cost Basis"].sum()
        total_unrealized = open_positions["Unrealized P&L"].sum()
        total_realized = holdings["Realized Gains"].sum()
        total_dividends = holdings["Dividend Income"].sum()

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("💼 Portfolio Value", f"${total_value:,.2f}")
        k2.metric("💵 Total Cost", f"${total_cost:,.2f}")
        k3.metric("📈 Unrealized P&L", f"${total_unrealized:,.2f}",
                  delta=f"{total_unrealized / total_cost * 100:.1f}%" if total_cost else None)
        k4.metric("✅ Realized Gains", f"${total_realized:,.2f}")
        k5.metric("💰 Dividends", f"${total_dividends:,.2f}")

        st.divider()

        display = open_positions[[
            "Symbol", "Asset Type", "Shares", "Avg Cost",
            "Current Price", "Current Value", "Cost Basis",
            "Unrealized P&L", "Unrealized P&L %",
        ]].copy()

        def color_pnl(val):
            if pd.isna(val):
                return ""
            return f"color: {'#7cfc00' if val >= 0 else '#fc0000'}"

        styled = (
            display.style
            .format({
                "Avg Cost": "${:,.2f}",
                "Current Price": "${:,.4f}",
                "Current Value": "${:,.2f}",
                "Cost Basis": "${:,.2f}",
                "Unrealized P&L": "${:,.2f}",
                "Unrealized P&L %": "{:.2f}%",
                "Shares": "{:,.6f}",
            })
            .map(color_pnl, subset=["Unrealized P&L", "Unrealized P&L %"])
        )

        st.dataframe(styled, hide_index=True, use_container_width=True)
        st.caption("Prices refresh every 5 minutes. Click **🔄 Refresh** in the sidebar to force an update.")

    # Closed / realized gains section
    closed = holdings[holdings["Shares"] <= 0]
    if not closed.empty:
        st.subheader("Closed Positions")
        st.dataframe(
            closed[["Symbol", "Asset Type", "Realized Gains", "Dividend Income"]]
            .style.format({"Realized Gains": "${:,.2f}", "Dividend Income": "${:,.2f}"}),
            hide_index=True,
            use_container_width=True,
        )
