import streamlit as st
import pandas as pd
from gap_checker import scan_all_patterns, get_market_status
from datetime import datetime
import json
import requests
import base64

# --- GitHub configuratie ---
REPO = "delaspo-hash/AEX-Gap-Down-Scanner"
SAVED_FILE = "saved_signals.json"
GITHUB_API = f"https://api.github.com/repos/{REPO}/contents/{SAVED_FILE}"
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

# --- Functies om saved_signals.json te lezen/schrijven via GitHub ---
def load_saved_signals():
    """Haal de opgeslagen signalen op. Retourneer een list of lege list."""
    try:
        resp = requests.get(GITHUB_API, headers=HEADERS)
        if resp.status_code == 200:
            content = resp.json()["content"]
            decoded = base64.b64decode(content).decode("utf-8")
            return json.loads(decoded)
        elif resp.status_code == 404:
            return []
        else:
            st.error(f"Fout bij laden opgeslagen signalen: {resp.status_code}")
            return []
    except Exception as e:
        st.error(f"Verbindingsfout: {e}")
        return []

def save_saved_signals(signals_list):
    """Sla de lijst met signalen op naar GitHub. Retourneer True bij succes."""
    sha = None
    try:
        resp = requests.get(GITHUB_API, headers=HEADERS)
        if resp.status_code == 200:
            sha = resp.json()["sha"]
    except:
        pass

    payload = {
        "message": "Update saved signals",
        "content": base64.b64encode(json.dumps(signals_list, indent=2).encode("utf-8")).decode("utf-8")
    }
    if sha:
        payload["sha"] = sha

    try:
        resp = requests.put(GITHUB_API, headers=HEADERS, json=payload)
        if resp.status_code in [200, 201]:
            return True
        else:
            st.error(f"Opslaan mislukt: {resp.status_code} – {resp.text}")
            return False
    except Exception as e:
        st.error(f"Verbindingsfout bij opslaan: {e}")
        return False

# --- Initialiseer sessie ---
if 'saved_signals' not in st.session_state:
    with st.spinner("Laden van opgeslagen signalen..."):
        st.session_state.saved_signals = load_saved_signals()

if 'daily_df' not in st.session_state or st.button("🔄 Ververs data", type="primary"):
    st.session_state.daily_df = scan_all_patterns()
    st.session_state.confirm_save = False
    st.rerun()

daily_df = st.session_state.daily_df

# --- Header met status ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("AEX", status["AEX"])
col2.metric("US Beurzen", status["US"])
col3.metric("Signalen vandaag", len(daily_df))
col4.metric("Opgeslagen", len(st.session_state.saved_signals))

st.divider()

# ============ DAGELIJKSE SIGNALEN ============
st.subheader("📋 Signalen van de laatste handelsdag")

if not daily_df.empty:
    labels = [f"{row['Ticker']} | {row['Datum']} | {row['Signaaltype']}" for _, row in daily_df.iterrows()]

    selected = st.multiselect(
        "Selecteer signalen om op te slaan:",
        options=labels,
        key="save_select"
    )

    if st.button("💾 Sla geselecteerde signalen op", disabled=len(selected) == 0):
        # Bouw een dataframe met alleen de geselecteerde rijen
        mask = daily_df.apply(
            lambda row: f"{row['Ticker']} | {row['Datum']} | {row['Signaaltype']}" in selected,
            axis=1
        )
        to_save = daily_df[mask].to_dict(orient='records')

        # Voeg toe aan de bestaande lijst (voorkom duplicaten)
        current_saved = st.session_state.saved_signals
        # Simpele duplicaatcontrole op Ticker + Datum + Signaaltype
        new_entries = []
        for entry in to_save:
            if not any(e['Ticker'] == entry['Ticker'] and e['Datum'] == entry['Datum'] and e['Signaaltype'] == entry['Signaaltype'] for e in current_saved):
                new_entries.append(entry)

        if new_entries:
            current_saved.extend(new_entries)
            if save_saved_signals(current_saved):
                st.session_state.saved_signals = current_saved
                st.success(f"{len(new_entries)} signa(a)l(en) opgeslagen!")
                st.rerun()
            else:
                st.error("Opslaan mislukt.")
        else:
            st.info("Deze signalen zijn al opgeslagen.")

    # Tabel met dagelijkse data (HTML)
    html = '<table class="gap-table"><thead><tr>'
    for col in daily_df.columns:
        html += f'<th>{col}</th>'
    html += '</tr></thead><tbody>'
    for _, row in daily_df.iterrows():
        cls = 'dubbele-gap' if row['Signaaltype'] == 'Dubbele Gap Down' else 'bearish-gap'
        html += f'<tr class="{cls}">'
        for col in daily_df.columns:
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

else:
    st.success("✅ Geen signalen vandaag.")

st.divider()

# ============ OPGESLAGEN SIGNALEN ============
st.subheader("📁 Opgeslagen signalen (permanent)")

if st.session_state.saved_signals:
    saved_df = pd.DataFrame(st.session_state.saved_signals)
    # Toon tabel
    html = '<table class="gap-table"><thead><tr>'
    for col in saved_df.columns:
        html += f'<th>{col}</th>'
    html += '</tr></thead><tbody>'
    for _, row in saved_df.iterrows():
        cls = 'dubbele-gap' if row['Signaaltype'] == 'Dubbele Gap Down' else 'bearish-gap'
        html += f'<tr class="{cls}">'
        for col in saved_df.columns:
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

    # Download CSV van opgeslagen signalen
    csv = saved_df.to_csv(index=False)
    st.download_button("📥 Download opgeslagen signalen als CSV", data=csv,
                       file_name=f"saved_signals_{datetime.now().strftime('%Y%m%d')}.csv",
                       mime="text/csv")

    # Mogelijkheid om opgeslagen signalen te verwijderen (handmatig)
    st.markdown("---")
    st.subheader("🗑️ Verwijder uit opgeslagen lijst")
    saved_labels = [f"{row['Ticker']} | {row['Datum']} | {row['Signaaltype']}" for _, row in saved_df.iterrows()]
    to_delete = st.multiselect("Selecteer signalen om te verwijderen:", options=saved_labels, key="delete_select")
    if st.button("🗑️ Verwijder geselecteerde uit opgeslagen lijst", disabled=len(to_delete) == 0):
        # Verwijder uit de lijst
        new_list = [entry for entry in st.session_state.saved_signals if f"{entry['Ticker']} | {entry['Datum']} | {entry['Signaaltype']}" not in to_delete]
        if save_saved_signals(new_list):
            st.session_state.saved_signals = new_list
            st.success(f"{len(to_delete)} signa(a)l(en) verwijderd uit opgeslagen lijst.")
            st.rerun()
        else:
            st.error("Verwijderen mislukt.")

else:
    st.info("Nog geen signalen opgeslagen. Selecteer hierboven signalen en klik op 'Sla geselecteerde signalen op'.")

st.divider()
st.caption("📊 Data via Yahoo Finance (15 min vertraagd) • AEX + 100 US-bedrijven • Opgeslagen signalen in GitHub")