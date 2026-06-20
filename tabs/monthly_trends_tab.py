import pandas as pd
import plotly.express as px
import streamlit as st
from styling import category_color_map
from utils import month_labels

def monthly_trends_tab(df: pd.DataFrame):
    df = df.copy()
    df['Period'] = df['Date'].dt.to_period('M')
    df = df.sort_values(by='Period')
    m_grouped_data = df.groupby(
        ['Category', 'Period'], as_index=False
    ).sum(numeric_only=True)
    m_grouped_data['Period'] = m_grouped_data['Period'].astype(str)

    expenses = m_grouped_data.loc[(m_grouped_data['Category'] != 'Income'), :]
    expenses = expenses.groupby(['Period'], as_index=False).sum(numeric_only=True)

    line_chart = px.line(
        m_grouped_data[m_grouped_data['Category'] == 'Income'],
        x='Period', y='Price', color='Category',
        color_discrete_map=category_color_map, markers=True,
    )
    line_chart.add_bar(
        x=expenses['Period'], y=expenses['Price'],
        marker={'color': '#fc0000'}, name='Expenses',
        hovertemplate="%{y:$,.2f}",
        textfont_size=12, textangle=0, textposition="outside",
    )
    line_chart.update_yaxes(title='')
    line_chart.update_xaxes(title='')
    line_chart.update_layout(hovermode='x unified')
    line_chart.update_traces(hovertemplate="%{y:$,.2f}")
    st.plotly_chart(line_chart, use_container_width=True)
