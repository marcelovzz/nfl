#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MÓDULO 3: app_nfl.py
Interfaz Principal de "TERMINAL SHARP: NFL QUANT"
  - Gestión de base de datos vía archivo Excel (.xlsx) en st.sidebar con persistencia
    en st.session_state.nfl_stats y descarga directa de nfl_stats_calibrado.xlsx
    mediante io.BytesIO() para conservar el aprendizaje Kalman entre semanas.
  - Separación de vistas en dos pestañas principales mediante st.tabs:
    1) "🏈 Cartelera & Momios en Vivo": Muestra exclusivamente los partidos pendientes
       o en curso en cuadrícula de 3 columnas con auditoría +EV en FORMATO DECIMAL
       (con Shrinkage Bayesiano profesional: máx +5% a +12% EV en líneas 1.91).
    2) "📈 Auditoría & Calibración": Muestra los partidos con estado FINAL, comparando
       Marcador Real vs. Modelo Previo (ocultando los badges de apuestas en juegos ya
       concluidos) e integra el botón global "⚡ Calibrar Todos los Partidos Finalizados"
       para ejecutar el ajuste bayesiano/Kalman de toda la jornada en una sola pasada.
"""

import copy
import os
from typing import Any, Dict, List, Optional
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from sync_espn_nfl import (
    NFL_FRANCHISE_NAMES,
    obtener_calendario_nfl_semana,
    obtener_lineas_mercado_nfl,
    obtener_logo_nfl,
)
from engine_nfl import (
    REQUIRED_EXCEL_COLUMNS,
    auditar_partido_nfl,
    calibrar_stats_nfl,
    generar_plantilla_excel_bytes,
    obtener_stats_nfl_default,
    run_simulacion_nfl,
    validar_y_parsear_excel_nfl,
)

# ==============================================================================
# CONFIGURACIÓN DE PÁGINA Y ESTILOS CSS (CYBER-QUANT / GLASSMORPHISM)
# ==============================================================================
st.set_page_config(
    page_title="TERMINAL SHARP: NFL QUANT",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inyectar_estilos_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600;700;800&display=swap');

        .stApp {
            background-color: #070A10;
            color: #E6EDF3;
            font-family: 'Inter', sans-serif;
        }
        [data-testid="stSidebar"] {
            background-color: #0B1018 !important;
            border-right: 1px solid #1E293B !important;
        }

        /* Header Principal */
        .terminal-banner {
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.14) 0%, rgba(13, 18, 28, 0.96) 55%, rgba(56, 189, 248, 0.12) 100%);
            border: 1px solid rgba(56, 189, 248, 0.30);
            border-left: 5px solid #10B981;
            border-radius: 14px;
            padding: 18px 24px;
            margin-bottom: 18px;
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.45);
        }
        .terminal-title {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.55rem;
            font-weight: 800;
            letter-spacing: 0.8px;
            color: #F8FAFC;
            margin: 0;
        }
        .terminal-sub {
            font-size: 0.86rem;
            color: #94A3B8;
            margin-top: 4px;
        }

        /* Tarjeta de Cartelera (Grid 3 columnas) */
        .nfl-game-card {
            background: linear-gradient(180deg, rgba(19, 26, 40, 0.92) 0%, rgba(12, 17, 27, 0.97) 100%);
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 14px;
            padding: 16px 16px 12px 16px;
            margin-bottom: 8px;
            transition: all 0.2s ease-in-out;
            box-shadow: 0 8px 22px rgba(0, 0, 0, 0.42);
        }
        .nfl-game-card:hover {
            border-color: #38BDF8;
            box-shadow: 0 10px 28px rgba(56, 189, 248, 0.18);
            transform: translateY(-2px);
        }
        .card-top-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255, 255, 255, 0.07);
            padding-bottom: 8px;
            margin-bottom: 12px;
        }
        .league-pill {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.70rem;
            font-weight: 700;
            color: #38BDF8;
            background: rgba(56, 189, 248, 0.12);
            border: 1px solid rgba(56, 189, 248, 0.30);
            padding: 3px 9px;
            border-radius: 999px;
            text-transform: uppercase;
        }
        .league-pill-final {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.70rem;
            font-weight: 700;
            color: #F59E0B;
            background: rgba(245, 158, 11, 0.14);
            border: 1px solid rgba(245, 158, 11, 0.40);
            padding: 3px 9px;
            border-radius: 999px;
            text-transform: uppercase;
        }
        .game-clock {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.72rem;
            color: #94A3B8;
        }

        /* Filas de Equipos con Escudos CDN */
        .team-match-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 7px 6px;
            border-radius: 8px;
            margin-bottom: 5px;
            background: rgba(255, 255, 255, 0.025);
        }
        .team-left {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .team-logo-img {
            width: 34px;
            height: 34px;
            object-fit: contain;
            filter: drop-shadow(0 2px 4px rgba(0,0,0,0.5));
        }
        .team-abbr-txt {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.98rem;
            font-weight: 800;
            color: #F8FAFC;
        }
        .team-qb-sub {
            font-size: 0.73rem;
            color: #94A3B8;
            display: block;
        }
        .team-proj-pts {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.15rem;
            font-weight: 800;
            color: #10B981;
        }
        .team-real-pts {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.22rem;
            font-weight: 800;
            color: #F59E0B;
        }

        /* Cintillos de Auditoría +EV (Solo para juegos pendientes/en vivo) */
        .ev-badge-positive {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.72rem;
            font-weight: 700;
            color: #ECFDF5;
            background: linear-gradient(90deg, rgba(5, 150, 105, 0.40) 0%, rgba(16, 185, 129, 0.22) 100%);
            border: 1px solid #10B981;
            border-radius: 8px;
            padding: 6px 9px;
            margin-top: 6px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 10px rgba(16, 185, 129, 0.15);
        }
        .ev-badge-neutral {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.71rem;
            font-weight: 600;
            color: #94A3B8;
            background: rgba(15, 23, 42, 0.75);
            border: 1px solid rgba(148, 163, 184, 0.20);
            border-radius: 8px;
            padding: 6px 9px;
            margin-top: 6px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .ev-pct-pill {
            background: rgba(16, 185, 129, 0.28);
            color: #6EE7B7;
            padding: 1px 6px;
            border-radius: 5px;
            font-weight: 800;
            font-size: 0.69rem;
        }
        .ev-pct-pill-gray {
            background: rgba(148, 163, 184, 0.14);
            color: #94A3B8;
            padding: 1px 6px;
            border-radius: 5px;
            font-weight: 600;
            font-size: 0.68rem;
        }

        /* Caja de Auditoría Post-Partido (Pestaña de Auditoría & Calibración) */
        .kalman-audit-box {
            background: linear-gradient(135deg, rgba(245, 158, 11, 0.13) 0%, rgba(15, 23, 42, 0.94) 100%);
            border: 1px solid rgba(245, 158, 11, 0.42);
            border-radius: 10px;
            padding: 11px 13px;
            margin-top: 9px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.74rem;
        }
        .kalman-calibrated-pill {
            display: inline-block;
            background: rgba(16, 185, 129, 0.22);
            border: 1px solid #10B981;
            color: #6EE7B7;
            padding: 2px 8px;
            border-radius: 999px;
            font-size: 0.67rem;
            font-weight: 700;
        }

        /* Caja de pronóstico rápido */
        .quick-forecast-box {
            background: rgba(56, 189, 248, 0.07);
            border: 1px solid rgba(56, 189, 248, 0.24);
            border-radius: 9px;
            padding: 8px 10px;
            margin-top: 8px;
            text-align: center;
        }
        .quick-forecast-txt {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.80rem;
            font-weight: 700;
            color: #E2E8F0;
        }
        .quick-fair-sub {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.72rem;
            color: #38BDF8;
            margin-top: 3px;
        }

        /* Scoreboard TV Header en Vista Detallada */
        .tv-scoreboard {
            background: linear-gradient(135deg, #111927 0%, #0A0F18 100%);
            border: 1px solid #26334D;
            border-top: 4px solid #38BDF8;
            border-radius: 16px;
            padding: 22px 26px;
            margin-bottom: 18px;
            box-shadow: 0 14px 36px rgba(0, 0, 0, 0.55);
        }
        .kpi-glass {
            background: rgba(17, 24, 39, 0.86);
            border: 1px solid rgba(148, 163, 184, 0.20);
            border-radius: 12px;
            padding: 14px 16px;
            text-align: center;
        }
        .kpi-title {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: #94A3B8;
        }
        .kpi-number {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.38rem;
            font-weight: 800;
            color: #F8FAFC;
            margin-top: 4px;
        }
        .kpi-sub {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: #10B981;
            margin-top: 2px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_logo_html(logo_str: str, abbr: str, size: int = 34) -> str:
    """Garantiza renderizado limpio tanto si obtener_logo_nfl devuelve tag <img> como si devuelve URL."""
    clean = str(logo_str or "").strip()
    if clean.startswith("<img"):
        return clean
    return (
        f'<img src="{clean}" alt="{abbr}" width="{size}" height="{size}" '
        f'style="width:{size}px; height:{size}px; object-fit:contain;">'
    )


# ==============================================================================
# FLUJO HÍBRIDO DE CARGA DE DATOS (REPOSITORIO LOCAL + UPLOADER OPCIONAL)
# ==============================================================================
NOMBRE_ARCHIVO_DEFECTO: str = "nfl_stats.xlsx"
ARCHIVOS_RESPALDO_REPO: List[str] = [
    "nfl_stats.xlsx",
    "nfl_stats.csv",
    "nfl_stats_completo.csv",
]


def cargar_datos_base(ruta_archivo: str = NOMBRE_ARCHIVO_DEFECTO) -> Optional[pd.DataFrame]:
    """
    Comprueba con os.path.exists() si el archivo predeterminado ('nfl_stats.xlsx'
    o su equivalente '.csv') existe en el disco/repositorio y lo lee automáticamente.
    Si no existe ningún archivo local en el repositorio, retorna None.
    """
    rutas_candidatas = [ruta_archivo] + [
        r for r in ARCHIVOS_RESPALDO_REPO if r != ruta_archivo
    ]
    for ruta in rutas_candidatas:
        if os.path.exists(ruta):
            if str(ruta).lower().endswith(".csv"):
                return pd.read_csv(ruta)
            return pd.read_excel(ruta)
    return None


def _leer_archivo_subido(archivo_subido: Any) -> pd.DataFrame:
    """Lee un archivo subido (.xlsx o .csv) desde st.file_uploader."""
    nombre_archivo = str(getattr(archivo_subido, "name", "")).lower()
    if nombre_archivo.endswith(".csv"):
        return pd.read_csv(archivo_subido)
    return pd.read_excel(archivo_subido)


# ==============================================================================
# INICIALIZACIÓN DE ESTADO EN ST.SESSION_STATE
# ==============================================================================
def inicializar_session_state() -> None:
    if "df_nfl" not in st.session_state:
        df_base = cargar_datos_base(NOMBRE_ARCHIVO_DEFECTO)
        st.session_state.df_nfl = df_base
        if df_base is not None:
            st.session_state.nfl_stats = validar_y_parsear_excel_nfl(df_base)
            st.session_state.nfl_stats_source = (
                f"Repositorio Local: {NOMBRE_ARCHIVO_DEFECTO} ({len(df_base)} eq.)"
            )
        else:
            st.session_state.nfl_stats = None
            st.session_state.nfl_stats_source = "Sin archivo base en el repositorio"
    elif "nfl_stats" not in st.session_state:
        if st.session_state.df_nfl is not None:
            st.session_state.nfl_stats = validar_y_parsear_excel_nfl(st.session_state.df_nfl)
        else:
            st.session_state.nfl_stats = None

    if "nfl_stats_source" not in st.session_state:
        st.session_state.nfl_stats_source = f"Repositorio Local: {NOMBRE_ARCHIVO_DEFECTO}"
    if "ultimo_archivo_subido_id" not in st.session_state:
        st.session_state.ultimo_archivo_subido_id = None
    if "semana_actual" not in st.session_state:
        st.session_state.semana_actual = 8
    if "odds_api_key" not in st.session_state:
        st.session_state.odds_api_key = ""
    if "viento_mph_global" not in st.session_state:
        st.session_state.viento_mph_global = 8.0
    if "learning_rate_kalman" not in st.session_state:
        st.session_state.learning_rate_kalman = 0.06
    if "partidos_semana" not in st.session_state:
        st.session_state.partidos_semana = obtener_calendario_nfl_semana(
            semana=st.session_state.semana_actual,
            api_key=st.session_state.odds_api_key,
        )
    if "partido_seleccionado" not in st.session_state:
        st.session_state.partido_seleccionado = None
    if "simulaciones_cache" not in st.session_state:
        st.session_state.simulaciones_cache = {}
    if "simulaciones_previas" not in st.session_state:
        st.session_state.simulaciones_previas = {}
    if "partidos_calibrados" not in st.session_state:
        st.session_state.partidos_calibrados = set()
    if "historial_calibraciones" not in st.session_state:
        st.session_state.historial_calibraciones = []


def obtener_simulacion_partido(partido: Dict[str, Any]) -> Dict[str, Any]:
    """Calcula o recupera de caché la simulación por series ofensivas (11.5 drives/equipo, 5,000 iteraciones)."""
    pid = str(partido.get("id_partido", f"{partido['away_abbr']}_{partido['home_abbr']}"))
    away = partido["away_abbr"]
    home = partido["home_abbr"]

    lineas_mercado = {
        "total_mercado": partido.get("total_mercado", 43.5),
        "cuota_over_decimal": partido.get("cuota_over_decimal", 1.91),
        "cuota_under_decimal": partido.get("cuota_under_decimal", 1.91),
        "spread_mercado_home": partido.get("spread_mercado_home", -2.5),
        "cuota_spread_home_decimal": partido.get("cuota_spread_home_decimal", 1.91),
        "cuota_spread_away_decimal": partido.get("cuota_spread_away_decimal", 1.91),
        "fuente_odds": partido.get("fuente_odds", "ESPN Scoreboard (Decimal)"),
    }

    viento_partido = float(partido.get("viento_mph", st.session_state.get("viento_mph_global", 8.0)))

    if pid not in st.session_state.simulaciones_cache:
        sim = run_simulacion_nfl(
            away_abbr=away,
            home_abbr=home,
            nfl_stats_dict=st.session_state.nfl_stats,
            n_sims=5000,
            lineas_mercado=lineas_mercado,
            viento_mph=viento_partido,
            tipo_estadio="Auto",
        )
        st.session_state.simulaciones_cache[pid] = sim
        if pid not in st.session_state.simulaciones_previas:
            st.session_state.simulaciones_previas[pid] = copy.deepcopy(sim)

    return st.session_state.simulaciones_cache[pid]


def aplicar_calibracion_partido_en_estado(partido: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ejecuta el ciclo completo de auditoría y calibración Kalman sobre un partido finalizado,
    actualiza st.session_state.nfl_stats y recalcula inmediatamente las simulaciones de
    todos los partidos pendientes.
    """
    pid = str(partido.get("id_partido", f"{partido['away_abbr']}_{partido['home_abbr']}"))
    away = partido["away_abbr"]
    home = partido["home_abbr"]

    sim_previa = st.session_state.simulaciones_previas.get(pid) or obtener_simulacion_partido(partido)
    auditoria = auditar_partido_nfl(sim_previa, partido)

    lr = float(st.session_state.get("learning_rate_kalman", 0.06))

    stats_antes_away = copy.deepcopy(st.session_state.nfl_stats.get(away, {}))
    stats_antes_home = copy.deepcopy(st.session_state.nfl_stats.get(home, {}))

    nuevo_dict = calibrar_stats_nfl(
        nfl_stats_dict=st.session_state.nfl_stats,
        away_abbr=away,
        home_abbr=home,
        error_away=auditoria["error_away"],
        error_home=auditoria["error_home"],
        learning_rate=lr,
        auditoria_info=auditoria,
    )

    st.session_state.nfl_stats = nuevo_dict
    st.session_state.df_nfl = pd.DataFrame(
        [v for k, v in nuevo_dict.items() if k not in ("LAR", "WSH")]
    )
    st.session_state.partidos_calibrados.add(pid)
    st.session_state.nfl_stats_source = (
        f"Base Calibrada Kalman ({len(st.session_state.partidos_calibrados)} juegos auditados)"
    )
    st.session_state.simulaciones_cache = {}

    stats_despues_away = st.session_state.nfl_stats.get(away, {})
    stats_despues_home = st.session_state.nfl_stats.get(home, {})

    registro_log = {
        "id_partido": pid,
        "Partida": f"{away} @ {home}",
        "Marcador_Real": f"{home} {int(round(auditoria['puntos_home_real']))} - {int(round(auditoria['puntos_away_real']))} {away}",
        "Modelo_Previo": f"{home} {auditoria['home_pts_modelo']:.1f} - {auditoria['away_pts_modelo']:.1f} {away}",
        "Error_Spread": f"{auditoria['error_spread']:+.1f} pts",
        "Error_Total": f"{auditoria['error_total']:+.1f} pts",
        "Diagnostico": auditoria["origen_desviacion"],
        "Delta_EPA_Pass_Away": f"{stats_antes_away.get('EPA_Pass_Off', 0):.3f} → {stats_despues_away.get('EPA_Pass_Off', 0):.3f}",
        "Delta_EPA_Pass_Home": f"{stats_antes_home.get('EPA_Pass_Off', 0):.3f} → {stats_despues_home.get('EPA_Pass_Off', 0):.3f}",
        "Pace_Sec_Home": f"{stats_antes_home.get('Pace_Sec', 27.0):.1f}s → {stats_despues_home.get('Pace_Sec', 27.0):.1f}s",
    }
    st.session_state.historial_calibraciones.append(registro_log)
    return auditoria


def calibrar_todos_los_finalizados(partidos_finalizados: List[Dict[str, Any]]) -> int:
    """
    Ejecuta la calibración masiva bayesiana/Kalman en una sola pasada sobre todas
    las discrepancias de los partidos finalizados de la jornada.
    """
    if not partidos_finalizados:
        return 0
    pendientes = [
        pf
        for pf in partidos_finalizados
        if str(pf.get("id_partido", f"{pf['away_abbr']}_{pf['home_abbr']}"))
        not in st.session_state.partidos_calibrados
    ]
    objetivo = pendientes if pendientes else partidos_finalizados
    for pf in objetivo:
        aplicar_calibracion_partido_en_estado(pf)
    return len(objetivo)


# ==============================================================================
# BARRA LATERAL: CARGA DE EXCEL (.XLSX), DESCARGA CALIBRADA Y LEARNING RATE KALMAN
# ==============================================================================
def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### 🏈 TERMINAL SHARP: NFL QUANT")
        st.caption("Drives Dinámicos (9.4-12.6/Eq) · EV Continuo · Filtro Kalman")

        st.markdown("#### 1. Base de Datos Híbrida (`.xlsx` / `.csv`)")
        archivo_subido = st.file_uploader(
            "Actualizar métricas (Opcional)",
            type=["xlsx", "csv"],
            help=(
                "Opcional: Si no subes ningún archivo, la app utiliza automáticamente "
                f"'{NOMBRE_ARCHIVO_DEFECTO}' del repositorio. Columnas requeridas: "
                "Team_Abbr, QB_Name, EPA_Pass_Off, EPA_Rush_Off, EPA_Pass_Def, "
                "EPA_Rush_Def, Success_Rate_Off, Success_Rate_Def, Pace_Sec."
            ),
        )

        if archivo_subido is not None:
            file_id = f"{archivo_subido.name}_{archivo_subido.size}"
            try:
                if str(archivo_subido.name).lower().endswith(".csv"):
                    st.session_state.df_nfl = pd.read_csv(archivo_subido)
                else:
                    st.session_state.df_nfl = pd.read_excel(archivo_subido)

                parsed_dict = validar_y_parsear_excel_nfl(st.session_state.df_nfl)
                st.session_state.nfl_stats = parsed_dict
                st.session_state.nfl_stats_source = (
                    f"Archivo Subido: {archivo_subido.name} ({len(st.session_state.df_nfl)} eq.)"
                )
                if st.session_state.ultimo_archivo_subido_id != file_id:
                    st.session_state.ultimo_archivo_subido_id = file_id
                    st.session_state.simulaciones_cache = {}
                    st.session_state.simulaciones_previas = {}
                    st.session_state.partidos_calibrados = set()
                st.success(f"Métricas actualizadas desde '{archivo_subido.name}'.")
            except Exception as exc:
                st.error(f"Error al leer o validar el archivo subido: {exc}")

        if st.button("🔄 Restaurar archivo del repositorio", use_container_width=True):
            df_repo = cargar_datos_base(NOMBRE_ARCHIVO_DEFECTO)
            if df_repo is not None:
                st.session_state.df_nfl = df_repo
                st.session_state.nfl_stats = validar_y_parsear_excel_nfl(df_repo)
                st.session_state.nfl_stats_source = (
                    f"Repositorio Local: {NOMBRE_ARCHIVO_DEFECTO} ({len(df_repo)} eq.)"
                )
                st.session_state.ultimo_archivo_subido_id = None
                st.session_state.simulaciones_cache = {}
                st.session_state.simulaciones_previas = {}
                st.session_state.partidos_calibrados = set()
                st.session_state.historial_calibraciones = []
                st.rerun()
            else:
                st.session_state.df_nfl = None
                st.session_state.nfl_stats = None
                st.rerun()

        if st.session_state.get("df_nfl") is not None and st.session_state.get("nfl_stats") is not None:
            st.info(f"**Fuente activa:** {st.session_state.nfl_stats_source}")
            excel_calibrado_bytes = generar_plantilla_excel_bytes(st.session_state.nfl_stats)
            st.download_button(
                label="📥 Descargar nfl_stats_calibrado.xlsx",
                data=excel_calibrado_bytes,
                file_name="nfl_stats_calibrado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                help=(
                    "Exporta en memoria (BytesIO) el diccionario st.session_state.nfl_stats con "
                    "los últimos ajustes de EPA y Pace_Sec para reutilizarlo la próxima semana."
                ),
            )

        st.markdown("---")
        st.markdown("#### 2. Bucle Kalman (Auto-Corrección)")
        lr_val = st.slider(
            "Tasa de Aprendizaje Kalman (Learning Rate)",
            min_value=0.04,
            max_value=0.08,
            value=float(st.session_state.learning_rate_kalman),
            step=0.005,
            format="%.3f",
            help=(
                "Controla la magnitud del ajuste en EPA_Pass, EPA_Rush, Success_Rate y Pace_Sec "
                "tras auditar un partido finalizado (recomendado: 0.04 a 0.08 para evitar sobreajuste)."
            ),
        )
        st.session_state.learning_rate_kalman = float(lr_val)

        if st.session_state.partidos_calibrados:
            st.caption(
                f"⚡ **{len(st.session_state.partidos_calibrados)} partido(s)** calibrados en la sesión actual."
            )
            if st.button("↩️ Restaurar Ratings Originales", use_container_width=True):
                df_orig = cargar_datos_base(NOMBRE_ARCHIVO_DEFECTO)
                if df_orig is not None:
                    st.session_state.df_nfl = df_orig
                    st.session_state.nfl_stats = validar_y_parsear_excel_nfl(df_orig)
                    st.session_state.nfl_stats_source = f"Repositorio Local: {NOMBRE_ARCHIVO_DEFECTO} ({len(df_orig)} eq.)"
                else:
                    st.session_state.nfl_stats = obtener_stats_nfl_default()
                    st.session_state.nfl_stats_source = "Base Pre-Cargada (32 Franquicias NFL)"
                st.session_state.simulaciones_cache = {}
                st.session_state.simulaciones_previas = {}
                st.session_state.partidos_calibrados = set()
                st.session_state.historial_calibraciones = []
                st.rerun()

        st.markdown("---")
        st.markdown("#### 3. Sincronización ESPN & Momios")
        semana_sel = st.selectbox(
            "Semana NFL (Temporada Regular)",
            options=list(range(1, 19)),
            index=int(st.session_state.semana_actual) - 1,
        )

        api_key_input = st.text_input(
            "The Odds API Key (Opcional)",
            value=st.session_state.odds_api_key,
            type="password",
            help=(
                "Si se deja vacía, el sistema usa automáticamente las líneas de consenso "
                "de ESPN Scoreboard convertidas a FORMATO DECIMAL."
            ),
        )

        viento_input = st.slider(
            "Viento Estimado en Estadios Abiertos (mph)",
            min_value=0.0,
            max_value=30.0,
            value=float(st.session_state.viento_mph_global),
            step=1.0,
            help=(
                "Si supera 14 mph en estadios abiertos (Outdoor), el motor penaliza la tasa de "
                "éxito de Field Goals largos y reduce EPA_Pass_Off."
            ),
        )

        if viento_input != st.session_state.viento_mph_global:
            st.session_state.viento_mph_global = float(viento_input)
            st.session_state.simulaciones_cache = {}

        if st.button("🔄 Sincronizar Calendario y Momios", use_container_width=True, type="primary"):
            st.session_state.semana_actual = int(semana_sel)
            st.session_state.odds_api_key = api_key_input.strip()
            st.session_state.partidos_semana = obtener_calendario_nfl_semana(
                semana=int(semana_sel),
                api_key=st.session_state.odds_api_key or None,
            )
            st.session_state.simulaciones_cache = {}
            st.session_state.simulaciones_previas = {}
            st.session_state.partidos_calibrados = set()
            st.session_state.partido_seleccionado = None
            st.rerun()

        if st.session_state.partido_seleccionado is not None:
            st.markdown("---")
            if st.button("⬅️ Volver a la Cartelera", use_container_width=True):
                st.session_state.partido_seleccionado = None
                st.rerun()

        with st.expander("📋 Ver Tabla de 32 Franquicias (En Memoria)"):
            df_preview = pd.DataFrame(
                [
                    v
                    for k, v in (st.session_state.get("nfl_stats") or {}).items()
                    if k not in ("LAR", "WSH")
                ]
            )
            if not df_preview.empty:
                cols_order = [c for c in REQUIRED_EXCEL_COLUMNS if c in df_preview.columns]
                st.dataframe(
                    df_preview[cols_order].sort_values("EPA_Pass_Off", ascending=False),
                    use_container_width=True,
                    hide_index=True,
                )


# ==============================================================================
# VISTA A: PESTAÑAS SEPARADAS (EN VIVO vs. AUDITORÍA & CALIBRACIÓN MASIVA)
# ==============================================================================
def render_vista_cartelera() -> None:
    semana = st.session_state.semana_actual
    partidos: List[Dict[str, Any]] = st.session_state.partidos_semana

    st.markdown(
        f"""
        <div class="terminal-banner">
            <p class="terminal-title">🏈 TERMINAL SHARP: NFL QUANT — SEMANA {semana}</p>
            <p class="terminal-sub">
                Drive-Based Engine (Drives Dinámicos por Pace 9.4–12.6/Eq · Media 43.0–45.5 pts · 5,000 Iteraciones) ·
                Shrinkage Bayesiano +EV en <b>Cuota Decimal</b> · Auto-Corrección Dinámica (Filtro Kalman)
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not partidos:
        st.warning("No se encontraron partidos para la semana seleccionada.")
        return

    # Separar estrictamente partidos en vivo/pendientes de los finalizados (STATUS_FINAL)
    partidos_en_vivo: List[Dict[str, Any]] = []
    partidos_finalizados: List[Dict[str, Any]] = []
    total_ev_en_vivo = 0

    for p in partidos:
        sim_p = obtener_simulacion_partido(p)
        if p.get("finalizado", False):
            partidos_finalizados.append(p)
        else:
            partidos_en_vivo.append(p)
            if sim_p["ev_totales"]["hay_valor"] or sim_p["ev_spread"]["hay_valor"]:
                total_ev_en_vivo += 1

    fuente_detectada = partidos[0].get("fuente_odds", "ESPN Scoreboard (Decimal)")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Juegos Pendientes / En Vivo", f"{len(partidos_en_vivo)} Partidos")
    k2.metric("Oportunidades +EV (En Vivo)", f"{total_ev_en_vivo} con Ventaja")
    k3.metric("Partidos Finalizados (Auditables)", f"{len(partidos_finalizados)} Finales")
    k4.metric("Learning Rate / Fuente", f"LR {st.session_state.learning_rate_kalman:.3f} · {fuente_detectada[:14]}")

    # SEPARACIÓN DE VISTAS MEDIANTE ST.TABS
    tab_vivo, tab_auditoria = st.tabs(
        ["🏈 Cartelera & Momios en Vivo", "📈 Auditoría & Calibración"]
    )

    # --------------------------------------------------------------------------
    # PESTAÑA 1: SOLO JUEGOS PENDIENTES O EN CURSO CON BADGES +EV
    # --------------------------------------------------------------------------
    with tab_vivo:
        if not partidos_en_vivo:
            st.info(
                "Todos los partidos de esta semana han concluido (`STATUS_FINAL`). "
                "Cambia a la pestaña **📈 Auditoría & Calibración** para auditar los marcadores reales y recalibrar el modelo."
            )
        else:
            st.markdown(
                f"#### 📅 Cartelera Activa y Momios en Formato Decimal ({len(partidos_en_vivo)} Juegos en Curso / Programados)"
            )
            for row_start in range(0, len(partidos_en_vivo), 3):
                cols = st.columns(3)
                chunk = partidos_en_vivo[row_start : row_start + 3]

                for idx, partido in enumerate(chunk):
                    with cols[idx]:
                        pid = str(partido.get("id_partido", f"{partido['away_abbr']}_{partido['home_abbr']}"))
                        sim = obtener_simulacion_partido(partido)
                        away = partido["away_abbr"]
                        home = partido["home_abbr"]
                        logo_away_html = _render_logo_html(obtener_logo_nfl(away, size=34), away, size=34)
                        logo_home_html = _render_logo_html(obtener_logo_nfl(home, size=34), home, size=34)

                        ev_tot = sim["ev_totales"]
                        ev_spr = sim["ev_spread"]

                        # Cintillo 1: Auditoría de TOTALES (Over / Under en Cuota Decimal con Shrinkage)
                        if ev_tot["hay_valor"]:
                            tot_badge_html = (
                                f'<div class="ev-badge-positive">'
                                f'<span>🔥 VALOR: {ev_tot["recomendacion"]} ({ev_tot["cuota_mercado_decimal"]:.2f})</span>'
                                f'<span class="ev-pct-pill">EV: +{ev_tot["ev_pct"]:.1f}%</span>'
                                f'</div>'
                            )
                        else:
                            tot_badge_html = (
                                f'<div class="ev-badge-neutral">'
                                f'<span>⚖️ TOTAL {ev_tot["total_mercado"]:.1f} SIN VALOR</span>'
                                f'<span class="ev-pct-pill-gray">O {ev_tot["cuota_over_decimal"]:.2f} | U {ev_tot["cuota_under_decimal"]:.2f}</span>'
                                f'</div>'
                            )

                        # Cintillo 2: Auditoría de HÁNDICAP / SPREAD (en Cuota Decimal con Shrinkage)
                        if ev_spr["hay_valor"]:
                            spr_badge_html = (
                                f'<div class="ev-badge-positive">'
                                f'<span>🔥 VALOR: {ev_spr["recomendacion"]} ({ev_spr["cuota_mercado_decimal"]:.2f})</span>'
                                f'<span class="ev-pct-pill">EV: +{ev_spr["ev_pct"]:.1f}%</span>'
                                f'</div>'
                            )
                        else:
                            spr_home_fmt = f"{home} {ev_spr['spread_mercado_home']:+.1f}"
                            spr_badge_html = (
                                f'<div class="ev-badge-neutral">'
                                f'<span>⚖️ SPREAD ({spr_home_fmt}) SIN VALOR</span>'
                                f'<span class="ev-pct-pill-gray">{ev_spr["cuota_spread_home_decimal"]:.2f} / {ev_spr["cuota_spread_away_decimal"]:.2f}</span>'
                                f'</div>'
                            )

                        drives_away_card = float(sim.get("drives_away", sim["n_drives_equipo"]))
                        drives_home_card = float(sim.get("drives_home", sim["n_drives_equipo"]))

                        card_live_html = (
                            f'<div class="nfl-game-card">'
                            f'<div class="card-top-bar">'
                            f'<span class="league-pill">NFL · SEMANA {semana}</span>'
                            f'<span class="game-clock">{partido.get("hora", "TBD")} · {sim["tipo_estadio"]} ({sim["pace_combinado"]:.1f}s/play)</span>'
                            f'</div>'
                            f'<div class="team-match-row">'
                            f'<div class="team-left">'
                            f'{logo_away_html}'
                            f'<div>'
                            f'<span class="team-abbr-txt">{away} · {NFL_FRANCHISE_NAMES.get(away, away)}</span>'
                            f'<span class="team-qb-sub">QB: {sim["away_qb"]} · {drives_away_card:.1f} drives (TD {sim["drive_td_pct_away"]:.0f}% · FG {sim["drive_fg_pct_away"]:.0f}%)</span>'
                            f'</div>'
                            f'</div>'
                            f'<div class="team-proj-pts">{sim["away_pts"]:.1f}</div>'
                            f'</div>'
                            f'<div class="team-match-row">'
                            f'<div class="team-left">'
                            f'{logo_home_html}'
                            f'<div>'
                            f'<span class="team-abbr-txt">{home} · {NFL_FRANCHISE_NAMES.get(home, home)}</span>'
                            f'<span class="team-qb-sub">QB: {sim["home_qb"]} · {drives_home_card:.1f} drives (TD {sim["drive_td_pct_home"]:.0f}% · FG {sim["drive_fg_pct_home"]:.0f}%)</span>'
                            f'</div>'
                            f'</div>'
                            f'<div class="team-proj-pts">{sim["home_pts"]:.1f}</div>'
                            f'</div>'
                            f'<div class="quick-forecast-box">'
                            f'<div class="quick-forecast-txt">'
                            f'Proyección Drive-Engine: {away} {sim["away_pts"]:.1f} - {sim["home_pts"]:.1f} {home}'
                            f'</div>'
                            f'<div class="quick-fair-sub">'
                            f'Cuota Justa ML: {away} <b>{sim["ml_away_decimal"]:.2f}</b> | {home} <b>{sim["ml_home_decimal"]:.2f}</b> · '
                            f'Total Proy: <b>{sim["total_ou"]:.1f} pts</b> ({sim["drives_combinados"]:.1f} drives · HFA +{sim["hfa_pts"]:.2f})'
                            f'</div>'
                            f'</div>'
                            f'{tot_badge_html}'
                            f'{spr_badge_html}'
                            f'</div>'
                        )
                        st.markdown(card_live_html, unsafe_allow_html=True)

                        if st.button(
                            "LEER ANÁLISIS →",
                            key=f"btn_drill_live_{pid}_{row_start}_{idx}",
                            use_container_width=True,
                        ):
                            st.session_state.partido_seleccionado = partido
                            st.rerun()

    # --------------------------------------------------------------------------
    # PESTAÑA 2: AUDITORÍA & CALIBRACIÓN MASIVA (SIN BADGES DE APUESTAS)
    # --------------------------------------------------------------------------
    with tab_auditoria:
        st.markdown("#### 📈 Auditoría Post-Partido (`STATUS_FINAL`) y Calibración Bayesiana / Kalman")

        if not partidos_finalizados:
            st.info(
                "Aún no hay partidos finalizados (`STATUS_FINAL`) en esta semana para auditar contra el modelo."
            )
        else:
            pendientes_calibrar = [
                pf
                for pf in partidos_finalizados
                if str(pf.get("id_partido", f"{pf['away_abbr']}_{pf['home_abbr']}"))
                not in st.session_state.partidos_calibrados
            ]

            col_hdr_info, col_hdr_btn = st.columns([3.0, 1.5])
            with col_hdr_info:
                st.markdown(
                    f"Se detectaron **{len(partidos_finalizados)} partidos concluidos (`FINAL`)** en la jornada "
                    f"(**{len(pendientes_calibrar)}** pendientes de calibrar). Presiona el botón global para ajustar "
                    f"`EPA_Pass`, `EPA_Rush`, `Success_Rate` y `Pace_Sec` de todas las franquicias en una sola pasada."
                )
            with col_hdr_btn:
                if st.button(
                    "⚡ Calibrar Todos los Partidos Finalizados",
                    key="btn_global_calibrar_todos",
                    use_container_width=True,
                    type="primary",
                ):
                    n_cal = calibrar_todos_los_finalizados(partidos_finalizados)
                    st.toast(
                        f"⚡ Calibración masiva completada sobre {n_cal} partido(s) finalizado(s)."
                    )
                    st.rerun()

            if st.session_state.historial_calibraciones:
                with st.expander(
                    f"✅ Bitácora de Recalibraciones Kalman Aplicadas ({len(st.session_state.historial_calibraciones)})",
                    expanded=True,
                ):
                    st.dataframe(
                        pd.DataFrame(st.session_state.historial_calibraciones),
                        use_container_width=True,
                        hide_index=True,
                    )

            # Cuadrícula de 3 columnas de partidos finalizados (SIN badges de apuestas)
            for row_start in range(0, len(partidos_finalizados), 3):
                cols_fin = st.columns(3)
                chunk_fin = partidos_finalizados[row_start : row_start + 3]

                for idx, partido in enumerate(chunk_fin):
                    with cols_fin[idx]:
                        pid = str(partido.get("id_partido", f"{partido['away_abbr']}_{partido['home_abbr']}"))
                        sim = obtener_simulacion_partido(partido)
                        sim_prev = st.session_state.simulaciones_previas.get(pid, sim)
                        aud_card = auditar_partido_nfl(sim_prev, partido)

                        away = partido["away_abbr"]
                        home = partido["home_abbr"]
                        logo_away_html = _render_logo_html(obtener_logo_nfl(away, size=34), away, size=34)
                        logo_home_html = _render_logo_html(obtener_logo_nfl(home, size=34), home, size=34)
                        ya_calibrado = pid in st.session_state.partidos_calibrados

                        estado_cal_html = (
                            '<span class="kalman-calibrated-pill">✓ CALIBRADO</span>'
                            if ya_calibrado
                            else '<span style="color:#FBBF24; font-weight:700;">⏳ PENDIENTE</span>'
                        )

                        pts_away_real_int = int(round(aud_card["puntos_away_real"]))
                        pts_home_real_int = int(round(aud_card["puntos_home_real"]))

                        card_audit_html = (
                            f'<div class="nfl-game-card">'
                            f'<div class="card-top-bar">'
                            f'<span class="league-pill-final">NFL · S{semana} · FINAL</span>'
                            f'<span class="game-clock">{partido.get("hora", "FINAL")} · {sim["tipo_estadio"]}</span>'
                            f'</div>'
                            f'<div class="team-match-row">'
                            f'<div class="team-left">'
                            f'{logo_away_html}'
                            f'<div>'
                            f'<span class="team-abbr-txt">{away} · {NFL_FRANCHISE_NAMES.get(away, away)}</span>'
                            f'<span class="team-qb-sub">Modelo Previo: {aud_card["away_pts_modelo"]:.1f} pts ({aud_card[" error_away" if " error_away" in aud_card else "error_away"]:+.1f})</span>'
                            f'</div>'
                            f'</div>'
                            f'<div class="team-real-pts">{pts_away_real_int}</div>'
                            f'</div>'
                            f'<div class="team-match-row">'
                            f'<div class="team-left">'
                            f'{logo_home_html}'
                            f'<div>'
                            f'<span class="team-abbr-txt">{home} · {NFL_FRANCHISE_NAMES.get(home, home)}</span>'
                            f'<span class="team-qb-sub">Modelo Previo: {aud_card["home_pts_modelo"]:.1f} pts ({aud_card["error_home"]:+.1f})</span>'
                            f'</div>'
                            f'</div>'
                            f'<div class="team-real-pts">{pts_home_real_int}</div>'
                            f'</div>'
                            f'<div class="kalman-audit-box">'
                            f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:5px;">'
                            f'<span style="color:#F8FAFC; font-weight:800;">🏁 REAL vs. MODELO</span>'
                            f'{estado_cal_html}'
                            f'</div>'
                            f'<div style="color:#E2E8F0; margin-top:3px;">'
                            f'<b>Marcador Real:</b> {home} {pts_home_real_int} - {pts_away_real_int} {away}<br>'
                            f'<b>Modelo Previo:</b> {home} {aud_card["home_pts_modelo"]:.1f} - {aud_card["away_pts_modelo"]:.1f} {away}'
                            f'</div>'
                            f'<div style="color:#38BDF8; margin-top:5px; font-weight:700;">'
                            f'Desviación Spread: {aud_card["error_spread"]:+.1f} pts | Desviación Total: {aud_card["error_total"]:+.1f} pts'
                            f'</div>'
                            f'<div style="color:#94A3B8; font-size:0.68rem; margin-top:4px;">'
                            f'Diagnóstico: {aud_card["origen_desviacion"]}'
                            f'</div>'
                            f'</div>'
                            f'</div>'
                        )
                        st.markdown(card_audit_html, unsafe_allow_html=True)

                        btn_cal_label = (
                            "✅ CALIBRACIÓN APLICADA (RE-APLICAR)"
                            if ya_calibrado
                            else "⚡ APLICAR CALIBRACIÓN AL MODELO"
                        )
                        if st.button(
                            btn_cal_label,
                            key=f"btn_kalman_tab_{pid}_{row_start}_{idx}",
                            use_container_width=True,
                            type="primary" if not ya_calibrado else "secondary",
                        ):
                            aud_res = aplicar_calibracion_partido_en_estado(partido)
                            st.toast(
                                f"⚡ Modelo recalibrado con {away} @ {home} "
                                f"(Err Spread: {aud_res['error_spread']:+.1f} pts | Err Total: {aud_res['error_total']:+.1f} pts)."
                            )
                            st.rerun()

                        if st.button(
                            "VER AUDITORÍA DETALLADA →",
                            key=f"btn_drill_fin_{pid}_{row_start}_{idx}",
                            use_container_width=True,
                        ):
                            st.session_state.partido_seleccionado = partido
                            st.rerun()


# ==============================================================================
# VISTA B: DRILL-DOWN DE ANÁLISIS PROFUNDO (SERIES OFENSIVAS + EV + KALMAN)
# ==============================================================================
def render_vista_detalle(partido: Dict[str, Any]) -> None:
    pid = str(partido.get("id_partido", f"{partido['away_abbr']}_{partido['home_abbr']}"))
    sim = obtener_simulacion_partido(partido)
    away = sim["away_abbr"]
    home = sim["home_abbr"]
    logo_away_tv = _render_logo_html(obtener_logo_nfl(away, size=68), away, size=68)
    logo_home_tv = _render_logo_html(obtener_logo_nfl(home, size=68), home, size=68)

    ev_tot = sim["ev_totales"]
    ev_spr = sim["ev_spread"]
    es_final = bool(partido.get("finalizado", False))

    top_col1, top_col2 = st.columns([1.4, 4.6])
    with top_col1:
        if st.button("⬅️ VOLVER A LA CARTELERA", use_container_width=True, type="primary"):
            st.session_state.partido_seleccionado = None
            st.rerun()
    with top_col2:
        st.caption(
            f"Auditoría Cuantitativa por Series Ofensivas · Semana {st.session_state.semana_actual} · "
            f"{partido.get('hora', '')} · Fuente de Momios: {partido.get('fuente_odds', 'ESPN Scoreboard (Decimal)')}"
        )

    spread_justo_label = f"{home} {sim['spread_proyectado']:+.1f}"

    st.markdown(
        f"""
        <div class="tv-scoreboard">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px;">
                <div style="display:flex; align-items:center; gap:16px;">
                    {logo_away_tv}
                    <div>
                        <div style="font-size:0.78rem; color:#94A3B8; text-transform:uppercase;">Visitante · QB {sim["away_qb"]}</div>
                        <div style="font-size:1.45rem; font-weight:800; color:#F8FAFC;">{sim["away_name"]} ({away})</div>
                        <div style="font-family:'JetBrains Mono',monospace; font-size:0.84rem; color:#38BDF8;">
                            Win Prob: {sim["win_away_pct"]:.1f}% · Cuota Justa Decimal: <b>{sim["ml_away_decimal"]:.2f}</b>
                        </div>
                    </div>
                </div>
                <div style="text-align:center; padding:8px 22px; background:rgba(16,185,129,0.10); border:1px solid rgba(16,185,129,0.35); border-radius:12px;">
                    <div style="font-family:'JetBrains Mono',monospace; font-size:0.74rem; color:#94A3B8;">MARCADOR PROYECTADO (5,000 SIMS · {sim["drives_combinados"]} DRIVES)</div>
                    <div style="font-family:'JetBrains Mono',monospace; font-size:2.1rem; font-weight:800; color:#10B981;">
                        {away} {sim["away_pts"]:.1f}  —  {sim["home_pts"]:.1f} {home}
                    </div>
                    <div style="font-family:'JetBrains Mono',monospace; font-size:0.82rem; color:#E2E8F0;">
                        Spread Justo: <b>{spread_justo_label}</b> · Total Justo: <b>{sim["total_ou"]:.1f} pts</b> · HFA: <b>+{sim["hfa_pts"]:.2f} pts</b>
                    </div>
                </div>
                <div style="display:flex; align-items:center; gap:16px;">
                    <div style="text-align:right;">
                        <div style="font-size:0.78rem; color:#94A3B8; text-transform:uppercase;">Local · QB {sim["home_qb"]}</div>
                        <div style="font-size:1.45rem; font-weight:800; color:#F8FAFC;">{sim["home_name"]} ({home})</div>
                        <div style="font-family:'JetBrains Mono',monospace; font-size:0.84rem; color:#38BDF8;">
                            Win Prob: {sim["win_home_pct"]:.1f}% · Cuota Justa Decimal: <b>{sim["ml_home_decimal"]:.2f}</b>
                        </div>
                    </div>
                    {logo_home_tv}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if es_final:
        sim_prev = st.session_state.simulaciones_previas.get(pid, sim)
        aud_det = auditar_partido_nfl(sim_prev, partido)
        st.markdown("#### 📡 Auditoría Post-Partido y Auto-Corrección Dinámica (Filtro de Kalman)")
        ka1, ka2, ka3, ka4 = st.columns(4)
        ka1.metric(
            "Marcador Final Real",
            f"{home} {int(round(aud_det['puntos_home_real']))} - {int(round(aud_det['puntos_away_real']))} {away}",
            delta=f"Total Real: {aud_det['total_real']:.0f} pts",
        )
        ka2.metric(
            "Modelo Previo (Pre-Kalman)",
            f"{home} {aud_det['home_pts_modelo']:.1f} - {aud_det['away_pts_modelo']:.1f} {away}",
            delta=f"Total Modelo: {aud_det['total_modelo']:.1f} pts",
        )
        ka3.metric(
            "Desviación Spread",
            f"{aud_det['error_spread']:+.1f} pts",
            delta=f"Error {away}: {aud_det['error_away']:+.1f} | {home}: {aud_det['error_home']:+.1f}",
        )
        ka4.metric(
            "Desviación Total",
            f"{aud_det['error_total']:+.1f} pts",
            delta=aud_det["origen_desviacion"][:28],
        )

        col_diag, col_act = st.columns([3.0, 1.5])
        with col_diag:
            st.info(
                f"**Diagnóstico de Residuales:** {aud_det['origen_desviacion']} · "
                f"Share Aéreo {away}: **{aud_det['pass_share_away']*100:.1f}%** | "
                f"Share Aéreo {home}: **{aud_det['pass_share_home']*100:.1f}%** · "
                f"Desviación de Ritmo: **{aud_det['error_jugadas']:+.1f} jugadas**."
            )
        with col_act:
            if st.button(
                "⚡ APLICAR CALIBRACIÓN AL MODELO",
                key=f"btn_kalman_detail_{pid}",
                use_container_width=True,
                type="primary",
            ):
                aplicar_calibracion_partido_en_estado(partido)
                st.success(
                    f"Ratings de {away} y {home} actualizados en st.session_state.nfl_stats. "
                    f"Puedes descargar el Excel calibrado desde la barra lateral."
                )
                st.rerun()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f"""
            <div class="kpi-glass">
                <div class="kpi-title">Línea Mercado Total (O/U)</div>
                <div class="kpi-number">{ev_tot["total_mercado"]:.1f} pts</div>
                <div class="kpi-sub">Over {ev_tot["cuota_over_decimal"]:.2f} | Under {ev_tot["cuota_under_decimal"]:.2f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
            <div class="kpi-glass">
                <div class="kpi-title">Línea Mercado Spread ({home})</div>
                <div class="kpi-number">{ev_spr["spread_mercado_home"]:+.1f} pts</div>
                <div class="kpi-sub">{home} {ev_spr["cuota_spread_home_decimal"]:.2f} | {away} {ev_spr["cuota_spread_away_decimal"]:.2f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"""
            <div class="kpi-glass">
                <div class="kpi-title">Probabilidades por Serie (TD / FG)</div>
                <div class="kpi-number">{away} {sim["drive_td_pct_away"]:.1f}% | {home} {sim["drive_td_pct_home"]:.1f}%</div>
                <div class="kpi-sub">FG/Serie: {away} {sim["drive_fg_pct_away"]:.1f}% · {home} {sim["drive_fg_pct_home"]:.1f}%</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f"""
            <div class="kpi-glass">
                <div class="kpi-title">Clima, Ritmo y HFA Dinámico</div>
                <div class="kpi-number">{sim["tipo_estadio"]} · {sim["viento_mph"]:.0f} mph</div>
                <div class="kpi-sub">HFA: +{sim["hfa_pts"]:.2f} pts · Penalización Viento: -{sim["penalizacion_viento_pts"]:.1f} pts</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # En la vista detallada, solo mostramos la tabla de apuestas activas si el partido NO ha finalizado
    if not es_final:
        st.markdown("#### 💹 Auditoría de Valor Esperado (+EV con Shrinkage Bayesiano) y Probabilidad de Push")
        df_ev_audit = pd.DataFrame(
            [
                {
                    "Mercado": f"TOTALES: OVER {ev_tot['total_mercado']:.1f}",
                    "Prob. Modelo (Shrunk %)": f"{ev_tot['prob_over_pct']:.1f}%",
                    "Prob. Push (%)": f"{ev_tot['prob_push_pct']:.1f}%",
                    "Cuota Justa (Fair Decimal)": f"{ev_tot['fair_over_decimal']:.2f}",
                    "Cuota Casa (Decimal)": f"{ev_tot['cuota_over_decimal']:.2f}",
                    "EV Matemático (%)": f"{ev_tot['ev_over_pct']:+.2f}%",
                    "Señal Cuantitativa": "🔥 +EV DETECTADO" if (ev_tot["hay_valor"] and ev_tot["lado"] == "OVER") else "⚖️ Sin Ventaja",
                },
                {
                    "Mercado": f"TOTALES: UNDER {ev_tot['total_mercado']:.1f}",
                    "Prob. Modelo (Shrunk %)": f"{ev_tot['prob_under_pct']:.1f}%",
                    "Prob. Push (%)": f"{ev_tot['prob_push_pct']:.1f}%",
                    "Cuota Justa (Fair Decimal)": f"{ev_tot['fair_under_decimal']:.2f}",
                    "Cuota Casa (Decimal)": f"{ev_tot['cuota_under_decimal']:.2f}",
                    "EV Matemático (%)": f"{ev_tot['ev_under_pct']:+.2f}%",
                    "Señal Cuantitativa": "🔥 +EV DETECTADO" if (ev_tot["hay_valor"] and ev_tot["lado"] == "UNDER") else "⚖️ Sin Ventaja",
                },
                {
                    "Mercado": f"SPREAD: {home} {ev_spr['spread_mercado_home']:+.1f}",
                    "Prob. Modelo (Shrunk %)": f"{ev_spr['prob_cover_home_pct']:.1f}%",
                    "Prob. Push (%)": f"{ev_spr['prob_push_pct']:.1f}%",
                    "Cuota Justa (Fair Decimal)": f"{ev_spr['fair_home_decimal']:.2f}",
                    "Cuota Casa (Decimal)": f"{ev_spr['cuota_spread_home_decimal']:.2f}",
                    "EV Matemático (%)": f"{ev_spr['ev_home_pct']:+.2f}%",
                    "Señal Cuantitativa": "🔥 +EV DETECTADO" if (ev_spr["hay_valor"] and ev_spr["lado"] == "HOME") else "⚖️ Sin Ventaja",
                },
                {
                    "Mercado": f"SPREAD: {away} {ev_spr['spread_mercado_away']:+.1f}",
                    "Prob. Modelo (Shrunk %)": f"{ev_spr['prob_cover_away_pct']:.1f}%",
                    "Prob. Push (%)": f"{ev_spr['prob_push_pct']:.1f}%",
                    "Cuota Justa (Fair Decimal)": f"{ev_spr['fair_away_decimal']:.2f}",
                    "Cuota Casa (Decimal)": f"{ev_spr['cuota_spread_away_decimal']:.2f}",
                    "EV Matemático (%)": f"{ev_spr['ev_away_pct']:+.2f}%",
                    "Señal Cuantitativa": "🔥 +EV DETECTADO" if (ev_spr["hay_valor"] and ev_spr["lado"] == "AWAY") else "⚖️ Sin Ventaja",
                },
            ]
        )
        st.dataframe(df_ev_audit, use_container_width=True, hide_index=True)

    kn = sim["key_numbers_freq"]
    st.markdown(
        f"**🔑 Frecuencia Exacta en Números Clave NFL (|Margen|):** "
        f"`3 pts`: **{kn.get('Margen 3 pts', 0):.1f}%** · "
        f"`7 pts`: **{kn.get('Margen 7 pts', 0):.1f}%** · "
        f"`6 pts`: **{kn.get('Margen 6 pts', 0):.1f}%** · "
        f"`10 pts`: **{kn.get('Margen 10 pts', 0):.1f}%** · "
        f"`4 pts`: **{kn.get('Margen 4 pts', 0):.1f}%** · "
        f"`14 pts`: **{kn.get('Margen 14 pts', 0):.1f}%**"
    )

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("#### ⚔️ Eficiencia por Serie Ofensiva y EPA Matchup")
        away_raw = st.session_state.nfl_stats.get(away, {})
        home_raw = st.session_state.nfl_stats.get(home, {})

        categorias = [
            "EPA Pass Off",
            "EPA Rush Off",
            "EPA Pass Def",
            "EPA Rush Def",
            "Net Pass EPA",
            "EPA Compuesto",
        ]
        vals_away = [
            float(away_raw.get("EPA_Pass_Off", 0.0)),
            float(away_raw.get("EPA_Rush_Off", 0.0)),
            float(away_raw.get("EPA_Pass_Def", 0.0)),
            float(away_raw.get("EPA_Rush_Def", 0.0)),
            float(sim["net_pass_epa_away"]),
            float(sim["epa_comp_away"]),
        ]
        vals_home = [
            float(home_raw.get("EPA_Pass_Off", 0.0)),
            float(home_raw.get("EPA_Rush_Off", 0.0)),
            float(home_raw.get("EPA_Pass_Def", 0.0)),
            float(home_raw.get("EPA_Rush_Def", 0.0)),
            float(sim["net_pass_epa_home"]),
            float(sim["epa_comp_home"]),
        ]

        fig_epa = go.Figure()
        fig_epa.add_trace(
            go.Bar(
                name=f"{away} ({sim['away_qb']})",
                x=categorias,
                y=vals_away,
                marker_color="#38BDF8",
                text=[f"{v:+.3f}" for v in vals_away],
                textposition="outside",
            )
        )
        fig_epa.add_trace(
            go.Bar(
                name=f"{home} ({sim['home_qb']})",
                x=categorias,
                y=vals_home,
                marker_color="#10B981",
                text=[f"{v:+.3f}" for v in vals_home],
                textposition="outside",
            )
        )
        fig_epa.update_layout(
            barmode="group",
            paper_bgcolor="#0D131F",
            plot_bgcolor="#0D131F",
            font=dict(color="#E2E8F0", family="Inter"),
            height=360,
            margin=dict(l=20, r=20, t=30, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(gridcolor="rgba(148,163,184,0.14)", zerolinecolor="rgba(255,255,255,0.25)"),
        )
        st.plotly_chart(fig_epa, use_container_width=True)

    with col_chart2:
        st.markdown("#### 📈 Percentiles de Puntos Totales (Drive-Based vs Mercado)")
        percentiles_labels = [
            "P10 (Juego Cerrado)",
            "Línea Casa (O/U)",
            "Mediana P50",
            "Media Drive-Engine",
            "P90 (Shootout)",
        ]
        percentiles_vals = [
            sim["mc_p10_total"],
            ev_tot["total_mercado"],
            sim["mc_p50_total"],
            sim["total_ou"],
            sim["mc_p90_total"],
        ]
        bar_colors = ["#64748B", "#F59E0B", "#38BDF8", "#10B981", "#A85F73"]

        fig_tot = go.Figure(
            go.Bar(
                x=percentiles_labels,
                y=percentiles_vals,
                marker_color=bar_colors,
                text=[f"{v:.1f} pts" for v in percentiles_vals],
                textposition="outside",
            )
        )
        fig_tot.update_layout(
            paper_bgcolor="#0D131F",
            plot_bgcolor="#0D131F",
            font=dict(color="#E2E8F0", family="Inter"),
            height=360,
            margin=dict(l=20, r=20, t=30, b=20),
            yaxis=dict(
                title="Puntos Combinados",
                gridcolor="rgba(148,163,184,0.14)",
                range=[0, max(percentiles_vals) * 1.22],
            ),
        )
        st.plotly_chart(fig_tot, use_container_width=True)

    st.markdown("#### 🧮 Desglose de Métricas y Resultados por Serie Ofensiva (`st.session_state.nfl_stats`)")
    df_comp = pd.DataFrame(
        [
            {
                "Equipo": f"{away} ({sim['away_name']})",
                "QB Titular": sim["away_qb"],
                "Drives / Juego": sim.get("drives_away", sim["n_drives_equipo"]),
                "Pts / Drive": f"{sim['pts_por_drive_away']:.2f}",
                "P(TD / Drive)": f"{sim['drive_td_pct_away']:.1f}%",
                "P(FG / Drive)": f"{sim['drive_fg_pct_away']:.1f}%",
                "P(Punt-TO / Drive)": f"{sim['drive_punt_pct_away']:.1f}%",
                "EPA_Pass_Off": away_raw.get("EPA_Pass_Off"),
                "EPA_Rush_Off": away_raw.get("EPA_Rush_Off"),
                "EPA_Pass_Def": away_raw.get("EPA_Pass_Def"),
                "EPA_Rush_Def": away_raw.get("EPA_Rush_Def"),
                "Pace_Sec": f"{sim['pace_away']:.1f}s",
                "Puntos Proy.": f"{sim['away_pts']:.1f}",
                "Cuota Justa ML (Decimal)": f"{sim['ml_away_decimal']:.2f}",
            },
            {
                "Equipo": f"{home} ({sim['home_name']})",
                "QB Titular": sim["home_qb"],
                "Drives / Juego": sim.get("drives_home", sim["n_drives_equipo"]),
                "Pts / Drive": f"{sim['pts_por_drive_home']:.2f}",
                "P(TD / Drive)": f"{sim['drive_td_pct_home']:.1f}%",
                "P(FG / Drive)": f"{sim['drive_fg_pct_home']:.1f}%",
                "P(Punt-TO / Drive)": f"{sim['drive_punt_pct_home']:.1f}%",
                "EPA_Pass_Off": home_raw.get("EPA_Pass_Off"),
                "EPA_Rush_Off": home_raw.get("EPA_Rush_Off"),
                "EPA_Pass_Def": home_raw.get("EPA_Pass_Def"),
                "EPA_Rush_Def": home_raw.get("EPA_Rush_Def"),
                "Pace_Sec": f"{sim['pace_home']:.1f}s",
                "Puntos Proy.": f"{sim['home_pts']:.1f}",
                "Cuota Justa ML (Decimal)": f"{sim['ml_home_decimal']:.2f}",
            },
        ]
    )
    st.dataframe(df_comp, use_container_width=True, hide_index=True)


# ==============================================================================
# PUNTO DE ENTRADA PRINCIPAL
# ==============================================================================
def verificar_datos_disponibles() -> None:
    """
    Control de errores: Si no existe el archivo local en el repositorio
    y tampoco se ha subido ningún archivo mediante el uploader, detiene
    la ejecución limpiamente con st.error(...) y st.stop().
    """
    if st.session_state.get("df_nfl") is None or st.session_state.get("nfl_stats") is None:
        st.error(
            f"🚨 Error Crítico de Datos: No se encontró el archivo base '{NOMBRE_ARCHIVO_DEFECTO}' "
            "en la raíz del repositorio y tampoco se ha cargado ningún archivo en la barra lateral. "
            "Por favor, sube un archivo '.xlsx' o '.csv' en 'Actualizar métricas (Opcional)' "
            f"o agrega '{NOMBRE_ARCHIVO_DEFECTO}' a tu repositorio en GitHub."
        )
        st.stop()


def main() -> None:
    inyectar_estilos_css()
    inicializar_session_state()
    render_sidebar()
    verificar_datos_disponibles()

    if st.session_state.partido_seleccionado is None:
        render_vista_cartelera()
    else:
        render_vista_detalle(st.session_state.partido_seleccionado)


if __name__ == "__main__":
    main()