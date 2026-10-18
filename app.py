import datetime
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

try:
    import nfl_data_py as nfl
    NFL_DATA_PY_AVAILABLE = True
except ImportError:
    NFL_DATA_PY_AVAILABLE = False

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
# ESTILOS CSS: CYBER-QUANT UI (ORBITRON + JETBRAINS MONO)
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
    border-radius: 10px;
    padding: 18px 24px;
    margin-bottom: 18px;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.55), 0 0 18px rgba(0, 240, 255, 0.08);
}

.terminal-title {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.75rem;
    font-weight: 800;
    letter-spacing: 1.8px;
    color: #FFFFFF;
    margin: 0;
    text-transform: uppercase;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.terminal-subtitle {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
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

/* Radar Ejecutivo de la Semana */
.radar-section-title {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.08rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: var(--cyan-neon);
    text-transform: uppercase;
    margin: 14px 0 12px 0;
    border-bottom: 1px solid var(--border-subtle);
    padding-bottom: 6px;
}

.radar-card {
    background: linear-gradient(180deg, rgba(17, 26, 46, 0.96) 0%, rgba(11, 17, 30, 0.98) 100%);
    border: 1px solid var(--border-subtle);
    border-top: 3px solid var(--cyan-neon);
    border-radius: 10px;
    padding: 15px 16px;
    height: 100%;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45);
}

.radar-card.lock { border-top-color: var(--green-sharp); }
.radar-card.total { border-top-color: var(--cyan-neon); }
.radar-card.star { border-top-color: var(--amber-quant); }
.radar-card.dog { border-top-color: var(--purple-prop); }

.radar-tag {
    font-family: 'Orbitron', sans-serif;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 1.1px;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 6px;
}

.radar-pick {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.06rem;
    font-weight: 800;
    color: #FFFFFF;
    margin-bottom: 6px;
}

.radar-metrics {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.80rem;
    color: var(--cyan-neon);
    margin-bottom: 4px;
}

.radar-sub {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.73rem;
    color: var(--text-muted);
}

/* Scoreboard TV Header */
.tv-scoreboard {
    background: linear-gradient(90deg, #0B1324 0%, #13203B 50%, #0B1324 100%);
    border: 1px solid var(--border-strong);
    border-radius: 12px;
    padding: 16px 22px;
    margin-top: 22px;
    margin-bottom: 12px;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.5);
}

.tv-top-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding-bottom: 8px;
    margin-bottom: 12px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: var(--text-muted);
}

.tv-main-grid {
    display: grid;
    grid-template-columns: 1.3fr 1fr 1.3fr;
    align-items: center;
    gap: 12px;
}

.team-side {
    display: flex;
    align-items: center;
    gap: 14px;
}

.team-side.right {
    justify-content: flex-end;
    text-align: right;
}

.team-badge {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.15rem;
    font-weight: 900;
    color: #060A12;
    background: linear-gradient(135deg, var(--cyan-neon), #00A8FF);
    padding: 10px 12px;
    border-radius: 8px;
    min-width: 58px;
    text-align: center;
    box-shadow: 0 0 12px rgba(0, 240, 255, 0.35);
}

.team-badge.home {
    background: linear-gradient(135deg, var(--green-sharp), #00B862);
    box-shadow: 0 0 12px rgba(0, 230, 118, 0.35);
}

.team-name-tv {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.05rem;
    font-weight: 800;
    color: #FFFFFF;
}

.team-epa-sub {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: var(--text-muted);
}

.score-center-box {
    text-align: center;
    background: rgba(6, 10, 18, 0.75);
    border: 1px solid rgba(0, 240, 255, 0.25);
    border-radius: 10px;
    padding: 10px 14px;
}

.projected-score-tv {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.55rem;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: 2px;
}

.projected-total-pill {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: var(--amber-quant);
    margin-top: 3px;
}

/* Tarjetas de Mercados y Props */
.quant-card {
    background: var(--bg-card);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 10px;
    padding: 14px 16px;
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
    padding: 5px 0;
    border-bottom: 1px dashed rgba(255, 255, 255, 0.06);
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
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
    font-size: 0.76rem;
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
    background: rgba(6, 10, 18, 0.65);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-left: 3px solid var(--amber-quant);
    border-radius: 7px;
    padding: 8px 10px;
    font-family: 'JetBrains Mono', monospace;
}

.td-role {
    font-size: 0.68rem;
    color: var(--text-muted);
    text-transform: uppercase;
}

.td-player {
    font-size: 0.80rem;
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
</style>
"""
st.markdown(CYBER_QUANT_CSS, unsafe_allow_html=True)


# ==============================================================================
# 1. CATÁLOGO OFICIAL DE LAS 32 FRANQUICIAS Y RESPALDO BASE (FALLBACK)
# ==============================================================================
NFL_TEAMS_META = {
    "KC":  {"Equipo": "Kansas City Chiefs",    "Dome": 0, "Cold_Base": 0.015, "HFA_Mod": 0.35},
    "SF":  {"Equipo": "San Francisco 49ers",   "Dome": 0, "Cold_Base": 0.048, "HFA_Mod": 0.20},
    "BUF": {"Equipo": "Buffalo Bills",         "Dome": 0, "Cold_Base": 0.010, "HFA_Mod": 0.30},
    "BAL": {"Equipo": "Baltimore Ravens",      "Dome": 0, "Cold_Base": 0.018, "HFA_Mod": 0.28},
    "DET": {"Equipo": "Detroit Lions",         "Dome": 1, "Cold_Base": 0.055, "HFA_Mod": 0.32},
    "DAL": {"Equipo": "Dallas Cowboys",        "Dome": 1, "Cold_Base": 0.052, "HFA_Mod": 0.22},
    "PHI": {"Equipo": "Philadelphia Eagles",   "Dome": 0, "Cold_Base": 0.022, "HFA_Mod": 0.30},
    "NE":  {"Equipo": "New England Patriots",  "Dome": 0, "Cold_Base": 0.014, "HFA_Mod": 0.12},
    "HOU": {"Equipo": "Houston Texans",        "Dome": 1, "Cold_Base": 0.050, "HFA_Mod": 0.20},
    "GB":  {"Equipo": "Green Bay Packers",     "Dome": 0, "Cold_Base": 0.012, "HFA_Mod": 0.28},
    "CIN": {"Equipo": "Cincinnati Bengals",    "Dome": 0, "Cold_Base": 0.020, "HFA_Mod": 0.22},
    "MIA": {"Equipo": "Miami Dolphins",        "Dome": 0, "Cold_Base": 0.082, "HFA_Mod": 0.24},
    "LAR": {"Equipo": "Los Angeles Rams",      "Dome": 1, "Cold_Base": 0.056, "HFA_Mod": 0.15},
    "MIN": {"Equipo": "Minnesota Vikings",     "Dome": 1, "Cold_Base": 0.045, "HFA_Mod": 0.28},
    "NYJ": {"Equipo": "New York Jets",         "Dome": 0, "Cold_Base": 0.025, "HFA_Mod": 0.16},
    "CLE": {"Equipo": "Cleveland Browns",      "Dome": 0, "Cold_Base": 0.018, "HFA_Mod": 0.22},
    "PIT": {"Equipo": "Pittsburgh Steelers",   "Dome": 0, "Cold_Base": 0.015, "HFA_Mod": 0.26},
    "ATL": {"Equipo": "Atlanta Falcons",       "Dome": 1, "Cold_Base": 0.054, "HFA_Mod": 0.18},
    "CHI": {"Equipo": "Chicago Bears",         "Dome": 0, "Cold_Base": 0.016, "HFA_Mod": 0.20},
    "JAX": {"Equipo": "Jacksonville Jaguars",  "Dome": 0, "Cold_Base": 0.058, "HFA_Mod": 0.15},
    "IND": {"Equipo": "Indianapolis Colts",    "Dome": 1, "Cold_Base": 0.048, "HFA_Mod": 0.18},
    "SEA": {"Equipo": "Seattle Seahawks",      "Dome": 0, "Cold_Base": 0.024, "HFA_Mod": 0.32},
    "TB":  {"Equipo": "Tampa Bay Buccaneers",  "Dome": 0, "Cold_Base": 0.055, "HFA_Mod": 0.18},
    "WAS": {"Equipo": "Washington Commanders", "Dome": 0, "Cold_Base": 0.025, "HFA_Mod": 0.16},
    "ARI": {"Equipo": "Arizona Cardinals",     "Dome": 1, "Cold_Base": 0.056, "HFA_Mod": 0.16},
    "LAC": {"Equipo": "Los Angeles Chargers",  "Dome": 1, "Cold_Base": 0.048, "HFA_Mod": 0.12},
    "NO":  {"Equipo": "New Orleans Saints",    "Dome": 1, "Cold_Base": 0.058, "HFA_Mod": 0.25},
    "LV":  {"Equipo": "Las Vegas Raiders",     "Dome": 1, "Cold_Base": 0.046, "HFA_Mod": 0.16},
    "DEN": {"Equipo": "Denver Broncos",        "Dome": 0, "Cold_Base": 0.016, "HFA_Mod": 0.32},
    "TEN": {"Equipo": "Tennessee Titans",      "Dome": 0, "Cold_Base": 0.032, "HFA_Mod": 0.18},
    "NYG": {"Equipo": "New York Giants",       "Dome": 0, "Cold_Base": 0.022, "HFA_Mod": 0.14},
    "CAR": {"Equipo": "Carolina Panthers",     "Dome": 0, "Cold_Base": 0.038, "HFA_Mod": 0.14},
}

TEAM_ABBR_NORMALIZE = {
    "LA": "LAR", "STL": "LAR", "SD": "LAC", "OAK": "LV",
    "WSH": "WAS", "JAC": "JAX", "ARZ": "ARI", "BLT": "BAL",
    "CLV": "CLE", "HST": "HOU",
}

DEFAULT_TEAMS_DATA = [
    {"Equipo": "Kansas City Chiefs", "Abrev": "KC", "Pass_EPA": 0.195, "Rush_EPA": 0.015, "Pass_Success_Rate": 0.518, "Pace_Sec": 27.6, "RedZone_TD_Pct": 0.615, "Def_Pass_EPA": -0.065, "Def_Rush_EPA": -0.035, "Pressure_Pct": 0.258, "Def_RZ_Stop_Pct": 0.515, "Dome": 0, "Cold_Weather_Drop": 0.015, "RB1_TD_Rate": 0.310, "WR1_TD_Rate": 0.275, "TE1_TD_Rate": 0.295, "QB_Rush_TD_Rate": 0.115, "Pass_Rate": 0.615, "HFA_Mod": 0.35, "QB_Nombre": "P. Mahomes", "RB1_Nombre": "I. Pacheco", "WR1_Nombre": "R. Rice", "TE1_Nombre": "T. Kelce"},
    {"Equipo": "San Francisco 49ers", "Abrev": "SF", "Pass_EPA": 0.235, "Rush_EPA": 0.095, "Pass_Success_Rate": 0.532, "Pace_Sec": 28.9, "RedZone_TD_Pct": 0.655, "Def_Pass_EPA": -0.078, "Def_Rush_EPA": -0.062, "Pressure_Pct": 0.264, "Def_RZ_Stop_Pct": 0.505, "Dome": 0, "Cold_Weather_Drop": 0.048, "RB1_TD_Rate": 0.435, "WR1_TD_Rate": 0.265, "TE1_TD_Rate": 0.215, "QB_Rush_TD_Rate": 0.095, "Pass_Rate": 0.535, "HFA_Mod": 0.20, "QB_Nombre": "B. Purdy", "RB1_Nombre": "C. McCaffrey", "WR1_Nombre": "B. Aiyuk", "TE1_Nombre": "G. Kittle"},
    {"Equipo": "Buffalo Bills", "Abrev": "BUF", "Pass_EPA": 0.182, "Rush_EPA": 0.052, "Pass_Success_Rate": 0.504, "Pace_Sec": 26.8, "RedZone_TD_Pct": 0.638, "Def_Pass_EPA": -0.048, "Def_Rush_EPA": -0.022, "Pressure_Pct": 0.249, "Def_RZ_Stop_Pct": 0.488, "Dome": 0, "Cold_Weather_Drop": 0.010, "RB1_TD_Rate": 0.275, "WR1_TD_Rate": 0.255, "TE1_TD_Rate": 0.195, "QB_Rush_TD_Rate": 0.265, "Pass_Rate": 0.565, "HFA_Mod": 0.30, "QB_Nombre": "J. Allen", "RB1_Nombre": "J. Cook", "WR1_Nombre": "K. Shakir", "TE1_Nombre": "D. Kincaid"},
    {"Equipo": "Baltimore Ravens", "Abrev": "BAL", "Pass_EPA": 0.168, "Rush_EPA": 0.118, "Pass_Success_Rate": 0.498, "Pace_Sec": 28.4, "RedZone_TD_Pct": 0.628, "Def_Pass_EPA": -0.092, "Def_Rush_EPA": -0.075, "Pressure_Pct": 0.272, "Def_RZ_Stop_Pct": 0.545, "Dome": 0, "Cold_Weather_Drop": 0.018, "RB1_TD_Rate": 0.385, "WR1_TD_Rate": 0.240, "TE1_TD_Rate": 0.225, "QB_Rush_TD_Rate": 0.195, "Pass_Rate": 0.505, "HFA_Mod": 0.28, "QB_Nombre": "L. Jackson", "RB1_Nombre": "D. Henry", "WR1_Nombre": "Z. Flowers", "TE1_Nombre": "M. Andrews"},
    {"Equipo": "Detroit Lions", "Abrev": "DET", "Pass_EPA": 0.188, "Rush_EPA": 0.088, "Pass_Success_Rate": 0.524, "Pace_Sec": 26.5, "RedZone_TD_Pct": 0.648, "Def_Pass_EPA": -0.025, "Def_Rush_EPA": -0.068, "Pressure_Pct": 0.252, "Def_RZ_Stop_Pct": 0.465, "Dome": 1, "Cold_Weather_Drop": 0.055, "RB1_TD_Rate": 0.395, "WR1_TD_Rate": 0.310, "TE1_TD_Rate": 0.220, "QB_Rush_TD_Rate": 0.045, "Pass_Rate": 0.545, "HFA_Mod": 0.32, "QB_Nombre": "J. Goff", "RB1_Nombre": "J. Gibbs", "WR1_Nombre": "A. St. Brown", "TE1_Nombre": "S. LaPorta"},
    {"Equipo": "Dallas Cowboys", "Abrev": "DAL", "Pass_EPA": 0.145, "Rush_EPA": -0.018, "Pass_Success_Rate": 0.495, "Pace_Sec": 26.1, "RedZone_TD_Pct": 0.575, "Def_Pass_EPA": -0.042, "Def_Rush_EPA": 0.015, "Pressure_Pct": 0.278, "Def_RZ_Stop_Pct": 0.455, "Dome": 1, "Cold_Weather_Drop": 0.052, "RB1_TD_Rate": 0.245, "WR1_TD_Rate": 0.355, "TE1_TD_Rate": 0.205, "QB_Rush_TD_Rate": 0.085, "Pass_Rate": 0.595, "HFA_Mod": 0.22, "QB_Nombre": "D. Prescott", "RB1_Nombre": "R. Dowdle", "WR1_Nombre": "C. Lamb", "TE1_Nombre": "J. Ferguson"},
    {"Equipo": "Philadelphia Eagles", "Abrev": "PHI", "Pass_EPA": 0.152, "Rush_EPA": 0.082, "Pass_Success_Rate": 0.502, "Pace_Sec": 26.9, "RedZone_TD_Pct": 0.622, "Def_Pass_EPA": -0.038, "Def_Rush_EPA": -0.055, "Pressure_Pct": 0.262, "Def_RZ_Stop_Pct": 0.492, "Dome": 0, "Cold_Weather_Drop": 0.022, "RB1_TD_Rate": 0.335, "WR1_TD_Rate": 0.295, "TE1_TD_Rate": 0.165, "QB_Rush_TD_Rate": 0.255, "Pass_Rate": 0.530, "HFA_Mod": 0.30, "QB_Nombre": "J. Hurts", "RB1_Nombre": "S. Barkley", "WR1_Nombre": "A.J. Brown", "TE1_Nombre": "D. Goedert"},
    {"Equipo": "New England Patriots", "Abrev": "NE", "Pass_EPA": -0.095, "Rush_EPA": -0.045, "Pass_Success_Rate": 0.428, "Pace_Sec": 28.2, "RedZone_TD_Pct": 0.495, "Def_Pass_EPA": -0.032, "Def_Rush_EPA": -0.058, "Pressure_Pct": 0.228, "Def_RZ_Stop_Pct": 0.510, "Dome": 0, "Cold_Weather_Drop": 0.014, "RB1_TD_Rate": 0.325, "WR1_TD_Rate": 0.220, "TE1_TD_Rate": 0.215, "QB_Rush_TD_Rate": 0.125, "Pass_Rate": 0.540, "HFA_Mod": 0.12, "QB_Nombre": "D. Maye", "RB1_Nombre": "R. Stevenson", "WR1_Nombre": "D. Douglas", "TE1_Nombre": "H. Henry"},
    {"Equipo": "Houston Texans", "Abrev": "HOU", "Pass_EPA": 0.148, "Rush_EPA": -0.012, "Pass_Success_Rate": 0.492, "Pace_Sec": 27.1, "RedZone_TD_Pct": 0.585, "Def_Pass_EPA": -0.035, "Def_Rush_EPA": -0.048, "Pressure_Pct": 0.260, "Def_RZ_Stop_Pct": 0.485, "Dome": 1, "Cold_Weather_Drop": 0.050, "RB1_TD_Rate": 0.330, "WR1_TD_Rate": 0.315, "TE1_TD_Rate": 0.185, "QB_Rush_TD_Rate": 0.075, "Pass_Rate": 0.580, "HFA_Mod": 0.20, "QB_Nombre": "C.J. Stroud", "RB1_Nombre": "J. Mixon", "WR1_Nombre": "N. Collins", "TE1_Nombre": "D. Schultz"},
    {"Equipo": "Green Bay Packers", "Abrev": "GB", "Pass_EPA": 0.158, "Rush_EPA": 0.038, "Pass_Success_Rate": 0.506, "Pace_Sec": 27.5, "RedZone_TD_Pct": 0.605, "Def_Pass_EPA": -0.022, "Def_Rush_EPA": 0.012, "Pressure_Pct": 0.244, "Def_RZ_Stop_Pct": 0.478, "Dome": 0, "Cold_Weather_Drop": 0.012, "RB1_TD_Rate": 0.330, "WR1_TD_Rate": 0.285, "TE1_TD_Rate": 0.190, "QB_Rush_TD_Rate": 0.090, "Pass_Rate": 0.555, "HFA_Mod": 0.28, "QB_Nombre": "J. Love", "RB1_Nombre": "J. Jacobs", "WR1_Nombre": "J. Reed", "TE1_Nombre": "T. Kraft"},
    {"Equipo": "Cincinnati Bengals", "Abrev": "CIN", "Pass_EPA": 0.172, "Rush_EPA": -0.015, "Pass_Success_Rate": 0.508, "Pace_Sec": 26.7, "RedZone_TD_Pct": 0.610, "Def_Pass_EPA": 0.018, "Def_Rush_EPA": 0.025, "Pressure_Pct": 0.235, "Def_RZ_Stop_Pct": 0.460, "Dome": 0, "Cold_Weather_Drop": 0.020, "RB1_TD_Rate": 0.285, "WR1_TD_Rate": 0.345, "TE1_TD_Rate": 0.175, "QB_Rush_TD_Rate": 0.085, "Pass_Rate": 0.625, "HFA_Mod": 0.22, "QB_Nombre": "J. Burrow", "RB1_Nombre": "C. Brown", "WR1_Nombre": "J. Chase", "TE1_Nombre": "M. Gesicki"},
    {"Equipo": "Miami Dolphins", "Abrev": "MIA", "Pass_EPA": 0.162, "Rush_EPA": 0.065, "Pass_Success_Rate": 0.505, "Pace_Sec": 27.3, "RedZone_TD_Pct": 0.598, "Def_Pass_EPA": -0.015, "Def_Rush_EPA": -0.020, "Pressure_Pct": 0.246, "Def_RZ_Stop_Pct": 0.452, "Dome": 0, "Cold_Weather_Drop": 0.082, "RB1_TD_Rate": 0.365, "WR1_TD_Rate": 0.350, "TE1_TD_Rate": 0.155, "QB_Rush_TD_Rate": 0.045, "Pass_Rate": 0.560, "HFA_Mod": 0.24, "QB_Nombre": "T. Tagovailoa", "RB1_Nombre": "D. Achane", "WR1_Nombre": "T. Hill", "TE1_Nombre": "J. Smith"},
    {"Equipo": "Los Angeles Rams", "Abrev": "LAR", "Pass_EPA": 0.142, "Rush_EPA": 0.028, "Pass_Success_Rate": 0.496, "Pace_Sec": 27.4, "RedZone_TD_Pct": 0.592, "Def_Pass_EPA": 0.022, "Def_Rush_EPA": 0.008, "Pressure_Pct": 0.232, "Def_RZ_Stop_Pct": 0.448, "Dome": 1, "Cold_Weather_Drop": 0.056, "RB1_TD_Rate": 0.380, "WR1_TD_Rate": 0.310, "TE1_TD_Rate": 0.160, "QB_Rush_TD_Rate": 0.035, "Pass_Rate": 0.575, "HFA_Mod": 0.15, "QB_Nombre": "M. Stafford", "RB1_Nombre": "K. Williams", "WR1_Nombre": "P. Nacua", "TE1_Nombre": "T. Higbee"},
    {"Equipo": "Minnesota Vikings", "Abrev": "MIN", "Pass_EPA": 0.125, "Rush_EPA": -0.010, "Pass_Success_Rate": 0.488, "Pace_Sec": 27.0, "RedZone_TD_Pct": 0.580, "Def_Pass_EPA": -0.068, "Def_Rush_EPA": -0.042, "Pressure_Pct": 0.275, "Def_RZ_Stop_Pct": 0.512, "Dome": 1, "Cold_Weather_Drop": 0.045, "RB1_TD_Rate": 0.295, "WR1_TD_Rate": 0.365, "TE1_TD_Rate": 0.205, "QB_Rush_TD_Rate": 0.065, "Pass_Rate": 0.590, "HFA_Mod": 0.28, "QB_Nombre": "S. Darnold", "RB1_Nombre": "A. Jones", "WR1_Nombre": "J. Jefferson", "TE1_Nombre": "T.J. Hockenson"},
    {"Equipo": "New York Jets", "Abrev": "NYJ", "Pass_EPA": 0.045, "Rush_EPA": -0.025, "Pass_Success_Rate": 0.462, "Pace_Sec": 28.8, "RedZone_TD_Pct": 0.535, "Def_Pass_EPA": -0.085, "Def_Rush_EPA": -0.045, "Pressure_Pct": 0.268, "Def_RZ_Stop_Pct": 0.525, "Dome": 0, "Cold_Weather_Drop": 0.025, "RB1_TD_Rate": 0.355, "WR1_TD_Rate": 0.315, "TE1_TD_Rate": 0.165, "QB_Rush_TD_Rate": 0.040, "Pass_Rate": 0.575, "HFA_Mod": 0.16, "QB_Nombre": "A. Rodgers", "RB1_Nombre": "B. Hall", "WR1_Nombre": "G. Wilson", "TE1_Nombre": "T. Conklin"},
    {"Equipo": "Cleveland Browns", "Abrev": "CLE", "Pass_EPA": -0.035, "Rush_EPA": -0.020, "Pass_Success_Rate": 0.442, "Pace_Sec": 26.6, "RedZone_TD_Pct": 0.525, "Def_Pass_EPA": -0.088, "Def_Rush_EPA": -0.052, "Pressure_Pct": 0.276, "Def_RZ_Stop_Pct": 0.532, "Dome": 0, "Cold_Weather_Drop": 0.018, "RB1_TD_Rate": 0.340, "WR1_TD_Rate": 0.275, "TE1_TD_Rate": 0.225, "QB_Rush_TD_Rate": 0.095, "Pass_Rate": 0.555, "HFA_Mod": 0.22, "QB_Nombre": "J. Winston", "RB1_Nombre": "N. Chubb", "WR1_Nombre": "J. Jeudy", "TE1_Nombre": "D. Njoku"},
    {"Equipo": "Pittsburgh Steelers", "Abrev": "PIT", "Pass_EPA": 0.038, "Rush_EPA": 0.018, "Pass_Success_Rate": 0.465, "Pace_Sec": 28.5, "RedZone_TD_Pct": 0.520, "Def_Pass_EPA": -0.058, "Def_Rush_EPA": -0.038, "Pressure_Pct": 0.266, "Def_RZ_Stop_Pct": 0.538, "Dome": 0, "Cold_Weather_Drop": 0.015, "RB1_TD_Rate": 0.335, "WR1_TD_Rate": 0.270, "TE1_TD_Rate": 0.195, "QB_Rush_TD_Rate": 0.110, "Pass_Rate": 0.520, "HFA_Mod": 0.26, "QB_Nombre": "R. Wilson", "RB1_Nombre": "N. Harris", "WR1_Nombre": "G. Pickens", "TE1_Nombre": "P. Freiermuth"},
    {"Equipo": "Atlanta Falcons", "Abrev": "ATL", "Pass_EPA": 0.088, "Rush_EPA": 0.035, "Pass_Success_Rate": 0.484, "Pace_Sec": 26.8, "RedZone_TD_Pct": 0.565, "Def_Pass_EPA": 0.012, "Def_Rush_EPA": -0.015, "Pressure_Pct": 0.218, "Def_RZ_Stop_Pct": 0.472, "Dome": 1, "Cold_Weather_Drop": 0.054, "RB1_TD_Rate": 0.375, "WR1_TD_Rate": 0.285, "TE1_TD_Rate": 0.200, "QB_Rush_TD_Rate": 0.035, "Pass_Rate": 0.550, "HFA_Mod": 0.18, "QB_Nombre": "K. Cousins", "RB1_Nombre": "B. Robinson", "WR1_Nombre": "D. London", "TE1_Nombre": "K. Pitts"},
    {"Equipo": "Chicago Bears", "Abrev": "CHI", "Pass_EPA": 0.032, "Rush_EPA": 0.010, "Pass_Success_Rate": 0.458, "Pace_Sec": 27.7, "RedZone_TD_Pct": 0.548, "Def_Pass_EPA": -0.045, "Def_Rush_EPA": -0.048, "Pressure_Pct": 0.238, "Def_RZ_Stop_Pct": 0.495, "Dome": 0, "Cold_Weather_Drop": 0.016, "RB1_TD_Rate": 0.305, "WR1_TD_Rate": 0.295, "TE1_TD_Rate": 0.210, "QB_Rush_TD_Rate": 0.115, "Pass_Rate": 0.555, "HFA_Mod": 0.20, "QB_Nombre": "C. Williams", "RB1_Nombre": "D. Swift", "WR1_Nombre": "D.J. Moore", "TE1_Nombre": "C. Kmet"},
    {"Equipo": "Jacksonville Jaguars", "Abrev": "JAX", "Pass_EPA": 0.068, "Rush_EPA": -0.022, "Pass_Success_Rate": 0.475, "Pace_Sec": 26.9, "RedZone_TD_Pct": 0.542, "Def_Pass_EPA": 0.025, "Def_Rush_EPA": -0.018, "Pressure_Pct": 0.236, "Def_RZ_Stop_Pct": 0.462, "Dome": 0, "Cold_Weather_Drop": 0.058, "RB1_TD_Rate": 0.335, "WR1_TD_Rate": 0.290, "TE1_TD_Rate": 0.205, "QB_Rush_TD_Rate": 0.095, "Pass_Rate": 0.580, "HFA_Mod": 0.15, "QB_Nombre": "T. Lawrence", "RB1_Nombre": "T. Etienne", "WR1_Nombre": "B. Thomas Jr.", "TE1_Nombre": "E. Engram"},
    {"Equipo": "Indianapolis Colts", "Abrev": "IND", "Pass_EPA": 0.042, "Rush_EPA": 0.055, "Pass_Success_Rate": 0.464, "Pace_Sec": 25.9, "RedZone_TD_Pct": 0.578, "Def_Pass_EPA": 0.018, "Def_Rush_EPA": 0.010, "Pressure_Pct": 0.242, "Def_RZ_Stop_Pct": 0.458, "Dome": 1, "Cold_Weather_Drop": 0.048, "RB1_TD_Rate": 0.385, "WR1_TD_Rate": 0.255, "TE1_TD_Rate": 0.150, "QB_Rush_TD_Rate": 0.215, "Pass_Rate": 0.525, "HFA_Mod": 0.18, "QB_Nombre": "A. Richardson", "RB1_Nombre": "J. Taylor", "WR1_Nombre": "M. Pittman", "TE1_Nombre": "K. Granson"},
    {"Equipo": "Seattle Seahawks", "Abrev": "SEA", "Pass_EPA": 0.095, "Rush_EPA": 0.008, "Pass_Success_Rate": 0.486, "Pace_Sec": 26.8, "RedZone_TD_Pct": 0.558, "Def_Pass_EPA": -0.012, "Def_Rush_EPA": 0.018, "Pressure_Pct": 0.245, "Def_RZ_Stop_Pct": 0.475, "Dome": 0, "Cold_Weather_Drop": 0.024, "RB1_TD_Rate": 0.360, "WR1_TD_Rate": 0.310, "TE1_TD_Rate": 0.165, "QB_Rush_TD_Rate": 0.065, "Pass_Rate": 0.585, "HFA_Mod": 0.32, "QB_Nombre": "G. Smith", "RB1_Nombre": "K. Walker III", "WR1_Nombre": "D.K. Metcalf", "TE1_Nombre": "N. Fant"},
    {"Equipo": "Tampa Bay Buccaneers", "Abrev": "TB", "Pass_EPA": 0.118, "Rush_EPA": -0.018, "Pass_Success_Rate": 0.489, "Pace_Sec": 27.2, "RedZone_TD_Pct": 0.572, "Def_Pass_EPA": 0.015, "Def_Rush_EPA": -0.042, "Pressure_Pct": 0.250, "Def_RZ_Stop_Pct": 0.510, "Dome": 0, "Cold_Weather_Drop": 0.055, "RB1_TD_Rate": 0.315, "WR1_TD_Rate": 0.345, "TE1_TD_Rate": 0.180, "QB_Rush_TD_Rate": 0.065, "Pass_Rate": 0.585, "HFA_Mod": 0.18, "QB_Nombre": "B. Mayfield", "RB1_Nombre": "B. Irving", "WR1_Nombre": "M. Evans", "TE1_Nombre": "C. Otton"},
    {"Equipo": "Washington Commanders", "Abrev": "WAS", "Pass_EPA": 0.135, "Rush_EPA": 0.072, "Pass_Success_Rate": 0.498, "Pace_Sec": 26.2, "RedZone_TD_Pct": 0.595, "Def_Pass_EPA": 0.048, "Def_Rush_EPA": 0.022, "Pressure_Pct": 0.225, "Def_RZ_Stop_Pct": 0.435, "Dome": 0, "Cold_Weather_Drop": 0.025, "RB1_TD_Rate": 0.345, "WR1_TD_Rate": 0.285, "TE1_TD_Rate": 0.165, "QB_Rush_TD_Rate": 0.195, "Pass_Rate": 0.535, "HFA_Mod": 0.16, "QB_Nombre": "J. Daniels", "RB1_Nombre": "B. Robinson Jr.", "WR1_Nombre": "T. McLaurin", "TE1_Nombre": "Z. Ertz"},
    {"Equipo": "Arizona Cardinals", "Abrev": "ARI", "Pass_EPA": 0.065, "Rush_EPA": 0.058, "Pass_Success_Rate": 0.478, "Pace_Sec": 27.1, "RedZone_TD_Pct": 0.568, "Def_Pass_EPA": 0.062, "Def_Rush_EPA": 0.038, "Pressure_Pct": 0.215, "Def_RZ_Stop_Pct": 0.428, "Dome": 1, "Cold_Weather_Drop": 0.056, "RB1_TD_Rate": 0.350, "WR1_TD_Rate": 0.295, "TE1_TD_Rate": 0.215, "QB_Rush_TD_Rate": 0.145, "Pass_Rate": 0.545, "HFA_Mod": 0.16, "QB_Nombre": "K. Murray", "RB1_Nombre": "J. Conner", "WR1_Nombre": "M. Harrison Jr.", "TE1_Nombre": "T. McBride"},
    {"Equipo": "Los Angeles Chargers", "Abrev": "LAC", "Pass_EPA": 0.105, "Rush_EPA": 0.025, "Pass_Success_Rate": 0.482, "Pace_Sec": 28.6, "RedZone_TD_Pct": 0.562, "Def_Pass_EPA": -0.042, "Def_Rush_EPA": -0.028, "Pressure_Pct": 0.248, "Def_RZ_Stop_Pct": 0.508, "Dome": 1, "Cold_Weather_Drop": 0.048, "RB1_TD_Rate": 0.340, "WR1_TD_Rate": 0.285, "TE1_TD_Rate": 0.175, "QB_Rush_TD_Rate": 0.085, "Pass_Rate": 0.535, "HFA_Mod": 0.12, "QB_Nombre": "J. Herbert", "RB1_Nombre": "J.K. Dobbins", "WR1_Nombre": "L. McConkey", "TE1_Nombre": "W. Dissly"},
    {"Equipo": "New Orleans Saints", "Abrev": "NO", "Pass_EPA": 0.052, "Rush_EPA": -0.008, "Pass_Success_Rate": 0.472, "Pace_Sec": 27.3, "RedZone_TD_Pct": 0.545, "Def_Pass_EPA": -0.038, "Def_Rush_EPA": -0.012, "Pressure_Pct": 0.226, "Def_RZ_Stop_Pct": 0.498, "Dome": 1, "Cold_Weather_Drop": 0.058, "RB1_TD_Rate": 0.370, "WR1_TD_Rate": 0.275, "TE1_TD_Rate": 0.195, "QB_Rush_TD_Rate": 0.055, "Pass_Rate": 0.565, "HFA_Mod": 0.25, "QB_Nombre": "D. Carr", "RB1_Nombre": "A. Kamara", "WR1_Nombre": "C. Olave", "TE1_Nombre": "J. Johnson"},
    {"Equipo": "Las Vegas Raiders", "Abrev": "LV", "Pass_EPA": -0.045, "Rush_EPA": -0.038, "Pass_Success_Rate": 0.448, "Pace_Sec": 27.8, "RedZone_TD_Pct": 0.515, "Def_Pass_EPA": -0.018, "Def_Rush_EPA": -0.008, "Pressure_Pct": 0.254, "Def_RZ_Stop_Pct": 0.482, "Dome": 1, "Cold_Weather_Drop": 0.046, "RB1_TD_Rate": 0.310, "WR1_TD_Rate": 0.275, "TE1_TD_Rate": 0.265, "QB_Rush_TD_Rate": 0.055, "Pass_Rate": 0.580, "HFA_Mod": 0.16, "QB_Nombre": "A. O'Connell", "RB1_Nombre": "A. Mattison", "WR1_Nombre": "J. Meyers", "TE1_Nombre": "B. Bowers"},
    {"Equipo": "Denver Broncos", "Abrev": "DEN", "Pass_EPA": 0.015, "Rush_EPA": -0.005, "Pass_Success_Rate": 0.460, "Pace_Sec": 27.6, "RedZone_TD_Pct": 0.540, "Def_Pass_EPA": -0.055, "Def_Rush_EPA": -0.025, "Pressure_Pct": 0.258, "Def_RZ_Stop_Pct": 0.515, "Dome": 0, "Cold_Weather_Drop": 0.016, "RB1_TD_Rate": 0.315, "WR1_TD_Rate": 0.305, "TE1_TD_Rate": 0.160, "QB_Rush_TD_Rate": 0.125, "Pass_Rate": 0.560, "HFA_Mod": 0.32, "QB_Nombre": "B. Nix", "RB1_Nombre": "J. Williams", "WR1_Nombre": "C. Sutton", "TE1_Nombre": "A. Trautman"},
    {"Equipo": "Tennessee Titans", "Abrev": "TEN", "Pass_EPA": -0.055, "Rush_EPA": -0.015, "Pass_Success_Rate": 0.440, "Pace_Sec": 28.1, "RedZone_TD_Pct": 0.518, "Def_Pass_EPA": -0.022, "Def_Rush_EPA": -0.035, "Pressure_Pct": 0.234, "Def_RZ_Stop_Pct": 0.502, "Dome": 0, "Cold_Weather_Drop": 0.032, "RB1_TD_Rate": 0.345, "WR1_TD_Rate": 0.295, "TE1_TD_Rate": 0.175, "QB_Rush_TD_Rate": 0.085, "Pass_Rate": 0.555, "HFA_Mod": 0.18, "QB_Nombre": "W. Levis", "RB1_Nombre": "T. Pollard", "WR1_Nombre": "C. Ridley", "TE1_Nombre": "C. Okonkwo"},
    {"Equipo": "New York Giants", "Abrev": "NYG", "Pass_EPA": -0.068, "Rush_EPA": -0.022, "Pass_Success_Rate": 0.438, "Pace_Sec": 27.9, "RedZone_TD_Pct": 0.502, "Def_Pass_EPA": 0.020, "Def_Rush_EPA": 0.028, "Pressure_Pct": 0.248, "Def_RZ_Stop_Pct": 0.468, "Dome": 0, "Cold_Weather_Drop": 0.022, "RB1_TD_Rate": 0.320, "WR1_TD_Rate": 0.335, "TE1_TD_Rate": 0.160, "QB_Rush_TD_Rate": 0.115, "Pass_Rate": 0.570, "HFA_Mod": 0.14, "QB_Nombre": "D. Jones", "RB1_Nombre": "T. Tracy Jr.", "WR1_Nombre": "M. Nabers", "TE1_Nombre": "T. Johnson"},
    {"Equipo": "Carolina Panthers", "Abrev": "CAR", "Pass_EPA": -0.105, "Rush_EPA": -0.032, "Pass_Success_Rate": 0.422, "Pace_Sec": 27.5, "RedZone_TD_Pct": 0.492, "Def_Pass_EPA": 0.055, "Def_Rush_EPA": 0.048, "Pressure_Pct": 0.205, "Def_RZ_Stop_Pct": 0.420, "Dome": 0, "Cold_Weather_Drop": 0.038, "RB1_TD_Rate": 0.355, "WR1_TD_Rate": 0.275, "TE1_TD_Rate": 0.170, "QB_Rush_TD_Rate": 0.085, "Pass_Rate": 0.565, "HFA_Mod": 0.14, "QB_Nombre": "B. Young", "RB1_Nombre": "C. Hubbard", "WR1_Nombre": "D. Johnson", "TE1_Nombre": "J. Sanders"},
]


# ==============================================================================
# 2. MOTOR CLOUD INTEGRADO: SINCRONIZACIÓN AUTOMÁTICA CON NFLVERSE (nfl_data_py)
# ==============================================================================
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


def _calcular_metricas_equipos_pbp(pbp: pd.DataFrame) -> pd.DataFrame:
    df = pbp.copy()
    if "season_type" in df.columns:
        df = df[df["season_type"].isin(["REG", "POST"])]

    df["posteam"] = normalizar_abrev(df["posteam"])
    df["defteam"] = normalizar_abrev(df["defteam"])
    df = df[df["posteam"].isin(NFL_TEAMS_META.keys()) & df["defteam"].isin(NFL_TEAMS_META.keys())]

    for col_flag in ["qb_spike", "qb_kneel", "two_point_attempt"]:
        if col_flag in df.columns:
            df = df[df[col_flag].fillna(0) == 0]

    if "pass_attempt" in df.columns and "rush_attempt" in df.columns:
        df["is_pass"] = (df["pass_attempt"].fillna(0) == 1) | (df.get("play_type", "") == "pass")
        df["is_rush"] = (df["rush_attempt"].fillna(0) == 1) | (df.get("play_type", "") == "run")
    else:
        df["is_pass"] = df["play_type"] == "pass"
        df["is_rush"] = df["play_type"] == "run"

    scrimmage = df[(df["is_pass"] | df["is_rush"]) & df["epa"].notna()].copy()
    pass_plays = scrimmage[scrimmage["is_pass"]].copy()
    rush_plays = scrimmage[scrimmage["is_rush"]].copy()

    if "success" not in pass_plays.columns:
        pass_plays["success"] = (pass_plays["epa"] > 0).astype(float)

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

    pace_series = {}
    if {"game_id", "drive", "game_seconds_remaining"}.issubset(scrimmage.columns):
        scr_sorted = scrimmage.sort_values(["game_id", "drive", "game_seconds_remaining"], ascending=[True, True, False])
        scr_sorted["sec_diff"] = scr_sorted.groupby(["game_id", "posteam", "drive"])["game_seconds_remaining"].diff(-1)
        valid_pace = scr_sorted[(scr_sorted["sec_diff"] >= 12) & (scr_sorted["sec_diff"] <= 40)]
        pace_raw = valid_pace.groupby("posteam")["sec_diff"].mean()
        if not pace_raw.empty and pace_raw.mean() > 0:
            scale_factor = 27.4 / pace_raw.mean()
            for tm, val in pace_raw.items():
                pace_series[tm] = float(np.clip(val * scale_factor, 25.2, 30.2))

    plays_per_game = scrimmage.groupby(["posteam", "game_id"]).size().groupby("posteam").mean()
    for tm in NFL_TEAMS_META.keys():
        if tm not in pace_series or np.isnan(pace_series[tm]):
            ppg = float(plays_per_game.get(tm, 63.5))
            pace_series[tm] = float(np.clip(1740.0 / max(52.0, ppg), 25.4, 30.0))

    off_summary["Pace_Sec"] = pd.Series(pace_series)

    if {"game_id", "drive", "yardline_100", "touchdown"}.issubset(scrimmage.columns):
        rz_plays = scrimmage[scrimmage["yardline_100"].fillna(99) <= 20].copy()
        if "td_team" in rz_plays.columns:
            rz_plays["off_td"] = ((rz_plays["touchdown"].fillna(0) == 1) & (rz_plays["td_team"] == rz_plays["posteam"])).astype(int)
        else:
            rz_plays["off_td"] = (rz_plays["touchdown"].fillna(0) == 1).astype(int)

        rz_drives_off = rz_plays.groupby(["posteam", "game_id", "drive"])["off_td"].max().reset_index()
        rz_off_pct = rz_drives_off.groupby("posteam")["off_td"].mean()

        rz_drives_def = rz_plays.groupby(["defteam", "game_id", "drive"])["off_td"].max().reset_index()
        rz_def_stop_pct = 1.0 - rz_drives_def.groupby("defteam")["off_td"].mean()
    else:
        rz_off_pct = pd.Series(0.565, index=list(NFL_TEAMS_META.keys()))
        rz_def_stop_pct = pd.Series(0.485, index=list(NFL_TEAMS_META.keys()))

    off_summary["RedZone_TD_Pct"] = rz_off_pct.reindex(off_summary.index).fillna(0.565).clip(0.420, 0.720)

    def_pass = pass_plays.groupby("defteam").agg(
        Def_Pass_EPA=("epa", "mean"),
        sacks=("sack", "sum") if "sack" in pass_plays.columns else ("epa", lambda s: 0),
        qb_hits=("qb_hit", "sum") if "qb_hit" in pass_plays.columns else ("epa", lambda s: 0),
        dropbacks=("epa", "count"),
    )
    def_rush = rush_plays.groupby("defteam").agg(Def_Rush_EPA=("epa", "mean"))
    def_summary = def_pass.join(def_rush, how="outer").fillna(0.0)

    if "was_pressure" in pass_plays.columns and pass_plays["was_pressure"].notna().sum() > 100:
        press_direct = pass_plays.groupby("defteam")["was_pressure"].mean()
        def_summary["Pressure_Pct"] = press_direct.reindex(def_summary.index).fillna(0.245).clip(0.185, 0.315)
    else:
        disruption_rate = (def_summary["sacks"] + 0.85 * def_summary["qb_hits"]) / def_summary["dropbacks"].replace(0, np.nan)
        mean_disrupt = disruption_rate.mean()
        scale_press = (0.248 / mean_disrupt) if (mean_disrupt and mean_disrupt > 0) else 1.65
        def_summary["Pressure_Pct"] = (disruption_rate * scale_press).fillna(0.245).clip(0.190, 0.310)

    def_summary["Def_RZ_Stop_Pct"] = rz_def_stop_pct.reindex(def_summary.index).fillna(0.485).clip(0.380, 0.620)

    return off_summary.join(
        def_summary[["Def_Pass_EPA", "Def_Rush_EPA", "Pressure_Pct", "Def_RZ_Stop_Pct"]],
        how="outer",
    )


def _calcular_props_jugadores_pbp(pbp: pd.DataFrame, rosters: pd.DataFrame) -> dict[str, dict]:
    df = pbp.copy()
    if "season_type" in df.columns:
        df = df[df["season_type"].isin(["REG", "POST"])]

    df["posteam"] = normalizar_abrev(df["posteam"])
    df = df[df["posteam"].isin(NFL_TEAMS_META.keys())]

    pos_map = {}
    name_map = {}
    if rosters is not None and not rosters.empty:
        r_df = rosters.copy()
        id_col = "gsis_id" if "gsis_id" in r_df.columns else ("player_id" if "player_id" in r_df.columns else None)
        pos_col = "position" if "position" in r_df.columns else ("depth_chart_position" if "depth_chart_position" in r_df.columns else None)
        name_col = "short_name" if "short_name" in r_df.columns else ("player_name" if "player_name" in r_df.columns else "full_name")

        if id_col and pos_col:
            for _, row in r_df.dropna(subset=[id_col, pos_col]).iterrows():
                pid = str(row[id_col])
                pos_map[pid] = str(row[pos_col]).upper().strip()
                if name_col in r_df.columns and pd.notna(row[name_col]):
                    name_map[pid] = abreviar_nombre_jugador(str(row[name_col]))

    team_games = df.groupby("posteam")["game_id"].nunique().replace(0, 1)
    pass_tds_team = df.groupby("posteam")["pass_touchdown"].sum() if "pass_touchdown" in df.columns else pd.Series(25, index=NFL_TEAMS_META.keys())
    rush_tds_team = df.groupby("posteam")["rush_touchdown"].sum() if "rush_touchdown" in df.columns else pd.Series(15, index=NFL_TEAMS_META.keys())
    total_tds_team = (pass_tds_team.add(rush_tds_team, fill_value=0)).replace(0, 1)
    tds_per_game_team = (total_tds_team / team_games).clip(1.5, 4.2)

    qb_passes = df[df["passer_player_id"].notna()].groupby(["posteam", "passer_player_id"]).agg(
        att=("pass_attempt", "sum"),
        games_qb=("game_id", "nunique"),
        name=("passer_player_name", "first"),
    ).reset_index()

    rush_df = df[df["rusher_player_id"].notna()].copy()
    rush_df["is_rz"] = (rush_df["yardline_100"].fillna(99) <= 20).astype(int)
    rush_stats = rush_df.groupby(["posteam", "rusher_player_id"]).agg(
        carries=("rush_attempt", "sum"),
        rz_carries=("is_rz", "sum"),
        rush_td=("rush_touchdown", "sum"),
        games_rush=("game_id", "nunique"),
        name=("rusher_player_name", "first"),
    ).reset_index().rename(columns={"rusher_player_id": "player_id", "name": "rush_name"})

    rec_df = df[df["receiver_player_id"].notna()].copy()
    rec_df["is_rz"] = (rec_df["yardline_100"].fillna(99) <= 20).astype(int)
    rec_stats = rec_df.groupby(["posteam", "receiver_player_id"]).agg(
        targets=("pass_attempt", "sum"),
        rz_targets=("is_rz", "sum"),
        rec_td=("pass_touchdown", "sum"),
        games_rec=("game_id", "nunique"),
        name=("receiver_player_name", "first"),
    ).reset_index().rename(columns={"receiver_player_id": "player_id", "name": "rec_name"})

    skill = pd.merge(rush_stats, rec_stats, on=["posteam", "player_id"], how="outer").fillna(0)
    skill["player_name"] = np.where(
        skill["rec_name"].astype(str) != "0",
        skill["rec_name"].astype(str),
        skill["rush_name"].astype(str),
    )
    skill["player_name"] = skill.apply(
        lambda r: name_map.get(str(r["player_id"]), abreviar_nombre_jugador(str(r["player_name"]))),
        axis=1,
    )
    skill["games_active"] = np.maximum(skill["games_rush"], skill["games_rec"]).clip(lower=1)
    skill["total_td"] = skill["rush_td"] + skill["rec_td"]
    skill["rz_touches"] = skill["rz_carries"] + skill["rz_targets"]
    skill["total_opps"] = skill["carries"] + skill["targets"]

    def resolver_posicion(row: pd.Series) -> str:
        pid = str(row["player_id"])
        if pid in pos_map and pos_map[pid] in {"QB", "RB", "FB", "WR", "TE"}:
            return "RB" if pos_map[pid] == "FB" else pos_map[pid]
        if row["carries"] > row["targets"] * 1.5:
            return "RB"
        return "WR"

    skill["pos"] = skill.apply(resolver_posicion, axis=1)

    props_por_equipo = {}
    for tm in NFL_TEAMS_META.keys():
        tm_td_pg = float(tds_per_game_team.get(tm, 2.45))
        tm_skill = skill[skill["posteam"] == tm].copy()

        tm_qbs = qb_passes[qb_passes["posteam"] == tm].sort_values("att", ascending=False)
        if not tm_qbs.empty:
            qb_id = str(tm_qbs.iloc[0]["passer_player_id"])
            qb_games = max(1.0, float(tm_qbs.iloc[0]["games_qb"]))
            qb_name = name_map.get(qb_id, abreviar_nombre_jugador(str(tm_qbs.iloc[0]["name"])))
            qb_rush_row = tm_skill[tm_skill["player_id"] == qb_id]
            qb_r_td_pg = (float(qb_rush_row["rush_td"].sum()) / qb_games) if not qb_rush_row.empty else 0.0
            qb_rz_c_pg = (float(qb_rush_row["rz_carries"].sum()) / qb_games) if not qb_rush_row.empty else 0.0
            xtd_qb_pg = 0.65 * qb_r_td_pg + 0.35 * (qb_rz_c_pg * 0.22)
            raw_qb_rate = xtd_qb_pg / tm_td_pg
            qb_td_rate = float(np.clip(0.75 * raw_qb_rate + 0.25 * 0.095, 0.035, 0.285))
        else:
            qb_name = f"{tm} QB1"
            qb_td_rate = 0.085

        def seleccionar_playmaker(pos_target: str, prior_rate: float, min_r: float, max_r: float) -> tuple[str, float]:
            sub = tm_skill[tm_skill["pos"] == pos_target].copy()
            if sub.empty:
                return f"{tm} {pos_target}1", prior_rate
            sub["score_lider"] = sub["total_opps"] + sub["rz_touches"] * 3.5 + sub["total_td"] * 8.0
            sub = sub.sort_values("score_lider", ascending=False)
            top = sub.iloc[0]
            p_name = str(top["player_name"])
            g_act = max(1.0, float(top["games_active"]))
            td_pg = float(top["total_td"]) / g_act
            rz_pg = float(top["rz_touches"]) / g_act
            xtd_player_pg = 0.62 * td_pg + 0.38 * (rz_pg * 0.21)
            obs_rate = xtd_player_pg / tm_td_pg
            blended_rate = 0.72 * obs_rate + 0.28 * prior_rate
            return p_name, float(np.clip(blended_rate, min_r, max_r))

        rb1_name, rb1_rate = seleccionar_playmaker("RB", 0.335, 0.220, 0.460)
        wr1_name, wr1_rate = seleccionar_playmaker("WR", 0.295, 0.200, 0.385)
        te1_name, te1_rate = seleccionar_playmaker("TE", 0.195, 0.135, 0.310)

        props_por_equipo[tm] = {
            "QB_Nombre": qb_name,
            "RB1_Nombre": rb1_name,
            "WR1_Nombre": wr1_name,
            "TE1_Nombre": te1_name,
            "RB1_TD_Rate": round(rb1_rate, 3),
            "WR1_TD_Rate": round(wr1_rate, 3),
            "TE1_TD_Rate": round(te1_rate, 3),
            "QB_Rush_TD_Rate": round(qb_td_rate, 3),
        }

    return props_por_equipo


@st.cache_data(ttl=86400, show_spinner=False)
def obtener_dataset_cloud_nfl(
    season_target: int | None = None,
    forzar_remoto: bool = False,
    csv_path: str = "nfl_stats_completo.csv",
) -> tuple[pd.DataFrame, dict]:
    """
    Motor de datos Cloud con caché automático de 24 horas (ttl=86400s):
    1. Si 'forzar_remoto=True' o si no existe el CSV y nfl_data_py está disponible,
       descarga el Play-by-Play y Rosters vigentes directamente desde nflverse en la nube,
       procesa las 32 franquicias y guarda nfl_stats_completo.csv.
    2. Si ya existe nfl_stats_completo.csv y no se forzó recarga, lo lee al instante.
    3. Si ocurre cualquier fallo de red o falta librería, usa el respaldo base sin caer.
    """
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # Intento de sincronización en vivo con nflverse (nfl_data_py)
    if NFL_DATA_PY_AVAILABLE and (forzar_remoto or not os.path.exists(csv_path)):
        hoy = datetime.date.today()
        default_season = hoy.year if hoy.month >= 9 else hoy.year - 1
        candidatos = [season_target] if season_target is not None else [default_season, default_season - 1, default_season - 2]

        pbp_df = pd.DataFrame()
        season_used = candidatos[0]
        for yr in candidatos:
            try:
                df_temp = nfl.import_pbp_data([int(yr)], downcast=True)
                if df_temp is not None and len(df_temp) > 1500:
                    pbp_df = df_temp
                    season_used = int(yr)
                    break
            except Exception:
                continue

        if not pbp_df.empty:
            rosters_df = pd.DataFrame()
            for yr_r in [season_used, season_used - 1]:
                try:
                    rosters_df = nfl.import_seasonal_rosters([int(yr_r)])
                    if rosters_df is not None and not rosters_df.empty:
                        break
                except Exception:
                    try:
                        rosters_df = nfl.import_players()
                        if rosters_df is not None and not rosters_df.empty:
                            break
                    except Exception:
                        pass

            team_metrics = _calcular_metricas_equipos_pbp(pbp_df)
            player_props = _calcular_props_jugadores_pbp(pbp_df, rosters_df)

            filas_salida = []
            for abrev, meta in NFL_TEAMS_META.items():
                tm_row = team_metrics.loc[abrev] if abrev in team_metrics.index else pd.Series(dtype=float)
                p_row = player_props.get(abrev, {})

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
                    "RB1_TD_Rate": round(float(p_row.get("RB1_TD_Rate", 0.335)), 3),
                    "WR1_TD_Rate": round(float(p_row.get("WR1_TD_Rate", 0.295)), 3),
                    "TE1_TD_Rate": round(float(p_row.get("TE1_TD_Rate", 0.195)), 3),
                    "QB_Rush_TD_Rate": round(float(p_row.get("QB_Rush_TD_Rate", 0.085)), 3),
                    "Pass_Rate": round(float(tm_row.get("Pass_Rate", 0.565)), 3),
                    "HFA_Mod": round(float(meta["HFA_Mod"]), 2),
                    "QB_Nombre": p_row.get("QB_Nombre", f"{abrev} QB1"),
                    "RB1_Nombre": p_row.get("RB1_Nombre", f"{abrev} RB1"),
                    "WR1_Nombre": p_row.get("WR1_Nombre", f"{abrev} WR1"),
                    "TE1_Nombre": p_row.get("TE1_Nombre", f"{abrev} TE1"),
                })

            df_live = pd.DataFrame(filas_salida)
            try:
                df_live.to_csv(csv_path, index=False, encoding="utf-8")
            except Exception:
                pass

            meta_info = {
                "origen": f"NFLVERSE LIVE ({season_used})",
                "jugadas": len(pbp_df),
                "actualizado": timestamp_str,
                "live": True,
            }
            return df_live.set_index("Equipo"), meta_info

    # Lectura desde CSV existente o generación desde respaldo base
    if not os.path.exists(csv_path):
        df_fallback = pd.DataFrame(DEFAULT_TEAMS_DATA)
        try:
            df_fallback.to_csv(csv_path, index=False, encoding="utf-8")
        except Exception:
            pass
    else:
        df_fallback = pd.read_csv(csv_path)

    if "Equipo" in df_fallback.columns:
        df_fallback = df_fallback.set_index("Equipo")

    meta_info = {
        "origen": "CSV CACHÉ / BASE SYNDICATE",
        "jugadas": 0,
        "actualizado": timestamp_str,
        "live": False,
    }
    return df_fallback, meta_info


# ==============================================================================
# 3. CALCULADORA DE FAIR ODDS (+EV) Y UTILIDADES MATEMÁTICAS
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
# 4. MOTOR CUANTITATIVO SHARP NFL (EPA + MONTECARLO + KEY NUMBERS + PROPS)
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
        return str(row["Abrev"])
    palabras = equipo_nombre.split()
    return "".join(p[0] for p in palabras[-2:]).upper()


def simular_partido_nfl(
    equipo_local: str,
    equipo_visita: str,
    df: pd.DataFrame,
    clima_frio_activo: bool = False,
    linea_total_mercado: float = 45.5,
    n_sims: int = 8000,
) -> dict:
    loc = df.loc[equipo_local]
    vis = df.loc[equipo_visita]

    # --- A. RITMO Y VOLUMEN DE JUGADAS (PLAYS) ---
    pace_loc = float(loc["Pace_Sec"])
    pace_vis = float(vis["Pace_Sec"])
    pace_suma = pace_loc + pace_vis
    plays_por_equipo = 63.5 * (54.8 / max(46.0, pace_suma))
    plays_totales_juego = plays_por_equipo * 2.0

    pass_rate_loc = float(loc["Pass_Rate"]) if "Pass_Rate" in loc else 0.565
    pass_rate_vis = float(vis["Pass_Rate"]) if "Pass_Rate" in vis else 0.565

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
    hfa_mod_estadio = float(loc["HFA_Mod"]) if "HFA_Mod" in loc else 0.18
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

    base_pts_loc = plays_por_equipo * 0.348
    base_pts_vis = plays_por_equipo * 0.348

    pts_proj_loc = (
        base_pts_loc
        + (epa_play_loc * plays_por_equipo * 0.82)
        + rz_pts_adj_loc
        + (hfa_total / 2.0)
        + dome_total_boost
    )
    pts_proj_vis = (
        base_pts_vis
        + (epa_play_vis * plays_por_equipo * 0.82)
        + rz_pts_adj_vis
        - (hfa_total / 2.0)
        + dome_total_boost
    )

    pts_proj_loc = float(np.clip(pts_proj_loc, 12.5, 36.5))
    pts_proj_vis = float(np.clip(pts_proj_vis, 11.5, 35.5))

    total_proyectado = round(pts_proj_loc + pts_proj_vis, 1)
    spread_local = round(-(pts_proj_loc - pts_proj_vis), 1)

    # --- E. SIMULACIÓN MONTECARLO (POSESIONES NFL) + MATRIZ KEY NUMBERS ---
    seed_val = abs(hash(f"{equipo_local}_{equipo_visita}_{clima_frio_activo}")) % (2**31 - 1)
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
            "Marcador": f"{c[1]} - {c[2]}",
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
                "xTD": round(lam_player, 2),
                "Prob": round(prob_atd * 100.0, 1),
                "Prob_Raw": prob_atd,
                "Fair_Dec": dec_odd,
                "Fair_Am": am_odd,
            })
        return props_out

    abrev_loc = obtener_iniciales(equipo_local, loc)
    abrev_vis = obtener_iniciales(equipo_visita, vis)

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
# 5. GESTIÓN DE SESSION STATE Y SINCRONIZACIÓN AUTOMÁTICA EN LA NUBE
# ==============================================================================
if "forzar_sync_cloud" not in st.session_state:
    st.session_state.forzar_sync_cloud = False

if "temporada_nfl_sel" not in st.session_state:
    hoy_init = datetime.date.today()
    st.session_state.temporada_nfl_sel = hoy_init.year if hoy_init.month >= 9 else hoy_init.year - 1

with st.spinner("🛰️ Sincronizando telemetría oficial NFL (nflfastR / nflverse Cloud)..."):
    df_nfl, meta_sync = obtener_dataset_cloud_nfl(
        season_target=st.session_state.temporada_nfl_sel,
        forzar_remoto=st.session_state.forzar_sync_cloud,
    )

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

if "expander_open" not in st.session_state:
    st.session_state.expander_open = True

if "scan_ejecutado" not in st.session_state:
    st.session_state.scan_ejecutado = False

if "num_juegos_activos" not in st.session_state:
    st.session_state.num_juegos_activos = 8

if "clima_invierno" not in st.session_state:
    st.session_state.clima_invierno = False

if "linea_mercado_base" not in st.session_state:
    st.session_state.linea_mercado_base = 45.5

if "partidos_seleccionados" not in st.session_state:
    partidos_init = []
    for idx in range(16):
        loc_def, vis_def = DEFAULT_16_MATCHUPS[idx % len(DEFAULT_16_MATCHUPS)]
        if loc_def not in lista_equipos:
            loc_def = lista_equipos[0]
        if vis_def not in lista_equipos:
            vis_def = lista_equipos[min(1, len(lista_equipos) - 1)]
        partidos_init.append({"local": loc_def, "visita": vis_def})
    st.session_state.partidos_seleccionados = partidos_init


# ==============================================================================
# 6. BARRA LATERAL: CENTRO DE SINCRONIZACIÓN CLOUD (STREAMLIT CLOUD + GITHUB)
# ==============================================================================
with st.sidebar:
    st.markdown(
        """
        <div style='font-family: Orbitron, sans-serif; font-size: 1.05rem; font-weight: 800; color: #00F0FF; letter-spacing: 1px;'>
            ⚡ SHARP SYNDICATE TERMINAL
        </div>
        <div style='font-family: JetBrains Mono, monospace; font-size: 0.74rem; color: #8A99AD; margin-bottom: 14px;'>
            CLOUD ENGINE: NFLVERSE + MONTECARLO
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("🔓 Abrir Configurador de Semana", use_container_width=True):
        st.session_state.expander_open = True

    st.markdown("### ☁️ Sincronización nflfastR Cloud")
    anio_actual = datetime.date.today().year
    opciones_temp = [anio_actual, anio_actual - 1, anio_actual - 2]
    idx_temp = opciones_temp.index(st.session_state.temporada_nfl_sel) if st.session_state.temporada_nfl_sel in opciones_temp else 0
    temp_elegida = st.selectbox(
        "Temporada Oficial nflverse",
        options=opciones_temp,
        index=idx_temp,
    )

    if st.button("🔄 Sincronizar Datos en Vivo (nflfastR)", use_container_width=True):
        st.session_state.temporada_nfl_sel = temp_elegida
        st.session_state.forzar_sync_cloud = True
        obtener_dataset_cloud_nfl.clear()
        st.rerun()

    # Indicador de estado de la fuente en la nube
    estado_color = "#00E676" if meta_sync["live"] else "#00F0FF"
    jugadas_str = f" • {meta_sync['jugadas']:,} snaps" if meta_sync["jugadas"] > 0 else ""
    st.markdown(
        f"""
        <div style='background: rgba(12,19,34,0.9); border: 1px solid {estado_color}; border-radius: 8px; padding: 8px 10px; font-family: JetBrains Mono, monospace; font-size: 0.72rem; margin-bottom: 12px;'>
            <div style='color: {estado_color}; font-weight: 700;'>● FUENTE: {meta_sync['origen']}</div>
            <div style='color: #8A99AD; margin-top: 3px;'>Sync: {meta_sync['actualizado']}{jugadas_str}</div>
            <div style='color: #8A99AD;'>Caché Automático Cloud: 24h (TTL)</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not NFL_DATA_PY_AVAILABLE:
        st.caption("💡 Agrega `nfl_data_py` y `pyarrow` a tu `requirements.txt` en GitHub para habilitar la descarga directa de `nflverse`.")

    ver_tabla_csv = st.checkbox("Mostrar Dataset Activo (`nfl_stats_completo.csv`)", value=False)

    st.download_button(
        label="⬇️ Descargar CSV Actualizado",
        data=df_nfl.reset_index().to_csv(index=False).encode("utf-8"),
        file_name="nfl_stats_completo.csv",
        mime="text/csv",
        use_container_width=True,
    )


# ==============================================================================
# 7. ENCABEZADO DE LA TERMINAL Y VISTA DEL DATASET ACTIVO
# ==============================================================================
st.markdown(
    f"""
    <div class="terminal-banner">
        <div class="terminal-title">
            <span>🏈 TERMINAL SHARP: NFL QUANT SCANNER</span>
            <span class="live-pill">● {meta_sync['origen']}</span>
        </div>
        <div class="terminal-subtitle">
            BLOOMBERG SPORTSBOOK ANALYTICS // EPA MATCHUP MATRIX • MONTECARLO KEY-NUMBER CLUSTERING • POISSON TD PROPS • FAIR ODDS (+EV)
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if ver_tabla_csv:
    with st.expander("📂 DATASET ACTIVO EN MEMORIA (`nfl_stats_completo.csv`)", expanded=True):
        st.dataframe(df_nfl, use_container_width=True)


# ==============================================================================
# 8. FORMULARIO DE LOS 16 JUEGOS SEMANALES (st.form + st.expander auto-close)
# ==============================================================================
def callback_cerrar_expander():
    st.session_state.expander_open = False
    st.session_state.scan_ejecutado = True


with st.expander(
    "🎛️ CONFIGURADOR DEL GAME WEEK SCANNER (HASTA 16 PARTIDOS NFL)",
    expanded=st.session_state.expander_open,
):
    with st.form("form_semana_nfl"):
        col_cfg1, col_cfg2, col_cfg3 = st.columns([1.2, 1.2, 1.6])
        with col_cfg1:
            num_juegos = st.slider(
                "Número de Juegos de la Semana a Escanear",
                min_value=1,
                max_value=16,
                value=st.session_state.num_juegos_activos,
                step=1,
            )
        with col_cfg2:
            linea_total_ref = st.select_slider(
                "Línea de Mercado Referencia Over/Under (Pts)",
                options=[43.5, 44.0, 44.5, 45.0, 45.5, 46.0, 46.5, 47.0, 47.5],
                value=st.session_state.linea_mercado_base,
            )
        with col_cfg3:
            clima_frio = st.checkbox(
                "❄️ Activar Factor de Clima Invernal / Viento en Estadios Abiertos (Cold Weather Drop)",
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
                    vis_sel = st.selectbox(
                        f"Visita #{game_i + 1}",
                        options=lista_equipos,
                        index=lista_equipos.index(default_vis),
                        key=f"vis_select_{game_i}",
                    )
                    loc_sel = st.selectbox(
                        f"Local #{game_i + 1}",
                        options=lista_equipos,
                        index=lista_equipos.index(default_loc),
                        key=f"loc_select_{game_i}",
                    )
                    nuevos_partidos.append({"local": loc_sel, "visita": vis_sel})

        submitted = st.form_submit_button(
            "🚀 EJECUTAR ESCANEO CUANTITATIVO DE LA SEMANA (SHARP SCAN)",
            use_container_width=True,
            on_click=callback_cerrar_expander,
        )

        if submitted:
            st.session_state.num_juegos_activos = num_juegos
            st.session_state.linea_mercado_base = linea_total_ref
            st.session_state.clima_invierno = clima_frio
            st.session_state.partidos_seleccionados = nuevos_partidos


# ==============================================================================
# 9. VALIDACIÓN DE ERRORES Y EJECUCIÓN DEL ESCANEO SEMANAL
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
        partidos_validos.append((idx + 1, p["local"], p["visita"]))

if errores_mismo_equipo:
    for err_msg in errores_mismo_equipo:
        st.error(err_msg)

if not partidos_validos:
    st.warning("Configura al menos un partido válido (Local ≠ Visita) para visualizar el escaneo cuantitativo.")
    st.stop()

resultados_semana = [
    simular_partido_nfl(
        equipo_local=loc_team,
        equipo_visita=vis_team,
        df=df_nfl,
        clima_frio_activo=st.session_state.clima_invierno,
        linea_total_mercado=st.session_state.linea_mercado_base,
    )
    for _, loc_team, vis_team in partidos_validos
]


# ==============================================================================
# 10. RADAR EJECUTIVO DE LA SEMANA (TOP 4 PICKS DEL SINDICATO)
# ==============================================================================
mejor_lock = None
mejor_lock_score = -1.0
for r in resultados_semana:
    if r["Prob_Win_Loc"] >= r["Prob_Win_Vis"]:
        score_cand = 0.60 * r["Prob_Win_Loc"] + 0.40 * r["Prob_Cover_Loc"]
        cand = {
            "Equipo": r["Local"],
            "Rival": r["Visita"],
            "Mercado": f"ML ({r['ML_Am_Loc']}) / Spread {r['Spread_Mercado_Ref']:+.1f}",
            "Prob_ML": r["Prob_Win_Loc"],
            "Fair_Dec": r["ML_Dec_Loc"],
            "Fair_Am": r["ML_Am_Loc"],
            "Spread_Proj": f"{r['Spread_Justo_Loc']:+.1f}",
            "Marcador": r["Marcador_Exacto"],
        }
    else:
        score_cand = 0.60 * r["Prob_Win_Vis"] + 0.40 * r["Prob_Cover_Vis"]
        cand = {
            "Equipo": r["Visita"],
            "Rival": r["Local"],
            "Mercado": f"ML ({r['ML_Am_Vis']}) / Spread {-r['Spread_Mercado_Ref']:+.1f}",
            "Prob_ML": r["Prob_Win_Vis"],
            "Fair_Dec": r["ML_Dec_Vis"],
            "Fair_Am": r["ML_Am_Vis"],
            "Spread_Proj": f"{-r['Spread_Justo_Loc']:+.1f}",
            "Marcador": r["Marcador_Exacto"],
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
        todos_los_props.append(p_copy)
anotador_estrella = max(todos_los_props, key=lambda x: x["Prob_Raw"])

mejor_underdog = None
mejor_dog_prob = -1.0
for r in resultados_semana:
    if r["Spread_Mercado_Ref"] < 0:
        dog_team = r["Visita"]
        dog_line = abs(r["Spread_Mercado_Ref"])
        dog_cover_prob = r["Prob_Cover_Vis"]
        dog_fair_spread = -r["Spread_Justo_Loc"]
        dog_dec = r["SP_Dec_Vis"]
        dog_am = r["SP_Am_Vis"]
        match_str = f"{r['Abrev_Vis']} @ {r['Abrev_Loc']}"
    else:
        dog_team = r["Local"]
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
            "Matchup": match_str,
            "Linea_Dog": f"+{dog_line:.1f}",
            "Spread_Modelo": f"{dog_fair_spread:+.1f}",
            "Prob_Cover": dog_cover_prob,
            "Fair_Dec": dog_dec,
            "Fair_Am": dog_am,
        }

st.markdown('<div class="radar-section-title">📡 RADAR EJECUTIVO DE LA SEMANA // TOP SYNDICATE EDGES</div>', unsafe_allow_html=True)

r_col1, r_col2, r_col3, r_col4 = st.columns(4)

with r_col1:
    st.markdown(
        f"""
        <div class="radar-card lock">
            <div class="radar-tag">🔒 EL LOCK DE LA SEMANA</div>
            <div class="radar-pick">{mejor_lock['Equipo']}</div>
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
            <div class="radar-pick">{mejor_total['Partido']}: {mejor_total['Pick']}</div>
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
            <div class="radar-pick">{anotador_estrella['Jugador']} ({anotador_estrella['Abrev']} - {anotador_estrella['Rol']})</div>
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
            <div class="radar-pick">{mejor_underdog['Equipo']} ({mejor_underdog['Linea_Dog']})</div>
            <div class="radar-metrics">Cobertura: {mejor_underdog['Prob_Cover']}% | Fair: {mejor_underdog['Fair_Dec']} ({mejor_underdog['Fair_Am']})</div>
            <div class="radar-sub">Línea Justa Modelo: {mejor_underdog['Spread_Modelo']} • {mejor_underdog['Matchup']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ==============================================================================
# 11. DESGLOSE POR JUEGO (SCOREBOARD TV HEADER + 3 FILAS + EXPANDER GRÁFICO)
# ==============================================================================
st.markdown('<div class="radar-section-title">📊 ESCÁNER CUANTITATIVO POR PARTIDO (GAME WEEK BOARD)</div>', unsafe_allow_html=True)

for idx_game, res in enumerate(resultados_semana, start=1):
    st.markdown(
        f"""
        <div class="tv-scoreboard">
            <div class="tv-top-bar">
                <span>JUEGO #{idx_game:02d} // {res['Entorno_Tag']}</span>
                <span>RITMO COMBINADO: {res['Pace_Suma']}s ({res['Plays_Totales']} SNAPS) // HFA LOCAL: +{res['HFA_Pts']} PTS</span>
                <span>CLUSTER KEY NUMBER: {res['Marcador_Exacto']}</span>
            </div>
            <div class="tv-main-grid">
                <div class="team-side">
                    <div class="team-badge">{res['Abrev_Vis']}</div>
                    <div>
                        <div class="team-name-tv">{res['Visita']} (VISITA)</div>
                        <div class="team-epa-sub">EPA/Play Proy: {res['EPA_Play_Vis']:+.3f} | RZ Eff: {res['RZ_Eff_Vis']}%</div>
                    </div>
                </div>
                <div class="score-center-box">
                    <div class="projected-score-tv">{res['Pts_Vis']:.1f}  —  {res['Pts_Loc']:.1f}</div>
                    <div class="projected-total-pill">MARCADOR EXACTO: {res['Marcador_Vis']} - {res['Marcador_Loc']}  |  TOTAL PROY: {res['Total_Proyectado']} PTS</div>
                </div>
                <div class="team-side right">
                    <div>
                        <div class="team-name-tv">{res['Local']} (LOCAL)</div>
                        <div class="team-epa-sub">EPA/Play Proy: {res['EPA_Play_Loc']:+.3f} | RZ Eff: {res['RZ_Eff_Loc']}%</div>
                    </div>
                    <div class="team-badge home">{res['Abrev_Loc']}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
        top_clusters_str = " | ".join([f"{m['Marcador']} ({m['Prob']}%)" for m in res["Top_3_Marcadores"]])
        st.markdown(
            f"""
            <div class="quant-card">
                <div class="quant-card-header">🏆 FILA 1B // MONEYLINE (VICTORIA DIRECTA) & CLUSTERS</div>
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

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    f2_col1, f2_col2 = st.columns(2)
    with f2_col1:
        edge_ou = round(res["Total_Proyectado"] - res["Linea_Total_Mercado"], 1)
        recomendacion_ou = f"OVER {res['Linea_Total_Mercado']}" if edge_ou >= 0 else f"UNDER {res['Linea_Total_Mercado']}"
        st.markdown(
            f"""
            <div class="quant-card">
                <div class="quant-card-header">⚡ FILA 2A // OVER / UNDER TOTAL PROYECTADO DEL JUEGO</div>
                <div class="metric-row">
                    <span class="metric-label">Total Proyectado vs Línea Ref ({res['Linea_Total_Mercado']})</span>
                    <span class="metric-val">{res['Total_Proyectado']} pts (Edge: {edge_ou:+.1f} pts → {recomendacion_ou})</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">OVER {res['Linea_Total_Mercado']} Puntos</span>
                    <span>
                        <span class="metric-val">{res['Prob_Over']}%</span>
                        <span class="odds-chip green">Fair: {res['OU_Dec_Over']} ({res['OU_Am_Over']})</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">UNDER {res['Linea_Total_Mercado']} Puntos</span>
                    <span>
                        <span class="metric-val">{res['Prob_Under']}%</span>
                        <span class="odds-chip">Fair: {res['OU_Dec_Under']} ({res['OU_Am_Under']})</span>
                    </span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with f2_col2:
        tt_ref_loc = round(res["Pts_Loc"] * 2.0) / 2.0 - 0.5 if res["Pts_Loc"] % 1 == 0 else round(res["Pts_Loc"] - 0.5) + 0.5
        tt_ref_vis = round(res["Pts_Vis"] * 2.0) / 2.0 - 0.5 if res["Pts_Vis"] % 1 == 0 else round(res["Pts_Vis"] - 0.5) + 0.5
        st.markdown(
            f"""
            <div class="quant-card">
                <div class="quant-card-header">🎯 FILA 2B // IMPLIED TEAM TOTALS (PUNTOS POR EQUIPO)</div>
                <div class="metric-row">
                    <span class="metric-label">Team Total Local ({res['Local']})</span>
                    <span>
                        <span class="metric-val">{res['Pts_Loc']:.1f} pts</span>
                        <span class="odds-chip green">Línea Justa O/U: {tt_ref_loc:.1f}</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Team Total Visita ({res['Visita']})</span>
                    <span>
                        <span class="metric-val">{res['Pts_Vis']:.1f} pts</span>
                        <span class="odds-chip">Línea Justa O/U: {tt_ref_vis:.1f}</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Diferencial de Ritmo y Volumen</span>
                    <span class="metric-val">{res['Plays_Por_Equipo']} snaps/equipo ({res['Plays_Totales']} jugadas totales)</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    props_loc_html = "".join(
        [
            f"""
            <div class="td-prop-box">
                <div class="td-role">{p['Abrev']} • {p['Rol']}</div>
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
                <div class="td-role">{p['Abrev']} • {p['Rol']}</div>
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
                <span class="metric-label"><b>{res['Local']} (Local)</b> — xTD Total: <b>{res['xTD_Loc']}</b> (Pase: {res['xTD_Pass_Loc']} | Carrera: {res['xTD_Rush_Loc']})</span>
                <span>
                    <span class="odds-chip green">Over 2.5 TDs: {res['Prob_O25_TD_Loc']}% | {res['O25_TD_Loc_Dec']} ({res['O25_TD_Loc_Am']})</span>
                    <span class="odds-chip">Under 2.5 TDs: {res['Prob_U25_TD_Loc']}% | {res['U25_TD_Loc_Dec']} ({res['U25_TD_Loc_Am']})</span>
                </span>
            </div>
            <div class="td-prop-grid">{props_loc_html}</div>
            <div style="height: 10px;"></div>
            <div class="metric-row">
                <span class="metric-label"><b>{res['Visita']} (Visita)</b> — xTD Total: <b>{res['xTD_Vis']}</b> (Pase: {res['xTD_Pass_Vis']} | Carrera: {res['xTD_Rush_Vis']})</span>
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

    with st.expander(f"📈 ANÁLISIS GRÁFICO DE TRINCHERAS Y DISTRIBUCIÓN DE PROBABILIDAD: {res['Abrev_Vis']} @ {res['Abrev_Loc']}"):
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
                    height=280,
                    margin=dict(l=10, r=10, t=40, b=10),
                    xaxis=dict(range=[0, 100], title="Probabilidad (%)"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig_prob, use_container_width=True, key=f"chart_prob_{idx_game}")
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
                    height=280,
                    margin=dict(l=10, r=10, t=40, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig_trench, use_container_width=True, key=f"chart_trench_{idx_game}")
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