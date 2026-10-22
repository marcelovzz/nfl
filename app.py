import math
import os
import warnings
import numpy as np
import pandas as pd
import streamlit as st

warnings.filterwarnings("ignore")

try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# ==============================================================================
# CONFIGURACIÓN DE PÁGINA Y ARQUITECTURA CYBER-QUANT / BLOOMBERG SPORTSBOOK
# ==============================================================================
st.set_page_config(
    page_title="TERMINAL SHARP: NFL QUANT SCANNER",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==============================================================================
# ESTILOS CSS: CYBER-QUANT UI + GLASSMORPHISM CARTELERA 3x3 + DRILL-DOWN
# ==============================================================================
CYBER_QUANT_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Orbitron:wght@500;600;700;800;900&family=Inter:wght@400;500;600;700&display=swap');

:root {
    --bg-main: #060A12;
    --bg-panel: #0C1322;
    --bg-card: #111A2E;
    --bg-card-alt: #0E1729;
    --cyan-neon: #00F0FF;
    --green-sharp: #00E676;
    --amber-quant: #FFB300;
    --red-alert: #FF2E63;
    --purple-prop: #B388FF;
    --text-primary: #ECF2F8;
    --text-muted: #8A99AD;
    --border-subtle: rgba(0, 240, 255, 0.18);
    --border-strong: rgba(0, 240, 255, 0.42);
}

.stApp {
    background: radial-gradient(circle at 15% 10%, #0D1B30 0%, #060A12 55%, #04070D 100%);
    color: var(--text-primary);
    font-family: 'Inter', sans-serif;
}

/* Encabezado Principal Terminal */
.terminal-banner {
    background: linear-gradient(135deg, rgba(12, 19, 34, 0.96) 0%, rgba(17, 26, 46, 0.92) 100%);
    border: 1px solid var(--border-strong);
    border-left: 5px solid var(--cyan-neon);
    border-radius: 12px;
    padding: 18px 24px;
    margin-bottom: 18px;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.55), 0 0 18px rgba(0, 240, 255, 0.08);
}

.terminal-title {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.72rem;
    font-weight: 800;
    letter-spacing: 1.8px;
    color: #FFFFFF;
    margin: 0;
    text-transform: uppercase;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
}

.terminal-subtitle {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.81rem;
    color: var(--cyan-neon);
    letter-spacing: 0.8px;
    margin-top: 6px;
}

.live-pill {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 700;
    background: rgba(0, 230, 118, 0.14);
    color: var(--green-sharp);
    border: 1px solid var(--green-sharp);
    padding: 4px 10px;
    border-radius: 999px;
    letter-spacing: 1px;
}

/* Títulos de Sección */
.radar-section-title {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.05rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: var(--cyan-neon);
    text-transform: uppercase;
    margin: 16px 0 12px 0;
    border-bottom: 1px solid var(--border-subtle);
    padding-bottom: 6px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

/* Radar Ejecutivo de la Semana */
.radar-card {
    background: linear-gradient(180deg, rgba(17, 26, 46, 0.92) 0%, rgba(11, 17, 30, 0.96) 100%);
    backdrop-filter: blur(10px);
    border: 1px solid var(--border-subtle);
    border-top: 3px solid var(--cyan-neon);
    border-radius: 10px;
    padding: 14px 16px;
    height: 100%;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45);
}

.radar-card.lock { border-top-color: var(--green-sharp); }
.radar-card.total { border-top-color: var(--cyan-neon); }
.radar-card.star { border-top-color: var(--amber-quant); }
.radar-card.dog { border-top-color: var(--purple-prop); }

.radar-tag {
    font-family: 'Orbitron', sans-serif;
    font-size: 0.70rem;
    font-weight: 700;
    letter-spacing: 1.1px;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 6px;
}

.radar-pick {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.02rem;
    font-weight: 800;
    color: #FFFFFF;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.radar-metrics {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.79rem;
    color: var(--cyan-neon);
    margin-bottom: 4px;
}

.radar-sub {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    color: var(--text-muted);
}

/* ==========================================================================
   CARTELERA DEPORTIVA 3x3 (GLASSMORPHISM MATCHUP CARDS)
   ========================================================================== */
.billboard-card {
    background: linear-gradient(160deg, rgba(19, 30, 54, 0.78) 0%, rgba(10, 16, 29, 0.88) 100%);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(0, 240, 255, 0.22);
    border-radius: 14px;
    padding: 16px 18px 14px 18px;
    margin-bottom: 6px;
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.08);
    transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.billboard-card:hover {
    border-color: rgba(0, 240, 255, 0.58);
    box-shadow: 0 14px 36px rgba(0, 0, 0, 0.68), 0 0 18px rgba(0, 240, 255, 0.14);
    transform: translateY(-2px);
}

.billboard-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding-bottom: 9px;
    margin-bottom: 12px;
}

.league-week-pill {
    font-family: 'Orbitron', sans-serif;
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 1.2px;
    color: var(--cyan-neon);
    background: rgba(0, 240, 255, 0.12);
    border: 1px solid rgba(0, 240, 255, 0.30);
    padding: 3px 9px;
    border-radius: 999px;
    text-transform: uppercase;
}

.kickoff-time {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    color: var(--text-muted);
    font-weight: 600;
}

.billboard-team-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 7px 0;
}

.billboard-team-left {
    display: flex;
    align-items: center;
    gap: 11px;
    min-width: 0;
}

.team-logo-card {
    width: 38px;
    height: 38px;
    object-fit: contain;
    filter: drop-shadow(0 2px 6px rgba(0, 0, 0, 0.6));
    background: rgba(255, 255, 255, 0.04);
    border-radius: 50%;
    padding: 3px;
    border: 1px solid rgba(255, 255, 255, 0.10);
}

.team-name-card {
    font-family: 'Orbitron', sans-serif;
    font-size: 0.88rem;
    font-weight: 700;
    color: #FFFFFF;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.team-sub-card {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.69rem;
    color: var(--text-muted);
    margin-top: 1px;
}

/* Pastillas W/L de Forma Reciente */
.wl-container {
    display: flex;
    align-items: center;
    gap: 3px;
}

.wl-pill {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.63rem;
    font-weight: 800;
    width: 19px;
    height: 19px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    letter-spacing: 0;
}

.wl-pill.w {
    background: rgba(0, 230, 118, 0.18);
    color: #00E676;
    border: 1px solid rgba(0, 230, 118, 0.48);
}

.wl-pill.l {
    background: rgba(255, 46, 99, 0.18);
    color: #FF2E63;
    border: 1px solid rgba(255, 46, 99, 0.45);
}

/* Caja de Pronóstico Rápido en la Tarjeta */
.billboard-prediction-box {
    margin-top: 11px;
    padding: 10px 12px;
    background: rgba(6, 10, 18, 0.78);
    border: 1px solid rgba(0, 240, 255, 0.22);
    border-left: 3px solid var(--green-sharp);
    border-radius: 9px;
}

.prediction-headline {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.80rem;
    font-weight: 700;
    color: #FFFFFF;
}

.prediction-headline span.score-hi {
    color: var(--green-sharp);
    font-weight: 800;
}

.prediction-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 5px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.70rem;
    color: var(--cyan-neon);
}

/* ==========================================================================
   SCOREBOARD TV HEADER (VISTA DETALLADA DRILL-DOWN)
   ========================================================================== */
.tv-scoreboard {
    background: linear-gradient(90deg, rgba(11, 19, 36, 0.95) 0%, rgba(19, 32, 59, 0.95) 50%, rgba(11, 19, 36, 0.95) 100%);
    backdrop-filter: blur(16px);
    border: 1px solid var(--border-strong);
    border-radius: 14px;
    padding: 18px 24px;
    margin-top: 10px;
    margin-bottom: 16px;
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.6);
}

.tv-top-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding-bottom: 8px;
    margin-bottom: 14px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: var(--text-muted);
}

.tv-main-grid {
    display: grid;
    grid-template-columns: 1.35fr 1fr 1.35fr;
    align-items: center;
    gap: 14px;
}

.team-side {
    display: flex;
    align-items: center;
    gap: 15px;
}

.team-side.right {
    justify-content: flex-end;
    text-align: right;
}

.team-logo-tv {
    width: 68px;
    height: 68px;
    object-fit: contain;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(0, 240, 255, 0.30);
    border-radius: 14px;
    padding: 6px;
    filter: drop-shadow(0 4px 10px rgba(0, 0, 0, 0.65));
}

.team-name-tv {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.12rem;
    font-weight: 800;
    color: #FFFFFF;
}

.team-epa-sub {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 3px;
    margin-bottom: 5px;
}

.score-center-box {
    text-align: center;
    background: rgba(6, 10, 18, 0.82);
    border: 1px solid rgba(0, 240, 255, 0.32);
    border-radius: 12px;
    padding: 12px 16px;
    box-shadow: inset 0 0 18px rgba(0, 240, 255, 0.06);
}

.projected-score-tv {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.65rem;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: 2px;
}

.projected-total-pill {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.76rem;
    color: var(--amber-quant);
    margin-top: 4px;
    font-weight: 700;
}

/* Tarjetas Cuantitativas de Mercados y Props */
.quant-card {
    background: linear-gradient(180deg, rgba(17, 26, 46, 0.90) 0%, rgba(12, 19, 34, 0.94) 100%);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 12px;
    padding: 15px 18px;
    height: 100%;
}

.quant-card-header {
    font-family: 'Orbitron', sans-serif;
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--cyan-neon);
    letter-spacing: 1px;
    text-transform: uppercase;
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
    padding-bottom: 6px;
    margin-bottom: 10px;
}

.metric-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 0;
    border-bottom: 1px dashed rgba(255, 255, 255, 0.06);
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.81rem;
}

.metric-row:last-child {
    border-bottom: none;
}

.metric-label {
    color: var(--text-muted);
}

.metric-val {
    color: #FFFFFF;
    font-weight: 700;
}

.odds-chip {
    background: rgba(0, 240, 255, 0.12);
    color: var(--cyan-neon);
    border: 1px solid rgba(0, 240, 255, 0.3);
    padding: 2px 7px;
    border-radius: 5px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    font-weight: 600;
}

.odds-chip.green {
    background: rgba(0, 230, 118, 0.13);
    color: var(--green-sharp);
    border-color: rgba(0, 230, 118, 0.35);
}

.odds-chip.amber {
    background: rgba(255, 179, 0, 0.13);
    color: var(--amber-quant);
    border-color: rgba(255, 179, 0, 0.35);
}

.td-prop-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    margin-top: 8px;
}

.td-prop-box {
    background: rgba(6, 10, 18, 0.70);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-left: 3px solid var(--amber-quant);
    border-radius: 8px;
    padding: 9px 11px;
    font-family: 'JetBrains Mono', monospace;
}

.td-role {
    font-size: 0.68rem;
    color: var(--text-muted);
    text-transform: uppercase;
}

.td-player {
    font-size: 0.81rem;
    font-weight: 700;
    color: #FFFFFF;
    margin: 2px 0;
}

.td-prob {
    font-size: 0.84rem;
    font-weight: 800;
    color: var(--green-sharp);
}

.td-odds {
    font-size: 0.71rem;
    color: var(--cyan-neon);
}

/* Estilizado de Botones Streamlit para Acción Cartelera */
div.stButton > button {
    font-family: 'Orbitron', sans-serif !important;
    font-size: 0.76rem !important;
    font-weight: 700 !important;
    letter-spacing: 1px !important;
    border-radius: 9px !important;
    border: 1px solid rgba(0, 240, 255, 0.38) !important;
    background: linear-gradient(90deg, rgba(0, 240, 255, 0.12) 0%, rgba(0, 230, 118, 0.12) 100%) !important;
    color: #ECF2F8 !important;
    transition: all 0.18s ease !important;
}

div.stButton > button:hover {
    border-color: #00F0FF !important;
    background: linear-gradient(90deg, rgba(0, 240, 255, 0.26) 0%, rgba(0, 230, 118, 0.24) 100%) !important;
    color: #FFFFFF !important;
    box-shadow: 0 0 14px rgba(0, 240, 255, 0.28) !important;
}
</style>
"""
st.markdown(CYBER_QUANT_CSS, unsafe_allow_html=True)


# ==============================================================================
# 1. METADATA DE EQUIPOS, LOGOS OFICIALES ESPN/NFLVERSE Y EXTRACCIÓN 2026
# ==============================================================================
SEASON_DEFAULT = 2026

PBP_COLS = [
    "game_id", "season_type", "posteam", "defteam", "home_team", "away_team",
    "home_score", "away_score", "drive", "game_seconds_remaining", "play_type",
    "pass_attempt", "rush_attempt", "qb_spike", "qb_kneel", "two_point_attempt",
    "epa", "success", "yardline_100", "touchdown", "td_team", "pass_touchdown",
    "rush_touchdown", "sack", "qb_hit", "passer_player_id", "passer_player_name",
    "rusher_player_id", "rusher_player_name", "receiver_player_id", "receiver_player_name"
]

NFL_TEAMS_META = {
    "KC":  {"Equipo": "Kansas City Chiefs",    "Dome": 0, "Cold_Base": 0.015, "HFA_Mod": 0.35, "ESPN": "kc",  "Form": "W-W-W-L-W"},
    "SF":  {"Equipo": "San Francisco 49ers",   "Dome": 0, "Cold_Base": 0.048, "HFA_Mod": 0.20, "ESPN": "sf",  "Form": "W-W-L-W-W"},
    "BUF": {"Equipo": "Buffalo Bills",         "Dome": 0, "Cold_Base": 0.010, "HFA_Mod": 0.30, "ESPN": "buf", "Form": "W-L-W-W-W"},
    "BAL": {"Equipo": "Baltimore Ravens",      "Dome": 0, "Cold_Base": 0.018, "HFA_Mod": 0.28, "ESPN": "bal", "Form": "W-W-W-W-L"},
    "DET": {"Equipo": "Detroit Lions",         "Dome": 1, "Cold_Base": 0.055, "HFA_Mod": 0.32, "ESPN": "det", "Form": "W-W-W-L-W"},
    "DAL": {"Equipo": "Dallas Cowboys",        "Dome": 1, "Cold_Base": 0.052, "HFA_Mod": 0.22, "ESPN": "dal", "Form": "W-L-W-L-W"},
    "PHI": {"Equipo": "Philadelphia Eagles",   "Dome": 0, "Cold_Base": 0.022, "HFA_Mod": 0.30, "ESPN": "phi", "Form": "W-W-L-W-W"},
    "NE":  {"Equipo": "New England Patriots",  "Dome": 0, "Cold_Base": 0.014, "HFA_Mod": 0.12, "ESPN": "ne",  "Form": "L-W-L-L-W"},
    "HOU": {"Equipo": "Houston Texans",        "Dome": 1, "Cold_Base": 0.050, "HFA_Mod": 0.20, "ESPN": "hou", "Form": "W-W-L-W-L"},
    "GB":  {"Equipo": "Green Bay Packers",     "Dome": 0, "Cold_Base": 0.012, "HFA_Mod": 0.28, "ESPN": "gb",  "Form": "W-L-W-W-L"},
    "CIN": {"Equipo": "Cincinnati Bengals",    "Dome": 0, "Cold_Base": 0.020, "HFA_Mod": 0.22, "ESPN": "cin", "Form": "L-W-W-L-W"},
    "MIA": {"Equipo": "Miami Dolphins",        "Dome": 0, "Cold_Base": 0.082, "HFA_Mod": 0.24, "ESPN": "mia", "Form": "W-L-L-W-W"},
    "LAR": {"Equipo": "Los Angeles Rams",      "Dome": 1, "Cold_Base": 0.056, "HFA_Mod": 0.15, "ESPN": "lar", "Form": "W-L-W-W-L"},
    "MIN": {"Equipo": "Minnesota Vikings",     "Dome": 1, "Cold_Base": 0.045, "HFA_Mod": 0.28, "ESPN": "min", "Form": "W-W-L-W-L"},
    "NYJ": {"Equipo": "New York Jets",         "Dome": 0, "Cold_Base": 0.025, "HFA_Mod": 0.16, "ESPN": "nyj", "Form": "L-W-L-W-L"},
    "CLE": {"Equipo": "Cleveland Browns",      "Dome": 0, "Cold_Base": 0.018, "HFA_Mod": 0.22, "ESPN": "cle", "Form": "L-L-W-L-W"},
    "PIT": {"Equipo": "Pittsburgh Steelers",   "Dome": 0, "Cold_Base": 0.015, "HFA_Mod": 0.26, "ESPN": "pit", "Form": "W-W-L-W-L"},
    "ATL": {"Equipo": "Atlanta Falcons",       "Dome": 1, "Cold_Base": 0.054, "HFA_Mod": 0.18, "ESPN": "atl", "Form": "W-L-W-L-W"},
    "CHI": {"Equipo": "Chicago Bears",         "Dome": 0, "Cold_Base": 0.016, "HFA_Mod": 0.20, "ESPN": "chi", "Form": "L-W-W-L-L"},
    "JAX": {"Equipo": "Jacksonville Jaguars",  "Dome": 0, "Cold_Base": 0.058, "HFA_Mod": 0.15, "ESPN": "jax", "Form": "L-W-L-W-L"},
    "IND": {"Equipo": "Indianapolis Colts",    "Dome": 1, "Cold_Base": 0.048, "HFA_Mod": 0.18, "ESPN": "ind", "Form": "W-L-W-L-L"},
    "SEA": {"Equipo": "Seattle Seahawks",      "Dome": 0, "Cold_Base": 0.024, "HFA_Mod": 0.32, "ESPN": "sea", "Form": "W-L-W-L-W"},
    "TB":  {"Equipo": "Tampa Bay Buccaneers",  "Dome": 0, "Cold_Base": 0.055, "HFA_Mod": 0.18, "ESPN": "tb",  "Form": "W-L-L-W-W"},
    "WAS": {"Equipo": "Washington Commanders", "Dome": 0, "Cold_Base": 0.025, "HFA_Mod": 0.16, "ESPN": "wsh", "Form": "W-W-L-W-L"},
    "ARI": {"Equipo": "Arizona Cardinals",     "Dome": 1, "Cold_Base": 0.056, "HFA_Mod": 0.16, "ESPN": "ari", "Form": "L-W-L-L-W"},
    "LAC": {"Equipo": "Los Angeles Chargers",  "Dome": 1, "Cold_Base": 0.048, "HFA_Mod": 0.12, "ESPN": "lac", "Form": "W-L-W-W-L"},
    "NO":  {"Equipo": "New Orleans Saints",    "Dome": 1, "Cold_Base": 0.058, "HFA_Mod": 0.25, "ESPN": "no",  "Form": "L-L-W-L-W"},
    "LV":  {"Equipo": "Las Vegas Raiders",     "Dome": 1, "Cold_Base": 0.046, "HFA_Mod": 0.16, "ESPN": "lv",  "Form": "L-W-L-L-L"},
    "DEN": {"Equipo": "Denver Broncos",        "Dome": 0, "Cold_Base": 0.016, "HFA_Mod": 0.32, "ESPN": "den", "Form": "W-W-L-L-W"},
    "TEN": {"Equipo": "Tennessee Titans",      "Dome": 0, "Cold_Base": 0.032, "HFA_Mod": 0.18, "ESPN": "ten", "Form": "L-L-W-L-L"},
    "NYG": {"Equipo": "New York Giants",       "Dome": 0, "Cold_Base": 0.022, "HFA_Mod": 0.14, "ESPN": "nyg", "Form": "L-W-L-L-L"},
    "CAR": {"Equipo": "Carolina Panthers",     "Dome": 0, "Cold_Base": 0.038, "HFA_Mod": 0.14, "ESPN": "car", "Form": "L-L-L-W-L"},
}

TEAM_ABBR_NORMALIZE = {
    "LA": "LAR", "STL": "LAR", "SD": "LAC", "OAK": "LV",
    "WSH": "WAS", "JAC": "JAX", "ARZ": "ARI", "BLT": "BAL",
    "CLV": "CLE", "HST": "HOU",
}

HORARIOS_CARTELERA = [
    "JUE 20:15 ET · TNF",
    "DOM 13:00 ET · FOX",
    "DOM 13:00 ET · CBS",
    "DOM 13:00 ET · CBS",
    "DOM 13:00 ET · FOX",
    "DOM 13:00 ET · CBS",
    "DOM 16:05 ET · FOX",
    "DOM 16:25 ET · CBS",
    "DOM 20:20 ET · SNF",
    "LUN 20:15 ET · MNF",
    "DOM 13:00 ET · FOX",
    "DOM 13:00 ET · CBS",
    "DOM 16:05 ET · CBS",
    "DOM 16:25 ET · FOX",
    "DOM 16:25 ET · CBS",
    "LUN 21:00 ET · ESPN",
]


def normalizar_abrev(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().replace(TEAM_ABBR_NORMALIZE)


def abreviar_nombre_jugador(nombre: str) -> str:
    if not isinstance(nombre, str) or not nombre.strip():
        return "N/A"
    nombre = nombre.strip()
    if "." in nombre.split()[0]:
        return nombre
    partes = nombre.split()
    if len(partes) >= 2:
        return f"{partes[0][0]}. {' '.join(partes[1:])}"
    return nombre


def obtener_logo_url(abrev: str) -> str:
    """Devuelve la URL oficial del logo en el CDN de ESPN para una abreviatura NFL."""
    abrev_clean = str(abrev).upper().strip()
    meta = NFL_TEAMS_META.get(abrev_clean)
    espn_code = meta["ESPN"] if meta and "ESPN" in meta else abrev_clean.lower()
    if espn_code == "was":
        espn_code = "wsh"
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{espn_code}.png"


def renderizar_pastillas_wl(form_str: str) -> str:
    """Convierte una cadena 'W-W-L-W-W' en pastillas HTML de colores W/L."""
    if not isinstance(form_str, str) or not form_str.strip():
        form_str = "W-L-W-L-W"
    tokens = [t.strip().upper() for t in form_str.replace(",", "-").split("-") if t.strip()][:5]
    if not tokens:
        tokens = ["W", "L", "W", "L", "W"]
    pills_html = []
    for tok in tokens:
        clase = "w" if tok.startswith("W") else "l"
        letra = "W" if clase == "w" else "L"
        pills_html.append(f'<span class="wl-pill {clase}">{letra}</span>')
    return f'<div class="wl-container">{"".join(pills_html)}</div>'


@st.cache_data(ttl=86400, show_spinner=False)
def sincronizar_nflverse_2026(
    season: int = 2026,
    csv_path: str = "nfl_stats_completo.csv",
) -> pd.DataFrame:
    """
    Descarga directamente las tablas oficiales de nflverse para la temporada 2026
    usando pandas puro + pyarrow (sin nfl_data_py):
    - Play-by-Play 2026 (Parquet): extrae solo las columnas necesarias en <3s.
    - Fast Rosters 2026 (CSV / Parquet): mapea posiciones (QB, RB, WR, TE) y nombres.
    Cruza todas las métricas avanzadas, guarda 'nfl_stats_completo.csv' y devuelve
    el DataFrame indexado por 'Equipo'.
    """
    url_pbp_2026 = f"https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet"
    url_fast_rosters_2026_csv = f"https://raw.githubusercontent.com/nflverse/nflfastR-roster/master/data/seasons/roster_{season}.csv"
    url_rosters_2026_parquet = f"https://github.com/nflverse/nflverse-data/releases/download/rosters/roster_{season}.parquet"

    try:
        pbp = pd.read_parquet(url_pbp_2026, columns=PBP_COLS, engine="pyarrow")

        try:
            rosters = pd.read_csv(url_fast_rosters_2026_csv)
        except Exception:
            rosters = pd.read_parquet(url_rosters_2026_parquet, engine="pyarrow")

        df = pbp[pbp["season_type"].isin(["REG", "POST"])].copy()
        df["posteam"] = normalizar_abrev(df["posteam"])
        df["defteam"] = normalizar_abrev(df["defteam"])
        df = df[df["posteam"].isin(NFL_TEAMS_META.keys()) & df["defteam"].isin(NFL_TEAMS_META.keys())]

        # Calcular racha reciente real (últimos 5 juegos) por franquicia
        form_map = {}
        if {"home_team", "away_team", "home_score", "away_score"}.issubset(df.columns):
            games_df = (
                df[["game_id", "home_team", "away_team", "home_score", "away_score"]]
                .drop_duplicates(subset=["game_id"])
                .dropna()
            )
            games_df["home_team"] = normalizar_abrev(games_df["home_team"])
            games_df["away_team"] = normalizar_abrev(games_df["away_team"])
            for abrev in NFL_TEAMS_META.keys():
                tg = games_df[(games_df["home_team"] == abrev) | (games_df["away_team"] == abrev)].tail(5)
                if not tg.empty:
                    res_list = []
                    for _, grow in tg.iterrows():
                        es_home = grow["home_team"] == abrev
                        gano = (grow["home_score"] >= grow["away_score"]) if es_home else (grow["away_score"] > grow["home_score"])
                        res_list.append("W" if gano else "L")
                    while len(res_list) < 5:
                        res_list.insert(0, "W")
                    form_map[abrev] = "-".join(res_list[-5:])

        for col_flag in ["qb_spike", "qb_kneel", "two_point_attempt"]:
            df = df[df[col_flag].fillna(0) == 0]

        df["is_pass"] = (df["pass_attempt"].fillna(0) == 1) | (df["play_type"] == "pass")
        df["is_rush"] = (df["rush_attempt"].fillna(0) == 1) | (df["play_type"] == "run")
        scrimmage = df[(df["is_pass"] | df["is_rush"]) & df["epa"].notna()].copy()

        pass_plays = scrimmage[scrimmage["is_pass"]].copy()
        rush_plays = scrimmage[scrimmage["is_rush"]].copy()
        pass_plays["success"] = pass_plays["success"].fillna((pass_plays["epa"] > 0).astype(float))

        off_pass = pass_plays.groupby("posteam").agg(
            Pass_EPA=("epa", "mean"),
            Pass_Success_Rate=("success", "mean"),
            n_pass=("epa", "count"),
        )
        off_rush = rush_plays.groupby("posteam").agg(
            Rush_EPA=("epa", "mean"),
            n_rush=("epa", "count"),
        )
        off_summary = off_pass.join(off_rush, how="outer").fillna(0.0)
        off_summary["Pass_Rate"] = (
            off_summary["n_pass"] / (off_summary["n_pass"] + off_summary["n_rush"]).replace(0, np.nan)
        ).fillna(0.565)

        scr_sorted = scrimmage.sort_values(["game_id", "drive", "game_seconds_remaining"], ascending=[True, True, False])
        scr_sorted["sec_diff"] = scr_sorted.groupby(["game_id", "posteam", "drive"])["game_seconds_remaining"].diff(-1)
        valid_pace = scr_sorted[(scr_sorted["sec_diff"] >= 12) & (scr_sorted["sec_diff"] <= 40)]
        pace_raw = valid_pace.groupby("posteam")["sec_diff"].mean()
        scale_factor = (27.4 / pace_raw.mean()) if (not pace_raw.empty and pace_raw.mean() > 0) else 1.0
        off_summary["Pace_Sec"] = (pace_raw * scale_factor).reindex(off_summary.index).fillna(27.4).clip(25.2, 30.2)

        rz_plays = scrimmage[scrimmage["yardline_100"].fillna(99) <= 20].copy()
        rz_plays["off_td"] = ((rz_plays["touchdown"].fillna(0) == 1) & (rz_plays["td_team"] == rz_plays["posteam"])).astype(int)
        rz_off_pct = rz_plays.groupby(["posteam", "game_id", "drive"])["off_td"].max().groupby("posteam").mean()
        rz_def_stop = 1.0 - rz_plays.groupby(["defteam", "game_id", "drive"])["off_td"].max().groupby("defteam").mean()
        off_summary["RedZone_TD_Pct"] = rz_off_pct.reindex(off_summary.index).fillna(0.565).clip(0.420, 0.720)

        def_pass = pass_plays.groupby("defteam").agg(
            Def_Pass_EPA=("epa", "mean"),
            sacks=("sack", "sum"),
            qb_hits=("qb_hit", "sum"),
            dropbacks=("epa", "count"),
        )
        def_rush = rush_plays.groupby("defteam").agg(Def_Rush_EPA=("epa", "mean"))
        def_summary = def_pass.join(def_rush, how="outer").fillna(0.0)
        disruption = (def_summary["sacks"] + 0.85 * def_summary["qb_hits"]) / def_summary["dropbacks"].replace(0, np.nan)
        scale_press = (0.248 / disruption.mean()) if (disruption.mean() and disruption.mean() > 0) else 1.65
        def_summary["Pressure_Pct"] = (disruption * scale_press).fillna(0.245).clip(0.190, 0.310)
        def_summary["Def_RZ_Stop_Pct"] = rz_def_stop.reindex(def_summary.index).fillna(0.485).clip(0.380, 0.620)

        team_metrics = off_summary.join(
            def_summary[["Def_Pass_EPA", "Def_Rush_EPA", "Pressure_Pct", "Def_RZ_Stop_Pct"]],
            how="outer",
        )

        pos_map, name_map = {}, {}
        id_col = "gsis_id" if "gsis_id" in rosters.columns else ("player_id" if "player_id" in rosters.columns else None)
        pos_col = "position" if "position" in rosters.columns else ("depth_chart_position" if "depth_chart_position" in rosters.columns else None)
        name_col = "short_name" if "short_name" in rosters.columns else ("full_name" if "full_name" in rosters.columns else "player_name")

        if id_col and pos_col:
            for _, r_row in rosters.dropna(subset=[id_col, pos_col]).iterrows():
                pid = str(r_row[id_col])
                pos_map[pid] = str(r_row[pos_col]).upper().strip()
                if name_col in rosters.columns and pd.notna(r_row[name_col]):
                    name_map[pid] = abreviar_nombre_jugador(str(r_row[name_col]))

        team_games = df.groupby("posteam")["game_id"].nunique().replace(0, 1)
        total_tds_team = (df.groupby("posteam")["pass_touchdown"].sum().add(df.groupby("posteam")["rush_touchdown"].sum(), fill_value=0)).replace(0, 1)
        tds_per_game_team = (total_tds_team / team_games).clip(1.5, 4.2)

        qb_passes = df[df["passer_player_id"].notna()].groupby(["posteam", "passer_player_id"]).agg(
            att=("pass_attempt", "sum"), games_qb=("game_id", "nunique"), name=("passer_player_name", "first")
        ).reset_index()

        rush_df = df[df["rusher_player_id"].notna()].copy()
        rush_df["is_rz"] = (rush_df["yardline_100"].fillna(99) <= 20).astype(int)
        rush_stats = rush_df.groupby(["posteam", "rusher_player_id"]).agg(
            carries=("rush_attempt", "sum"), rz_carries=("is_rz", "sum"),
            rush_td=("rush_touchdown", "sum"), games_rush=("game_id", "nunique"), name=("rusher_player_name", "first")
        ).reset_index().rename(columns={"rusher_player_id": "player_id", "name": "rush_name"})

        rec_df = df[df["receiver_player_id"].notna()].copy()
        rec_df["is_rz"] = (rec_df["yardline_100"].fillna(99) <= 20).astype(int)
        rec_stats = rec_df.groupby(["posteam", "receiver_player_id"]).agg(
            targets=("pass_attempt", "sum"), rz_targets=("is_rz", "sum"),
            rec_td=("pass_touchdown", "sum"), games_rec=("game_id", "nunique"), name=("receiver_player_name", "first")
        ).reset_index().rename(columns={"receiver_player_id": "player_id", "name": "rec_name"})

        skill = pd.merge(rush_stats, rec_stats, on=["posteam", "player_id"], how="outer").fillna(0)
        skill["player_name"] = np.where(skill["rec_name"].astype(str) != "0", skill["rec_name"].astype(str), skill["rush_name"].astype(str))
        skill["player_name"] = skill.apply(lambda r: name_map.get(str(r["player_id"]), abreviar_nombre_jugador(str(r["player_name"]))), axis=1)
        skill["games_active"] = np.maximum(skill["games_rush"], skill["games_rec"]).clip(lower=1)
        skill["total_td"] = skill["rush_td"] + skill["rec_td"]
        skill["rz_touches"] = skill["rz_carries"] + skill["rz_targets"]
        skill["total_opps"] = skill["carries"] + skill["targets"]
        skill["pos"] = skill.apply(
            lambda r: ("RB" if pos_map.get(str(r["player_id"])) == "FB" else pos_map.get(str(r["player_id"])))
            if pos_map.get(str(r["player_id"])) in {"QB", "RB", "FB", "WR", "TE"}
            else ("RB" if r["carries"] > r["targets"] * 1.5 else "WR"),
            axis=1,
        )

        filas_salida = []
        for abrev, meta in NFL_TEAMS_META.items():
            tm_row = team_metrics.loc[abrev] if abrev in team_metrics.index else pd.Series(dtype=float)
            tm_td_pg = float(tds_per_game_team.get(abrev, 2.45))
            tm_skill = skill[skill["posteam"] == abrev].copy()

            tm_qbs = qb_passes[qb_passes["posteam"] == abrev].sort_values("att", ascending=False)
            if not tm_qbs.empty:
                qb_id = str(tm_qbs.iloc[0]["passer_player_id"])
                qb_games = max(1.0, float(tm_qbs.iloc[0]["games_qb"]))
                qb_name = name_map.get(qb_id, abreviar_nombre_jugador(str(tm_qbs.iloc[0]["name"])))
                qb_rush_row = tm_skill[tm_skill["player_id"] == qb_id]
                qb_r_td_pg = (float(qb_rush_row["rush_td"].sum()) / qb_games) if not qb_rush_row.empty else 0.0
                qb_rz_c_pg = (float(qb_rush_row["rz_carries"].sum()) / qb_games) if not qb_rush_row.empty else 0.0
                xtd_qb_pg = 0.65 * qb_r_td_pg + 0.35 * (qb_rz_c_pg * 0.22)
                qb_td_rate = float(np.clip(0.75 * (xtd_qb_pg / tm_td_pg) + 0.25 * 0.095, 0.035, 0.285))
            else:
                qb_name, qb_td_rate = f"{abrev} QB1", 0.085

            def elegir_playmaker(pos_target: str, prior_rate: float, min_r: float, max_r: float) -> tuple[str, float]:
                sub = tm_skill[tm_skill["pos"] == pos_target].copy()
                if sub.empty:
                    return f"{abrev} {pos_target}1", prior_rate
                sub["score_lider"] = sub["total_opps"] + sub["rz_touches"] * 3.5 + sub["total_td"] * 8.0
                top = sub.sort_values("score_lider", ascending=False).iloc[0]
                g_act = max(1.0, float(top["games_active"]))
                xtd_p = 0.62 * (float(top["total_td"]) / g_act) + 0.38 * ((float(top["rz_touches"]) / g_act) * 0.21)
                blended = 0.72 * (xtd_p / tm_td_pg) + 0.28 * prior_rate
                return str(top["player_name"]), float(np.clip(blended, min_r, max_r))

            rb1_name, rb1_rate = elegir_playmaker("RB", 0.335, 0.220, 0.460)
            wr1_name, wr1_rate = elegir_playmaker("WR", 0.295, 0.200, 0.385)
            te1_name, te1_rate = elegir_playmaker("TE", 0.195, 0.135, 0.310)

            filas_salida.append({
                "Equipo": meta["Equipo"],
                "Abrev": abrev,
                "Pass_EPA": round(float(tm_row.get("Pass_EPA", 0.020)), 3),
                "Rush_EPA": round(float(tm_row.get("Rush_EPA", -0.010)), 3),
                "Pass_Success_Rate": round(float(tm_row.get("Pass_Success_Rate", 0.475)), 3),
                "Pace_Sec": round(float(tm_row.get("Pace_Sec", 27.4)), 1),
                "RedZone_TD_Pct": round(float(tm_row.get("RedZone_TD_Pct", 0.565)), 3),
                "Def_Pass_EPA": round(float(tm_row.get("Def_Pass_EPA", 0.010)), 3),
                "Def_Rush_EPA": round(float(tm_row.get("Def_Rush_EPA", -0.015)), 3),
                "Pressure_Pct": round(float(tm_row.get("Pressure_Pct", 0.245)), 3),
                "Def_RZ_Stop_Pct": round(float(tm_row.get("Def_RZ_Stop_Pct", 0.485)), 3),
                "Dome": int(meta["Dome"]),
                "Cold_Weather_Drop": round(float(meta["Cold_Base"]), 3),
                "RB1_TD_Rate": round(rb1_rate, 3),
                "WR1_TD_Rate": round(wr1_rate, 3),
                "TE1_TD_Rate": round(te1_rate, 3),
                "QB_Rush_TD_Rate": round(qb_td_rate, 3),
                "Pass_Rate": round(float(tm_row.get("Pass_Rate", 0.565)), 3),
                "HFA_Mod": round(float(meta["HFA_Mod"]), 2),
                "QB_Nombre": qb_name,
                "RB1_Nombre": rb1_name,
                "WR1_Nombre": wr1_name,
                "TE1_Nombre": te1_name,
                "Ultimos_5": form_map.get(abrev, meta["Form"]),
            })

        df_out = pd.DataFrame(filas_salida)
        df_out.to_csv(csv_path, index=False, encoding="utf-8")
        return df_out.set_index("Equipo")

    except Exception:
        if os.path.exists(csv_path):
            df_local = pd.read_csv(csv_path)
            if "Ultimos_5" not in df_local.columns and "Abrev" in df_local.columns:
                df_local["Ultimos_5"] = df_local["Abrev"].map(
                    lambda a: NFL_TEAMS_META.get(str(a).strip(), {}).get("Form", "W-W-L-W-L")
                )
            if "Equipo" in df_local.columns:
                df_local = df_local.set_index("Equipo")
            return df_local
        raise


# ==============================================================================
# 2. CALCULADORA DE FAIR ODDS (+EV) Y UTILIDADES MATEMÁTICAS
# ==============================================================================
def prob_to_fair_odds(prob: float) -> tuple[float, str]:
    p = float(np.clip(prob, 0.005, 0.995))
    decimal_odds = round(1.0 / p, 2)
    if p >= 0.5:
        american_val = -int(round((p / (1.0 - p)) * 100.0))
        american_str = f"{american_val}"
    else:
        american_val = int(round(((1.0 - p) / p) * 100.0))
        american_str = f"+{american_val}"
    return decimal_odds, american_str


def poisson_pmf(k: int, lam: float) -> float:
    lam = max(0.05, float(lam))
    return (math.exp(-lam) * (lam ** k)) / math.factorial(k)


def poisson_over_prob(threshold: float, lam: float) -> float:
    max_k = int(math.floor(threshold))
    cdf = sum(poisson_pmf(k, lam) for k in range(max_k + 1))
    return float(np.clip(1.0 - cdf, 0.01, 0.99))


# ==============================================================================
# 3. MOTOR CUANTITATIVO SHARP NFL (EPA + 5,000 SIMS MONTECARLO + PROPS)
# ==============================================================================
NFL_REALISTIC_SCORES = {
    0: 0.35, 2: 0.05, 3: 0.65, 6: 0.72, 7: 0.85, 9: 0.60, 10: 1.15,
    12: 0.55, 13: 1.10, 14: 1.25, 15: 0.45, 16: 1.15, 17: 1.45,
    19: 0.70, 20: 1.50, 21: 1.35, 22: 0.55, 23: 1.35, 24: 1.60,
    26: 0.85, 27: 1.55, 28: 1.35, 29: 0.55, 30: 1.20, 31: 1.45,
    33: 0.75, 34: 1.25, 35: 1.10, 37: 0.85, 38: 1.05, 40: 0.60,
    41: 0.85, 42: 0.70, 44: 0.45, 45: 0.60, 48: 0.40
}

NFL_KEY_MARGIN_WEIGHTS = {
    1: 0.55, 2: 0.50, 3: 1.85, 4: 1.22, 5: 0.58, 6: 1.30, 7: 1.72,
    8: 0.92, 9: 0.55, 10: 1.45, 11: 0.62, 12: 0.52, 13: 0.88, 14: 1.40,
    15: 0.50, 16: 0.75, 17: 1.18, 18: 0.48, 19: 0.45, 20: 0.95, 21: 1.15
}


def obtener_iniciales(equipo_nombre: str, row: pd.Series) -> str:
    if "Abrev" in row and pd.notna(row["Abrev"]):
        return str(row["Abrev"]).strip()
    palabras = equipo_nombre.split()
    return "".join(p[0] for p in palabras[-2:]).upper()


def obtener_forma_equipo(abrev: str, row: pd.Series) -> str:
    if "Ultimos_5" in row and pd.notna(row["Ultimos_5"]):
        return str(row["Ultimos_5"])
    return NFL_TEAMS_META.get(abrev, {}).get("Form", "W-W-L-W-L")


def simular_partido_nfl(
    equipo_local: str,
    equipo_visita: str,
    df: pd.DataFrame,
    clima_frio_activo: bool = False,
    linea_total_mercado: float = 45.5,
    n_sims: int = 5000,
    horario_str: str = "DOM 13:00 ET",
) -> dict:
    loc = df.loc[equipo_local]
    vis = df.loc[equipo_visita]

    # --- A. RITMO Y VOLUMEN DE JUGADAS (PLAYS) ---
    pace_loc = float(loc["Pace_Sec"])
    pace_vis = float(vis["Pace_Sec"])
    pace_suma = pace_loc + pace_vis
    plays_por_equipo = 63.5 * (54.8 / max(46.0, pace_suma))
    plays_totales_juego = plays_por_equipo * 2.0

    pass_rate_loc = float(loc["Pass_Rate"]) if "Pass_Rate" in loc and pd.notna(loc["Pass_Rate"]) else 0.565
    pass_rate_vis = float(vis["Pass_Rate"]) if "Pass_Rate" in vis and pd.notna(vis["Pass_Rate"]) else 0.565

    def norm_pct(val: float) -> float:
        v = float(val)
        return v / 100.0 if v > 1.0 else v

    pass_sr_loc = norm_pct(loc["Pass_Success_Rate"])
    pass_sr_vis = norm_pct(vis["Pass_Success_Rate"])
    rz_td_loc = norm_pct(loc["RedZone_TD_Pct"])
    rz_td_vis = norm_pct(vis["RedZone_TD_Pct"])
    press_loc = norm_pct(loc["Pressure_Pct"])
    press_vis = norm_pct(vis["Pressure_Pct"])
    def_rz_stop_loc = norm_pct(loc["Def_RZ_Stop_Pct"])
    def_rz_stop_vis = norm_pct(vis["Def_RZ_Stop_Pct"])

    # --- B. FACTORES DE ENTORNO Y VENTAJAS DE LOCALÍA (HFA) ---
    es_domo = int(loc["Dome"]) == 1
    hfa_base = 1.92
    hfa_mod_estadio = float(loc["HFA_Mod"]) if "HFA_Mod" in loc and pd.notna(loc["HFA_Mod"]) else 0.18
    if es_domo:
        hfa_total = np.clip(hfa_base + hfa_mod_estadio * 0.65, 1.85, 2.25)
        dome_total_boost = 0.85
        penal_clima_loc = 0.0
        penal_clima_vis = 0.0
        entorno_tag = "🏟️ DOMO TECHADO (FAST TRACK)"
    else:
        dome_total_boost = 0.0
        hfa_total = np.clip(hfa_base + hfa_mod_estadio * 0.55, 1.80, 2.20)
        if clima_frio_activo:
            penal_clima_loc = float(loc["Cold_Weather_Drop"]) * 0.65
            mult_vis_domo = 1.35 if int(vis["Dome"]) == 1 else 1.0
            penal_clima_vis = float(vis["Cold_Weather_Drop"]) * mult_vis_domo
            hfa_total = min(2.35, hfa_total + 0.18)
            entorno_tag = "❄️ AIRE LIBRE / CLIMA ADVERSO"
        else:
            penal_clima_loc = float(loc["Cold_Weather_Drop"]) * 0.15
            penal_clima_vis = float(vis["Cold_Weather_Drop"]) * 0.20
            entorno_tag = "🌤️ AIRE LIBRE (CLIMA ESTÁNDAR)"

    # --- C. CRUCE DE EFICIENCIA EPA OFENSIVA VS DEFENSIVA Y TRINCHERAS ---
    trench_mismatch_loc = (press_vis - 0.245) * 0.45
    sr_boost_loc = (pass_sr_loc - 0.480) * 0.35
    net_pass_epa_loc = (
        float(loc["Pass_EPA"]) + float(vis["Def_Pass_EPA"])
        + sr_boost_loc - trench_mismatch_loc - penal_clima_loc
    )
    net_rush_epa_loc = float(loc["Rush_EPA"]) + float(vis["Def_Rush_EPA"])
    epa_play_loc = pass_rate_loc * net_pass_epa_loc + (1.0 - pass_rate_loc) * net_rush_epa_loc

    trench_mismatch_vis = (press_loc - 0.245) * 0.45
    sr_boost_vis = (pass_sr_vis - 0.480) * 0.35
    net_pass_epa_vis = (
        float(vis["Pass_EPA"]) + float(loc["Def_Pass_EPA"])
        + sr_boost_vis - trench_mismatch_vis - penal_clima_vis
    )
    net_rush_epa_vis = float(vis["Rush_EPA"]) + float(loc["Def_Rush_EPA"])
    epa_play_vis = pass_rate_vis * net_pass_epa_vis + (1.0 - pass_rate_vis) * net_rush_epa_vis

    # --- D. AJUSTE DE ZONA ROJA Y PUNTOS PROYECTADOS (IMPLIED TEAM TOTALS) ---
    rz_eff_loc = 0.55 * rz_td_loc + 0.45 * (1.0 - def_rz_stop_vis)
    rz_eff_vis = 0.55 * rz_td_vis + 0.45 * (1.0 - def_rz_stop_loc)
    rz_pts_adj_loc = (rz_eff_loc - 0.545) * 14.5
    rz_pts_adj_vis = (rz_eff_vis - 0.545) * 14.5

    # Ajuste leve por potencial anotador de playmakers activos (sensible a cambios en st.data_editor)
    td_talent_loc = (
        norm_pct(loc["RB1_TD_Rate"]) + norm_pct(loc["WR1_TD_Rate"])
        + norm_pct(loc["TE1_TD_Rate"]) + norm_pct(loc["QB_Rush_TD_Rate"])
    )
    td_talent_vis = (
        norm_pct(vis["RB1_TD_Rate"]) + norm_pct(vis["WR1_TD_Rate"])
        + norm_pct(vis["TE1_TD_Rate"]) + norm_pct(vis["QB_Rush_TD_Rate"])
    )
    talent_adj_loc = (td_talent_loc - 0.92) * 3.2
    talent_adj_vis = (td_talent_vis - 0.92) * 3.2

    base_pts_loc = plays_por_equipo * 0.348
    base_pts_vis = plays_por_equipo * 0.348

    pts_proj_loc = (
        base_pts_loc
        + (epa_play_loc * plays_por_equipo * 0.82)
        + rz_pts_adj_loc
        + talent_adj_loc
        + (hfa_total / 2.0)
        + dome_total_boost
    )
    pts_proj_vis = (
        base_pts_vis
        + (epa_play_vis * plays_por_equipo * 0.82)
        + rz_pts_adj_vis
        + talent_adj_vis
        - (hfa_total / 2.0)
        + dome_total_boost
    )

    pts_proj_loc = float(np.clip(pts_proj_loc, 12.5, 36.5))
    pts_proj_vis = float(np.clip(pts_proj_vis, 11.5, 35.5))

    total_proyectado = round(pts_proj_loc + pts_proj_vis, 1)
    spread_local = round(-(pts_proj_loc - pts_proj_vis), 1)

    # --- E. SIMULACIÓN MONTECARLO (5,000 ITERACIONES) + MATRIZ KEY NUMBERS ---
    seed_val = abs(hash(f"{equipo_local}_{equipo_visita}_{clima_frio_activo}_{pts_proj_loc:.2f}_{pts_proj_vis:.2f}")) % (2**31 - 1)
    rng = np.random.default_rng(seed_val)

    n_drives = int(round(11.0 * (plays_por_equipo / 63.5)))
    n_drives = max(10, min(13, n_drives))

    def simular_drives_equipo(pts_esperados: float, rz_eff: float) -> np.ndarray:
        pts_por_drive = pts_esperados / n_drives
        p_td = np.clip((pts_por_drive * (0.62 + 0.25 * (rz_eff - 0.54))) / 6.96, 0.08, 0.38)
        p_fg = np.clip((pts_por_drive - p_td * 6.96) / 3.0, 0.06, 0.26)
        p_safety = 0.004
        p_zero = max(0.10, 1.0 - (p_td + p_fg + p_safety))
        probs = np.array([p_zero, p_safety, p_fg, p_td * 0.08, p_td * 0.89, p_td * 0.03])
        probs = probs / probs.sum()
        valores_drive = np.array([0, 2, 3, 6, 7, 8])
        drives_matrix = rng.choice(valores_drive, size=(n_sims, n_drives), p=probs)
        return drives_matrix.sum(axis=1)

    scores_mc_loc = simular_drives_equipo(pts_proj_loc, rz_eff_loc)
    scores_mc_vis = simular_drives_equipo(pts_proj_vis, rz_eff_vis)

    empates_mask = scores_mc_loc == scores_mc_vis
    n_empates = int(empates_mask.sum())
    ot_rate_pct = round((n_empates / float(n_sims)) * 100.0, 1)
    if n_empates > 0:
        p_ot_loc = np.clip(0.51 + (pts_proj_loc - pts_proj_vis) * 0.015, 0.35, 0.65)
        gana_loc_ot = rng.random(n_empates) < p_ot_loc
        pts_ot = rng.choice([3, 6], size=n_empates, p=[0.68, 0.32])
        scores_mc_loc[empates_mask] += np.where(gana_loc_ot, pts_ot, 0)
        scores_mc_vis[empates_mask] += np.where(~gana_loc_ot, pts_ot, 0)

    grid_scores = sorted(list(NFL_REALISTIC_SCORES.keys()))
    sigma_team = 9.4
    cluster_candidates = []
    for s_loc in grid_scores:
        if s_loc < 6 or s_loc > 45:
            continue
        w_score_loc = NFL_REALISTIC_SCORES[s_loc]
        dens_loc = math.exp(-0.5 * ((s_loc - pts_proj_loc) / sigma_team) ** 2) * w_score_loc
        for s_vis in grid_scores:
            if s_vis < 6 or s_vis > 45 or s_loc == s_vis:
                continue
            w_score_vis = NFL_REALISTIC_SCORES[s_vis]
            dens_vis = math.exp(-0.5 * ((s_vis - pts_proj_vis) / sigma_team) ** 2) * w_score_vis
            margen = abs(s_loc - s_vis)
            w_margen = NFL_KEY_MARGIN_WEIGHTS.get(margen, 0.42)
            if (pts_proj_loc >= pts_proj_vis and s_loc > s_vis) or (pts_proj_vis > pts_proj_loc and s_vis > s_loc):
                fav_align = 1.25
            else:
                fav_align = 0.78
            joint_weight = dens_loc * dens_vis * w_margen * fav_align
            cluster_candidates.append((joint_weight, s_loc, s_vis))

    cluster_candidates.sort(key=lambda x: x[0], reverse=True)
    total_cluster_w = sum(c[0] for c in cluster_candidates)
    marcador_exacto_loc = cluster_candidates[0][1]
    marcador_exacto_vis = cluster_candidates[0][2]
    top_3_marcadores = [
        {
            "Marcador": f"{c[2]} - {c[1]}",
            "Marcador_Loc_Vis": f"{c[1]} - {c[2]}",
            "Prob": round((c[0] / total_cluster_w) * 100.0, 2),
        }
        for c in cluster_candidates[:3]
    ]

    # --- F. PROBABILIDADES DE MERCADOS PRINCIPALES Y FAIR ODDS ---
    prob_ml_loc = float(np.mean(scores_mc_loc > scores_mc_vis))
    prob_norm_loc = 0.5 * (1.0 + math.erf((pts_proj_loc - pts_proj_vis) / (13.45 * math.sqrt(2.0))))
    prob_win_loc = float(np.clip(0.55 * prob_ml_loc + 0.45 * prob_norm_loc, 0.05, 0.95))
    prob_win_vis = 1.0 - prob_win_loc

    ml_dec_loc, ml_am_loc = prob_to_fair_odds(prob_win_loc)
    ml_dec_vis, ml_am_vis = prob_to_fair_odds(prob_win_vis)

    lineas_std_nfl = [-14.0, -10.5, -10.0, -9.5, -7.5, -7.0, -6.5, -4.5, -3.5, -3.0, -2.5, -1.5, 1.5, 2.5, 3.0, 3.5, 4.5, 6.5, 7.0, 7.5, 9.5, 10.0, 10.5, 14.0]
    spread_mercado_ref = min(lineas_std_nfl, key=lambda x: abs(x - (spread_local * 0.84)))

    margen_mc = scores_mc_loc - scores_mc_vis
    no_push_mask = (margen_mc + spread_mercado_ref) != 0
    if no_push_mask.sum() > 0:
        prob_cover_mc = float(np.mean((margen_mc[no_push_mask] + spread_mercado_ref) > 0))
    else:
        prob_cover_mc = 0.50
    prob_cover_analit = 0.5 * (1.0 + math.erf(((pts_proj_loc - pts_proj_vis) + spread_mercado_ref) / (13.45 * math.sqrt(2.0))))
    prob_cover_loc = float(np.clip(0.50 * prob_cover_mc + 0.50 * prob_cover_analit, 0.08, 0.92))
    prob_cover_vis = 1.0 - prob_cover_loc

    sp_dec_loc, sp_am_loc = prob_to_fair_odds(prob_cover_loc)
    sp_dec_vis, sp_am_vis = prob_to_fair_odds(prob_cover_vis)

    total_mc = scores_mc_loc + scores_mc_vis
    prob_over_mc = float(np.mean(total_mc > linea_total_mercado))
    prob_over_analit = 0.5 * (1.0 + math.erf((total_proyectado - linea_total_mercado) / (13.8 * math.sqrt(2.0))))
    prob_over = float(np.clip(0.50 * prob_over_mc + 0.50 * prob_over_analit, 0.08, 0.92))
    prob_under = 1.0 - prob_over

    ou_dec_over, ou_am_over = prob_to_fair_odds(prob_over)
    ou_dec_under, ou_am_under = prob_to_fair_odds(prob_under)

    # Estadísticos del Desglose de Montecarlo (5,000 iteraciones)
    mc_total_p10 = round(float(np.percentile(total_mc, 10)), 1)
    mc_total_p50 = round(float(np.percentile(total_mc, 50)), 1)
    mc_total_p90 = round(float(np.percentile(total_mc, 90)), 1)
    mc_margen_medio = round(float(np.mean(margen_mc)), 1)
    mc_std_margen = round(float(np.std(margen_mc)), 1)

    # --- G. MÓDULO DE TOUCHDOWNS (POISSON / BERNOULLI Y ANYTIME TD) ---
    td_share_pts_loc = np.clip(0.68 + (rz_eff_loc - 0.52) * 0.45, 0.60, 0.84)
    td_share_pts_vis = np.clip(0.68 + (rz_eff_vis - 0.52) * 0.45, 0.60, 0.84)

    xtd_loc = round((pts_proj_loc * td_share_pts_loc) / 6.95, 2)
    xtd_vis = round((pts_proj_vis * td_share_pts_vis) / 6.95, 2)

    qb_rush_rate_loc = norm_pct(loc["QB_Rush_TD_Rate"])
    qb_rush_rate_vis = norm_pct(vis["QB_Rush_TD_Rate"])

    pass_td_ratio_loc = np.clip(pass_rate_loc + (net_pass_epa_loc - net_rush_epa_loc) * 0.25 - qb_rush_rate_loc * 0.35, 0.42, 0.76)
    pass_td_ratio_vis = np.clip(pass_rate_vis + (net_pass_epa_vis - net_rush_epa_vis) * 0.25 - qb_rush_rate_vis * 0.35, 0.42, 0.76)

    xtd_pass_loc = round(xtd_loc * pass_td_ratio_loc, 2)
    xtd_rush_loc = round(xtd_loc * (1.0 - pass_td_ratio_loc), 2)
    xtd_pass_vis = round(xtd_vis * pass_td_ratio_vis, 2)
    xtd_rush_vis = round(xtd_vis * (1.0 - pass_td_ratio_vis), 2)

    prob_o25_td_loc = poisson_over_prob(2.5, xtd_loc)
    prob_u25_td_loc = 1.0 - prob_o25_td_loc
    prob_o25_td_vis = poisson_over_prob(2.5, xtd_vis)
    prob_u25_td_vis = 1.0 - prob_o25_td_vis

    def calcular_props_equipo(row: pd.Series, xtd_team: float, equipo_str: str, abrev_str: str) -> list[dict]:
        roles = [
            ("RB1", "RB1_TD_Rate", "RB1_Nombre", "RB1"),
            ("WR1", "WR1_TD_Rate", "WR1_Nombre", "WR1"),
            ("TE1", "TE1_TD_Rate", "TE1_Nombre", "TE1"),
            ("QB RUSH", "QB_Rush_TD_Rate", "QB_Nombre", "QB"),
        ]
        props_out = []
        for rol_label, col_rate, col_nombre, default_tag in roles:
            td_rate = norm_pct(row[col_rate])
            nombre_jug = str(row[col_nombre]) if col_nombre in row and pd.notna(row[col_nombre]) else f"{abrev_str} {default_tag}"
            lam_player = max(0.04, xtd_team * td_rate)
            prob_atd = float(np.clip(1.0 - math.exp(-lam_player), 0.04, 0.88))
            dec_odd, am_odd = prob_to_fair_odds(prob_atd)
            props_out.append({
                "Equipo": equipo_str,
                "Abrev": abrev_str,
                "Rol": rol_label,
                "Jugador": nombre_jug,
                "TD_Rate_Pct": round(td_rate * 100.0, 1),
                "xTD": round(lam_player, 2),
                "Prob": round(prob_atd * 100.0, 1),
                "Prob_Raw": prob_atd,
                "Fair_Dec": dec_odd,
                "Fair_Am": am_odd,
            })
        return props_out

    abrev_loc = obtener_iniciales(equipo_local, loc)
    abrev_vis = obtener_iniciales(equipo_visita, vis)

    logo_loc = obtener_logo_url(abrev_loc)
    logo_vis = obtener_logo_url(abrev_vis)

    form_loc = obtener_forma_equipo(abrev_loc, loc)
    form_vis = obtener_forma_equipo(abrev_vis, vis)

    props_loc = calcular_props_equipo(loc, xtd_loc, equipo_local, abrev_loc)
    props_vis = calcular_props_equipo(vis, xtd_vis, equipo_visita, abrev_vis)

    key_numbers_check = [3, 7, 10, 14, 6, 4]
    key_margins_dist = {}
    margen_abs = np.abs(margen_mc)
    for kn in key_numbers_check:
        mc_freq = float(np.mean(margen_abs == kn)) * 100.0
        key_margins_dist[f"Margen {kn} pts"] = round(max(2.5, mc_freq * 1.15), 1)

    return {
        "Local": equipo_local,
        "Visita": equipo_visita,
        "Abrev_Loc": abrev_loc,
        "Abrev_Vis": abrev_vis,
        "Logo_Loc": logo_loc,
        "Logo_Vis": logo_vis,
        "Form_Loc": form_loc,
        "Form_Vis": form_vis,
        "Horario": horario_str,
        "N_Sims": n_sims,
        "Entorno_Tag": entorno_tag,
        "Es_Domo": es_domo,
        "HFA_Pts": round(hfa_total, 2),
        "Plays_Por_Equipo": round(plays_por_equipo, 1),
        "Plays_Totales": round(plays_totales_juego, 1),
        "Pace_Suma": round(pace_suma, 1),
        "EPA_Play_Loc": round(epa_play_loc, 3),
        "EPA_Play_Vis": round(epa_play_vis, 3),
        "Net_Pass_EPA_Loc": round(net_pass_epa_loc, 3),
        "Net_Pass_EPA_Vis": round(net_pass_epa_vis, 3),
        "Net_Rush_EPA_Loc": round(net_rush_epa_loc, 3),
        "Net_Rush_EPA_Vis": round(net_rush_epa_vis, 3),
        "Press_Loc": round(press_loc * 100.0, 1),
        "Press_Vis": round(press_vis * 100.0, 1),
        "RZ_Eff_Loc": round(rz_eff_loc * 100.0, 1),
        "RZ_Eff_Vis": round(rz_eff_vis * 100.0, 1),
        "Pts_Loc": round(pts_proj_loc, 1),
        "Pts_Vis": round(pts_proj_vis, 1),
        "Total_Proyectado": total_proyectado,
        "Linea_Total_Mercado": linea_total_mercado,
        "Spread_Justo_Loc": spread_local,
        "Spread_Mercado_Ref": spread_mercado_ref,
        "Marcador_Exacto": f"{marcador_exacto_loc} - {marcador_exacto_vis}",
        "Marcador_Loc": marcador_exacto_loc,
        "Marcador_Vis": marcador_exacto_vis,
        "Top_3_Marcadores": top_3_marcadores,
        "Prob_Win_Loc": round(prob_win_loc * 100.0, 1),
        "Prob_Win_Vis": round(prob_win_vis * 100.0, 1),
        "ML_Dec_Loc": ml_dec_loc,
        "ML_Am_Loc": ml_am_loc,
        "ML_Dec_Vis": ml_dec_vis,
        "ML_Am_Vis": ml_am_vis,
        "Prob_Cover_Loc": round(prob_cover_loc * 100.0, 1),
        "Prob_Cover_Vis": round(prob_cover_vis * 100.0, 1),
        "SP_Dec_Loc": sp_dec_loc,
        "SP_Am_Loc": sp_am_loc,
        "SP_Dec_Vis": sp_dec_vis,
        "SP_Am_Vis": sp_am_vis,
        "Prob_Over": round(prob_over * 100.0, 1),
        "Prob_Under": round(prob_under * 100.0, 1),
        "OU_Dec_Over": ou_dec_over,
        "OU_Am_Over": ou_am_over,
        "OU_Dec_Under": ou_dec_under,
        "OU_Am_Under": ou_am_under,
        "MC_Total_P10": mc_total_p10,
        "MC_Total_P50": mc_total_p50,
        "MC_Total_P90": mc_total_p90,
        "MC_Margen_Medio": mc_margen_medio,
        "MC_Std_Margen": mc_std_margen,
        "MC_OT_Pct": ot_rate_pct,
        "xTD_Loc": xtd_loc,
        "xTD_Vis": xtd_vis,
        "xTD_Pass_Loc": xtd_pass_loc,
        "xTD_Rush_Loc": xtd_rush_loc,
        "xTD_Pass_Vis": xtd_pass_vis,
        "xTD_Rush_Vis": xtd_rush_vis,
        "Prob_O25_TD_Loc": round(prob_o25_td_loc * 100.0, 1),
        "Prob_U25_TD_Loc": round(prob_u25_td_loc * 100.0, 1),
        "O25_TD_Loc_Dec": prob_to_fair_odds(prob_o25_td_loc)[0],
        "O25_TD_Loc_Am": prob_to_fair_odds(prob_o25_td_loc)[1],
        "U25_TD_Loc_Dec": prob_to_fair_odds(prob_u25_td_loc)[0],
        "U25_TD_Loc_Am": prob_to_fair_odds(prob_u25_td_loc)[1],
        "Prob_O25_TD_Vis": round(prob_o25_td_vis * 100.0, 1),
        "Prob_U25_TD_Vis": round(prob_u25_td_vis * 100.0, 1),
        "O25_TD_Vis_Dec": prob_to_fair_odds(prob_o25_td_vis)[0],
        "O25_TD_Vis_Am": prob_to_fair_odds(prob_o25_td_vis)[1],
        "U25_TD_Vis_Dec": prob_to_fair_odds(prob_u25_td_vis)[0],
        "U25_TD_Vis_Am": prob_to_fair_odds(prob_u25_td_vis)[1],
        "Props_Loc": props_loc,
        "Props_Vis": props_vis,
        "Key_Margins_Dist": key_margins_dist,
    }


# ==============================================================================
# 4. GESTIÓN DE SESSION STATE, NAVEGACIÓN Y CARGA DE DATOS 2026
# ==============================================================================
with st.spinner("⚡ Descargando Parquet oficial nflverse 2026 (<3s)..."):
    df_nfl_base = sincronizar_nflverse_2026(season=SEASON_DEFAULT, csv_path="nfl_stats_completo.csv")

if "df_nfl_activo" not in st.session_state:
    st.session_state.df_nfl_activo = df_nfl_base.copy()

df_nfl = st.session_state.df_nfl_activo
lista_equipos = list(df_nfl.index)

DEFAULT_16_MATCHUPS = [
    ("Kansas City Chiefs", "Baltimore Ravens"),
    ("San Francisco 49ers", "Detroit Lions"),
    ("Buffalo Bills", "Miami Dolphins"),
    ("Philadelphia Eagles", "Dallas Cowboys"),
    ("Cincinnati Bengals", "New England Patriots"),
    ("Houston Texans", "Indianapolis Colts"),
    ("Green Bay Packers", "Chicago Bears"),
    ("Los Angeles Rams", "Seattle Seahawks"),
    ("Minnesota Vikings", "New York Giants"),
    ("New York Jets", "Cleveland Browns"),
    ("Pittsburgh Steelers", "Atlanta Falcons"),
    ("Tampa Bay Buccaneers", "Washington Commanders"),
    ("Jacksonville Jaguars", "Tennessee Titans"),
    ("Los Angeles Chargers", "Las Vegas Raiders"),
    ("New Orleans Saints", "Carolina Panthers"),
    ("Denver Broncos", "Arizona Cardinals"),
]

if "vista_actual" not in st.session_state:
    st.session_state.vista_actual = "cartelera"  # "cartelera" | "detalle"

if "partido_seleccionado_idx" not in st.session_state:
    st.session_state.partido_seleccionado_idx = 0

if "semana_nfl_label" not in st.session_state:
    st.session_state.semana_nfl_label = "NFL · SEMANA 8"

if "expander_open" not in st.session_state:
    st.session_state.expander_open = False

if "num_juegos_activos" not in st.session_state:
    # Por defecto 9 juegos para desplegar la cuadrícula 3x3 de cartelera deportiva
    st.session_state.num_juegos_activos = min(9, max(1, len(lista_equipos) // 2))

if "clima_invierno" not in st.session_state:
    st.session_state.clima_invierno = False

if "linea_mercado_base" not in st.session_state:
    st.session_state.linea_mercado_base = 45.5

if "n_simulaciones_mc" not in st.session_state:
    st.session_state.n_simulaciones_mc = 5000

if "partidos_seleccionados" not in st.session_state:
    partidos_init = []
    for idx in range(16):
        loc_def, vis_def = DEFAULT_16_MATCHUPS[idx % len(DEFAULT_16_MATCHUPS)]
        if loc_def not in lista_equipos:
            loc_def = lista_equipos[idx % len(lista_equipos)]
        if vis_def not in lista_equipos or vis_def == loc_def:
            vis_def = lista_equipos[(idx + 1) % len(lista_equipos)]
        partidos_init.append(
            {
                "local": loc_def,
                "visita": vis_def,
                "horario": HORARIOS_CARTELERA[idx % len(HORARIOS_CARTELERA)],
            }
        )
    st.session_state.partidos_seleccionados = partidos_init


def ir_a_detalle_partido(idx_partido: int):
    st.session_state.partido_seleccionado_idx = idx_partido
    st.session_state.vista_actual = "detalle"


def volver_a_cartelera():
    st.session_state.vista_actual = "cartelera"


# ==============================================================================
# 5. BARRA LATERAL: CONTROLES DEL SINDICATO + EDITOR RÁPIDO DE ROSTERS
# ==============================================================================
ROSTER_COLS_EDIT = [
    "Abrev",
    "QB_Nombre",
    "QB_Rush_TD_Rate",
    "RB1_Nombre",
    "RB1_TD_Rate",
    "WR1_Nombre",
    "WR1_TD_Rate",
    "TE1_Nombre",
    "TE1_TD_Rate",
]

with st.sidebar:
    st.markdown(
        """
        <div style='font-family: Orbitron, sans-serif; font-size: 1.05rem; font-weight: 800; color: #00F0FF; letter-spacing: 1px;'>
            ⚡ SHARP SYNDICATE TERMINAL
        </div>
        <div style='font-family: JetBrains Mono, monospace; font-size: 0.73rem; color: #8A99AD; margin-bottom: 12px;'>
            CARTELERA 3x3 • DRILL-DOWN • ROSTER LIVE
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.vista_actual == "detalle":
        st.button(
            "← Volver a la Cartelera (Grid 3x3)",
            on_click=volver_a_cartelera,
            use_container_width=True,
        )

    st.session_state.semana_nfl_label = st.selectbox(
        "🗓️ Etiqueta de Jornada Activa",
        options=[f"NFL · SEMANA {w}" for w in range(1, 19)] + ["NFL · WILD CARD", "NFL · DIVISIONAL", "NFL · SUPER BOWL"],
        index=7,
    )

    if st.button("🎛️ Configurar Cruces de la Semana", use_container_width=True):
        st.session_state.expander_open = not st.session_state.expander_open
        st.session_state.vista_actual = "cartelera"

    if st.button("🔄 Resincronizar Parquet 2026 (nflverse)", use_container_width=True):
        sincronizar_nflverse_2026.clear()
        st.session_state.df_nfl_activo = sincronizar_nflverse_2026(
            season=SEASON_DEFAULT, csv_path="nfl_stats_completo.csv"
        ).copy()
        st.rerun()

    st.markdown("### 🏥 Ajuste Rápido por Lesión (Sidebar)")
    equipo_sidebar_sel = st.selectbox(
        "Seleccionar Franquicia a Ajustar",
        options=lista_equipos,
        index=0,
    )
    row_sb = st.session_state.df_nfl_activo.loc[equipo_sidebar_sel]

    with st.form("form_roster_sidebar"):
        st.caption(f"Titulares activos y TD_Rate — **{equipo_sidebar_sel}**")
        c_sb1, c_sb2 = st.columns([1.3, 1.0])
        with c_sb1:
            qb_n_sb = st.text_input("QB1", value=str(row_sb["QB_Nombre"]))
            rb_n_sb = st.text_input("RB1", value=str(row_sb["RB1_Nombre"]))
            wr_n_sb = st.text_input("WR1", value=str(row_sb["WR1_Nombre"]))
            te_n_sb = st.text_input("TE1", value=str(row_sb["TE1_Nombre"]))
        with c_sb2:
            qb_r_sb = st.number_input(
                "QB TD Rate", min_value=0.01, max_value=0.60, value=float(row_sb["QB_Rush_TD_Rate"]), step=0.01, format="%.3f"
            )
            rb_r_sb = st.number_input(
                "RB1 TD Rate", min_value=0.05, max_value=0.75, value=float(row_sb["RB1_TD_Rate"]), step=0.01, format="%.3f"
            )
            wr_r_sb = st.number_input(
                "WR1 TD Rate", min_value=0.05, max_value=0.70, value=float(row_sb["WR1_TD_Rate"]), step=0.01, format="%.3f"
            )
            te_r_sb = st.number_input(
                "TE1 TD Rate", min_value=0.03, max_value=0.60, value=float(row_sb["TE1_TD_Rate"]), step=0.01, format="%.3f"
            )
        guardar_sb = st.form_submit_button("💾 Aplicar Ajuste al Modelo", use_container_width=True)
        if guardar_sb:
            st.session_state.df_nfl_activo.loc[equipo_sidebar_sel, "QB_Nombre"] = qb_n_sb
            st.session_state.df_nfl_activo.loc[equipo_sidebar_sel, "QB_Rush_TD_Rate"] = round(float(qb_r_sb), 3)
            st.session_state.df_nfl_activo.loc[equipo_sidebar_sel, "RB1_Nombre"] = rb_n_sb
            st.session_state.df_nfl_activo.loc[equipo_sidebar_sel, "RB1_TD_Rate"] = round(float(rb_r_sb), 3)
            st.session_state.df_nfl_activo.loc[equipo_sidebar_sel, "WR1_Nombre"] = wr_n_sb
            st.session_state.df_nfl_activo.loc[equipo_sidebar_sel, "WR1_TD_Rate"] = round(float(wr_r_sb), 3)
            st.session_state.df_nfl_activo.loc[equipo_sidebar_sel, "TE1_Nombre"] = te_n_sb
            st.session_state.df_nfl_activo.loc[equipo_sidebar_sel, "TE1_TD_Rate"] = round(float(te_r_sb), 3)
            st.session_state.df_nfl_activo.reset_index().to_csv("nfl_stats_completo.csv", index=False, encoding="utf-8")
            st.success(f"Roster de {equipo_sidebar_sel} actualizado.")
            st.rerun()

    st.download_button(
        label="⬇️ Exportar nfl_stats_completo.csv",
        data=st.session_state.df_nfl_activo.reset_index().to_csv(index=False).encode("utf-8"),
        file_name="nfl_stats_completo.csv",
        mime="text/csv",
        use_container_width=True,
    )


# ==============================================================================
# 6. ENCABEZADO DE LA TERMINAL Y PANEL INTERACTIVO DE ROSTER (st.data_editor)
# ==============================================================================
df_nfl = st.session_state.df_nfl_activo

st.markdown(
    f"""
    <div class="terminal-banner">
        <div class="terminal-title">
            <span>🏈 TERMINAL SHARP: NFL QUANT SCANNER</span>
            <span class="live-pill">● {st.session_state.semana_nfl_label} // PARQUET 2026</span>
        </div>
        <div class="terminal-subtitle">
            DASHBOARD INTERACTIVO DE CARTELERA (GRID 3x3) • DRILL-DOWN CUANTITATIVO • 5,000 SIMS MONTECARLO • LOGOS OFICIALES ESPN • ROSTER EDITOR LIVE
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Panel global con st.data_editor para editar todos los titulares y TD_Rate en vivo
with st.expander("🛠️ PANEL DE AJUSTE DE ROSTER Y TD_RATE EN VIVO (st.data_editor — Lesiones de Última Hora)", expanded=False):
    st.markdown(
        "Modifica directamente en la tabla el **nombre del jugador titular** (`QB_Nombre`, `RB1_Nombre`, `WR1_Nombre`, `TE1_Nombre`) "
        "o su **tasa esperada de anotación (`TD_Rate`)** antes de correr las simulaciones. Los cambios actualizan al instante la cartelera y las props."
    )
    df_roster_vista = df_nfl[ROSTER_COLS_EDIT].copy()
    df_roster_editado = st.data_editor(
        df_roster_vista,
        use_container_width=True,
        num_rows="fixed",
        key=" roster_data_editor_main",
        column_config={
            "Abrev": st.column_config.TextColumn("Abrev", disabled=True, width="small"),
            "QB_Nombre": st.column_config.TextColumn("QB Titular", help="Modificar si hay cambio de QB por lesión"),
            "QB_Rush_TD_Rate": st.column_config.NumberColumn(
                "QB Rush TD Rate", min_value=0.010, max_value=0.600, step=0.005, format="%.3f"
            ),
            "RB1_Nombre": st.column_config.TextColumn("RB1 Titular", help="Corredor principal en Zona Roja"),
            "RB1_TD_Rate": st.column_config.NumberColumn(
                "RB1 TD Rate", min_value=0.050, max_value=0.750, step=0.005, format="%.3f"
            ),
            "WR1_Nombre": st.column_config.TextColumn("WR1 Titular", help="Receptor #1"),
            "WR1_TD_Rate": st.column_config.NumberColumn(
                "WR1 TD Rate", min_value=0.050, max_value=0.700, step=0.005, format="%.3f"
            ),
            "TE1_Nombre": st.column_config.TextColumn("TE1 Titular", help="Ala cerrada #1"),
            "TE1_TD_Rate": st.column_config.NumberColumn(
                "TE1 TD Rate", min_value=0.030, max_value=0.600, step=0.005, format="%.3f"
            ),
        },
    )

    col_ed1, col_ed2 = st.columns([1.5, 1.0])
    with col_ed1:
        if st.button("⚡ Aplicar Cambios de Roster y Recalcular Simulaciones", use_container_width=True):
            for col_r in ROSTER_COLS_EDIT:
                if col_r != "Abrev":
                    st.session_state.df_nfl_activo[col_r] = df_roster_editado[col_r]
            st.session_state.df_nfl_activo.reset_index().to_csv("nfl_stats_completo.csv", index=False, encoding="utf-8")
            st.success("Roster y TD_Rates actualizados en el motor cuantitativo.")
            st.rerun()
    with col_ed2:
        if st.button("↩️ Restaurar Rosters Oficiales nflverse 2026", use_container_width=True):
            st.session_state.df_nfl_activo = df_nfl_base.copy()
            st.rerun()


# ==============================================================================
# 7. CONFIGURADOR DE LOS PARTIDOS DE LA JORNADA (st.form + st.expander)
# ==============================================================================
def callback_cerrar_expander():
    st.session_state.expander_open = False
    st.session_state.vista_actual = "cartelera"


with st.expander(
    "🎛️ CONFIGURADOR DE PARTIDOS DE LA JORNADA (CARTELERA HASTA 16 JUEGOS NFL)",
    expanded=st.session_state.expander_open,
):
    with st.form("form_semana_nfl"):
        col_cfg1, col_cfg2, col_cfg3, col_cfg4 = st.columns([1.1, 1.1, 1.1, 1.3])
        with col_cfg1:
            num_juegos = st.slider(
                "Partidos en Cartelera (9 = Grid 3x3)",
                min_value=1,
                max_value=16,
                value=st.session_state.num_juegos_activos,
                step=1,
            )
        with col_cfg2:
            linea_total_ref = st.select_slider(
                "Línea Mercado Over/Under (Pts)",
                options=[43.5, 44.0, 44.5, 45.0, 45.5, 46.0, 46.5, 47.0, 47.5],
                value=st.session_state.linea_mercado_base,
            )
        with col_cfg3:
            n_sims_cfg = st.select_slider(
                "Simulaciones Montecarlo",
                options=[5000, 7500, 10000],
                value=st.session_state.n_simulaciones_mc,
            )
        with col_cfg4:
            clima_frio = st.checkbox(
                "❄️ Activar Clima Invernal / Viento (Cold Weather Drop)",
                value=st.session_state.clima_invierno,
            )

        st.markdown("##### Selección de Cruces (Visita @ Local — 16 Slots Disponibles)")
        nuevos_partidos = []
        for row_idx in range(4):
            cols_games = st.columns(4)
            for col_idx in range(4):
                game_i = row_idx * 4 + col_idx
                with cols_games[col_idx]:
                    activo_tag = "🟢" if game_i < num_juegos else "⚪"
                    st.markdown(f"**{activo_tag} Juego #{game_i + 1}**")
                    default_vis = st.session_state.partidos_seleccionados[game_i]["visita"]
                    default_loc = st.session_state.partidos_seleccionados[game_i]["local"]
                    default_hor = st.session_state.partidos_seleccionados[game_i].get(
                        "horario", HORARIOS_CARTELERA[game_i % len(HORARIOS_CARTELERA)]
                    )
                    idx_vis = lista_equipos.index(default_vis) if default_vis in lista_equipos else 0
                    idx_loc = lista_equipos.index(default_loc) if default_loc in lista_equipos else min(1, len(lista_equipos) - 1)
                    vis_sel = st.selectbox(
                        f"Visita #{game_i + 1}",
                        options=lista_equipos,
                        index=idx_vis,
                        key=f"vis_select_{game_i}",
                    )
                    loc_sel = st.selectbox(
                        f"Local #{game_i + 1}",
                        options=lista_equipos,
                        index=idx_loc,
                        key=f"loc_select_{game_i}",
                    )
                    nuevos_partidos.append({"local": loc_sel, "visita": vis_sel, "horario": default_hor})

        submitted = st.form_submit_button(
            "🚀 ACTUALIZAR CARTELERA Y CORRER 5,000 SIMULACIONES MONTECARLO",
            use_container_width=True,
            on_click=callback_cerrar_expander,
        )

        if submitted:
            st.session_state.num_juegos_activos = num_juegos
            st.session_state.linea_mercado_base = linea_total_ref
            st.session_state.n_simulaciones_mc = n_sims_cfg
            st.session_state.clima_invierno = clima_frio
            st.session_state.partidos_seleccionados = nuevos_partidos


# ==============================================================================
# 8. VALIDACIÓN DE ERRORES Y SIMULACIÓN DE TODOS LOS PARTIDOS ACTIVOS
# ==============================================================================
juegos_a_procesar = st.session_state.partidos_seleccionados[: st.session_state.num_juegos_activos]
errores_mismo_equipo = []
partidos_validos = []

for idx, p in enumerate(juegos_a_procesar):
    if p["local"] == p["visita"]:
        errores_mismo_equipo.append(
            f"⚠️ Error en Juego #{idx + 1}: **{p['local']}** no puede jugar contra sí mismo. Selecciona un rival distinto."
        )
    else:
        partidos_validos.append(
            (
                idx + 1,
                p["local"],
                p["visita"],
                p.get("horario", HORARIOS_CARTELERA[idx % len(HORARIOS_CARTELERA)]),
            )
        )

if errores_mismo_equipo:
    for err_msg in errores_mismo_equipo:
        st.error(err_msg)

if not partidos_validos:
    st.warning("Configura al menos un partido válido (Local ≠ Visita) para visualizar la cartelera.")
    st.stop()

resultados_semana = [
    simular_partido_nfl(
        equipo_local=loc_team,
        equipo_visita=vis_team,
        df=st.session_state.df_nfl_activo,
        clima_frio_activo=st.session_state.clima_invierno,
        linea_total_mercado=st.session_state.linea_mercado_base,
        n_sims=st.session_state.n_simulaciones_mc,
        horario_str=hor_str,
    )
    for _, loc_team, vis_team, hor_str in partidos_validos
]


# ==============================================================================
# 9. CÁLCULO DEL RADAR EJECUTIVO DE LA SEMANA (TOP 4 PICKS DEL SINDICATO)
# ==============================================================================
mejor_lock = None
mejor_lock_score = -1.0
for r in resultados_semana:
    if r["Prob_Win_Loc"] >= r["Prob_Win_Vis"]:
        score_cand = 0.60 * r["Prob_Win_Loc"] + 0.40 * r["Prob_Cover_Loc"]
        cand = {
            "Equipo": r["Local"],
            "Logo": r["Logo_Loc"],
            "Rival": r["Visita"],
            "Prob_ML": r["Prob_Win_Loc"],
            "Fair_Dec": r["ML_Dec_Loc"],
            "Fair_Am": r["ML_Am_Loc"],
            "Spread_Proj": f"{r['Spread_Justo_Loc']:+.1f}",
        }
    else:
        score_cand = 0.60 * r["Prob_Win_Vis"] + 0.40 * r["Prob_Cover_Vis"]
        cand = {
            "Equipo": r["Visita"],
            "Logo": r["Logo_Vis"],
            "Rival": r["Local"],
            "Prob_ML": r["Prob_Win_Vis"],
            "Fair_Dec": r["ML_Dec_Vis"],
            "Fair_Am": r["ML_Am_Vis"],
            "Spread_Proj": f"{-r['Spread_Justo_Loc']:+.1f}",
        }
    if score_cand > mejor_lock_score:
        mejor_lock_score = score_cand
        mejor_lock = cand

mejor_total = None
mejor_total_edge = -1.0
for r in resultados_semana:
    linea_comp = float(np.clip(r["Linea_Total_Mercado"], 43.5, 47.5))
    diff_pts = r["Total_Proyectado"] - linea_comp
    edge_abs = abs(diff_pts)
    if edge_abs > mejor_total_edge:
        mejor_total_edge = edge_abs
        es_over = diff_pts >= 0
        prob_sel = r["Prob_Over"] if es_over else r["Prob_Under"]
        dec_sel = r["OU_Dec_Over"] if es_over else r["OU_Dec_Under"]
        am_sel = r["OU_Am_Over"] if es_over else r["OU_Am_Under"]
        mejor_total = {
            "Partido": f"{r['Abrev_Vis']} @ {r['Abrev_Loc']}",
            "Logo": r["Logo_Loc"],
            "Pick": f"{'OVER' if es_over else 'UNDER'} {linea_comp:.1f}",
            "Proyectado": r["Total_Proyectado"],
            "Edge_Pts": round(edge_abs, 1),
            "Prob": prob_sel,
            "Fair_Dec": dec_sel,
            "Fair_Am": am_sel,
        }

todos_los_props = []
for r in resultados_semana:
    for p_item in r["Props_Loc"] + r["Props_Vis"]:
        p_copy = dict(p_item)
        p_copy["Matchup"] = f"{r['Abrev_Vis']} @ {r['Abrev_Loc']}"
        p_copy["Logo"] = obtener_logo_url(p_item["Abrev"])
        todos_los_props.append(p_copy)
anotador_estrella = max(todos_los_props, key=lambda x: x["Prob_Raw"])

mejor_underdog = None
mejor_dog_prob = -1.0
for r in resultados_semana:
    if r["Spread_Mercado_Ref"] < 0:
        dog_team = r["Visita"]
        dog_logo = r["Logo_Vis"]
        dog_line = abs(r["Spread_Mercado_Ref"])
        dog_cover_prob = r["Prob_Cover_Vis"]
        dog_fair_spread = -r["Spread_Justo_Loc"]
        dog_dec = r["SP_Dec_Vis"]
        dog_am = r["SP_Am_Vis"]
        match_str = f"{r['Abrev_Vis']} @ {r['Abrev_Loc']}"
    else:
        dog_team = r["Local"]
        dog_logo = r["Logo_Loc"]
        dog_line = abs(r["Spread_Mercado_Ref"])
        dog_cover_prob = r["Prob_Cover_Loc"]
        dog_fair_spread = r["Spread_Justo_Loc"]
        dog_dec = r["SP_Dec_Loc"]
        dog_am = r["SP_Am_Loc"]
        match_str = f"{r['Abrev_Vis']} @ {r['Abrev_Loc']}"

    if dog_cover_prob > mejor_dog_prob:
        mejor_dog_prob = dog_cover_prob
        mejor_underdog = {
            "Equipo": dog_team,
            "Logo": dog_logo,
            "Matchup": match_str,
            "Linea_Dog": f"+{dog_line:.1f}",
            "Spread_Modelo": f"{dog_fair_spread:+.1f}",
            "Prob_Cover": dog_cover_prob,
            "Fair_Dec": dog_dec,
            "Fair_Am": dog_am,
        }


# ==============================================================================
# 10. ENRUTADOR DE VISTAS: CARTELERA 3x3 vs VISTA DETALLADA (DRILL-DOWN)
# ==============================================================================
if st.session_state.vista_actual == "cartelera":
    # --- A. RADAR EJECUTIVO DE LA SEMANA ---
    st.markdown(
        '<div class="radar-section-title"><span>📡 RADAR EJECUTIVO DE LA SEMANA // TOP SYNDICATE EDGES</span></div>',
        unsafe_allow_html=True,
    )
    r_col1, r_col2, r_col3, r_col4 = st.columns(4)

    with r_col1:
        st.markdown(
            f"""
            <div class="radar-card lock">
                <div class="radar-tag">🔒 EL LOCK DE LA SEMANA</div>
                <div class="radar-pick">
                    <img src="{mejor_lock['Logo']}" width="26" height="26" style="object-fit:contain;" onerror="this.style.display='none'">
                    <span>{mejor_lock['Equipo']}</span>
                </div>
                <div class="radar-metrics">Win Prob: {mejor_lock['Prob_ML']}% | Fair: {mejor_lock['Fair_Dec']} ({mejor_lock['Fair_Am']})</div>
                <div class="radar-sub">Spread Modelo: {mejor_lock['Spread_Proj']} vs {mejor_lock['Rival']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with r_col2:
        st.markdown(
            f"""
            <div class="radar-card total">
                <div class="radar-tag">⚡ LA FIJA DE PUNTOS</div>
                <div class="radar-pick">
                    <img src="{mejor_total['Logo']}" width="26" height="26" style="object-fit:contain;" onerror="this.style.display='none'">
                    <span>{mejor_total['Partido']}: {mejor_total['Pick']}</span>
                </div>
                <div class="radar-metrics">Proy: {mejor_total['Proyectado']} pts (Edge +{mejor_total['Edge_Pts']} pts)</div>
                <div class="radar-sub">Prob: {mejor_total['Prob']}% | Fair: {mejor_total['Fair_Dec']} ({mejor_total['Fair_Am']})</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with r_col3:
        st.markdown(
            f"""
            <div class="radar-card star">
                <div class="radar-tag">🎯 EL ANOTADOR ESTRELLA</div>
                <div class="radar-pick">
                    <img src="{anotador_estrella['Logo']}" width="26" height="26" style="object-fit:contain;" onerror="this.style.display='none'">
                    <span>{anotador_estrella['Jugador']} ({anotador_estrella['Abrev']} - {anotador_estrella['Rol']})</span>
                </div>
                <div class="radar-metrics">Anytime TD: {anotador_estrella['Prob']}% | xTD: {anotador_estrella['xTD']}</div>
                <div class="radar-sub">Momio Justo: {anotador_estrella['Fair_Dec']} ({anotador_estrella['Fair_Am']}) • {anotador_estrella['Matchup']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with r_col4:
        st.markdown(
            f"""
            <div class="radar-card dog">
                <div class="radar-tag">🛡️ EL PERRO CON VALOR</div>
                <div class="radar-pick">
                    <img src="{mejor_underdog['Logo']}" width="26" height="26" style="object-fit:contain;" onerror="this.style.display='none'">
                    <span>{mejor_underdog['Equipo']} ({mejor_underdog['Linea_Dog']})</span>
                </div>
                <div class="radar-metrics">Cobertura: {mejor_underdog['Prob_Cover']}% | Fair: {mejor_underdog['Fair_Dec']} ({mejor_underdog['Fair_Am']})</div>
                <div class="radar-sub">Línea Justa Modelo: {mejor_underdog['Spread_Modelo']} • {mejor_underdog['Matchup']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # --- B. CARTELERA INTERACTIVA EN CUADRÍCULA 3x3 (GLASSMORPHISM) ---
    st.markdown(
        f"""
        <div class="radar-section-title">
            <span>🏟️ CARTELERA INTERACTIVA DE LA JORNADA // {st.session_state.semana_nfl_label} (GRID 3x3)</span>
            <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.76rem; color: #8A99AD;">
                Haz clic en "LEER ANÁLISIS →" para abrir el desglose cuantitativo completo
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Renderizar tarjetas en filas de 3 columnas (3x3 Grid)
    for start_idx in range(0, len(resultados_semana), 3):
        cols_grid = st.columns(3)
        chunk = resultados_semana[start_idx : start_idx + 3]
        for col_offset, res in enumerate(chunk):
            game_idx = start_idx + col_offset
            with cols_grid[col_offset]:
                wl_vis_html = renderizar_pastillas_wl(res["Form_Vis"])
                wl_loc_html = renderizar_pastillas_wl(res["Form_Loc"])
                domo_badge = "🏟️ Domo" if res["Es_Domo"] else "🌤️ Aire Libre"
                spread_fav_tag = (
                    f"{res['Abrev_Loc']} {res['Spread_Justo_Loc']:+.1f}"
                    if res["Spread_Justo_Loc"] <= 0
                    else f"{res['Abrev_Vis']} {-res['Spread_Justo_Loc']:+.1f}"
                )

                st.markdown(
                    f"""
                    <div class="billboard-card">
                        <div class="billboard-header">
                            <span class="league-week-pill">{st.session_state.semana_nfl_label}</span>
                            <span class="kickoff-time">🕒 {res['Horario']} • {domo_badge}</span>
                        </div>
                        <div class="billboard-team-row">
                            <div class="billboard-team-left">
                                <img src="{res['Logo_Vis']}" class="team-logo-card" alt="{res['Abrev_Vis']}" onerror="this.style.display='none'">
                                <div>
                                    <div class="team-name-card">{res['Visita']}</div>
                                    <div class="team-sub-card">{res['Abrev_Vis']} (Visita) • Win {res['Prob_Win_Vis']}% ({res['ML_Am_Vis']})</div>
                                </div>
                            </div>
                            {wl_vis_html}
                        </div>
                        <div class="billboard-team-row">
                            <div class="billboard-team-left">
                                <img src="{res['Logo_Loc']}" class="team-logo-card" alt="{res['Abrev_Loc']}" onerror="this.style.display='none'">
                                <div>
                                    <div class="team-name-card">{res['Local']}</div>
                                    <div class="team-sub-card">{res['Abrev_Loc']} (Local) • Win {res['Prob_Win_Loc']}% ({res['ML_Am_Loc']})</div>
                                </div>
                            </div>
                            {wl_loc_html}
                        </div>
                        <div class="billboard-prediction-box">
                            <div class="prediction-headline">
                                Nuestro pronóstico: {res['Abrev_Vis']} <span class="score-hi">{res['Marcador_Vis']} - {res['Marcador_Loc']}</span> {res['Abrev_Loc']}
                            </div>
                            <div class="prediction-meta">
                                <span>Spread Justo: <b>{spread_fav_tag}</b></span>
                                <span>Total Proy: <b>{res['Total_Proyectado']} pts</b></span>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.button(
                    "LEER ANÁLISIS →",
                    key=f"btn_leer_analisis_{game_idx}",
                    use_container_width=True,
                    on_click=ir_a_detalle_partido,
                    args=(game_idx,),
                )
                st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

else:
    # ==========================================================================
    # 11. VISTA DETALLADA (DRILL-DOWN DE PARTIDO SELECCIONADO)
    # ==========================================================================
    idx_sel = int(np.clip(st.session_state.partido_seleccionado_idx, 0, len(resultados_semana) - 1))
    res = resultados_semana[idx_sel]

    nav_col1, nav_col2, nav_col3 = st.columns([1.1, 1.8, 1.1])
    with nav_col1:
        st.button(
            "← Volver a la Cartelera",
            key="btn_volver_top",
            use_container_width=True,
            on_click=volver_a_cartelera,
        )
    with nav_col2:
        opciones_partidos = [
            f"Juego #{i + 1:02d}: {r['Visita']} @ {r['Local']} ({r['Marcador_Vis']}-{r['Marcador_Loc']})"
            for i, r in enumerate(resultados_semana)
        ]
        nuevo_idx = st.selectbox(
            "Cambiar de Partido en Vista Detallada",
            options=range(len(resultados_semana)),
            index=idx_sel,
            format_func=lambda i: opciones_partidos[i],
            label_visibility="collapsed",
        )
        if nuevo_idx != idx_sel:
            st.session_state.partido_seleccionado_idx = nuevo_idx
            st.rerun()
    with nav_col3:
        st.markdown(
            f"""
            <div style="text-align:right; font-family:'JetBrains Mono',monospace; font-size:0.78rem; color:#00F0FF; padding-top:6px;">
                {st.session_state.semana_nfl_label} • {res['Horario']}
            </div>
            """,
            unsafe_allow_html=True,
        )

    wl_vis_tv = renderizar_pastillas_wl(res["Form_Vis"])
    wl_loc_tv = renderizar_pastillas_wl(res["Form_Loc"])

    # --- A. SCOREBOARD TV HEADER CON LOGOS OFICIALES Y FORMA W/L ---
    st.markdown(
        f"""
        <div class="tv-scoreboard">
            <div class="tv-top-bar">
                <span>{st.session_state.semana_nfl_label} // {res['Horario']} // {res['Entorno_Tag']}</span>
                <span>RITMO COMBINADO: {res['Pace_Suma']}s ({res['Plays_Totales']} SNAPS) // HFA LOCAL: +{res['HFA_Pts']} PTS</span>
                <span>SIMULACIÓN MONTECARLO: {res['N_Sims']:,} ITERACIONES</span>
            </div>
            <div class="tv-main-grid">
                <div class="team-side">
                    <img src="{res['Logo_Vis']}" class="team-logo-tv" alt="{res['Abrev_Vis']}" onerror="this.style.display='none'">
                    <div>
                        <div class="team-name-tv">{res['Visita']} ({res['Abrev_Vis']} · VISITA)</div>
                        <div class="team-epa-sub">EPA/Play Proy: {res['EPA_Play_Vis']:+.3f} | RZ Eff: {res['RZ_Eff_Vis']}%</div>
                        {wl_vis_tv}
                    </div>
                </div>
                <div class="score-center-box">
                    <div style="font-family:'Orbitron',sans-serif; font-size:0.68rem; color:#00F0FF; letter-spacing:1px; margin-bottom:2px;">
                        IMPLIED TEAM TOTALS PROYECTADOS
                    </div>
                    <div class="projected-score-tv">{res['Pts_Vis']:.1f}  —  {res['Pts_Loc']:.1f}</div>
                    <div class="projected-total-pill">
                        NUESTRO PRONÓSTICO EXACTO: {res['Abrev_Vis']} {res['Marcador_Vis']} - {res['Marcador_Loc']} {res['Abrev_Loc']}  |  TOTAL: {res['Total_Proyectado']} PTS
                    </div>
                </div>
                <div class="team-side right">
                    <div>
                        <div class="team-name-tv">{res['Local']} ({res['Abrev_Loc']} · LOCAL)</div>
                        <div class="team-epa-sub">EPA/Play Proy: {res['EPA_Play_Loc']:+.3f} | RZ Eff: {res['RZ_Eff_Loc']}%</div>
                        <div style="display:flex; justify-content:flex-end;">{wl_loc_tv}</div>
                    </div>
                    <img src="{res['Logo_Loc']}" class="team-logo-tv" alt="{res['Abrev_Loc']}" onerror="this.style.display='none'">
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- B. FILA 1: SPREAD, MONEYLINE Y CLUSTERS DE MARCADOR EXACTO ---
    f1_col1, f1_col2 = st.columns(2)
    with f1_col1:
        spread_vis_justo = -res["Spread_Justo_Loc"]
        spread_vis_ref = -res["Spread_Mercado_Ref"]
        st.markdown(
            f"""
            <div class="quant-card">
                <div class="quant-card-header">📏 FILA 1A // PROYECCIÓN DE SPREAD (HÁNDICAP NFL & KEY NUMBERS)</div>
                <div class="metric-row">
                    <span class="metric-label">Spread Justo Modelo ({res['Abrev_Loc']} Local)</span>
                    <span class="metric-val">{res['Spread_Justo_Loc']:+.1f} pts (Visita {spread_vis_justo:+.1f})</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">{res['Local']} cubre ({res['Spread_Mercado_Ref']:+.1f})</span>
                    <span>
                        <span class="metric-val">{res['Prob_Cover_Loc']}%</span>
                        <span class="odds-chip green">Fair: {res['SP_Dec_Loc']} ({res['SP_Am_Loc']})</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">{res['Visita']} cubre ({spread_vis_ref:+.1f})</span>
                    <span>
                        <span class="metric-val">{res['Prob_Cover_Vis']}%</span>
                        <span class="odds-chip">Fair: {res['SP_Dec_Vis']} ({res['SP_Am_Vis']})</span>
                    </span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with f1_col2:
        top_clusters_str = " | ".join(
            [f"{res['Abrev_Vis']} {m['Marcador']} {res['Abrev_Loc']} ({m['Prob']}%)" for m in res["Top_3_Marcadores"]]
        )
        st.markdown(
            f"""
            <div class="quant-card">
                <div class="quant-card-header">🏆 FILA 1B // MONEYLINE (VICTORIA DIRECTA) & CLUSTERS EXACTOS</div>
                <div class="metric-row">
                    <span class="metric-label">Moneyline Local ({res['Local']})</span>
                    <span>
                        <span class="metric-val">{res['Prob_Win_Loc']}%</span>
                        <span class="odds-chip green">Fair: {res['ML_Dec_Loc']} ({res['ML_Am_Loc']})</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Moneyline Visita ({res['Visita']})</span>
                    <span>
                        <span class="metric-val">{res['Prob_Win_Vis']}%</span>
                        <span class="odds-chip">Fair: {res['ML_Dec_Vis']} ({res['ML_Am_Vis']})</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Top 3 Marcadores Exactos (Key Numbers)</span>
                    <span class="odds-chip amber">{top_clusters_str}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # --- C. FILA 2: OVER/UNDER TOTAL, TEAM TOTALS Y DESGLOSE DE 5,000 SIMULACIONES MONTECARLO ---
    f2_col1, f2_col2 = st.columns(2)
    with f2_col1:
        edge_ou = round(res["Total_Proyectado"] - res["Linea_Total_Mercado"], 1)
        recomendacion_ou = f"OVER {res['Linea_Total_Mercado']}" if edge_ou >= 0 else f"UNDER {res['Linea_Total_Mercado']}"
        tt_ref_loc = round(res["Pts_Loc"] * 2.0) / 2.0 - 0.5 if res["Pts_Loc"] % 1 == 0 else round(res["Pts_Loc"] - 0.5) + 0.5
        tt_ref_vis = round(res["Pts_Vis"] * 2.0) / 2.0 - 0.5 if res["Pts_Vis"] % 1 == 0 else round(res["Pts_Vis"] - 0.5) + 0.5
        st.markdown(
            f"""
            <div class="quant-card">
                <div class="quant-card-header">⚡ FILA 2A // OVER / UNDER TOTAL Y TEAM TOTALS INDIVIDUALES</div>
                <div class="metric-row">
                    <span class="metric-label">Total Proyectado vs Línea ({res['Linea_Total_Mercado']})</span>
                    <span class="metric-val">{res['Total_Proyectado']} pts (Edge: {edge_ou:+.1f} pts → {recomendacion_ou})</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">OVER {res['Linea_Total_Mercado']} / UNDER {res['Linea_Total_Mercado']}</span>
                    <span>
                        <span class="odds-chip green">O: {res['Prob_Over']}% ({res['OU_Dec_Over']} / {res['OU_Am_Over']})</span>
                        <span class="odds-chip">U: {res['Prob_Under']}% ({res['OU_Dec_Under']} / {res['OU_Am_Under']})</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Team Totals Proyectados ({res['Abrev_Vis']} / {res['Abrev_Loc']})</span>
                    <span>
                        <span class="odds-chip">{res['Abrev_Vis']}: {res['Pts_Vis']:.1f} (O/U {tt_ref_vis:.1f})</span>
                        <span class="odds-chip green">{res['Abrev_Loc']}: {res['Pts_Loc']:.1f} (O/U {tt_ref_loc:.1f})</span>
                    </span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with f2_col2:
        st.markdown(
            f"""
            <div class="quant-card">
                <div class="quant-card-header">🎲 FILA 2B // DESGLOSE DE {res['N_Sims']:,} SIMULACIONES DE MONTECARLO</div>
                <div class="metric-row">
                    <span class="metric-label">Percentiles de Puntos Totales (P10 / Mediana P50 / P90)</span>
                    <span class="metric-val">{res['MC_Total_P10']} pts  |  {res['MC_Total_P50']} pts  |  {res['MC_Total_P90']} pts</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Margen Medio Simulado (Local - Visita) y Volatilidad (σ)</span>
                    <span class="metric-val">{res['MC_Margen_Medio']:+.1f} pts  (σ = {res['MC_Std_Margen']} pts)</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Frecuencia de Tiempo Extra (Overtime) y Snaps Esperados</span>
                    <span>
                        <span class="odds-chip amber">OT: {res['MC_OT_Pct']}%</span>
                        <span class="odds-chip">{res['Plays_Totales']} jugadas ({res['Plays_Por_Equipo']}/eq)</span>
                    </span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # --- D. FILA 3: PROYECCIÓN DE TOUCHDOWNS Y PLAYER PROPS (ANYTIME TD) ---
    props_loc_html = "".join(
        [
            f"""
            <div class="td-prop-box">
                <div class="td-role">{p['Abrev']} • {p['Rol']} (Share {p['TD_Rate_Pct']}%)</div>
                <div class="td-player">{p['Jugador']}</div>
                <div class="td-prob">{p['Prob']}% (xTD {p['xTD']})</div>
                <div class="td-odds">Fair: {p['Fair_Dec']} ({p['Fair_Am']})</div>
            </div>
            """
            for p in res["Props_Loc"]
        ]
    )

    props_vis_html = "".join(
        [
            f"""
            <div class="td-prop-box">
                <div class="td-role">{p['Abrev']} • {p['Rol']} (Share {p['TD_Rate_Pct']}%)</div>
                <div class="td-player">{p['Jugador']}</div>
                <div class="td-prob">{p['Prob']}% (xTD {p['xTD']})</div>
                <div class="td-odds">Fair: {p['Fair_Dec']} ({p['Fair_Am']})</div>
            </div>
            """
            for p in res["Props_Vis"]
        ]
    )

    st.markdown(
        f"""
        <div class="quant-card">
            <div class="quant-card-header">🏈 FILA 3 // PROYECCIÓN DE TOUCHDOWNS (POISSON O/U 2.5 TDs) & PLAYER PROPS (ANYTIME TD)</div>
            <div class="metric-row">
                <span class="metric-label">
                    <img src="{res['Logo_Loc']}" width="20" height="20" style="vertical-align:middle; margin-right:6px;" onerror="this.style.display='none'">
                    <b>{res['Local']} (Local)</b> — xTD Total: <b>{res['xTD_Loc']}</b> (Pase: {res['xTD_Pass_Loc']} | Carrera: {res['xTD_Rush_Loc']})
                </span>
                <span>
                    <span class="odds-chip green">Over 2.5 TDs: {res['Prob_O25_TD_Loc']}% | {res['O25_TD_Loc_Dec']} ({res['O25_TD_Loc_Am']})</span>
                    <span class="odds-chip">Under 2.5 TDs: {res['Prob_U25_TD_Loc']}% | {res['U25_TD_Loc_Dec']} ({res['U25_TD_Loc_Am']})</span>
                </span>
            </div>
            <div class="td-prop-grid">{props_loc_html}</div>
            <div style="height: 12px;"></div>
            <div class="metric-row">
                <span class="metric-label">
                    <img src="{res['Logo_Vis']}" width="20" height="20" style="vertical-align:middle; margin-right:6px;" onerror="this.style.display='none'">
                    <b>{res['Visita']} (Visita)</b> — xTD Total: <b>{res['xTD_Vis']}</b> (Pase: {res['xTD_Pass_Vis']} | Carrera: {res['xTD_Rush_Vis']})
                </span>
                <span>
                    <span class="odds-chip green">Over 2.5 TDs: {res['Prob_O25_TD_Vis']}% | {res['O25_TD_Vis_Dec']} ({res['O25_TD_Vis_Am']})</span>
                    <span class="odds-chip">Under 2.5 TDs: {res['Prob_U25_TD_Vis']}% | {res['U25_TD_Vis_Dec']} ({res['U25_TD_Vis_Am']})</span>
                </span>
            </div>
            <div class="td-prop-grid">{props_vis_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # --- E. GRÁFICOS INTERACTIVOS DE TRINCHERAS, PROBABILIDAD Y KEY NUMBERS ---
    st.markdown(
        '<div class="radar-section-title"><span>📈 VISUALIZACIÓN DE PROBABILIDADES, TRINCHERAS Y KEY NUMBERS NFL</span></div>',
        unsafe_allow_html=True,
    )
    g_col1, g_col2 = st.columns(2)

    with g_col1:
        if PLOTLY_AVAILABLE:
            fig_prob = go.Figure()
            categorias_prob = [
                f"Win Prob ({res['Abrev_Loc']} vs {res['Abrev_Vis']})",
                f"Cover Spread ({res['Spread_Mercado_Ref']:+.1f})",
                f"Total O/U ({res['Linea_Total_Mercado']})",
            ]
            valores_loc_over = [res["Prob_Win_Loc"], res["Prob_Cover_Loc"], res["Prob_Over"]]
            valores_vis_under = [res["Prob_Win_Vis"], res["Prob_Cover_Vis"], res["Prob_Under"]]

            fig_prob.add_trace(
                go.Bar(
                    y=categorias_prob,
                    x=valores_loc_over,
                    name=f"{res['Abrev_Loc']} / OVER",
                    orientation="h",
                    marker_color="#00E676",
                    text=[f"{v:.1f}%" for v in valores_loc_over],
                    textposition="inside",
                )
            )
            fig_prob.add_trace(
                go.Bar(
                    y=categorias_prob,
                    x=valores_vis_under,
                    name=f"{res['Abrev_Vis']} / UNDER",
                    orientation="h",
                    marker_color="#00F0FF",
                    text=[f"{v:.1f}%" for v in valores_vis_under],
                    textposition="inside",
                )
            )
            fig_prob.update_layout(
                title="Distribución de Probabilidad de Victoria, Hándicap y Total",
                barmode="stack",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(12,19,34,0.8)",
                font=dict(family="JetBrains Mono, monospace", color="#ECF2F8", size=11),
                height=300,
                margin=dict(l=10, r=10, t=40, b=10),
                xaxis=dict(range=[0, 100], title="Probabilidad (%)"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig_prob, use_container_width=True, key="chart_prob_detail")
        else:
            df_prob_chart = pd.DataFrame(
                {
                    f"{res['Abrev_Loc']} / OVER (%)": [res["Prob_Win_Loc"], res["Prob_Cover_Loc"], res["Prob_Over"]],
                    f"{res['Abrev_Vis']} / UNDER (%)": [res["Prob_Win_Vis"], res["Prob_Cover_Vis"], res["Prob_Under"]],
                },
                index=["Moneyline Win", "Spread Cover", "Over/Under Total"],
            )
            st.bar_chart(df_prob_chart)

    with g_col2:
        if PLOTLY_AVAILABLE:
            metricas_trench = ["Pass EPA Neto (x100)", "Rush EPA Neto (x100)", "Presión Def (%)", "Zona Roja TD (%)"]
            vals_trench_loc = [
                res["Net_Pass_EPA_Loc"] * 100.0,
                res["Net_Rush_EPA_Loc"] * 100.0,
                res["Press_Loc"],
                res["RZ_Eff_Loc"],
            ]
            vals_trench_vis = [
                res["Net_Pass_EPA_Vis"] * 100.0,
                res["Net_Rush_EPA_Vis"] * 100.0,
                res["Press_Vis"],
                res["RZ_Eff_Vis"],
            ]

            fig_trench = go.Figure()
            fig_trench.add_trace(
                go.Bar(
                    x=metricas_trench,
                    y=vals_trench_loc,
                    name=f"{res['Abrev_Loc']} (Local)",
                    marker_color="#00E676",
                    text=[f"{v:.1f}" for v in vals_trench_loc],
                    textposition="auto",
                )
            )
            fig_trench.add_trace(
                go.Bar(
                    x=metricas_trench,
                    y=vals_trench_vis,
                    name=f"{res['Abrev_Vis']} (Visita)",
                    marker_color="#FFB300",
                    text=[f"{v:.1f}" for v in vals_trench_vis],
                    textposition="auto",
                )
            )
            fig_trench.update_layout(
                title="Duelo de Trincheras: EPA Ajustado (x100), Pressure % y Zona Roja",
                barmode="group",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(12,19,34,0.8)",
                font=dict(family="JetBrains Mono, monospace", color="#ECF2F8", size=11),
                height=300,
                margin=dict(l=10, r=10, t=40, b=10),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig_trench, use_container_width=True, key="chart_trench_detail")
        else:
            df_trench_chart = pd.DataFrame(
                {
                    f"{res['Abrev_Loc']} (Local)": [
                        res["Net_Pass_EPA_Loc"] * 100.0,
                        res["Net_Rush_EPA_Loc"] * 100.0,
                        res["Press_Loc"],
                        res["RZ_Eff_Loc"],
                    ],
                    f"{res['Abrev_Vis']} (Visita)": [
                        res["Net_Pass_EPA_Vis"] * 100.0,
                        res["Net_Rush_EPA_Vis"] * 100.0,
                        res["Press_Vis"],
                        res["RZ_Eff_Vis"],
                    ],
                },
                index=["Pass EPA (x100)", "Rush EPA (x100)", "Pressure %", "RedZone Eff %"],
            )
            st.bar_chart(df_trench_chart)

    kn_cols = st.columns(6)
    for kn_idx, (kn_label, kn_val) in enumerate(res["Key_Margins_Dist"].items()):
        with kn_cols[kn_idx]:
            st.metric(label=f"🔑 {kn_label}", value=f"{kn_val}%")

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    st.button(
        "← Volver a la Cartelera Principal (Grid 3x3)",
        key="btn_volver_bottom",
        use_container_width=True,
        on_click=volver_a_cartelera,
    )