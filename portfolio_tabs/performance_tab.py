import io
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from portfolio_utils import (
    compute_holdings, compute_portfolio_value_over_time,
    compute_portfolio_metrics, compute_drawdown_series,
    compute_xirr, compute_tax_lots,
    fetch_benchmark_history, cached_live_prices,
)

BENCHMARKS = {"None": None, "SPY (S&P 500)": "SPY", "QQQ (Nasdaq 100)": "QQQ"}


@st.cache_data(ttl=3600, show_spinner="Building portfolio history…")
def _cached_value_over_time(df_json: str) -> pd.DataFrame:
    df = pd.read_json(io.StringIO(df_json), orient="records", convert_dates=["Date"])
    return compute_portfolio_value_over_time(df)


def performance_tab(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No portfolio transactions found. Add your first position in the **Add Transaction** tab.")
        return

    holdings = compute_holdings(df)
    open_positions = holdings[holdings["Shares"] > 0]

    # ── Live terminal value for XIRR ──────────────────────────────────────
    terminal_value = 0.0
    if not open_positions.empty:
        syms = tuple(open_positions["Symbol"].tolist())
        live = cached_live_prices(syms)
        terminal_value = float(
            open_positions.apply(lambda r: r["Shares"] * live.get(r["Symbol"], 0.0), axis=1).sum()
        )

    # ── Build cashflow list for XIRR ──────────────────────────────────────
    cashflows = []
    for _, row in df.iterrows():
        if row["Transaction Type"] == "Buy":
            cashflows.append((row["Date"], -float(row["Total"])))
        elif row["Transaction Type"] in ("Sell", "Dividend"):
            cashflows.append((row["Date"], float(row["Total"])))

    xirr_val = compute_xirr(cashflows, terminal_value=terminal_value)

    # ── Portfolio value series ─────────────────────────────────────────────
    value_df = _cached_value_over_time(df.to_json(orient="records", date_format="iso"))

    # ── KPI metrics ───────────────────────────────────────────────────────
    if not value_df.empty:
        first_nonzero = value_df[value_df["Total Value"] > 0]
        start_val = float(first_nonzero["Total Value"].iloc[0]) if not first_nonzero.empty else 0.0
        end_val = float(value_df["Total Value"].iloc[-1])
        total_return_pct = (end_val / start_val - 1) * 100 if start_val > 0 else 0.0
        metrics = compute_portfolio_metrics(value_df["Total Value"])
    else:
        total_return_pct = 0.0
        metrics = {"sharpe": None, "max_drawdown": None, "volatility": None}

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("📈 Total Return", f"{total_return_pct:+.1f}%")
    k2.metric("💹 XIRR", f"{xirr_val * 100:+.1f}%" if xirr_val is not None else "N/A")
    k3.metric("⚡ Sharpe", f"{metrics['sharpe']:.2f}" if metrics["sharpe"] is not None else "N/A")
    k4.metric("📉 Max Drawdown",
              f"{metrics['max_drawdown'] * 100:.1f}%" if metrics["max_drawdown"] is not None else "N/A")
    k5.metric("〰️ Volatility",
              f"{metrics['volatility'] * 100:.1f}%" if metrics["volatility"] is not None else "N/A")

    st.divider()

    # ── Portfolio value chart with benchmark overlay ───────────────────────
    bench_label = st.selectbox("Benchmark overlay", list(BENCHMARKS.keys()), index=0,
                                key="perf_benchmark")
    bench_sym = BENCHMARKS[bench_label]

    st.subheader("Portfolio Value Over Time")

    if not value_df.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=value_df["Date"], y=value_df["Total Value"],
            fill="tozeroy", name="Portfolio",
            line=dict(color="#4169e1"),
            hovertemplate="%{x|%b %d, %Y}<br>$%{y:,.2f}<extra>Portfolio</extra>",
        ))

        if bench_sym:
            start_ts = value_df["Date"].min()
            end_ts = value_df["Date"].max()
            bench = fetch_benchmark_history(bench_sym, start_ts, end_ts)
            if not bench.empty:
                # Normalize both to the portfolio start value for visual comparison
                portfolio_start = value_df[value_df["Total Value"] > 0]["Total Value"].iloc[0]
                bench_start = bench[bench > 0].iloc[0] if (bench > 0).any() else 1.0
                bench_scaled = bench / float(bench_start) * portfolio_start
                bench_df = bench_scaled.reset_index()
                bench_df.columns = ["Date", "Value"]
                fig.add_trace(go.Scatter(
                    x=bench_df["Date"], y=bench_df["Value"],
                    name=bench_label, line=dict(color="#ffa500", dash="dash"),
                    hovertemplate="%{x|%b %d, %Y}<br>$%{y:,.2f}<extra>" + bench_label + "</extra>",
                ))

        fig.update_yaxes(title="", tickprefix="$", tickformat=",.0f")
        fig.update_xaxes(title="")
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        # ── Drawdown chart ─────────────────────────────────────────────────
        with st.expander("Drawdown chart"):
            dd = compute_drawdown_series(value_df["Total Value"])
            dd_df = pd.DataFrame({"Date": value_df["Date"], "Drawdown %": dd.values})
            dd_fig = px.area(dd_df, x="Date", y="Drawdown %",
                             color_discrete_sequence=["#fc0000"])
            dd_fig.update_yaxes(title="", ticksuffix="%")
            dd_fig.update_xaxes(title="")
            dd_fig.update_traces(hovertemplate="%{x|%b %d, %Y}<br>%{y:.1f}%<extra></extra>")
            st.plotly_chart(dd_fig, use_container_width=True)
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
            var_name="Type", value_name="Amount",
        )
        bar = px.bar(
            melted, x="Symbol", y="Amount", color="Type", barmode="group",
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
        st.divider()

    # ── Tax-lot report ─────────────────────────────────────────────────────
    lots_df = compute_tax_lots(df)
    if not lots_df.empty:
        with st.expander("Tax-lot report"):
            year_opts = sorted(lots_df["Sell Date"].dt.year.unique().tolist(), reverse=True)
            tax_year = st.selectbox("Tax year", ["All"] + year_opts, key="tax_year")
            filtered_lots = lots_df if tax_year == "All" else \
                lots_df[lots_df["Sell Date"].dt.year == int(tax_year)]

            st_total = filtered_lots[filtered_lots["Term"] == "Short-term"]["Gain/Loss"].sum()
            lt_total = filtered_lots[filtered_lots["Term"] == "Long-term"]["Gain/Loss"].sum()
            tc1, tc2, tc3 = st.columns(3)
            tc1.metric("Short-term Gains", f"${st_total:,.2f}")
            tc2.metric("Long-term Gains", f"${lt_total:,.2f}")
            tc3.metric("Total Realized", f"${st_total + lt_total:,.2f}")

            display = filtered_lots.copy()
            display["Buy Date"] = display["Buy Date"].dt.strftime("%m/%d/%Y")
            display["Sell Date"] = display["Sell Date"].dt.strftime("%m/%d/%Y")

            def color_gain(val):
                return f"color: {'#7cfc00' if val >= 0 else '#fc0000'}"

            st.dataframe(
                display.style
                .format({
                    "Shares": "{:,.6f}",
                    "Cost Per Share": "${:,.4f}",
                    "Cost Basis": "${:,.2f}",
                    "Proceeds": "${:,.2f}",
                    "Gain/Loss": "${:,.2f}",
                })
                .map(color_gain, subset=["Gain/Loss"]),
                hide_index=True, use_container_width=True,
            )

            csv = display.to_csv(index=False).encode()
            st.download_button(
                "⬇️ Download CSV",
                data=csv,
                file_name=f"tax_lots{'_' + str(tax_year) if tax_year != 'All' else ''}.csv",
                mime="text/csv",
            )

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
