import streamlit as st
import pandas as pd
import plotly.express as px
from portfolio_utils import compute_holdings, compute_portfolio_value_over_time


@st.cache_data(ttl=3600, show_spinner="Building portfolio history (this may take a moment)…")
def _cached_value_over_time(df_json: str) -> pd.DataFrame:
    df = pd.read_json(df_json, orient="records", convert_dates=["Date"])
    return compute_portfolio_value_over_time(df)


def performance_tab(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No portfolio transactions found. Add your first position in the **Add Transaction** tab.")
        return

    holdings = compute_holdings(df)

    # ── Portfolio value over time ──────────────────────────────────────────
    st.subheader("Portfolio Value Over Time")
    value_df = _cached_value_over_time(df.to_json(orient="records", date_format="iso"))

    if not value_df.empty:
        fig = px.area(value_df, x="Date", y="Total Value", color_discrete_sequence=["#4169e1"])
        fig.update_yaxes(title="", tickprefix="$", tickformat=",.0f")
        fig.update_xaxes(title="")
        fig.update_traces(hovertemplate="%{x|%b %d, %Y}<br>$%{y:,.2f}<extra></extra>")
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Historical price data unavailable for the selected symbols.")

    st.divider()

    # ── Realized gains by symbol ───────────────────────────────────────────
    gains_df = holdings[["Symbol", "Asset Type", "Realized Gains", "Dividend Income"]].copy()
    gains_df = gains_df[(gains_df["Realized Gains"] != 0) | (gains_df["Dividend Income"] != 0)]

    if not gains_df.empty:
        st.subheader("Realized Gains & Dividend Income by Symbol")
        melted = gains_df.melt(
            id_vars=["Symbol", "Asset Type"],
            value_vars=["Realized Gains", "Dividend Income"],
            var_name="Type",
            value_name="Amount",
        )
        bar = px.bar(
            melted,
            x="Symbol",
            y="Amount",
            color="Type",
            barmode="group",
            color_discrete_map={"Realized Gains": "#4169e1", "Dividend Income": "#7cfc00"},
            text_auto=".2s",
        )
        bar.update_yaxes(title="", tickprefix="$", tickformat=",.0f")
        bar.update_xaxes(title="")
        bar.update_traces(
            hovertemplate="%{x}<br>%{y:$,.2f}<extra></extra>",
            textfont_size=12, textangle=0, textposition="outside", cliponaxis=False,
        )
        st.plotly_chart(bar, use_container_width=True)

    # ── Transaction history ────────────────────────────────────────────────
    st.subheader("Transaction History")
    display = df.sort_values("Date", ascending=False).copy()
    display["Date"] = display["Date"].dt.strftime("%m/%d/%Y")

    def color_txn_type(val: str) -> str:
        return {
            "Buy": "color: #4169e1",
            "Sell": "color: #fc0000",
            "Dividend": "color: #7cfc00",
        }.get(str(val), "")

    styled = (
        display.style
        .format({"Shares": "{:,.6f}", "Price Per Share": "${:,.4f}", "Total": "${:,.2f}"})
        .map(color_txn_type, subset=["Transaction Type"])
    )
    st.dataframe(styled, hide_index=True, use_container_width=True)
