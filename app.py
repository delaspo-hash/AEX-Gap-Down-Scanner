import streamlit as st
import pandas as pd
import plotly.express as px
from gap_checker import check_gap_down, get_market_status, get_snapshot_info
from datetime import datetime, timezone, timedelta

# Pagina configuratie
st.set_page_config(
    page_title="AEX Gap Scanner",
    page_icon="📉",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #FF4B4B;
    }
    .gap-card {
        background-color: #1E1E1E;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #FF4B4B;
        margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# Header
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    st.markdown('<p class="main-header">📉 AEX Gap Down Scanner</p>', unsafe_allow_html=True)
with col2:
    st.metric("Status", get_market_status())
with col3:
	st.metric("Data", f"📸 Snapshot van {snapshot_time}")

st.divider()

# Refresh knop
if st.button("🔄 Ververs data", type="primary"):
    st.rerun()

# Data ophalen
with st.spinner("📊 AEX data ophalen..."):
	df, snapshot_time = check_gap_down()

# Resultaten tonen
if not df.empty:
    # Metrics bovenaan
    total_gaps = len(df)
    avg_gap = df['Gap %'].mean()
    max_gap = df['Gap %'].max()
    max_ticker = df.loc[df['Gap %'].idxmax(), 'Ticker']
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Aantal gap downs", total_gaps)
    m2.metric("Gemiddelde gap", f"{avg_gap:.2f}%")
    m3.metric("Grootste gap", f"{max_ticker}: {max_gap:.2f}%", delta=f"-{max_gap:.2f}%")
    
    st.divider()
    
    # Staafdiagram
    st.subheader("📊 Gap Down Percentages")
    
    fig = px.bar(
        df,
        x='Ticker',
        y='Gap %',
        color='Gap %',
        color_continuous_scale='Reds',
        text='Gap %'
    )
    fig.update_traces(
        texttemplate='%{text:.2f}%',
        textposition='outside',
        marker_line_color='darkred',
        marker_line_width=1
    )
    fig.update_layout(
        showlegend=False,
        height=500,
        xaxis_title="",
        yaxis_title="Gap Percentage",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white')
    )
    st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # Detailtabel
    st.subheader("📋 Alle Gap Downs")
    
    styled_df = df.style.background_gradient(
        subset=['Gap %'],
        cmap='Reds'
    ).format({
        'Slot gisteren': '{:.2f}',
        'Low gisteren': '{:.2f}',
        'Open vandaag': '{:.2f}',
        'Gap %': '{:.2f}%'
    })
    
    st.dataframe(styled_df, use_container_width=True, height=400)
    
    # Download knop
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Download als CSV",
        data=csv,
        file_name=f"aex_gap_downs_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )
    
else:
    st.success("✅ Geen AEX gap downs gevonden vandaag!")
    
    st.markdown("""
    ### 📖 Wat is een gap down?
    Een gap down ontstaat wanneer de openingskoers **lager** is dan de **laagste koers** van de vorige dag.
    Dit duidt vaak op negatief nieuws of sentiment rond het aandeel.
    
    *Data wordt elke 15 minuten automatisch ververst door Yahoo Finance.*
    """)

# Footer
st.divider()
st.caption(f"📊 Data via Yahoo Finance (15 min vertraagd) • AEX fondsen • {get_snapshot_info()}")