import streamlit as st
import pandas as pd
from gap_checker import scan_all_patterns, get_market_status
from datetime import datetime
import json
import requests
import base64

REPO = "delaspo-hash/AEX-Gap-Down-Scanner"
FILE_PATH = "verwijderd.json"
GITHUB_API = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
TOKEN = st.secrets["GITHUB_TOKEN"]
HEADERS = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}

st.set_page_config(page_title="AEX+US Bearish Gap Scanner", page_icon="🐻", layout="wide")

st.markdown("""
<style>
    .gap-table { background-color: white; color: black; border-collapse: collapse; width: 100%; font-size: 14px; }
    .gap-table th { background-color: #f2f2f2; color: black; padding: 8px; text-align: left; border-bottom: 2px solid #ddd; }
    .gap-table td { padding: 8px; border-bottom: 1px solid #ddd; color: black; }
    .dubbele-gap { font-weight: bold; background-color: #ffe6e6; }
    .bearish-gap { background-color: white; }
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 style="color:#FF4B4B;">🐻 Bearish Gap Scanner</h1>', unsafe_allow_html=True)

status = get_market_status()

def load_deleted_set():
    try:
        resp = requests.get(GITHUB_API, headers=HEADERS)
        if resp.status_code == 200:
            content = resp.json()["content"]
            decoded = base64.b64decode(content).decode("utf-8")
            return set(json.loads(decoded))
        else:
            return set()
    except:
        return set()

def save_deleted_set(deleted_set):
    sha = None
    try:
        resp = requests.get(GITHUB_API, headers=HEADERS)
        if resp.status_code == 200:
            sha = resp.json()["sha"]
    except:
        pass
    payload = {
        "message": "Update deleted signals",
        "content": base64.b64encode(json.dumps(list(deleted_set)).encode("utf-8")).decode("utf-8")
    }
    if sha:
        payload["sha"] = sha
    try:
        requests.put(GITHUB_API, headers=HEADERS, json=payload)
    except:
        st.error("Opslaan mislukt. Controleer je token.")

if 'deleted_set' not in st.session_state:
    with st.spinner("Laden van verwijderde signalen..."):
        st.session_state.deleted_set = load_deleted_set()

if 'df' not in st.session_state or st.button("🔄 Ververs data", type="primary"):
    full_df = scan_all_patterns()
    if not full_df.empty:
        mask = full_df.apply(lambda row: f"{row['Ticker']}|{row['Datum']}|{row['Signaaltype']}" not in st.session_state.deleted_set, axis=1)
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

if st.button("🗑️ Verwijderlijst legen (alle signalen terugzetten)"):
    st.session_state.deleted_set = set()
    save_deleted_set(set())
    full_df = scan_all_patterns()
    st.session_state.df = full_df
    st.success("Verwijderlijst gewist.")
    st.rerun()

if not df.empty:
    st.subheader("📋 Signalen")
    labels = [f"{row['Ticker']} | {row['Datum']} | {row['Signaaltype']}" for _, row in df.iterrows()]
    selected_labels = st.multiselect("Selecteer signalen om te verwijderen:", options=labels, key="selected")
    if st.button("🗑️ Verwijder geselecteerde signalen", disabled=len(selected_labels) == 0):
        st.session_state.confirm_delete = True
        st.rerun()
    if st.session_state.get('confirm_delete'):
        with st.container():
            st.warning("⚠️ Weet u het zeker?")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Ja, verwijderen"):
                    st.session_state.deleted_set.update(selected_labels)
                    save_deleted_set(st.session_state.deleted_set)
                    mask = df.apply(lambda row: f"{row['Ticker']}|{row['Datum']}|{row['Signaaltype']}" not in selected_labels, axis=1)
                    st.session_state.df = df[mask].reset_index(drop=True)
                    st.session_state.confirm_delete = False
                    st.rerun()
            with c2:
                if st.button("❌ Annuleren"):
                    st.session_state.confirm_delete = False
                    st.rerun()

    html = '<table class="gap-table"><thead><tr>'
    for col in df.columns:
        html += f'<th>{col}</th>'
    html += '</tr></thead><tbody>'
    for _, row in df.iterrows():
        cls = 'dubbele-gap' if row['Signaaltype'] == 'Dubbele Gap Down' else 'bearish-gap'
        html += f'<tr class="{cls}">'
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
    st.caption("💡 Dubbele Gap Down = vet + lichtrode achtergrond.")
    csv = df.to_csv(index=False)
    st.download_button("📥 Download CSV", csv, file_name=f"bearish_signals_{datetime.now().strftime('%Y%m%d')}.csv")
else:
    st.success("✅ Geen signalen vandaag.")
    st.markdown("""
    ### 📖 Uitleg
    - **Bearish Gap**: N+1 open < low N, close < open N+1.
    - **Dubbele Gap Down**: N+1 high < low N, N+2 open < low N.
    """)

st.divider()
st.caption("📊 Yahoo Finance (15 min vertraagd) • AEX + 100 US-bedrijven")