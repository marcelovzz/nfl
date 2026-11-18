#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_injuries_nfl.py — Sincronizador Oficial de Lesiones, Depth Chart, Inactivos,
Recién Activados, Clima en Vivo (Open-Meteo API) y Bucle de Auto-Calibración (Audit_Log)
para 'TERMINAL SHARP: NFL QUANT'.

Funcionalidades principales:
  1. Consulta los 3 endpoints oficiales de ESPN NFL:
     - Reporte general de lesiones: https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries
     - Depth Chart por franquicia: https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/depthcharts
     - Resumen del evento (inactivos oficiales 90 min antes del kickoff):
       https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={event_id}
  2. Detección de RECIÉN ACTIVADOS (Diff contra snapshot previo 'nfl_injuries_live.json'):
     - Compara jugadores que estaban en 'Out', 'Doubtful' o 'Injured Reserve' en la ejecución
       anterior contra el estado actual; si un titular de impacto (QB1, RB1, WR1, WR2, TE1, OL
       titular o defensivo clave) ya no aparece lesionado y figura activo en el Depth Chart/Roster,
       lo clasifica como 'RECIEN_ACTIVADO'.
  3. Clasifica el estado exacto ('ACTIVO_CONFIRMADO', 'RECIEN_ACTIVADO', 'QUESTIONABLE_GTD',
     'OUT_INACTIVO') para los titulares #1 en posiciones críticas:
     QB1, RB1, WR1, WR2, TE1, Linieros Ofensivos (LT, LG, C, RG, RT), CB1, Edge Rushers (DE1/OLB1) y MLB1.
  4. Guarda 'nfl_injuries_live.json' y 'nfl_starters_verified.json', y actualiza/crea la pestaña
     'Injuries_Live' en 'nfl_stats1.xlsx' con timestamp en CST.
  5. Clima en vivo para los 32 estadios de la NFL vía Open-Meteo API:
     - Si es 'OUTDOOR' y el viento supera 24 km/h (15 mph) o precipitación > 50%, aplica ajuste
       bajista al Total proyectado (-2.5 a -4.5 pts), reduce 'Pass_Rate' un 6% y penaliza un 8%
       las yardas de pase en 'engine_props_nfl.py'.
  6. Bucle de Auto-Calibración Bayesiana post-jornada y pestaña 'Audit_Log' en 'nfl_stats1.xlsx'
     (modo append con: 'Fecha', 'Semana', 'Partido', 'Marcador_Real', 'Proy_Spread', 'Error_Spread',
     'Proy_Total', 'Error_Total', 'Equipo', 'EPA_Off_Prev', 'EPA_Off_New', 'EPA_Def_Prev', 'EPA_Def_New').
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd
import requests

from sync_espn_nfl import (
    ESPN_NFL_SCOREBOARD_URL,
    NFL_FRANCHISE_NAMES,
    normalizar_abbr_nfl,
    obtener_calendario_nfl_semana,
)

ESPN_INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
ESPN_DEPTHCHART_URL_TPL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/depthcharts"
ESPN_ROSTER_URL_TPL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/roster"
ESPN_TRANSACTIONS_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/transactions"
ESPN_SUMMARY_URL_TPL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={event_id}"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

INJURIES_JSON_PATH = "nfl_injuries_live.json"
STARTERS_JSON_PATH = "nfl_starters_verified.json"
ROSTER_MOVES_JSON_PATH = "nfl_roster_moves.json"
DEFAULT_EXCEL_STATS_PATH = "nfl_stats1.xlsx"

NEW_TEAM_ADAPTATION_FACTOR = 0.85  # Factor conservador del 85% por adaptación al playbook en nuevo equipo

CST_TZ = timezone(timedelta(hours=-6))

# Mapeo oficial de IDs de equipo en ESPN para consultar Depth Charts
ESPN_TEAM_IDS: Dict[str, int] = {
    "ATL": 1,
    "BUF": 2,
    "CHI": 3,
    "CIN": 4,
    "CLE": 5,
    "DAL": 6,
    "DEN": 7,
    "DET": 8,
    "GB": 9,
    "TEN": 10,
    "IND": 11,
    "KC": 12,
    "LV": 13,
    "LA": 14,
    "MIA": 15,
    "MIN": 16,
    "NE": 17,
    "NO": 18,
    "NYG": 19,
    "NYJ": 20,
    "PHI": 21,
    "ARI": 22,
    "PIT": 23,
    "LAC": 24,
    "SF": 25,
    "SEA": 26,
    "TB": 27,
    "WAS": 28,
    "CAR": 29,
    "JAX": 30,
    "BAL": 33,
    "HOU": 34,
}

# Diccionario de coordenadas (lat, lon) y tipo de techo ('DOME' vs 'OUTDOOR') de los 32 estadios NFL
NFL_STADIUMS_COORDS: Dict[str, Dict[str, Any]] = {
    "ARI": {"name": "State Farm Stadium", "lat": 33.5276, "lon": -112.2626, "roof": "DOME"},
    "ATL": {"name": "Mercedes-Benz Stadium", "lat": 33.7554, "lon": -84.4010, "roof": "DOME"},
    "BAL": {"name": "M&T Bank Stadium", "lat": 39.2780, "lon": -76.6227, "roof": "OUTDOOR"},
    "BUF": {"name": "Highmark Stadium", "lat": 42.7738, "lon": -78.7870, "roof": "OUTDOOR"},
    "CAR": {"name": "Bank of America Stadium", "lat": 35.2258, "lon": -80.8528, "roof": "OUTDOOR"},
    "CHI": {"name": "Soldier Field", "lat": 41.8623, "lon": -87.6167, "roof": "OUTDOOR"},
    "CIN": {"name": "Paycor Stadium", "lat": 39.0954, "lon": -84.5160, "roof": "OUTDOOR"},
    "CLE": {"name": "Huntington Bank Field", "lat": 41.5061, "lon": -81.6995, "roof": "OUTDOOR"},
    "DAL": {"name": "AT&T Stadium", "lat": 32.7473, "lon": -97.0945, "roof": "DOME"},
    "DEN": {"name": "Empower Field at Mile High", "lat": 39.7439, "lon": -105.0201, "roof": "OUTDOOR"},
    "DET": {"name": "Ford Field", "lat": 42.3400, "lon": -83.0456, "roof": "DOME"},
    "GB":  {"name": "Lambeau Field", "lat": 44.5013, "lon": -88.0622, "roof": "OUTDOOR"},
    "HOU": {"name": "NRG Stadium", "lat": 29.6847, "lon": -95.4107, "roof": "DOME"},
    "IND": {"name": "Lucas Oil Stadium", "lat": 39.7601, "lon": -86.1639, "roof": "DOME"},
    "JAX": {"name": "EverBank Stadium", "lat": 30.3239, "lon": -81.6373, "roof": "OUTDOOR"},
    "KC":  {"name": "GEHA Field at Arrowhead", "lat": 39.0489, "lon": -94.4839, "roof": "OUTDOOR"},
    "LA":  {"name": "SoFi Stadium", "lat": 33.9535, "lon": -118.3392, "roof": "DOME"},
    "LAR": {"name": "SoFi Stadium", "lat": 33.9535, "lon": -118.3392, "roof": "DOME"},
    "LAC": {"name": "SoFi Stadium", "lat": 33.9535, "lon": -118.3392, "roof": "DOME"},
    "LV":  {"name": "Allegiant Stadium", "lat": 36.0909, "lon": -115.1833, "roof": "DOME"},
    "MIA": {"name": "Hard Rock Stadium", "lat": 25.9580, "lon": -80.2389, "roof": "OUTDOOR"},
    "MIN": {"name": "U.S. Bank Stadium", "lat": 44.9736, "lon": -93.2575, "roof": "DOME"},
    "NE":  {"name": "Gillette Stadium", "lat": 42.0909, "lon": -71.2643, "roof": "OUTDOOR"},
    "NO":  {"name": "Caesars Superdome", "lat": 29.9511, "lon": -90.0812, "roof": "DOME"},
    "NYG": {"name": "MetLife Stadium", "lat": 40.8128, "lon": -74.0742, "roof": "OUTDOOR"},
    "NYJ": {"name": "MetLife Stadium", "lat": 40.8128, "lon": -74.0742, "roof": "OUTDOOR"},
    "PHI": {"name": "Lincoln Financial Field", "lat": 39.9008, "lon": -75.1675, "roof": "OUTDOOR"},
    "PIT": {"name": "Acrisure Stadium", "lat": 40.4468, "lon": -80.0158, "roof": "OUTDOOR"},
    "SEA": {"name": "Lumen Field", "lat": 47.5952, "lon": -122.3316, "roof": "OUTDOOR"},
    "SF":  {"name": "Levi's Stadium", "lat": 37.4033, "lon": -121.9694, "roof": "OUTDOOR"},
    "TB":  {"name": "Raymond James Stadium", "lat": 27.9759, "lon": -82.5033, "roof": "OUTDOOR"},
    "TEN": {"name": "Nissan Stadium", "lat": 36.1665, "lon": -86.7713, "roof": "OUTDOOR"},
    "WAS": {"name": "Northwest Stadium", "lat": 38.9076, "lon": -76.8645, "roof": "OUTDOOR"},
    "WSH": {"name": "Northwest Stadium", "lat": 38.9076, "lon": -76.8645, "roof": "OUTDOOR"},
}

OFFENSIVE_ROTATION_SLOTS: List[str] = [
    "QB1",
    "WR1",
    "WR2",
    "WR3",
    "RB1",
    "RB2",
    "TE1",
    "TE2",
]

CRITICAL_POSITIONS_ORDER: List[str] = [
    "QB1",
    "RB1",
    "RB2",
    "WR1",
    "WR2",
    "WR3",
    "TE1",
    "TE2",
    "LT",
    "LG",
    "C",
    "RG",
    "RT",
    "CB1",
    "EDGE1",
    "MLB1",
]

SLOT_IMPACT_PRIORITY: Dict[str, int] = {
    "QB1": 1,
    "WR1": 2,
    "RB1": 3,
    "TE1": 4,
    "WR2": 5,
    "RB2": 6,
    "WR3": 7,
    "TE2": 8,
    "LT": 9,
    "RT": 10,
    "CB1": 11,
    "EDGE1": 12,
    "LG": 13,
    "C": 14,
    "RG": 15,
    "MLB1": 16,
}

AUDIT_LOG_COLUMNS: List[str] = [
    "Fecha",
    "Semana",
    "Partido",
    "Marcador_Real",
    "Proy_Spread",
    "Error_Spread",
    "Proy_Total",
    "Error_Total",
    "Equipo",
    "EPA_Off_Prev",
    "EPA_Off_New",
    "EPA_Def_Prev",
    "EPA_Def_New",
]

ROSTER_MOVES_COLUMNS: List[str] = [
    "Timestamp_CST",
    "Player",
    "Pos",
    "Equipo_Prev",
    "Equipo_Actual",
    "Tipo_Movimiento",
    "Factor_Adaptacion",
    "Role_Share_Base",
    "Baseline_Yds",
    "Catch_Rate",
    "Yds_Per_Unit",
    "TD_Rate",
    "Detalle_ESPN",
]


def _limpiar_nombre_jugador(nombre: str) -> str:
    txt = str(nombre or "").upper().strip()
    txt = re.sub(r"\b(JR\.?|SR\.?|II|III|IV|V)\b", "", txt)
    txt = re.sub(r"[^A-Z\s]", " ", txt)
    return " ".join(txt.split())


def _clave_canonica_jugador(team_abbr: str, player_name: str) -> str:
    std_team = normalizar_abbr_nfl(team_abbr)
    limpio = _limpiar_nombre_jugador(player_name)
    partes = limpio.split()
    if not partes:
        return f"{std_team}_UNK"
    if len(partes) == 1:
        return f"{std_team}_{partes[0]}"
    return f"{std_team}_{partes[0][0]}_{partes[-1]}"


def _clasificar_grupo_posicion(pos_raw: str, slot_label: str = "") -> str:
    p = str(pos_raw or "").strip().upper()
    s = str(slot_label or "").strip().upper()
    if p == "QB" or s.startswith("QB"):
        return "QB"
    if p in {"RB", "HB", "FB"} or s.startswith("RB"):
        return "RB"
    if p in {"WR", "FL", "SE", "SWR"} or s.startswith("WR"):
        return "WR"
    if p == "TE" or s.startswith("TE"):
        return "TE"
    if p in {"OT", "LT", "RT", "G", "LG", "RG", "C", "OL", "T"} or s in {"LT", "LG", "C", "RG", "RT"}:
        return "OL"
    if p in {"CB", "DB", "LCB", "RCB", "FS", "SS", "S"} or s.startswith("CB"):
        return "CB"
    if p in {"DE", "EDGE", "OLB", "LDE", "RDE", "LOLB", "ROLB", "DL", "DT", "NT"} or "EDGE" in s or "DE" in s:
        return "EDGE"
    if p in {"LB", "MLB", "ILB", "WLB", "SLB", "MIKE", "WILL", "SAM"} or "LB" in s:
        return "LB"
    return p or "OTHER"


def _mapear_estatus_espn(status_raw: str, comment_raw: str = "") -> str:
    st = str(status_raw or "").strip().upper()
    cm = str(comment_raw or "").strip().upper()
    if st in {"OUT", "INJURED RESERVE", "IR", "INACTIVE", "SUSPENDED", "PUP", "NFI", "NON-FOOTBALL INJURY"} or "INACTIVE" in st:
        return "OUT_INACTIVO"
    if st == "DOUBTFUL" or "DOUBTFUL" in st:
        return "DOUBTFUL"
    if st in {"QUESTIONABLE", "DAY-TO-DAY", "GTD"} or "QUESTIONABLE" in st or "GAME-TIME" in cm:
        return "QUESTIONABLE_GTD"
    return "ACTIVO_CONFIRMADO"


def cargar_snapshot_previo_lesiones(json_path: str = INJURIES_JSON_PATH) -> Dict[str, Any]:
    """
    Lee el snapshot anterior de 'nfl_injuries_live.json' antes de sobrescribirlo
    para detectar jugadores que estaban 'Out', 'Doubtful' o 'Injured Reserve'
    y ahora están activos ('RECIEN_ACTIVADO').
    """
    if not os.path.exists(json_path):
        return {}
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _extraer_bajas_previas_por_clave(snapshot_prev: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Extrae un diccionario {clave_canonica: info_jugador} de todos los jugadores
    que en la ejecución previa figuraban en 'Out', 'Doubtful', 'IR' o 'OUT_INACTIVO'.
    """
    bajas_prev: Dict[str, Dict[str, Any]] = {}
    if not snapshot_prev or not isinstance(snapshot_prev, dict):
        return bajas_prev

    equipos_prev = snapshot_prev.get("teams", {}) or {}
    for team_abbr, t_data in equipos_prev.items():
        std_t = normalizar_abbr_nfl(team_abbr)
        for item in (t_data.get("injuries", []) or []):
            raw_st = str(item.get("raw_status", item.get("status", ""))).upper()
            mapped_st = str(item.get("status_code", "")).upper()
            if (
                any(k in raw_st for k in ("OUT", "DOUBTFUL", "INJURED RESERVE", "IR", "INACTIVE"))
                or mapped_st in {"OUT_INACTIVO", "DOUBTFUL"}
            ):
                p_name = str(item.get("player", "")).strip()
                if p_name:
                    k_can = _clave_canonica_jugador(std_t, p_name)
                    bajas_prev[k_can] = {
                        "team": std_t,
                        "player": p_name,
                        "pos": str(item.get("pos", "")).upper(),
                        "prev_status": raw_st or mapped_st,
                    }
    return bajas_prev


def consultar_inactivos_evento_espn(event_id: str, timeout: int = 5) -> Dict[str, List[Dict[str, str]]]:
    """
    Consulta el resumen oficial del evento ('summary?event={event_id}') para extraer
    inactivos oficiales 90 minutos antes del kickoff o bajas reportadas en el boxscore/gameInfo.
    """
    inactivos_por_equipo: Dict[str, List[Dict[str, str]]] = {}
    if not event_id or str(event_id).startswith("SYNTH_"):
        return inactivos_por_equipo

    url = ESPN_SUMMARY_URL_TPL.format(event_id=event_id)
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
        )
        if resp.status_code != 200:
            return inactivos_por_equipo
        data = resp.json()

        # Revisar bloque 'injuries' dentro del summary del partido
        for team_inj in data.get("injuries", []) or []:
            team_obj = team_inj.get("team", {}) or {}
            t_abbr = normalizar_abbr_nfl(str(team_obj.get("abbreviation", "")))
            if not t_abbr:
                continue
            for inj in team_inj.get("injuries", []) or []:
                status_raw = str(inj.get("status", "")).strip()
                ath = inj.get("athlete", {}) or {}
                p_name = str(ath.get("displayName") or ath.get("shortName") or "").strip()
                p_pos = str((ath.get("position") or {}).get("abbreviation", "")).strip().upper()
                if p_name and status_raw:
                    inactivos_por_equipo.setdefault(t_abbr, []).append(
                        {
                            "player": p_name,
                            "pos": p_pos,
                            "status": status_raw,
                            "source": f"event_summary:{event_id}",
                        }
                    )
    except Exception:
        pass
    return inactivos_por_equipo


def consultar_depth_chart_equipo_espn(team_abbr: str, timeout: int = 5) -> Dict[str, Dict[str, str]]:
    """
    Consulta el Depth Chart oficial de ESPN para una franquicia:
    'https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/depthcharts'
    y extrae la rotación ofensiva completa ('QB1', 'WR1', 'WR2', 'WR3', 'RB1', 'RB2',
    'TE1', 'TE2') más los titulares en posiciones críticas de trinchera y defensa
    ('LT', 'LG', 'C', 'RG', 'RT', 'CB1', 'EDGE1', 'MLB1').
    """
    std_abbr = normalizar_abbr_nfl(team_abbr)
    team_id = ESPN_TEAM_IDS.get(std_abbr)
    titulares: Dict[str, Dict[str, str]] = {}
    if not team_id:
        return titulares

    url = ESPN_DEPTHCHART_URL_TPL.format(team_id=team_id)
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
        )
        if resp.status_code != 200:
            return titulares
        data = resp.json()
        items = data.get("depthchart", []) or data.get("items", []) or []

        def _extraer_nombre_ath(ath_raw: Any) -> str:
            if isinstance(ath_raw, dict) and "athlete" in ath_raw:
                ath_raw = ath_raw["athlete"]
            if not isinstance(ath_raw, dict):
                return ""
            return str(ath_raw.get("displayName") or ath_raw.get("shortName") or "").strip()

        wrs_candidatos_2nd: List[str] = []
        for block in items:
            positions = block.get("positions", {}) or {}
            for pos_key, pos_obj in positions.items():
                pos_abbr = str(
                    (pos_obj.get("position") or {}).get("abbreviation")
                    or pos_obj.get("abbreviation")
                    or pos_key
                ).strip().upper()
                athletes = pos_obj.get("athletes", []) or []
                if not athletes:
                    continue

                p_name = _extraer_nombre_ath(athletes[0])
                if not p_name:
                    continue
                backup_name = _extraer_nombre_ath(athletes[1]) if len(athletes) > 1 else ""
                third_name = _extraer_nombre_ath(athletes[2]) if len(athletes) > 2 else ""

                if pos_abbr == "QB" and "QB1" not in titulares:
                    titulares["QB1"] = {"slot": "QB1", "pos": "QB", "player": p_name, "backup": backup_name}
                elif pos_abbr in {"RB", "HB"}:
                    if "RB1" not in titulares:
                        titulares["RB1"] = {"slot": "RB1", "pos": "RB", "player": p_name, "backup": backup_name}
                    if "RB2" not in titulares and backup_name and backup_name != p_name:
                        titulares["RB2"] = {"slot": "RB2", "pos": "RB", "player": backup_name, "backup": third_name}
                elif pos_abbr in {"WR", "WR1", "WR2", "WR3", "FL", "SE", "SWR"}:
                    wrs_actuales = {
                        titulares[k]["player"]
                        for k in ("WR1", "WR2", "WR3")
                        if k in titulares
                    }
                    if "WR1" not in titulares and p_name not in wrs_actuales:
                        titulares["WR1"] = {"slot": "WR1", "pos": "WR", "player": p_name, "backup": backup_name}
                    elif "WR2" not in titulares and p_name not in wrs_actuales:
                        titulares["WR2"] = {"slot": "WR2", "pos": "WR", "player": p_name, "backup": backup_name}
                    elif "WR3" not in titulares and p_name not in wrs_actuales:
                        titulares["WR3"] = {"slot": "WR3", "pos": "WR", "player": p_name, "backup": backup_name}
                    if backup_name and backup_name not in wrs_candidatos_2nd:
                        wrs_candidatos_2nd.append(backup_name)
                elif pos_abbr == "TE":
                    if "TE1" not in titulares:
                        titulares["TE1"] = {"slot": "TE1", "pos": "TE", "player": p_name, "backup": backup_name}
                    if "TE2" not in titulares and backup_name and backup_name != p_name:
                        titulares["TE2"] = {"slot": "TE2", "pos": "TE", "player": backup_name, "backup": third_name}
                elif pos_abbr in {"LT", "LG", "C", "RG", "RT"} and pos_abbr not in titulares:
                    titulares[pos_abbr] = {"slot": pos_abbr, "pos": pos_abbr, "player": p_name, "backup": backup_name}
                elif pos_abbr in {"CB", "LCB", "RCB"} and "CB1" not in titulares:
                    titulares["CB1"] = {"slot": "CB1", "pos": "CB", "player": p_name, "backup": backup_name}
                elif pos_abbr in {"DE", "LDE", "RDE", "EDGE", "OLB", "LOLB", "ROLB"} and "EDGE1" not in titulares:
                    titulares["EDGE1"] = {"slot": "EDGE1", "pos": pos_abbr, "player": p_name, "backup": backup_name}
                elif pos_abbr in {"MLB", "ILB", "LB", "MIKE", "WLB"} and "MLB1" not in titulares:
                    titulares["MLB1"] = {"slot": "MLB1", "pos": pos_abbr, "player": p_name, "backup": backup_name}

        # Si el Depth Chart de ESPN listó solo 1 o 2 columnas de WR, completar WR2/WR3 con los backups inmediatos
        for cand_wr in wrs_candidatos_2nd:
            wrs_ya = {titulares[k]["player"] for k in ("WR1", "WR2", "WR3") if k in titulares}
            if cand_wr in wrs_ya:
                continue
            if "WR2" not in titulares:
                titulares["WR2"] = {"slot": "WR2", "pos": "WR", "player": cand_wr, "backup": ""}
            elif "WR3" not in titulares:
                titulares["WR3"] = {"slot": "WR3", "pos": "WR", "player": cand_wr, "backup": ""}
    except Exception:
        pass
    return titulares


def consultar_clima_estadio_open_meteo(
    home_abbr: str,
    kickoff_iso: Optional[str] = None,
    timeout: int = 5,
) -> Dict[str, Any]:
    """
    Consulta la API gratuita de Open-Meteo para el estadio del equipo local:
    `https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=wind_speed_10m,precipitation_probability,temperature_2m`
    Si el estadio es 'OUTDOOR' y el viento supera 24 km/h (15 mph) o hay precipitación > 50%:
      - Aplica un ajuste bajista al Total proyectado (-2.5 a -4.5 puntos).
      - Reduce 'Pass_Rate' en un 6% (multiplicador 0.94).
      - Penaliza un 8% las yardas de pase en 'engine_props_nfl.py' (multiplicador 0.92).
    """
    std_home = normalizar_abbr_nfl(home_abbr)
    st_info = NFL_STADIUMS_COORDS.get(
        std_home,
        {"name": f"{std_home} Stadium", "lat": 39.0, "lon": -94.5, "roof": "OUTDOOR"},
    )
    roof = str(st_info.get("roof", "OUTDOOR")).upper()
    st_name = str(st_info.get("name", f"{std_home} Stadium"))

    if roof == "DOME":
        return {
            "home_abbr": std_home,
            "stadium": st_name,
            "roof": "DOME",
            "temp_c": 21.0,
            "temp_f": 70.0,
            "wind_kmh": 0.0,
            "wind_mph": 0.0,
            "precip_prob": 0.0,
            "clima_adverso": False,
            "ajuste_total_pts": 0.0,
            "pass_rate_multiplier": 1.0,
            "pass_yds_multiplier": 1.0,
            "resumen_clima": f"Domo ({st_name} · 70°F)",
        }

    lat = float(st_info["lat"])
    lon = float(st_info["lon"])
    temp_c = 15.0
    wind_kmh = 11.0
    precip_prob = 10.0

    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "wind_speed_10m,precipitation_probability,temperature_2m",
            "forecast_days": 7,
            "timezone": "UTC",
        }
        resp = requests.get(OPEN_METEO_FORECAST_URL, params=params, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            hourly = data.get("hourly", {}) or {}
            times = hourly.get("time", []) or []
            winds = hourly.get("wind_speed_10m", []) or []
            precips = hourly.get("precipitation_probability", []) or []
            temps = hourly.get("temperature_2m", []) or []

            idx_sel = 0
            if kickoff_iso and times:
                target_prefix = str(kickoff_iso)[:13]
                for i, t_str in enumerate(times):
                    if str(t_str).startswith(target_prefix):
                        idx_sel = i
                        break
            elif times:
                idx_sel = min(18, len(times) - 1)

            if idx_sel < len(winds) and winds[idx_sel] is not None:
                wind_kmh = float(winds[idx_sel])
            if idx_sel < len(precips) and precips[idx_sel] is not None:
                precip_prob = float(precips[idx_sel])
            if idx_sel < len(temps) and temps[idx_sel] is not None:
                temp_c = float(temps[idx_sel])
    except Exception:
        pass

    wind_mph = round(wind_kmh * 0.621371, 1)
    temp_f = round((temp_c * 9.0 / 5.0) + 32.0, 1)

    clima_adverso = (wind_kmh > 24.0) or (precip_prob > 50.0)
    if clima_adverso:
        exceso_viento = max(0.0, (wind_kmh - 24.0) / 10.0)
        exceso_lluvia = max(0.0, (precip_prob - 50.0) / 25.0)
        severidad = min(1.0, 0.45 * exceso_viento + 0.55 * exceso_lluvia)
        ajuste_total_pts = -round(2.5 + 2.0 * severidad, 2)  # Entre -2.5 y -4.5 puntos
        pass_rate_mult = 0.94  # Reduce Pass_Rate en un 6%
        pass_yds_mult = 0.92   # Penaliza un 8% las yardas de pase en engine_props_nfl.py
        alerta_tag = " ⚠️ Viento/Lluvia"
    else:
        ajuste_total_pts = 0.0
        pass_rate_mult = 1.0
        pass_yds_mult = 1.0
        alerta_tag = ""

    resumen_clima = (
        f"Abierto · {temp_f:.0f}°F ({temp_c:.0f}°C) · Viento {wind_mph:.0f} mph "
        f"({wind_kmh:.0f} km/h) · Lluvia {precip_prob:.0f}%{alerta_tag}"
    )

    return {
        "home_abbr": std_home,
        "stadium": st_name,
        "roof": "OUTDOOR",
        "temp_c": round(temp_c, 1),
        "temp_f": temp_f,
        "wind_kmh": round(wind_kmh, 1),
        "wind_mph": wind_mph,
        "precip_prob": round(precip_prob, 1),
        "clima_adverso": bool(clima_adverso),
        "ajuste_total_pts": ajuste_total_pts,
        "pass_rate_multiplier": pass_rate_mult,
        "pass_yds_multiplier": pass_yds_mult,
        "resumen_clima": resumen_clima,
    }


consultar_clima_open_meteo_estadio = consultar_clima_estadio_open_meteo


def _clave_jugador_sin_equipo(player_name: str) -> str:
    """
    Genera una clave canónica independiente del equipo (Inicial + Apellido, ej. 'D_ADAMS')
    para detectar cuando un jugador de 'NFL_Stats' o 'Player_Props_Baseline' cambió de
    franquicia o fue cortado ('FA') en los rosters en vivo de ESPN.
    """
    limpio = _limpiar_nombre_jugador(player_name)
    partes = limpio.split()
    if not partes:
        return "UNK"
    if len(partes) == 1:
        return partes[0]
    return f"{partes[0][0]}_{partes[-1]}"


def consultar_roster_equipo_espn(team_abbr: str, timeout: int = 5) -> List[Dict[str, str]]:
    """
    Consulta el roster vivo oficial de ESPN para una franquicia:
    'https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/roster'
    Retorna la lista de jugadores activos/en plantilla del equipo.
    """
    std_abbr = normalizar_abbr_nfl(team_abbr)
    team_id = ESPN_TEAM_IDS.get(std_abbr)
    jugadores_roster: List[Dict[str, str]] = []
    if not team_id:
        return jugadores_roster

    url = ESPN_ROSTER_URL_TPL.format(team_id=team_id)
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
        )
        if resp.status_code != 200:
            return jugadores_roster
        data = resp.json()
        grupos = data.get("athletes", []) or []
        for grp in grupos:
            items = grp.get("items", []) if isinstance(grp, dict) else []
            if not items and isinstance(grp, dict) and ("displayName" in grp or "fullName" in grp):
                items = [grp]
            for ath in items:
                if not isinstance(ath, dict):
                    continue
                disp_name = str(ath.get("displayName") or ath.get("fullName") or ath.get("shortName") or "").strip()
                short_name = str(ath.get("shortName") or disp_name).strip()
                pos_abbr = str((ath.get("position") or {}).get("abbreviation", "")).strip().upper()
                status_obj = ath.get("status") or {}
                status_type = str(
                    status_obj.get("type") or status_obj.get("name") or status_obj.get("abbreviation") or "Active"
                ).strip()
                if disp_name:
                    jugadores_roster.append(
                        {
                            "team": std_abbr,
                            "player": disp_name,
                            "short_name": short_name,
                            "pos": pos_abbr,
                            "status": status_type,
                            "player_key": _clave_jugador_sin_equipo(disp_name),
                            "full_clean": _limpiar_nombre_jugador(disp_name),
                        }
                    )
    except Exception:
        pass
    return jugadores_roster


def consultar_transacciones_espn_nfl(timeout: int = 6) -> List[Dict[str, Any]]:
    """
    Consulta el feed oficial de transacciones de ESPN NFL:
    'https://site.api.espn.com/apis/site/v2/sports/football/nfl/transactions'
    Filtra e IGNORA movimientos de 'practice squad', 'futures' o relleno, conservando
    únicamente trades o firmas/cortes relevantes de primer equipo.
    """
    transacciones: List[Dict[str, Any]] = []
    patrones_relleno = (
        "practice squad",
        "reserve/future",
        "futures contract",
        "standard elevation",
        "reverted to practice",
        "signed to practice",
        "waived/injured",
        "workout",
        "try out",
    )
    try:
        resp = requests.get(
            ESPN_TRANSACTIONS_URL,
            timeout=timeout,
            headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
        )
        if resp.status_code != 200:
            return transacciones
        data = resp.json()
        raw_list = data.get("transactions", []) or data.get("items", []) or []
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            team_obj = item.get("team", {}) or {}
            raw_abbr = str(team_obj.get("abbreviation") or "").strip().upper()
            std_abbr = normalizar_abbr_nfl(raw_abbr) if raw_abbr else ""
            desc = str(item.get("description") or item.get("text") or "").strip()
            date_str = str(item.get("date") or "").strip()
            if not desc:
                continue

            desc_low = desc.lower()
            # Ignorar estrictamente movimientos de practice squad o contratos de reserva
            if any(p_ign in desc_low for p_ign in patrones_relleno):
                continue

            if "trade" in desc_low or "acquired" in desc_low:
                tipo_tx = "TRADE"
            elif any(w in desc_low for w in ("released", "waived", "cut", "terminated")):
                tipo_tx = "CORTE_FA"
            elif any(w in desc_low for w in ("signed", "claimed", "activated")):
                tipo_tx = "FIRMA_ALTA"
            else:
                continue

            transacciones.append(
                {
                    "team": std_abbr,
                    "date": date_str,
                    "type": tipo_tx,
                    "description": desc,
                }
            )
    except Exception:
        pass
    return transacciones


def sincronizar_traspasos_y_movimientos_roster_nfl(
    excel_path: str = DEFAULT_EXCEL_STATS_PATH,
    guardar_excel: bool = True,
) -> Dict[str, Any]:
    """
    1. DETECCIÓN DE TRASPASOS Y MOVIMIENTOS DE ROSTER:
       - Consulta los rosters vivos de ESPN ('teams/{team_id}/roster') para las 32 franquicias
         y el feed de transacciones ('transactions').
       - Cruza los jugadores registrados en 'NFL_Stats' y 'Player_Props_Baseline' contra los
         rosters actuales: si un jugador de impacto cambió de equipo ('Equipo_Prev' != 'Equipo_Actual')
         o fue cortado ('FA'), lo guarda en 'nfl_roster_moves.json' y actualiza/crea la pestaña
         'Roster_Moves' en 'nfl_stats1.xlsx'.
    """
    ts_cst = datetime.now(CST_TZ).strftime("%Y-%m-%d %H:%M:%S CST")
    qb_base_map, df_props_base = _cargar_baseline_jugadores_excel(excel_path)
    transacciones_espn = consultar_transacciones_espn_nfl()

    # Consultar los 32 rosters vivos de ESPN
    rosters_por_equipo: Dict[str, List[Dict[str, str]]] = {}
    indice_global_nombre_exacto: Dict[str, List[Dict[str, str]]] = {}
    indice_global_clave_pos: Dict[Tuple[str, str], List[Dict[str, str]]] = {}
    indice_global_clave: Dict[str, List[Dict[str, str]]] = {}

    for std_abbr in sorted(ESPN_TEAM_IDS.keys()):
        r_list = consultar_roster_equipo_espn(std_abbr)
        rosters_por_equipo[std_abbr] = r_list
        for p_item in r_list:
            f_clean = p_item["full_clean"]
            p_key = p_item["player_key"]
            p_grp = _clasificar_grupo_posicion(p_item["pos"])
            indice_global_nombre_exacto.setdefault(f_clean, []).append(p_item)
            indice_global_clave_pos.setdefault((p_key, p_grp), []).append(p_item)
            indice_global_clave.setdefault(p_key, []).append(p_item)

    # Construir lista unificada de jugadores base desde 'NFL_Stats' y 'Player_Props_Baseline'
    jugadores_base: List[Dict[str, Any]] = []
    vistos_base: Set[str] = set()

    if not df_props_base.empty:
        for _, row in df_props_base.iterrows():
            t_prev = normalizar_abbr_nfl(str(row.get("Team", "")).strip())
            p_name = str(row.get("Player", "")).strip()
            p_pos = str(row.get("Pos", "WR")).strip().upper()
            if not t_prev or not p_name:
                continue
            uid = f"{t_prev}_{_clave_jugador_sin_equipo(p_name)}_{p_pos}"
            if uid in vistos_base:
                continue
            vistos_base.add(uid)
            jugadores_base.append(
                {
                    "Equipo_Prev": t_prev,
                    "Player": p_name,
                    "Pos": p_pos,
                    "Role_Share": float(row.get("Role_Share", 0.22) or 0.22),
                    "Catch_Rate": float(row.get("Catch_Rate", 0.65) or 0.65),
                    "Yds_Per_Unit": float(row.get("Yds_Per_Unit", 7.5) or 7.5),
                    "Baseline_Yds": float(row.get("Baseline_Yds", 45.0) or 45.0),
                    "TD_Rate": float(row.get("TD_Rate", 0.20) or 0.20),
                }
            )

    for t_prev, qb_nm in qb_base_map.items():
        uid = f"{t_prev}_{_clave_jugador_sin_equipo(qb_nm)}_QB"
        if uid not in vistos_base and qb_nm:
            vistos_base.add(uid)
            jugadores_base.append(
                {
                    "Equipo_Prev": t_prev,
                    "Player": qb_nm,
                    "Pos": "QB",
                    "Role_Share": 1.0,
                    "Catch_Rate": 0.65,
                    "Yds_Per_Unit": 7.4,
                    "Baseline_Yds": 225.0,
                    "TD_Rate": 1.5,
                }
            )

    # Verificar si los rosters vivos de ESPN devolvieron datos reales (al menos 16 equipos con jugadores)
    equipos_con_roster_vivo = sum(1 for v in rosters_por_equipo.values() if len(v) > 0)
    movimientos_detectados: List[Dict[str, Any]] = []
    por_equipo_prev: Dict[str, List[Dict[str, Any]]] = {}
    por_equipo_actual: Dict[str, List[Dict[str, Any]]] = {}
    resumen_por_equipo: Dict[str, List[str]] = {abbr: [] for abbr in ESPN_TEAM_IDS.keys()}

    if equipos_con_roster_vivo >= 16:
        for jb in jugadores_base:
            t_prev = jb["Equipo_Prev"]
            p_name = jb["Player"]
            p_pos = jb["Pos"]
            p_grp = _clasificar_grupo_posicion(p_pos)
            p_key = _clave_jugador_sin_equipo(p_name)
            f_clean = _limpiar_nombre_jugador(p_name)

            # 1) ¿Sigue en el roster de su Equipo_Prev?
            roster_prev = rosters_por_equipo.get(t_prev, [])
            sigue_en_prev = any(
                (r["full_clean"] == f_clean)
                or (r["player_key"] == p_key and _clasificar_grupo_posicion(r["pos"]) == p_grp)
                for r in roster_prev
            )
            if sigue_en_prev:
                continue

            # 2) Buscar en los rosters del resto de las franquicias NFL
            candidatos = indice_global_nombre_exacto.get(f_clean, [])
            if not candidatos:
                candidatos = indice_global_clave_pos.get((p_key, p_grp), [])

            otros_equipos = [c for c in candidatos if c["team"] != t_prev]
            if len(otros_equipos) == 1:
                nuevo_item = otros_equipos[0]
                t_actual = nuevo_item["team"]
                tipo_mov = "TRASPASO_NUEVO_EQUIPO"
                factor_adap = NEW_TEAM_ADAPTATION_FACTOR
                detalle_tx = f"Detectado en roster vivo ESPN de {t_actual} (antes {t_prev})"
            elif len(otros_equipos) > 1:
                # Si hay colisión de inicial+apellido en la misma posición, verificar transacciones ESPN
                apellido_b = f_clean.split()[-1] if f_clean.split() else ""
                match_tx = None
                for cand in otros_equipos:
                    for tx in transacciones_espn:
                        if apellido_b and apellido_b in tx["description"].upper() and tx["team"] == cand["team"]:
                            match_tx = cand
                            break
                if match_tx is not None:
                    t_actual = match_tx["team"]
                    tipo_mov = "TRASPASO_NUEVO_EQUIPO"
                    factor_adap = NEW_TEAM_ADAPTATION_FACTOR
                    detalle_tx = f"Confirmado por Roster + Transacción ESPN en {t_actual} (antes {t_prev})"
                else:
                    continue
            else:
                # No figura en ningún roster activo de las 32 franquicias -> Cortado / Agente Libre ('FA')
                if not roster_prev:
                    continue
                t_actual = "FA"
                tipo_mov = "CORTE_FA"
                factor_adap = 0.0
                detalle_tx = f"Fuera del roster activo de {t_prev} (Agente Libre / FA)"

            reg_mov = {
                "Timestamp_CST": ts_cst,
                "Player": p_name,
                "Pos": p_pos,
                "Equipo_Prev": t_prev,
                "Equipo_Actual": t_actual,
                "Tipo_Movimiento": tipo_mov,
                "Factor_Adaptacion": factor_adap,
                "Role_Share_Base": round(float(jb["Role_Share"]), 3),
                "Baseline_Yds": round(float(jb["Baseline_Yds"]), 1),
                "Catch_Rate": round(float(jb["Catch_Rate"]), 3),
                "Yds_Per_Unit": round(float(jb["Yds_Per_Unit"]), 2),
                "TD_Rate": round(float(jb["TD_Rate"]), 3),
                "Detalle_ESPN": detalle_tx,
                "player_key": p_key,
            }
            movimientos_detectados.append(reg_mov)
            por_equipo_prev.setdefault(t_prev, []).append(reg_mov)
            if t_actual != "FA":
                por_equipo_actual.setdefault(t_actual, []).append(reg_mov)
                resumen_por_equipo.setdefault(t_actual, []).append(
                    f"Alta: {p_name} ({p_pos}, ex-{t_prev} · 85%)"
                )
                resumen_por_equipo.setdefault(t_prev, []).append(
                    f"Baja: {p_name} ({p_pos} -> {t_actual})"
                )
            else:
                resumen_por_equipo.setdefault(t_prev, []).append(
                    f"Baja: {p_name} ({p_pos} -> FA)"
                )

    # En 'TRASPASOS', mostrar únicamente trades o firmas relevantes que afecten a
    # QB1, WR1-WR3, RB1-RB2, TE1-TE2 o titulares defensivos clave (sin relleno de practice squad)
    apellidos_impacto = {
        _limpiar_nombre_jugador(jb["Player"]).split()[-1]
        for jb in jugadores_base
        if _limpiar_nombre_jugador(jb["Player"]).split()
    }
    for tx in transacciones_espn[:30]:
        t_tx = tx.get("team", "")
        desc_up = tx.get("description", "").upper()
        es_relevante_impacto = (
            tx.get("type") == "TRADE"
            or any(ap in desc_up for ap in apellidos_impacto if len(ap) >= 4)
        )
        if t_tx and es_relevante_impacto:
            desc_corta = tx["description"]
            if len(desc_corta) > 74:
                desc_corta = desc_corta[:71] + "..."
            if len(resumen_por_equipo.get(t_tx, [])) < 2:
                etiqueta_tx = f"{tx['type']}: {desc_corta}"
                if etiqueta_tx not in resumen_por_equipo.setdefault(t_tx, []):
                    resumen_por_equipo[t_tx].append(etiqueta_tx)

    payload_moves = {
        "timestamp_cst": ts_cst,
        "new_team_adaptation_factor": NEW_TEAM_ADAPTATION_FACTOR,
        "total_moves": len(movimientos_detectados),
        "moves": movimientos_detectados,
        "by_prev_team": por_equipo_prev,
        "by_current_team": por_equipo_actual,
        "summary_by_team": resumen_por_equipo,
        "recent_espn_transactions": transacciones_espn[:50],
    }

    with open(ROSTER_MOVES_JSON_PATH, "w", encoding="utf-8") as f_rm:
        json.dump(payload_moves, f_rm, ensure_ascii=False, indent=2)

    if guardar_excel:
        filas_rm_excel = [
            {col: m.get(col, "") for col in ROSTER_MOVES_COLUMNS}
            for m in movimientos_detectados
        ]
        df_rm_sheet = pd.DataFrame(filas_rm_excel, columns=ROSTER_MOVES_COLUMNS)
        _actualizar_hoja_excel_seguro(
            excel_path=excel_path,
            sheet_name="Roster_Moves",
            df_new=df_rm_sheet,
            append=False,
        )

    return payload_moves


def cargar_traspasos_roster_nfl(forzar_sync: bool = False) -> Dict[str, Any]:
    """
    Carga 'nfl_roster_moves.json' si existe; de lo contrario ejecuta
    'sincronizar_traspasos_y_movimientos_roster_nfl'.
    """
    if not forzar_sync and os.path.exists(ROSTER_MOVES_JSON_PATH):
        try:
            with open(ROSTER_MOVES_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "moves" in data:
                return data
        except Exception:
            pass
    return sincronizar_traspasos_y_movimientos_roster_nfl()


def _cargar_baseline_jugadores_excel(excel_path: str = DEFAULT_EXCEL_STATS_PATH) -> Tuple[Dict[str, str], pd.DataFrame]:
    """
    Lee 'NFL_Stats' y 'Player_Props_Baseline' desde 'nfl_stats1.xlsx' para conocer
    los titulares base del modelo y cruzarlos con ESPN.
    """
    qb_por_equipo: Dict[str, str] = {}
    df_props = pd.DataFrame()
    if not os.path.exists(excel_path):
        return qb_por_equipo, df_props

    try:
        xl = pd.ExcelFile(excel_path)
        if "NFL_Stats" in xl.sheet_names:
            df_st = pd.read_excel(xl, sheet_name="NFL_Stats")
            for _, r in df_st.iterrows():
                t = normalizar_abbr_nfl(str(r.get("Team_Abbr", "")))
                qb = str(r.get("QB_Name", "")).strip()
                if t and qb:
                    qb_por_equipo[t] = qb
        if "Player_Props_Baseline" in xl.sheet_names:
            df_props = pd.read_excel(xl, sheet_name="Player_Props_Baseline")
    except Exception:
        pass
    return qb_por_equipo, df_props


def sincronizar_lesiones_titulares_y_clima_nfl(
    semana: Optional[int] = None,
    excel_path: str = DEFAULT_EXCEL_STATS_PATH,
    incluir_depth_charts: bool = True,
    guardar_excel: bool = True,
) -> Dict[str, Any]:
    """
    Ejecuta la sincronización integral:
      1. Carga el snapshot previo de 'nfl_injuries_live.json' para detectar 'RECIEN_ACTIVADO'.
      2. Consulta 'injuries', 'scoreboard' + 'summary?event={event_id}', 'depthcharts',
         'roster' y 'transactions' en ESPN.
      3. Clasifica el estatus exacto ('ACTIVO_CONFIRMADO', 'RECIEN_ACTIVADO', 'QUESTIONABLE_GTD',
         'OUT_INACTIVO') para QB1, RB1, WR1, WR2, TE1, LT, LG, C, RG, RT, CB1, EDGE1 y MLB1.
      4. Detecta traspasos y cortes ('nfl_roster_moves.json' y pestaña 'Roster_Moves').
      5. Consulta Open-Meteo para todos los partidos de la jornada.
      6. Guarda 'nfl_injuries_live.json', 'nfl_starters_verified.json' y actualiza las hojas
         'Injuries_Live' y 'Roster_Moves' en 'nfl_stats1.xlsx' con timestamp en CST.
    """
    ts_cst = datetime.now(CST_TZ).strftime("%Y-%m-%d %H:%M:%S CST")
    snapshot_prev = cargar_snapshot_previo_lesiones(INJURIES_JSON_PATH)
    bajas_previas_map = _extraer_bajas_previas_por_clave(snapshot_prev)

    qb_base_map, df_props_base = _cargar_baseline_jugadores_excel(excel_path)
    roster_moves_payload = sincronizar_traspasos_y_movimientos_roster_nfl(
        excel_path=excel_path,
        guardar_excel=guardar_excel,
    )
    moves_by_prev = roster_moves_payload.get("by_prev_team", {}) or {}
    moves_by_curr = roster_moves_payload.get("by_current_team", {}) or {}
    moves_summary_map = roster_moves_payload.get("summary_by_team", {}) or {}

    # 1. Consultar calendario de la jornada y extraer event_ids
    partidos_semana = obtener_calendario_nfl_semana(semana=semana)
    equipos_en_jornada: Set[str] = set()
    inactivos_eventos: Dict[str, List[Dict[str, str]]] = {}
    clima_por_partido: Dict[str, Dict[str, Any]] = {}

    for p in partidos_semana:
        aw = normalizar_abbr_nfl(str(p.get("away_abbr", "")))
        hm = normalizar_abbr_nfl(str(p.get("home_abbr", "")))
        ev_id = str(p.get("id_partido", ""))
        equipos_en_jornada.update([aw, hm])

        ev_inact = consultar_inactivos_evento_espn(ev_id)
        for k_t, lista_i in ev_inact.items():
            inactivos_eventos.setdefault(k_t, []).extend(lista_i)

        match_key = f"{aw} @ {hm}"
        clima_por_partido[match_key] = consultar_clima_estadio_open_meteo(
            home_abbr=hm,
            kickoff_iso=str(p.get("fecha_iso", "")),
        )

    # 2. Consultar endpoint global de lesiones de ESPN
    lesiones_por_equipo: Dict[str, List[Dict[str, Any]]] = {
        abbr: [] for abbr in ESPN_TEAM_IDS.keys()
    }
    claves_lesionados_actuales: Dict[str, Dict[str, Any]] = {}

    try:
        resp_inj = requests.get(
            ESPN_INJURIES_URL,
            timeout=8,
            headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
        )
        if resp_inj.status_code == 200:
            data_inj = resp_inj.json()
            for team_block in data_inj.get("injuries", []) or []:
                team_info = team_block.get("team", {}) or {}
                raw_abbr = str(team_info.get("abbreviation") or "").strip().upper()
                std_abbr = normalizar_abbr_nfl(raw_abbr)
                if not std_abbr:
                    continue

                for item in team_block.get("injuries", []) or []:
                    ath = item.get("athlete", {}) or {}
                    p_name = str(ath.get("displayName") or ath.get("shortName") or "").strip()
                    p_short = str(ath.get("shortName") or p_name).strip()
                    p_pos = str((ath.get("position") or {}).get("abbreviation", "")).strip().upper()
                    raw_status = str(item.get("status", "")).strip()
                    short_comment = str(item.get("shortComment", "")).strip()
                    if not p_name:
                        continue

                    status_code = _mapear_estatus_espn(raw_status, short_comment)
                    pos_group = _clasificar_grupo_posicion(p_pos)
                    k_can = _clave_canonica_jugador(std_abbr, p_name)

                    reg_inj = {
                        "team": std_abbr,
                        "player": p_name,
                        "short_name": p_short,
                        "pos": p_pos,
                        "pos_group": pos_group,
                        "raw_status": raw_status,
                        "status_code": status_code,
                        "comment": short_comment,
                        "canonical_key": k_can,
                        "timestamp_cst": ts_cst,
                    }
                    lesiones_por_equipo.setdefault(std_abbr, []).append(reg_inj)
                    claves_lesionados_actuales[k_can] = reg_inj
    except Exception:
        pass

    # Fusionar inactivos oficiales del resumen de partido (90 min antes del kickoff)
    for std_abbr, lista_ev in inactivos_eventos.items():
        for ev_item in lista_ev:
            p_name = ev_item["player"]
            k_can = _clave_canonica_jugador(std_abbr, p_name)
            if k_can not in claves_lesionados_actuales:
                status_code = _mapear_estatus_espn(ev_item["status"])
                reg_ev = {
                    "team": std_abbr,
                    "player": p_name,
                    "short_name": p_name,
                    "pos": ev_item["pos"],
                    "pos_group": _clasificar_grupo_posicion(ev_item["pos"]),
                    "raw_status": ev_item["status"],
                    "status_code": status_code,
                    "comment": ev_item.get("source", "event_summary"),
                    "canonical_key": k_can,
                    "timestamp_cst": ts_cst,
                }
                lesiones_por_equipo.setdefault(std_abbr, []).append(reg_ev)
                claves_lesionados_actuales[k_can] = reg_ev

    # 3. Consultar Depth Charts y verificar titulares #1 + detectar RECIEN_ACTIVADO
    equipos_a_consultar = equipos_en_jornada if equipos_en_jornada else set(ESPN_TEAM_IDS.keys())
    starters_por_equipo: Dict[str, Dict[str, Any]] = {}
    filas_excel_injuries: List[Dict[str, Any]] = []

    for std_abbr in sorted(ESPN_TEAM_IDS.keys()):
        dc_map: Dict[str, Dict[str, str]] = {}
        if incluir_depth_charts and std_abbr in equipos_a_consultar:
            dc_map = consultar_depth_chart_equipo_espn(std_abbr)

        # Completar con baseline de Excel si algún puesto ofensivo no vino en el Depth Chart
        qb_base = qb_base_map.get(std_abbr, f"{std_abbr} QB1")
        if "QB1" not in dc_map:
            dc_map["QB1"] = {"slot": "QB1", "pos": "QB", "player": qb_base, "backup": ""}

        if not df_props_base.empty:
            df_t_base = df_props_base[
                df_props_base["Team"].astype(str).str.upper().isin({std_abbr, "LAR" if std_abbr == "LA" else std_abbr, "WSH" if std_abbr == "WAS" else std_abbr})
            ]
            rbs_b = df_t_base[df_t_base["Pos"].astype(str).str.upper().str.startswith("RB")]
            wrs_b = df_t_base[df_t_base["Pos"].astype(str).str.upper().str.startswith("WR")]
            tes_b = df_t_base[df_t_base["Pos"].astype(str).str.upper().str.startswith("TE")]

            if "RB1" not in dc_map and not rbs_b.empty:
                dc_map["RB1"] = {"slot": "RB1", "pos": "RB", "player": str(rbs_b.iloc[0]["Player"]), "backup": ""}
            if "RB2" not in dc_map and len(rbs_b) > 1:
                dc_map["RB2"] = {"slot": "RB2", "pos": "RB", "player": str(rbs_b.iloc[1]["Player"]), "backup": ""}
            if "WR1" not in dc_map and not wrs_b.empty:
                dc_map["WR1"] = {"slot": "WR1", "pos": "WR", "player": str(wrs_b.iloc[0]["Player"]), "backup": ""}
            if "WR2" not in dc_map and len(wrs_b) > 1:
                dc_map["WR2"] = {"slot": "WR2", "pos": "WR", "player": str(wrs_b.iloc[1]["Player"]), "backup": ""}
            if "WR3" not in dc_map and len(wrs_b) > 2:
                dc_map["WR3"] = {"slot": "WR3", "pos": "WR", "player": str(wrs_b.iloc[2]["Player"]), "backup": ""}
            if "TE1" not in dc_map and not tes_b.empty:
                dc_map["TE1"] = {"slot": "TE1", "pos": "TE", "player": str(tes_b.iloc[0]["Player"]), "backup": ""}
            if "TE2" not in dc_map and len(tes_b) > 1:
                dc_map["TE2"] = {"slot": "TE2", "pos": "TE", "player": str(tes_b.iloc[1]["Player"]), "backup": ""}

        # Mapa de jugadores recién llegados por traspaso/firma a este equipo
        altas_trasp_keys = {
            _clave_jugador_sin_equipo(str(m.get("Player", "")))
            for m in (moves_by_curr.get(std_abbr, []) or [])
        }

        titulares_clasificados: Dict[str, Dict[str, Any]] = {}
        rotacion_ofensiva_8: Dict[str, Dict[str, Any]] = {}
        recien_activados_equipo: List[str] = []
        candidatos_bajas_impacto: List[Dict[str, Any]] = []

        ol_out_count = 0
        def_out_count = 0
        qb1_out_or_replaced = False
        wr1_te1_out_shares: List[str] = []
        rb1_out = False

        for slot in CRITICAL_POSITIONS_ORDER:
            slot_info = dc_map.get(slot, {"slot": slot, "pos": slot.rstrip("123"), "player": f"{std_abbr} {slot}", "backup": ""})
            p_name = str(slot_info.get("player", "")).strip()
            pos_str = str(slot_info.get("pos", slot.rstrip("123"))).strip().upper()
            k_can = _clave_canonica_jugador(std_abbr, p_name)
            p_key_notm = _clave_jugador_sin_equipo(p_name)

            inj_match = claves_lesionados_actuales.get(k_can)
            if inj_match is not None:
                st_exacto = str(inj_match["status_code"])
                raw_st = str(inj_match["raw_status"])
            else:
                if p_key_notm in altas_trasp_keys:
                    st_exacto = "TRASPASO_NUEVO"
                    raw_st = "New Trade/Signing Active"
                elif k_can in bajas_previas_map:
                    st_exacto = "RECIEN_ACTIVADO"
                    raw_st = f"Activated (Prev: {bajas_previas_map[k_can]['prev_status']})"
                else:
                    st_exacto = "ACTIVO_CONFIRMADO"
                    raw_st = "Active"

            # Si es QB1 y el Depth Chart tiene un titular distinto al QB1 base o está OUT/DOUBTFUL
            if slot == "QB1":
                k_qb_base = _clave_canonica_jugador(std_abbr, qb_base)
                if k_qb_base in claves_lesionados_actuales and claves_lesionados_actuales[k_qb_base]["status_code"] in {"OUT_INACTIVO", "DOUBTFUL"}:
                    qb1_out_or_replaced = True
                    if k_can == k_qb_base and slot_info.get("backup"):
                        p_name = str(slot_info["backup"])
                        k_can = _clave_canonica_jugador(std_abbr, p_name)
                        p_key_notm = _clave_jugador_sin_equipo(p_name)
                        st_exacto = "ACTIVO_CONFIRMADO"
                        raw_st = "Active (Backup promoted to QB1)"
                elif st_exacto in {"OUT_INACTIVO", "DOUBTFUL"}:
                    qb1_out_or_replaced = True
                    if slot_info.get("backup"):
                        bajas_qb1_orig = p_name
                        candidatos_bajas_impacto.append(
                            {
                                "priority": SLOT_IMPACT_PRIORITY.get("QB1", 1),
                                "player": bajas_qb1_orig,
                                "slot": "QB1",
                                "badge": "OUT",
                                "raw_status": raw_st,
                                "text": f"{bajas_qb1_orig} (QB1 - OUT)",
                            }
                        )
                        p_name = str(slot_info["backup"])
                        k_can = _clave_canonica_jugador(std_abbr, p_name)
                        p_key_notm = _clave_jugador_sin_equipo(p_name)
                        st_exacto = "ACTIVO_CONFIRMADO"
                        raw_st = "Active (Promoted QB1)"

            if st_exacto == "RECIEN_ACTIVADO" and slot in OFFENSIVE_ROTATION_SLOTS:
                recien_activados_equipo.append(f"{p_name} ({slot})")
            elif st_exacto in {"OUT_INACTIVO", "DOUBTFUL"}:
                candidatos_bajas_impacto.append(
                    {
                        "priority": SLOT_IMPACT_PRIORITY.get(slot, 20),
                        "player": p_name,
                        "slot": slot,
                        "badge": "OUT",
                        "raw_status": raw_st,
                        "text": f"{p_name} ({slot} - OUT)",
                    }
                )
                if slot in {"WR1", "WR2", "WR3", "TE1", "TE2"}:
                    wr1_te1_out_shares.append(p_name)
                elif slot in {"RB1", "RB2"}:
                    if slot == "RB1":
                        rb1_out = True
                elif slot in {"LT", "LG", "C", "RG", "RT"}:
                    ol_out_count += 1
                elif slot in {"CB1", "EDGE1", "MLB1"}:
                    def_out_count += 1
            elif st_exacto == "QUESTIONABLE_GTD":
                candidatos_bajas_impacto.append(
                    {
                        "priority": SLOT_IMPACT_PRIORITY.get(slot, 20) + 10,
                        "player": p_name,
                        "slot": slot,
                        "badge": "GTD",
                        "raw_status": raw_st,
                        "text": f"{p_name} ({slot} - GTD)",
                    }
                )

            slot_entry = {
                "slot": slot,
                "pos": pos_str,
                "player": p_name,
                "backup": slot_info.get("backup", ""),
                "status": st_exacto,
                "raw_status": raw_st,
                "canonical_key": k_can,
                "player_key": p_key_notm,
                "full_clean": _limpiar_nombre_jugador(p_name),
            }
            titulares_clasificados[slot] = slot_entry
            if slot in OFFENSIVE_ROTATION_SLOTS:
                rotacion_ofensiva_8[slot] = slot_entry

            filas_excel_injuries.append(
                {
                    "Timestamp_CST": ts_cst,
                    "Team": std_abbr,
                    "Slot": slot,
                    "Pos": pos_str,
                    "Player": p_name,
                    "Backup": slot_info.get("backup", ""),
                    "Status_Clasificado": st_exacto,
                    "ESPN_Raw_Status": raw_st,
                    "Source": "ESPN DepthChart + Injuries",
                }
            )

        # Ordenar bajas estrictamente por impacto (QB1 > WR1/RB1/TE1 > WR2/RB2/WR3/TE2/OL/CB1) y limitar a MÁXIMO 3 por equipo
        candidatos_bajas_impacto.sort(key=lambda x: x["priority"])
        top3_bajas_items = candidatos_bajas_impacto[:3]
        bajas_clave_equipo = [x["text"] for x in top3_bajas_items if x["badge"] == "OUT"]
        gtd_equipo = [x["text"] for x in top3_bajas_items if x["badge"] == "GTD"]

        qb1_slot = titulares_clasificados.get("QB1", {})
        qb1_nombre_real = str(qb1_slot.get("player", qb_base))
        qb1_tag = "NUEVO" if (qb1_out_or_replaced or qb1_slot.get("status") in {"RECIEN_ACTIVADO", "TRASPASO_NUEVO"}) else "TITULAR OK"

        starters_por_equipo[std_abbr] = {
            "team": std_abbr,
            "timestamp_cst": ts_cst,
            "qb1_name": qb1_nombre_real,
            "qb1_base": qb_base,
            "qb1_status": qb1_slot.get("status", "ACTIVO_CONFIRMADO"),
            "qb1_tag": qb1_tag,
            "qb1_out_or_replaced": bool(qb1_out_or_replaced),
            "rb1_out": bool(rb1_out),
            "wr1_te1_out_players": wr1_te1_out_shares,
            "ol_out_count": int(ol_out_count),
            "def_key_out_count": int(def_out_count),
            "recien_activados": recien_activados_equipo[:3],
            "bajas_out_doubtful": bajas_clave_equipo,
            "questionable_gtd": gtd_equipo,
            "bajas_top3_pills": top3_bajas_items,
            "traspasos_altas": moves_by_curr.get(std_abbr, []),
            "traspasos_bajas": moves_by_prev.get(std_abbr, []),
            "traspasos_resumen": (moves_summary_map.get(std_abbr, []) or [])[:2],
            "offensive_rotation": rotacion_ofensiva_8,
            "starters": titulares_clasificados,
            "titulares": [
                {
                    "slot": v["slot"],
                    "position": v["pos"],
                    "player_name": v["player"],
                    "status": v["status"],
                    "raw_espn_status": v["raw_status"],
                    "detail": v["raw_status"],
                    "recien_activado": v["status"] == "RECIEN_ACTIVADO",
                }
                for v in titulares_clasificados.values()
            ],
        }

    payload_injuries = {
        "timestamp_cst": ts_cst,
        "semana": semana or 10,
        "weather_by_matchup": clima_por_partido,
        "roster_moves": roster_moves_payload,
        "teams": {
            abbr: {
                "injuries": lesiones_por_equipo.get(abbr, []),
                "summary": starters_por_equipo.get(abbr, {}),
            }
            for abbr in sorted(ESPN_TEAM_IDS.keys())
        },
    }

    payload_starters = {
        "timestamp_cst": ts_cst,
        "semana": semana or 10,
        "weather_by_matchup": clima_por_partido,
        "clima_por_local": {
            normalizar_abbr_nfl(k.split("@")[-1].strip()): v
            for k, v in clima_por_partido.items()
            if "@" in k
        },
        "roster_moves": roster_moves_payload,
        "teams": starters_por_equipo,
        "equipos": starters_por_equipo,
    }

    with open(INJURIES_JSON_PATH, "w", encoding="utf-8") as f_inj:
        json.dump(payload_injuries, f_inj, ensure_ascii=False, indent=2)

    with open(STARTERS_JSON_PATH, "w", encoding="utf-8") as f_st:
        json.dump(payload_starters, f_st, ensure_ascii=False, indent=2)

    # 4. Actualizar/crear la pestaña 'Injuries_Live' en 'nfl_stats1.xlsx'
    if guardar_excel:
        df_inj_sheet = pd.DataFrame(filas_excel_injuries)
        _actualizar_hoja_excel_seguro(
            excel_path=excel_path,
            sheet_name="Injuries_Live",
            df_new=df_inj_sheet,
            append=False,
        )

    return payload_starters


def _actualizar_hoja_excel_seguro(
    excel_path: str,
    sheet_name: str,
    df_new: pd.DataFrame,
    append: bool = False,
) -> None:
    """
    Actualiza o crea una pestaña ('Injuries_Live' o 'Audit_Log') en 'nfl_stats1.xlsx'
    preservando intactas el resto de las hojas del libro.
    """
    if not os.path.exists(excel_path):
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            df_new.to_excel(writer, index=False, sheet_name=sheet_name)
        return

    try:
        xl = pd.ExcelFile(excel_path)
        hojas_existentes: Dict[str, pd.DataFrame] = {}
        for sh in xl.sheet_names:
            hojas_existentes[sh] = pd.read_excel(xl, sheet_name=sh)
        xl.close()

        if append and sheet_name in hojas_existentes and not hojas_existentes[sheet_name].empty:
            df_combinado = pd.concat([hojas_existentes[sheet_name], df_new], ignore_index=True)
            if sheet_name == "Audit_Log" and {"Semana", "Partido", "Equipo"}.issubset(df_combinado.columns):
                df_combinado = df_combinado.drop_duplicates(
                    subset=["Semana", "Partido", "Equipo"], keep="last"
                ).reset_index(drop=True)
            hojas_existentes[sheet_name] = df_combinado
        else:
            hojas_existentes[sheet_name] = df_new

        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            for sh_name, df_sh in hojas_existentes.items():
                df_sh.to_excel(writer, index=False, sheet_name=sh_name)
    except Exception as exc:
        print(f"[WARN] No se pudo actualizar la hoja '{sheet_name}' en '{excel_path}': {exc}")


def cargar_estado_titulares_y_clima(
    forzar_sync: bool = False,
    semana: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Carga 'nfl_starters_verified.json' si existe; si no existe o se pide forzar_sync,
    ejecuta 'sincronizar_lesiones_titulares_y_clima_nfl'.
    """
    if not forzar_sync and os.path.exists(STARTERS_JSON_PATH):
        try:
            with open(STARTERS_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data.get("teams"):
                return data
        except Exception:
            pass
    return sincronizar_lesiones_titulares_y_clima_nfl(semana=semana)


def obtener_bloque_estado_partido(
    away_abbr: str,
    home_abbr: str,
    estado_global: Optional[Dict[str, Any]] = None,
    starters_verified: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Construye las 4 líneas compactas de estado de plantilla, traspasos y entorno para un partido:
      - Línea 1: "QB1: [Nombre Visitante] [OK/NUEVO] vs [Nombre Local] [OK/NUEVO] | Clima: [Domo / Temp y Viento]"
      - Línea 2: "🔴 OUT / GTD: [Bajas relevantes de ambos equipos con posición]"
      - Línea 3: "🟢 ACTIVADOS: [Jugadores clave recién activados de IR/lesión para este juego, o 'Sin novedades']"
      - Línea 4: "🔄 TRASPASOS: [Altas/bajas recientes por trade o firma en ambos equipos, o 'Sin cambios']"
    """
    aw = normalizar_abbr_nfl(away_abbr)
    hm = normalizar_abbr_nfl(home_abbr)
    partido_key = f"{aw} @ {hm}"

    data = (
        estado_global
        if estado_global is not None
        else (starters_verified if starters_verified is not None else cargar_estado_titulares_y_clima(forzar_sync=False))
    )
    teams_map = (data or {}).get("teams", (data or {}).get("equipos", {})) or {}
    weather_map = (data or {}).get("weather_by_matchup", {}) or {}
    rm_global = (data or {}).get("roster_moves", {}) or {}
    rm_summary_map = rm_global.get("summary_by_team", {}) if isinstance(rm_global, dict) else {}

    aw_info = teams_map.get(aw, {}) or {}
    hm_info = teams_map.get(hm, {}) or {}

    qb_aw = str(aw_info.get("qb1_name") or f"{aw} QB1")
    tag_aw = str(aw_info.get("qb1_tag") or "TITULAR OK")
    if tag_aw == "OK":
        tag_aw = "TITULAR OK"
    qb_hm = str(hm_info.get("qb1_name") or f"{hm} QB1")
    tag_hm = str(hm_info.get("qb1_tag") or "TITULAR OK")
    if tag_hm == "OK":
        tag_hm = "TITULAR OK"

    clima_info = weather_map.get(partido_key)
    if not clima_info:
        clima_info = consultar_clima_estadio_open_meteo(hm)
    clima_str = str(clima_info.get("resumen_clima", "Domo"))
    roof_type = str(clima_info.get("roof", "OUTDOOR")).upper()
    if roof_type == "DOME" or "DOMO" in clima_str.upper():
        clima_pill = "🏟️ Domo · 70°F"
    else:
        t_f = float(clima_info.get("temp_f", 65.0))
        w_mph = float(clima_info.get("wind_mph", 8.0))
        alerta_w = " ⚠️" if clima_info.get("clima_adverso") else ""
        clima_pill = f"🌤️ {t_f:.0f}°F · 💨 {w_mph:.0f} mph{alerta_w}"

    linea_1 = f"QB1: {qb_aw} [{tag_aw}] vs {qb_hm} [{tag_hm}] | Clima: {clima_str}"

    # Máximo 3 bajas clave por equipo ordenadas por impacto (QB1 > WR1/RB1/TE1 > WR2/RB2/TE2/OL/CB1)
    pills_aw = (aw_info.get("bajas_top3_pills") or [])[:3]
    pills_hm = (hm_info.get("bajas_top3_pills") or [])[:3]
    bajas_aw = [f"{x['player']} ({x['slot']} - {x['badge']})" for x in pills_aw] if pills_aw else (
        (aw_info.get("bajas_out_doubtful", []) or []) + (aw_info.get("questionable_gtd", []) or [])
    )[:3]
    bajas_hm = [f"{x['player']} ({x['slot']} - {x['badge']})" for x in pills_hm] if pills_hm else (
        (hm_info.get("bajas_out_doubtful", []) or []) + (hm_info.get("questionable_gtd", []) or [])
    )[:3]

    partes_bajas = []
    if bajas_aw:
        partes_bajas.append(f"{aw}: {', '.join(bajas_aw[:3])}")
    if bajas_hm:
        partes_bajas.append(f"{hm}: {', '.join(bajas_hm[:3])}")
    bajas_str = " | ".join(partes_bajas) if partes_bajas else "Sin bajas titulares críticas"
    linea_2 = f"🔴 OUT / GTD: {bajas_str}"

    act_aw = (aw_info.get("recien_activados", []) or [])[:3]
    act_hm = (hm_info.get("recien_activados", []) or [])[:3]
    partes_act = []
    if act_aw:
        partes_act.append(f"{aw}: {', '.join(act_aw)}")
    if act_hm:
        partes_act.append(f"{hm}: {', '.join(act_hm)}")
    act_str = " | ".join(partes_act) if partes_act else "Sin novedades"
    linea_3 = f"🟢 ACTIVADOS: {act_str}"

    tr_aw = [
        x for x in ((aw_info.get("traspasos_resumen") or rm_summary_map.get(aw) or [])[:2])
        if "practice squad" not in str(x).lower()
    ]
    tr_hm = [
        x for x in ((hm_info.get("traspasos_resumen") or rm_summary_map.get(hm) or [])[:2])
        if "practice squad" not in str(x).lower()
    ]
    partes_tr = []
    if tr_aw:
        partes_tr.append(f"{aw}: {', '.join(tr_aw)}")
    if tr_hm:
        partes_tr.append(f"{hm}: {', '.join(tr_hm)}")
    traspasos_str = " | ".join(partes_tr) if partes_tr else "Sin movimientos relevantes"
    linea_4 = f"🔄 TRASPASOS: {traspasos_str}"

    return {
        "partido": partido_key,
        "clima_pill": clima_pill,
        "qb_away_name": qb_aw,
        "qb_away_tag": tag_aw,
        "qb_home_name": qb_hm,
        "qb_home_tag": tag_hm,
        "bajas_away_pills": pills_aw,
        "bajas_home_pills": pills_hm,
        "bajas_away_list": bajas_aw[:3],
        "bajas_home_list": bajas_hm[:3],
        "activados_reales": partes_act,
        "traspasos_reales": partes_tr,
        "hay_movimientos_reales": bool(partes_act or partes_tr),
        "linea_1_qb_clima": linea_1,
        "linea_2_out_gtd": linea_2,
        "linea_3_activados": linea_3,
        "linea_4_traspasos": linea_4,
        "clima": clima_info,
        "away_team_state": aw_info,
        "home_team_state": hm_info,
    }


def ejecutar_autocalibracion_post_jornada(
    semana: Optional[int] = None,
    excel_path: str = DEFAULT_EXCEL_STATS_PATH,
    learning_rate: float = 0.06,
) -> pd.DataFrame:
    """
    4. BUCLE DE AUTO-CALIBRACIÓN BAYESIANA Y PESTAÑA 'Audit_Log' EN EXCEL:
    Toma los marcadores finales de ESPN ('STATUS_FINAL' / finalizado=True), ejecuta la
    proyección previa del modelo, actualiza 'EPA_Pass_Off', 'EPA_Rush_Off',
    'EPA_Pass_Def' y 'EPA_Rush_Def' en 'nfl_stats1.xlsx', y guarda cada ajuste en
    la pestaña 'Audit_Log' en modo append con las columnas:
    ['Fecha', 'Semana', 'Partido', 'Marcador_Real', 'Proy_Spread', 'Error_Spread',
     'Proy_Total', 'Error_Total', 'Equipo', 'EPA_Off_Prev', 'EPA_Off_New',
     'EPA_Def_Prev', 'EPA_Def_New'].
    """
    from engine_nfl import (
        auditar_partido_nfl,
        calibrar_stats_nfl,
        obtener_stats_nfl_default,
        run_simulacion_nfl,
        validar_y_parsear_excel_nfl,
    )

    fecha_hoy = datetime.now(CST_TZ).strftime("%Y-%m-%d %H:%M CST")
    partidos = obtener_calendario_nfl_semana(semana=semana)
    finalizados = [p for p in partidos if p.get("finalizado", False)]

    if os.path.exists(excel_path):
        try:
            df_stats_orig = pd.read_excel(excel_path, sheet_name="NFL_Stats")
            nfl_stats = validar_y_parsear_excel_nfl(df_stats_orig)
        except Exception:
            df_stats_orig = pd.DataFrame()
            nfl_stats = obtener_stats_nfl_default()
    else:
        df_stats_orig = pd.DataFrame()
        nfl_stats = obtener_stats_nfl_default()

    filas_audit: List[Dict[str, Any]] = []
    if not finalizados:
        # Si aún no hay partidos finalizados en la semana actual, asegurar que la hoja Audit_Log exista
        if os.path.exists(excel_path):
            xl = pd.ExcelFile(excel_path)
            if "Audit_Log" in xl.sheet_names:
                return pd.read_excel(xl, sheet_name="Audit_Log")
        df_empty_log = pd.DataFrame(columns=AUDIT_LOG_COLUMNS)
        _actualizar_hoja_excel_seguro(excel_path, "Audit_Log", df_empty_log, append=True)
        return df_empty_log

    for p in finalizados:
        aw = normalizar_abbr_nfl(str(p.get("away_abbr", "")))
        hm = normalizar_abbr_nfl(str(p.get("home_abbr", "")))
        sem_p = int(p.get("semana", semana or 10))
        partido_lbl = f"{aw} @ {hm}"

        aw_st_prev = dict(nfl_stats.get(aw, {}))
        hm_st_prev = dict(nfl_stats.get(hm, {}))

        epa_off_prev_aw = round(
            0.58 * float(aw_st_prev.get("EPA_Pass_Off", 0.0)) + 0.42 * float(aw_st_prev.get("EPA_Rush_Off", 0.0)),
            4,
        )
        epa_def_prev_aw = round(
            0.58 * float(aw_st_prev.get("EPA_Pass_Def", 0.0)) + 0.42 * float(aw_st_prev.get("EPA_Rush_Def", 0.0)),
            4,
        )
        epa_off_prev_hm = round(
            0.58 * float(hm_st_prev.get("EPA_Pass_Off", 0.0)) + 0.42 * float(hm_st_prev.get("EPA_Rush_Off", 0.0)),
            4,
        )
        epa_def_prev_hm = round(
            0.58 * float(hm_st_prev.get("EPA_Pass_Def", 0.0)) + 0.42 * float(hm_st_prev.get("EPA_Rush_Def", 0.0)),
            4,
        )

        sim_prev = run_simulacion_nfl(
            away_abbr=aw,
            home_abbr=hm,
            nfl_stats_dict=nfl_stats,
            n_sims=5000,
            lineas_mercado={
                "total_mercado": p.get("total_mercado", 44.5),
                "spread_mercado_home": p.get("spread_mercado_home", -2.5),
            },
        )
        aud = auditar_partido_nfl(sim_prev, p)
        nfl_stats = calibrar_stats_nfl(
            nfl_stats_dict=nfl_stats,
            away_abbr=aw,
            home_abbr=hm,
            error_away=float(aud["error_away"]),
            error_home=float(aud["error_home"]),
            learning_rate=learning_rate,
            auditoria_info=aud,
        )

        aw_st_new = nfl_stats.get(aw, {})
        hm_st_new = nfl_stats.get(hm, {})

        epa_off_new_aw = round(
            0.58 * float(aw_st_new.get("EPA_Pass_Off", 0.0)) + 0.42 * float(aw_st_new.get("EPA_Rush_Off", 0.0)),
            4,
        )
        epa_def_new_aw = round(
            0.58 * float(aw_st_new.get("EPA_Pass_Def", 0.0)) + 0.42 * float(aw_st_new.get("EPA_Rush_Def", 0.0)),
            4,
        )
        epa_off_new_hm = round(
            0.58 * float(hm_st_new.get("EPA_Pass_Off", 0.0)) + 0.42 * float(hm_st_new.get("EPA_Rush_Off", 0.0)),
            4,
        )
        epa_def_new_hm = round(
            0.58 * float(hm_st_new.get("EPA_Pass_Def", 0.0)) + 0.42 * float(hm_st_new.get("EPA_Rush_Def", 0.0)),
            4,
        )

        marcador_real_str = f"{aw} {int(round(aud['puntos_away_real']))} - {int(round(aud['puntos_home_real']))} {hm}"

        filas_audit.append(
            {
                "Fecha": fecha_hoy,
                "Semana": sem_p,
                "Partido": partido_lbl,
                "Marcador_Real": marcador_real_str,
                "Proy_Spread": round(float(aud["spread_modelo"]), 1),
                "Error_Spread": round(float(aud["error_spread"]), 1),
                "Proy_Total": round(float(aud["total_modelo"]), 1),
                "Error_Total": round(float(aud["error_total"]), 1),
                "Equipo": aw,
                "EPA_Off_Prev": epa_off_prev_aw,
                "EPA_Off_New": epa_off_new_aw,
                "EPA_Def_Prev": epa_def_prev_aw,
                "EPA_Def_New": epa_def_new_aw,
            }
        )
        filas_audit.append(
            {
                "Fecha": fecha_hoy,
                "Semana": sem_p,
                "Partido": partido_lbl,
                "Marcador_Real": marcador_real_str,
                "Proy_Spread": round(float(aud["spread_modelo"]), 1),
                "Error_Spread": round(float(aud["error_spread"]), 1),
                "Proy_Total": round(float(aud["total_modelo"]), 1),
                "Error_Total": round(float(aud["error_total"]), 1),
                "Equipo": hm,
                "EPA_Off_Prev": epa_off_prev_hm,
                "EPA_Off_New": epa_off_new_hm,
                "EPA_Def_Prev": epa_def_prev_hm,
                "EPA_Def_New": epa_def_new_hm,
            }
        )

    # Actualizar hoja NFL_Stats en nfl_stats1.xlsx con los nuevos EPA calibrados
    if not df_stats_orig.empty and "Team_Abbr" in df_stats_orig.columns:
        df_stats_upd = df_stats_orig.copy()
        for idx_r, row_s in df_stats_upd.iterrows():
            t_ab = normalizar_abbr_nfl(str(row_s.get("Team_Abbr", "")))
            if t_ab in nfl_stats:
                for col_epa in ("EPA_Pass_Off", "EPA_Rush_Off", "EPA_Pass_Def", "EPA_Rush_Def", "Success_Rate_Off", "Success_Rate_Def", "Pace_Sec"):
                    if col_epa in df_stats_upd.columns and col_epa in nfl_stats[t_ab]:
                        df_stats_upd.at[idx_r, col_epa] = nfl_stats[t_ab][col_epa]
        _actualizar_hoja_excel_seguro(excel_path, "NFL_Stats", df_stats_upd, append=False)

    df_audit_new = pd.DataFrame(filas_audit, columns=AUDIT_LOG_COLUMNS)
    _actualizar_hoja_excel_seguro(excel_path, "Audit_Log", df_audit_new, append=True)
    return df_audit_new


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sincronizador de Lesiones, Depth Chart, Recién Activados, Clima Open-Meteo y Audit_Log NFL."
    )
    parser.add_argument("--week", type=int, default=None, help="Semana NFL opcional (1-18).")
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Ejecuta también el bucle de auto-calibración post-jornada y escribe en 'Audit_Log'.",
    )
    args = parser.parse_args()

    semana_env = os.environ.get("NFL_WEEK", "").strip()
    semana_val = args.week if args.week is not None else (int(semana_env) if semana_env.isdigit() else None)

    res = sincronizar_lesiones_titulares_y_clima_nfl(semana=semana_val)
    n_teams = len(res.get("teams", {}))
    n_weather = len(res.get("weather_by_matchup", {}))
    print(
        f"[SYNC INJURIES NFL] Completado ({res.get('timestamp_cst')}) | "
        f"Equipos auditados: {n_teams} | Estadios con clima Open-Meteo: {n_weather}"
    )

    if args.calibrate or os.environ.get("NFL_RUN_CALIBRATION", "").strip() == "1":
        df_log = ejecutar_autocalibracion_post_jornada(semana=semana_val)
        print(f"[AUDIT LOG NFL] Auto-calibración ejecutada | Registros generados: {len(df_log)}")


if __name__ == "__main__":
    main()
