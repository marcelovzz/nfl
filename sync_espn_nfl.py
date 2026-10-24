#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MÓDULO 1: sync_espn_nfl.py
Sincronización del calendario semanal de la NFL desde la API pública de ESPN
(Scoreboard API) y generación dinámica de escudos oficiales vía CDN.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import requests

ESPN_NFL_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
ESPN_NFL_LOGO_CDN = "https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png"

# Normalización de abreviaturas de ESPN hacia los códigos estándar de 32 franquicias
# (Ej. WSH -> WAS, LAR -> LA)
ESPN_TO_STANDARD_ABBR: Dict[str, str] = {
    "WSH": "WAS",
    "WAS": "WAS",
    "LAR": "LA",
    "LA": "LA",
    "STL": "LA",
    "JAC": "JAX",
    "JAX": "JAX",
    "OAK": "LV",
    "LV": "LV",
    "SD": "LAC",
    "LAC": "LAC",
    "ARZ": "ARI",
    "ARI": "ARI",
    "BLT": "BAL",
    "BAL": "BAL",
    "CLV": "CLE",
    "CLE": "CLE",
    "HST": "HOU",
    "HOU": "HOU",
}

# Mapeo inverso hacia el slug exacto que requiere el CDN de logos de ESPN
STANDARD_TO_ESPN_CDN_SLUG: Dict[str, str] = {
    "WAS": "wsh",
    "WSH": "wsh",
    "LA": "lar",
    "LAR": "lar",
    "JAX": "jax",
    "LV": "lv",
    "LAC": "lac",
    "KC": "kc",
    "SF": "sf",
    "BUF": "buf",
    "BAL": "bal",
    "DET": "det",
    "DAL": "dal",
    "PHI": "phi",
    "NE": "ne",
    "HOU": "hou",
    "GB": "gb",
    "CIN": "cin",
    "MIA": "mia",
    "MIN": "min",
    "NYJ": "nyj",
    "CLE": "cle",
    "PIT": "pit",
    "ATL": "atl",
    "CHI": "chi",
    "IND": "ind",
    "SEA": "sea",
    "TB": "tb",
    "ARI": "ari",
    "NO": "no",
    "DEN": "den",
    "TEN": "ten",
    "NYG": "nyg",
    "CAR": "car",
}

NFL_FRANCHISE_NAMES: Dict[str, str] = {
    "KC": "Kansas City Chiefs",
    "SF": "San Francisco 49ers",
    "BUF": "Buffalo Bills",
    "BAL": "Baltimore Ravens",
    "DET": "Detroit Lions",
    "DAL": "Dallas Cowboys",
    "PHI": "Philadelphia Eagles",
    "NE": "New England Patriots",
    "HOU": "Houston Texans",
    "GB": "Green Bay Packers",
    "CIN": "Cincinnati Bengals",
    "MIA": "Miami Dolphins",
    "LA": "Los Angeles Rams",
    "MIN": "Minnesota Vikings",
    "NYJ": "New York Jets",
    "CLE": "Cleveland Browns",
    "PIT": "Pittsburgh Steelers",
    "ATL": "Atlanta Falcons",
    "CHI": "Chicago Bears",
    "JAX": "Jacksonville Jaguars",
    "IND": "Indianapolis Colts",
    "SEA": "Seattle Seahawks",
    "TB": "Tampa Bay Buccaneers",
    "WAS": "Washington Commanders",
    "ARI": "Arizona Cardinals",
    "LAC": "Los Angeles Chargers",
    "NO": "New Orleans Saints",
    "LV": "Las Vegas Raiders",
    "DEN": "Denver Broncos",
    "TEN": "Tennessee Titans",
    "NYG": "New York Giants",
    "CAR": "Carolina Panthers",
}


def normalizar_abbr_nfl(abbr: str) -> str:
    """
    Normaliza cualquier abreviatura de equipo proveniente de ESPN o Excel
    hacia los 32 códigos estándar del motor (ej. WSH -> WAS, LAR -> LA).
    """
    if not abbr:
        return "UNK"
    clean = str(abbr).strip().upper()
    return ESPN_TO_STANDARD_ABBR.get(clean, clean)


def obtener_url_escudo_nfl(team_abbr: str) -> str:
    """
    Retorna la URL directa del escudo oficial en el CDN de ESPN.
    """
    std_abbr = normalizar_abbr_nfl(team_abbr)
    cdn_slug = STANDARD_TO_ESPN_CDN_SLUG.get(std_abbr, std_abbr.lower())
    return ESPN_NFL_LOGO_CDN.format(abbr=cdn_slug)


def escudo_nfl_html(team_abbr: str, size: int = 32) -> str:
    """
    Retorna el tag <img> apuntando al CDN público de ESPN:
    'https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png'
    """
    std_abbr = normalizar_abbr_nfl(team_abbr)
    logo_url = obtener_url_escudo_nfl(std_abbr)
    return (
        f'<img src="{logo_url}" alt="{std_abbr}" width="{size}" height="{size}" '
        f'style="width:{size}px; height:{size}px; object-fit:contain; '
        f'vertical-align:middle; filter:drop-shadow(0 2px 5px rgba(0,0,0,0.55));" '
        f'onerror="this.style.display=\'none\'">'
    )


def _formatear_fecha_espn(iso_date_str: str, short_detail: str = "") -> str:
    """Convierte la fecha ISO de ESPN a formato corto legible para la cartelera."""
    if short_detail and any(tok in short_detail.upper() for tok in ["PM", "AM", "FINAL", "Q1", "Q2", "Q3", "Q4", "OT", "HALFTIME"]):
        return short_detail
    if not iso_date_str:
        return "DOM 13:00 ET"
    try:
        dt = datetime.fromisoformat(iso_date_str.replace("Z", "+00:00"))
        dias_es = ["LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB", "DOM"]
        dia_str = dias_es[dt.weekday()]
        return f"{dia_str} {dt.strftime('%H:%M')} UTC"
    except Exception:
        return short_detail or "DOM 13:00 ET"


def _calendario_fallback_semana(semana: Optional[int] = None) -> List[Dict[str, str]]:
    """
    Calendario de respaldo determinístico de 12 partidos en caso de que
    el entorno no tenga salida a Internet o la API de ESPN esté en receso.
    """
    sem_num = semana if semana is not None else 8
    cruces_base = [
        ("BAL", "KC", "JUE 20:15 ET · TNF"),
        ("DET", "SF", "DOM 13:00 ET · FOX"),
        ("MIA", "BUF", "DOM 13:00 ET · CBS"),
        ("DAL", "PHI", "DOM 16:25 ET · FOX"),
        ("CIN", "CLE", "DOM 13:00 ET · CBS"),
        ("IND", "HOU", "DOM 13:00 ET · CBS"),
        ("CHI", "GB", "DOM 16:25 ET · CBS"),
        ("SEA", "LA", "DOM 16:05 ET · FOX"),
        ("NYG", "WAS", "DOM 13:00 ET · FOX"),
        ("NYJ", "NE", "DOM 13:00 ET · CBS"),
        ("ATL", "NO", "DOM 13:00 ET · FOX"),
        ("LV", "LAC", "DOM 20:20 ET · SNF"),
    ]
    partidos: List[Dict[str, str]] = []
    for idx, (away, home, hora) in enumerate(cruces_base, start=1):
        away_name = NFL_FRANCHISE_NAMES.get(away, away)
        home_name = NFL_FRANCHISE_NAMES.get(home, home)
        partidos.append(
            {
                "id_partido": f"NFL_W{sem_num}_{idx:02d}_{away}_{home}",
                "nombre": f"{away_name} at {home_name}",
                "away_abbr": away,
                "home_abbr": home,
                "hora": hora,
                "estado": f"Programado · Semana {sem_num}",
            }
        )
    return partidos


def obtener_calendario_nfl_semana(semana: Optional[int] = None) -> List[Dict[str, str]]:
    """
    Consulta el endpoint público de ESPN:
    'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard'
    Extrae los partidos programados o en curso devolviendo una lista de diccionarios:
    [{'id_partido': str, 'nombre': str, 'away_abbr': str, 'home_abbr': str, 'hora': str, 'estado': str}]
    Normaliza abreviaturas de ESPN hacia los códigos estándar de 32 franquicias
    (ej. WSH -> WAS, LAR -> LA).
    """
    params: Dict[str, Any] = {}
    if semana is not None and int(semana) > 0:
        params["week"] = int(semana)
        params["seasontype"] = 2  # Temporada Regular

    try:
        response = requests.get(
            ESPN_NFL_SCOREBOARD_URL,
            params=params,
            timeout=6,
            headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        data = response.json()
        events = data.get("events", [])
        if not events:
            return _calendario_fallback_semana(semana)

        partidos_extraidos: List[Dict[str, str]] = []
        for ev in events:
            event_id = str(ev.get("id", ""))
            event_name = str(ev.get("name", "NFL Matchup"))
            iso_date = str(ev.get("date", ""))

            status_obj = ev.get("status", {}).get("type", {})
            short_detail = str(status_obj.get("shortDetail", ""))
            estado_desc = str(status_obj.get("description", "Scheduled"))

            competitions = ev.get("competitions", [])
            if not competitions:
                continue

            comp = competitions[0]
            competitors = comp.get("competitors", [])
            away_abbr = ""
            home_abbr = ""

            for team_entry in competitors:
                home_away = str(team_entry.get("homeAway", "")).lower()
                raw_abbr = str(team_entry.get("team", {}).get("abbreviation", ""))
                norm_abbr = normalizar_abbr_nfl(raw_abbr)
                if home_away == "away":
                    away_abbr = norm_abbr
                elif home_away == "home":
                    home_abbr = norm_abbr

            if not away_abbr or not home_abbr:
                continue

            hora_formateada = _formatear_fecha_espn(iso_date, short_detail)
            partidos_extraidos.append(
                {
                    "id_partido": event_id or f"{away_abbr}_{home_abbr}",
                    "nombre": event_name,
                    "away_abbr": away_abbr,
                    "home_abbr": home_abbr,
                    "hora": hora_formateada,
                    "estado": estado_desc,
                }
            )

        if not partidos_extraidos:
            return _calendario_fallback_semana(semana)

        return partidos_extraidos

    except Exception:
        return _calendario_fallback_semana(semana)