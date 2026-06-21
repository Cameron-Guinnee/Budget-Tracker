import streamlit as st

st.set_page_config(
    page_title="Ledgerline",
    page_icon="📈",
    layout="wide",
)

pg = st.navigation({
    "Ledger": [st.Page("pages/ledger.py", title="Ledger", icon="📒")],
    "Portfolio": [st.Page("pages/portfolio.py", title="Portfolio", icon="💼")],
    "Overview": [st.Page("pages/net_worth.py", title="Net Worth", icon="📊")],
})
pg.run()
