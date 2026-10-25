#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MÓDULO 3: app_nfl.py
Orquestador Streamlit con Control de Sesión, Simulación Discreta por Series
Ofensivas (Drive-Based Simulation), Controles de Viento/Estadio y Auditoría
de Valor Matemático (+EV) estrictamente en FORMATO DECIMAL para
"TERMINAL SHARP: NFL QUANT".
"""

import hashlib
from typing import Any, Dict, List
import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

from sync_espn_nfl import (
    escudo_nfl_html,
    normalizar_abbr_nfl,
    obtener_calendario_nfl_semana,
)
from engine_nfl import (
    DOME_FRANCHISES,
    REQUIRED_EXCEL_COLUMNS,
    generar_plantilla_excel_bytes,
    obtener_stats_nfl_default,
    run_simulacion_nfl,
    validar_y_parsear_excel_nfl,
)

# ==============================================================================
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS CSS (CYBER-QUANT + EV DECIMAL UI)
# ==============================================================================
st.set_page_config(
    page_title="TERMINAL SHARP: NFL QUANT (DRIVE ENGINE)",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="expanded",
)

CYBER_QUANT_NFL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Orbitron:wght@500;600;700;800;900&family=Inter:wght@400;500;600;700&display=swap');

:root {
    --bg-main: #060A12;
    --bg-panel: #0C1322;
    --bg-card: #111A2E;
    --cyan-neon: #00F0FF;
    --green-sharp: #00E676;
    --amber-quant: #FFB300;
    --red-alert: #FF2E63;
    --purple-prop: #B388FF;
    --text-primary: #ECF2F8;
    --text-muted: #8A99AD;
    --border-subtle: rgba(0, 240, 255, 0.20);
    --border-strong: rgba(0, 240, 255, 0.45);
}

.stApp {
    background: radial-gradient(circle at 15% 10%, #0D1B30 0%, #060A12 55%, #04070D 100%);
    color: var(--text-primary);
    font-family: 'Inter', sans-serif;
}

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
    font-size: 1.65rem;
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
    font-size: 0.79rem;
    color: var(--cyan-neon);
    letter-spacing: 0.6px;
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

.section-header {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.00rem;
    font-weight: 700;
    letter-spacing: 1.4px;
    color: var(--cyan-neon);
    text-transform: uppercase;
    margin: 14px 0 12px 0;
    border-bottom: 1px solid var(--border-subtle);
    padding-bottom: 6px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
}

/* Tarjetas de Cartelera 3x3 (Glassmorphism) */
.nfl-grid-card {
    background: linear-gradient(160deg, rgba(19, 30, 54, 0.84) 0%, rgba(10, 16, 29, 0.92) 100%);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid var(--border-subtle);
    border-radius: 14px;
    padding: 15px 17px 13px 17px;
    margin-bottom: 6px;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.55);
    transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.nfl-grid-card.has-ev {
    border-color: rgba(0, 230, 118, 0.52);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.60), 0 0 16px rgba(0, 230, 118, 0.12);
}

.nfl-grid-card:hover {
    border-color: var(--cyan-neon);
    transform: translateY(-2px);
}

.card-top-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding-bottom: 7px;
    margin-bottom: 10px;
}

.badge-league {
    font-family: 'Orbitron', sans-serif;
    font-size: 0.65rem;
    font-weight: 800;
    color: var(--cyan-neon);
    background: rgba(0, 240, 255, 0.12);
    border: 1px solid rgba(0, 240, 255, 0.30);
    padding: 3px 8px;
    border-radius: 999px;
    letter-spacing: 0.8px;
}

.badge-hora {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    color: var(--text-muted);
    font-weight: 600;
}

.team-row-grid {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 0;
}

.team-info-left {
    display: flex;
    align-items: center;
    gap: 10px;
}

.team-abbr-title {
    font-family: 'Orbitron', sans-serif;
    font-size: 0.88rem;
    font-weight: 800;
    color: #FFFFFF;
}

.qb-sub-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    color: var(--text-muted);
}

.proj-pts-badge {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.92rem;
    font-weight: 800;
    color: #FFFFFF;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    padding: 3px 9px;
    border-radius: 7px;
}

.proj-pts-badge.fav {
    color: var(--green-sharp);
    border-color: rgba(0, 230, 118, 0.38);
    background: rgba(0, 230, 118, 0.10);
}

.quick-forecast-box {
    margin-top: 9px;
    padding: 8px 11px;
    background: rgba(6, 10, 18, 0.82);
    border: 1px solid rgba(0, 240, 255, 0.20);
    border-left: 3px solid var(--cyan-neon);
    border-radius: 8px;
    font-family: 'JetBrains Mono', monospace;
}

.forecast-main-line {
    font-size: 0.75rem;
    font-weight: 700;
    color: #FFFFFF;
    display: flex;
    justify-content: space-between;
}

.forecast-sub-line {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 3px;
    font-size: 0.68rem;
    color: var(--cyan-neon);
}

/* Bloques de Auditoría +EV en cada Tarjeta (Totales y Hándicap en Decimal) */
.ev-audit-section {
    margin-top: 9px;
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.ev-market-row {
    padding: 7px 10px;
    border-radius: 8px;
    font-family: 'JetBrains Mono', monospace;
    background: rgba(8, 13, 24, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.09);
}

.ev-market-row.positive {
    background: linear-gradient(90deg, rgba(0, 230, 118, 0.14) 0%, rgba(8, 13, 24, 0.90) 100%);
    border: 1px solid rgba(0, 230, 118, 0.48);
    border-left: 4px solid var(--green-sharp);
}

.ev-market-row.neutral {
    border-left: 3px solid rgba(138, 153, 173, 0.38);
}

.ev-row-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.72rem;
    font-weight: 700;
    color: #FFFFFF;
}

.ev-row-bottom {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 2px;
    font-size: 0.66rem;
    color: var(--text-muted);
}

.ev-pill-tag {
    font-size: 0.65rem;
    font-weight: 800;
    padding: 1px 6px;
    border-radius: 4px;
}

.ev-pill-tag.pos {
    background: rgba(0, 230, 118, 0.20);
    color: var(--green-sharp);
    border: 1px solid rgba(0, 230, 118, 0.45);
}

.ev-pill-tag.neu {
    background: rgba(255, 255, 255, 0.06);
    color: var(--text-muted);
    border: 1px solid rgba(255, 255, 255, 0.12);
}

.key-num-chip {
    color: var(--amber-quant);
    font-weight: 700;
}

/* Vista B: Expediente Cuantitativo */
.tv-scoreboard {
    background: linear-gradient(90deg, rgba(11, 19, 36, 0.96) 0%, rgba(19, 32, 59, 0.96) 50%, rgba(11, 19, 36, 0.96) 100%);
    border: 1px solid var(--border-strong);
    border-radius: 14px;
    padding: 18px 24px;
    margin-top: 8px;
    margin-bottom: 16px;
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.60);
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
    font-size: 0.74rem;
    color: var(--text-muted);
}

.tv-main-grid {
    display: grid;
    grid-template-columns: 1.35fr 1fr 1.35fr;
    align-items: center;
    gap: 14px;
}

.tv-team-side {
    display: flex;
    align-items: center;
    gap: 14px;
}

.tv-team-side.right {
    justify-content: flex-end;
    text-align: right;
}

.tv-team-name {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.12rem;
    font-weight: 800;
    color: #FFFFFF;
}

.tv-team-sub {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.74rem;
    color: var(--cyan-neon);
    margin-top: 3px;
}

.tv-center-score {
    text-align: center;
    background: rgba(6, 10, 18, 0.84);
    border: 1px solid rgba(0, 240, 255, 0.32);
    border-radius: 12px;
    padding: 12px 16px;
}

.tv-pts-big {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.65rem;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: 2px;
}

.tv-ou-pill {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.74rem;
    color: var(--amber-quant);
    margin-top: 4px;
    font-weight: 700;
}

.quant-card {
    background: linear-gradient(180deg, rgba(17, 26, 46, 0.92) 0%, rgba(12, 19, 34, 0.95) 100%);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 12px;
    padding: 15px 18px;
    height: 100%;
}

.quant-card-header {
    font-family: 'Orbitron', sans-serif;
    font-size: 0.77rem;
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
    font-size: 0.79rem;
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
    border: 1px solid rgba(0, 240, 255, 0.30);
    padding: 2px 7px;
    border-radius: 5px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.73rem;
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

div.stButton > button {
    font-family: 'Orbitron', sans-serif !important;
    font-size: 0.75rem !important;
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
st.markdown(CYBER_QUANT_NFL_CSS, unsafe_allow_html=True)


# ==============================================================================
# 2. INICIALIZACIÓN DE ESTADO DE SESIÓN (st.session_state)
# ==============================================================================
if "nfl_stats" not in st.session_state:
    st.session_state.nfl_stats = obtener_stats_nfl_default()

if "nfl_stats_source" not in st.session_state:
    st.session_state.nfl_stats_source = "Base Preconfigurada (32 Franquicias)"

if "ultimo_excel_hash" not in st.session_state:
    st.session_state.ultimo_excel_hash = ""

if "odds_api_key" not in st.session_state:
    st.session_state.odds_api_key = ""

if "semana_seleccionada" not in st.session_state:
    st.session_state.semana_seleccionada = "Actual"

if "viento_mph_global" not in st.session_state:
    st.session_state.viento_mph_global = 5

if "tipo_estadio_global" not in st.session_state:
    st.session_state.tipo_estadio_global = "Abierto"

if "hfa_base_global" not in st.session_state:
    st.session_state.hfa_base_global = 1.8

if "calendario_nfl" not in st.session_state:
    st.session_state.calendario_nfl = obtener_calendario_nfl_semana(
        semana=None, api_key=st.session_state.odds_api_key
    )

if "vista_nfl" not in st.session_state:
    st.session_state.vista_nfl = "cartelera"  # "cartelera" | "expediente"

if "partido_seleccionado" not in st.session_state:
    st.session_state.partido_seleccionado = None


def abrir_expediente_partido(partido_dict: Dict[str, Any]):
    st.session_state.partido_seleccionado = partido_dict
    st.session_state.vista_nfl = "expediente"


def volver_a_cartelera_nfl():
    st.session_state.vista_nfl = "cartelera"


# ==============================================================================
# 3. BARRA LATERAL: EXCEL (.XLSX), THE ODDS API Y PARÁMETROS DE CLIMA/ESTADIO
# ==============================================================================
with st.sidebar:
    st.markdown(
        """
        <div style='font-family: Orbitron, sans-serif; font-size: 1.05rem; font-weight: 800; color: #00F0FF; letter-spacing: 1px;'>
            ⚡ TERMINAL SHARP: NFL
        </div>
        <div style='font-family: JetBrains Mono, monospace; font-size: 0.72rem; color: #8A99AD; margin-bottom: 12px;'>
            DRIVE ENGINE • +EV DECIMAL • KEY NUMBERS
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.vista_nfl == "expediente":
        st.button(
            "← Volver a la Cartelera NFL",
            on_click=volver_a_cartelera_nfl,
            use_container_width=True,
        )

    st.markdown("### 📊 1. Motor de Datos (`nfl_stats.xlsx`)")
    archivo_excel = st.file_uploader(
        "Subir archivo nfl_stats.xlsx",
        type=["xlsx", "xls"],
        help="Columnas requeridas: Team_Abbr, QB_Name, EPA_Pass_Off, EPA_Rush_Off, EPA_Pass_Def, EPA_Rush_Def, Success_Rate_Off, Success_Rate_Def, Pace_Sec",
    )

    if archivo_excel is not None:
        raw_bytes = archivo_excel.getvalue()
        nuevo_hash = hashlib.md5(raw_bytes).hexdigest()
        if nuevo_hash != st.session_state.ultimo_excel_hash:
            try:
                df_subido = pd.read_excel(archivo_excel)
                stats_validadas = validar_y_parsear_excel_nfl(df_subido)
                st.session_state.nfl_stats = stats_validadas
                st.session_state.nfl_stats_source = f"Excel: {archivo_excel.name} ({len(df_subido)} eq.)"
                st.session_state.ultimo_excel_hash = nuevo_hash
                st.rerun()
            except Exception as exc:
                st.error(f"Error al validar Excel: {exc}")

    st.caption(f"Fuente EPA: **{st.session_state.nfl_stats_source}**")

    try:
        bytes_plantilla = generar_plantilla_excel_bytes(st.session_state.nfl_stats)
        st.download_button(
            label="⬇️ Descargar Plantilla nfl_stats.xlsx",
            data=bytes_plantilla,
            file_name="nfl_stats.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except Exception:
        pass

    st.markdown("### 🌦️ 2. Clima, Estadio y HFA (Drive Sim)")
    st.session_state.viento_mph_global = st.slider(
        "🌬️ Viento (mph)",
        min_value=0,
        max_value=30,
        value=int(st.session_state.viento_mph_global),
        step=1,
        help="Si viento > 14 mph en estadio Abierto: resta 0.35 pts al total por cada mph sobre 14 y reduce 4% la conversión de goles de campo (3 pts).",
    )

    st.session_state.tipo_estadio_global = st.selectbox(
        "🏟️ Tipo de Estadio",
        options=["Abierto", "Domo", "Auto (Según Franquicia Local)"],
        index=["Abierto", "Domo", "Auto (Según Franquicia Local)"].index(
            st.session_state.tipo_estadio_global
        )
        if st.session_state.tipo_estadio_global in ["Abierto", "Domo", "Auto (Según Franquicia Local)"]
        else 0,
        help="Define si el partido se simula en estadio Abierto (afectado por viento >14 mph) o Domo techado.",
    )

    st.session_state.hfa_base_global = st.slider(
        "🏠 Ventaja de Localía HFA (pts)",
        min_value=1.2,
        max_value=2.2,
        value=float(st.session_state.hfa_base_global),
        step=0.1,
        help="Home Field Advantage calibrado entre 1.2 y 2.2 puntos.",
    )

    st.markdown("### 📡 3. Servidor de Momios (Decimal)")
    api_key_input = st.text_input(
        "The Odds API Key (Opcional)",
        value=st.session_state.odds_api_key,
        type="password",
        help="Si se deja vacío, extrae las líneas de consenso de ESPN Scoreboard convertidas a formato decimal.",
    )
    if api_key_input != st.session_state.odds_api_key:
        st.session_state.odds_api_key = api_key_input

    opciones_semana = ["Actual"] + [str(w) for w in range(1, 19)]
    semana_ui = st.selectbox(
        "Seleccionar Semana NFL",
        options=opciones_semana,
        index=opciones_semana.index(str(st.session_state.semana_seleccionada))
        if str(st.session_state.semana_seleccionada) in opciones_semana
        else 0,
    )

    if st.button("🔄 Actualizar Calendario y Momios", use_container_width=True):
        st.session_state.semana_seleccionada = semana_ui
        sem_param = None if semana_ui == "Actual" else int(semana_ui)
        with st.spinner("Sincronizando calendario ESPN y cuotas decimales..."):
            st.session_state.calendario_nfl = obtener_calendario_nfl_semana(
                semana=sem_param, api_key=st.session_state.odds_api_key
            )
        st.session_state.vista_nfl = "cartelera"
        st.rerun()

    if semana_ui != st.session_state.semana_seleccionada:
        st.session_state.semana_seleccionada = semana_ui
        sem_param = None if semana_ui == "Actual" else int(semana_ui)
        st.session_state.calendario_nfl = obtener_calendario_nfl_semana(
            semana=sem_param, api_key=st.session_state.odds_api_key
        )
        st.session_state.vista_nfl = "cartelera"
        st.rerun()


# ==============================================================================
# 4. ENCABEZADO PRINCIPAL Y EDITOR EN VIVO DE ROSTERS / EPA
# ==============================================================================
etiqueta_sem_header = (
    "SEMANA ACTUAL"
    if st.session_state.semana_seleccionada == "Actual"
    else f"SEMANA {st.session_state.semana_seleccionada}"
)

fuente_odds_global = (
    "THE ODDS API (DECIMAL)"
    if st.session_state.odds_api_key.strip()
    else "ESPN CONSENSUS FALLBACK (DECIMAL)"
)

st.markdown(
    f"""
    <div class="terminal-banner">
        <div class="terminal-title">
            <span>🏈 TERMINAL SHARP: NFL QUANT</span>
            <span class="live-pill">● {etiqueta_sem_header} // DRIVE-BASED SIM // {fuente_odds_global}</span>
        </div>
        <div class="terminal-subtitle">
            SIMULACIÓN DISCRETA POR SERIES OFENSIVAS (~11 DRIVES/EQ) • KEY NUMBERS NFL (3, 7, 6, 10, 4) • VIENTO & HFA • CUOTAS 100% DECIMALES
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.expander("🛠️ INSPECTOR / EDITOR EN VIVO DE `st.session_state.nfl_stats` (QBs Titulares y EPA)", expanded=False):
    filas_actuales = []
    vistos_ed = set()
    for k_abbr, val_dict in st.session_state.nfl_stats.items():
        std_k = normalizar_abbr_nfl(k_abbr)
        if std_k in vistos_ed:
            continue
        vistos_ed.add(std_k)
        filas_actuales.append({col: val_dict[col] for col in REQUIRED_EXCEL_COLUMNS})
    df_ed_base = pd.DataFrame(filas_actuales)
    df_ed_new = st.data_editor(
        df_ed_base,
        use_container_width=True,
        num_rows="fixed",
        key="editor_nfl_stats_live",
        column_config={
            "Team_Abbr": st.column_config.TextColumn("Team_Abbr", disabled=True, width="small"),
            "QB_Name": st.column_config.TextColumn("QB Titular (QB_Name)"),
            "EPA_Pass_Off": st.column_config.NumberColumn("EPA_Pass_Off", format="%.3f", step=0.005),
            "EPA_Rush_Off": st.column_config.NumberColumn("EPA_Rush_Off", format="%.3f", step=0.005),
            "EPA_Pass_Def": st.column_config.NumberColumn("EPA_Pass_Def", format="%.3f", step=0.005),
            "EPA_Rush_Def": st.column_config.NumberColumn("EPA_Rush_Def", format="%.3f", step=0.005),
            "Success_Rate_Off": st.column_config.NumberColumn("Success_Rate_Off", format="%.3f", step=0.005),
            "Success_Rate_Def": st.column_config.NumberColumn("Success_Rate_Def", format="%.3f", step=0.005),
            "Pace_Sec": st.column_config.NumberColumn("Pace_Sec", format="%.1f", step=0.1),
        },
    )
    if st.button("💾 Guardar Cambios en st.session_state.nfl_stats", use_container_width=True):
        st.session_state.nfl_stats = validar_y_parsear_excel_nfl(df_ed_new)
        st.session_state.nfl_stats_source = "Editado en Vivo (Session State)"
        st.rerun()


# ==============================================================================
# 5. SIMULACIÓN POR SERIES DISCRETAS (DRIVES) DE LA JORNADA ACTIVA
# ==============================================================================
calendario_activo: List[Dict[str, Any]] = st.session_state.calendario_nfl
if not calendario_activo:
    st.warning("No se encontraron partidos para la semana seleccionada.")
    st.stop()

cartelera_simulada: List[Dict[str, Any]] = []
for game_meta in calendario_activo:
    sim_res = run_simulacion_nfl(
        away_abbr=game_meta["away_abbr"],
        home_abbr=game_meta["home_abbr"],
        nfl_stats_dict=st.session_state.nfl_stats,
        n_sims=5000,
        lineas_mercado=game_meta,
        viento_mph=float(st.session_state.viento_mph_global),
        tipo_estadio=str(st.session_state.tipo_estadio_global),
        hfa_override=float(st.session_state.hfa_base_global),
    )
    combinado = {**game_meta, **sim_res}
    cartelera_simulada.append(combinado)


# ==============================================================================
# 6. VISTA A: CARTELERA EN CUADRÍCULA 3x3 CON DETECTOR +EV Y NÚMEROS CLAVE
# ==============================================================================
if st.session_state.vista_nfl == "cartelera":
    n_ev_totales = sum(1 for g in cartelera_simulada if g["ev_totales"]["hay_valor"])
    n_ev_spread = sum(1 for g in cartelera_simulada if g["ev_spread"]["hay_valor"])

    st.markdown(
        f"""
        <div class="section-header">
            <span>🏟️ CARTELERA NFL EN CUADRÍCULA (3x3) // {etiqueta_sem_header} ({len(cartelera_simulada)} JUEGOS)</span>
            <span style="font-family:'JetBrains Mono',monospace; font-size:0.75rem; color:#00E676;">
                🔥 +EV Detectados: {n_ev_totales} en Totales (O/U)  |  {n_ev_spread} en Hándicap (Spread)  •  🌬️ Viento: {st.session_state.viento_mph_global} mph ({st.session_state.tipo_estadio_global})
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for row_start in range(0, len(cartelera_simulada), 3):
        cols = st.columns(3)
        fila_partidos = cartelera_simulada[row_start : row_start + 3]

        for col_idx, item in enumerate(fila_partidos):
            with cols[col_idx]:
                logo_away_html = escudo_nfl_html(item["away_abbr"], size=36)
                logo_home_html = escudo_nfl_html(item["home_abbr"], size=36)

                es_home_fav = item["home_pts"] >= item["away_pts"]
                clase_away_pts = "proj-pts-badge" if es_home_fav else "proj-pts-badge fav"
                clase_home_pts = "proj-pts-badge fav" if es_home_fav else "proj-pts-badge"

                ev_tot = item["ev_totales"]
                ev_sp = item["ev_spread"]
                tiene_algun_ev = ev_tot["hay_valor"] or ev_sp["hay_valor"]
                card_ev_class = "nfl-grid-card has-ev" if tiene_algun_ev else "nfl-grid-card"

                tot_row_cls = "ev-market-row positive" if ev_tot["hay_valor"] else "ev-market-row neutral"
                tot_pill_cls = "ev-pill-tag pos" if ev_tot["hay_valor"] else "ev-pill-tag neu"
                tot_badge_txt = (
                    f"🔥 +EV {ev_tot['lado']} ({ev_tot['ev_pct']:+.1f}%)"
                    if ev_tot["hay_valor"]
                    else f"⚖️ SIN VALOR ({ev_tot['ev_pct']:+.1f}%)"
                )

                sp_row_cls = "ev-market-row positive" if ev_sp["hay_valor"] else "ev-market-row neutral"
                sp_pill_cls = "ev-pill-tag pos" if ev_sp["hay_valor"] else "ev-pill-tag neu"
                sp_badge_txt = (
                    f"🔥 +EV {ev_sp['recomendacion']} ({ev_sp['ev_pct']:+.1f}%)"
                    if ev_sp["hay_valor"]
                    else f"⚖️ SIN VALOR ({ev_sp['ev_pct']:+.1f}%)"
                )

                spread_modelo_str = (
                    f"{item['home_abbr']} {item['spread_proyectado']:+.1f}"
                    if item["spread_proyectado"] <= 0
                    else f"{item['away_abbr']} {-item['spread_proyectado']:+.1f}"
                )

                push_txt = (
                    f" • Push {ev_sp['prob_push_pct']}%"
                    if ev_sp["prob_push_pct"] > 0.0
                    else ""
                )

                estadio_icon = "🏟️ Domo" if item["tipo_estadio"] == "Domo" else f"🌬️ {item['viento_mph']:.0f}mph"

                st.markdown(
                    f"""
                    <div class="{card_ev_class}">
                        <div class="card-top-meta">
                            <span class="badge-league">NFL · {etiqueta_sem_header}</span>
                            <span class="badge-hora">🕒 {item['hora']} • {estadio_icon}</span>
                        </div>
                        <div class="team-row-grid">
                            <div class="team-info-left">
                                {logo_away_html}
                                <div>
                                    <div class="team-abbr-title">{item['away_name']} ({item['away_abbr']})</div>
                                    <div class="qb-sub-label">QB: {item['away_qb']} • Win: {item['win_away_pct']}% (Fair {item['ml_away_decimal']:.2f})</div>
                                </div>
                            </div>
                            <div class="{clase_away_pts}">{item['away_pts']:.1f}</div>
                        </div>
                        <div class="team-row-grid">
                            <div class="team-info-left">
                                {logo_home_html}
                                <div>
                                    <div class="team-abbr-title">{item['home_name']} ({item['home_abbr']})</div>
                                    <div class="qb-sub-label">QB: {item['home_qb']} • Win: {item['win_home_pct']}% (Fair {item['ml_home_decimal']:.2f})</div>
                                </div>
                            </div>
                            <div class="{clase_home_pts}">{item['home_pts']:.1f}</div>
                        </div>
                        <div class="quick-forecast-box">
                            <div class="forecast-main-line">
                                <span>Pronóstico: {item['away_abbr']} {item['exact_away']} - {item['exact_home']} {item['home_abbr']}</span>
                                <span>{item['drives_combinados']} Drives ({item['n_drives_equipo']}/eq)</span>
                            </div>
                            <div class="forecast-sub-line">
                                <span>Modelo: <b>{spread_modelo_str} | Tot {item['total_ou']:.1f}</b></span>
                                <span>Mkt: <b>{item['home_abbr']} {item['spread_mercado_home']:+.1f} | O/U {item['total_mercado']:.1f}</b></span>
                            </div>
                        </div>
                        <div class="ev-audit-section">
                            <div class="{tot_row_cls}">
                                <div class="ev-row-top">
                                    <span>1. TOTAL: {ev_tot['lado']} {ev_tot['total_mercado']:.1f} @ {ev_tot['cuota_mercado_decimal']:.2f}</span>
                                    <span class="{tot_pill_cls}">{tot_badge_txt}</span>
                                </div>
                                <div class="ev-row-bottom">
                                    <span>Prob {ev_tot['lado']}: {ev_tot['prob_mejor_pct']}% (Modelo {ev_tot['total_modelo']:.1f} pts)</span>
                                    <span>Fair Decimal: <b>{ev_tot['fair_decimal']:.2f}</b></span>
                                </div>
                            </div>
                            <div class="{sp_row_cls}">
                                <div class="ev-row-top">
                                    <span>2. SPREAD: {ev_sp['recomendacion']} @ {ev_sp['cuota_mercado_decimal']:.2f}</span>
                                    <span class="{sp_pill_cls}">{sp_badge_txt}</span>
                                </div>
                                <div class="ev-row-bottom">
                                    <span>Cobertura: <b>{ev_sp['prob_mejor_pct']}%</b>{push_txt} | <span class="key-num-chip">{item['key_number_tag']}</span></span>
                                    <span>Fair: <b>{ev_sp['fair_decimal']:.2f}</b></span>
                                </div>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                st.button(
                    "LEER ANÁLISIS →",
                    key=f"btn_analisis_{item['id_partido']}",
                    use_container_width=True,
                    on_click=abrir_expediente_partido,
                    args=(item,),
                )
                st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

else:
    # ==========================================================================
    # 7. VISTA B: EXPEDIENTE CUANTITATIVO DEL PARTIDO (DRIVE SIMULATION + EV)
    # ==========================================================================
    partido_actual = st.session_state.partido_seleccionado or cartelera_simulada[0]

    top_c1, top_c2, top_c3 = st.columns([1.15, 1.85, 1.0])
    with top_c1:
        st.button(
            "← Volver a la Cartelera NFL",
            key="btn_volver_top_nfl",
            use_container_width=True,
            on_click=volver_a_cartelera_nfl,
        )
    with top_c2:
        ids_disponibles = [g["id_partido"] for g in cartelera_simulada]
        idx_actual = (
            ids_disponibles.index(partido_actual["id_partido"])
            if partido_actual["id_partido"] in ids_disponibles
            else 0
        )
        idx_elegido = st.selectbox(
            "Cambiar de Partido",
            options=range(len(cartelera_simulada)),
            index=idx_actual,
            format_func=lambda i: (
                f"{cartelera_simulada[i]['away_abbr']} @ {cartelera_simulada[i]['home_abbr']} "
                f"— {cartelera_simulada[i]['nombre']}"
            ),
            label_visibility="collapsed",
        )
        if idx_elegido != idx_actual:
            st.session_state.partido_seleccionado = cartelera_simulada[idx_elegido]
            st.rerun()
    with top_c3:
        st.markdown(
            f"""
            <div style="text-align:right; font-family:'JetBrains Mono',monospace; font-size:0.76rem; color:#00F0FF; padding-top:6px;">
                {partido_actual['hora']} • {partido_actual.get('fuente_odds', 'Consenso Decimal')}
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Panel interactivo de clima/estadio y cuotas decimales para este partido específico
    estadio_default_partido = (
        "Domo"
        if (
            st.session_state.tipo_estadio_global == "Domo"
            or (
                "Auto" in st.session_state.tipo_estadio_global
                and DOME_FRANCHISES.get(partido_actual["home_abbr"], False)
            )
        )
        else "Abierto"
    )

    with st.expander(
        "🎛️ SIMULADOR INTERACTIVO DE CLIMA (VIENTO / ESTADIO) Y LÍNEAS DECIMALES DEL PARTIDO",
        expanded=True,
    ):
        cl_c1, cl_c2, cl_c3 = st.columns(3)
        with cl_c1:
            viento_partido_in = st.slider(
                "🌬️ Viento en el Estadio (mph)",
                min_value=0,
                max_value=30,
                value=int(st.session_state.viento_mph_global),
                step=1,
                key="slider_viento_detalle",
            )
        with cl_c2:
            estadio_partido_in = st.selectbox(
                "🏟️ Tipo de Estadio del Partido",
                options=["Abierto", "Domo"],
                index=0 if estadio_default_partido == "Abierto" else 1,
                key="select_estadio_detalle",
            )
        with cl_c3:
            hfa_partido_in = st.slider(
                "🏠 Ventaja de Localía HFA (pts)",
                min_value=1.2,
                max_value=2.2,
                value=float(st.session_state.hfa_base_global),
                step=0.1,
                key="slider_hfa_detalle",
            )

        ac1, ac2, ac3, ac4, ac5, ac6 = st.columns(6)
        with ac1:
            mkt_total_in = st.number_input(
                "Línea Total (O/U)", value=float(partido_actual["total_mercado"]), step=0.5, format="%.1f"
            )
        with ac2:
            mkt_over_dec_in = st.number_input(
                "Cuota OVER (Dec)",
                value=float(partido_actual["cuota_over_decimal"]),
                min_value=1.05,
                max_value=10.0,
                step=0.01,
                format="%.2f",
            )
        with ac3:
            mkt_under_dec_in = st.number_input(
                "Cuota UNDER (Dec)",
                value=float(partido_actual["cuota_under_decimal"]),
                min_value=1.05,
                max_value=10.0,
                step=0.01,
                format="%.2f",
            )
        with ac4:
            mkt_sp_home_in = st.number_input(
                f"Spread {partido_actual['home_abbr']} (Local)",
                value=float(partido_actual["spread_mercado_home"]),
                step=0.5,
                format="%.1f",
            )
        with ac5:
            mkt_sp_h_dec_in = st.number_input(
                f"Cuota {partido_actual['home_abbr']} (Dec)",
                value=float(partido_actual["cuota_spread_home_decimal"]),
                min_value=1.05,
                max_value=10.0,
                step=0.01,
                format="%.2f",
            )
        with ac6:
            mkt_sp_a_dec_in = st.number_input(
                f"Cuota {partido_actual['away_abbr']} (Dec)",
                value=float(partido_actual["cuota_spread_away_decimal"]),
                min_value=1.05,
                max_value=10.0,
                step=0.01,
                format="%.2f",
            )

    lineas_custom = {
        "total_mercado": mkt_total_in,
        "cuota_over_decimal": mkt_over_dec_in,
        "cuota_under_decimal": mkt_under_dec_in,
        "spread_mercado_home": mkt_sp_home_in,
        "cuota_spread_home_decimal": mkt_sp_h_dec_in,
        "cuota_spread_away_decimal": mkt_sp_a_dec_in,
    }

    sim_detalle = run_simulacion_nfl(
        away_abbr=partido_actual["away_abbr"],
        home_abbr=partido_actual["home_abbr"],
        nfl_stats_dict=st.session_state.nfl_stats,
        n_sims=5000,
        lineas_mercado=lineas_custom,
        viento_mph=float(viento_partido_in),
        tipo_estadio=str(estadio_partido_in),
        hfa_override=float(hfa_partido_in),
    )
    res = {**partido_actual, **sim_detalle}
    ev_tot = res["ev_totales"]
    ev_sp = res["ev_spread"]

    escudo_away_big = escudo_nfl_html(res["away_abbr"], size=68)
    escudo_home_big = escudo_nfl_html(res["home_abbr"], size=68)

    # --- A. SCOREBOARD TV HEADER ---
    st.markdown(
        f"""
        <div class="tv-scoreboard">
            <div class="tv-top-bar">
                <span>EXPEDIENTE DRIVE-BASED // {res['nombre']} ({res['drives_combinados']} POSESIONES: {res['n_drives_equipo']} DRIVES/EQ)</span>
                <span>ESTADIO: {res['tipo_estadio'].upper()} // VIENTO: {res['viento_mph']} MPH (PENALIZACIÓN: -{res['penalizacion_viento_pts']:.2f} PTS) // HFA: +{res['hfa_pts']:.2f} PTS</span>
                <span>5,000 ITERACIONES // CUOTAS DECIMALES</span>
            </div>
            <div class="tv-main-grid">
                <div class="tv-team-side">
                    {escudo_away_big}
                    <div>
                        <div class="tv-team-name">{res['away_name']} ({res['away_abbr']})</div>
                        <div class="tv-team-sub">QB Titular: {res['away_qb']} • Win: {res['win_away_pct']}% (Fair Dec: {res['ml_away_decimal']:.2f})</div>
                        <div style="font-family:'JetBrains Mono',monospace; font-size:0.72rem; color:#8A99AD; margin-top:2px;">
                            Drive Probs: TD {res['drive_td_pct_away']}% | FG {res['drive_fg_pct_away']}% | Punt/TO {res['drive_punt_pct_away']}%
                        </div>
                    </div>
                </div>
                <div class="tv-center-score">
                    <div style="font-family:'Orbitron',sans-serif; font-size:0.68rem; color:#00F0FF; letter-spacing:1px;">
                        PROYECCIÓN POR SERIES (5,000 SIMS)
                    </div>
                    <div class="tv-pts-big">{res['away_pts']:.1f}  —  {res['home_pts']:.1f}</div>
                    <div class="tv-ou-pill">
                        MARCADOR CLAVE: {res['away_abbr']} {res['exact_away']} - {res['exact_home']} {res['home_abbr']}  |  TOTAL MODELO: {res['total_ou']:.1f}
                    </div>
                </div>
                <div class="tv-team-side right">
                    <div>
                        <div class="tv-team-name">{res['home_name']} ({res['home_abbr']})</div>
                        <div class="tv-team-sub">QB Titular: {res['home_qb']} • Win: {res['win_home_pct']}% (Fair Dec: {res['ml_home_decimal']:.2f})</div>
                        <div style="font-family:'JetBrains Mono',monospace; font-size:0.72rem; color:#8A99AD; margin-top:2px;">
                            Drive Probs: TD {res['drive_td_pct_home']}% | FG {res['drive_fg_pct_home']}% | Punt/TO {res['drive_punt_pct_home']}%
                        </div>
                    </div>
                    {escudo_home_big}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- B. FILA 1: AUDITORÍA +EV DE TOTALES, HÁNDICAP (CON PUSH Y KEY NUMBERS) Y DRIVES ---
    c_m1, c_m2, c_m3 = st.columns(3)

    with c_m1:
        st.markdown(
            f"""
            <div class="quant-card">
                <div class="quant-card-header">⚡ 1. AUDITORÍA +EV TOTALES (OVER / UNDER DECIMAL)</div>
                <div class="metric-row">
                    <span class="metric-label">Total Modelo vs Línea Mercado</span>
                    <span class="metric-val">{ev_tot['total_modelo']:.1f} pts vs {ev_tot['total_mercado']:.1f} pts (Edge {ev_tot['edge_pts']:+.1f})</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">OVER {ev_tot['total_mercado']:.1f} (Prob {ev_tot['prob_over_pct']}%)</span>
                    <span>
                        <span class="odds-chip green">Mkt: {ev_tot['cuota_over_decimal']:.2f} | Fair: {ev_tot['fair_over_decimal']:.2f} (EV {ev_tot['ev_over_pct']:+.1f}%)</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">UNDER {ev_tot['total_mercado']:.1f} (Prob {ev_tot['prob_under_pct']}%)</span>
                    <span>
                        <span class="odds-chip">Mkt: {ev_tot['cuota_under_decimal']:.2f} | Fair: {ev_tot['fair_under_decimal']:.2f} (EV {ev_tot['ev_under_pct']:+.1f}%)</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Dictamen Cuantitativo Totales</span>
                    <span class="odds-chip {'green' if ev_tot['hay_valor'] else 'amber'}">{ev_tot['etiqueta_ev']}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c_m2:
        spread_away_mkt = -res["spread_mercado_home"]
        st.markdown(
            f"""
            <div class="quant-card">
                <div class="quant-card-header">📏 2. AUDITORÍA +EV SPREAD (CON PUSH & KEY NUMBERS)</div>
                <div class="metric-row">
                    <span class="metric-label">Spread Modelo vs Mkt ({res['key_number_tag']})</span>
                    <span class="metric-val">{res['spread_proyectado']:+.1f} vs {res['spread_mercado_home']:+.1f} (Push {ev_sp['prob_push_pct']}%)</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">{res['home_abbr']} {res['spread_mercado_home']:+.1f} (Cov {ev_sp['prob_cover_home_pct']}%)</span>
                    <span>
                        <span class="odds-chip green">Mkt: {ev_sp['cuota_spread_home_decimal']:.2f} | Fair: {ev_sp['fair_home_decimal']:.2f} (EV {ev_sp['ev_home_pct']:+.1f}%)</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">{res['away_abbr']} {spread_away_mkt:+.1f} (Cov {ev_sp['prob_cover_away_pct']}%)</span>
                    <span>
                        <span class="odds-chip">Mkt: {ev_sp['cuota_spread_away_decimal']:.2f} | Fair: {ev_sp['fair_away_decimal']:.2f} (EV {ev_sp['ev_away_pct']:+.1f}%)</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Dictamen Cuantitativo Spread</span>
                    <span class="odds-chip {'green' if ev_sp['hay_valor'] else 'amber'}">{ev_sp['etiqueta_ev']}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c_m3:
        st.markdown(
            f"""
            <div class="quant-card">
                <div class="quant-card-header">🏈 3. SIMULACIÓN POR SERIES (DRIVES) & CLIMA</div>
                <div class="metric-row">
                    <span class="metric-label">Victoria Moneyline ({res['home_abbr']} / {res['away_abbr']})</span>
                    <span>
                        <span class="odds-chip green">{res['home_abbr']} {res['win_home_pct']}% (Fair {res['ml_home_decimal']:.2f})</span>
                        <span class="odds-chip">{res['away_abbr']} {res['win_away_pct']}% (Fair {res['ml_away_decimal']:.2f})</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Series Ofensivas Simuladas (Drives)</span>
                    <span class="metric-val">{res['n_drives_equipo']} Local + {res['n_drives_equipo']} Visita ({res['drives_combinados']} totales)</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Impacto Viento ({res['viento_mph']} mph en {res['tipo_estadio']})</span>
                    <span class="metric-val">-{res['penalizacion_viento_pts']:.2f} pts al Total | FG {'-4%' if (res['tipo_estadio']=='Abierto' and res['viento_mph']>14) else 'Estándar'}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Percentiles P10 / P50 / P90 (OT {res['ot_pct']}%)</span>
                    <span class="odds-chip amber">{res['mc_p10_total']} / {res['mc_p50_total']} / {res['mc_p90_total']} pts</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

    # --- C. GRÁFICOS INTERACTIVOS DE PROBABILIDADES Y PROBABILIDADES POR DRIVE ---
    st.markdown(
        '<div class="section-header"><span>📈 DISTRIBUCIÓN DE PROBABILIDADES Y EFICIENCIA POR DRIVE</span></div>',
        unsafe_allow_html=True,
    )
    g1, g2 = st.columns(2)

    with g1:
        if PLOTLY_AVAILABLE:
            fig_p = go.Figure()
            categorias = [
                f"Win % ({res['home_abbr']} vs {res['away_abbr']})",
                f"Spread Cover ({res['spread_mercado_home']:+.1f})",
                f"Total O/U ({res['total_mercado']:.1f})",
            ]
            v_home = [res["win_home_pct"], res["cover_home_pct"], res["over_pct"]]
            v_away = [res["win_away_pct"], res["cover_away_pct"], res["under_pct"]]

            fig_p.add_trace(
                go.Bar(
                    y=categorias,
                    x=v_home,
                    name=f"{res['home_abbr']} / OVER",
                    orientation="h",
                    marker_color="#00E676",
                    text=[f"{v:.1f}%" for v in v_home],
                    textposition="inside",
                )
            )
            fig_p.add_trace(
                go.Bar(
                    y=categorias,
                    x=v_away,
                    name=f"{res['away_abbr']} / UNDER",
                    orientation="h",
                    marker_color="#00F0FF",
                    text=[f"{v:.1f}%" for v in v_away],
                    textposition="inside",
                )
            )
            fig_p.update_layout(
                title="Distribución de Probabilidad (5,000 Iteraciones por Series)",
                barmode="stack",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(12,19,34,0.85)",
                font=dict(family="JetBrains Mono, monospace", color="#ECF2F8", size=11),
                height=290,
                margin=dict(l=10, r=10, t=40, b=10),
                xaxis=dict(range=[0, 100], title="Probabilidad (%)"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig_p, use_container_width=True)

    with g2:
        if PLOTLY_AVAILABLE:
            fig_drv = go.Figure()
            labels_drv = ["Prob. Touchdown / Drive (%)", "Prob. Field Goal / Drive (%)", "Prob. Punt o Turnover (%)", "Success Rate Off (%)"]
            vals_home_drv = [
                res["drive_td_pct_home"],
                res["drive_fg_pct_home"],
                res["drive_punt_pct_home"],
                res["sr_off_home"],
            ]
            vals_away_drv = [
                res["drive_td_pct_away"],
                res["drive_fg_pct_away"],
                res["drive_punt_pct_away"],
                res["sr_off_away"],
            ]
            fig_drv.add_trace(
                go.Bar(
                    x=labels_drv,
                    y=vals_home_drv,
                    name=f"{res['home_abbr']} (Local)",
                    marker_color="#00E676",
                    text=[f"{v:.1f}%" for v in vals_home_drv],
                    textposition="auto",
                )
            )
            fig_drv.add_trace(
                go.Bar(
                    x=labels_drv,
                    y=vals_away_drv,
                    name=f"{res['away_abbr']} (Visita)",
                    marker_color="#FFB300",
                    text=[f"{v:.1f}%" for v in vals_away_drv],
                    textposition="auto",
                )
            )
            fig_drv.update_layout(
                title="Probabilidades por Serie Ofensiva (Drive Outcome %)",
                barmode="group",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(12,19,34,0.85)",
                font=dict(family="JetBrains Mono, monospace", color="#ECF2F8", size=11),
                height=290,
                margin=dict(l=10, r=10, t=40, b=10),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig_drv, use_container_width=True)

    st.markdown(
        '<div class="section-header"><span>🔑 AGRUPACIÓN EN NÚMEROS CLAVE DE LA NFL (MARGEN EXACTO EN 5,000 SIMS)</span></div>',
        unsafe_allow_html=True,
    )
    kn_cols = st.columns(6)
    for idx_kn, (kn_label, kn_pct) in enumerate(res["key_numbers_freq"].items()):
        with kn_cols[idx_kn]:
            st.metric(label=f"🔑 {kn_label}", value=f"{kn_pct}%")

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    st.button(
        "← Volver a la Cartelera NFL",
        key="btn_volver_bottom_nfl",
        use_container_width=True,
        on_click=volver_a_cartelera_nfl,
    )