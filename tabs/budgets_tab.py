import pandas as pd
import streamlit as st
from utils import get_budget_config

NON_BUDGET_CATS = {"Income", "Transfer In", "Transfer Out", "Savings"}


def budgets_tab(df: pd.DataFrame) -> None:
    budgets = get_budget_config()

    if not budgets:
        st.info(
            "No budgets configured. Add monthly budget amounts to `.streamlit/secrets.toml`:\n\n"
            "```toml\n[expense_tracker.budgets]\nGrocery = 500\nDining = 200\nEntertainment = 100\n```"
        )
        return

    df = df.copy()
    df = df[~df["Category"].isin(NON_BUDGET_CATS)]

    # Determine how many months are represented in filtered_df
    periods = df["Date"].dt.to_period("M").unique()
    n_months = max(len(periods), 1)

    # Actual spend per category (total across the filtered period)
    actual = df.groupby("Category")["Price"].sum()

    st.caption(
        f"Showing spend vs. budget across {n_months} month(s) in the current filter. "
        "Monthly budget × number of months = period budget."
    )
    st.divider()

    over_budget = []
    on_track = []

    for cat, monthly_limit in sorted(budgets.items()):
        period_limit = monthly_limit * n_months
        spent = float(actual.get(cat, 0.0))
        pct = spent / period_limit if period_limit > 0 else 0.0
        over = spent > period_limit
        (over_budget if over else on_track).append((cat, spent, period_limit, pct, over))

    def _render_row(cat, spent, limit, pct, over):
        col_label, col_bar, col_nums = st.columns([2, 4, 2])
        indicator = "🔴" if over else ("🟡" if pct > 0.8 else "🟢")
        col_label.write(f"{indicator} **{cat}**")
        col_label.caption(f"{pct * 100:.0f}% used")
        col_bar.progress(min(pct, 1.0))
        col_nums.write(f"${spent:,.0f} / ${limit:,.0f}")
        if over:
            col_nums.caption(f":red[+${spent - limit:,.0f} over]")

    if over_budget:
        st.subheader("🔴 Over Budget")
        for args in over_budget:
            _render_row(*args)
        st.divider()

    if on_track:
        st.subheader("✅ On Track")
        for args in on_track:
            _render_row(*args)

    # Categories with spend but no budget
    untracked = [c for c in actual.index if c not in budgets and c not in NON_BUDGET_CATS]
    if untracked:
        st.divider()
        st.subheader("📋 Unbudgeted Spending")
        rows = [{"Category": c, "Spent": f"${actual[c]:,.2f}"} for c in sorted(untracked)]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
