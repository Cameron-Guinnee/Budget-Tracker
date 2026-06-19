import streamlit as st
import pandas as pd
import plotly.express as px
from portfolio_utils import compute_holdings, fetch_live_prices


@st.cache_data(ttl=300, show_spinner="Fetching live prices…")
def _cached_live_prices(symbols: tuple[str, ...]) -> dict[str, float]:
    return fetch_live_prices(list(symbols))


def allocation_tab(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No portfolio transactions found. Add your first position in the **Add Transaction** tab.")
        return

    holdings = compute_holdings(df)
    open_positions = holdings[holdings["Shares"] > 0].copy()

    if open_positions.empty:
        st.info("No open positions to display.")
        return

    symbols = tuple(open_positions["Symbol"].tolist())
    live_prices = _cached_live_prices(symbols)

    open_positions["Current Price"] = open_positions["Symbol"].map(live_prices)
    open_positions["Current Value"] = open_positions["Shares"] * open_positions["Current Price"]
    open_positions = open_positions.dropna(subset=["Current Value"])

    col1, col2 = st.columns(2)

    with col1:
        fig_symbol = px.pie(
            open_positions,
            values="Current Value",
            names="Symbol",
            hole=0.65,
            title="Allocation by Symbol",
        )
        fig_symbol.update_traces(
            textinfo="percent+label",
            hovertemplate="%{label}<br>%{value:$,.2f} (%{percent})<extra></extra>",
        )
        fig_symbol.update_layout(showlegend=False)
        st.plotly_chart(fig_symbol, use_container_width=True)

    with col2:
        type_totals = open_positions.groupby("Asset Type")["Current Value"].sum().reset_index()
        fig_type = px.pie(
            type_totals,
            values="Current Value",
            names="Asset Type",
            hole=0.65,
            title="Allocation by Asset Type",
            color="Asset Type",
            color_discrete_map={"Stock": "#4169e1", "Crypto": "#f7931a"},
        )
        fig_type.update_traces(
            textinfo="percent+label",
            hovertemplate="%{label}<br>%{value:$,.2f} (%{percent})<extra></extra>",
        )
        fig_type.update_layout(showlegend=False)
        st.plotly_chart(fig_type, use_container_width=True)

    st.divider()

    # Treemap for a second look at symbol-level allocation
    total_value = open_positions["Current Value"].sum()
    open_positions["Weight %"] = open_positions["Current Value"] / total_value * 100

    fig_tree = px.treemap(
        open_positions,
        path=["Asset Type", "Symbol"],
        values="Current Value",
        color="Asset Type",
        color_discrete_map={"Stock": "#4169e1", "Crypto": "#f7931a"},
        title="Portfolio Treemap",
    )
    fig_tree.update_traces(
        hovertemplate="%{label}<br>$%{value:,.2f}<extra></extra>",
        textinfo="label+percent root",
    )
    st.plotly_chart(fig_tree, use_container_width=True)
