import pandas as pd
import plotly.express as px
import streamlit as st

INFLOW_CATEGORIES_DEFAULT = {"Income", "Deposit", "Transfer In"}

RANGE_PRESETS = {
    "7D": 7,
    "1M": 30,
    "3M": 90,
    "YTD": "YTD",
    "1Y": 365,
    "All": "ALL",
    "Custom": "CUSTOM",
}

FREQ_MAP = {
    "Daily": "D",
    "Weekly": "W",
    "Monthly": "M",
}

def _ensure_account_and_signed_amount(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Back-compat: if Account doesn't exist, assume Checking
    if "Account" not in df.columns:
        df["Account"] = "Checking"

    # Clean types
    df["Date"] = pd.to_datetime(df["Date"])
    df["Price"] = pd.to_numeric(df["Price"])

    # Signed Amount (for balances)
    inflows = INFLOW_CATEGORIES_DEFAULT
    df["Signed Amount"] = df.apply(
        lambda r: r["Price"] if r["Category"] in inflows else -r["Price"],
        axis=1
    )
    return df

def _balance_timeseries(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, freq: str) -> pd.DataFrame:
    """
    Returns a long dataframe: Date | Account | Balance
    Balance includes carry-in from before `start`.
    """
    df = df.sort_values("Date")

    # carry-in (sum before start)
    carry = (
        df[df["Date"] < start]
        .groupby("Account")["Signed Amount"]
        .sum()
    )

    # net change by day within range
    in_range = df[(df["Date"] >= start) & (df["Date"] <= end)]
    daily_net = (
        in_range
        .groupby(["Account", "Date"])["Signed Amount"]
        .sum()
        .reset_index()
    )

    accounts = sorted(df["Account"].dropna().unique().tolist())
    date_index = pd.date_range(start=start, end=end, freq="D")

    # Build a daily balance series per account, then resample to requested freq (last value)
    frames = []
    for acct in accounts:
        acct_net = daily_net[daily_net["Account"] == acct].set_index("Date")["Signed Amount"]
        acct_net = acct_net.reindex(date_index, fill_value=0.0)
        acct_bal = acct_net.cumsum() + float(carry.get(acct, 0.0))

        s = acct_bal.to_frame("Balance")
        s["Account"] = acct
        s.index.name = "Date"
        frames.append(s.reset_index())

    out = pd.concat(frames, ignore_index=True)

    # Resample for weekly/monthly view (take last balance in period)
    if freq != "D":
        out = (
            out.set_index("Date")
               .groupby("Account")["Balance"]
               .resample(freq)
               .last()
               .reset_index()
        )

    return out

def accounts_tab(df: pd.DataFrame):
    st.header("Account balances")

    df = _ensure_account_and_signed_amount(df)

    # Current balances (as-of max date in data)
    current = df.groupby("Account")["Signed Amount"].sum().sort_values(ascending=False)

    cols = st.columns(max(1, len(current)))
    for i, (acct, bal) in enumerate(current.items()):
        cols[i].metric(acct, f"${bal:,.2f}")

    st.divider()

    # Controls
    col1, col2, col3 = st.columns([1, 1, 2])
    preset = col1.selectbox("Range", list(RANGE_PRESETS.keys()), index=0)
    granularity = col2.selectbox("Granularity", ["Daily", "Weekly", "Monthly"], index=0)

    min_date = df["Date"].min().normalize()
    max_date = df["Date"].max().normalize()

    if RANGE_PRESETS[preset] == "ALL":
        start, end = min_date, max_date
    elif RANGE_PRESETS[preset] == "YTD":
        start = pd.Timestamp(year=max_date.year, month=1, day=1)
        end = max_date
    elif RANGE_PRESETS[preset] == "CUSTOM":
        start, end = col3.date_input("Custom dates", value=(min_date.date(), max_date.date()))
        start, end = pd.Timestamp(start), pd.Timestamp(end)
    else:
        days = int(RANGE_PRESETS[preset])
        end = max_date
        start = (end - pd.Timedelta(days=days - 1)).normalize()
        if start < min_date:
            start = min_date

    freq = FREQ_MAP[granularity]

    series = _balance_timeseries(df, start=start, end=end, freq=freq)

    fig = px.line(series, x="Date", y="Balance", color="Account", markers=True)
    fig.update_yaxes(title="")
    fig.update_xaxes(title="")
    fig.update_layout(hovermode="x unified")

    st.plotly_chart(fig, use_container_width=True)
