import streamlit as st
import pandas as pd
from gap_checker import scan_all_patterns, get_market_status
from datetime import datetime

st.set_page_config(page_title="AEX+US Bearish Gap Scanner", page_icon="🐻", layout="wide")
st.markdown('<p style="font-size:2.5rem;font-weight:bold;color:#FF4B4B;">🐻 Bearish Gap Scanner</p>', unsafe_allow_html=True)

status = get_market_status()
df = scan_all_patterns()

col1, col2, col3 = st.columns(3)
col1.metric("AEX", status["AEX"])
col2.metric("US Beurzen", status["US"])
col3.metric("Signalen", f"{len(df)} vandaag")

st.divider()

if st.button("🔄 Ververs data", type="primary"):
    st.rerun()

if not df.empty:
    st.subheader("📋 Signalen")

    # Maak een styled DataFrame met vetgedrukte rijen voor 'Dubbele Gap Down'
    def highlight_dubbele_gap(row):
        if row['Signaaltype'] == 'Dubbele Gap Down':
            return ['font-weight: bold; background-color: #2d1f1f'] * len(row)
        else:
            return [''] * len(row)

    styled = df.style.apply(highlight_dubbele_gap, axis=1).format({
        'Dag N Low': '{:.2f}',
        'N+1 Open': '{:.2f}',
        'N+1 Close': '{:.2f}',
        'Gap %': '{:.2f}%',
        'Candle %': '{:.2f}%'
    })

    # Render HTML-tabel met vetgedrukte regels
    html_table = styled.to_html(escape=False)
    st.markdown(html_table, unsafe_allow_html=True)

    # Downloadknop (zonder styling maar wel met signaaltype)
    csv = df.to_csv(index=False)
    st.download_button("📥 Download als CSV", data=csv,
                       file_name=f"bearish_signals_{datetime.now().strftime('%Y%m%d')}.csv",
                       mime="text/csv")

    st.caption("💡 **Dubbele Gap Down**-signalen zijn **vet** weergegeven.")
else:
    st.success("✅ Geen signalen vandaag.")
    st.markdown("""
    ### 📖 Uitleg signalen
    - **Bearish Gap**: N+1 open < low van N, én N+1 sluit lager dan opening (bearish candle).
    - **Dubbele Gap Down**: N+1 high < low van N, én N+2 open < low van N (extra bevestiging).
    """)

st.divider()
st.caption("📊 Data via Yahoo Finance (15 min vertraagd) • AEX + 100 grootste US bedrijven")