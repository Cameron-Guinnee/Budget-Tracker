import streamlit as st

st.set_page_config(
    page_title="Ledgerline",
    page_icon="📈",
    layout="wide",
)

pg = st.navigation({
    "Ledger": [st.Page("pages/ledger.py", title="Ledger", icon="📒")],
    "Portfolio": [st.Page("pages/portfolio.py", title="Portfolio", icon="💼")],
})
pg.run()
