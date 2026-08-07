import streamlit as st
import pandas as pd
from gap_checker import scan_all_patterns, get_market_status
from datetime import datetime
import json
import streamlit.components.v1 as components

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

# ==================== COOKIE FUNCTIES ====================
def set_cookie(key, value):
    """Sla een waarde op in een cookie (als JSON string)"""
    js = f"""
    <script>
        document.cookie = "{key}=" + '{json.dumps(list(value))}' + "; path=/; max-age=" + (365*24*60*60);
    </script>
    """
    components.html(js, height=0)

def get_cookie(key):
    """Lees een cookie uit en retourneer als Python object (list of lege list)"""
    # We gebruiken een trucje: we injecteren een script dat de cookie-waarde terugstuurt via de URL
    # Streamlit kan dan de query parameters uitlezen.
    # Dit is een betrouwbare manier zonder callbacks.
    
    # We gebruiken een unieke key om de waarde in de session state te krijgen.
    # Omdat de cookie direct beschikbaar is, kunnen we de JavaScript uitvoeren en een redirect doen
    # naar dezelfde pagina met ?cookie_data=... 
    # Maar dat is omslachtig.
    
    # Eenvoudiger: we gebruiken st.markdown met een hidden iframe dat de cookie doorgeeft aan Python.
    # Dat werkt niet direct.
    
    # Alternatief: we gebruiken de experimentele st.components.v1.declare_component.
    # Voor nu: we lezen de cookie eenmalig met behulp van st.markdown die een script draait
    # en de waarde in een HTML element zet, en dan lezen we dat element met een andere component?
    
    # De meest pragmatische aanpak: gebruik st.experimental_get_query_params 
    # en laat de pagina automatisch herladen met de cookie in de URL.
    
    # Omdat de gebruiker waarschijnlijk een eenvoudige oplossing wil, doen we het zo:
    # We zetten bij het laden een JS script dat de cookie-waarde in een query parameter plaatst en de pagina herlaadt.
    # Dat is één extra refresh bij de eerste keer laden, daarna is de waarde in st.session_state.
    
    return []  # placeholder, we implementeren hieronder een werkend mechanisme