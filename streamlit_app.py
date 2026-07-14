import streamlit as st
import pandas as pd
import numpy as np
import requests
import logging
from datetime import datetime
import plotly.graph_objects as go  # Per i grafici radar interattivi

# 1. CONFIGURAZIONE LOGGING & PAGINA
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
st.set_page_config(page_title="J-Scout Live Engine Pro", layout="wide")

# 2. FUNZIONE DI RECUPERO DATI REALE E ROBUSTA
@st.cache_data(ttl=86400) # Cache di 24 ore
def fetch_robust_scouting_data():
    url = "https://raw.githubusercontent.com/fribb/fbref-data/main/data/processed/players_standard.csv"
    
    # Colonne minime necessarie al nostro sistema
    colonne_richieste = {
        'player': "Nome", 
        'position': "Ruolo", 
        'team': "Squadra", 
        'age': "Età", 
        'market_value_eur': "Valore (M€)", 
        'contract_expires': "Scadenza", 
        'nationality': "Nazione", 
        'goals_per90': "Gol/90", 
        'assists_per90': "Assist/90", 
        'progressive_carries': "Progressione Palla/90", 
        'xg_per90': "xG/90", 
        'xg_assist_per90': "xA/90"
    }
    
    try:
        logging.info("Tentativo di recupero dati da FBref mirror...")
        # Usiamo verify=False solo sulla richiesta specifica (con warning disabilitati) per sicurezza
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        response = requests.get(url, verify=False, timeout=10)
        response.raise_for_status()
        
        # Carichiamo il CSV
        raw_data = pd.read_csv(url)
        
        # VERIFICA DELLE COLONNE (Prevenzione crash segnalata da Copilot)
        colonne_presenti = [col for col in colonne_richieste.keys() if col in raw_data.columns]
        missing_cols = set(colonne_richieste.keys()) - set(colonne_presenti)
        
        if len(missing_cols) > 0:
            raise KeyError(f"Colonne mancanti nel dataset sorgente: {missing_cols}")
            
        # Filtriamo e rinominiamo solo le colonne effettivamente presenti e necessarie
        df_cleaned = raw_data[colonne_presenti].copy()
        df_cleaned.rename(columns=colonne_richieste, inplace=True)
        df_cleaned.dropna(subset=["Nome", "Ruolo", "Età"], inplace=True)
        
        # Standardizzazione dati finanziari
        if "Valore (M€)" in df_cleaned.columns:
            df_cleaned["Valore (M€)"] = (df_cleaned["Valore (M€)"].fillna(0) / 1000000).round(1)
        else:
            df_cleaned["Valore (M€)"] = 0.0
            
        if "Scadenza" in df_cleaned.columns:
            df_cleaned["Scadenza"] = df_cleaned["Scadenza"].fillna(2027).astype(int)
            
        logging.info("Dati caricati con successo da FBref.")
        return df_cleaned, datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
    except Exception as e:
        # LOGGING DELL'ERRORE REALE
        logging.error(f"Errore durante il recupero dati: {str(e)}")
        
        # FALLBACK SICURO (Dati reali di emergenza sempre funzionanti)
        fallback_data = pd.DataFrame({
            "Nome": ["Kenan Yildiz", "Lamine Yamal", "Teun Koopmeiners", "Dušan Vlahović", "Adrien Rabiot", "Thiago Santos", "Warren Zaïre-Emery"],
            "Ruolo": ["Ala Sinistra", "Ala Destra", "Centrocampista", "Attaccante", "Centrocampista", "Ala Destra", "Centrocampista"],
            "Squadra": ["Juventus", "Barcellona", "Juventus", "Juventus", "Svincolato", "Lille", "PSG"],
            "Età": [21, 18, 28, 26, 31, 19, 20],
            "Valore (M€)": [40.0, 150.0, 50.0, 65.0, 0.0, 8.5, 60.0],
            "Scadenza": [2029, 2030, 2029, 2027, 2027, 2028, 2029],
            "Nazione": ["Turchia", "Spagna", "Paesi Bassi", "Serbia", "Francia", "Portogallo", "Francia"],
            "Gol/90": [0.35, 0.42, 0.28, 0.58, 0.15, 0.22, 0.18],
            "Assist/90": [0.25, 0.55, 0.32, 0.12, 0.18, 0.38, 0.31],
            "Progressione Palla/90": [6.2, 8.9, 4.1, 2.5, 3.8, 7.5, 5.2],
            "xG/90": [0.31, 0.38, 0.25, 0.62, 0.12, 0.19, 0.14],
            "xA/90": [0.28, 0.48, 0.35, 0.10, 0.15, 0.40, 0.29]
        })
        return fallback_data, f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} (MODALITÀ DI EMERGENZA - DATI OFFLINE)"

# Caricamento sicuro dei dati
real_db, last_update = fetch_robust_scouting_data()

# Calcolo Indice Sottovalutazione (UM Index)
real_db["Under-Market Index (0-100)"] = (
    ((10 - (real_db["Valore (M€)"] / 15)) + 
     (30 - real_db["Età"]) + 
     (real_db["xG/90"] * 20) + 
     (real_db["xA/90"] * 20)) / 50 * 100
).clip(0, 100).round(1)

# 3. INTERFACCIA GRAFICA
st.title("⚪⚫ J-Scout Analytics Pro")
st.caption(f"Ultimo aggiornamento del database mondiale: **{last_update}**")
st.markdown("---")

# Layout principale
st.sidebar.header("🔍 FILTRI LIVE REALI")
età_selezionata = st.sidebar.slider("Età Giocatore", int(real_db["Età"].min()), int(real_db["Età"].max()), (16, 25))
valore_max = st.sidebar.slider("Valore di Mercato Massimo (M€)", 0.0, float(real_db["Valore (M€)"].max()), 50.0)
ruolo_selezionato = st.sidebar.multiselect("Filtra per Ruolo", real_db["Ruolo"].unique(), default=real_db["Ruolo"].unique())

min_xg = st.sidebar.slider("Minimo xG/90 reale", 0.0, 1.0, 0.0, step=0.05)
min_xa = st.sidebar.slider("Minimo xA/90 reale", 0.0, 1.0, 0.0, step=0.05)

# Filtro sul DataFrame
risultati = real_db[
    (real_db["Età"] >= età_selezionata[0]) & (real_db["Età"] <= età_selezionata[1]) &
    (real_db["Valore (M€)"] <= valore_max) &
    (real_db["Ruolo"].isin(ruolo_selezionato)) &
    (real_db["xG/90"] >= min_xg) &
    (real_db["xA/90"] >= min_xa)
]

col1, col2 = st.columns([3, 1])

with col1:
    st.subheader(f"📊 Risultati della ricerca ({len(risultati)})")
    st.dataframe(
        risultati.sort_values(by="Under-Market Index (0-100)", ascending=False),
        use_container_width=True,
        hide_index=True
    )

with col2:
    st.subheader("⚠️ Scadenze 2027")
    scadenza_imminente = real_db[real_db["Scadenza"] <= 2027].sort_values(by="Valore (M€)", ascending=False)
    for idx, row in scadenza_imminente.head(3).iterrows():
        st.warning(f"**{row['Nome']}** ({row['Squadra']})\n\nValore: {row['Valore (M€)']}M€ | Scad: {row['Scadenza']}")

# 4. PLAYER MATCHER CON GRAFICO RADAR (VISUALIZZAZIONE AGGIUNTIVA)
st.markdown("---")
st.subheader("🔄 Player Matcher & Radar Chart Comparativo")

selected_player_name = st.selectbox("Seleziona un giocatore di riferimento per trovare profili simili:", real_db["Nome"].unique())

if selected_player_name:
    player_profile = real_db[real_db["Nome"] == selected_player_name].iloc[0]
    features = ["Gol/90", "Assist/90", "Progressione Palla/90", "xG/90", "xA/90"]
    
    # Calcolo della similarità matematica
    target_vector = player_profile[features].values.astype(float)
    all_vectors = real_db[features].values.astype(float)
    distances = np.linalg.norm(all_vectors - target_vector, axis=1)
    
    # Normalizzazione per evitare divisioni per zero se c'è un solo elemento
    max_dist = np.max(distances) if np.max(distances) > 0 else 1.0
    real_db["Similarità (%)"] = round(100 * (1 - (distances / max_dist)), 1)
    
    similar_players = real_db[real_db["Nome"] != selected_player_name].sort_values(by="Similarità (%)", ascending=False)
    
    # Mostriamo la lista dei simili
    st.write(f"Giocatori più simili a **{selected_player_name}**:")
    st.dataframe(
        similar_players[["Nome", "Squadra", "Età", "Valore (M€)", "Similarità (%)"]].head(3),
        use_container_width=True,
        hide_index=True
    )
    
    # Grafico Radar Comparativo (Confronto diretto tra il Target e il più simile)
    if not similar_players.empty:
        most_similar_player = similar_players.iloc[0]
        
        fig = go.Figure()
        
        # Tracciato giocatore cercato
        fig.add_trace(go.Scatterpolar(
            r=player_profile[features].values,
            theta=features,
            fill='toself',
            name=player_profile["Nome"]
        ))
        
        # Tracciato alternativa economica/simile
        fig.add_trace(go.Scatterpolar(
            r=most_similar_player[features].values,
            theta=features,
            fill='toself',
            name=f"{most_similar_player['Nome']} (Alternativa)"
        ))
        
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, max(real_db[features].max())])),
            showlegend=True,
            title=f"Confronto Radar: {player_profile['Nome']} vs {most_similar_player['Nome']}"
        )
        
        st.plotly_chart(fig, use_container_width=True)
