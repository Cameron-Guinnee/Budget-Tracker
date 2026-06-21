import streamlit as st
import pandas as pd
import plotly.express as px
from portfolio_utils import compute_holdings, cached_live_prices, cached_dividend_info


def dividends_tab(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No portfolio transactions found. Add your first position in the **Add Transaction** tab.")
        return

    holdings = compute_holdings(df)
    open_positions = holdings[holdings["Shares"] > 0].copy()
    all_positions = holdings.copy()

    # ── Historical dividend income ────────────────────────────────────────
    dividend_txns = df[df["Transaction Type"] == "Dividend"].copy()
    if not dividend_txns.empty:
        st.subheader("Dividend Income History")
        dividend_txns["Period"] = dividend_txns["Date"].dt.to_period("Q").astype(str)
        div_by_period = (
            dividend_txns.groupby(["Period", "Symbol"])["Total"].sum().reset_index()
        )
        fig = px.bar(
            div_by_period, x="Period", y="Total", color="Symbol",
            barmode="stack", text_auto=".2s",
        )
        fig.update_yaxes(title="", tickprefix="$")
        fig.update_xaxes(title="")
        fig.update_traces(hovertemplate="%{x}<br>%{fullData.name}: $%{y:,.2f}<extra></extra>")
        st.plotly_chart(fig, use_container_width=True)
        st.divider()

    # ── Yield-on-cost and projected income ────────────────────────────────
    if open_positions.empty:
        st.info("No open positions.")
        return

    syms = tuple(open_positions["Symbol"].tolist())
    live = cached_live_prices(syms)
    div_info = cached_dividend_info(syms)

    open_positions["Current Price"] = open_positions["Symbol"].map(live)
    open_positions["Annual Dividend Rate"] = open_positions["Symbol"].map(
        lambda s: div_info.get(s, {}).get("rate") or 0.0
    )
    open_positions["Projected Annual Income"] = (
        open_positions["Shares"] * open_positions["Annual Dividend Rate"]
    )
    open_positions["Yield on Cost"] = (
        open_positions["Annual Dividend Rate"] / open_positions["Avg Cost"] * 100
    ).where(open_positions["Avg Cost"] > 0)
    open_positions["Current Yield %"] = open_positions["Symbol"].map(
        lambda s: div_info.get(s, {}).get("yield_pct") or 0.0
    )

    total_projected = open_positions["Projected Annual Income"].sum()
    total_received = all_positions["Dividend Income"].sum()

    c1, c2 = st.columns(2)
    c1.metric("📅 Projected Annual Income", f"${total_projected:,.2f}")
    c2.metric("✅ Total Dividends Received", f"${total_received:,.2f}")

    st.subheader("Yield-on-Cost by Holding")
    paying = open_positions[open_positions["Annual Dividend Rate"] > 0].copy()
    if paying.empty:
        st.info("No dividend-paying open positions found (yfinance reports no dividend rate).")
    else:
        display = paying[[
            "Symbol", "Shares", "Avg Cost", "Annual Dividend Rate",
            "Projected Annual Income", "Yield on Cost", "Current Yield %",
        ]].copy()
        st.dataframe(
            display.style.format({
                "Shares": "{:,.6f}",
                "Avg Cost": "${:,.2f}",
                "Annual Dividend Rate": "${:,.4f}",
                "Projected Annual Income": "${:,.2f}",
                "Yield on Cost": "{:.2f}%",
                "Current Yield %": "{:.2f}%",
            }),
            hide_index=True, use_container_width=True,
        )

    # ── Upcoming ex-dividend dates ────────────────────────────────────────
    st.subheader("Upcoming Ex-Dividend Dates")
    today = pd.Timestamp.today().normalize()
    upcoming = []
    for sym in syms:
        info = div_info.get(sym, {})
        ex_ts = info.get("ex_date")
        if ex_ts:
            try:
                ex_date = pd.Timestamp(ex_ts, unit="s") if isinstance(ex_ts, (int, float)) \
                    else pd.Timestamp(ex_ts)
                ex_date = ex_date.normalize()
                if ex_date >= today:
                    upcoming.append({
                        "Symbol": sym,
                        "Ex-Dividend Date": ex_date,
                        "Annual Rate": info.get("rate"),
                    })
            except Exception:
                pass

    if upcoming:
        upcoming_df = pd.DataFrame(upcoming).sort_values("Ex-Dividend Date")
        upcoming_df["Ex-Dividend Date"] = upcoming_df["Ex-Dividend Date"].dt.strftime("%m/%d/%Y")
        st.dataframe(
            upcoming_df.style.format({"Annual Rate": "${:,.4f}"}),
            hide_index=True, use_container_width=True,
        )
    else:
        st.info("No upcoming ex-dividend dates found for open positions.")
