import pandas as pd
import plotly.express as px
import streamlit as st
from utils import month_labels

# Treat these as NOT expenses for the heatmap
NON_EXPENSE_CATS = {"Income", "Transfer In", "Transfer Out"}

def expense_heatmap_tab(df: pd.DataFrame):
    df = df.copy()
    df["Month"] = df["Date"].dt.month

    m_grouped_data = (
        df.groupby(["Category", "Month"], as_index=False)
          .sum(numeric_only=True)
    )

    # Exclude non-expense categories
    m_grouped_data = m_grouped_data.loc[~m_grouped_data["Category"].isin(NON_EXPENSE_CATS), :]

    if m_grouped_data.empty:
        st.info("No expense data available for this selection.")
        return
    categories = sorted(m_grouped_data["Category"].astype(str).str.strip().unique())
    months = sorted(m_grouped_data["Month"].unique())

    category_index = {c: i for i, c in enumerate(categories)}
    month_index = {m: i for i, m in enumerate(months)}

    data = [[0 for _ in categories] for _ in months]

    for _, row in m_grouped_data.iterrows():
        r = month_index[int(row["Month"])]
        c = category_index[str(row["Category"]).strip()]
        data[r][c] = float(row["Price"])

    heatmap = px.imshow(
        data,
        x=categories,
        y=months,
        labels=dict(color="Total Expenses"),
        text_auto=".2s_
