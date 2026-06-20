import pandas as pd
import streamlit as st
from styling import category_color_map, payment_method_color_map, payment_method_label_prefix, get_owner_color_map

def df_tab(df: pd.DataFrame) -> None:
    df = df.reset_index(drop=True)
    df["Price"] = df["Price"].astype(float)

    with pd.option_context('mode.chained_assignment', None):
        df.loc[:, "Payment Method"] = df["Payment Method"].map(lambda x: f"{payment_method_label_prefix[x]} {x}")

    styled_df = df.style \
                .format({
                    "Date": "{:%m/%d/%Y}",
                    "Price": "${:,.2f}",
                }) \
                .map(lambda x: f"color: {category_color_map.get(str(x), '#ffffff')}", subset=["Category"]) \
                .map(lambda x: f"color: {payment_method_color_map.get(str(x).split()[-1], '#ffffff')}", subset=["Payment Method"])
    owner_color_map = get_owner_color_map()
    if owner_color_map:
        styled_df = styled_df.map(lambda x: f"color: {owner_color_map.get(str(x), 'black')}", subset=["Owner"])

    try:
        st.dataframe(styled_df, column_config={
            "Shared": st.column_config.CheckboxColumn(),
        }, hide_index=True, use_container_width=True)
    except TypeError as e:
        st.warning(f"Table view unavailable ({e}); showing static table instead.")
        st.markdown(
            f'<div style="max-height: 600px; overflow: auto;">{styled_df.to_html()}</div>',
            unsafe_allow_html=True,
        )
        with st.expander("🔍 Debug info (for fixing the table view)"):
            st.write("dtypes:", df.dtypes.astype(str).to_dict())
            st.write("index dtype:", str(df.index.dtype), "| index sample:", df.index[:5].tolist())
            for col in df.columns:
                st.write(f"`{col}` sample values:", df[col].head(3).tolist(), "| python types:", [type(v).__name__ for v in df[col].head(3)])
