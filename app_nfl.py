#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MÓDULO 3: app_nfl.py
Orquestador Streamlit con Control de Sesión para "TERMINAL SHARP: NFL QUANT".
Integra:
  1. Carga de métricas y rosters vía Excel (.xlsx) con persistencia en st.session_state.
  2. Sincronización de calendario semanal desde la API pública de ESPN (Scoreboard API)
     y escudos oficiales vía CDN (sync_espn_nfl.py).
  3. Vista A: Cartelera en Cuadrícula 3x3 (Glassmorphism) con QBs, Spread, Total y botón
     "LEER ANÁLISIS →".
  4. Vista B: Expediente Cuantitativo (5,000 simulaciones Poisson / Monte Carlo,
     Win %, Spread Cover %, Totales, Fair Odds y gráficos de trincheras).
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
    NFL_FRANCHISE_NAMES,
    escudo_nfl_html,
    normalizar_abbr_nfl,
    obtener_calendario_nfl_semana,
)
from engine_nfl import (
    REQUIRED_EXCEL_COLUMNS,
    generar_plantilla_excel_bytes,
    obtener_stats_nfl_default,
    run_simulacion_nfl,
    validar_y_parsear_excel_nfl,
)

# ==============================================================================
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS CSS (CYBER-QUANT / GLASSMORPHISM)
# ==============================================================================
st.set_page_config(
    page_title="TERMINAL SHARP: NFL QUANT",
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
    font-size: 1.68rem;
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
    font-size: 0.80rem;
    color: var(--cyan-neon);
    letter-spacing: 0.7px;
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
    font-size: 1.02rem;
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
}

/* Tarjetas de Cartelera 3x3 (Glassmorphism) */
.nfl-grid-card {
    background: linear-gradient(160deg, rgba(19, 30, 54, 0.80) 0%, rgba(10, 16, 29, 0.90) 100%);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid var(--border-subtle);
    border-radius: 14px;
    padding: 16px 18px 14px 18px;
    margin-bottom: 6px;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.55);
    transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.nfl-grid-card:hover {
    border-color: var(--cyan-neon);
    box-shadow: 0 14px 34px rgba(0, 0, 0, 0.68), 0 0 16px rgba(0, 240, 255, 0.14);
    transform: translateY(-2px);
}

.card-top-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding-bottom: 8px;
    margin-bottom: 11px;
}

.badge-league {
    font-family: 'Orbitron', sans-serif;
    font-size: 0.67rem;
    font-weight: 800;
    color: var(--cyan-neon);
    background: rgba(0, 240, 255, 0.12);
    border: 1px solid rgba(0, 240, 255, 0.30);
    padding: 3px 8px;
    border-radius: 999px;
    letter-spacing: 1px;
}

.badge-hora {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.71rem;
    color: var(--text-muted);
    font-weight: 600;
}

.team-row-grid {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 0;
}

.team-info-left {
    display: flex;
    align-items: center;
    gap: 10px;
}

.team-abbr-title {
    font-family: 'Orbitron', sans-serif;
    font-size: 0.92rem;
    font-weight: 800;
    color: #FFFFFF;
}

.qb-sub-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.70rem;
    color: var(--text-muted);
}

.proj-pts-badge {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.96rem;
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
    margin-top: 10px;
    padding: 10px 12px;
    background: rgba(6, 10, 18, 0.78);
    border: 1px solid rgba(0, 240, 255, 0.22);
    border-left: 3px solid var(--green-sharp);
    border-radius: 9px;
    font-family: 'JetBrains Mono', monospace;
}

.forecast-main-line {
    font-size: 0.79rem;
    font-weight: 700;
    color: #FFFFFF;
}

.forecast-sub-line {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 4px;
    font-size: 0.71rem;
    color: var(--cyan-neon);
}

/* Vista B: Expediente Cuantitativo (TV Scoreboard + Cards) */
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
    font-size: 0.75rem;
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
    font-size: 0.75rem;
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
    font-size: 0.75rem;
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
    border: 1px solid rgba(0, 240, 255, 0.30);
    padding: 2px 7px;
    border-radius: 5px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.74rem;
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

if "semana_seleccionada" not in st.session_state:
    st.session_state.semana_seleccionada = "Actual"

if "calendario_nfl" not in st.session_state:
    st.session_state.calendario_nfl = obtener_calendario_nfl_semana(semana=None)

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
# 3. BARRA LATERAL: CARGA DE EXCEL (.XLSX) Y SINCRONIZACIÓN ESPN
# ==============================================================================
with st.sidebar:
    st.markdown(
        """
        <div style='font-family: Orbitron, sans-serif; font-size: 1.05rem; font-weight: 800; color: #00F0FF; letter-spacing: 1px;'>
            ⚡ TERMINAL SHARP: NFL
        </div>
        <div style='font-family: JetBrains Mono, monospace; font-size: 0.72rem; color: #8A99AD; margin-bottom: 12px;'>
            EXCEL ENGINE • ESPN API • MONTE CARLO
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

    st.caption(f"Fuente activa: **{st.session_state.nfl_stats_source}**")

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

    st.markdown("### 🗓️ 2. Calendario ESPN Scoreboard")
    opciones_semana = ["Actual"] + [str(w) for w in range(1, 19)]
    semana_ui = st.selectbox(
        "Seleccionar Semana NFL",
        options=opciones_semana,
        index=opciones_semana.index(str(st.session_state.semana_seleccionada))
        if str(st.session_state.semana_seleccionada) in opciones_semana
        else 0,
    )

    if st.button("🔄 Actualizar Calendario NFL", use_container_width=True):
        st.session_state.semana_seleccionada = semana_ui
        sem_param = None if semana_ui == "Actual" else int(semana_ui)
        with st.spinner("Consultando ESPN NFL Scoreboard API..."):
            st.session_state.calendario_nfl = obtener_calendario_nfl_semana(semana=sem_param)
        st.session_state.vista_nfl = "cartelera"
        st.rerun()

    if semana_ui != st.session_state.semana_seleccionada:
        st.session_state.semana_seleccionada = semana_ui
        sem_param = None if semana_ui == "Actual" else int(semana_ui)
        st.session_state.calendario_nfl = obtener_calendario_nfl_semana(semana=sem_param)
        st.session_state.vista_nfl = "cartelera"
        st.rerun()


# ==============================================================================
# 4. ENCABEZADO PRINCIPAL Y EDITOR RÁPIDO DE MÉTRICAS / QBs EN SESIÓN
# ==============================================================================
etiqueta_sem_header = (
    "SEMANA ACTUAL"
    if st.session_state.semana_seleccionada == "Actual"
    else f"SEMANA {st.session_state.semana_seleccionada}"
)

st.markdown(
    f"""
    <div class="terminal-banner">
        <div class="terminal-title">
            <span>🏈 TERMINAL SHARP: NFL QUANT</span>
            <span class="live-pill">● ESPN SCOREBOARD // {etiqueta_sem_header}</span>
        </div>
        <div class="terminal-subtitle">
            ARQUITECTURA MODULAR (SYNC + ENGINE + APP) • EXCEL ROSTER & EPA PARSER • 5,000 SIMULACIONES POISSON/MONTE CARLO
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
# 5. PRE-SIMULACIÓN DE LA JORNADA ACTIVA
# ==============================================================================
calendario_activo: List[Dict[str, str]] = st.session_state.calendario_nfl
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
    )
    combinado = {**game_meta, **sim_res}
    cartelera_simulada.append(combinado)


# ==============================================================================
# 6. VISTA A: CARTELERA EN CUADRÍCULA 3x3
# ==============================================================================
if st.session_state.vista_nfl == "cartelera":
    st.markdown(
        f"""
        <div class="section-header">
            <span>🏟️ CARTELERA NFL EN CUADRÍCULA (3x3) // {etiqueta_sem_header} ({len(cartelera_simulada)} JUEGOS)</span>
            <span style="font-family:'JetBrains Mono',monospace; font-size:0.75rem; color:#8A99AD;">
                Selecciona "LEER ANÁLISIS →" para abrir el Expediente Cuantitativo
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
                logo_away_html = escudo_nfl_html(item["away_abbr"], size=38)
                logo_home_html = escudo_nfl_html(item["home_abbr"], size=38)

                es_home_fav = item["home_pts"] >= item["away_pts"]
                clase_away_pts = "proj-pts-badge" if es_home_fav else "proj-pts-badge fav"
                clase_home_pts = "proj-pts-badge fav" if es_home_fav else "proj-pts-badge"

                spread_str = (
                    f"{item['home_abbr']} {item['spread_proyectado']:+.1f}"
                    if item["spread_proyectado"] <= 0
                    else f"{item['away_abbr']} {-item['spread_proyectado']:+.1f}"
                )

                st.markdown(
                    f"""
                    <div class="nfl-grid-card">
                        <div class="card-top-meta">
                            <span class="badge-league">NFL · {etiqueta_sem_header}</span>
                            <span class="badge-hora">🕒 {item['hora']}</span>
                        </div>
                        <div class="team-row-grid">
                            <div class="team-info-left">
                                {logo_away_html}
                                <div>
                                    <div class="team-abbr-title">{item['away_name']} ({item['away_abbr']})</div>
                                    <div class="qb-sub-label">QB: {item['away_qb']} • Win: {item['win_away_pct']}%</div>
                                </div>
                            </div>
                            <div class="{clase_away_pts}">{item['away_pts']:.1f}</div>
                        </div>
                        <div class="team-row-grid">
                            <div class="team-info-left">
                                {logo_home_html}
                                <div>
                                    <div class="team-abbr-title">{item['home_name']} ({item['home_abbr']})</div>
                                    <div class="qb-sub-label">QB: {item['home_qb']} • Win: {item['win_home_pct']}%</div>
                                </div>
                            </div>
                            <div class="{clase_home_pts}">{item['home_pts']:.1f}</div>
                        </div>
                        <div class="quick-forecast-box">
                            <div class="forecast-main-line">
                                Pronóstico: {item['away_abbr']} {item['exact_away']} - {item['exact_home']} {item['home_abbr']}
                            </div>
                            <div class="forecast-sub-line">
                                <span>Spread: <b>{spread_str}</b></span>
                                <span>Total O/U: <b>{item['total_ou']:.1f} pts</b></span>
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
    # 7. VISTA B: EXPEDIENTE CUANTITATIVO DEL PARTIDO SELECCIONADO
    # ==========================================================================
    partido_actual = st.session_state.partido_seleccionado or cartelera_simulada[0]
    # Re-ejecutar simulación en vivo con el diccionario actualizado de st.session_state.nfl_stats
    sim_detalle = run_simulacion_nfl(
        away_abbr=partido_actual["away_abbr"],
        home_abbr=partido_actual["home_abbr"],
        nfl_stats_dict=st.session_state.nfl_stats,
        n_sims=5000,
    )
    res = {**partido_actual, **sim_detalle}

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
        idx_actual = ids_disponibles.index(res["id_partido"]) if res["id_partido"] in ids_disponibles else 0
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
            <div style="text-align:right; font-family:'JetBrains Mono',monospace; font-size:0.77rem; color:#00F0FF; padding-top:6px;">
                {res['hora']} • {res['estado']}
            </div>
            """,
            unsafe_allow_html=True,
        )

    escudo_away_big = escudo_nfl_html(res["away_abbr"], size=68)
    escudo_home_big = escudo_nfl_html(res["home_abbr"], size=68)

    # --- A. SCOREBOARD TV HEADER ---
    st.markdown(
        f"""
        <div class="tv-scoreboard">
            <div class="tv-top-bar">
                <span>EXPEDIENTE CUANTITATIVO // {res['nombre']}</span>
                <span>VENTAJA LOCALÍA (HFA): +{res['hfa_pts']:.1f} PTS // SNAPS PROY: {res['snaps_por_equipo']}/EQ</span>
                <span>MONTE CARLO / POISSON: {res['n_sims']:,} SIMULACIONES</span>
            </div>
            <div class="tv-main-grid">
                <div class="tv-team-side">
                    {escudo_away_big}
                    <div>
                        <div class="tv-team-name">{res['away_name']} ({res['away_abbr']})</div>
                        <div class="tv-team-sub">QB Titular: {res['away_qb']}</div>
                        <div style="font-family:'JetBrains Mono',monospace; font-size:0.73rem; color:#8A99AD; margin-top:2px;">
                            EPA Comp: {res['epa_comp_away']:+.3f} | Success Off: {res['sr_off_away']}% | Pace: {res['pace_away']}s
                        </div>
                    </div>
                </div>
                <div class="tv-center-score">
                    <div style="font-family:'Orbitron',sans-serif; font-size:0.68rem; color:#00F0FF; letter-spacing:1px;">
                        PROYECCIÓN MEDIA (5,000 SIMS)
                    </div>
                    <div class="tv-pts-big">{res['away_pts']:.1f}  —  {res['home_pts']:.1f}</div>
                    <div class="tv-ou-pill">
                        MARCADOR CLAVE: {res['away_abbr']} {res['exact_away']} - {res['exact_home']} {res['home_abbr']}  |  TOTAL O/U: {res['total_ou']:.1f}
                    </div>
                </div>
                <div class="tv-team-side right">
                    <div>
                        <div class="tv-team-name">{res['home_name']} ({res['home_abbr']})</div>
                        <div class="tv-team-sub">QB Titular: {res['home_qb']}</div>
                        <div style="font-family:'JetBrains Mono',monospace; font-size:0.73rem; color:#8A99AD; margin-top:2px;">
                            EPA Comp: {res['epa_comp_home']:+.3f} | Success Off: {res['sr_off_home']}% | Pace: {res['pace_home']}s
                        </div>
                    </div>
                    {escudo_home_big}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- B. FILA 1: WIN %, SPREAD PROYECTADO / COBERTURA Y TOTALES ---
    c_m1, c_m2, c_m3 = st.columns(3)

    with c_m1:
        st.markdown(
            f"""
            <div class="quant-card">
                <div class="quant-card-header">🏆 PROBABILIDAD DE VICTORIA (WIN % & FAIR ODDS)</div>
                <div class="metric-row">
                    <span class="metric-label">{res['home_name']} ({res['home_abbr']} · Local)</span>
                    <span>
                        <span class="metric-val">{res['win_home_pct']}%</span>
                        <span class="odds-chip green">Fair: {res['ml_home_dec']} ({res['ml_home_am']})</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">{res['away_name']} ({res['away_abbr']} · Visita)</span>
                    <span>
                        <span class="metric-val">{res['win_away_pct']}%</span>
                        <span class="odds-chip">Fair: {res['ml_away_dec']} ({res['ml_away_am']})</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Duelo de QBs Titulares</span>
                    <span class="odds-chip amber">{res['away_qb']} vs {res['home_qb']}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c_m2:
        spread_away_proj = -res["spread_proyectado"]
        spread_away_ref = -res["spread_ref_line"]
        st.markdown(
            f"""
            <div class="quant-card">
                <div class="quant-card-header">📏 SPREAD PROYECTADO Y COBERTURA DE LÍNEA</div>
                <div class="metric-row">
                    <span class="metric-label">Spread Justo Proyectado</span>
                    <span class="metric-val">{res['home_abbr']} {res['spread_proyectado']:+.1f} ({res['away_abbr']} {spread_away_proj:+.1f})</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">{res['home_abbr']} cubre ({res['spread_ref_line']:+.1f})</span>
                    <span>
                        <span class="metric-val">{res['cover_home_pct']}%</span>
                        <span class="odds-chip green">Fair: {res['sp_home_dec']} ({res['sp_home_am']})</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">{res['away_abbr']} cubre ({spread_away_ref:+.1f})</span>
                    <span>
                        <span class="metric-val">{res['cover_away_pct']}%</span>
                        <span class="odds-chip">Fair: {res['sp_away_dec']} ({res['sp_away_am']})</span>
                    </span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c_m3:
        st.markdown(
            f"""
            <div class="quant-card">
                <div class="quant-card-header">⚡ TOTAL PROYECTADO (OVER / UNDER & MONTE CARLO)</div>
                <div class="metric-row">
                    <span class="metric-label">Total Proyectado Modelo</span>
                    <span class="metric-val">{res['total_ou']:.1f} pts (Línea Ref: {res['total_ref_line']:.1f})</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">OVER {res['total_ref_line']:.1f} / UNDER {res['total_ref_line']:.1f}</span>
                    <span>
                        <span class="odds-chip green">O: {res['over_pct']}% ({res['ou_over_am']})</span>
                        <span class="odds-chip">U: {res['under_pct']}% ({res['ou_under_am']})</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Percentiles P10 / P50 / P90 (OT {res['ot_pct']}%)</span>
                    <span class="metric-val">{res['mc_p10_total']} / {res['mc_p50_total']} / {res['mc_p90_total']} pts</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

    # --- C. GRÁFICOS INTERACTIVOS DE PROBABILIDADES Y TRINCHERAS EPA ---
    st.markdown(
        '<div class="section-header"><span>📈 ANÁLISIS VISUAL DE PROBABILIDADES Y DIFERENCIALES EPA</span></div>',
        unsafe_allow_html=True,
    )
    g1, g2 = st.columns(2)

    with g1:
        if PLOTLY_AVAILABLE:
            fig_p = go.Figure()
            categorias = [
                f"Win % ({res['home_abbr']} vs {res['away_abbr']})",
                f"Spread Cover ({res['spread_ref_line']:+.1f})",
                f"Total O/U ({res['total_ref_line']:.1f})",
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
                title="Distribución de Probabilidad (5,000 Iteraciones Monte Carlo)",
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
            fig_epa = go.Figure()
            labels_epa = ["Net Pass EPA (x100)", "Net Rush EPA (x100)", "EPA Compuesto (x100)", "Success Rate Off (%)"]
            vals_home_epa = [
                res["net_pass_epa_home"] * 100.0,
                res["net_rush_epa_home"] * 100.0,
                res["epa_comp_home"] * 100.0,
                res["sr_off_home"],
            ]
            vals_away_epa = [
                res["net_pass_epa_away"] * 100.0,
                res["net_rush_epa_away"] * 100.0,
                res["epa_comp_away"] * 100.0,
                res["sr_off_away"],
            ]
            fig_epa.add_trace(
                go.Bar(
                    x=labels_epa,
                    y=vals_home_epa,
                    name=f"{res['home_abbr']} (Local)",
                    marker_color="#00E676",
                    text=[f"{v:.1f}" for v in vals_home_epa],
                    textposition="auto",
                )
            )
            fig_epa.add_trace(
                go.Bar(
                    x=labels_epa,
                    y=vals_away_epa,
                    name=f"{res['away_abbr']} (Visita)",
                    marker_color="#FFB300",
                    text=[f"{v:.1f}" for v in vals_away_epa],
                    textposition="auto",
                )
            )
            fig_epa.update_layout(
                title="Comparativa de Eficiencia EPA Neto (x100) y Success Rate",
                barmode="group",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(12,19,34,0.85)",
                font=dict(family="JetBrains Mono, monospace", color="#ECF2F8", size=11),
                height=290,
                margin=dict(l=10, r=10, t=40, b=10),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig_epa, use_container_width=True)

    # Frecuencia de Key Numbers NFL
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