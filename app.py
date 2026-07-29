import streamlit as st
import pandas as pd
from gap_checker import check_bearish_gaps, get_market_status
from datetime import datetime

st.set_page_config(page_title="AEX+US Bearish Gap Scanner", page_icon="🐻", layout="wide")
st.markdown('<p style="font-size:2.5rem;font-weight:bold;color:#FF4B4B;">🐻 Bearish Gap Scanner</p>', unsafe_allow_html=True)

status = get_market_status()
df = check_bearish_gaps()

col1, col2, col3 = st.columns(3)
col1.metric("AEX", status["AEX"])
col2.metric("US Beurzen", status["US"])
col3.metric("Signalen", f"{len(df)} vandaag")

st.divider()

if st.button("🔄 Ververs data", type="primary"):
    st.rerun()

if not df.empty:
    latest_date = df['Datum'].max()
    st.subheader(f"📅 Bearish gaps van {latest_date}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Aantal", len(df))
    c2.metric("Gem. gap %", f"{df['Gap %'].mean():.2f}%")
    c3.metric("Gem. candle %", f"{df['Candle %'].mean():.2f}%")

    st.divider()
    st.subheader("📋 Alle Bearish Gaps")
    styled_df = df.style.background_gradient(subset=['Gap %', 'Candle %'], cmap='Reds').format({
        'Dag N Low': '{:.2f}',
        'N+1 Open': '{:.2f}',
        'N+1 Close': '{:.2f}',
        'Gap %': '{:.2f}%',
        'Candle %': '{:.2f}%'
    })
    st.dataframe(styled_df, use_container_width=True, height=500)

    csv = df.to_csv(index=False)
    st.download_button("📥 Download als CSV", data=csv,
                       file_name=f"bearish_gaps_{datetime.now().strftime('%Y%m%d')}.csv",
                       mime="text/csv")
else:
    st.success("✅ Geen bearish gap signalen vandaag.")
    st.markdown("""
    ### 📖 Bearish Gap + Bearish Candle
    - **Gisteren (N+1) open < Low van eergisteren (N)** (gap down)
    - **Gisteren (N+1) close < open** (bearish candle)
    """)

st.divider()
st.caption("📊 Data via Yahoo Finance (15 min vertraagd) • AEX + 100 grootste US bedrijven")