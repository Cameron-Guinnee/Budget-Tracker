"""
Net Worth page — combines ledger account balances with live portfolio value.
"""

import io
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from utils import get_worksheet_dataframe, get_worksheet
from portfolio_utils import load_portfolio_df, prep_portfolio_df, compute_portfolio_value_over_time

NW_TTL = 10 * 60
INFLOW_CATEGORIES = {"Income", "Deposit", "Transfer In"}


@st.cache_data(ttl=NW_TTL)
def _load_ledger() -> pd.DataFrame | None:
    from streamlit_gsheets import GSheetsConnection
    df = get_worksheet_dataframe()
    if df is not None:
        return df
    conn = st.connection("gsheets", type=GSheetsConnection)
    return conn.read(worksheet=get_worksheet(), ttl=NW_TTL)


@st.cache_data(ttl=NW_TTL)
def _load_portfolio() -> pd.DataFrame | None:
    return load_portfolio_df()


@st.cache_data(ttl=NW_TTL, show_spinner="Building portfolio history…")
def _portfolio_value_over_time(df_json: str) -> pd.DataFrame:
    df = pd.read_json(io.StringIO(df_json), orient="records", convert_dates=["Date"])
    return compute_portfolio_value_over_time(df)


def _prep_ledger(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df.columns = df.iloc[0]
    df = df[1:]
    df = df.dropna(subset=["Date", "Price", "Category"])
    df["Price"] = pd.to_numeric(df["Price"].map(lambda x: str(x).lstrip("$").replace(",", "")),
                                errors="coerce").fillna(0.0)
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y", errors="coerce")
    df = df.dropna(subset=["Date"])
    if "Account" not in df.columns:
        df["Account"] = "Checking"
    df["Signed Amount"] = df.apply(
        lambda r: r["Price"] if r["Category"] in INFLOW_CATEGORIES else -r["Price"], axis=1
    )
    return df.sort_values("Date")


# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── Load data ──────────────────────────────────────────────────────────────
raw_ledger = _load_ledger()
raw_portfolio = _load_portfolio()

ledger_ok = raw_ledger is not None
portfolio_ok = raw_portfolio is not None and not raw_portfolio.empty

if not ledger_ok and not portfolio_ok:
    st.error("Neither ledger nor portfolio data is available. Configure both sheets first.")
    st.stop()

# ── Process ledger balances ────────────────────────────────────────────────
if ledger_ok:
    ledger_df = _prep_ledger(raw_ledger)
    end_date = ledger_df["Date"].max().normalize()
    start_date = ledger_df["Date"].min().normalize()
    date_index = pd.date_range(start=start_date, end=end_date, freq="D")

    account_balance_series: dict[str, pd.Series] = {}
    for acct, grp in ledger_df.groupby("Account"):
        daily = grp.groupby("Date")["Signed Amount"].sum().reindex(date_index, fill_value=0.0)
        account_balance_series[acct] = daily.cumsum()

    ledger_total = pd.Series(0.0, index=date_index)
    for s in account_balance_series.values():
        ledger_total += s
else:
    end_date = pd.Timestamp.today().normalize()
    start_date = end_date
    date_index = pd.date_range(start=start_date, end=end_date, freq="D")
    ledger_total = pd.Series(0.0, index=date_index)

# ── Process portfolio value ────────────────────────────────────────────────
if portfolio_ok:
    port_df = prep_portfolio_df(raw_portfolio)
    port_value_df = _portfolio_value_over_time(
        port_df.to_json(orient="records", date_format="iso")
    )
    if not port_value_df.empty:
        port_series = port_value_df.set_index("Date")["Total Value"]
        port_series.index = pd.to_datetime(port_series.index).normalize()
    else:
        port_series = pd.Series(dtype=float)
else:
    port_series = pd.Series(dtype=float)

# ── Combine into unified date range ───────────────────────────────────────
all_start = min(
    ledger_total.index[0] if ledger_ok else end_date,
    port_series.index[0] if not port_series.empty else end_date,
)
all_end = max(
    ledger_total.index[-1] if ledger_ok else start_date,
    port_series.index[-1] if not port_series.empty else start_date,
)
full_index = pd.date_range(start=all_start, end=all_end, freq="D")

ledger_aligned = ledger_total.reindex(full_index).ffill().fillna(0.0)
port_aligned = port_series.reindex(full_index).ffill().fillna(0.0) if not port_series.empty \
    else pd.Series(0.0, index=full_index)

net_worth = ledger_aligned + port_aligned

# ── Current snapshot KPIs ─────────────────────────────────────────────────
current_ledger = float(ledger_aligned.iloc[-1]) if ledger_ok else 0.0
current_portfolio = float(port_aligned.iloc[-1]) if portfolio_ok else 0.0
current_net_worth = current_ledger + current_portfolio

k1, k2, k3 = st.columns(3)
k1.metric("🏦 Account Balances", f"${current_ledger:,.2f}")
k2.metric("💼 Portfolio Value", f"${current_portfolio:,.2f}")
k3.metric("📊 Net Worth", f"${current_net_worth:,.2f}")

st.divider()

# ── Net worth chart ────────────────────────────────────────────────────────
st.subheader("Net Worth Over Time")

nw_df = pd.DataFrame({
    "Date": full_index,
    "Account Balances": ledger_aligned.values,
    "Portfolio": port_aligned.values,
    "Net Worth": net_worth.values,
})

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=nw_df["Date"], y=nw_df["Net Worth"],
    name="Net Worth", fill="tozeroy",
    line=dict(color="#7cfc00", width=2),
    hovertemplate="%{x|%b %d, %Y}<br>Net Worth: $%{y:,.2f}<extra></extra>",
))
if ledger_ok:
    fig.add_trace(go.Scatter(
        x=nw_df["Date"], y=nw_df["Account Balances"],
        name="Account Balances", line=dict(color="#4169e1", dash="dot"),
        hovertemplate="%{x|%b %d, %Y}<br>Balances: $%{y:,.2f}<extra></extra>",
    ))
if portfolio_ok and not port_series.empty:
    fig.add_trace(go.Scatter(
        x=nw_df["Date"], y=nw_df["Portfolio"],
        name="Portfolio", line=dict(color="#ffa500", dash="dot"),
        hovertemplate="%{x|%b %d, %Y}<br>Portfolio: $%{y:,.2f}<extra></extra>",
    ))
fig.update_yaxes(title="", tickprefix="$", tickformat=",.0f")
fig.update_xaxes(title="")
fig.update_layout(hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

# ── Assets / Liabilities split ────────────────────────────────────────────
if ledger_ok and account_balance_series:
    st.divider()
    st.subheader("Assets & Liabilities Breakdown")

    latest_balances = {acct: float(s.iloc[-1]) for acct, s in account_balance_series.items()}
    if not port_series.empty:
        latest_balances["Portfolio"] = float(port_aligned.iloc[-1])

    assets = {k: v for k, v in latest_balances.items() if v >= 0}
    liabilities = {k: abs(v) for k, v in latest_balances.items() if v < 0}

    col_a, col_l = st.columns(2)
    with col_a:
        if assets:
            asset_df = pd.DataFrame(assets.items(), columns=["Account", "Value"])
            fig_a = px.pie(asset_df, values="Value", names="Account",
                           hole=0.6, title=f"Assets — ${sum(assets.values()):,.0f}")
            fig_a.update_traces(
                textinfo="percent+label",
                hovertemplate="%{label}<br>$%{value:,.2f}<extra></extra>",
            )
            fig_a.update_layout(showlegend=False)
            st.plotly_chart(fig_a, use_container_width=True)
        else:
            st.info("No assets found.")

    with col_l:
        if liabilities:
            liab_df = pd.DataFrame(liabilities.items(), columns=["Account", "Value"])
            fig_l = px.pie(liab_df, values="Value", names="Account",
                           hole=0.6, title=f"Liabilities — ${sum(liabilities.values()):,.0f}")
            fig_l.update_traces(
                textinfo="percent+label",
                hovertemplate="%{label}<br>$%{value:,.2f}<extra></extra>",
            )
            fig_l.update_layout(showlegend=False)
            st.plotly_chart(fig_l, use_container_width=True)
        else:
            st.info("No liabilities found (all account balances are positive).")
