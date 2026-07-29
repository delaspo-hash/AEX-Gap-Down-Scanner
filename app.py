import streamlit as st
import pandas as pd
import plotly.express as px
from gap_checker import check_bearish_gap, get_market_status, get_snapshot_info, backfill_history
from datetime import datetime

st.set_page_config(page_title="AEX+US Bearish Gap Scanner", page_icon="🐻", layout="wide")
st.markdown('<p style="font-size:2.5rem;font-weight:bold;color:#FF4B4B;">🐻 Bearish Gap Scanner</p>', unsafe_allow_html=True)

status = get_market_status()
df, snapshot_time = check_bearish_gap()

col1, col2, col3 = st.columns(3)
col1.metric("Status", status)
col2.metric("Scan tijd", f"📸 {snapshot_time}")
col3.metric("Historie", f"{len(df)} signalen")

st.divider()

# Knoppen naast elkaar
c1, c2 = st.columns(2)
with c1:
    if st.button("🔄 Ververs data", type="primary", key="refresh"):
        st.rerun()
with c2:
    # Alleen tonen als backfill nog niet gedaan is
    if not st.session_state.get('backfill_done', False):
        if st.button("📥 Backfill vanaf 20 juli"):
            with st.spinner("Historische data ophalen... Dit kan enkele minuten duren."):
                backfill_history("2026-07-20")
                st.session_state['backfill_done'] = True
            st.rerun()

if not df.empty:
    latest_date = df['Datum'].max()
    today_df = df[df['Datum'] == latest_date]
    if not today_df.empty:
        st.subheader(f"📅 Signalen van {latest_date}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Aantal vandaag", len(today_df))
        c2.metric("Gem. gap %", f"{today_df['Gap %'].mean():.2f}%")
        c3.metric("Gem. candle %", f"{today_df['Candle %'].mean():.2f}%")
    else:
        st.info("Geen signalen voor de meest recente datum.")

    st.divider()
    st.subheader("📈 Gap % per aandeel (alle historie)")
    fig = px.bar(df, x='Ticker', y='Gap %', color='Datum',
                 text='Gap %', barmode='group',
                 color_discrete_sequence=px.colors.sequential.Reds_r)
    fig.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
    fig.update_layout(height=500, xaxis_title="", yaxis_title="Gap Percentage",
                      plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                      font=dict(color='white'))
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("📋 Alle Bearish Gap Signalens")
    styled_df = df.style.background_gradient(subset=['Gap %', 'Candle %'], cmap='Reds').format({
        'Dag N Low': '{:.2f}',
        'N+1 Open': '{:.2f}',
        'N+1 Close': '{:.2f}',
        'Gap %': '{:.2f}%',
        'Candle %': '{:.2f}%'
    })
    st.dataframe(styled_df, use_container_width=True, height=500)

    csv = df.to_csv(index=False)
    st.download_button("📥 Download historie als CSV", data=csv,
                       file_name=f"bearish_gaps_history_{datetime.now().strftime('%Y%m%d')}.csv",
                       mime="text/csv")
else:
    st.success("✅ Nog geen bearish gap signalen gevonden.")
    st.markdown("""
    ### 📖 Bearish Gap + Bearish Candle
    - **Dag N+1 open < laagste koers Dag N** (gap down)
    - **Dag N+1 slot < opening Dag N+1** (bearish candle)
    """)

st.divider()
st.caption("📊 Data via Yahoo Finance (15 min vertraagd) • AEX, S&P 500, Nasdaq-100")