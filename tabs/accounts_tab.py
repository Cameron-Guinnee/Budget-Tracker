import pandas as pd
import plotly.express as px
import streamlit as st
from utils import get_account_apy_config

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

    # ── APY tracking ──────────────────────────────────────────────────────
    apy_config = get_account_apy_config()
    if not apy_config:
        return

    st.divider()
    st.subheader("Savings Interest Tracking")
    st.caption(
        "Projected vs. logged interest for accounts with an APY configured in secrets.toml. "
        "Uses end-of-month balance × (APY / 12) as the monthly expected interest."
    )

    # Get unfiltered data for accurate carry-in across all time
    df_all = _ensure_account_and_signed_amount(df)
    df_all = df_all.sort_values("Date")

    # Find "Interest" transactions in the selected date range
    interest_cats = {"Interest", "Savings Interest", "Interest Income"}
    interest_txns = df_all[df_all["Category"].isin(interest_cats)].copy()

    rows = []
    for acct, apy in apy_config.items():
        monthly_rate = apy / 100 / 12
        acct_df = df_all[df_all["Account"] == acct]
        if acct_df.empty:
            continue

        acct_start = acct_df["Date"].min()
        acct_end = pd.Timestamp.today().normalize()
        month_ends = pd.date_range(start=acct_start, end=acct_end, freq="ME")

        for month_end in month_ends:
            month_start = month_end.replace(day=1)
            balance = float(acct_df[acct_df["Date"] <= month_end]["Signed Amount"].sum())
            projected = balance * monthly_rate if balance > 0 else 0.0

            actual = float(
                interest_txns[
                    (interest_txns["Account"] == acct) &
                    (interest_txns["Date"] >= month_start) &
                    (interest_txns["Date"] <= month_end)
                ]["Price"].sum()
            )
            rows.append({
                "Account": acct,
                "Month": month_end.strftime("%Y-%m"),
                "End Balance": balance,
                "APY %": apy,
                "Projected Interest": round(projected, 2),
                "Logged Interest": round(actual, 2),
                "Difference": round(actual - projected, 2),
            })

    if not rows:
        st.info("No data found for configured APY accounts.")
        return

    apy_df = pd.DataFrame(rows)
    for acct in apy_df["Account"].unique():
        acct_apy = apy_df[apy_df["Account"] == acct]
        total_proj = acct_apy["Projected Interest"].sum()
        total_logged = acct_apy["Logged Interest"].sum()
        a1, a2, a3 = st.columns(3)
        a1.metric(f"{acct} — APY configured", f"{apy_config[acct]:.2f}%")
        a2.metric("Total Projected", f"${total_proj:,.2f}")
        a3.metric("Total Logged", f"${total_logged:,.2f}",
                  delta=f"${total_logged - total_proj:+,.2f}")

        with st.expander(f"{acct} month-by-month"):
            st.dataframe(
                acct_apy.style.format({
                    "End Balance": "${:,.2f}",
                    "Projected Interest": "${:,.2f}",
                    "Logged Interest": "${:,.2f}",
                    "Difference": "${:,.2f}",
                }),
                hide_index=True, use_container_width=True,
            )
