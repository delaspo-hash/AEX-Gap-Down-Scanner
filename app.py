import streamlit as st
import pandas as pd
from gap_checker import scan_all_patterns, get_market_status
from datetime import datetime
import json
import requests
import base64
from io import BytesIO

# --- Controleer of openpyxl beschikbaar is ---
try:
    import openpyxl
    EXCEL_OK = True
except ImportError:
    EXCEL_OK = False

# --- GitHub configuratie ---
REPO = "delaspo-hash/AEX-Gap-Down-Scanner"
SAVED_FILE = "saved_signals.json"
GITHUB_API = f"https://api.github.com/repos/{REPO}/contents/{SAVED_FILE}"
TOKEN = st.secrets["GITHUB_TOKEN"]
HEADERS = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}

st.set_page_config(page_title="Euronext Gap Scanner", page_icon="🐻", layout="wide")

# Lichte tabelstijl
st.markdown("""
<style>
    .gap-table { background-color: white; color: black; border-collapse: collapse; width: 100%; font-size: 14px; }
    .gap-table th { background-color: #f2f2f2; color: black; padding: 8px; text-align: left; border-bottom: 2px solid #ddd; }
    .gap-table td { padding: 8px; border-bottom: 1px solid #ddd; color: black; }
    .bearish-gap { font-weight: bold; background-color: #ffe6e6; }
    .bullish-gap { font-weight: bold; background-color: #e6ffe6; }
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 style="color:#FF4B4B;">🐻🐂 Euronext Gap Scanner</h1>', unsafe_allow_html=True)

status = get_market_status()

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Signalen')
    return output.getvalue()

def load_saved_signals():
    try:
        resp = requests.get(GITHUB_API, headers=HEADERS)
        if resp.status_code == 200:
            content = resp.json()["content"]
            return json.loads(base64.b64decode(content).decode("utf-8"))
        elif resp.status_code == 404:
            return []
        else:
            st.error(f"Fout bij laden: {resp.status_code}")
            return []
    except Exception as e:
        st.error(f"Verbindingsfout: {e}")
        return []

def save_saved_signals(signals_list):
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
        return resp.status_code in [200, 201]
    except Exception as e:
        st.error(f"Opslaan mislukt: {e}")
        return False

# --- Sessiestate ---
if 'saved_signals' not in st.session_state:
    with st.spinner("Laden opgeslagen signalen..."):
        st.session_state.saved_signals = load_saved_signals()

if 'daily_df' not in st.session_state or st.button("🔄 Ververs data", type="primary"):
    st.session_state.daily_df = scan_all_patterns()
    st.rerun()

daily_df = st.session_state.daily_df

# --- Header metrics ---
col1, col2, col3 = st.columns(3)
col1.metric("Euronext", status)
col2.metric("Signalen vandaag", len(daily_df))
col3.metric("Opgeslagen", len(st.session_state.saved_signals))

st.divider()

# ============ DAGELIJKSE SIGNALEN ============
st.subheader("📋 Signalen van de laatste handelsdag")

if not daily_df.empty:
    labels = [f"{row['Ticker']} | {row['Datum']} | {row['Signaaltype']}" for _, row in daily_df.iterrows()]
    selected = st.multiselect("Selecteer signalen om op te slaan:", options=labels, key="save_select")

    if st.button("💾 Sla geselecteerde signalen op", disabled=len(selected) == 0):
        mask = daily_df.apply(lambda r: f"{r['Ticker']} | {r['Datum']} | {r['Signaaltype']}" in selected, axis=1)
        to_save = daily_df[mask].to_dict(orient='records')
        current = st.session_state.saved_signals
        new = [e for e in to_save if not any(x['Ticker']==e['Ticker'] and x['Datum']==e['Datum'] and x['Signaaltype']==e['Signaaltype'] for x in current)]
        if new:
            current.extend(new)
            if save_saved_signals(current):
                st.session_state.saved_signals = current
                st.success(f"{len(new)} opgeslagen!")
                st.rerun()
            else:
                st.error("Opslaan mislukt.")
        else:
            st.info("Deze signalen zijn al opgeslagen.")

    # HTML-tabel
    html = '<table class="gap-table"><thead><tr>'
    for col in daily_df.columns:
        html += f'<th>{col}</th>'
    html += '</tr></thead><tbody>'
    for _, row in daily_df.iterrows():
        cls = 'bearish-gap' if row['Signaaltype']=='Bearish Gap' else 'bullish-gap'
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

    # Downloadknoppen
    st.markdown("**Download dagelijkse signalen:**")
    st.download_button("📥 Download als CSV", daily_df.to_csv(index=False),
                       file_name=f"daily_signals_{datetime.now().strftime('%Y%m%d')}.csv",
                       mime="text/csv")
    if EXCEL_OK:
        st.download_button("📥 Download als Excel", to_excel(daily_df),
                           file_name=f"daily_signals_{datetime.now().strftime('%Y%m%d')}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.warning("Excel-export niet beschikbaar. Controleer of openpyxl in requirements.txt staat.")

else:
    st.success("✅ Geen signalen vandaag.")

st.divider()

# ============ OPGESLAGEN SIGNALEN ============
st.subheader("📁 Opgeslagen signalen (permanent)")

if st.session_state.saved_signals:
    saved_df = pd.DataFrame(st.session_state.saved_signals)

    html = '<table class="gap-table"><thead><tr>'
    for col in saved_df.columns:
        html += f'<th>{col}</th>'
    html += '</tr></thead><tbody>'
    for _, row in saved_df.iterrows():
        cls = 'bearish-gap' if row['Signaaltype']=='Bearish Gap' else 'bullish-gap'
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

    st.markdown("**Download opgeslagen signalen:**")
    st.download_button("📥 Download als CSV", saved_df.to_csv(index=False),
                       file_name=f"saved_signals_{datetime.now().strftime('%Y%m%d')}.csv",
                       mime="text/csv")
    if EXCEL_OK:
        st.download_button("📥 Download als Excel", to_excel(saved_df),
                           file_name=f"saved_signals_{datetime.now().strftime('%Y%m%d')}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.markdown("---")
    st.subheader("🗑️ Verwijder uit opgeslagen lijst")
    saved_labels = [f"{row['Ticker']} | {row['Datum']} | {row['Signaaltype']}" for _, row in saved_df.iterrows()]
    to_delete = st.multiselect("Selecteer signalen om te verwijderen:", options=saved_labels, key="delete_select")
    if st.button("🗑️ Verwijder geselecteerde", disabled=len(to_delete)==0):
        new_list = [e for e in st.session_state.saved_signals if f"{e['Ticker']} | {e['Datum']} | {e['Signaaltype']}" not in to_delete]
        if save_saved_signals(new_list):
            st.session_state.saved_signals = new_list
            st.success(f"{len(to_delete)} verwijderd.")
            st.rerun()
        else:
            st.error("Verwijderen mislukt.")
else:
    st.info("Nog geen opgeslagen signalen.")

st.divider()
st.caption("📊 Data via Yahoo Finance (15 min vertraagd) • Euronext Amsterdam & Brussel")