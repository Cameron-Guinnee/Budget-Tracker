import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import tabs
from utils import get_google_sheet_titles_and_url, get_worksheet, get_worksheet_dataframe

st.title("📒 Ledger")

conn: GSheetsConnection = st.connection("gsheets", type=GSheetsConnection)

DATA_TTL_SECONDS = 10 * 60

@st.cache_data(ttl=DATA_TTL_SECONDS)
def load_data() -> pd.DataFrame:
    df = get_worksheet_dataframe()
    if df is not None:
        return df
    conn: GSheetsConnection = st.connection("gsheets", type=GSheetsConnection)
    return conn.read(worksheet=get_worksheet(), ttl=DATA_TTL_SECONDS)

df: pd.DataFrame = load_data()

# Prep dataframe
df.columns = df.iloc[0]
df = df[1:]
df = df.dropna(subset=["Date", "Price", "Category"])
df['Memo'] = df['Memo'].str.strip()
df["Price"] = pd.to_numeric(df['Price'].map(lambda x: str(x).lstrip('$').replace(',', '')))
df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y")
df.sort_values(by="Date", ascending=False, inplace=True)

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    google_sheets_titles_and_url = get_google_sheet_titles_and_url()
    if google_sheets_titles_and_url:
        s_title, w_title, url = google_sheets_titles_and_url
        title = f"{s_title} ({w_title})" if w_title else s_title
        st.link_button(f"📝 {title}", url, help="Open in Google Sheets", use_container_width=True)

    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()

    year_options: list[str] = df["Date"].dt.strftime('%Y').drop_duplicates().tolist()
    year_options.sort(reverse=True)
    selected_year: str | None = st.selectbox("📆 Year", ["All"] + year_options, index=1)

    owner_options: list[str] = ["All"] + df["Owner"].drop_duplicates().tolist()
    selected_owner: str | None = st.selectbox("👤 Owner", owner_options, index=0)

    st.divider()
    with st.expander("🔬 Raw data"):
        st.write("dtypes:", df.dtypes.astype(str).to_dict())
        st.write("shape:", df.shape)
        raw_repr = df.head(5).map(lambda x: repr(x))
        st.dataframe(raw_repr.astype(str), hide_index=True)

NON_EXPENSE_CATS = {"Income", "Transfer In", "Transfer Out", "Savings"}

# ── Filtering ──────────────────────────────────────────────────────────────
filtered_df = df
if selected_year and selected_year != "All":
    filtered_df = df[df['Date'].dt.year == int(selected_year)]
if selected_owner != "All":
    filtered_df = filtered_df[filtered_df['Owner'] == selected_owner]

# ── KPI helpers ────────────────────────────────────────────────────────────
def _kpis(frame):
    g = frame.groupby("Category", as_index=False)["Price"].sum()
    inc = g.loc[g["Category"] == "Income", "Price"].sum()
    exp = g.loc[~g["Category"].isin(NON_EXPENSE_CATS), "Price"].sum()
    sav = inc - exp
    rate = (sav / inc * 100) if inc else 0.0
    return inc, exp, sav, rate

income_total, expenses_total, net_savings, savings_pct = _kpis(filtered_df)

# Year-over-year deltas (only when a specific year is selected)
prev_income = prev_expenses = prev_savings = prev_rate = None
if selected_year and selected_year != "All":
    prev_year = str(int(selected_year) - 1)
    if prev_year in year_options:
        prev_df = df[df['Date'].dt.year == int(prev_year)]
        if selected_owner != "All":
            prev_df = prev_df[prev_df['Owner'] == selected_owner]
        if not prev_df.empty:
            prev_income, prev_expenses, prev_savings, prev_rate = _kpis(prev_df)

def _delta(cur, prev):
    if prev is None:
        return None
    diff = cur - prev
    sign = "+" if diff >= 0 else ""
    return f"{sign}${diff:,.0f} vs {prev_year}"

def _delta_pct(cur, prev):
    if prev is None:
        return None
    diff = cur - prev
    sign = "+" if diff >= 0 else ""
    return f"{sign}{diff:.1f}pp vs {prev_year}"

# ── KPI row ────────────────────────────────────────────────────────────────
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("💰 Income", f"${income_total:,.0f}", delta=_delta(income_total, prev_income))
kpi2.metric("💸 Expenses", f"${expenses_total:,.0f}", delta=_delta(expenses_total, prev_expenses), delta_color="inverse")
kpi3.metric("🏦 Net Savings", f"${net_savings:,.0f}", delta=_delta(net_savings, prev_savings))
kpi4.metric("📊 Savings Rate", f"{savings_pct:.1f}%", delta=_delta_pct(savings_pct, prev_rate))

st.divider()

# ── Tabs ───────────────────────────────────────────────────────────────────
summary_tab, accounts_tab, breakdown_tab, monthly_trends_tab, expense_heatmap_tab, wordcloud_tab, budgets_tab, subscriptions_tab, df_tab, add_transaction_tab = st.tabs([
    "📋 Summary", "🏦 Accounts", "📊 Breakdown", "📈 Monthly Trends",
    "🗓️ Expense Heatmap", "☁️ Word Cloud", "🎯 Budgets", "🔍 Insights", 
    "🗃️ Data", "➕ Add Transaction"
])

with summary_tab:
    tabs.render_summary_tab(filtered_df.copy())

with accounts_tab:
    tabs.render_accounts_tab(filtered_df.copy())

with breakdown_tab:
    tabs.render_breakdown_tab(filtered_df.copy())

with monthly_trends_tab:
    tabs.render_monthly_trends_tab(filtered_df.copy())

with expense_heatmap_tab:
    tabs.render_expense_heatmap_tab(filtered_df.copy())

with wordcloud_tab:
    tabs.render_wordcloud_tab(filtered_df.copy())

with budgets_tab:
    tabs.render_budgets_tab(filtered_df.copy())

with add_transaction_tab:
    tabs.render_add_transaction_tab(filtered_df.copy())

with subscriptions_tab:
    tabs.render_subscriptions_tab(filtered_df.copy())

with df_tab:
    tabs.render_df_tab(filtered_df.copy())
