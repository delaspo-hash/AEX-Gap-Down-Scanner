import streamlit as st
import pandas as pd
from gap_checker import scan_all_patterns, get_market_status
from datetime import datetime

st.set_page_config(page_title="AEX+US Bearish Gap Scanner", page_icon="🐻", layout="wide")

# Lichte tabelstijl
st.markdown("""
<style>
    .gap-table {
        background-color: white;
        color: black;
        border-collapse: collapse;
        width: 100%;
        font-size: 14px;
    }
    .gap-table th {
        background-color: #f2f2f2;
        color: black;
        padding: 8px;
        text-align: left;
        border-bottom: 2px solid #ddd;
    }
    .gap-table td {
        padding: 8px;
        border-bottom: 1px solid #ddd;
        color: black;
    }
    .dubbele-gap {
        font-weight: bold;
        background-color: #ffe6e6;
    }
    .bearish-gap {
        background-color: white;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 style="color:#FF4B4B;">🐻 Bearish Gap Scanner</h1>', unsafe_allow_html=True)

status = get_market_status()

# --- Initialiseer de set met verwijderde signalen ---
if 'deleted_set' not in st.session_state:
    st.session_state.deleted_set = set()

# --- Data ophalen en filteren ---
if 'df' not in st.session_state or st.button("🔄 Ververs data", type="primary"):
    full_df = scan_all_patterns()
    # Verwijder alle signalen die ooit zijn verwijderd
    if not full_df.empty:
        mask = full_df.apply(
            lambda row: f"{row['Ticker']}|{row['Datum']}|{row['Signaaltype']}" not in st.session_state.deleted_set,
            axis=1
        )
        st.session_state.df = full_df[mask].reset_index(drop=True)
    else:
        st.session_state.df = full_df
    st.session_state.confirm_delete = False
    st.rerun()

df = st.session_state.df

col1, col2, col3 = st.columns(3)
col1.metric("AEX", status["AEX"])
col2.metric("US Beurzen", status["US"])
col3.metric("Signalen", f"{len(df)} vandaag")

st.divider()

if not df.empty:
    st.subheader("📋 Signalen")

    # --- Multiselect met alleen de huidige signalen ---
    labels = [f"{row['Ticker']} | {row['Datum']} | {row['Signaaltype']}" for _, row in df.iterrows()]
    selected_labels = st.multiselect(
        "Selecteer signalen om te verwijderen:",
        options=labels,
        key="selected_signals"
    )

    # Verwijderknop
    if st.button("🗑️ Verwijder geselecteerde signalen", disabled=len(selected_labels) == 0):
        st.session_state.confirm_delete = True
        st.rerun()

    # Popup bevestiging
    if st.session_state.get('confirm_delete', False):
        with st.container():
            st.warning("⚠️ **Weet u zeker dat u de geselecteerde signalen wilt verwijderen?**")
            col_ja, col_nee = st.columns(2)
            with col_ja:
                if st.button("✅ Ja, verwijderen", key="ja"):
                    # Voeg toe aan de set van verwijderde signalen
                    st.session_state.deleted_set.update(selected_labels)
                    # Verwijder ze direct uit de DataFrame
                    mask = df.apply(
                        lambda row: f"{row['Ticker']} | {row['Datum']} | {row['Signaaltype']}" not in selected_labels,
                        axis=1
                    )
                    st.session_state.df = df[mask].reset_index(drop=True)
                    st.session_state.confirm_delete = False
                    st.rerun()
            with col_nee:
                if st.button("❌ Annuleren", key="nee"):
                    st.session_state.confirm_delete = False
                    st.rerun()

    # --- Tabel weergeven (HTML) ---
    html = '<table class="gap-table"><thead><tr>'
    for col in df.columns:
        html += f'<th>{col}</th>'
    html += '</tr></thead><tbody>'

    for _, row in df.iterrows():
        row_class = 'dubbele-gap' if row['Signaaltype'] == 'Dubbele Gap Down' else 'bearish-gap'
        html += f'<tr class="{row_class}">'
        for col in df.columns:
            val = row[col]
            if isinstance(val, float):
                if 'Gap %' in col or 'Candle %' in col:
                    val = f"{val:.2f}%"
                else:
                    val = f"{val:.2f}"
            html += f'<td>{val}</td>'
        html += '</tr>'
    html += '</tbody></table>'

    st.markdown(html, unsafe_allow_html=True)
    st.caption("💡 **Dubbele Gap Down**-signalen zijn **vet** met een lichtrode achtergrond.")

    csv = df.to_csv(index=False)
    st.download_button("📥 Download als CSV", data=csv,
                       file_name=f"bearish_signals_{datetime.now().strftime('%Y%m%d')}.csv",
                       mime="text/csv")
else:
    st.success("✅ Geen signalen vandaag.")
    st.markdown("""
    ### 📖 Uitleg signalen
    - **Bearish Gap**: N+1 open < low van N, én N+1 close < open N+1.
    - **Dubbele Gap Down**: N+1 high < low van N, én N+2 open < low van N.
    """)

st.divider()
st.caption("📊 Data via Yahoo Finance (15 min vertraagd) • AEX + 100 US-bedrijven")