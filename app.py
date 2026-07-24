import streamlit as st
import pandas as pd
import plotly.express as px
from gap_checker import check_bearish_gap, get_market_status, get_snapshot_info
from datetime import datetime

# Pagina configuratie
st.set_page_config(
    page_title="AEX Bearish Gap Scanner",
    page_icon="🐻",
    layout="wide"
)

# Header
st.markdown('<p style="font-size:2.5rem;font-weight:bold;color:#FF4B4B;">🐻 Bearish Gap Scanner</p>', unsafe_allow_html=True)

# Status en data ophalen
status = get_market_status()
df, snapshot_time = check_bearish_gap()

col1, col2 = st.columns(2)
col1.metric("Status", status)
col2.metric("Data", f"📸 {snapshot_time}")

st.divider()

# Refresh knop
if st.button("🔄 Ververs data", type="primary", key="refresh"):
    st.rerun()

# Resultaten
if not df.empty:
    total = len(df)
    avg_gap = df['Gap %'].mean()
    avg_candle = df['Candle %'].mean()

    m1, m2, m3 = st.columns(3)
    m1.metric("Aantal signalen", total)
    m2.metric("Gem. gap down", f"{avg_gap:.2f}%")
    m3.metric("Gem. bearish candle", f"{avg_candle:.2f}%")

    st.divider()
    st.subheader("📊 Gap Down Percentages")

    fig = px.bar(df, x='Ticker', y='Gap %', color='Gap %',
                 color_continuous_scale='Reds', text='Gap %')
    fig.update_traces(texttemplate='%{text:.2f}%', textposition='outside',
                      marker_line_color='darkred', marker_line_width=1)
    fig.update_layout(showlegend=False, height=500,
                      xaxis_title="", yaxis_title="Gap Percentage",
                      plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                      font=dict(color='white'))
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("📋 Bearish Gap + Bearish Candle")

    styled_df = df.style.background_gradient(subset=['Gap %', 'Candle %'], cmap='Reds').format({
        'Dag N Low': '{:.2f}',
        'N+1 Open': '{:.2f}',
        'N+1 Close': '{:.2f}',
        'Gap %': '{:.2f}%',
        'Candle %': '{:.2f}%'
    })
    st.dataframe(styled_df, use_container_width=True, height=400)

    csv = df.to_csv(index=False)
    st.download_button("📥 Download als CSV", data=csv,
                       file_name=f"bearish_gaps_{datetime.now().strftime('%Y%m%d')}.csv",
                       mime="text/csv")

else:
    st.success("✅ Geen bearish gap signalen gevonden vandaag!")
    st.markdown("""
    ### 📖 Bearish Gap + Bearish Candle
    Dit patroon toont aandelen die aan twee voorwaarden voldoen:
    - **N+1 Open < N Low** → gap down (lager geopend dan de laagste koers van de dag ervoor)
    - **N+1 Close < N+1 Open** → bearish candle (lager gesloten dan geopend)
    
    Dit is een sterk bearish signaal op de daily timeframe.
    """)

st.divider()
st.caption("📊 Data via Yahoo Finance (15 min vertraagd) • AEX fondsen")