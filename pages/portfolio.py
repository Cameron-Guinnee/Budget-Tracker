import streamlit as st
import portfolio_tabs
from portfolio_utils import load_portfolio_df, prep_portfolio_df, get_portfolio_sheet_url

PORTFOLIO_TTL = 5 * 60


@st.cache_data(ttl=PORTFOLIO_TTL)
def load_portfolio():
    return load_portfolio_df()


# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    url = get_portfolio_sheet_url()
    if url:
        st.link_button("📝 Portfolio Sheet", url, help="Open in Google Sheets", use_container_width=True)

    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── Load & prep data ───────────────────────────────────────────────────────
raw_df = load_portfolio()

if raw_df is None:
    st.error(
        "Portfolio sheet not configured. "
        "Add `[connections.portfolio_gsheets]` to `.streamlit/secrets.toml`."
    )
    with st.expander("Configuration example"):
        st.code(
            """
[connections.portfolio_gsheets]
type = "service_account"
spreadsheet = "https://docs.google.com/spreadsheets/d/<YOUR_SHEET_ID>/edit"
worksheet = 0
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN RSA PRIVATE KEY-----\\n...\\n-----END RSA PRIVATE KEY-----\\n"
client_email = "...@....iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
""",
            language="toml",
        )
    st.stop()

df = prep_portfolio_df(raw_df) if not raw_df.empty else raw_df

# ── Tabs ───────────────────────────────────────────────────────────────────
holdings_tab, performance_tab, allocation_tab, add_tab = st.tabs([
    "💼 Holdings", "📈 Performance", "🥧 Allocation", "➕ Add Transaction",
])

with holdings_tab:
    portfolio_tabs.render_holdings_tab(df.copy())

with performance_tab:
    portfolio_tabs.render_performance_tab(df.copy())

with allocation_tab:
    portfolio_tabs.render_allocation_tab(df.copy())

with add_tab:
    portfolio_tabs.render_add_transaction_tab()
