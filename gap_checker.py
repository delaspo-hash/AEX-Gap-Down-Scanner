import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta
import time
import requests
from io import StringIO

# === JOUW EXACTE LIJST VAN 77 AANDELEN ===
TICKERS = [
    "AALB.AS", "AABI.BR", "AABN.AS", "AACKB.BR", "AAD.AS",
    "AADYEN.AS", "AAED.BR", "AAGN.AS", "AAKZA.AS", "AALLFG.AS",
    "AAPAM.AS", "AARCAD.AS", "AARGX.BR", "AASM.AS", "AASML.AS",
    "AASRNL.AS", "AAZE.BR", "BAMNB.AS", "BESI.AS", "BFIT.AS",
    "BNJ.AS", "BREB.BR", "CCEP.AS", "CCENER.BR", "CCMBT.BR",
    "CCOLR.BR", "CCSG.AS", "CCTPNV.AS", "CCVC.AS", "DDEME.BR",
    "DDIE.BR", "DSFIR.AS", "EELI.BR", "EXO.AS", "FER.AS",
    "GBLB.BR", "HHAL.AS", "HEIA.AS", "HEIJM.AS", "HEIO.AS",
    "IMCD.AS", "INGA.AS", "INPST.AS", "KBCA.BR", "KPN.AS",
    "LOTB.BR", "MELE.BR", "MICC.AS", "MT.AS", "NN.AS",
    "NNRP.AS", "PPHIA.AS", "PPROX.BR", "PPRX.AS", "RAND.AS",
    "REINA.AS", "REN.AS", "SBMO.AS", "SHELL.AS", "SHUR.BR",
    "SOF.BR", "SOLB.BR", "SWICH.AS", "SYENS.BR", "TTHEON.AS",
    "TITC.BR", "TUB.BR", "UCB.BR", "UUMG.AS", "UUMI.BR",
    "UUNA.AS", "VGP.BR", "VIO.BR", "VLK.AS", "VPK.AS",
    "WDP.BR", "WKL.AS"
]

def yahoo_to_stooq(ticker):
    """Zet een Yahoo-ticker om naar een Stooq-symbool (probeer .nl en .be)."""
    if ticker.endswith('.AS'):
        return ticker.replace('.AS', '').lower() + '.nl'
    elif ticker.endswith('.BR'):
        return ticker.replace('.BR', '').lower() + '.be'
    else:
        return ticker.lower()

def fetch_daily_data_stooq(ticker, days=15):
    """
    Haalt dagelijkse koersdata op van Stooq voor een ticker.
    Retourneert een DataFrame met index=Date en kolommen Open, High, Low, Close.
    """
    symbol = yahoo_to_stooq(ticker)
    # Bepaal datumbereik: vanaf (vandaag - days) tot vandaag
    end_date = datetime.now(timezone.utc) + timedelta(hours=2)  # NL tijd
    start_date = end_date - timedelta(days=days)
    d1 = start_date.strftime('%Y%m%d')
    d2 = end_date.strftime('%Y%m%d')

    url = f"https://stooq.com/q/d/l/?s={symbol}&d1={d1}&d2={d2}&i=d"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200 and resp.text.strip():
            df = pd.read_csv(StringIO(resp.text))
            if df.empty:
                return None
            # Stooq kolommen: Date,Open,High,Low,Close,Volume
            if 'Date' not in df.columns or 'Low' not in df.columns or 'High' not in df.columns or 'Open' not in df.columns or 'Close' not in df.columns:
                return None
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.set_index('Date')
            df = df.sort_index()
            return df
    except:
        pass
    return None

def fetch_daily_data_stooq_for_all(tickers):
    """Haalt dagelijkse data op voor alle tickers via Stooq (met kleine pauzes)."""
    result = {}
    for i, t in enumerate(tickers):
        df = fetch_daily_data_stooq(t)
        if df is not None and len(df) > 0:
            result[t] = df
        if (i + 1) % 10 == 0:
            time.sleep(0.2)
    return result

def fetch_today_open_prices_yahoo(tickers):
    """
    Haalt voor vandaag de openingskoers op via Yahoo intraday (1-minuut).
    Retourneert dict {ticker: float open_price}
    """
    if not tickers:
        return {}
    # Probeer batch
    try:
        data = yf.download(tickers, period="1d", interval="1m", progress=False, group_by='ticker')
        opens = {}
        for t in tickers:
            if t in data and not data[t].empty:
                df = data[t]
                if 'Open' in df.columns:
                    opens[t] = float(df.iloc[0]['Open'])
        if opens:
            return opens
    except:
        pass

    # Fallback per ticker
    opens = {}
    for t in tickers:
        try:
            df = yf.download(t, period="1d", interval="1m", progress=False)
            if not df.empty and 'Open' in df.columns:
                opens[t] = float(df.iloc[0]['Open'])
        except:
            continue
    return opens

def scan_all_patterns():
    """
    Scant op openingsgaps van vandaag t.o.v. de laatste handelsdag vóór vandaag.
    Historische dagdata van Stooq; openingskoers vandaag van Yahoo intraday.
    Alleen als beide beschikbaar zijn, wordt het aandeel getoond.
    """
    nederland_nu = datetime.now(timezone.utc) + timedelta(hours=2)
    today_nl = nederland_nu.date()
    scan_time = nederland_nu.strftime('%H:%M:%S')

    # Haal data op
    daily_data = fetch_daily_data_stooq_for_all(TICKERS)
    today_opens = fetch_today_open_prices_yahoo(TICKERS)

    results = []

    for ticker, df in daily_data.items():
        if df is None or len(df) < 1:
            continue
        try:
            # Zoek laatste handelsdag vóór vandaag (exclusief vandaag)
            df_before = df[df.index.date < today_nl]
            if df_before.empty:
                continue
            prev_row = df_before.iloc[-1]
            prev_high = float(prev_row['High'])
            prev_low = float(prev_row['Low'])

            open_today = today_opens.get(ticker)
            if open_today is None or pd.isna(open_today):
                continue

            # Bepaal exchange en schone ticker
            if ticker.endswith('.AS'):
                exchange = "Amsterdam"
                ticker_clean = ticker.replace('.AS', '')
            elif ticker.endswith('.BR'):
                exchange = "Brussel"
                ticker_clean = ticker.replace('.BR', '')
            else:
                exchange = "Onbekend"
                ticker_clean = ticker

            # Bearish Gap
            if open_today < prev_low:
                gap_pct = ((prev_low - open_today) / prev_low) * 100
                results.append({
                    'Datum': today_nl.strftime('%Y-%m-%d'),
                    'Tijdstip': scan_time,
                    'Exchange': exchange,
                    'Ticker': ticker_clean,
                    'Vorige High': round(prev_high, 2),
                    'Vorige Low': round(prev_low, 2),
                    'Open Vandaag': round(open_today, 2),
                    'Gap %': round(gap_pct, 2),
                    'Signaaltype': 'Bearish Gap'
                })

            # Bullish Gap
            if open_today > prev_high:
                gap_pct = ((open_today - prev_high) / prev_high) * 100
                results.append({
                    'Datum': today_nl.strftime('%Y-%m-%d'),
                    'Tijdstip': scan_time,
                    'Exchange': exchange,
                    'Ticker': ticker_clean,
                    'Vorige High': round(prev_high, 2),
                    'Vorige Low': round(prev_low, 2),
                    'Open Vandaag': round(open_today, 2),
                    'Gap %': round(gap_pct, 2),
                    'Signaaltype': 'Bullish Gap'
                })
        except:
            continue

    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(
            ['Datum', 'Tijdstip', 'Exchange', 'Ticker'],
            ascending=[False, False, True, True]
        )
    return df

def get_market_status():
    """Bepaal of Euronext geopend is (Nederlandse tijd)."""
    now = datetime.now(timezone.utc) + timedelta(hours=2)
    hour = now.hour
    minute = now.minute
    weekday = now.weekday()

    if weekday >= 5:
        return "🔴 Weekend - Euronext gesloten"
    if hour < 9:
        return "⏳ Euronext nog niet open"
    elif hour < 17 or (hour == 17 and minute < 30):
        return "🟢 Euronext open"
    else:
        return "🔴 Euronext gesloten"