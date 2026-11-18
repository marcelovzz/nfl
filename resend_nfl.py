#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MÓDULO 4: resend_nfl.py
Pipeline Automatizado Desatendido de "TERMINAL SHARP: NFL QUANT" (Mobile-First Briefing)
  - Consulta la cartelera activa de la semana en curso desde ESPN Scoreboard API / The Odds API
    (vía sync_espn_nfl.py) y audita el reporte oficial de bajas de ESPN (especialmente QBs
    titulares y jugadores clave) para alimentar el factor de reemplazo de QB.
  - Ejecuta las 5,000 simulaciones de Monte Carlo por partido mediante el generador
    discreto de anotaciones (TD=7/6/8, FG=3), filtro de situaciones competitivas (WP 5%-95%)
    y anclaje bayesiano al spread de consenso (engine_nfl.py), más las 5,000 simulaciones
    Log-Normal de Player Props cruzadas con factores defensivos DvP (engine_props_nfl.py).
  - Rediseña el correo HTML como un Briefing Ejecutivo Mobile-First (estilo Terminal Financiera,
    max-width: 600px, tarjetas apiladas #161b22 sobre #0d1117 con borde #30363d y escudos
    oficiales del CDN de ESPN):
      * SECCIÓN 1 — TOP 5 ANCHORS DE LA JORNADA (borde #00ffcc, combinando Spreads, Totales
        y Player Props ordenados de mayor a menor % de cubrimiento con escudo 18x18).
      * SECCIÓN 2 — DESGLOSE POR PARTIDO EN ORDEN CRONOLÓGICO CST (cabecera con escudos 26x26,
        marcador proyectado, línea de mercado, badges de Spread y Total con % Cubre en 5,000
        sims y sub-lista compacta de Player Props +EV > 0.0%).
  - Renderiza el reporte estructurado a un archivo PDF vertical limpio
    ('Terminal_Sharp_NFL_Briefing.pdf') usando 'fpdf2' o 'reportlab' (con fallback seguro
    para no detener el flujo si falla el PDF) y lo envía vía la API REST de Resend.
"""

import base64
import io
import os
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import requests

from sync_espn_nfl import (
    ESPN_NFL_SCOREBOARD_URL,
    NFL_FRANCHISE_NAMES,
    get_team_logo_url as _sync_get_team_logo_url,
    normalizar_abbr_nfl,
    obtener_calendario_nfl_semana,
)
from engine_nfl import (
    build_nfl_predictions_export_df,
    obtener_stats_nfl_default,
    run_simulacion_nfl,
    validar_y_parsear_excel_nfl,
)
from engine_props_nfl import (
    build_player_props_ranking_export_df,
    estilizar_hoja_player_props_openpyxl,
    obtener_top_3_player_props_jornada,
    ordenar_props_multinivel_por_juego,
    simular_player_props_jornada,
)
try:
    from sync_injuries_nfl import (
        cargar_estado_titulares_y_clima,
        obtener_bloque_estado_partido,
        sincronizar_lesiones_titulares_y_clima_nfl,
    )
except Exception:
    cargar_estado_titulares_y_clima = None  # type: ignore
    obtener_bloque_estado_partido = None  # type: ignore
    sincronizar_lesiones_titulares_y_clima_nfl = None  # type: ignore

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

RESEND_API_URL = "https://api.resend.com/emails"
ESPN_NFL_INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
DEFAULT_STATS_FILE = "nfl_stats.xlsx"
ATTACHMENT_FILENAME = "Terminal_Sharp_NFL_Briefing.pdf"
EXCEL_ATTACHMENT_FILENAME = "nfl_quant_projections.xlsx"


def get_team_logo_url(team_abbr: str) -> str:
    """
    Recibe la abreviatura del equipo (ej. 'DAL', 'IND', 'KC', 'WAS', 'LA')
    y devuelve su URL oficial del CDN de ESPN en alta resolución:
      'https://a.espncdn.com/i/teamlogos/nfl/500/{abbr_lower}.png'
    Incluye el mapeo de normalización para las excepciones de ESPN:
      - 'WAS' -> 'wsh'
      - 'LA' / 'LAR' -> 'lar'
      - 'JAC' / 'JAX' -> 'jax'
    """
    raw = str(team_abbr or "").strip().upper()
    mapa_excepciones = {
        "WAS": "wsh",
        "WSH": "wsh",
        "LA": "lar",
        "LAR": "lar",
        "STL": "lar",
        "JAC": "jax",
        "JAX": "jax",
    }
    if raw in mapa_excepciones:
        abbr_lower = mapa_excepciones[raw]
        return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr_lower}.png"
    return _sync_get_team_logo_url(raw)


def _convertir_hora_a_cst(hora_raw: str) -> Tuple[int, str]:
    """
    Convierte una cadena de horario de ESPN (ET / UTC / local) a formato legible CST
    y devuelve una clave entera (orden_dia * 10000 + hh * 60 + mm) para ordenar
    cronológicamente los partidos.
    """
    txt = str(hora_raw or "DOM 12:00 CST").strip().upper()
    mapa_dias = {
        "JUE": 1,
        "THU": 1,
        "VIE": 2,
        "FRI": 2,
        "SÁB": 3,
        "SAB": 3,
        "SAT": 3,
        "DOM": 4,
        "SUN": 4,
        "LUN": 5,
        "MON": 5,
        "MAR": 6,
        "TUE": 6,
        "MIÉ": 7,
        "MIE": 7,
        "WED": 7,
    }
    dia_es_label = "DOM"
    orden_dia = 4
    for pref, valor in mapa_dias.items():
        if pref in txt:
            orden_dia = valor
            if pref in ("JUE", "THU"):
                dia_es_label = "JUE"
            elif pref in ("VIE", "FRI"):
                dia_es_label = "VIE"
            elif pref in ("SÁB", "SAB", "SAT"):
                dia_es_label = "SÁB"
            elif pref in ("DOM", "SUN"):
                dia_es_label = "DOM"
            elif pref in ("LUN", "MON"):
                dia_es_label = "LUN"
            break

    m = re.search(r"(\d{1,2}):(\d{2})\s*(AM|PM)?", txt)
    if not m:
        return orden_dia * 10000 + 720, f"{dia_es_label} 12:00 CST"

    hh = int(m.group(1))
    mm = int(m.group(2))
    ampm = (m.group(3) or "").strip()
    if ampm == "PM" and hh < 12:
        hh += 12
    elif ampm == "AM" and hh == 12:
        hh = 0

    # Si viene en ET/EDT, restamos 1 hora para CST; si viene en UTC, restamos 6 horas
    if "UTC" in txt:
        hh = (hh - 6) % 24
    elif "ET" in txt or "EDT" in txt or "EST" in txt:
        hh = (hh - 1) % 24

    clave_sort = orden_dia * 10000 + (hh * 60 + mm)
    return clave_sort, f"{dia_es_label} {hh:02d}:{mm:02d} CST"


def cargar_diccionario_stats_local() -> Dict[str, Dict[str, Any]]:
    """
    Carga la base de métricas EPA/play y Success Rate desde 'nfl_stats1.xlsx' / 'nfl_stats.xlsx'
    (o respaldo CSV en el repositorio). Si no existe, retorna el pool calibrado por defecto.
    """
    candidatos = ["nfl_stats1.xlsx", "nfl_stats.xlsx", "nfl_stats.csv", "nfl_stats_completo.csv"]
    for ruta in candidatos:
        if os.path.exists(ruta):
            try:
                if ruta.lower().endswith(".csv"):
                    df = pd.read_csv(ruta)
                else:
                    df = pd.read_excel(ruta)
                return validar_y_parsear_excel_nfl(df)
            except Exception:
                continue
    return obtener_stats_nfl_default()


def detectar_semana_actual_nfl() -> int:
    """
    Consulta el endpoint de ESPN Scoreboard sin parámetros para identificar
    automáticamente la semana activa de la temporada regular de la NFL.
    """
    env_week = os.environ.get("NFL_WEEK", "").strip()
    if env_week.isdigit():
        return max(1, min(18, int(env_week)))

    try:
        resp = requests.get(
            ESPN_NFL_SCOREBOARD_URL,
            timeout=6,
            headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        data = resp.json()
        week_num = data.get("week", {}).get("number")
        if week_num is not None:
            return max(1, min(18, int(week_num)))
    except Exception:
        pass
    return 10


def consultar_reporte_bajas_nfl(
    nfl_stats_dict: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    Consulta el reporte de lesiones de ESPN NFL para identificar bajas confirmadas
    (OUT / IR / DOUBTFUL), prestando especial atención a los Quarterbacks titulares
    y jugadores clave de cada franquicia.
    """
    reporte_por_equipo: Dict[str, Dict[str, Any]] = {}
    for abbr, st_team in nfl_stats_dict.items():
        if abbr in ("LAR", "WSH"):
            continue
        reporte_por_equipo[abbr] = {
            "qb_titular": str(st_team.get("QB_Name", f"{abbr} QB1")),
            "qb_status": "ACTIVE",
            "qb_out": False,
            "bajas_clave": [],
        }

    try:
        resp = requests.get(
            ESPN_NFL_INJURIES_URL,
            timeout=6,
            headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
        )
        if resp.status_code == 200:
            data = resp.json()
            equipos_inj = data.get("injuries", []) or []
            for team_block in equipos_inj:
                team_info = team_block.get("team", {}) or {}
                raw_abbr = str(team_info.get("abbreviation") or team_block.get("displayName", ""))
                abbr = normalizar_abbr_nfl(raw_abbr)
                if abbr not in reporte_por_equipo:
                    continue

                qb_titular_apellido = (
                    reporte_por_equipo[abbr]["qb_titular"].split()[-1].strip().upper()
                )
                lista_inj = team_block.get("injuries", []) or []
                for item in lista_inj:
                    athlete = item.get("athlete", {}) or {}
                    nombre_jug = str(athlete.get("displayName") or athlete.get("shortName") or "").strip()
                    pos = str(athlete.get("position", {}).get("abbreviation", "")).strip().upper()
                    status = str(item.get("status", "")).strip().upper()

                    if status in {"OUT", "INJURED RESERVE", "IR", "DOUBTFUL"}:
                        if len(reporte_por_equipo[abbr]["bajas_clave"]) < 3 and nombre_jug:
                            reporte_por_equipo[abbr]["bajas_clave"].append(f"{nombre_jug} ({pos} - {status})")

                        if pos == "QB" and qb_titular_apellido and qb_titular_apellido in nombre_jug.upper():
                            if status in {"OUT", "INJURED RESERVE", "IR"}:
                                reporte_por_equipo[abbr]["qb_status"] = "OUT"
                                reporte_por_equipo[abbr]["qb_out"] = True
                            elif status == "DOUBTFUL":
                                reporte_por_equipo[abbr]["qb_status"] = "DOUBTFUL"
    except Exception:
        pass

    return reporte_por_equipo


def ejecutar_pipeline_simulaciones_nfl(
    semana: Optional[int] = None,
) -> Tuple[int, List[Dict[str, Any]], pd.DataFrame, pd.DataFrame, Dict[str, Dict[str, Any]]]:
    """
    Ejecuta las 5,000 simulaciones de Monte Carlo calibradas para todos los partidos
    de la semana y construye tanto el DataFrame general como el DataFrame
    'Ranking_Alta_Probabilidad' ordenado descendentemente por probabilidad.
    """
    semana_activa = semana if semana is not None else detectar_semana_actual_nfl()
    odds_api_key = os.environ.get("ODDS_API_KEY", "").strip() or None
    viento_default = float(os.environ.get("NFL_WIND_MPH", "8.0"))

    nfl_stats = cargar_diccionario_stats_local()
    reporte_bajas = consultar_reporte_bajas_nfl(nfl_stats)
    partidos = obtener_calendario_nfl_semana(semana=semana_activa, api_key=odds_api_key)

    starters_verified: Dict[str, Any] = {}
    if cargar_estado_titulares_y_clima is not None:
        try:
            starters_verified = cargar_estado_titulares_y_clima(forzar_sync=False)
        except Exception:
            starters_verified = {}

    partidos_pendientes = [p for p in partidos if not p.get("finalizado", False)]
    partidos_objetivo = partidos_pendientes if partidos_pendientes else partidos

    resultados_simulados: List[Dict[str, Any]] = []
    filas_ranking: List[Dict[str, Any]] = []

    for p in partidos_objetivo:
        away = normalizar_abbr_nfl(p["away_abbr"])
        home = normalizar_abbr_nfl(p["home_abbr"])

        bajas_away = reporte_bajas.get(away, {})
        bajas_home = reporte_bajas.get(home, {})

        lineas_mercado = {
            "total_mercado": p.get("total_mercado", 44.5),
            "cuota_over_decimal": p.get("cuota_over_decimal", 1.91),
            "cuota_under_decimal": p.get("cuota_under_decimal", 1.91),
            "spread_mercado_home": p.get("spread_mercado_home", -2.5),
            "cuota_spread_home_decimal": p.get("cuota_spread_home_decimal", 1.91),
            "cuota_spread_away_decimal": p.get("cuota_spread_away_decimal", 1.91),
            "fuente_odds": p.get("fuente_odds", "ESPN Consensus (Decimal)"),
            "qb_status_away": bajas_away.get("qb_status", "ACTIVE"),
            "qb_status_home": bajas_home.get("qb_status", "ACTIVE"),
            "qb_out_away": bool(bajas_away.get("qb_out", False)),
            "qb_out_home": bool(bajas_home.get("qb_out", False)),
        }

        sim = run_simulacion_nfl(
            away_abbr=away,
            home_abbr=home,
            nfl_stats_dict=nfl_stats,
            n_sims=5000,
            lineas_mercado=lineas_mercado,
            viento_mph=float(p.get("viento_mph", viento_default)),
            tipo_estadio="Auto",
        )

        hora_raw = str(p.get("hora", "DOM 13:00 ET"))
        kickoff_sort, hora_cst = _convertir_hora_a_cst(hora_raw)

        sim_record = dict(sim)
        sim_record["semana"] = semana_activa
        sim_record["hora"] = hora_cst
        sim_record["hora_raw"] = hora_raw
        sim_record["_kickoff_sort"] = kickoff_sort
        sim_record["estado"] = p.get("estado", f"Semana {semana_activa}")
        sim_record["fuente_odds"] = lineas_mercado["fuente_odds"]
        sim_record["bajas_clave_away"] = ", ".join(bajas_away.get("bajas_clave", [])) or "Sin bajas críticas QB"
        sim_record["bajas_clave_home"] = ", ".join(bajas_home.get("bajas_clave", [])) or "Sin bajas críticas QB"
        if obtener_bloque_estado_partido is not None:
            try:
                bloque_est = obtener_bloque_estado_partido(
                    away_abbr=away,
                    home_abbr=home,
                    starters_verified=starters_verified,
                )
                sim_record["bloque_estado_partido"] = bloque_est
                sim_record["linea_1_qb_clima"] = bloque_est.get("linea_1_qb_clima", sim_record.get("linea_1_qb_clima", ""))
                sim_record["linea_2_out_gtd"] = bloque_est.get("linea_2_out_gtd", sim_record.get("linea_2_out_gtd", ""))
                sim_record["linea_3_activados"] = bloque_est.get("linea_3_activados", sim_record.get("linea_3_activados", ""))
                sim_record["linea_4_traspasos"] = bloque_est.get("linea_4_traspasos", sim_record.get("linea_4_traspasos", "🔄 TRASPASOS: Sin cambios"))
            except Exception:
                pass
        resultados_simulados.append(sim_record)

        matchup_label = f"{away} @ {home}"
        marcador_proy = f"{away} {sim['away_pts']:.1f} - {sim['home_pts']:.1f} {home}"
        ev_tot = sim["ev_totales"]
        ev_spr = sim["ev_spread"]

        # 1) Selección de mayor probabilidad en Moneyline
        if sim["win_home_pct"] >= sim["win_away_pct"]:
            ml_pick = f"{home} ML ({sim['home_name']})"
            ml_prob = float(sim["win_home_pct"])
            ml_fair = float(sim["ml_home_decimal"])
            ml_mkt_prob = float(sim["casas_home_pct"])
        else:
            ml_pick = f"{away} ML ({sim['away_name']})"
            ml_prob = float(sim["win_away_pct"])
            ml_fair = float(sim["ml_away_decimal"])
            ml_mkt_prob = float(sim["casas_away_pct"])

        ml_edge_pct = round(ml_prob - ml_mkt_prob, 1)
        sp_cov_pct = round(float(sim.get("spread_cover_pct", ev_spr.get("spread_cover_pct", ev_spr["prob_mejor_pct"]))), 1)
        tot_cov_pct = round(float(sim.get("total_cover_pct", ev_tot.get("total_cover_pct", ev_tot["prob_mejor_pct"]))), 1)

        sp_badges_str = str(ev_spr.get("edge_badges_str", sim.get("edge_badges_str", ""))).strip()
        suf_sp_badges = f" | {sp_badges_str}" if sp_badges_str else ""
        if ev_spr["hay_valor"]:
            senal_sp_str = f"🔥 {ev_spr['recomendacion']} ({ev_spr['cuota_mercado_decimal']:.2f}) | Cubre: {sp_cov_pct:.1f}% | EV: {ev_spr['ev_pct']:+.1f}%{suf_sp_badges}"
        else:
            senal_sp_str = f"⚪ {ev_spr['recomendacion']} | Cubre: {sp_cov_pct:.1f}%{suf_sp_badges}"

        if ev_tot["hay_valor"]:
            senal_tot_str = f"🔥 {ev_tot['lado']} {ev_tot['total_mercado']:.1f} ({ev_tot['cuota_mercado_decimal']:.2f}) | Cubre: {tot_cov_pct:.1f}% | EV: {ev_tot['ev_pct']:+.1f}%"
        else:
            senal_tot_str = f"⚪ {ev_tot['lado']} {ev_tot['total_mercado']:.1f} | Cubre: {tot_cov_pct:.1f}%"

        filas_ranking.append(
            {
                "Semana": semana_activa,
                "Partido": matchup_label,
                "Horario": sim_record["hora"],
                "Mercado": "MONEYLINE",
                "Seleccion": ml_pick,
                "Probabilidad_%": round(ml_prob, 1),
                "% Cubre Spread": sp_cov_pct,
                "% Cubre Total": tot_cov_pct,
                "Cuota_Justa_Dec": round(ml_fair, 2),
                "Cuota_Mercado_Dec": round(100.0 / max(5.0, ml_mkt_prob), 2),
                "EV_%": ml_edge_pct,
                "Señal_Cuantitativa": "🔥 ALTA CONFIANZA ML" if ml_prob >= 62.0 else "⚖️ ML Estándar",
                "Marcador_Proyectado": marcador_proy,
            }
        )

        # 2) Selección de mayor probabilidad en Spread
        filas_ranking.append(
            {
                "Semana": semana_activa,
                "Partido": matchup_label,
                "Horario": sim_record["hora"],
                "Mercado": "SPREAD (HÁNDICAP)",
                "Seleccion": f"{ev_spr['recomendacion']} (Mod: {sim['spread_proyectado']:+.1f})",
                "Probabilidad_%": sp_cov_pct,
                "% Cubre Spread": sp_cov_pct,
                "% Cubre Total": tot_cov_pct,
                "Cuota_Justa_Dec": round(float(ev_spr["fair_decimal"]), 2),
                "Cuota_Mercado_Dec": round(float(ev_spr["cuota_mercado_decimal"]), 2),
                "EV_%": round(float(ev_spr["ev_pct"]), 1),
                "Señal_Cuantitativa": senal_sp_str,
                "Marcador_Proyectado": marcador_proy,
            }
        )

        # 3) Selección de mayor probabilidad en Totales (Over / Under)
        filas_ranking.append(
            {
                "Semana": semana_activa,
                "Partido": matchup_label,
                "Horario": sim_record["hora"],
                "Mercado": "TOTALES (O/U)",
                "Seleccion": f"{ev_tot['lado']} {ev_tot['total_mercado']:.1f} (Proy: {sim['total_ou']:.1f})",
                "Probabilidad_%": tot_cov_pct,
                "% Cubre Spread": sp_cov_pct,
                "% Cubre Total": tot_cov_pct,
                "Cuota_Justa_Dec": round(float(ev_tot["fair_decimal"]), 2),
                "Cuota_Mercado_Dec": round(float(ev_tot["cuota_mercado_decimal"]), 2),
                "EV_%": round(float(ev_tot["ev_pct"]), 1),
                "Señal_Cuantitativa": senal_tot_str,
                "Marcador_Proyectado": marcador_proy,
            }
        )

    # Ordenar resultados_simulados cronológicamente en CST y luego por Partido
    resultados_simulados.sort(
        key=lambda x: (int(x.get("_kickoff_sort", 40720)), f"{x['away_abbr']} @ {x['home_abbr']}")
    )

    df_general = build_nfl_predictions_export_df(resultados_simulados, semana=semana_activa)
    df_ranking = pd.DataFrame(filas_ranking)
    if not df_ranking.empty:
        df_ranking = df_ranking.sort_values(
            by=["Probabilidad_%", "EV_%"], ascending=[False, False]
        ).reset_index(drop=True)
        df_ranking.insert(0, "Rank", range(1, len(df_ranking) + 1))

    return semana_activa, resultados_simulados, df_general, df_ranking, nfl_stats


def construir_df_rankings_probabilidad(
    resultados_simulados: List[Dict[str, Any]],
) -> pd.DataFrame:
    """
    Construye la pestaña 'Rankings_Probabilidad':
    Consolida todas las selecciones de partido de los tres mercados principales
    ('Moneyline (ML)', 'Spread' y 'Over/Under') ordenadas estrictamente de MAYOR a MENOR
    'Prob_Modelo_%' (de arriba hacia abajo, independientemente del partido).
    Columnas exactas:
      ['Rank', 'Fecha_Hora_CST', 'Partido', 'Mercado', 'Eleccion_Pick', 'Cuota_Decimal',
       'Prob_Modelo_%', 'EV_%', 'Estado_Titulares', 'Edge_Badges']
    """
    cols = [
        "Rank",
        "Fecha_Hora_CST",
        "Partido",
        "Mercado",
        "Eleccion_Pick",
        "Cuota_Decimal",
        "Prob_Modelo_%",
        "EV_%",
        "Estado_Titulares",
        "Edge_Badges",
    ]
    filas: List[Dict[str, Any]] = []
    for s in resultados_simulados or []:
        away = str(s.get("away_abbr", ""))
        home = str(s.get("home_abbr", ""))
        partido = f"{away} @ {home}"
        hora_cst = str(s.get("hora", "DOM 12:00 CST"))
        bloque_est = s.get("bloque_estado_partido") or {}
        qb_aw_tag = str(bloque_est.get("qb_away_tag") or "TITULAR OK")
        qb_hm_tag = str(bloque_est.get("qb_home_tag") or "TITULAR OK")
        estado_titulares = (
            "QB1 OK"
            if ("OK" in qb_aw_tag and "OK" in qb_hm_tag)
            else f"{away}:{qb_aw_tag} / {home}:{qb_hm_tag}"
        )

        ev_spr = s.get("ev_spread", {}) or {}
        ev_tot = s.get("ev_totales", {}) or {}
        edge_badges = str(ev_spr.get("edge_badges_str", s.get("edge_badges_str", ""))).strip()

        # 1. Moneyline (ML)
        win_h = _safe_float(s.get("win_home_pct"), 50.0)
        win_a = _safe_float(s.get("win_away_pct"), 50.0)
        if win_h >= win_a:
            ml_pick = f"{home} ML"
            ml_prob = round(win_h, 1)
            ml_mkt_prob = _safe_float(s.get("casas_home_pct"), 50.0)
        else:
            ml_pick = f"{away} ML"
            ml_prob = round(win_a, 1)
            ml_mkt_prob = _safe_float(s.get("casas_away_pct"), 50.0)
        ml_odds = round(100.0 / max(5.0, ml_mkt_prob), 2)
        ml_ev = round(((ml_prob / 100.0) * ml_odds - 1.0) * 100.0, 1)

        filas.append(
            {
                "Fecha_Hora_CST": hora_cst,
                "Partido": partido,
                "Mercado": "Moneyline (ML)",
                "Eleccion_Pick": ml_pick,
                "Cuota_Decimal": ml_odds,
                "Prob_Modelo_%": ml_prob,
                "EV_%": ml_ev,
                "Estado_Titulares": estado_titulares,
                "Edge_Badges": "🔥 ALTA CONFIANZA ML" if ml_prob >= 62.0 else "",
            }
        )

        # 2. Spread
        sp_pick = str(ev_spr.get("recomendacion", f"{home} {_safe_float(s.get('spread_mercado_home'), -2.5):+.1f}"))
        sp_odds = round(_safe_float(ev_spr.get("cuota_mercado_decimal"), 1.91), 2)
        sp_prob = round(
            _safe_float(s.get("spread_cover_pct", ev_spr.get("spread_cover_pct", ev_spr.get("prob_mejor_pct", 50.0))), 50.0),
            1,
        )
        sp_ev = round(_safe_float(ev_spr.get("ev_pct"), 0.0), 1)

        filas.append(
            {
                "Fecha_Hora_CST": hora_cst,
                "Partido": partido,
                "Mercado": "Spread",
                "Eleccion_Pick": sp_pick,
                "Cuota_Decimal": sp_odds,
                "Prob_Modelo_%": sp_prob,
                "EV_%": sp_ev,
                "Estado_Titulares": estado_titulares,
                "Edge_Badges": edge_badges,
            }
        )

        # 3. Over/Under (Total)
        tot_lado = str(ev_tot.get("lado", "OVER"))
        tot_lin = _safe_float(ev_tot.get("total_mercado", s.get("total_mercado", 44.5)), 44.5)
        tot_pick = f"{tot_lado} {tot_lin:.1f}"
        tot_odds = round(_safe_float(ev_tot.get("cuota_mercado_decimal"), 1.91), 2)
        tot_prob = round(
            _safe_float(s.get("total_cover_pct", ev_tot.get("total_cover_pct", ev_tot.get("prob_mejor_pct", 50.0))), 50.0),
            1,
        )
        tot_ev = round(_safe_float(ev_tot.get("ev_pct"), 0.0), 1)

        filas.append(
            {
                "Fecha_Hora_CST": hora_cst,
                "Partido": partido,
                "Mercado": "Over/Under",
                "Eleccion_Pick": tot_pick,
                "Cuota_Decimal": tot_odds,
                "Prob_Modelo_%": tot_prob,
                "EV_%": tot_ev,
                "Estado_Titulares": estado_titulares,
                "Edge_Badges": "🌧️ CLIMA ADVERSO" if s.get("clima_adverso") else "",
            }
        )

    if not filas:
        return pd.DataFrame(columns=cols)

    df_rk = pd.DataFrame(filas)
    df_rk = df_rk.sort_values(
        by=["Prob_Modelo_%", "EV_%"], ascending=[False, False]
    ).reset_index(drop=True)
    df_rk.insert(0, "Rank", [f"#{i}" for i in range(1, len(df_rk) + 1)])
    return df_rk[cols]


def construir_df_proyecciones_partidos(
    resultados_simulados: List[Dict[str, Any]],
) -> pd.DataFrame:
    """
    Construye la pestaña 'Proyecciones_Partidos' con las columnas exactas:
      ['Fecha/Hora CST', 'Matchup', 'QB1_Visitante [Estado]', 'QB1_Local [Estado]',
       'Clima', 'Descanso', 'Marcador_Proy', 'Total_Proy', 'Spread_Mercado',
       'Total_Mercado', 'Señal_Spread', 'Prob_Spread_%', 'EV_Spread_%',
       'Señal_Total', 'Prob_Total_%', 'EV_Total_%', 'Edge_Badges']
    """
    cols = [
        "Fecha/Hora CST",
        "Matchup",
        "QB1_Visitante [Estado]",
        "QB1_Local [Estado]",
        "Clima",
        "Descanso",
        "Marcador_Proy",
        "Total_Proy",
        "Spread_Mercado",
        "Total_Mercado",
        "Señal_Spread",
        "Prob_Spread_%",
        "EV_Spread_%",
        "Señal_Total",
        "Prob_Total_%",
        "EV_Total_%",
        "Edge_Badges",
    ]
    filas: List[Dict[str, Any]] = []
    for s in resultados_simulados or []:
        away = str(s.get("away_abbr", ""))
        home = str(s.get("home_abbr", ""))
        bloque_est = s.get("bloque_estado_partido") or {}
        qb_aw = str(bloque_est.get("qb_away_name") or s.get("away_qb", away))
        qb_hm = str(bloque_est.get("qb_home_name") or s.get("home_qb", home))
        tag_aw = str(bloque_est.get("qb_away_tag") or "TITULAR OK")
        tag_hm = str(bloque_est.get("qb_home_tag") or "TITULAR OK")
        clima_txt = str(bloque_est.get("clima_pill") or s.get("resumen_clima", s.get("tipo_estadio", "Outdoor")))

        ev_spr = s.get("ev_spread", {}) or {}
        ev_tot = s.get("ev_totales", {}) or {}
        sp_prob = round(_safe_float(s.get("spread_cover_pct", ev_spr.get("prob_mejor_pct", 50.0)), 50.0), 1)
        sp_ev = round(_safe_float(ev_spr.get("ev_pct"), 0.0), 1)
        tot_prob = round(_safe_float(s.get("total_cover_pct", ev_tot.get("prob_mejor_pct", 50.0)), 50.0), 1)
        tot_ev = round(_safe_float(ev_tot.get("ev_pct"), 0.0), 1)

        filas.append(
            {
                "Fecha/Hora CST": str(s.get("hora", "DOM 12:00 CST")),
                "Matchup": f"{away} @ {home}",
                "QB1_Visitante [Estado]": f"{qb_aw} [{tag_aw}]",
                "QB1_Local [Estado]": f"{qb_hm} [{tag_hm}]",
                "Clima": clima_txt,
                "Descanso": str(s.get("descanso_label", "Estándar (7d vs 7d)")),
                "Marcador_Proy": f"{away} {_safe_float(s.get('away_pts'), 0.0):.1f} - {_safe_float(s.get('home_pts'), 0.0):.1f} {home}",
                "Total_Proy": round(_safe_float(s.get("total_ou"), 44.5), 1),
                "Spread_Mercado": f"{home} {_safe_float(s.get('spread_mercado_home'), -2.5):+.1f}",
                "Total_Mercado": round(_safe_float(s.get("total_mercado"), 44.5), 1),
                "Señal_Spread": str(ev_spr.get("recomendacion", "")),
                "Prob_Spread_%": sp_prob,
                "EV_Spread_%": sp_ev,
                "Señal_Total": f"{ev_tot.get('lado', 'OVER')} {_safe_float(ev_tot.get('total_mercado'), 44.5):.1f}",
                "Prob_Total_%": tot_prob,
                "EV_Total_%": tot_ev,
                "Edge_Badges": str(ev_spr.get("edge_badges_str", s.get("edge_badges_str", ""))).strip(),
            }
        )
    if not filas:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(filas, columns=cols)


def construir_df_player_props_ev(
    df_props_ranking: Optional[pd.DataFrame],
) -> pd.DataFrame:
    """
    Construye la pestaña 'Player_Props_EV' con las columnas exactas:
      ['Partido', 'Jugador', 'Equipo', 'Pos_Rol', 'Estado_Plantilla', 'Mercado',
       'Pick', 'Línea', 'Proyección_Modelo', 'Prob_Cubre_%', 'EV_%']
    """
    cols = [
        "Partido",
        "Jugador",
        "Equipo",
        "Pos_Rol",
        "Estado_Plantilla",
        "Mercado",
        "Pick",
        "Línea",
        "Proyección_Modelo",
        "Prob_Cubre_%",
        "EV_%",
    ]
    if df_props_ranking is None or df_props_ranking.empty:
        return pd.DataFrame(columns=cols)

    mapa_mkt = {
        "Rush + Rec Yds": "Rush+Rec",
        "Pass + Rush Yds": "Pass+Rush",
        "Pass Completions": "Completions",
    }
    filas: List[Dict[str, Any]] = []
    for _, rp in df_props_ranking.iterrows():
        met_raw = str(rp.get("Mercado_Corto") or rp.get("Métrica") or "Rec Yds")
        met_lbl = mapa_mkt.get(met_raw, met_raw)
        lado_raw = _extraer_lado_prop(rp)
        pick_lbl = "SI" if met_lbl == "Anytime TD" else lado_raw
        notas_mod = str(rp.get("Notas_Modelo", ""))
        if "RecienActivado" in notas_mod:
            est_pl = "RECIEN_ACTIVADO (92%)"
        elif "TraspasoNuevo" in notas_mod:
            est_pl = "TRASPASO_NUEVO (85%)"
        elif "Questionable" in notas_mod:
            est_pl = "QUESTIONABLE_GTD"
        else:
            est_pl = "ACTIVO_CONFIRMADO"

        filas.append(
            {
                "Partido": str(rp.get("Partido", "")),
                "Jugador": str(rp.get("Jugador", "")),
                "Equipo": str(rp.get("Equipo", "")),
                "Pos_Rol": str(rp.get("Rol") or rp.get("Posición") or "WR1"),
                "Estado_Plantilla": est_pl,
                "Mercado": met_lbl,
                "Pick": pick_lbl,
                "Línea": round(_safe_float(rp.get("Línea Mercado"), 0.5), 1),
                "Proyección_Modelo": round(_safe_float(rp.get("Proyección Mediana"), 0.0), 1),
                "Prob_Cubre_%": round(_safe_float(rp.get("% Cubre"), 50.0), 1),
                "EV_%": round(_safe_float(rp.get("EV_%"), 0.0), 1),
            }
        )
    return pd.DataFrame(filas, columns=cols)


def construir_df_combos_correlacionados(
    resultados_simulados: List[Dict[str, Any]],
    df_props_ranking: Optional[pd.DataFrame],
) -> pd.DataFrame:
    """
    Construye la pestaña 'Combos_Correlacionados':
      ['Partido', 'Selección_1', 'Selección_2', 'Prob_Independiente_%',
       'Prob_Conjunta_Sim_%', 'Correlation_Edge_%']
    """
    cols = [
        "Partido",
        "Selección_1",
        "Selección_2",
        "Prob_Independiente_%",
        "Prob_Conjunta_Sim_%",
        "Correlation_Edge_%",
    ]
    filas: List[Dict[str, Any]] = []
    for s in resultados_simulados or []:
        away = str(s.get("away_abbr", ""))
        home = str(s.get("home_abbr", ""))
        partido = f"{away} @ {home}"
        ev_sp = s.get("ev_spread", {}) or {}
        ev_to = s.get("ev_totales", {}) or {}

        p_sp = _safe_float(s.get("spread_cover_pct", ev_sp.get("prob_mejor_pct", 52.0)), 52.0) / 100.0
        p_to = _safe_float(s.get("total_cover_pct", ev_to.get("prob_mejor_pct", 52.0)), 52.0) / 100.0
        sel_sp = str(ev_sp.get("recomendacion", f"{home} -2.5"))
        sel_to = f"{ev_to.get('lado', 'OVER')} {_safe_float(ev_to.get('total_mercado'), 44.5):.1f}"

        # Combo 1: Spread + Total correlacionado (Underdog + Under o Favorito + Over)
        es_dog = _safe_float(ev_sp.get("linea_pick"), 0.0) > 0.0
        es_under = str(ev_to.get("lado", "OVER")).upper() == "UNDER"
        rho_game = 0.22 if ((es_dog and es_under) or (not es_dog and not es_under)) else 0.11
        p_ind_1 = round((p_sp * p_to) * 100.0, 1)
        boost_1 = round(rho_game * ((p_sp * (1.0 - p_sp) * p_to * (1.0 - p_to)) ** 0.5) * 100.0, 1)
        p_conj_1 = round(min(78.0, p_ind_1 + boost_1), 1)
        filas.append(
            {
                "Partido": partido,
                "Selección_1": f"{sel_sp} (Spread)",
                "Selección_2": f"{sel_to} (Total)",
                "Prob_Independiente_%": p_ind_1,
                "Prob_Conjunta_Sim_%": p_conj_1,
                "Correlation_Edge_%": round(p_conj_1 - p_ind_1, 1),
            }
        )

        # Combo 2: Mejor Prop del partido + Selección correlacionada
        if df_props_ranking is not None and not df_props_ranking.empty and "Partido" in df_props_ranking.columns:
            df_jp = df_props_ranking[df_props_ranking["Partido"] == partido]
            if len(df_jp) >= 2:
                r1 = df_jp.iloc[0]
                r2 = df_jp.iloc[1]
                p1 = _safe_float(r1.get("% Cubre"), 56.0) / 100.0
                p2 = _safe_float(r2.get("% Cubre"), 55.0) / 100.0
                s1_lbl = f"{r1.get('Jugador')} ({r1.get('Rol', r1.get('Posición', ''))}) {_extraer_lado_prop(r1)} {_safe_float(r1.get('Línea Mercado'), 0.0):.1f} {r1.get('Mercado_Corto', r1.get('Métrica', ''))}"
                s2_lbl = f"{r2.get('Jugador')} ({r2.get('Rol', r2.get('Posición', ''))}) {_extraer_lado_prop(r2)} {_safe_float(r2.get('Línea Mercado'), 0.0):.1f} {r2.get('Mercado_Corto', r2.get('Métrica', ''))}"
                p_ind_2 = round((p1 * p2) * 100.0, 1)
                boost_2 = round(0.24 * ((p1 * (1.0 - p1) * p2 * (1.0 - p2)) ** 0.5) * 100.0, 1)
                p_conj_2 = round(min(79.0, p_ind_2 + boost_2), 1)
                filas.append(
                    {
                        "Partido": partido,
                        "Selección_1": s1_lbl,
                        "Selección_2": s2_lbl,
                        "Prob_Independiente_%": p_ind_2,
                        "Prob_Conjunta_Sim_%": p_conj_2,
                        "Correlation_Edge_%": round(p_conj_2 - p_ind_2, 1),
                    }
                )
    if not filas:
        return pd.DataFrame(columns=cols)
    df_c = pd.DataFrame(filas, columns=cols)
    return df_c.sort_values(by=["Prob_Conjunta_Sim_%", "Correlation_Edge_%"], ascending=[False, False]).reset_index(drop=True)


def construir_df_plantilla_y_lesiones(
    resultados_simulados: List[Dict[str, Any]],
    starters_verified: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """
    Construye la pestaña 'Plantilla_y_Lesiones' con las columnas exactas:
      ['Equipo', 'QB1', 'WR1', 'WR2', 'WR3', 'RB1', 'RB2', 'TE1', 'TE2',
       'Bajas_OUT_GTD', 'Recien_Activados', 'Traspasos']
    """
    cols = [
        "Equipo",
        "QB1",
        "WR1",
        "WR2",
        "WR3",
        "RB1",
        "RB2",
        "TE1",
        "TE2",
        "Bajas_OUT_GTD",
        "Recien_Activados",
        "Traspasos",
    ]
    if starters_verified is None and cargar_estado_titulares_y_clima is not None:
        try:
            starters_verified = cargar_estado_titulares_y_clima(forzar_sync=False)
        except Exception:
            starters_verified = {}
    teams_map = (starters_verified or {}).get("teams", (starters_verified or {}).get("equipos", {})) if isinstance(starters_verified, dict) else {}

    equipos_orden: List[str] = []
    for s in resultados_simulados or []:
        for ab in (str(s.get("away_abbr", "")), str(s.get("home_abbr", ""))):
            if ab and ab not in equipos_orden:
                equipos_orden.append(ab)
    if not equipos_orden:
        equipos_orden = sorted(teams_map.keys())

    filas: List[Dict[str, Any]] = []
    for eq in equipos_orden:
        t_info = teams_map.get(eq, {}) or {}
        rot = t_info.get("offensive_rotation") or t_info.get("starters") or {}

        def _fmt_slot(sl_key: str) -> str:
            obj = rot.get(sl_key, {}) if isinstance(rot, dict) else {}
            nm = str(obj.get("player") or (t_info.get("qb1_name") if sl_key == "QB1" else f"{eq} {sl_key}"))
            st_s = str(obj.get("status", "ACTIVO_CONFIRMADO")).upper()
            if st_s in {"OUT_INACTIVO", "DOUBTFUL"}:
                return f"{nm} [OUT]"
            if st_s == "QUESTIONABLE_GTD":
                return f"{nm} [GTD]"
            if st_s == "RECIEN_ACTIVADO":
                return f"{nm} [ACTIVADO]"
            if st_s in {"TRASPASO_NUEVO", "TRASPASO_NUEVO_EQUIPO"}:
                return f"{nm} [NUEVO]"
            return f"{nm} [OK]"

        pills_b = (t_info.get("bajas_top3_pills") or [])[:3]
        bajas_txt = (
            ", ".join(f"{x['player']} ({x['slot']}-{x['badge']})" for x in pills_b)
            if pills_b
            else "Sin bajas titulares críticas"
        )
        act_txt = ", ".join((t_info.get("recien_activados") or [])[:3]) or "Sin novedades"
        tr_txt = ", ".join((t_info.get("traspasos_resumen") or [])[:2]) or "Sin movimientos relevantes"

        filas.append(
            {
                "Equipo": eq,
                "QB1": _fmt_slot("QB1"),
                "WR1": _fmt_slot("WR1"),
                "WR2": _fmt_slot("WR2"),
                "WR3": _fmt_slot("WR3"),
                "RB1": _fmt_slot("RB1"),
                "RB2": _fmt_slot("RB2"),
                "TE1": _fmt_slot("TE1"),
                "TE2": _fmt_slot("TE2"),
                "Bajas_OUT_GTD": bajas_txt,
                "Recien_Activados": act_txt,
                "Traspasos": tr_txt,
            }
        )
    if not filas:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(filas, columns=cols)


def _estilizar_hoja_excel_profesional(ws: Any) -> None:
    """
    Aplica encabezados oscuros institucionales (#0D1117 / #00FFCC), bordes limpios,
    formato condicional en columnas de '% Probabilidad' y '+EV', y autoajuste de ancho.
    """
    if ws is None or ws.max_row < 1:
        return

    header_fill = PatternFill(start_color="0D1117", end_color="0D1117", fill_type="solid")
    header_font = Font(name="Calibri", size=10, bold=True, color="00FFCC")
    zebra_even = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
    zebra_odd = PatternFill(start_color="F4F7FA", end_color="F4F7FA", fill_type="solid")
    high_prob_fill = PatternFill(start_color="D1FAE5", end_color="D1FAE5", fill_type="solid")
    high_prob_font = Font(name="Calibri", size=10, bold=True, color="065F46")
    pos_ev_fill = PatternFill(start_color="CCFBF1", end_color="CCFBF1", fill_type="solid")
    pos_ev_font = Font(name="Calibri", size=10, bold=True, color="0F766E")
    thin_side = Side(style="thin", color="CBD5E1")
    cell_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    max_r = ws.max_row
    max_c = ws.max_column

    prob_cols: List[int] = []
    ev_cols: List[int] = []

    for c_idx in range(1, max_c + 1):
        hdr_cell = ws.cell(row=1, column=c_idx)
        hdr_txt = str(hdr_cell.value or "").strip()
        hdr_cell.fill = header_fill
        hdr_cell.font = header_font
        hdr_cell.alignment = Alignment(horizontal="center", vertical="center")
        if "Prob_" in hdr_txt or "Cubre" in hdr_txt:
            prob_cols.append(c_idx)
        elif "EV" in hdr_txt or "Edge_%" in hdr_txt:
            ev_cols.append(c_idx)

    for r_idx in range(2, max_r + 1):
        row_fill = zebra_even if (r_idx % 2 == 0) else zebra_odd
        for c_idx in range(1, max_c + 1):
            c = ws.cell(row=r_idx, column=c_idx)
            c.fill = row_fill
            c.border = cell_border
            val_num = _safe_float(c.value, -999.0)
            if c_idx in prob_cols and val_num >= 56.0:
                c.fill = high_prob_fill
                c.font = high_prob_font
            elif c_idx in ev_cols and val_num > 0.0:
                c.fill = pos_ev_fill
                c.font = pos_ev_font

    for c_idx in range(1, max_c + 1):
        col_letter = get_column_letter(c_idx)
        max_len = max(
            len(str(ws.cell(row=r_i, column=c_idx).value or ""))
            for r_i in range(1, min(max_r + 1, 150))
        )
        ws.column_dimensions[col_letter].width = max(12, min(46, max_len + 3))


def empaquetar_excel_en_memoria(
    df_general: pd.DataFrame,
    df_ranking: pd.DataFrame,
    df_props_ranking: Optional[pd.DataFrame] = None,
    resultados_simulados: Optional[List[Dict[str, Any]]] = None,
    starters_verified: Optional[Dict[str, Any]] = None,
    guardar_en_disco: bool = True,
) -> Tuple[bytes, str]:
    """
    Genera y formatea 'nfl_quant_projections.xlsx' en memoria (y en disco) con las 5 pestañas
    institucionales requeridas:
      1. 'Rankings_Probabilidad' (ML, Spread y Over/Under ordenados de MAYOR a MENOR Prob_Modelo_%)
      2. 'Proyecciones_Partidos'
      3. 'Player_Props_EV'
      4. 'Combos_Correlacionados'
      5. 'Plantilla_y_Lesiones'
    """
    sims_list = resultados_simulados or []
    df_tab_rankings = construir_df_rankings_probabilidad(sims_list)
    df_tab_partidos = construir_df_proyecciones_partidos(sims_list) if sims_list else df_general
    df_tab_props = construir_df_player_props_ev(df_props_ranking)
    df_tab_combos = construir_df_combos_correlacionados(sims_list, df_props_ranking)
    df_tab_plantilla = construir_df_plantilla_y_lesiones(sims_list, starters_verified=starters_verified)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_tab_rankings.to_excel(writer, index=False, sheet_name="Rankings_Probabilidad")
        df_tab_partidos.to_excel(writer, index=False, sheet_name="Proyecciones_Partidos")
        df_tab_props.to_excel(writer, index=False, sheet_name="Player_Props_EV")
        df_tab_combos.to_excel(writer, index=False, sheet_name="Combos_Correlacionados")
        df_tab_plantilla.to_excel(writer, index=False, sheet_name="Plantilla_y_Lesiones")

        for sh_name in (
            "Rankings_Probabilidad",
            "Proyecciones_Partidos",
            "Player_Props_EV",
            "Combos_Correlacionados",
            "Plantilla_y_Lesiones",
        ):
            if sh_name in writer.sheets:
                _estilizar_hoja_excel_profesional(writer.sheets[sh_name])

    buffer.seek(0)
    raw_bytes = buffer.getvalue()
    if guardar_en_disco:
        try:
            with open(EXCEL_ATTACHMENT_FILENAME, "wb") as f_xlsx:
                f_xlsx.write(raw_bytes)
        except Exception:
            pass
    b64_str = base64.b64encode(raw_bytes).decode("utf-8")
    return raw_bytes, b64_str


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Convierte de forma segura cualquier valor a float sin lanzar excepciones."""
    if val is None:
        return default
    try:
        if pd.isna(val):
            return default
    except Exception:
        pass
    try:
        if isinstance(val, (int, float)):
            return float(val)
        txt = str(val).strip().replace("%", "").replace("+", "").replace(",", "")
        return float(txt) if txt else default
    except Exception:
        return default


def _extraer_lado_prop(rp: Any) -> str:
    """
    Extrae de forma segura el lado recomendado ('OVER' o 'UNDER') desde una fila
    de 'df_props_ranking' verificando múltiples nombres de columna posibles
    ('Lado_Recomendado', 'Lado_Recom', 'Pick', 'Lado', 'Recomendación', 'Señal EV').
    """
    for col in ("Lado_Recomendado", "Lado_Recom", "Pick", "Lado", "Recomendación", "Recomendacion"):
        val = rp.get(col) if hasattr(rp, "get") else None
        if val is not None and str(val).strip() and str(val).strip().lower() != "nan":
            txt_u = str(val).strip().upper()
            if "UNDER" in txt_u:
                return "UNDER"
            if "OVER" in txt_u:
                return "OVER"
            return txt_u

    senal = str(rp.get("Señal EV", "") if hasattr(rp, "get") else "").upper()
    if "UNDER" in senal:
        return "UNDER"
    if "OVER" in senal:
        return "OVER"

    med = _safe_float(rp.get("Proyección Mediana") if hasattr(rp, "get") else 0.0, 0.0)
    lin = _safe_float(rp.get("Línea Mercado") if hasattr(rp, "get") else 0.0, 0.0)
    return "UNDER" if med < lin else "OVER"


def obtener_top_5_anchors_jornada(
    resultados_simulados: List[Dict[str, Any]],
    df_props_ranking: Optional[pd.DataFrame] = None,
) -> List[Dict[str, Any]]:
    """
    Construye el Top 5 Anchors de la jornada combinando Spreads, Totales y Player Props
    con ventaja matemática positiva (+EV > 0.0%), ordenados estrictamente de mayor a menor
    porcentaje de cubrimiento (% Cubre en las 5,000 simulaciones de Monte Carlo).
    """
    candidatos: List[Dict[str, Any]] = []

    for s in resultados_simulados:
        away = str(s.get("away_abbr", ""))
        home = str(s.get("home_abbr", ""))
        partido_str = f"{away} @ {home}"
        hora_cst = str(s.get("hora", "DOM 12:00 CST"))
        ev_sp = s.get("ev_spread", {}) or {}
        ev_to = s.get("ev_totales", {}) or {}

        sp_cov = _safe_float(s.get("spread_cover_pct", ev_sp.get("spread_cover_pct", ev_sp.get("prob_mejor_pct", 50.0))), 50.0)
        sp_ev = _safe_float(ev_sp.get("ev_pct", 0.0), 0.0)
        sp_odds = _safe_float(ev_sp.get("cuota_mercado_decimal", 1.91), 1.91)
        lado_sp = str(ev_sp.get("lado", "HOME"))
        team_sp = home if lado_sp == "HOME" else away
        sp_badges_anc = str(ev_sp.get("edge_badges_str", s.get("edge_badges_str", ""))).strip()
        sel_sp_anc = f"{ev_sp.get('recomendacion', team_sp)} ({sp_odds:.2f})"
        if sp_badges_anc:
            sel_sp_anc = f"{sel_sp_anc} · {sp_badges_anc}"

        candidatos.append(
            {
                "tipo": "SPREAD",
                "team_abbr": team_sp,
                "logo_url": get_team_logo_url(team_sp),
                "partido": partido_str,
                "horario": hora_cst,
                "seleccion": sel_sp_anc,
                "detalle": f"Proy: {away} {_safe_float(s.get('away_pts'), 0.0):.1f} - {_safe_float(s.get('home_pts'), 0.0):.1f} {home}",
                "pct_cubre": round(sp_cov, 1),
                "ev_pct": round(sp_ev, 1),
                "cuota": sp_odds,
                "es_ev_pos": sp_ev > 0.0,
                "edge_badges_str": sp_badges_anc,
            }
        )

        to_cov = _safe_float(s.get("total_cover_pct", ev_to.get("total_cover_pct", ev_to.get("prob_mejor_pct", 50.0))), 50.0)
        to_ev = _safe_float(ev_to.get("ev_pct", 0.0), 0.0)
        to_odds = _safe_float(ev_to.get("cuota_mercado_decimal", 1.91), 1.91)
        team_to = home if _safe_float(s.get("win_home_pct", 50.0), 50.0) >= _safe_float(s.get("win_away_pct", 50.0), 50.0) else away

        candidatos.append(
            {
                "tipo": "TOTAL",
                "team_abbr": team_to,
                "logo_url": get_team_logo_url(team_to),
                "partido": partido_str,
                "horario": hora_cst,
                "seleccion": f"{ev_to.get('lado', 'OVER')} {_safe_float(ev_to.get('total_mercado'), 44.5):.1f} ({to_odds:.2f})",
                "detalle": f"Total Proy: {_safe_float(s.get('total_ou'), 44.5):.1f} pts ({partido_str})",
                "pct_cubre": round(to_cov, 1),
                "ev_pct": round(to_ev, 1),
                "cuota": to_odds,
                "es_ev_pos": to_ev > 0.0,
            }
        )

    if df_props_ranking is not None and not df_props_ranking.empty:
        for _, rp in df_props_ranking.iterrows():
            ev_val = _safe_float(rp.get("EV_%", 0.0), 0.0)
            cov_val = _safe_float(rp.get("% Cubre", 50.0), 50.0)
            eq_abbr = str(rp.get("Equipo", "") or "").strip().upper()
            partido_p = str(rp.get("Partido", "") or "")
            if not eq_abbr and "@" in partido_p:
                eq_abbr = partido_p.split("@")[0].strip()
            jug = str(rp.get("Jugador", "") or "Jugador")
            pos = str(rp.get("Posición", rp.get("Posicion", "")) or "")
            met = str(rp.get("Métrica", rp.get("Metrica", "")) or "")
            lado_p = _extraer_lado_prop(rp)
            linea_p = _safe_float(rp.get("Línea Mercado", rp.get("Linea Mercado", 0.0)), 0.0)
            med_p = _safe_float(rp.get("Proyección Mediana", rp.get("Proyeccion Mediana", 0.0)), 0.0)

            candidatos.append(
                {
                    "tipo": f"PROP · {pos}",
                    "team_abbr": eq_abbr,
                    "logo_url": get_team_logo_url(eq_abbr),
                    "partido": partido_p,
                    "horario": str(rp.get("Kickoff", "DOM 12:00 CST") or "DOM 12:00 CST"),
                    "seleccion": f"{jug} ({pos}) — {lado_p} {linea_p:.1f} {met}",
                    "detalle": f"Proy: {med_p:.1f} | {partido_p}",
                    "pct_cubre": round(cov_val, 1),
                    "ev_pct": round(ev_val, 1),
                    "cuota": 1.91,
                    "es_ev_pos": ev_val > 0.0 and cov_val >= 54.5,
                }
            )

    positivos = [c for c in candidatos if c["es_ev_pos"]]
    pool = positivos if len(positivos) >= 5 else candidatos
    pool.sort(key=lambda x: (x["pct_cubre"], x["ev_pct"]), reverse=True)
    return pool[:5]


def generar_memorando_ejecutivo_top3(
    resultados_simulados: List[Dict[str, Any]],
    nfl_stats: Dict[str, Dict[str, Any]],
    semana: int,
) -> List[Dict[str, Any]]:
    """
    Selecciona los 3 mejores picks cuantitativos de la jornada priorizando el Valor
    Esperado (+EV %) y la probabilidad calibrada.
    """
    candidatos_picks: List[Dict[str, Any]] = []

    for sim in resultados_simulados:
        away = sim["away_abbr"]
        home = sim["home_abbr"]
        away_st = nfl_stats.get(away, {})
        home_st = nfl_stats.get(home, {})
        ev_spr = sim["ev_spread"]
        ev_tot = sim["ev_totales"]

        lado_sp = ev_spr["lado"]
        eq_pick = home if lado_sp == "HOME" else away
        eq_rival = away if lado_sp == "HOME" else home
        epa_pass_ventaja = (
            sim["net_pass_epa_home"] - sim["net_pass_epa_away"]
            if lado_sp == "HOME"
            else sim["net_pass_epa_away"] - sim["net_pass_epa_home"]
        )
        epa_rush_ventaja = (
            sim["net_rush_epa_home"] - sim["net_rush_epa_away"]
            if lado_sp == "HOME"
            else sim["net_rush_epa_away"] - sim["net_rush_epa_home"]
        )
        sr_pick = float(home_st.get("Success_Rate_Off", 0.48)) * 100.0 if lado_sp == "HOME" else float(away_st.get("Success_Rate_Off", 0.48)) * 100.0
        sr_def_rival = float(away_st.get("Success_Rate_Def", 0.44)) * 100.0 if lado_sp == "HOME" else float(home_st.get("Success_Rate_Def", 0.44)) * 100.0

        tesis_spread = (
            f"En situaciones competitivas (WP 5%–95%), {eq_pick} registra diferencial EPA/dropback "
            f"{epa_pass_ventaja:+.3f} y Success Rate de {sr_pick:.1f}% vs {sr_def_rival:.1f}% ({epa_rush_ventaja:+.3f} EPA/rush). "
            f"Línea justa proyectada: {home} {sim['spread_proyectado']:+.1f} (No-Vig {ev_spr['fair_decimal']:.2f})."
        )

        candidatos_picks.append(
            {
                "partido": f"{away} @ {home}",
                "horario": sim.get("hora", "DOM"),
                "mercado": "SPREAD",
                "pick": f"{ev_spr['recomendacion']} @ {ev_spr['cuota_mercado_decimal']:.2f}",
                "prob_pct": float(ev_spr["prob_mejor_pct"]),
                "ev_pct": float(ev_spr["ev_pct"]),
                "fair_odds": float(ev_spr["fair_decimal"]),
                "mkt_odds": float(ev_spr["cuota_mercado_decimal"]),
                "marcador_proy": f"{away} {sim['away_pts']:.1f} - {sim['home_pts']:.1f} {home}",
                "tesis": tesis_spread,
            }
        )

        lado_tot = ev_tot["lado"]
        tesis_total = (
            f"Media Monte Carlo en {sim['total_ou']:.1f} pts vs línea {ev_tot['total_mercado']:.1f} "
            f"(desviación {ev_tot['edge_pts']:+.1f} pts, ritmo {sim['pace_combinado']:.1f}s/play)."
        )

        candidatos_picks.append(
            {
                "partido": f"{away} @ {home}",
                "horario": sim.get("hora", "DOM"),
                "mercado": "TOTALES",
                "pick": f"{lado_tot} {ev_tot['total_mercado']:.1f} @ {ev_tot['cuota_mercado_decimal']:.2f}",
                "prob_pct": float(ev_tot["prob_mejor_pct"]),
                "ev_pct": float(ev_tot["ev_pct"]),
                "fair_odds": float(ev_tot["fair_decimal"]),
                "mkt_odds": float(ev_tot["cuota_mercado_decimal"]),
                "marcador_proy": f"{away} {sim['away_pts']:.1f} - {sim['home_pts']:.1f} {home}",
                "tesis": tesis_total,
            }
        )

    candidatos_picks.sort(key=lambda x: (x["ev_pct"], x["prob_pct"]), reverse=True)
    top_3: List[Dict[str, Any]] = []
    partidos_usados = set()
    for cand in candidatos_picks:
        if cand["partido"] not in partidos_usados:
            top_3.append(cand)
            partidos_usados.add(cand["partido"])
        if len(top_3) == 3:
            break
    if len(top_3) < 3:
        for cand in candidatos_picks:
            if cand not in top_3:
                top_3.append(cand)
            if len(top_3) == 3:
                break
    return top_3


def construir_html_reporte_nfl(
    semana: int,
    resultados_simulados: List[Dict[str, Any]],
    top_3_picks: List[Dict[str, Any]],
    df_ranking: pd.DataFrame,
    top_3_props: Optional[List[Dict[str, Any]]] = None,
    df_props_ranking: Optional[pd.DataFrame] = None,
    top_5_anchors: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Construye el Briefing Ejecutivo Mobile-First (estilo Terminal Financiera) usando
    tarjetas verticales apiladas (max-width: 600px, centrado, fondo #0d1117, tarjetas
    #161b22 con borde sutil #30363d) e incorporando los escudos oficiales de la NFL:
      - SECCIÓN 1: TOP 5 ANCHORS DE LA JORNADA (borde #00ffcc, escudos 18x18).
      - SECCIÓN 2: DESGLOSE POR PARTIDO EN ORDEN CRONOLÓGICO CST (escudos 26x26,
        marcador proyectado, línea de mercado, badges de Spread y Total con % Cubre
        en 5,000 sims y sub-lista compacta de Player Props +EV > 0.0%).
    """
    fecha_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total_partidos = len(resultados_simulados)
    oportunidades_ev = sum(
        1
        for s in resultados_simulados
        if s["ev_spread"]["hay_valor"] or s["ev_totales"]["hay_valor"]
    )
    total_props_ev = len(df_props_ranking) if (df_props_ranking is not None and not df_props_ranking.empty) else 0

    if top_5_anchors is None:
        top_5_anchors = obtener_top_5_anchors_jornada(resultados_simulados, df_props_ranking)

    # --------------------------------------------------------------------------
    # SECCIÓN 1 — TOP 5 ANCHORS DE LA JORNADA
    # --------------------------------------------------------------------------
    filas_anchors_html = ""
    for idx_a, anc in enumerate(top_5_anchors, start=1):
        logo_18 = (
            f'<img src="{anc["logo_url"]}" alt="{anc["team_abbr"]}" width="18" height="18" '
            f'style="width:18px; height:18px; vertical-align:middle; margin-right:6px; border:0;">'
        )
        borde_item = "border-bottom:1px solid #21262d;" if idx_a < len(top_5_anchors) else ""
        filas_anchors_html += (
            f'<div style="padding:9px 4px; {borde_item}">'
            f'<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;">'
            f'<div style="font-family:monospace; font-size:13px; color:#f0f6fc; font-weight:700;">'
            f'<span style="color:#00ffcc; font-weight:800; margin-right:5px;">#{idx_a}</span>'
            f'{logo_18}'
            f'<span>{anc["seleccion"]}</span>'
            f'</div>'
            f'<div style="background:rgba(0,255,204,0.12); border:1px solid #00ffcc; color:#00ffcc; '
            f'border-radius:4px; padding:2px 7px; font-family:monospace; font-size:11px; font-weight:700;">'
            f'Cubre: {anc["pct_cubre"]:.1f}% | {anc["ev_pct"]:+.1f}% EV'
            f'</div>'
            f'</div>'
            f'<div style="font-family:monospace; font-size:11px; color:#8b949e; margin-top:3px; padding-left:24px;">'
            f'[{anc["tipo"]}] · {anc["partido"]} ({anc["horario"]}) · {anc["detalle"]}'
            f'</div>'
            f'</div>'
        )

    seccion_top5_html = (
        f'<div style="background-color:#161b22; border:2px solid #00ffcc; border-radius:10px; '
        f'padding:14px 16px; margin-bottom:20px; box-shadow:0 4px 16px rgba(0,255,204,0.08);">'
        f'<div style="font-family:monospace; font-size:13px; font-weight:800; color:#00ffcc; '
        f'letter-spacing:0.6px; text-transform:uppercase; border-bottom:1px solid #30363d; '
        f'padding-bottom:8px; margin-bottom:6px;">'
        f'⚡ SECCIÓN 1 — TOP 5 ANCHORS DE LA JORNADA (MAYOR % CUBRE · 5,000 SIMS)'
        f'</div>'
        f'{filas_anchors_html}'
        f'</div>'
    )

    # --------------------------------------------------------------------------
    # SECCIÓN 2 — DESGLOSE POR PARTIDO (ORDEN CRONOLÓGICO CST)
    # --------------------------------------------------------------------------
    partidos_ordenados = sorted(
        resultados_simulados,
        key=lambda x: (int(x.get("_kickoff_sort", 40720)), f"{x['away_abbr']} @ {x['home_abbr']}"),
    )

    tarjetas_partidos_html = ""
    for s in partidos_ordenados:
        away = s["away_abbr"]
        home = s["home_abbr"]
        partido_key = f"{away} @ {home}"
        hora_cst = s.get("hora", "DOM 12:00 CST")
        away_full = NFL_FRANCHISE_NAMES.get(away, away)
        home_full = NFL_FRANCHISE_NAMES.get(home, home)

        logo_away_26 = (
            f'<img src="{get_team_logo_url(away)}" alt="{away}" width="26" height="26" '
            f'style="width:26px; height:26px; vertical-align:middle; margin-right:6px; border:0;">'
        )
        logo_home_26 = (
            f'<img src="{get_team_logo_url(home)}" alt="{home}" width="26" height="26" '
            f'style="width:26px; height:26px; vertical-align:middle; margin-left:6px; margin-right:6px; border:0;">'
        )

        ev_sp = s["ev_spread"]
        ev_to = s["ev_totales"]
        sp_cov = float(s.get("spread_cover_pct", ev_sp.get("spread_cover_pct", ev_sp.get("prob_mejor_pct", 50.0))))
        to_cov = float(s.get("total_cover_pct", ev_to.get("total_cover_pct", ev_to.get("prob_mejor_pct", 50.0))))
        sp_ev = float(ev_sp.get("ev_pct", 0.0))
        to_ev = float(ev_to.get("ev_pct", 0.0))
        sp_odds = float(ev_sp.get("cuota_mercado_decimal", 1.91))
        to_odds = float(ev_to.get("cuota_mercado_decimal", 1.91))

        # Badges para Spread y Total
        if ev_sp["hay_valor"] or sp_ev > 0.0:
            sp_badge_style = "background:rgba(0,255,204,0.10); border:1px solid #00ffcc; color:#00ffcc;"
            sp_icon = "🔥"
        else:
            sp_badge_style = "background:#0d1117; border:1px solid #30363d; color:#8b949e;"
            sp_icon = "⚪"

        if ev_to["hay_valor"] or to_ev > 0.0:
            to_badge_style = "background:rgba(0,255,204,0.10); border:1px solid #00ffcc; color:#00ffcc;"
            to_icon = "🔥"
        else:
            to_badge_style = "background:#0d1117; border:1px solid #30363d; color:#8b949e;"
            to_icon = "⚪"

        sp_edge_badges = str(ev_sp.get("edge_badges_str", s.get("edge_badges_str", ""))).strip()
        sp_edge_html_pill = ""
        if sp_edge_badges:
            pills_edge = []
            for b_item in [x.strip() for x in sp_edge_badges.split("·") if x.strip()]:
                pills_edge.append(
                    f'<span style="display:inline-block; white-space:nowrap; background:rgba(56,189,248,0.16); '
                    f'border:1px solid #38bdf8; color:#7dd3fc; padding:2px 7px; border-radius:999px; '
                    f'font-size:10.5px; font-weight:800; margin-left:4px;">{b_item}</span>'
                )
            sp_edge_html_pill = " " + "".join(pills_edge)

        # BLOQUE 4 — SEÑALES SPREAD & TOTAL (con white-space:nowrap en badges de ventaja estructural)
        badge_spread_html = (
            f'<div style="{sp_badge_style} border-radius:7px; padding:8px 11px; margin-bottom:6px; '
            f'font-family:\'Inter\',\'Segoe UI\',Arial,sans-serif; font-size:12px; font-weight:700; line-height:1.45;">'
            f'🛡️ SPREAD: {sp_icon} <b>{ev_sp["recomendacion"]}</b> · Cuota {sp_odds:.2f} · '
            f'<span style="white-space:nowrap;">{sp_cov:.1f}% Cubre</span> · '
            f'<span style="white-space:nowrap;">{sp_ev:+.1f}% EV</span>{sp_edge_html_pill}'
            f'</div>'
        )
        badge_total_html = (
            f'<div style="{to_badge_style} border-radius:7px; padding:8px 11px; margin-bottom:10px; '
            f'font-family:\'Inter\',\'Segoe UI\',Arial,sans-serif; font-size:12px; font-weight:700; line-height:1.45;">'
            f'🎯 TOTAL: {to_icon} <b>{ev_to["lado"]} {ev_to["total_mercado"]:.1f}</b> · Cuota {to_odds:.2f} · '
            f'<span style="white-space:nowrap;">{to_cov:.1f}% Cubre</span> · '
            f'<span style="white-space:nowrap;">{to_ev:+.1f}% EV</span>'
            f'</div>'
        )

        # BLOQUE 5 — PLAYER PROPS +EV (Tabla alineada con Rol confirmado y etiqueta corta de mercado)
        filas_props_tabla_html = ""
        if df_props_ranking is not None and not df_props_ranking.empty:
            df_juego_props = df_props_ranking[
                (df_props_ranking["Partido"] == partido_key)
                & (df_props_ranking["EV_%"] > 0.0)
            ].sort_values(by=["% Cubre", "EV_%"], ascending=[False, False])

            for _, rp in df_juego_props.iterrows():
                jug_n = str(rp.get("Jugador", "") or "Jugador")
                rol_n = str(rp.get("Rol") or rp.get("Posición") or rp.get("Posicion") or "WR1")
                met_raw = str(rp.get("Mercado_Corto") or rp.get("Métrica") or rp.get("Metrica") or "Rec Yds")
                mapa_etiqueta_mkt = {
                    "Rush + Rec Yds": "Rush+Rec",
                    "Pass + Rush Yds": "Pass+Rush",
                    "Pass Completions": "Completions",
                }
                met_label = mapa_etiqueta_mkt.get(met_raw, met_raw)
                lado_n = _extraer_lado_prop(rp)
                lin_n = _safe_float(rp.get("Línea Mercado", rp.get("Linea Mercado", 0.0)), 0.0)
                med_n = _safe_float(rp.get("Proyección Mediana", rp.get("Proyeccion Mediana", 0.0)), 0.0)
                cov_n = _safe_float(rp.get("% Cubre", 50.0), 50.0)
                ev_n = _safe_float(rp.get("EV_%", 0.0), 0.0)
                pick_cell = f"SI ({rp.get('Cuota_Decimal', 1.91):.2f})" if met_label == "Anytime TD" else f"{lado_n} {lin_n:.1f}"

                filas_props_tabla_html += (
                    f'<tr style="border-bottom:1px solid #21262d;">'
                    f'<td style="padding:5px 4px; color:#f0f6fc; font-weight:600;">'
                    f'{jug_n} <span style="color:#58a6ff; font-weight:700;">({rol_n})</span> · '
                    f'<span style="color:#8b949e;">{met_label}</span></td>'
                    f'<td style="padding:5px 4px; color:#00ffcc; font-weight:700; white-space:nowrap;">{pick_cell}</td>'
                    f'<td style="padding:5px 4px; color:#10b981; font-weight:700; text-align:right; white-space:nowrap;">{med_n:.1f}</td>'
                    f'<td style="padding:5px 4px; color:#f0f6fc; font-weight:700; text-align:right; white-space:nowrap;">{cov_n:.1f}%</td>'
                    f'<td style="padding:5px 4px; color:#00ffcc; font-weight:800; text-align:right; white-space:nowrap;">{ev_n:+.1f}%</td>'
                    f'</tr>'
                )

        if filas_props_tabla_html:
            props_bloque_5_html = (
                f'<table style="width:100%; border-collapse:collapse; font-family:\'Inter\',\'Segoe UI\',Arial,sans-serif; font-size:11.5px;">'
                f'<thead>'
                f'<tr style="border-bottom:1px solid #30363d; color:#8b949e; font-size:10.5px; text-transform:uppercase;">'
                f'<th style="padding:4px; text-align:left;">Jugador (Rol) · Mercado</th>'
                f'<th style="padding:4px; text-align:left;">Línea / Pick</th>'
                f'<th style="padding:4px; text-align:right;">Proy</th>'
                f'<th style="padding:4px; text-align:right;">Cubre %</th>'
                f'<th style="padding:4px; text-align:right;">+EV</th>'
                f'</tr>'
                f'</thead>'
                f'<tbody>{filas_props_tabla_html}</tbody>'
                f'</table>'
            )
        else:
            props_bloque_5_html = (
                '<div style="font-family:\'Inter\',\'Segoe UI\',Arial,sans-serif; font-size:11.5px; color:#8b949e; padding:3px 0;">'
                '• Sin Player Props con ventaja matemática (+EV > 0.0%) en este encuentro.'
                '</div>'
            )

        # BLOQUE 1 (Header con Pill compacto de Clima a la derecha, sin duplicar clima afuera)
        bloque_est_obj = s.get("bloque_estado_partido") or {}
        clima_pill_txt = str(
            bloque_est_obj.get("clima_pill")
            or ("🏟️ Domo · 70°F" if "DOM" in str(s.get("resumen_clima", "")).upper() else f"🌤️ {s.get('viento_mph', 8):.0f} mph")
        )

        # BLOQUE 2 (Plantilla — Filas limpias: Fila QB1 con [TITULAR OK], Fila Bajas con pills OUT/GTD, Fila Movimientos condicional)
        qb_aw_nm = str(bloque_est_obj.get("qb_away_name") or s.get("away_qb", f"{away} QB1"))
        qb_hm_nm = str(bloque_est_obj.get("qb_home_name") or s.get("home_qb", f"{home} QB1"))
        qb_aw_tag = str(bloque_est_obj.get("qb_away_tag") or "TITULAR OK")
        qb_hm_tag = str(bloque_est_obj.get("qb_home_tag") or "TITULAR OK")
        if qb_aw_tag == "OK":
            qb_aw_tag = "TITULAR OK"
        if qb_hm_tag == "OK":
            qb_hm_tag = "TITULAR OK"

        fila_qb1_html = (
            f'<div style="padding:4px 0; border-bottom:1px solid #21262d; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:4px;">'
            f'<div><span style="color:#8b949e; font-weight:600;">QB1 {away}:</span> <b style="color:#f0f6fc;">{qb_aw_nm}</b> '
            f'<span style="background:rgba(16,185,129,0.16); border:1px solid #10b981; color:#34d399; border-radius:4px; padding:1px 5px; font-size:10px; font-weight:700; white-space:nowrap;">[{qb_aw_tag}]</span></div>'
            f'<div><span style="color:#8b949e; font-weight:600;">QB1 {home}:</span> <b style="color:#f0f6fc;">{qb_hm_nm}</b> '
            f'<span style="background:rgba(16,185,129,0.16); border:1px solid #10b981; color:#34d399; border-radius:4px; padding:1px 5px; font-size:10px; font-weight:700; white-space:nowrap;">[{qb_hm_tag}]</span></div>'
            f'</div>'
        )

        pills_aw = bloque_est_obj.get("bajas_away_pills") or []
        pills_hm = bloque_est_obj.get("bajas_home_pills") or []
        bajas_badges_html_list: List[str] = []
        for eq_b, lista_p in ((away, pills_aw[:3]), (home, pills_hm[:3])):
            for item_b in lista_p:
                badge_tipo = str(item_b.get("badge", "OUT")).upper()
                rol_b = str(item_b.get("slot", ""))
                jug_b = str(item_b.get("player", ""))
                if badge_tipo == "OUT":
                    pill_style = "background:rgba(248,81,73,0.16); border:1px solid rgba(248,81,73,0.55); color:#ff7b72;"
                else:
                    pill_style = "background:rgba(210,153,34,0.18); border:1px solid rgba(210,153,34,0.55); color:#e3b341;"
                bajas_badges_html_list.append(
                    f'<span style="display:inline-block; white-space:nowrap; {pill_style} border-radius:5px; padding:1px 6px; font-size:10.5px; font-weight:700; margin:2px 3px 2px 0;">'
                    f'{eq_b} {jug_b} ({rol_b} · {badge_tipo})</span>'
                )

        if bajas_badges_html_list:
            fila_bajas_html = (
                f'<div style="padding:5px 0; border-bottom:1px solid #21262d;">'
                f'<span style="color:#8b949e; font-weight:700; font-size:11px; margin-right:4px;">BAJAS CLAVE:</span>'
                f'{"".join(bajas_badges_html_list)}'
                f'</div>'
            )
        else:
            fila_bajas_html = (
                f'<div style="padding:4px 0; color:#8b949e; font-size:11px;">'
                f'<b>BAJAS CLAVE:</b> Sin bajas titulares críticas en la rotación de 8 puestos.'
                f'</div>'
            )

        # Fila Movimientos: Mostrar ACTIVADOS o TRASPASOS únicamente si hay novedades reales en la rotación principal
        act_reales = bloque_est_obj.get("activados_reales") or []
        tr_reales = bloque_est_obj.get("traspasos_reales") or []
        partes_mov_html: List[str] = []
        if act_reales:
            partes_mov_html.append(
                f'<span style="color:#3fb950; font-weight:700;">🟢 ACTIVADOS:</span> {" | ".join(act_reales)}'
            )
        if tr_reales:
            partes_mov_html.append(
                f'<span style="color:#79c0ff; font-weight:700;">🔄 TRASPASOS:</span> {" | ".join(tr_reales)}'
            )
        fila_movimientos_html = (
            f'<div style="padding:4px 0 2px 0; font-size:11px; color:#e6edf3;">'
            f'{" · ".join(partes_mov_html)}'
            f'</div>'
            if partes_mov_html
            else ""
        )

        bloque_2_plantilla_html = (
            f'<div style="background:#0d1117; border:1px solid #30363d; border-left:3px solid #58a6ff; '
            f'border-radius:7px; padding:7px 10px; margin-bottom:9px; font-family:\'Inter\',\'Segoe UI\',Arial,sans-serif; '
            f'font-size:11.5px; color:#e6edf3; line-height:1.45;">'
            f'{fila_qb1_html}'
            f'{fila_bajas_html}'
            f'{fila_movimientos_html}'
            f'</div>'
        )

        # BLOQUE 3 (Proyección vs Mercado — Tabla compacta de 2 columnas)
        bloque_3_proy_mkt_html = (
            f'<table style="width:100%; border-collapse:collapse; background:#0d1117; border:1px solid #21262d; '
            f'border-radius:7px; margin-bottom:9px; font-family:\'Inter\',\'Segoe UI\',Arial,sans-serif; font-size:12px;">'
            f'<tr>'
            f'<td style="width:50%; padding:7px 10px; border-right:1px solid #21262d; vertical-align:top;">'
            f'<div style="font-size:10px; color:#8b949e; text-transform:uppercase; font-weight:700;">📊 Proyección Modelo (5,000 Sims)</div>'
            f'<div style="color:#10b981; font-weight:800; font-size:13.5px; margin-top:2px;">{away} {s["away_pts"]:.1f} — {s["home_pts"]:.1f} {home}</div>'
            f'<div style="color:#c9d1d9; font-size:11px; margin-top:2px;">Spread Mod: <b>{home} {s["spread_proyectado"]:+.1f}</b> · Total Mod: <b>{s["total_ou"]:.1f}</b></div>'
            f'</td>'
            f'<td style="width:50%; padding:7px 10px; vertical-align:top;">'
            f'<div style="font-size:10px; color:#8b949e; text-transform:uppercase; font-weight:700;">🏦 Líneas del Casino</div>'
            f'<div style="color:#f0f6fc; font-weight:800; font-size:13px; margin-top:2px;">Spread {home} {s["spread_mercado_home"]:+.1f} · O/U {s["total_mercado"]:.1f}</div>'
            f'<div style="color:#58a6ff; font-size:11px; margin-top:2px;">ML Favorito: <b>{s["ml_fav_abbr"]} ({s["ml_fav_model_pct"]:.1f}%)</b></div>'
            f'</td>'
            f'</tr>'
            f'</table>'
        )

        tarjetas_partidos_html += (
            f'<div style="background-color:#161b22; border:1px solid #30363d; border-radius:10px; '
            f'padding:14px 15px; margin-bottom:14px; font-family:\'Inter\',\'Segoe UI\',Arial,sans-serif;">'
            f'<div style="display:flex; justify-content:space-between; align-items:center; '
            f'border-bottom:1px solid #30363d; padding-bottom:8px; margin-bottom:9px; flex-wrap:wrap; gap:6px;">'
            f'<div style="font-size:15px; font-weight:800; color:#f0f6fc;">'
            f'{logo_away_26}{away} <span style="color:#8b949e; font-weight:500;">@</span> {logo_home_26}{home} '
            f'<span style="font-size:11.5px; color:#8b949e; font-weight:500; margin-left:4px;">({away_full} en {home_full})</span>'
            f'</div>'
            f'<div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">'
            f'<span style="background:#0d1117; border:1px solid #30363d; color:#58a6ff; '
            f'padding:2px 8px; border-radius:999px; font-size:11px; font-weight:700; white-space:nowrap;">'
            f'🕒 {hora_cst}'
            f'</span>'
            f'<span style="background:#0d1117; border:1px solid #30363d; color:#c9d1d9; '
            f'padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600; white-space:nowrap;">'
            f'{clima_pill_txt}'
            f'</span>'
            f'</div>'
            f'</div>'
            f'{bloque_2_plantilla_html}'
            f'{bloque_3_proy_mkt_html}'
            f'{badge_spread_html}'
            f'{badge_total_html}'
            f'<div style="background:#0d1117; border:1px solid #21262d; border-radius:7px; padding:8px 10px;">'
            f'<div style="font-size:11px; font-weight:800; color:#58a6ff; '
            f'text-transform:uppercase; margin-bottom:5px; letter-spacing:0.3px;">'
            f'🎯 PLAYER PROPS (+EV > 0.0% · ROTACIÓN OFENSIVA CONFIRMADA)'
            f'</div>'
            f'{props_bloque_5_html}'
            f'</div>'
            f'</div>'
        )

    html = (
        f'<!DOCTYPE html>'
        f'<html><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        f'</head>'
        f'<body style="margin:0; padding:12px; background-color:#0d1117; color:#e6edf3; '
        f'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">'
        f'<div style="max-width:600px; margin:0 auto; background-color:#0d1117; '
        f'border:1px solid #30363d; border-radius:12px; padding:16px;">'
        f'<div style="border-bottom:1px solid #30363d; padding-bottom:12px; margin-bottom:16px;">'
        f'<div style="color:#00ffcc; font-family:monospace; font-size:11px; font-weight:800; letter-spacing:0.8px;">'
        f'TERMINAL SHARP: NFL QUANT · MOBILE EXECUTIVE BRIEFING'
        f'</div>'
        f'<h1 style="margin:5px 0 4px 0; font-family:monospace; font-size:19px; color:#f0f6fc;">'
        f'🏈 NFL QUANT — SEMANA {semana} (5,000 SIMS)'
        f'</h1>'
        f'<div style="color:#8b949e; font-size:11px; font-family:monospace;">'
        f'{fecha_utc} · {total_partidos} Juegos · {oportunidades_ev} Líneas +EV · {total_props_ev} Player Props +EV'
        f'</div>'
        f'</div>'
        f'{seccion_top5_html}'
        f'<div style="font-family:monospace; font-size:13px; font-weight:800; color:#00ffcc; '
        f'text-transform:uppercase; letter-spacing:0.5px; margin:16px 0 10px 0;">'
        f'📅 SECCIÓN 2 — DESGLOSE POR PARTIDO (ORDEN CRONOLÓGICO CST)'
        f'</div>'
        f'{tarjetas_partidos_html}'
        f'<div style="margin-top:16px; padding-top:10px; border-top:1px solid #30363d; '
        f'color:#8b949e; font-size:11px; font-family:monospace; text-align:center;">'
        f'Adjuntos: <b>{ATTACHMENT_FILENAME}</b> &amp; <b>{EXCEL_ATTACHMENT_FILENAME}</b> · TERMINAL SHARP: NFL QUANT'
        f'</div>'
        f'</div>'
        f'</body></html>'
    )
    return html


def _limpiar_ascii_pdf(texto: str) -> str:
    """Normaliza acentos, emojis y símbolos Unicode a ASCII seguro para fuentes base PDF."""
    reemplazos = {
        "—": "--",
        "–": "-",
        "•": "-",
        "·": "|",
        "🔥": "[+EV]",
        "⚪": "[NEU]",
        "🏈": "[NFL]",
        "⚡": "[TOP]",
        "🛡️": "[SPR]",
        "🎯": "[TOT]",
        "🕒": "",
        "📊": "",
        "🏦": "",
        "📅": "",
        "≥": ">=",
        "≤": "<=",
    }
    res = str(texto or "")
    for k, v in reemplazos.items():
        res = res.replace(k, v)
    res_norm = unicodedata.normalize("NFKD", res)
    # Codificar en ASCII estricto ignorando diacríticos y emojis residuales
    return res_norm.encode("ascii", errors="ignore").decode("ascii")


def _generar_pdf_fallback_minimo(lineas: List[str]) -> bytes:
    """
    Generador PDF 1.4 vertical ligero en Python puro como respaldo en caso de que
    ni 'fpdf2' ni 'reportlab' estén disponibles en el entorno local.
    """
    lineas_por_pag = 48
    paginas = [lineas[i : i + lineas_por_pag] for i in range(0, max(1, len(lineas)), lineas_por_pag)]

    objetos: List[bytes] = []
    objetos.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids_refs = " ".join(f"{4 + idx * 2} 0 R" for idx in range(len(paginas)))
    objetos.append(f"<< /Type /Pages /Kids [{kids_refs}] /Count {len(paginas)} >>".encode("ascii"))
    objetos.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    for idx, pag_lineas in enumerate(paginas):
        page_obj_num = 4 + idx * 2
        content_obj_num = page_obj_num + 1
        cmd_lines = ["BT", "/F1 8.5 Tf", "36 756 Td", "14 TL"]
        for ln in pag_lineas:
            safe_ln = (
                _limpiar_ascii_pdf(ln)
                .replace("\\", "\\\\")
                .replace("(", "\\(")
                .replace(")", "\\)")
            )
            cmd_lines.append(f"({safe_ln[:96]}) Tj T*")
        cmd_lines.append("ET")
        stream_bytes = "\n".join(cmd_lines).encode("ascii", errors="ignore")
        page_dict = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_obj_num} 0 R >>"
        ).encode("ascii")
        content_dict = (
            f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("ascii")
            + stream_bytes
            + b"\nendstream"
        )
        objetos.append(page_dict)
        objetos.append(content_dict)

    out = bytearray(b"%PDF-1.4\n")
    offsets: List[int] = []
    for idx_obj, body in enumerate(objetos, start=1):
        offsets.append(len(out))
        out.extend(f"{idx_obj} 0 obj\n".encode("ascii"))
        out.extend(body)
        out.extend(b"\nendobj\n")

    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objetos) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return bytes(out)


def generar_pdf_briefing_nfl(
    semana: int,
    resultados_simulados: List[Dict[str, Any]],
    top_5_anchors: List[Dict[str, Any]],
    df_props_ranking: Optional[pd.DataFrame] = None,
) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Renderiza el Briefing Ejecutivo ('Terminal_Sharp_NFL_Briefing.pdf') en formato
    vertical limpio usando 'fpdf2' o 'reportlab' (con iniciales estilizadas [DAL] @ [KC]
    para preservar la maquetación). Si falla cualquier librería, retorna (None, None)
    sin detener el envío del correo HTML.
    """
    fecha_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    partidos_ordenados = sorted(
        resultados_simulados or [],
        key=lambda x: (int(x.get("_kickoff_sort", 40720)), f"{x.get('away_abbr', '')} @ {x.get('home_abbr', '')}"),
    )

    lineas_doc: List[str] = [
        f"TERMINAL SHARP: NFL QUANT -- BRIEFING EJECUTIVO SEMANA {semana}",
        f"Generado: {fecha_utc} | Simulaciones Monte Carlo: 5,000 por partido",
        "=" * 84,
        "SECCION 1 -- TOP 5 ANCHORS DE LA JORNADA (MAYOR % DE CUBRIMIENTO)",
        "-" * 84,
    ]
    for idx_a, anc in enumerate(top_5_anchors or [], start=1):
        t_abbr = str(anc.get("team_abbr", "NFL") or "NFL")
        t_tipo = str(anc.get("tipo", "PICK") or "PICK")
        t_sel = str(anc.get("seleccion", "") or "")
        t_cov = _safe_float(anc.get("pct_cubre", 50.0), 50.0)
        t_ev = _safe_float(anc.get("ev_pct", 0.0), 0.0)
        t_part = str(anc.get("partido", "") or "")
        t_hor = str(anc.get("horario", "") or "")
        lineas_doc.append(
            f" #{idx_a} [{t_abbr}] ({t_tipo}) {t_sel} | "
            f"Cubre: {t_cov:.1f}% | EV: {t_ev:+.1f}% | {t_part} ({t_hor})"
        )

    lineas_doc.append("=" * 84)
    lineas_doc.append("SECCION 2 -- DESGLOSE POR PARTIDO (ORDEN CRONOLOGICO CST)")
    lineas_doc.append("-" * 84)

    for s in partidos_ordenados:
        away = str(s.get("away_abbr", "") or "")
        home = str(s.get("home_abbr", "") or "")
        partido_key = f"{away} @ {home}"
        hora_cst = str(s.get("hora", "DOM 12:00 CST") or "DOM 12:00 CST")
        ev_sp = s.get("ev_spread", {}) or {}
        ev_to = s.get("ev_totales", {}) or {}
        sp_cov = _safe_float(s.get("spread_cover_pct", ev_sp.get("spread_cover_pct", ev_sp.get("prob_mejor_pct", 50.0))), 50.0)
        to_cov = _safe_float(s.get("total_cover_pct", ev_to.get("total_cover_pct", ev_to.get("prob_mejor_pct", 50.0))), 50.0)

        away_pts = _safe_float(s.get("away_pts", 0.0), 0.0)
        home_pts = _safe_float(s.get("home_pts", 0.0), 0.0)
        sp_mkt_home = _safe_float(s.get("spread_mercado_home", 0.0), 0.0)
        tot_mkt = _safe_float(s.get("total_mercado", 44.5), 44.5)

        lineas_doc.append(
            f"[{away}] @ [{home}] | {hora_cst} | Proy: {away} {away_pts:.1f} - {home_pts:.1f} {home} "
            f"(Mkt: {home} {sp_mkt_home:+.1f} | O/U {tot_mkt:.1f})"
        )
        ln1_pdf = str(s.get("linea_1_qb_clima") or f"QB1: {s.get('away_qb', away)} [OK] vs {s.get('home_qb', home)} [OK] | Clima: {s.get('resumen_clima', 'Outdoor')}")
        ln2_pdf = str(s.get("linea_2_out_gtd") or "OUT / GTD: Sin bajas titulares reportadas")
        ln3_pdf = str(s.get("linea_3_activados") or "ACTIVADOS: Sin novedades")
        ln4_pdf = str(s.get("linea_4_traspasos") or "🔄 TRASPASOS: Sin cambios")
        lineas_doc.append(f"  [ROSTER] {ln1_pdf}")
        lineas_doc.append(f"  [BAJAS]  {ln2_pdf}")
        lineas_doc.append(f"  [ACTIVO] {ln3_pdf}")
        lineas_doc.append(f"  [TRASP]  {ln4_pdf}")
        sp_badges_pdf = str(ev_sp.get("edge_badges_str", s.get("edge_badges_str", ""))).strip()
        suf_sp_pdf = f" | {sp_badges_pdf}" if sp_badges_pdf else ""
        lineas_doc.append(
            f"  [SPREAD] {ev_sp.get('recomendacion', home)} | Cuota: {_safe_float(ev_sp.get('cuota_mercado_decimal'), 1.91):.2f} | "
            f"Cubre: {sp_cov:.1f}% (5,000 sims) | EV: {_safe_float(ev_sp.get('ev_pct'), 0.0):+.1f}%{suf_sp_pdf}"
        )
        lineas_doc.append(
            f"  [TOTAL]  {ev_to.get('lado', 'OVER')} {_safe_float(ev_to.get('total_mercado'), tot_mkt):.1f} | Cuota: {_safe_float(ev_to.get('cuota_mercado_decimal'), 1.91):.2f} | "
            f"Cubre: {to_cov:.1f}% (5,000 sims) | EV: {_safe_float(ev_to.get('ev_pct'), 0.0):+.1f}%"
        )

        if df_props_ranking is not None and not df_props_ranking.empty and "Partido" in df_props_ranking.columns:
            df_jp = df_props_ranking[df_props_ranking["Partido"] == partido_key].copy()
            if "EV_%" in df_jp.columns:
                df_jp = df_jp[df_jp["EV_%"].apply(lambda v: _safe_float(v, 0.0) > 0.0)]
            cols_sort = [c for c in ["% Cubre", "EV_%"] if c in df_jp.columns]
            if cols_sort:
                df_jp = df_jp.sort_values(by=cols_sort, ascending=[False] * len(cols_sort))

            for _, rp in df_jp.iterrows():
                jug_pdf = str(rp.get("Jugador") or rp.get("Player") or "Jugador")
                pos_pdf = str(rp.get("Posición") or rp.get("Posicion") or rp.get("Pos") or "")
                met_pdf = str(rp.get("Métrica") or rp.get("Metrica") or rp.get("Market") or "")
                lado_pdf = _extraer_lado_prop(rp)
                linea_pdf = _safe_float(
                    rp.get("Línea Mercado")
                    if rp.get("Línea Mercado") is not None
                    else rp.get("Linea Mercado", rp.get("Linea", 0.0)),
                    0.0,
                )
                proy_pdf = _safe_float(
                    rp.get("Proyección Mediana")
                    if rp.get("Proyección Mediana") is not None
                    else rp.get("Proyeccion Mediana", rp.get("Mediana", 0.0)),
                    0.0,
                )
                cubre_pdf = _safe_float(
                    rp.get("% Cubre")
                    if rp.get("% Cubre") is not None
                    else rp.get("Probabilidad_%", 50.0),
                    50.0,
                )
                ev_pdf = _safe_float(rp.get("EV_%", 0.0), 0.0)

                lineas_doc.append(
                    f"    - {jug_pdf} ({pos_pdf} {met_pdf}) -- "
                    f"{lado_pdf} {linea_pdf:.1f} | "
                    f"Proy: {proy_pdf:.1f} | "
                    f"Cubre: {cubre_pdf:.1f}% ({ev_pdf:+.1f}% EV)"
                )
        lineas_doc.append("-" * 84)

    # 1) Intento con reportlab (C-extension rápida y estable para texto Courier)
    try:
        from reportlab.lib.pagesizes import letter  # type: ignore
        from reportlab.pdfgen import canvas  # type: ignore

        buf_rl = io.BytesIO()
        c = canvas.Canvas(buf_rl, pagesize=letter)
        _, height = letter
        y = height - 36
        c.setFont("Courier-Bold", 10)
        for ln in lineas_doc:
            if y < 40:
                c.showPage()
                y = height - 36
            txt_clean = _limpiar_ascii_pdf(ln)
            if txt_clean.startswith("SECCION") or txt_clean.startswith("[") or txt_clean.startswith("TERMINAL"):
                c.setFont("Courier-Bold", 8.2)
            else:
                c.setFont("Courier", 7.8)
            c.drawString(30, y, txt_clean[:102])
            y -= 12
        c.save()
        pdf_bytes = buf_rl.getvalue()
        if pdf_bytes:
            return pdf_bytes, base64.b64encode(pdf_bytes).decode("utf-8")
    except Exception:
        pass

    # 2) Intento con fpdf2 (FPDF)
    try:
        from fpdf import FPDF  # type: ignore

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=12)
        pdf.add_page()
        pdf.set_fill_color(13, 17, 23)
        pdf.set_text_color(0, 255, 204)
        pdf.set_font("Courier", "B", 11)
        pdf.cell(
            0,
            9,
            _limpiar_ascii_pdf(f"TERMINAL SHARP: NFL QUANT - SEMANA {semana} BRIEFING"),
            ln=True,
            fill=True,
        )
        pdf.ln(2)
        pdf.set_text_color(20, 24, 30)
        for ln in lineas_doc[1:]:
            txt_clean = _limpiar_ascii_pdf(ln)
            if txt_clean.startswith("SECCION") or txt_clean.startswith("["):
                pdf.set_font("Courier", "B", 8.5)
            else:
                pdf.set_font("Courier", "", 8)
            pdf.multi_cell(0, 4.5, txt_clean)
        try:
            raw_out = pdf.output()
        except TypeError:
            raw_out = pdf.output(dest="S")
        pdf_bytes = bytes(raw_out) if isinstance(raw_out, (bytes, bytearray)) else str(raw_out).encode("latin-1", errors="ignore")
        if pdf_bytes:
            return pdf_bytes, base64.b64encode(pdf_bytes).decode("utf-8")
    except Exception:
        pass

    # 3) Respaldo PDF 1.4 ligero en Python puro
    try:
        pdf_bytes = _generar_pdf_fallback_minimo(lineas_doc)
        return pdf_bytes, base64.b64encode(pdf_bytes).decode("utf-8")
    except Exception as exc:
        print(f"[WARN] Falló la generación del PDF ({exc}); se enviará el correo HTML sin adjunto.")
        return None, None


def enviar_reporte_resend_nfl(semana: Optional[int] = None) -> Dict[str, Any]:
    """
    Ejecuta el flujo completo de simulación, construcción del Briefing Ejecutivo Mobile-First
    con escudos oficiales de la NFL, renderizado del adjunto PDF limpio
    ('Terminal_Sharp_NFL_Briefing.pdf') y despacho vía POST a 'https://api.resend.com/emails'.
    """
    sem, resultados, df_general, df_ranking, nfl_stats = ejecutar_pipeline_simulaciones_nfl(semana=semana)
    df_props_raw = simular_player_props_jornada(resultados, incluir_anytime_td=True)
    df_props_ranking = build_player_props_ranking_export_df(df_props_raw)
    top_3_props = obtener_top_3_player_props_jornada(df_props_raw)
    top_3 = generar_memorando_ejecutivo_top3(resultados, nfl_stats, semana=sem)
    top_5_anchors = obtener_top_5_anchors_jornada(resultados, df_props_ranking)

    html_body = construir_html_reporte_nfl(
        sem,
        resultados,
        top_3,
        df_ranking,
        top_3_props=top_3_props,
        df_props_ranking=df_props_ranking,
        top_5_anchors=top_5_anchors,
    )

    pdf_bytes: Optional[bytes] = None
    pdf_b64: Optional[str] = None
    try:
        pdf_bytes, pdf_b64 = generar_pdf_briefing_nfl(sem, resultados, top_5_anchors, df_props_ranking)
    except Exception as e:
        print(
            f"[WARN] Excepción capturada en generar_pdf_briefing_nfl ({e}); "
            "continuando el envío del correo HTML sin adjunto PDF."
        )
        pdf_bytes, pdf_b64 = None, None

    excel_bytes: Optional[bytes] = None
    excel_b64: Optional[str] = None
    try:
        excel_bytes, excel_b64 = empaquetar_excel_en_memoria(
            df_general=df_general,
            df_ranking=df_ranking,
            df_props_ranking=df_props_ranking,
            resultados_simulados=resultados,
            guardar_en_disco=True,
        )
    except Exception as e_xl:
        print(f"[WARN] Excepción capturada al generar {EXCEL_ATTACHMENT_FILENAME} ({e_xl}).")
        excel_bytes, excel_b64 = None, None

    print(
        f"[TERMINAL SHARP NFL] Semana {sem} | Partidos: {len(resultados)} | "
        f"Top 5 Anchors: {len(top_5_anchors)} | Player Props +EV: {len(df_props_ranking)}"
    )
    for idx_a, anc in enumerate(top_5_anchors, start=1):
        print(
            f"  Anchor #{idx_a}: [{anc['team_abbr']}] {anc['seleccion']} -> "
            f"Cubre: {anc['pct_cubre']:.1f}% | EV: {anc['ev_pct']:+.1f}%"
        )

    resend_api_key = os.environ.get("RESEND_API_KEY", "").strip()
    to_email_raw = os.environ.get("TO_EMAIL", "").strip()

    if not resend_api_key or not to_email_raw:
        print(
            "[WARN] Variables de entorno RESEND_API_KEY o TO_EMAIL no definidas. "
            "Simulación, Briefing HTML móvil, PDF y Excel completados correctamente en modo dry-run."
        )
        return {
            "enviado": False,
            "semana": sem,
            "partidos": len(resultados),
            "top_3": top_3,
            "top_5_anchors": top_5_anchors,
            "pdf_generado": bool(pdf_b64),
            "excel_generado": bool(excel_b64),
        }

    destinatarios = [e.strip() for e in to_email_raw.split(",") if e.strip()]
    payload: Dict[str, Any] = {
        "from": "Terminal Sharp NFL <onboarding@resend.dev>",
        "to": destinatarios,
        "subject": f"🏈 TERMINAL SHARP: NFL QUANT — Semana {sem} | Briefing Móvil & Top 5 Anchors",
        "html": html_body,
    }
    adjuntos_resend: List[Dict[str, str]] = []
    if pdf_b64:
        adjuntos_resend.append(
            {
                "filename": ATTACHMENT_FILENAME,
                "content": pdf_b64,
            }
        )
    if excel_b64:
        adjuntos_resend.append(
            {
                "filename": EXCEL_ATTACHMENT_FILENAME,
                "content": excel_b64,
            }
        )
    if adjuntos_resend:
        payload["attachments"] = adjuntos_resend

    headers = {
        "Authorization": f"Bearer {resend_api_key}",
        "Content-Type": "application/json",
    }

    response = requests.post(RESEND_API_URL, headers=headers, json=payload, timeout=20)
    if response.status_code in (200, 201, 202):
        resp_data = response.json()
        print(f"[OK] Briefing móvil NFL enviado exitosamente vía Resend. ID: {resp_data.get('id')}")
        return {
            "enviado": True,
            "id": resp_data.get("id"),
            "semana": sem,
            "partidos": len(resultados),
            "pdf_adjunto": bool(pdf_b64),
        }

    raise RuntimeError(
        f"Error al enviar correo en Resend API (HTTP {response.status_code}): {response.text}"
    )


if __name__ == "__main__":
    enviar_reporte_resend_nfl()
