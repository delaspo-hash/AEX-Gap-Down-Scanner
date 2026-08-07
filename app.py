import streamlit as st
import pandas as pd
from gap_checker import scan_all_patterns, get_market_status
from datetime import datetime
import json
import requests
import base64

# --- Configuratie ---
REPO = "delaspo-hash/AEX-Gap-Down-Scanner"
FILE_PATH = "verwijderd.json"
GITHUB_API = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
TOKEN = st.secrets["GITHUB_TOKEN"]
HEADERS = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}

st.set_page_config(page_title="AEX+US Bearish Gap Scanner", page_icon="🐻", layout="wide")

# Lichte tabelstijl
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

# --- GitHub hulpfuncties (met foutmeldingen) ---
def load_deleted_set():
    """Haal de lijst met verwijderde signalen op van GitHub. Retourneer een set of None bij fout."""
    try:
        resp = requests.get(GITHUB_API, headers=HEADERS)
        if resp.status_code == 200:
            content = resp.json()["content"]
            decoded = base64.b64decode(content).decode("utf-8")
            return set(json.loads(decoded))
        elif resp.status_code == 404:
            # Bestand bestaat nog niet, dat is oké
            return set()
        else:
            st.error(f"GitHub fout bij laden: {resp.status_code} – {resp.text}")
            return None
    except Exception as e:
        st.error(f"Kan geen verbinding maken met GitHub: {e}")
        return None

def save_deleted_set(deleted_set):
    """Sla de lijst met verwijderde signalen op naar GitHub. Retourneer True bij succes."""
    # Eerst de huidige sha ophalen
    sha = None
    try:
        resp = requests.get(GITHUB_API, headers=HEADERS)
        if resp.status_code == 200:
            sha = resp.json()["sha"]
        elif resp.status_code != 404:
            st.error(f"GitHub fout bij ophalen sha: {resp.status_code}")
            return False
    except Exception as e:
        st.error(f"Verbindingsfout bij ophalen sha: {e}")
        return False

    payload = {
        "message": "Update deleted signals",
        "content": base64.b64encode(json.dumps(list(deleted_set)).encode("utf-8")).decode("utf-8")
    }
    if sha:
        payload["sha"] = sha

    try:
        resp = requests.put(GITHUB_API, headers=HEADERS, json=payload)
        if resp.status_code in [200, 201]:
            return True
        else:
            st.error(f"Fout bij opslaan: {resp.status_code} – {resp.text}")
            return False
    except Exception as e:
        st.error(f"Verbindingsfout bij opslaan: {e}")
        return False

# --- Initialiseer sessie ---
if 'deleted_set' not in st.session_state:
    with st.spinner("Laden van verwijderde signalen..."):
        st.session_state.deleted_set = load_deleted_set()
        if st.session_state.deleted_set is None:
            st.session_state.deleted_set = set()  # fallback naar lege set
if 'df' not in st.session_state:
    st.session_state.df = scan_all_patterns()
if 'confirm_delete' not in st.session_state:
    st.session_state.confirm_delete = False
if 'multiselect_key' not in st.session_state:
    st.session_state.multiselect_key = 0

# --- Ververs data (met herladen van verwijderlijst) ---
if st.button("🔄 Ververs data", type="primary"):
    # Herlaad altijd de laatste lijst van GitHub
    latest = load_deleted_set()
    if latest is not None:
        st.session_state.deleted_set = latest
    full_df = scan_all_patterns()
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

# --- Verwijderlijst legen (met bevestiging) ---
if st.button("🗑️ Verwijderlijst legen (alle signalen terugzetten)"):
    if save_deleted_set(set()):
        st.session_state.deleted_set = set()
        full_df = scan_all_patterns()
        st.session_state.df = full_df
        st.success("Verwijderlijst gewist. Alle signalen zijn terug.")
    else:
        st.error("Wissen mislukt. Controleer je token of netwerk.")
    st.rerun()

# --- Signalen weergeven ---
if not df.empty:
    st.subheader("📋 Signalen")

    labels = [f"{row['Ticker']} | {row['Datum']} | {row['Signaaltype']}" for _, row in df.iterrows()]
    selected = st.multiselect(
        "Selecteer signalen om te verwijderen:",
        options=labels,
        key=f"select_{st.session_state.multiselect_key}"
    )

    if st.button("🗑️ Verwijder geselecteerde signalen", disabled=len(selected) == 0):
        st.session_state.confirm_delete = True
        st.session_state.selected_to_delete = selected
        st.rerun()

    if st.session_state.confirm_delete and 'selected_to_delete' in st.session_state:
        with st.container():
            st.warning("⚠️ **Weet u zeker dat u de geselecteerde signalen wilt verwijderen?**")
            col_ja, col_nee = st.columns(2)
            with col_ja:
                if st.button("✅ Ja, verwijderen", key="ja_confirm"):
                    # Werk de set bij
                    st.session_state.deleted_set.update(st.session_state.selected_to_delete)
                    # Opslaan naar GitHub
                    if save_deleted_set(st.session_state.deleted_set):
                        mask = df.apply(
                            lambda row: f"{row['Ticker']} | {row['Datum']} | {row['Signaaltype']}" not in st.session_state.selected_to_delete,
                            axis=1
                        )
                        st.session_state.df = df[mask].reset_index(drop=True)
                        st.success("Verwijderd!")
                    else:
                        st.error("Verwijdering niet opgeslagen op GitHub. Signaal blijft na verversen terugkomen.")
                    # Reset popup en multiselect
                    st.session_state.confirm_delete = False
                    del st.session_state.selected_to_delete
                    st.session_state.multiselect_key += 1
                    st.rerun()
            with col_nee:
                if st.button("❌ Annuleren", key="nee_confirm"):
                    st.session_state.confirm_delete = False
                    if 'selected_to_delete' in st.session_state:
                        del st.session_state.selected_to_delete
                    st.rerun()

    # HTML-tabel
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