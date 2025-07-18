import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from styling import get_owner_color_map, category_color_map
from typing import Callable

def process_data(df: pd.DataFrame, get_savings_df: Callable[[int], pd.DataFrame], hide_savings: bool) -> pd.DataFrame:
    income: list[int] = df.loc[(df['Category'] == 'Income'), 'Price'].values
    if income:
        income_total = income[0]
        df = df.drop(df[(df['Category'] == 'Income')].index)
    else:
        income_total = 0
    if not hide_savings:
        expenses = df.loc[(df['Category'] != 'Income'), :]
        expenses_total = expenses.loc[:, 'Price'].sum(numeric_only=True)
        if not expenses_total:
            expenses_total = 0
        savings = income_total - expenses_total
        df = pd.concat([df, get_savings_df(savings)], axis=0)
    return df.copy()
