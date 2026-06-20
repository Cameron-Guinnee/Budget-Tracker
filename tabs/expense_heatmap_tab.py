import pandas as pd
import plotly.express as px
import streamlit as st

# Treat these as NOT expenses for the heatmap
NON_EXPENSE_CATS = {"Income", "Transfer In", "Transfer Out"}

def expense_heatmap_tab(df: pd.DataFrame):
    df = df.copy()
    df["Period"] = df["Date"].dt.to_period("M")

    m_grouped_data = (
        df.groupby(["Category", "Period"], as_index=False)
          .sum(numeric_only=True)
    )

    # Exclude non-expense categories
    m_grouped_data = m_grouped_data.loc[~m_grouped_data["Category"].isin(NON_EXPENSE_CATS), :]

    if m_grouped_data.empty:
        st.info("No expense data available for this selection.")
        return

    m_grouped_data["Period"] = m_grouped_data["Period"].astype(str)

    categories = sorted(m_grouped_data["Category"].astype(str).str.strip().unique())
    periods = sorted(m_grouped_data["Period"].unique())

    category_index = {c: i for i, c in enumerate(categories)}
    period_index = {p: i for i, p in enumerate(periods)}

    data = [[0 for _ in categories] for _ in periods]

    for _, row in m_grouped_data.iterrows():
        r = period_index[str(row["Period"])]
        c = category_index[str(row["Category"]).strip()]
        data[r][c] = float(row["Price"])

    heatmap = px.imshow(
        data,
        x=categories,
        y=periods,
        labels=dict(color="Total Expenses"),
        text_auto=".2s",
    )
    heatmap.update_yaxes(tickmode="linear")
    heatmap.update_traces(
        hovertemplate="Category: %{x}<br>Month: %{y}<br>Total: %{z:$,.2f}<extra></extra>"
    )
    st.plotly_chart(heatmap, use_container_width=True)
