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

RESEND_API_URL = "https://api.resend.com/emails"
ESPN_NFL_INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
DEFAULT_STATS_FILE = "nfl_stats.xlsx"
ATTACHMENT_FILENAME = "Terminal_Sharp_NFL_Briefing.pdf"


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

        if ev_spr["hay_valor"]:
            senal_sp_str = f"🔥 {ev_spr['recomendacion']} ({ev_spr['cuota_mercado_decimal']:.2f}) | Cubre: {sp_cov_pct:.1f}% | EV: {ev_spr['ev_pct']:+.1f}%"
        else:
            senal_sp_str = f"⚪ {ev_spr['recomendacion']} | Cubre: {sp_cov_pct:.1f}%"

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


def empaquetar_excel_en_memoria(
    df_general: pd.DataFrame,
    df_ranking: pd.DataFrame,
    df_props_ranking: Optional[pd.DataFrame] = None,
) -> Tuple[bytes, str]:
    """
    Mantiene compatibilidad con exportaciones Excel en memoria con openpyxl.
    """
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_general.to_excel(writer, index=False, sheet_name="Proyecciones_Generales")
        df_ranking.to_excel(writer, index=False, sheet_name="Ranking_Alta_Probabilidad")
        if df_props_ranking is not None and not df_props_ranking.empty:
            df_props_ranking.to_excel(writer, index=False, sheet_name="Player_Props_Ranking")
            estilizar_hoja_player_props_openpyxl(writer.sheets["Player_Props_Ranking"])
    buffer.seek(0)
    raw_bytes = buffer.getvalue()
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

        candidatos.append(
            {
                "tipo": "SPREAD",
                "team_abbr": team_sp,
                "logo_url": get_team_logo_url(team_sp),
                "partido": partido_str,
                "horario": hora_cst,
                "seleccion": f"{ev_sp.get('recomendacion', team_sp)} ({sp_odds:.2f})",
                "detalle": f"Proy: {away} {_safe_float(s.get('away_pts'), 0.0):.1f} - {_safe_float(s.get('home_pts'), 0.0):.1f} {home}",
                "pct_cubre": round(sp_cov, 1),
                "ev_pct": round(sp_ev, 1),
                "cuota": sp_odds,
                "es_ev_pos": sp_ev > 0.0,
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

        badge_spread_html = (
            f'<div style="{sp_badge_style} border-radius:6px; padding:7px 10px; margin-bottom:6px; '
            f'font-family:monospace; font-size:12px; font-weight:700;">'
            f'🛡️ SPREAD: {sp_icon} {ev_sp["recomendacion"]} | Cuota: {sp_odds:.2f} | '
            f'{sp_cov:.1f}% Cubre (5,000 sims) | {sp_ev:+.1f}% EV'
            f'</div>'
        )
        badge_total_html = (
            f'<div style="{to_badge_style} border-radius:6px; padding:7px 10px; margin-bottom:10px; '
            f'font-family:monospace; font-size:12px; font-weight:700;">'
            f'🎯 TOTAL: {to_icon} {ev_to["lado"]} {ev_to["total_mercado"]:.1f} | Cuota: {to_odds:.2f} | '
            f'{to_cov:.1f}% Cubre (5,000 sims) | {to_ev:+.1f}% EV'
            f'</div>'
        )

        # Sub-lista compacta de Player Props (+EV > 0.0%) de este partido ordenados de mayor a menor % Cubre
        props_lineas_html = ""
        if df_props_ranking is not None and not df_props_ranking.empty:
            df_juego_props = df_props_ranking[
                (df_props_ranking["Partido"] == partido_key)
                & (df_props_ranking["EV_%"] > 0.0)
            ].sort_values(by=["% Cubre", "EV_%"], ascending=[False, False])

            for _, rp in df_juego_props.iterrows():
                jug_n = str(rp.get("Jugador", "") or "Jugador")
                pos_n = str(rp.get("Posición", rp.get("Posicion", "")) or "")
                met_n = str(rp.get("Métrica", rp.get("Metrica", "")) or "")
                lado_n = _extraer_lado_prop(rp)
                lin_n = _safe_float(rp.get("Línea Mercado", rp.get("Linea Mercado", 0.0)), 0.0)
                med_n = _safe_float(rp.get("Proyección Mediana", rp.get("Proyeccion Mediana", 0.0)), 0.0)
                cov_n = _safe_float(rp.get("% Cubre", 50.0), 50.0)
                ev_n = _safe_float(rp.get("EV_%", 0.0), 0.0)
                props_lineas_html += (
                    f'<div style="font-family:monospace; font-size:11.5px; color:#e6edf3; '
                    f'padding:4px 0; border-bottom:1px dashed #21262d; line-height:1.45;">'
                    f'• <b style="color:#f0f6fc;">{jug_n}</b> ({pos_n} · {met_n}) — '
                    f'<span style="color:#00ffcc; font-weight:700;">{lado_n} {lin_n:.1f}</span> | '
                    f'Proy: <b style="color:#10b981;">{med_n:.1f}</b> | '
                    f'Cubre: <b style="color:#00ffcc;">{cov_n:.1f}%</b> ({ev_n:+.1f}% EV)'
                    f'</div>'
                )

        if not props_lineas_html:
            props_lineas_html = (
                '<div style="font-family:monospace; font-size:11px; color:#8b949e; padding:3px 0;">'
                '• Sin Player Props con ventaja matemática (+EV > 0.0%) en este encuentro.'
                '</div>'
            )

        tarjetas_partidos_html += (
            f'<div style="background-color:#161b22; border:1px solid #30363d; border-radius:10px; '
            f'padding:14px 15px; margin-bottom:14px;">'
            f'<div style="display:flex; justify-content:space-between; align-items:center; '
            f'border-bottom:1px solid #30363d; padding-bottom:8px; margin-bottom:8px; flex-wrap:wrap; gap:6px;">'
            f'<div style="font-family:monospace; font-size:15px; font-weight:800; color:#f0f6fc;">'
            f'{logo_away_26}{away} <span style="color:#8b949e; font-weight:400;">@</span> {logo_home_26}{home}'
            f'</div>'
            f'<span style="background:#0d1117; border:1px solid #30363d; color:#58a6ff; '
            f'padding:2px 8px; border-radius:4px; font-family:monospace; font-size:11px; font-weight:700;">'
            f'🕒 {hora_cst}'
            f'</span>'
            f'</div>'
            f'<div style="font-family:monospace; font-size:11.5px; color:#8b949e; margin-bottom:4px;">'
            f'{away_full} en {home_full} · {s.get("tipo_estadio", "Outdoor")}'
            f'</div>'
            f'<div style="background:#0d1117; border:1px solid #21262d; border-radius:6px; '
            f'padding:7px 10px; margin-bottom:9px; font-family:monospace; font-size:12px; color:#e6edf3;">'
            f'📊 <b>Marcador Proyectado:</b> <span style="color:#10b981; font-weight:800;">{away} {s["away_pts"]:.1f} - {s["home_pts"]:.1f} {home}</span> '
            f'(Total Mod: {s["total_ou"]:.1f})<br>'
            f'🏦 <b>Línea de Mercado:</b> Spread {home} {s["spread_mercado_home"]:+.1f} | Total O/U {s["total_mercado"]:.1f} '
            f'| ML Fav: {s["ml_fav_abbr"]} ({s["ml_fav_model_pct"]:.1f}%)'
            f'</div>'
            f'{badge_spread_html}'
            f'{badge_total_html}'
            f'<div style="background:#0d1117; border:1px solid #21262d; border-radius:6px; padding:8px 10px;">'
            f'<div style="font-family:monospace; font-size:11px; font-weight:800; color:#58a6ff; '
            f'text-transform:uppercase; margin-bottom:4px;">'
            f'🎯 PLAYER PROPS (+EV > 0.0% · ORDENADOS POR MAYOR % CUBRE)'
            f'</div>'
            f'{props_lineas_html}'
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
        f'Adjunto: <b>{ATTACHMENT_FILENAME}</b> · TERMINAL SHARP: NFL QUANT'
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
        lineas_doc.append(
            f"  [SPREAD] {ev_sp.get('recomendacion', home)} | Cuota: {_safe_float(ev_sp.get('cuota_mercado_decimal'), 1.91):.2f} | "
            f"Cubre: {sp_cov:.1f}% (5,000 sims) | EV: {_safe_float(ev_sp.get('ev_pct'), 0.0):+.1f}%"
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
    df_props_raw = simular_player_props_jornada(resultados, incluir_anytime_td=False)
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
            "Simulación, Briefing HTML móvil y PDF completados correctamente en modo dry-run."
        )
        return {
            "enviado": False,
            "semana": sem,
            "partidos": len(resultados),
            "top_3": top_3,
            "top_5_anchors": top_5_anchors,
            "pdf_generado": bool(pdf_b64),
        }

    destinatarios = [e.strip() for e in to_email_raw.split(",") if e.strip()]
    payload: Dict[str, Any] = {
        "from": "Terminal Sharp NFL <onboarding@resend.dev>",
        "to": destinatarios,
        "subject": f"🏈 TERMINAL SHARP: NFL QUANT — Semana {sem} | Briefing Móvil & Top 5 Anchors",
        "html": html_body,
    }
    if pdf_b64:
        payload["attachments"] = [
            {
                "filename": ATTACHMENT_FILENAME,
                "content": pdf_b64,
            }
        ]

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
