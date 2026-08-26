import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta
import time

# === JOUW EXACTE LIJST VAN 77 AANDELEN ===
TICKERS = [
    "AALB.AS",
    "AABI.BR",
    "AABN.AS",
    "AACKB.BR",
    "AAD.AS",
    "AADYEN.AS",
    "AAED.BR",
    "AAGN.AS",
    "AAKZA.AS",
    "AALLFG.AS",
    "AAPAM.AS",
    "AARCAD.AS",
    "AARGX.BR",
    "AASM.AS",
    "AASML.AS",
    "AASRNL.AS",
    "AAZE.BR",
    "BAMNB.AS",
    "BESI.AS",
    "BFIT.AS",
    "BNJ.AS",
    "BREB.BR",
    "CCEP.AS",
    "CCENER.BR",
    "CCMBT.BR",
    "CCOLR.BR",
    "CCSG.AS",
    "CCTPNV.AS",
    "CCVC.AS",
    "DDEME.BR",
    "DDIE.BR",
    "DSFIR.AS",
    "EELI.BR",
    "EXO.AS",
    "FER.AS",
    "GBLB.BR",
    "HHAL.AS",
    "HEIA.AS",
    "HEIJM.AS",
    "HEIO.AS",
    "IMCD.AS",
    "INGA.AS",
    "INPST.AS",
    "KBCA.BR",
    "KPN.AS",
    "LOTB.BR",
    "MELE.BR",
    "MICC.AS",
    "MT.AS",
    "NN.AS",
    "NNRP.AS",
    "PPHIA.AS",
    "PPROX.BR",
    "PPRX.AS",
    "RAND.AS",
    "REINA.AS",
    "REN.AS",
    "SBMO.AS",
    "SHELL.AS",
    "SHUR.BR",
    "SOF.BR",
    "SOLB.BR",
    "SWICH.AS",
    "SYENS.BR",
    "TTHEON.AS",
    "TITC.BR",
    "TUB.BR",
    "UCB.BR",
    "UUMG.AS",
    "UUMI.BR",
    "UUNA.AS",
    "VGP.BR",
    "VIO.BR",
    "VLK.AS",
    "VPK.AS",
    "WDP.BR",
    "WKL.AS"
]

def fetch_daily_data(tickers, period="5d"):
    """Haalt dagelijkse koersdata op voor een lijst tickers."""
    if not tickers:
        return {}
    try:
        data = yf.download(tickers, period=period, interval="1d", progress=False, group_by='ticker')
        if len(tickers) == 1:
            data = {tickers[0]: data}
        if data and any(not df.empty for df in data.values()):
            return data
    except:
        pass

    result = {}
    for i, t in enumerate(tickers):
        try:
            df = yf.download(t, period=period, interval="1d", progress=False)
            if not df.empty:
                result[t] = df
        except:
            continue
        if (i + 1) % 10 == 0:
            time.sleep(0.5)
    return result

def fetch_today_open_prices(tickers):
    """Haalt voor vandaag de openingskoers op via intraday (1-minuut) data."""
    if not tickers:
        return {}
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
    Scant op openingsgaps van vandaag t.o.v. de verwachte vorige handelsdag.
    Gebruikt dagdata voor vorige handelsdagen en intraday-data voor de opening van vandaag.
    Alleen als beide datums correct aanwezig zijn, wordt het aandeel getoond.
    """
    all_tickers = TICKERS
    batch_size = 50
    results = []

    nederland_nu = datetime.now(timezone.utc) + timedelta(hours=2)
    today_nl = nederland_nu.date()
    scan_time = nederland_nu.strftime('%H:%M:%S')

    # Verwachte vorige handelsdag bepalen
    if today_nl.weekday() == 0:  # maandag -> vrijdag
        expected_prev_date = today_nl - timedelta(days=3)
    else:
        expected_prev_date = today_nl - timedelta(days=1)

    daily_data = fetch_daily_data(all_tickers, period="5d")
    today_opens = fetch_today_open_prices(all_tickers)

    for ticker, df in daily_data.items():
        if df is None or len(df) < 1:
            continue
        try:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)

            df_prev = df[df.index.date == expected_prev_date]
            if df_prev.empty:
                continue
            prev_row = df_prev.iloc[-1]
            prev_high = float(prev_row['High'])
            prev_low = float(prev_row['Low'])

            open_today = today_opens.get(ticker)
            if open_today is None or pd.isna(open_today):
                continue

            # Bepaal exchange uit de ticker
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