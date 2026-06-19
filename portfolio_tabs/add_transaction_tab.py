import datetime
import streamlit as st
from portfolio_utils import (
    ASSET_TYPES, TRANSACTION_TYPES, get_portfolio_worksheet,
    append_portfolio_transaction,
)


def add_transaction_tab() -> None:
    ws = get_portfolio_worksheet()
    if ws is None:
        st.error(
            "Portfolio sheet not configured. Add `[connections.portfolio_gsheets]` "
            "to your `.streamlit/secrets.toml` file."
        )
        with st.expander("Configuration example"):
            st.code(
                """
[connections.portfolio_gsheets]
type = "service_account"
spreadsheet = "https://docs.google.com/spreadsheets/d/<YOUR_SHEET_ID>/edit"
worksheet = 0
# ... service account credential fields ...
""",
                language="toml",
            )
        return

    with st.form("add_portfolio_transaction", clear_on_submit=False, border=False):
        col1, col2 = st.columns(2)

        with col1:
            date = st.date_input("Date", value="today", format="MM/DD/YYYY")
            symbol = st.text_input("Symbol", placeholder="e.g. AAPL, BTC-USD").strip().upper()
            asset_type = st.selectbox("Asset Type", ASSET_TYPES)
            transaction_type = st.selectbox("Transaction Type", TRANSACTION_TYPES)

        with col2:
            shares = st.number_input(
                "Shares / Units",
                min_value=0.0, value=0.0, step=0.000001, format="%.6f",
                help="Leave 0 for Dividend transactions.",
            )
            price_per_share = st.number_input(
                "Price Per Share / Unit ($)",
                min_value=0.0, value=0.0, step=0.01, format="%.4f",
                help="For Dividends, enter 0 and put the total amount in the Total field.",
            )
            total_override = st.number_input(
                "Total ($)",
                min_value=0.0,
                value=round(shares * price_per_share, 2),
                step=0.01,
                format="%.2f",
                help="Auto-calculated from Shares × Price. Override for Dividends.",
            )
            notes = st.text_input("Notes", placeholder="Optional")

        submit_col, clear_col = st.columns(2)

        with submit_col:
            submitted = st.form_submit_button("Submit", type="primary", use_container_width=True)
        with clear_col:
            cleared = st.form_submit_button("Clear", type="secondary", use_container_width=True)

    if submitted:
        errors = []
        if not symbol:
            errors.append("Symbol is required.")
        if transaction_type != "Dividend" and shares <= 0:
            errors.append("Shares must be greater than 0 for Buy/Sell transactions.")
        if total_override <= 0:
            errors.append("Total must be greater than 0.")

        if errors:
            for e in errors:
                st.toast(f":red[{e}]", icon="❌")
        else:
            computed_total = total_override if total_override > 0 else shares * price_per_share
            row = [
                date.strftime("%m/%d/%Y"),
                symbol,
                asset_type,
                transaction_type,
                shares,
                price_per_share,
                round(computed_total, 2),
                notes,
            ]
            if append_portfolio_transaction(row):
                st.toast(":green[Transaction added!]", icon="🎉")
                st.cache_data.clear()
            else:
                st.toast(":red[Something went wrong. Check your sheet permissions.]", icon="❌")

    if cleared:
        st.rerun()
