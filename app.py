import streamlit as st
import pandas as pd
import plotly.express as px
from gap_checker import check_gap_down, get_market_status, get_snapshot_info
from datetime import datetime

# Pagina configuratie
st.set_page_config(
    page_title="AEX Gap Scanner",
    page_icon="📉",
    layout="wide"
)

# Header
st.markdown('<p style="font-size:2.5rem;font-weight:bold;color:#FF4B4B;">📉 AEX Gap Down Scanner</p>', unsafe_allow_html=True)

# Status en data ophalen
status = get_market_status()
df, snapshot_time = check_gap_down()

col1, col2 = st.columns(2)
col1.metric("Status", status)
col2.metric("Data", f"📸 {snapshot_time}")

st.divider()

# Refresh knop
if st.button("🔄 Ververs data", type="primary", key="refresh"):
    st.rerun()

# Resultaten
if not df.empty:
    total_gaps = len(df)
    avg_gap = df['Gap %'].mean()
    max_gap = df['Gap %'].max()
    max_ticker = df.loc[df['Gap %'].idxmax(), 'Ticker']

    m1, m2, m3 = st.columns(3)
    m1.metric("Aantal gap downs", total_gaps)
    m2.metric("Gemiddelde gap", f"{avg_gap:.2f}%")
    m3.metric("Grootste gap", f"{max_ticker}: {max_gap:.2f}%")

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
    st.subheader("📋 Alle Gap Downs")

    styled_df = df.style.background_gradient(subset=['Gap %'], cmap='Reds').format({
        'Slot gisteren': '{:.2f}',
        'Low gisteren': '{:.2f}',
        'Open vandaag': '{:.2f}',
        'Gap %': '{:.2f}%'
    })
    st.dataframe(styled_df, use_container_width=True, height=400)

    csv = df.to_csv(index=False)
    st.download_button("📥 Download als CSV", data=csv,
                       file_name=f"aex_gaps_{datetime.now().strftime('%Y%m%d')}.csv",
                       mime="text/csv")

else:
    st.success("✅ Geen AEX gap downs gevonden vandaag!")
    st.markdown("""
    ### 📖 Wat is een gap down?
    Een gap down ontstaat wanneer de openingskoers **lager** is dan de **laagste koers** van de vorige dag.
    """)

st.divider()
st.caption("📊 Data via Yahoo Finance (15 min vertraagd) • AEX fondsen")