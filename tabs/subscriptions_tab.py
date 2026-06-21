import io
import pandas as pd
import streamlit as st

NON_EXPENSE_CATS = {"Income", "Transfer In", "Transfer Out", "Savings"}
MIN_MONTHS_FOR_SUBSCRIPTION = 3


def _detect_subscriptions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Find memos that appear in 3+ distinct months at a consistent amount (CV < 0.15).
    Returns a summary DataFrame sorted by frequency descending.
    """
    df = df.copy()
    df["Memo_norm"] = df["Memo"].str.strip().str.lower()
    df["Month"] = df["Date"].dt.to_period("M")

    groups = df.groupby("Memo_norm")
    records = []
    for memo_norm, grp in groups:
        months = grp["Month"].nunique()
        if months < MIN_MONTHS_FOR_SUBSCRIPTION:
            continue
        amounts = grp["Price"]
        cv = amounts.std() / amounts.mean() if amounts.mean() > 0 else 1.0
        if cv > 0.25:
            continue
        records.append({
            "Memo": grp["Memo"].iloc[0],
            "Category": grp["Category"].mode().iloc[0],
            "Months Seen": months,
            "Avg Amount": round(float(amounts.mean()), 2),
            "Last Seen": grp["Date"].max().strftime("%m/%d/%Y"),
            "Est. Annual Cost": round(float(amounts.mean()) * 12, 2),
        })

    return pd.DataFrame(records).sort_values("Months Seen", ascending=False) \
        if records else pd.DataFrame(
        columns=["Memo", "Category", "Months Seen", "Avg Amount", "Last Seen", "Est. Annual Cost"]
    )


def _flag_anomalies(df: pd.DataFrame, z_threshold: float = 2.0) -> pd.DataFrame:
    """
    Flag transactions where amount > mean + z_threshold * std within their category.
    Only applied to expense categories with >= 5 transactions.
    """
    flagged = []
    for cat, grp in df.groupby("Category"):
        if len(grp) < 5:
            continue
        mean = grp["Price"].mean()
        std = grp["Price"].std()
        if std == 0:
            continue
        outliers = grp[grp["Price"] > mean + z_threshold * std].copy()
        outliers["Category Mean"] = round(mean, 2)
        outliers["Z-Score"] = ((outliers["Price"] - mean) / std).round(2)
        flagged.append(outliers)

    if not flagged:
        return pd.DataFrame()

    out = pd.concat(flagged).sort_values("Z-Score", ascending=False)
    return out[["Date", "Memo", "Category", "Price", "Category Mean", "Z-Score"]].copy()


def subscriptions_tab(df: pd.DataFrame) -> None:
    df = df.copy()
    expense_df = df[~df["Category"].isin(NON_EXPENSE_CATS)].copy()

    tab_subs, tab_anomaly, tab_export = st.tabs(
        ["🔁 Subscriptions", "⚠️ Anomalies", "📥 Export"]
    )

    # ── Subscription detection ─────────────────────────────────────────────
    with tab_subs:
        st.caption(
            f"Memos appearing in {MIN_MONTHS_FOR_SUBSCRIPTION}+ distinct months "
            "with consistent amounts (coefficient of variation < 0.25)."
        )
        subs = _detect_subscriptions(expense_df)
        if subs.empty:
            st.info("No recurring subscriptions detected in the current data window.")
        else:
            total_annual = subs["Est. Annual Cost"].sum()
            st.metric("Estimated Annual Subscription Cost", f"${total_annual:,.2f}")
            st.dataframe(
                subs.style.format({
                    "Avg Amount": "${:,.2f}",
                    "Est. Annual Cost": "${:,.2f}",
                }),
                hide_index=True, use_container_width=True,
            )

    # ── Anomaly flagging ───────────────────────────────────────────────────
    with tab_anomaly:
        z_thresh = st.slider("Z-score threshold", min_value=1.0, max_value=4.0,
                             value=2.0, step=0.5, key="anomaly_z")
        st.caption(
            f"Transactions more than **{z_thresh}σ** above their category mean "
            "(categories with < 5 transactions are excluded)."
        )
        anomalies = _flag_anomalies(expense_df, z_threshold=z_thresh)
        if anomalies.empty:
            st.info("No anomalies found at the current threshold.")
        else:
            st.metric("Flagged Transactions", len(anomalies))
            display = anomalies.copy()
            display["Date"] = display["Date"].dt.strftime("%m/%d/%Y")
            st.dataframe(
                display.style.format({
                    "Price": "${:,.2f}",
                    "Category Mean": "${:,.2f}",
                }),
                hide_index=True, use_container_width=True,
            )

    # ── Report export ──────────────────────────────────────────────────────
    with tab_export:
        st.subheader("Export Filtered Data")
        export_format = st.radio("Format", ["CSV", "Excel"], horizontal=True)

        display_export = df.copy()
        display_export["Date"] = display_export["Date"].dt.strftime("%m/%d/%Y")

        if export_format == "CSV":
            csv = display_export.to_csv(index=False).encode()
            st.download_button(
                "⬇️ Download CSV",
                data=csv,
                file_name="ledger_export.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                display_export.to_excel(writer, index=False, sheet_name="Transactions")
                # Summary sheet
                summary = df.groupby("Category")["Price"].agg(["sum", "count"]) \
                    .rename(columns={"sum": "Total", "count": "Count"}) \
                    .reset_index()
                summary.to_excel(writer, index=False, sheet_name="Summary")
            st.download_button(
                "⬇️ Download Excel",
                data=buf.getvalue(),
                file_name="ledger_export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
