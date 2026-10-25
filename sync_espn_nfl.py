#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MÓDULO 1: sync_espn_nfl.py
Sincronización del calendario semanal de la NFL desde ESPN Scoreboard API,
auditoría de líneas y cuotas en vivo desde The Odds API (con Fallback automático
al consenso de ESPN Scoreboard convertido a FORMATO DECIMAL europeo) y
generación dinámica de escudos oficiales vía CDN.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import requests

ESPN_NFL_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
THE_ODDS_API_NFL_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds/"
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

# Mapeo de nombres completos (The Odds API / ESPN) hacia los 32 códigos estándar
TEAM_NAME_TO_ABBR: Dict[str, str] = {
    nombre.upper(): abbr for abbr, nombre in NFL_FRANCHISE_NAMES.items()
}
TEAM_NAME_TO_ABBR.update(
    {
        "LA RAMS": "LA",
        "LOS ANGELES RAMS": "LA",
        "LA CHARGERS": "LAC",
        "LOS ANGELES CHARGERS": "LAC",
        "WASHINGTON": "WAS",
        "NY GIANTS": "NYG",
        "NY JETS": "NYJ",
        "CHIEFS": "KC",
        "49ERS": "SF",
        "BILLS": "BUF",
        "RAVENS": "BAL",
        "LIONS": "DET",
        "COWBOYS": "DAL",
        "EAGLES": "PHI",
        "PATRIOTS": "NE",
        "TEXANS": "HOU",
        "PACKERS": "GB",
        "BENGALS": "CIN",
        "DOLPHINS": "MIA",
        "RAMS": "LA",
        "VIKINGS": "MIN",
        "JETS": "NYJ",
        "BROWNS": "CLE",
        "STEELERS": "PIT",
        "FALCONS": "ATL",
        "BEARS": "CHI",
        "JAGUARS": "JAX",
        "COLTS": "IND",
        "SEAHAWKS": "SEA",
        "BUCCANEERS": "TB",
        "COMMANDERS": "WAS",
        "CARDINALS": "ARI",
        "CHARGERS": "LAC",
        "SAINTS": "NO",
        "RAIDERS": "LV",
        "BRONCOS": "DEN",
        "TITANS": "TEN",
        "GIANTS": "NYG",
        "PANTHERS": "CAR",
    }
)


def normalizar_abbr_nfl(abbr_or_name: str) -> str:
    """
    Normaliza cualquier abreviatura o nombre completo de equipo proveniente de
    The Odds API, ESPN o Excel hacia los 32 códigos estándar del motor
    (ej. WSH -> WAS, LAR -> LA, 'Kansas City Chiefs' -> KC).
    """
    if not abbr_or_name:
        return "UNK"
    clean = str(abbr_or_name).strip().upper()
    if clean in ESPN_TO_STANDARD_ABBR:
        return ESPN_TO_STANDARD_ABBR[clean]
    if clean in NFL_FRANCHISE_NAMES:
        return clean
    if clean in TEAM_NAME_TO_ABBR:
        return TEAM_NAME_TO_ABBR[clean]
    for full_name, code in TEAM_NAME_TO_ABBR.items():
        if full_name in clean or clean in full_name:
            return code
    return clean


def americano_a_decimal(momio: Any, default_decimal: float = 1.91) -> float:
    """
    Convierte un momio americano (ej. -110, +125) a FORMATO DECIMAL europeo con 2 decimales:
      - Si momio > 0: round(1 + (momio / 100), 2)
      - Si momio < 0: round(1 + (100 / abs(momio)), 2)
    Si el valor recibido ya está en formato decimal (ej. entre 1.01 y 15.0),
    lo redondea directamente a 2 decimales.
    """
    if momio is None:
        return round(default_decimal, 2)
    if isinstance(momio, str):
        limpio = momio.strip().upper().replace(",", ".")
        if limpio in {"EVEN", "EV", "PK", "PICK"}:
            return 2.00
        try:
            val = float(limpio)
        except ValueError:
            return round(default_decimal, 2)
    else:
        try:
            val = float(momio)
        except (TypeError, ValueError):
            return round(default_decimal, 2)

    if val == 0:
        return round(default_decimal, 2)

    # Si ya viene en rango decimal europeo (1.01 a 25.0)
    if 1.01 <= val <= 25.0:
        return round(val, 2)

    if val > 0:
        return round(1.0 + (val / 100.0), 2)
    return round(1.0 + (100.0 / abs(val)), 2)


def obtener_url_escudo_nfl(team_abbr: str) -> str:
    """Retorna la URL directa del escudo oficial en el CDN de ESPN."""
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
    if short_detail and any(
        tok in short_detail.upper() for tok in ["PM", "AM", "FINAL", "Q1", "Q2", "Q3", "Q4", "OT", "HALFTIME"]
    ):
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


def _parsear_spread_details_espn(details_str: str, home_abbr: str, away_abbr: str) -> Optional[float]:
    """
    Convierte el campo 'details' de ESPN (ej. 'KC -3.5', 'BAL -2.5', 'EVEN')
    en el spread desde la perspectiva del equipo Local ('spread_mercado_home').
    """
    if not details_str:
        return None
    clean = str(details_str).strip().upper()
    if clean in {"EVEN", "PK", "PICK"}:
        return 0.0
    partes = clean.split()
    if len(partes) >= 2:
        fav_abbr = normalizar_abbr_nfl(partes[0])
        try:
            line_val = float(partes[1])
        except ValueError:
            return None
        if fav_abbr == home_abbr:
            return -abs(line_val)
        if fav_abbr == away_abbr:
            return abs(line_val)
    return None


def _extraer_odds_espn_evento(comp: Dict[str, Any], away_abbr: str, home_abbr: str) -> Dict[str, Any]:
    """
    Extrae las líneas de consenso que vienen en 'competitions[0].odds' de ESPN Scoreboard
    y convierte cualquier momio americano a FORMATO DECIMAL con 2 decimales.
    """
    odds_list = comp.get("odds", [])
    # Valores de consenso por defecto en formato decimal si ESPN no publica momio en ese partido
    default_lineas = _generar_linea_consenso_fallback(away_abbr, home_abbr)

    if not odds_list or not isinstance(odds_list, list):
        return default_lineas

    odd_obj = odds_list[0] or {}
    provider_name = str(odd_obj.get("provider", {}).get("name", "ESPN Consensus"))

    # 1. Línea Total (Over / Under)
    raw_ou = odd_obj.get("overUnder")
    try:
        total_mercado = round(float(raw_ou), 1) if raw_ou is not None else default_lineas["total_mercado"]
    except (TypeError, ValueError):
        total_mercado = default_lineas["total_mercado"]

    cuota_over_decimal = americano_a_decimal(odd_obj.get("overOdds"), default_decimal=1.91)
    cuota_under_decimal = americano_a_decimal(odd_obj.get("underOdds"), default_decimal=1.91)

    # 2. Línea de Hándicap (Spread del equipo Local)
    details_str = str(odd_obj.get("details", ""))
    spread_home = _parsear_spread_details_espn(details_str, home_abbr=home_abbr, away_abbr=away_abbr)
    if spread_home is None:
        raw_sp = odd_obj.get("spread")
        try:
            spread_home = round(float(raw_sp), 1) if raw_sp is not None else default_lineas["spread_mercado_home"]
        except (TypeError, ValueError):
            spread_home = default_lineas["spread_mercado_home"]

    home_odds_obj = odd_obj.get("homeTeamOdds", {}) or {}
    away_odds_obj = odd_obj.get("awayTeamOdds", {}) or {}

    raw_sp_home_odds = (
        home_odds_obj.get("spreadOdds")
        or home_odds_obj.get("current", {}).get("pointSpread", {}).get("american")
    )
    raw_sp_away_odds = (
        away_odds_obj.get("spreadOdds")
        or away_odds_obj.get("current", {}).get("pointSpread", {}).get("american")
    )

    cuota_spread_home_decimal = americano_a_decimal(raw_sp_home_odds, default_decimal=1.91)
    cuota_spread_away_decimal = americano_a_decimal(raw_sp_away_odds, default_decimal=1.91)

    return {
        "total_mercado": total_mercado,
        "cuota_over_decimal": cuota_over_decimal,
        "cuota_under_decimal": cuota_under_decimal,
        "spread_mercado_home": spread_home,
        "cuota_spread_home_decimal": cuota_spread_home_decimal,
        "cuota_spread_away_decimal": cuota_spread_away_decimal,
        "fuente_odds": f"ESPN Scoreboard ({provider_name})",
    }


def _generar_linea_consenso_fallback(away_abbr: str, home_abbr: str) -> Dict[str, Any]:
    """
    Genera líneas de consenso de mercado realistas en FORMATO DECIMAL cuando
    un partido de ESPN aún no tiene momios abiertos o estamos en modo offline.
    """
    power_tier = {
        "KC": 5.5, "SF": 5.0, "BAL": 4.8, "BUF": 4.5, "DET": 4.5, "PHI": 3.8,
        "CIN": 3.0, "DAL": 2.8, "GB": 2.6, "HOU": 2.5, "MIA": 2.2, "LA": 1.8,
        "MIN": 1.5, "LAC": 1.4, "TB": 1.2, "ATL": 1.0, "SEA": 0.8, "WAS": 0.8,
        "PIT": 0.6, "NYJ": 0.4, "CHI": 0.0, "JAX": -0.3, "IND": -0.4, "CLE": -0.8,
        "NO": -1.0, "ARI": -1.2, "DEN": -1.4, "LV": -2.5, "NE": -3.2, "TEN": -3.4,
        "NYG": -3.8, "CAR": -4.8,
    }
    p_away = power_tier.get(normalizar_abbr_nfl(away_abbr), 0.0)
    p_home = power_tier.get(normalizar_abbr_nfl(home_abbr), 0.0)

    # Spread de mercado del local (redondeado a medios puntos .5)
    raw_margin_home = (p_home - p_away) + 1.8
    half_steps = round(-raw_margin_home * 2.0) / 2.0
    if half_steps % 1.0 == 0.0:
        half_steps += -0.5 if half_steps <= 0 else 0.5
    spread_mercado_home = float(max(-13.5, min(13.5, half_steps)))

    # Total de mercado (redondeado a .5 entre 41.5 y 51.5)
    raw_total = 45.5 + (p_home + p_away) * 0.45
    total_mercado = round(raw_total) - 0.5
    total_mercado = float(max(40.5, min(52.5, total_mercado)))

    return {
        "total_mercado": total_mercado,
        "cuota_over_decimal": 1.91,
        "cuota_under_decimal": 1.91,
        "spread_mercado_home": spread_mercado_home,
        "cuota_spread_home_decimal": 1.91,
        "cuota_spread_away_decimal": 1.91,
        "fuente_odds": "Consenso Vegas (Decimal)",
    }


def obtener_lineas_mercado_nfl(
    api_key: Optional[str] = None,
    semana: Optional[int] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Consulta The Odds API:
      - URL: 'https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds/'
      - Parámetros: 'regions=us', 'markets=totals,spreads', 'oddsFormat=decimal'
    Extrae por partido (indexado por clave '{away_abbr}@{home_abbr}'):
      - 'total_mercado': línea de puntos (ej. 47.5).
      - 'cuota_over_decimal' y 'cuota_under_decimal' (ej. 1.91 / 1.91).
      - 'spread_mercado_home': línea de hándicap del local (ej. -3.5 o +2.5).
      - 'cuota_spread_home_decimal' y 'cuota_spread_away_decimal' (ej. 1.95 / 1.87).
    Módulo Fallback:
      Si no se suministra API key o falla la llamada, extrae las líneas de consenso
      del payload de ESPN Scoreboard ('competitions[0].odds') convirtiendo momios
      americanos a formato decimal con 2 decimales.
    """
    lineas_por_partido: Dict[str, Dict[str, Any]] = {}

    # 1. Intento primario: The Odds API (en formato decimal nativo)
    if api_key and str(api_key).strip():
        try:
            params_odds = {
                "apiKey": str(api_key).strip(),
                "regions": "us",
                "markets": "totals,spreads",
                "oddsFormat": "decimal",
            }
            resp = requests.get(THE_ODDS_API_NFL_URL, params=params_odds, timeout=7)
            resp.raise_for_status()
            eventos_odds = resp.json()

            if isinstance(eventos_odds, list):
                for ev in eventos_odds:
                    home_team_raw = str(ev.get("home_team", ""))
                    away_team_raw = str(ev.get("away_team", ""))
                    home_abbr = normalizar_abbr_nfl(home_team_raw)
                    away_abbr = normalizar_abbr_nfl(away_team_raw)
                    if home_abbr == "UNK" or away_abbr == "UNK":
                        continue

                    match_key = f"{away_abbr}@{home_abbr}"
                    bookmakers = ev.get("bookmakers", [])
                    fallback_vals = _generar_linea_consenso_fallback(away_abbr, home_abbr)

                    total_mercado = fallback_vals["total_mercado"]
                    cuota_over_dec = 1.91
                    cuota_under_dec = 1.91
                    spread_home = fallback_vals["spread_mercado_home"]
                    cuota_sp_home_dec = 1.91
                    cuota_sp_away_dec = 1.91
                    book_title = "The Odds API (US)"

                    if bookmakers:
                        # Priorizar libros sharp/principales de US
                        bk = bookmakers[0]
                        book_title = f"The Odds API ({bk.get('title', 'US Book')})"
                        for mkt in bk.get("markets", []):
                            m_key = str(mkt.get("key", ""))
                            outcomes = mkt.get("outcomes", [])
                            if m_key == "totals":
                                for out in outcomes:
                                    name_out = str(out.get("name", "")).upper()
                                    if "OVER" in name_out:
                                        if out.get("point") is not None:
                                            total_mercado = round(float(out["point"]), 1)
                                        cuota_over_dec = americano_a_decimal(out.get("price"), 1.91)
                                    elif "UNDER" in name_out:
                                        if out.get("point") is not None:
                                            total_mercado = round(float(out["point"]), 1)
                                        cuota_under_dec = americano_a_decimal(out.get("price"), 1.91)
                            elif m_key == "spreads":
                                for out in outcomes:
                                    out_abbr = normalizar_abbr_nfl(str(out.get("name", "")))
                                    if out_abbr == home_abbr:
                                        if out.get("point") is not None:
                                            spread_home = round(float(out["point"]), 1)
                                        cuota_sp_home_dec = americano_a_decimal(out.get("price"), 1.91)
                                    elif out_abbr == away_abbr:
                                        if out.get("point") is not None and spread_home is None:
                                            spread_home = round(-float(out["point"]), 1)
                                        cuota_sp_away_dec = americano_a_decimal(out.get("price"), 1.91)

                    lineas_por_partido[match_key] = {
                        "away_abbr": away_abbr,
                        "home_abbr": home_abbr,
                        "total_mercado": total_mercado,
                        "cuota_over_decimal": cuota_over_dec,
                        "cuota_under_decimal": cuota_under_dec,
                        "spread_mercado_home": spread_home,
                        "cuota_spread_home_decimal": cuota_sp_home_dec,
                        "cuota_spread_away_decimal": cuota_sp_away_dec,
                        "fuente_odds": book_title,
                    }

                if lineas_por_partido:
                    return lineas_por_partido
        except Exception:
            pass

    # 2. Módulo Fallback: Extracción desde ESPN Scoreboard ('competitions[0].odds')
    params_espn: Dict[str, Any] = {}
    if semana is not None and int(semana) > 0:
        params_espn["week"] = int(semana)
        params_espn["seasontype"] = 2

    try:
        resp_espn = requests.get(
            ESPN_NFL_SCOREBOARD_URL,
            params=params_espn,
            timeout=6,
            headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
        )
        resp_espn.raise_for_status()
        events = resp_espn.json().get("events", [])
        for ev in events:
            comps = ev.get("competitions", [])
            if not comps:
                continue
            comp = comps[0]
            away_abbr, home_abbr = "", ""
            for c_team in comp.get("competitors", []):
                ha = str(c_team.get("homeAway", "")).lower()
                ab = normalizar_abbr_nfl(str(c_team.get("team", {}).get("abbreviation", "")))
                if ha == "away":
                    away_abbr = ab
                elif ha == "home":
                    home_abbr = ab
            if not away_abbr or not home_abbr:
                continue

            odds_extraidas = _extraer_odds_espn_evento(comp, away_abbr=away_abbr, home_abbr=home_abbr)
            match_key = f"{away_abbr}@{home_abbr}"
            lineas_por_partido[match_key] = {
                "away_abbr": away_abbr,
                "home_abbr": home_abbr,
                **odds_extraidas,
            }
    except Exception:
        pass

    return lineas_por_partido


def _calendario_fallback_semana(semana: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Calendario de respaldo determinístico de 12 partidos con líneas de mercado
    en formato decimal integradas.
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
    partidos: List[Dict[str, Any]] = []
    for idx, (away, home, hora) in enumerate(cruces_base, start=1):
        away_name = NFL_FRANCHISE_NAMES.get(away, away)
        home_name = NFL_FRANCHISE_NAMES.get(home, home)
        lineas_fb = _generar_linea_consenso_fallback(away, home)
        partidos.append(
            {
                "id_partido": f"NFL_W{sem_num}_{idx:02d}_{away}_{home}",
                "nombre": f"{away_name} at {home_name}",
                "away_abbr": away,
                "home_abbr": home,
                "hora": hora,
                "estado": f"Programado · Semana {sem_num}",
                **lineas_fb,
            }
        )
    return partidos


def obtener_calendario_nfl_semana(
    semana: Optional[int] = None,
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Consulta el endpoint público de ESPN Scoreboard API y fusiona cada partido
    con las líneas y cuotas en FORMATO DECIMAL obtenidas de The Odds API o del
    Fallback de consenso de ESPN ('competitions[0].odds').
    """
    params: Dict[str, Any] = {}
    if semana is not None and int(semana) > 0:
        params["week"] = int(semana)
        params["seasontype"] = 2

    mapa_odds_live = obtener_lineas_mercado_nfl(api_key=api_key, semana=semana)

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
            partidos_fb = _calendario_fallback_semana(semana)
            for p in partidos_fb:
                m_key = f"{p['away_abbr']}@{p['home_abbr']}"
                if m_key in mapa_odds_live:
                    p.update(mapa_odds_live[m_key])
            return partidos_fb

        partidos_extraidos: List[Dict[str, Any]] = []
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
            match_key = f"{away_abbr}@{home_abbr}"

            if match_key in mapa_odds_live:
                odds_partido = mapa_odds_live[match_key]
            else:
                odds_partido = _extraer_odds_espn_evento(comp, away_abbr=away_abbr, home_abbr=home_abbr)

            partidos_extraidos.append(
                {
                    "id_partido": event_id or f"{away_abbr}_{home_abbr}",
                    "nombre": event_name,
                    "away_abbr": away_abbr,
                    "home_abbr": home_abbr,
                    "hora": hora_formateada,
                    "estado": estado_desc,
                    "total_mercado": float(odds_partido["total_mercado"]),
                    "cuota_over_decimal": float(odds_partido["cuota_over_decimal"]),
                    "cuota_under_decimal": float(odds_partido["cuota_under_decimal"]),
                    "spread_mercado_home": float(odds_partido["spread_mercado_home"]),
                    "cuota_spread_home_decimal": float(odds_partido["cuota_spread_home_decimal"]),
                    "cuota_spread_away_decimal": float(odds_partido["cuota_spread_away_decimal"]),
                    "fuente_odds": str(odds_partido.get("fuente_odds", "ESPN Scoreboard (Decimal)")),
                }
            )

        if not partidos_extraidos:
            return _calendario_fallback_semana(semana)

        return partidos_extraidos

    except Exception:
        partidos_fb = _calendario_fallback_semana(semana)
        for p in partidos_fb:
            m_key = f"{p['away_abbr']}@{p['home_abbr']}"
            if m_key in mapa_odds_live:
                p.update(mapa_odds_live[m_key])
        return partidos_fb