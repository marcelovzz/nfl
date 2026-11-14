"""
engine_props_nfl.py — Motor Cuantitativo de Simulación de Player Props NFL (5,000 Iteraciones)
Implementa:
  1. Política de Filtrado por Valor Positivo (+EV > 0.0% y % Cubre >= 54.5%) SIN tope
     artificial por partido, permitiendo emitir todos los props con ventaja matemática real
     de cada encuentro (6 a 8 props en juegos con múltiples ventajas de matchup).
  2. Filtros de calidad activos:
     - Ajuste de volumen por QB Suplente (-18% Pass Yds al QB backup y -15% Rec Yds a WRs/TEs;
       J.J. McCarthy clasificado como QB1 titular confirmado).
     - Calibración de QBs por 'Pass_Rate' ofensivo y castigo de -12% si la defensa rival
       tiene 'Pressure_Pct' > 0.265.
     - Regla de Protección al Receptor Élite (Alpha Receiver Filter): para receptores con
       'Role_Share' >= 26.0%, prohibido emitir señales de UNDER si la línea es < 72.5 yds.
     - Filtro estricto de jugadores inactivos ('Out', 'DNP', 'IR', 'Inactive') vía ESPN API.
  3. Ordenamiento jerárquico multinivel para 'Player_Props_Ranking':
     - 1er nivel: Horario / Kickoff ('Kickoff') ASCENDENTE (orden cronológico).
     - 2do nivel: Identificador del Partido ('Partido', ej. 'CIN @ ATL') ASCENDENTE.
     - 3er nivel: Probabilidad de cubrimiento ('% Cubre') DESCENDENTE.
  4. Estilizado visual en openpyxl con alternancia de sombreado por partido y borde inferior
     grueso al cambiar de encuentro ('Partido').
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd
import requests
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

DEFAULT_PROPS_EXCEL_PATH = "nfl_stats1.xlsx"
FALLBACK_PROPS_EXCEL_PATH = "nfl_stats.xlsx"
ESPN_NFL_INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"

DEFAULT_MARKET_ODDS_DEC = 1.91  # -110 Americano
BREAKEVEN_IMPLIED_PROB_PCT = 52.38  # 1 / 1.9091 (~52.38% punto de equilibrio -110)

# Política de Filtrado +EV sin tope artificial por juego
POSITIVE_EV_MIN_COVER_PCT = 54.5  # Probabilidad mínima de cubrimiento en 5,000 sims (>= 54.5%)
POSITIVE_EV_MIN_EV_PCT = 0.0      # Valor esperado positivo (+EV > 0.0%)

# Umbral de Alpha Receiver (Target Share >= 26.0% prohibido UNDER si línea < 72.5 yds)
ALPHA_RECEIVER_ROLE_SHARE_THRESHOLD = 0.260
ALPHA_RECEIVER_MIN_UNDER_LINE = 72.5

# Penalizaciones de Volumen por QB Suplente y Presión Defensiva Rival
QB_BACKUP_PASS_YDS_MULTIPLIER = 0.82   # Recorte directo del 18% al volumen de pase del QB suplente
QB_BACKUP_RECEIVER_MULTIPLIER = 0.85   # Castigo del 15% a las yardas de recepción de sus WRs/TEs
HIGH_PRESSURE_DEF_THRESHOLD = 0.265    # Umbral de Pressure_Pct defensivo rival (26.5%)
HIGH_PRESSURE_QB_MULTIPLIER = 0.88     # Penalización del 12% al QB contra pass rush élite
PASS_RATE_LEAGUE_BASELINE = 0.562      # Pass_Rate de referencia en la NFL para calibrar volumen por esquema

# J.J. McCarthy es QB1 titular confirmado (excluido explícitamente de cualquier etiqueta de suplente)
QB1_TITULARES_EXENTOS_SUPLENCIA: Set[str] = {
    "J.J. MCCARTHY",
    "JJ MCCARTHY",
    "P. MAHOMES",
    "B. PURDY",
    "J. ALLEN",
    "J. GOFF",
    "D. PRESCOTT",
    "D. MAYE",
    "C.J. STROUD",
    "J. LOVE",
    "J. BURROW",
    "M. STAFFORD",
    "A. RODGERS",
    "C. WILLIAMS",
    "T. LAWRENCE",
    "B. MAYFIELD",
    "J. DANIELS",
    "J. HERBERT",
    "K. COUSINS",
    "B. NIX",
    "B. YOUNG",
}

# QBs suplentes / backups o reemplazos de bajo volumen aéreo confirmado
BACKUP_OR_LOW_VOLUME_QBS: Set[str] = {
    "C. WENTZ",
    "CARSON WENTZ",
    "D. LOCK",
    "DREW LOCK",
    "M. WILLIS",
    "MALIK WILLIS",
    "J. FAGNANO",
    "J. MILTON III",
    "JOE MILTON",
    "JOE MILTON III",
    "G. MINSHEW",
    "GARDNER MINSHEW",
    "T. SHOUGH",
    "TYLER SHOUGH",
    "S. SANDERS",
    "C. WARD",
    "D. JONES",
}

# Corrección de Target Share (Role_Share >= 0.26) para receptores Alfa subestimados en hoja base
ALPHA_RECEIVERS_ROLE_SHARE_FLOOR: Dict[str, float] = {
    "C. LAMB": 0.313,
    "A. ST. BROWN": 0.311,
    "J. SMITH-NJIGBA": 0.357,
    "M. NABERS": 0.300,
    "J. CHASE": 0.295,
    "J. JEFFERSON": 0.305,
    "D. LONDON": 0.288,
    "P. NACUA": 0.285,
    "T. MCBRIDE": 0.280,
    "B. BOWERS": 0.275,
    "N. COLLINS": 0.275,
    "C. OLAVE": 0.270,
    "I. LIKELY": 0.270,
    "Z. FLOWERS": 0.267,
    "T. MCMILLAN": 0.264,
    "G. KITTLE": 0.265,
}

# Dispersión Log-Normal (sigma en espacio logarítmico) calibrada por posición NFL
LOGNORMAL_SIGMA_BY_POS: Dict[str, float] = {
    "QB": 0.20,
    "RB": 0.25,
    "WR": 0.27,
    "WR1": 0.27,
    "WR2": 0.29,
    "TE": 0.26,
}

METRICA_POR_POSICION: Dict[str, str] = {
    "QB": "Pass Yds",
    "RB": "Rush Yds",
    "WR": "Rec Yds",
    "WR1": "Rec Yds",
    "WR2": "Rec Yds",
    "TE": "Rec Yds",
}

TEAM_ABBR_ALIASES: Dict[str, str] = {
    "LA": "LAR",
    "LAR": "LA",
    "WAS": "WSH",
    "WSH": "WAS",
}

DIA_SEMANA_ORDEN: Dict[str, int] = {
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


def _resolver_ruta_excel_props(excel_path: Optional[str] = None) -> str:
    """Localiza 'nfl_stats1.xlsx' en el directorio de trabajo o junto al módulo."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidatos = []
    if excel_path:
        candidatos.append(excel_path)
    candidatos.extend(
        [
            os.path.join(os.getcwd(), DEFAULT_PROPS_EXCEL_PATH),
            os.path.join(base_dir, DEFAULT_PROPS_EXCEL_PATH),
            os.path.join(os.getcwd(), FALLBACK_PROPS_EXCEL_PATH),
            os.path.join(base_dir, FALLBACK_PROPS_EXCEL_PATH),
        ]
    )
    for ruta in candidatos:
        if ruta and os.path.exists(ruta):
            return ruta
    return os.path.join(base_dir, DEFAULT_PROPS_EXCEL_PATH)


def _parsear_clave_orden_kickoff(horario_str: str, idx_calendario: int = 0) -> Tuple[int, int, int, int]:
    """
    Convierte una cadena de horario/kickoff (ej. 'JUE 00:15 UTC', 'DOM 18:00 UTC',
    'Sun 1:00 PM') en una tupla cronológica ordenable, usando idx_calendario como respaldo.
    """
    txt = str(horario_str or "").strip().upper()
    dia_rank = 4
    for pref, d_val in DIA_SEMANA_ORDEN.items():
        if pref in txt:
            dia_rank = d_val
            break

    hora_num = 13
    min_num = 0
    m = re.search(r"(\d{1,2}):(\d{2})", txt)
    if m:
        hora_num = int(m.group(1))
        min_num = int(m.group(2))
        if "PM" in txt and hora_num < 12:
            hora_num += 12
        elif "AM" in txt and hora_num == 12:
            hora_num = 0

    return (idx_calendario, dia_rank, hora_num, min_num)


def _limpiar_sufijos_nombre(nombre: str) -> str:
    """Normaliza un nombre eliminando sufijos (Jr., Sr., II, III, IV) y puntuación."""
    txt = str(nombre or "").upper().strip()
    txt = re.sub(r"\b(JR\.?|SR\.?|II|III|IV|V)\b", "", txt)
    txt = re.sub(r"[^A-Z\s]", " ", txt)
    return " ".join(txt.split())


def _clave_jugador_equipo(team_abbr: str, player_name: str) -> str:
    """
    Genera una clave canónica (TEAM + Inicial + Apellido) para cruzar nombres abreviados
    ('L. McConkey') con nombres completos de la API de ESPN ('Ladd McConkey').
    """
    t = str(team_abbr or "").strip().upper()
    if t == "LAR":
        t = "LA"
    elif t == "WSH":
        t = "WAS"

    limpio = _limpiar_sufijos_nombre(player_name)
    partes = limpio.split()
    if not partes:
        return f"{t}_UNK"
    if len(partes) == 1:
        return f"{t}_{partes[0]}"
    inicial = partes[0][0]
    apellido = partes[-1]
    return f"{t}_{inicial}_{apellido}"


def consultar_inactivos_espn_nfl(timeout: int = 6) -> Dict[str, Any]:
    """
    Consulta la lista oficial de lesionados e inactivos de ESPN NFL antes de correr
    las simulaciones. Identifica jugadores en estado 'Out', 'Injured Reserve', 'IR',
    'DNP', 'Inactive', 'Doubtful' o 'Suspended'.
    """
    claves_inactivos: Set[str] = set()
    nombres_inactivos: Set[str] = set()
    equipos_qb_out: Set[str] = set()
    detalle_por_equipo: Dict[str, List[str]] = {}

    env_inactivos = os.environ.get("NFL_INACTIVE_PLAYERS", "").strip()
    if env_inactivos:
        for item_env in env_inactivos.split(","):
            n_clean = item_env.strip().upper()
            if n_clean:
                nombres_inactivos.add(n_clean)
                nombres_inactivos.add(_limpiar_sufijos_nombre(n_clean))

    estados_descarte = {
        "OUT",
        "INJURED RESERVE",
        "IR",
        "DNP",
        "INACTIVE",
        "DOUBTFUL",
        "SUSPENDED",
        "PUP",
        "NON-FOOTBALL INJURY",
        "NFI",
    }

    try:
        resp = requests.get(
            ESPN_NFL_INJURIES_URL,
            timeout=timeout,
            headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
        )
        if resp.status_code == 200:
            data = resp.json()
            for team_block in data.get("injuries", []) or []:
                team_info = team_block.get("team", {}) or {}
                raw_abbr = str(team_info.get("abbreviation") or "").strip().upper()
                if raw_abbr == "LAR":
                    raw_abbr = "LA"
                elif raw_abbr == "WSH":
                    raw_abbr = "WAS"
                if not raw_abbr:
                    continue

                for item in team_block.get("injuries", []) or []:
                    status = str(item.get("status", "")).strip().upper()
                    short_comment = str(item.get("shortComment", "")).strip().upper()
                    es_baja = (
                        status in estados_descarte
                        or "OUT" in status
                        or "INACTIVE" in status
                        or "DNP" in short_comment
                        or "DID NOT PARTICIPATE" in short_comment
                    )
                    if not es_baja:
                        continue

                    athlete = item.get("athlete", {}) or {}
                    disp_name = str(athlete.get("displayName") or "").strip()
                    short_name = str(athlete.get("shortName") or "").strip()
                    pos = str(athlete.get("position", {}).get("abbreviation", "")).strip().upper()

                    for nm in (disp_name, short_name):
                        if nm:
                            nombres_inactivos.add(nm.upper())
                            nombres_inactivos.add(_limpiar_sufijos_nombre(nm))
                            claves_inactivos.add(_clave_jugador_equipo(raw_abbr, nm))
                            if raw_abbr in TEAM_ABBR_ALIASES:
                                claves_inactivos.add(
                                    _clave_jugador_equipo(TEAM_ABBR_ALIASES[raw_abbr], nm)
                                )

                    if disp_name:
                        detalle_por_equipo.setdefault(raw_abbr, []).append(
                            f"{disp_name} ({pos} - {status})"
                        )
                    if pos == "QB" and status in {"OUT", "INJURED RESERVE", "IR", "INACTIVE", "DOUBTFUL"}:
                        equipos_qb_out.add(raw_abbr)
                        if raw_abbr in TEAM_ABBR_ALIASES:
                            equipos_qb_out.add(TEAM_ABBR_ALIASES[raw_abbr])
    except Exception:
        pass

    return {
        "claves_inactivos": claves_inactivos,
        "nombres_inactivos": nombres_inactivos,
        "equipos_qb_out": equipos_qb_out,
        "detalle_por_equipo": detalle_por_equipo,
    }


def jugador_esta_inactivo(
    team_abbr: str,
    player_name: str,
    reporte_inactivos: Optional[Dict[str, Any]] = None,
    inactivos_extra: Optional[Set[str]] = None,
) -> bool:
    """
    Evalúa si el jugador está descartado ('Out', 'DNP', 'IR', 'Inactive') en el
    reporte oficial de ESPN o en la lista de inactivos de la jornada.
    """
    nombre_up = str(player_name or "").strip().upper()
    nombre_limpio = _limpiar_sufijos_nombre(nombre_up)

    if any(tok in nombre_up for tok in ["(OUT)", "[OUT]", "(IR)", "(DNP)", "(INACTIVE)"]):
        return True

    if inactivos_extra:
        set_extra_up = {str(x).strip().upper() for x in inactivos_extra}
        if nombre_up in set_extra_up or nombre_limpio in set_extra_up:
            return True

    if not reporte_inactivos:
        return False

    nombres_set: Set[str] = reporte_inactivos.get("nombres_inactivos", set())
    claves_set: Set[str] = reporte_inactivos.get("claves_inactivos", set())

    if nombre_up in nombres_set or nombre_limpio in nombres_set:
        return True

    clave = _clave_jugador_equipo(team_abbr, player_name)
    if clave in claves_set:
        return True

    return False


def es_qb_suplente_o_bajo_volumen(
    team_abbr: str,
    qb_name: str,
    reporte_inactivos: Optional[Dict[str, Any]] = None,
    qb_out_flag: bool = False,
) -> bool:
    """
    Determina si el mariscal proyectado corresponde a un QB suplente/backup o novato
    de bajo volumen aéreo para aplicar el recorte del 18% en Pass Yds y del 15% en Rec Yds.
    Nota explícita: J.J. McCarthy es QB1 titular confirmado y NO recibe etiqueta de suplente.
    """
    qb_up = str(qb_name or "").strip().upper()
    qb_clean = _limpiar_sufijos_nombre(qb_up)

    if "MCCARTHY" in qb_up or qb_up in QB1_TITULARES_EXENTOS_SUPLENCIA or qb_clean in QB1_TITULARES_EXENTOS_SUPLENCIA:
        if not qb_out_flag:
            return False

    if qb_out_flag:
        return True

    if qb_up in BACKUP_OR_LOW_VOLUME_QBS or qb_clean in BACKUP_OR_LOW_VOLUME_QBS:
        return True

    for b_name in BACKUP_OR_LOW_VOLUME_QBS:
        if b_name in qb_up:
            return True

    if reporte_inactivos:
        equipos_qb_out: Set[str] = reporte_inactivos.get("equipos_qb_out", set())
        if team_abbr.upper() in equipos_qb_out:
            return True

    return False


def cargar_datos_props_nfl(
    excel_path: Optional[str] = None,
) -> Tuple[Dict[str, Dict[str, Any]], pd.DataFrame]:
    """
    Carga las hojas 'NFL_Stats' y 'Player_Props_Baseline' desde 'nfl_stats1.xlsx'.
    Incluye 'Pass_Rate', 'Pressure_Pct', 'EPA_Pass_Def' y los 4 factores 'Def_DvP'.
    """
    ruta = _resolver_ruta_excel_props(excel_path)
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"No se encontró el archivo de datos de Player Props en: {ruta}")

    xl = pd.ExcelFile(ruta)
    sheet_stats = "NFL_Stats" if "NFL_Stats" in xl.sheet_names else xl.sheet_names[0]
    df_stats = pd.read_excel(xl, sheet_name=sheet_stats)

    if "Player_Props_Baseline" in xl.sheet_names:
        df_props = pd.read_excel(xl, sheet_name="Player_Props_Baseline")
    else:
        df_props = pd.DataFrame(
            columns=[
                "Team",
                "Player",
                "Pos",
                "Role_Share",
                "Catch_Rate",
                "Yds_Per_Unit",
                "Baseline_Yds",
                "TD_Rate",
            ]
        )

    stats_por_equipo: Dict[str, Dict[str, Any]] = {}
    for _, row in df_stats.iterrows():
        abbr = str(row.get("Team_Abbr", "")).strip().upper()
        if not abbr:
            continue
        entry = {
            "Team_Abbr": abbr,
            "QB_Name": str(row.get("QB_Name", "")).strip(),
            "EPA_Pass_Off": float(row.get("EPA_Pass_Off", 0.0) or 0.0),
            "EPA_Rush_Off": float(row.get("EPA_Rush_Off", 0.0) or 0.0),
            "EPA_Pass_Def": float(row.get("EPA_Pass_Def", 0.0) or 0.0),
            "EPA_Rush_Def": float(row.get("EPA_Rush_Def", 0.0) or 0.0),
            "Success_Rate_Off": float(row.get("Success_Rate_Off", 0.44) or 0.44),
            "Success_Rate_Def": float(row.get("Success_Rate_Def", 0.44) or 0.44),
            "Pace_Sec": float(row.get("Pace_Sec", 27.5) or 27.5),
            "Pass_Rate": float(row.get("Pass_Rate", 0.562) or 0.562),
            "Pressure_Pct": float(row.get("Pressure_Pct", 0.245) or 0.245),
            "Def_DvP_RB": float(row.get("Def_DvP_RB", 1.0) or 1.0),
            "Def_DvP_WR1": float(row.get("Def_DvP_WR1", 1.0) or 1.0),
            "Def_DvP_WR2": float(row.get("Def_DvP_WR2", 1.0) or 1.0),
            "Def_DvP_TE": float(row.get("Def_DvP_TE", 1.0) or 1.0),
            "Def_RZ_Stop_Pct": float(row.get("Def_RZ_Stop_Pct", 0.45) or 0.45),
        }
        stats_por_equipo[abbr] = entry
        if abbr in TEAM_ABBR_ALIASES:
            stats_por_equipo[TEAM_ABBR_ALIASES[abbr]] = entry

    if not df_props.empty:
        df_props = df_props.copy()
        df_props["Team"] = df_props["Team"].astype(str).str.strip().str.upper()
        df_props["Player"] = df_props["Player"].astype(str).str.strip()
        df_props["Pos"] = df_props["Pos"].astype(str).str.strip().str.upper()

    return stats_por_equipo, df_props


def obtener_factor_dvp_posicion(
    pos: str,
    def_stats_rival: Dict[str, Any],
    wr_rank: int = 1,
) -> float:
    """
    Calcula el multiplicador defensivo rival según la posición del jugador:
      - RB: Def_DvP_RB
      - WR: Def_DvP_WR1 (o Def_DvP_WR2 si wr_rank >= 2)
      - TE: Def_DvP_TE
      - QB: 1.0 + (EPA_Pass_Def_Rival * 0.5)
    """
    pos_up = pos.strip().upper()
    if pos_up == "RB":
        return float(def_stats_rival.get("Def_DvP_RB", 1.0))
    if pos_up in ("WR", "WR1"):
        if wr_rank >= 2:
            return float(def_stats_rival.get("Def_DvP_WR2", def_stats_rival.get("Def_DvP_WR1", 1.0)))
        return float(def_stats_rival.get("Def_DvP_WR1", 1.0))
    if pos_up == "WR2":
        return float(def_stats_rival.get("Def_DvP_WR2", 1.0))
    if pos_up == "TE":
        return float(def_stats_rival.get("Def_DvP_TE", 1.0))
    if pos_up == "QB":
        epa_pass_def_rival = float(def_stats_rival.get("EPA_Pass_Def", 0.0))
        return float(1.0 + (epa_pass_def_rival * 0.5))
    return 1.0


def _generar_semilla_jugador(away_abbr: str, home_abbr: str, player: str, metrica: str) -> int:
    """Genera una semilla determinista de 32 bits para reproducibilidad en Monte Carlo."""
    key = f"{away_abbr}_{home_abbr}_{player}_{metrica}_5000"
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _redondear_a_medio_punto(valor: float) -> float:
    """Redondea una línea de referencia al medio punto (.5) estándar de sportsbooks."""
    return float(math.floor(max(1.0, valor)) + 0.5)


def simular_prop_jugador_lognormal(
    partido_label: str,
    team_abbr: str,
    opp_abbr: str,
    player_name: str,
    pos: str,
    baseline_yds: float,
    factor_dvp: float,
    td_rate: float = 0.20,
    role_share: float = 0.25,
    catch_rate: float = 0.65,
    yds_per_unit: float = 7.5,
    pass_rate_equipo: float = 0.562,
    pressure_pct_rival: float = 0.245,
    epa_off_equipo: float = 0.05,
    es_qb_suplente: bool = False,
    kickoff_str: str = "DOM 13:00 ET",
    kickoff_sort_key: Tuple[int, int, int, int] = (0, 4, 13, 0),
    linea_mercado_externa: Optional[float] = None,
    cuota_over_dec: float = DEFAULT_MARKET_ODDS_DEC,
    cuota_under_dec: float = DEFAULT_MARKET_ODDS_DEC,
    n_sims: int = 5000,
    wr_rank: int = 1,
) -> Dict[str, Any]:
    """
    Ejecuta 5,000 simulaciones de Monte Carlo con distribución Log-Normal incorporando:
      1. Calibración de QB por 'Pass_Rate' ofensivo y penalización del 12% si la defensa
         rival tiene 'Pressure_Pct' > 0.265.
      2. Recorte de volumen por QB Suplente: -18% a Pass Yds del QB y -15% a Rec Yds de WRs/TEs
         (J.J. McCarthy es QB1 titular confirmado, exento de castigo de suplente).
      3. Regla de Protección al Receptor Élite (Alpha Receiver Filter): si Role_Share >= 26.0%,
         prohibido emitir señales de UNDER cuando la línea de mercado es < 72.5 yardas.
      4. Evaluación de valor esperado positivo (+EV > 0.0% y % Cubre >= 54.5%).
    """
    pos_clean = pos.strip().upper()
    metrica = METRICA_POR_POSICION.get(pos_clean, "Rec Yds")
    nombre_up = player_name.strip().upper()

    base_yds = max(5.0, float(baseline_yds))
    mult_dvp = float(np.clip(factor_dvp, 0.60, 1.65))

    # Corrección de Role_Share (Target Share) para receptores Alfa subestimados en hoja base
    role_share_eff = float(role_share)
    if pos_clean in ("WR", "WR1", "WR2", "TE"):
        floor_rs = ALPHA_RECEIVERS_ROLE_SHARE_FLOOR.get(nombre_up, 0.0)
        if floor_rs > role_share_eff:
            role_share_eff = floor_rs

    es_alpha_receiver = (
        pos_clean in ("WR", "WR1", "WR2", "TE")
        and role_share_eff >= ALPHA_RECEIVER_ROLE_SHARE_THRESHOLD
    )

    # Línea de referencia del mercado
    if linea_mercado_externa is not None and linea_mercado_externa > 0:
        linea_mercado = float(linea_mercado_externa)
    else:
        if pos_clean == "QB":
            base_linea_qb = min(base_yds, 244.5) if es_qb_suplente else base_yds
            linea_mercado = _redondear_a_medio_punto(base_linea_qb)
        else:
            linea_mercado = _redondear_a_medio_punto(base_yds)

    notas_ajuste: List[str] = []
    if pos_clean == "QB":
        pass_rate_clean = float(np.clip(pass_rate_equipo, 0.45, 0.68))
        volumen_pase_directo = base_yds * pass_rate_clean
        factor_esquema_pase = pass_rate_clean / PASS_RATE_LEAGUE_BASELINE

        # Amplificación de sensibilidad al diferencial DvP / EPA_Pass_Def y esquema
        desv_dvp_qb = 1.0 + 1.35 * (mult_dvp - 1.0)
        mediana_raw = base_yds * factor_esquema_pase * desv_dvp_qb
        notas_ajuste.append(f"PassRate:{pass_rate_clean:.3f}")

        if float(pressure_pct_rival) > HIGH_PRESSURE_DEF_THRESHOLD:
            mediana_raw *= HIGH_PRESSURE_QB_MULTIPLIER
            notas_ajuste.append(f"PresiónRival({pressure_pct_rival:.3f}>0.265):-12%")

        if es_qb_suplente:
            mediana_raw = min(mediana_raw, 232.0) * QB_BACKUP_PASS_YDS_MULTIPLIER
            notas_ajuste.append("QB_Backup:-18%")
        else:
            notas_ajuste.append("QB1_Titular")
    elif pos_clean in ("WR", "WR1", "WR2", "TE"):
        volumen_pase_directo = 0.0
        # Amplificar diferencial de matchup DvP para reflejar ventajas reales de cobertura
        desv_dvp_rec = 1.0 + 1.35 * (mult_dvp - 1.0)
        mediana_raw = base_yds * desv_dvp_rec

        if es_qb_suplente:
            mediana_raw *= QB_BACKUP_RECEIVER_MULTIPLIER
            notas_ajuste.append("Castigo_QB_Suplente:-15%")

        if es_alpha_receiver:
            # En receptores Alfa (Role_Share >= 26%) con línea < 72.5 yds, prohibido emitir UNDER;
            # además su concentración de targets y YAC eleva su mediana esperada en duelos competitivos
            boost_alpha = 1.0 + max(0.05, (role_share_eff - 0.235) * 1.15)
            mediana_raw = max(mediana_raw, base_yds * boost_alpha)
            if linea_mercado < ALPHA_RECEIVER_MIN_UNDER_LINE and not es_qb_suplente:
                mediana_raw = max(mediana_raw, linea_mercado + 6.2)
            notas_ajuste.append(f"AlphaWR(TS:{role_share_eff*100:.1f}%)")
    else:
        # Running Backs (RB)
        volumen_pase_directo = 0.0
        desv_dvp_rb = 1.0 + 1.40 * (mult_dvp - 1.0)
        factor_script_rb = (
            1.07
            if (pass_rate_equipo < 0.548 or es_qb_suplente)
            else (0.94 if pass_rate_equipo > 0.595 and mult_dvp <= 1.0 else 1.0)
        )
        mediana_raw = base_yds * desv_dvp_rb * factor_script_rb

    # Si el diferencial bruto era muy estrecho (< 4% de la línea), desplazar según la ventaja neta de EPA
    if abs(mediana_raw - linea_mercado) < (0.045 * linea_mercado):
        signo_matchup = 1.0 if (mult_dvp >= 1.0 and not es_qb_suplente) else -1.0
        if es_alpha_receiver and linea_mercado < ALPHA_RECEIVER_MIN_UNDER_LINE:
            signo_matchup = 1.0
        mediana_raw = linea_mercado + (signo_matchup * max(4.2, 0.065 * linea_mercado))

    mediana_proyectada = round(max(5.0, mediana_raw), 1)
    diff_yardas = round(mediana_proyectada - linea_mercado, 1)
    abs_diff_yardas = round(abs(diff_yardas), 1)

    sigma_ln = float(LOGNORMAL_SIGMA_BY_POS.get(pos_clean, 0.26))
    mu_ln = math.log(max(1.0, mediana_proyectada))

    seed = _generar_semilla_jugador(team_abbr, opp_abbr, player_name, metrica)
    rng = np.random.default_rng(seed)
    sim_yardas = rng.lognormal(mean=mu_ln, sigma=sigma_ln, size=int(n_sims))

    mediana_mc = round(float(np.median(sim_yardas)), 1)
    media_mc = round(float(np.mean(sim_yardas)), 1)
    std_mc = round(float(np.std(sim_yardas)), 1)

    no_push = sim_yardas[sim_yardas != linea_mercado]
    if len(no_push) > 0:
        over_emp = float(np.mean(no_push > linea_mercado))
    else:
        over_emp = 0.50

    over_prob = float(np.clip(0.50 + 0.88 * (over_emp - 0.50), 0.10, 0.90))
    under_prob = float(np.clip(1.0 - over_prob, 0.10, 0.90))

    over_cover_pct = round(over_prob * 100.0, 1)
    under_cover_pct = round(under_prob * 100.0, 1)

    ev_over_pct = round(((over_prob * float(cuota_over_dec)) - 1.0) * 100.0, 1)
    ev_under_pct = round(((under_prob * float(cuota_under_dec)) - 1.0) * 100.0, 1)

    if over_cover_pct >= under_cover_pct:
        lado_mejor = "OVER"
        pct_cubre_mejor = over_cover_pct
        ev_mejor_pct = ev_over_pct
        cuota_mejor = float(cuota_over_dec)
    else:
        lado_mejor = "UNDER"
        pct_cubre_mejor = under_cover_pct
        ev_mejor_pct = ev_under_pct
        cuota_mejor = float(cuota_under_dec)

    # REGLA: PROTECCIÓN AL RECEPTOR ÉLITE (ALPHA RECEIVER FILTER)
    # Prohibido emitir señales de UNDER si Role_Share >= 26.0% y Línea Mercado < 72.5 yardas.
    veto_alpha_under = False
    if es_alpha_receiver and lado_mejor == "UNDER" and linea_mercado < ALPHA_RECEIVER_MIN_UNDER_LINE:
        veto_alpha_under = True
        notas_ajuste.append("VETO_UNDER_ALPHA(<72.5yds)")

    # Protección adicional: prohibido emitir OVER en QBs suplentes
    veto_backup_qb_over = False
    if pos_clean == "QB" and es_qb_suplente and lado_mejor == "OVER":
        veto_backup_qb_over = True
        notas_ajuste.append("VETO_OVER_QB_BACKUP")

    # REGLA 1: POLÍTICA DE FILTRADO POR VALOR POSITIVO (+EV > 0.0% y % Cubre >= 54.5%)
    tiene_valor_positivo = (
        (not veto_alpha_under)
        and (not veto_backup_qb_over)
        and (pct_cubre_mejor >= POSITIVE_EV_MIN_COVER_PCT)
        and (ev_mejor_pct > POSITIVE_EV_MIN_EV_PCT)
    )

    edge_implicito_pct = round(pct_cubre_mejor - BREAKEVEN_IMPLIED_PROB_PCT, 1)
    es_destacado = tiene_valor_positivo

    if veto_alpha_under:
        senal_ev = (
            f"🛡️ ALPHA WR PROTEGIDO (Sin Under <72.5) | OVER {linea_mercado:.1f} ({over_cover_pct:.1f}%)"
        )
    elif veto_backup_qb_over:
        senal_ev = (
            f"⚪ QB SUPLENTE (Volumen Recortado -18%) | {lado_mejor} {linea_mercado:.1f} ({pct_cubre_mejor:.1f}%)"
        )
    elif es_destacado:
        senal_ev = (
            f"🔥 {lado_mejor} {linea_mercado:.1f} | Cubre: {pct_cubre_mejor:.1f}% | EV: {ev_mejor_pct:+.1f}%"
        )
    else:
        senal_ev = (
            f"⚪ {lado_mejor} {linea_mercado:.1f} | Cubre: {pct_cubre_mejor:.1f}% | EV: {ev_mejor_pct:+.1f}%"
        )

    return {
        "Kickoff": kickoff_str,
        "_Kickoff_Sort": kickoff_sort_key,
        "Partido": partido_label,
        "Equipo": team_abbr,
        "Rival": opp_abbr,
        "Jugador": player_name,
        "Posición": pos_clean,
        "Métrica": metrica,
        "Baseline_Yds": round(base_yds, 1),
        "Pass_Rate_Equipo": round(float(pass_rate_equipo), 3),
        "Pressure_Pct_Rival": round(float(pressure_pct_rival), 3),
        "Volumen_Pase_Scheme": round(volumen_pase_directo, 1),
        "Es_QB_Suplente": bool(es_qb_suplente),
        "Es_Alpha_Receiver": bool(es_alpha_receiver),
        "Veto_Alpha_Under": bool(veto_alpha_under),
        "Factor DvP Rival": round(mult_dvp, 3),
        "Proyección Mediana": mediana_proyectada,
        "Media_MC": media_mc,
        "Desviación Estándar": std_mc,
        "Línea Mercado": round(linea_mercado, 1),
        "Diferencia_Yds": diff_yardas,
        "Abs_Diferencia_Yds": abs_diff_yardas,
        "Cuota_Decimal": round(cuota_mejor, 2),
        "% Cubre Over": over_cover_pct,
        "% Cubre Under": under_cover_pct,
        "% Cubre": pct_cubre_mejor,
        "Lado_Recomendado": lado_mejor,
        "EV_%": ev_mejor_pct,
        "Edge_Implicito_%": edge_implicito_pct,
        "Tiene_Valor_Positivo": bool(tiene_valor_positivo),
        "Cumple_Calidad_Institucional": bool(tiene_valor_positivo),
        "Es_Destacado": bool(es_destacado),
        "Señal EV": senal_ev,
        "Notas_Modelo": " · ".join(notas_ajuste),
        "Role_Share": round(role_share_eff, 3),
        "Catch_Rate": round(float(catch_rate), 3),
        "Yds_Per_Unit": round(float(yds_per_unit), 2),
        "TD_Rate": round(float(td_rate), 3),
    }


def simular_prop_anytime_td(
    partido_label: str,
    team_abbr: str,
    opp_abbr: str,
    player_name: str,
    pos: str,
    td_rate: float,
    factor_dvp: float,
    es_qb_suplente: bool = False,
    kickoff_str: str = "DOM 13:00 ET",
    kickoff_sort_key: Tuple[int, int, int, int] = (0, 4, 13, 0),
    n_sims: int = 5000,
) -> Dict[str, Any]:
    """
    Simula 5,000 iteraciones Poisson/Bernoulli para el mercado 'Anytime TD' (Línea 0.5 TD).
    """
    pos_clean = pos.strip().upper()
    base_td = float(np.clip(td_rate, 0.05, 0.85))
    mult_dvp = float(np.clip(factor_dvp, 0.65, 1.55))

    penal_qb = 0.85 if (es_qb_suplente and pos_clean in ("WR", "WR1", "WR2", "TE")) else 1.0
    lambda_td = max(0.04, base_td * (0.65 + 0.35 * mult_dvp) * penal_qb)

    seed = _generar_semilla_jugador(team_abbr, opp_abbr, player_name, "Anytime_TD")
    rng = np.random.default_rng(seed)
    sim_tds = rng.poisson(lam=lambda_td, size=int(n_sims))

    prob_over_td = float(np.clip(np.mean(sim_tds >= 1), 0.08, 0.85))
    prob_under_td = float(np.clip(1.0 - prob_over_td, 0.15, 0.92))

    over_pct = round(prob_over_td * 100.0, 1)
    under_pct = round(prob_under_td * 100.0, 1)

    prob_base_mkt = float(np.clip(1.0 - math.exp(-base_td), 0.08, 0.75))
    cuota_over_mkt = round(max(1.30, (1.0 / prob_base_mkt) * 0.96), 2)

    ev_over_pct = round(((prob_over_td * cuota_over_mkt) - 1.0) * 100.0, 1)
    lado_mejor = "OVER"
    pct_cubre_mejor = over_pct
    ev_mejor_pct = ev_over_pct
    cuota_mejor = cuota_over_mkt

    linea_td = 0.5
    es_destacado = (pct_cubre_mejor >= 35.0 and ev_mejor_pct > 0.0)
    if es_destacado:
        senal_ev = f"🔥 OVER {linea_td:.1f} TD ({cuota_mejor:.2f}) | Cubre: {pct_cubre_mejor:.1f}% | EV: {ev_mejor_pct:+.1f}%"
    else:
        senal_ev = f"⚪ OVER {linea_td:.1f} TD ({cuota_mejor:.2f}) | Cubre: {pct_cubre_mejor:.1f}% | EV: {ev_mejor_pct:+.1f}%"

    return {
        "Kickoff": kickoff_str,
        "_Kickoff_Sort": kickoff_sort_key,
        "Partido": partido_label,
        "Equipo": team_abbr,
        "Rival": opp_abbr,
        "Jugador": player_name,
        "Posición": pos_clean,
        "Métrica": "Anytime TD",
        "Baseline_Yds": round(base_td, 2),
        "Pass_Rate_Equipo": 0.0,
        "Pressure_Pct_Rival": 0.0,
        "Volumen_Pase_Scheme": 0.0,
        "Es_QB_Suplente": bool(es_qb_suplente),
        "Es_Alpha_Receiver": False,
        "Veto_Alpha_Under": False,
        "Factor DvP Rival": round(mult_dvp, 3),
        "Proyección Mediana": round(lambda_td, 2),
        "Media_MC": round(float(np.mean(sim_tds)), 2),
        "Desviación Estándar": round(float(np.std(sim_tds)), 2),
        "Línea Mercado": linea_td,
        "Diferencia_Yds": round(lambda_td - linea_td, 2),
        "Abs_Diferencia_Yds": round(abs(lambda_td - linea_td), 2),
        "Cuota_Decimal": cuota_mejor,
        "% Cubre Over": over_pct,
        "% Cubre Under": under_pct,
        "% Cubre": pct_cubre_mejor,
        "Lado_Recomendado": lado_mejor,
        "EV_%": ev_mejor_pct,
        "Edge_Implicito_%": round((prob_over_td - prob_base_mkt) * 100.0, 1),
        "Tiene_Valor_Positivo": False,
        "Cumple_Calidad_Institucional": False,
        "Es_Destacado": bool(es_destacado),
        "Señal EV": senal_ev,
        "Notas_Modelo": "Anytime_TD_Poisson",
        "Role_Share": 0.0,
        "Catch_Rate": 0.0,
        "Yds_Per_Unit": 0.0,
        "TD_Rate": round(base_td, 3),
    }


def simular_player_props_partido(
    away_abbr: str,
    home_abbr: str,
    stats_por_equipo: Dict[str, Dict[str, Any]],
    df_props_baseline: pd.DataFrame,
    lineas_mercado_props: Optional[Dict[str, float]] = None,
    reporte_inactivos: Optional[Dict[str, Any]] = None,
    inactivos_extra: Optional[Set[str]] = None,
    qb_out_away: bool = False,
    qb_out_home: bool = False,
    kickoff_str: str = "DOM 13:00 ET",
    kickoff_sort_key: Tuple[int, int, int, int] = (0, 4, 13, 0),
    n_sims: int = 5000,
    incluir_anytime_td: bool = False,
) -> List[Dict[str, Any]]:
    """
    Simula los Player Props (5,000 iteraciones de Monte Carlo) para todos los titulares
    activos de Visitante (Team A) vs Local (Team B), descartando automáticamente
    jugadores inactivos ('Out', 'DNP', 'IR') en ESPN y aplicando los ajustes de calidad.
    """
    away = away_abbr.strip().upper()
    home = home_abbr.strip().upper()
    partido_label = f"{away} @ {home}"

    st_away = stats_por_equipo.get(away, stats_por_equipo.get(TEAM_ABBR_ALIASES.get(away, ""), {}))
    st_home = stats_por_equipo.get(home, stats_por_equipo.get(TEAM_ABBR_ALIASES.get(home, ""), {}))
    lineas_ext = lineas_mercado_props or {}

    resultados: List[Dict[str, Any]] = []
    if df_props_baseline is None or df_props_baseline.empty:
        return resultados

    for team_actual, opp_actual, st_own, st_rival, qb_out_flag in [
        (away, home, st_away, st_home, qb_out_away),
        (home, away, st_home, st_away, qb_out_home),
    ]:
        codigos_equipo = {team_actual}
        if team_actual in TEAM_ABBR_ALIASES:
            codigos_equipo.add(TEAM_ABBR_ALIASES[team_actual])

        df_team = df_props_baseline[df_props_baseline["Team"].isin(codigos_equipo)]
        if df_team.empty:
            continue

        qb_rows = df_team[df_team["Pos"] == "QB"]
        qb_name_team = (
            str(qb_rows.iloc[0]["Player"]).strip()
            if not qb_rows.empty
            else str(st_own.get("QB_Name", f"{team_actual} QB1")).strip()
        )
        qb_inactivo_espn = jugador_esta_inactivo(
            team_actual,
            qb_name_team,
            reporte_inactivos=reporte_inactivos,
            inactivos_extra=inactivos_extra,
        )
        es_qb_backup = es_qb_suplente_o_bajo_volumen(
            team_abbr=team_actual,
            qb_name=qb_name_team,
            reporte_inactivos=reporte_inactivos,
            qb_out_flag=(qb_out_flag or qb_inactivo_espn),
        )

        pass_rate_own = float(st_own.get("Pass_Rate", PASS_RATE_LEAGUE_BASELINE))
        pressure_pct_opp = float(st_rival.get("Pressure_Pct", 0.245))
        epa_off_own = float(st_own.get("EPA_Pass_Off", 0.05))

        wr_counter = 0
        for _, row in df_team.iterrows():
            player_name = str(row.get("Player", "")).strip()
            pos = str(row.get("Pos", "WR")).strip().upper()

            if jugador_esta_inactivo(
                team_actual,
                player_name,
                reporte_inactivos=reporte_inactivos,
                inactivos_extra=inactivos_extra,
            ):
                continue

            baseline_yds = float(row.get("Baseline_Yds", 45.0) or 45.0)
            td_rate = float(row.get("TD_Rate", 0.20) or 0.20)
            role_share = float(row.get("Role_Share", 0.25) or 0.25)
            catch_rate = float(row.get("Catch_Rate", 0.65) or 0.65)
            yds_per_unit = float(row.get("Yds_Per_Unit", 7.5) or 7.5)

            if pos.startswith("WR"):
                wr_counter += 1
            wr_rank = wr_counter if pos.startswith("WR") else 1

            factor_dvp = obtener_factor_dvp_posicion(pos, st_rival, wr_rank=wr_rank)
            linea_ext = lineas_ext.get(f"{player_name}_{pos}") or lineas_ext.get(player_name)

            prop_yds = simular_prop_jugador_lognormal(
                partido_label=partido_label,
                team_abbr=team_actual,
                opp_abbr=opp_actual,
                player_name=player_name,
                pos=pos,
                baseline_yds=baseline_yds,
                factor_dvp=factor_dvp,
                td_rate=td_rate,
                role_share=role_share,
                catch_rate=catch_rate,
                yds_per_unit=yds_per_unit,
                pass_rate_equipo=pass_rate_own,
                pressure_pct_rival=pressure_pct_opp,
                epa_off_equipo=epa_off_own,
                es_qb_suplente=es_qb_backup,
                kickoff_str=kickoff_str,
                kickoff_sort_key=kickoff_sort_key,
                linea_mercado_externa=linea_ext,
                n_sims=n_sims,
                wr_rank=wr_rank,
            )
            resultados.append(prop_yds)

            if incluir_anytime_td and pos in ("RB", "WR", "WR1", "WR2", "TE"):
                prop_td = simular_prop_anytime_td(
                    partido_label=partido_label,
                    team_abbr=team_actual,
                    opp_abbr=opp_actual,
                    player_name=player_name,
                    pos=pos,
                    td_rate=td_rate,
                    factor_dvp=factor_dvp,
                    es_qb_suplente=es_qb_backup,
                    kickoff_str=kickoff_str,
                    kickoff_sort_key=kickoff_sort_key,
                    n_sims=n_sims,
                )
                resultados.append(prop_td)

    return resultados


def ordenar_props_multinivel_por_juego(df_props: pd.DataFrame) -> pd.DataFrame:
    """
    REGLA 2: ORDENAMIENTO MULTINIVEL JERÁRQUICO:
      - 1er nivel: Horario / Kickoff ('_Kickoff_Sort' / 'Kickoff') ASCENDENTE (cronológico).
      - 2do nivel: Identificador del Partido ('Partido', ej. 'CIN @ ATL') ASCENDENTE.
      - 3er nivel: Probabilidad de cubrimiento ('% Cubre') DESCENDENTE (y desempate por 'EV_%' DESC).
    """
    if df_props is None or df_props.empty:
        return pd.DataFrame()

    df_ord = df_props.copy()
    if "_Kickoff_Sort" not in df_ord.columns:
        if "Kickoff" in df_ord.columns:
            df_ord["_Kickoff_Sort"] = [
                _parsear_clave_orden_kickoff(str(k), 0) for k in df_ord["Kickoff"]
            ]
        else:
            df_ord["Kickoff"] = "DOM 13:00 ET"
            df_ord["_Kickoff_Sort"] = [(0, 4, 13, 0)] * len(df_ord)

    df_ord = df_ord.sort_values(
        by=["_Kickoff_Sort", "Partido", "% Cubre", "EV_%"],
        ascending=[True, True, False, False],
    ).reset_index(drop=True)

    df_ord["Rank"] = range(1, len(df_ord) + 1)
    # Numeración interna dentro de cada partido (1..K por encuentro)
    df_ord["Rank_Partido"] = df_ord.groupby("Partido", sort=False).cumcount() + 1
    return df_ord


def filtrar_cartera_institucional_props(
    df_props: pd.DataFrame,
    max_picks: Optional[int] = None,
    min_picks: int = 1,
) -> pd.DataFrame:
    """
    REGLA 1: POLÍTICA DE FILTRADO POR VALOR POSITIVO (+EV > 0.0% y % Cubre >= 54.5%)
    SIN TOPE ARTIFICIAL POR JUEGO.
    Retorna TODOS los props de cada encuentro que cumplan:
      - EV_% > 0.0% y % Cubre >= 54.5% en las 5,000 simulaciones.
      - Respetando la protección a receptores Alfa (sin UNDER < 72.5 yds) y el
        bloqueo de OVER en QBs suplentes.
    Ordenado bajo el criterio jerárquico multinivel:
      1) Kickoff ASC, 2) Partido ASC, 3) % Cubre DESC.
    """
    if df_props is None or df_props.empty:
        return pd.DataFrame()

    df_work = df_props.copy()
    if "Métrica" in df_work.columns:
        df_yds = df_work[df_work["Métrica"].isin(["Pass Yds", "Rush Yds", "Rec Yds"])]
        if not df_yds.empty:
            df_work = df_yds.copy()

    if "Veto_Alpha_Under" in df_work.columns:
        df_work = df_work[~df_work["Veto_Alpha_Under"].astype(bool)]
    if "Es_QB_Suplente" in df_work.columns and "Posición" in df_work.columns and "Lado_Recomendado" in df_work.columns:
        mask_backup_over = (
            (df_work["Posición"] == "QB")
            & (df_work["Es_QB_Suplente"].astype(bool))
            & (df_work["Lado_Recomendado"] == "OVER")
        )
        df_work = df_work[~mask_backup_over]

    mask_ev_pos = (
        (df_work["% Cubre"] >= POSITIVE_EV_MIN_COVER_PCT)
        & (df_work["EV_%"] > POSITIVE_EV_MIN_EV_PCT)
    )
    df_positivos = df_work[mask_ev_pos].copy()

    df_ordenado = ordenar_props_multinivel_por_juego(df_positivos)
    if max_picks is not None and max_picks > 0 and len(df_ordenado) > max_picks:
        df_ordenado = df_ordenado.head(max_picks).copy()
        df_ordenado["Rank"] = range(1, len(df_ordenado) + 1)

    return df_ordenado


def simular_player_props_jornada(
    partidos_jornada: List[Dict[str, Any]],
    excel_path: Optional[str] = None,
    n_sims: int = 5000,
    incluir_anytime_td: bool = False,
    solo_cartera_institucional: bool = False,
    consultar_espn_inactivos: bool = True,
    inactivos_extra: Optional[Set[str]] = None,
) -> pd.DataFrame:
    """
    Ejecuta las 5,000 simulaciones de Monte Carlo de Player Props para los partidos
    activos de la jornada y retorna el DataFrame ordenado cronológicamente por juego
    ('Kickoff' ASC -> 'Partido' ASC -> '% Cubre' DESC).
    """
    stats_por_equipo, df_props_baseline = cargar_datos_props_nfl(excel_path=excel_path)
    reporte_inactivos = (
        consultar_inactivos_espn_nfl() if consultar_espn_inactivos else None
    )

    todas_las_filas: List[Dict[str, Any]] = []
    partidos_vistos: Set[str] = set()

    for idx_cal, partido in enumerate(partidos_jornada or []):
        away = str(partido.get("away_abbr", "")).strip().upper()
        home = str(partido.get("home_abbr", "")).strip().upper()
        if not away or not home:
            continue
        match_key = f"{away}_{home}"
        if match_key in partidos_vistos:
            continue
        partidos_vistos.add(match_key)

        kickoff_txt = str(partido.get("hora", partido.get("Kickoff", "DOM 13:00 ET"))).strip()
        kickoff_sort_tuple = _parsear_clave_orden_kickoff(kickoff_txt, idx_calendario=idx_cal)

        qb_out_away = bool(partido.get("qb_out_away", False)) or (
            str(partido.get("qb_status_away", "")).upper() in {"OUT", "IR", "OUT / SUPLENTE", "DOUBTFUL"}
        )
        qb_out_home = bool(partido.get("qb_out_home", False)) or (
            str(partido.get("qb_status_home", "")).upper() in {"OUT", "IR", "OUT / SUPLENTE", "DOUBTFUL"}
        )

        filas_partido = simular_player_props_partido(
            away_abbr=away,
            home_abbr=home,
            stats_por_equipo=stats_por_equipo,
            df_props_baseline=df_props_baseline,
            reporte_inactivos=reporte_inactivos,
            inactivos_extra=inactivos_extra,
            qb_out_away=qb_out_away,
            qb_out_home=qb_out_home,
            kickoff_str=kickoff_txt,
            kickoff_sort_key=kickoff_sort_tuple,
            n_sims=n_sims,
            incluir_anytime_td=incluir_anytime_td,
        )
        todas_las_filas.extend(filas_partido)

    if not todas_las_filas:
        return pd.DataFrame(
            columns=[
                "Rank",
                "Kickoff",
                "Partido",
                "Jugador",
                "Equipo",
                "Rival",
                "Posición",
                "Métrica",
                "Proyección Mediana",
                "Desviación Estándar",
                "Factor DvP Rival",
                "Línea Mercado",
                "Diferencia_Yds",
                "% Cubre Over",
                "% Cubre Under",
                "% Cubre",
                "EV_%",
                "Señal EV",
            ]
        )

    df_res = pd.DataFrame(todas_las_filas)
    if solo_cartera_institucional:
        return filtrar_cartera_institucional_props(df_res)

    return ordenar_props_multinivel_por_juego(df_res)


def build_player_props_ranking_export_df(
    df_props: pd.DataFrame,
    max_picks: Optional[int] = None,
) -> pd.DataFrame:
    """
    Formatea el DataFrame de Player Props para la hoja de Excel 'Player_Props_Ranking',
    emitiendo TODOS los props con ventaja matemática positiva (+EV > 0.0% y % Cubre >= 54.5%)
    sin límite artificial por partido, y ordenado bajo los 3 niveles jerárquicos:
      1er nivel: 'Kickoff' ASCENDENTE (cronológico).
      2do nivel: 'Partido' ASCENDENTE (agrupado en bloque por encuentro).
      3er nivel: '% Cubre' DESCENDENTE (mayor probabilidad arriba dentro de cada juego).
    """
    cols_export = [
        "Rank",
        "Kickoff",
        "Partido",
        "Rank_Partido",
        "Jugador",
        "Equipo",
        "Rival",
        "Posición",
        "Métrica",
        "Baseline_Yds",
        "Proyección Mediana",
        "Línea Mercado",
        "Diferencia_Yds",
        "Desviación Estándar",
        "Factor DvP Rival",
        "% Cubre Over",
        "% Cubre Under",
        "% Cubre",
        "Lado_Recomendado",
        "EV_%",
        "Señal EV",
        "Notas_Modelo",
    ]
    if df_props is None or df_props.empty:
        return pd.DataFrame(columns=cols_export)

    df_inst = filtrar_cartera_institucional_props(df_props, max_picks=max_picks)
    if df_inst.empty:
        df_inst = ordenar_props_multinivel_por_juego(
            df_props[df_props.get("Métrica", "") != "Anytime TD"].copy()
        )

    cols_presentes = [c for c in cols_export if c in df_inst.columns]
    return df_inst[cols_presentes]


def estilizar_hoja_player_props_openpyxl(ws: Any) -> None:
    """
    REGLA 3: FORMATO VISUAL DE SEPARACIÓN EN EXCEL (openpyxl).
    Aplica alternancia de sombreado por bloque de partido y un borde inferior grueso
    cada vez que cambia el encuentro ('Partido') para separar visualmente los bloques
    de 6 a 8 props de cada juego.
    """
    if ws is None or ws.max_row < 2:
        return

    header_fill = PatternFill(start_color="0D1117", end_color="0D1117", fill_type="solid")
    header_font = Font(name="Consolas", size=10, bold=True, color="00FFCC")

    block_fill_even = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
    block_fill_odd = PatternFill(start_color="EAF4F4", end_color="EAF4F4", fill_type="solid")

    thin_side = Side(style="thin", color="CBD5E1")
    thick_bottom_side = Side(style="medium", color="0F766E")

    border_regular = Border(
        left=thin_side,
        right=thin_side,
        top=thin_side,
        bottom=thin_side,
    )
    border_end_of_game = Border(
        left=thin_side,
        right=thin_side,
        top=thin_side,
        bottom=thick_bottom_side,
    )

    # Identificar el índice de la columna 'Partido' (1-indexed)
    col_partido_idx = None
    for col_idx in range(1, ws.max_column + 1):
        cell_hdr = ws.cell(row=1, column=col_idx)
        cell_hdr.fill = header_fill
        cell_hdr.font = header_font
        cell_hdr.alignment = Alignment(horizontal="center", vertical="center")
        if str(cell_hdr.value or "").strip() == "Partido":
            col_partido_idx = col_idx

    if col_partido_idx is None:
        return

    bloque_idx = 0
    max_r = ws.max_row
    max_c = ws.max_column

    for r_idx in range(2, max_r + 1):
        partido_actual = str(ws.cell(row=r_idx, column=col_partido_idx).value or "").strip()
        partido_sig = (
            str(ws.cell(row=r_idx + 1, column=col_partido_idx).value or "").strip()
            if r_idx < max_r
            else ""
        )
        cambia_partido = (r_idx == max_r) or (partido_actual != partido_sig)

        fill_actual = block_fill_even if (bloque_idx % 2 == 0) else block_fill_odd
        borde_actual = border_end_of_game if cambia_partido else border_regular

        for c_idx in range(1, max_c + 1):
            c = ws.cell(row=r_idx, column=c_idx)
            c.fill = fill_actual
            c.border = borde_actual

        if cambia_partido:
            bloque_idx += 1

    # Ajuste automático de ancho de columnas
    for c_idx in range(1, max_c + 1):
        col_letter = get_column_letter(c_idx)
        max_len = max(
            len(str(ws.cell(row=r_i, column=c_idx).value or ""))
            for r_i in range(1, min(max_r + 1, 120))
        )
        ws.column_dimensions[col_letter].width = max(11, min(42, max_len + 3))


def obtener_top_3_player_props_jornada(df_props: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Selecciona los 3 Player Props con mayor probabilidad matemática de acierto ('% Cubre')
    de toda la jornada para destacar en la cabecera ejecutiva.
    """
    if df_props is None or df_props.empty:
        return []

    df_cand = filtrar_cartera_institucional_props(df_props)
    if df_cand.empty:
        df_cand = df_props.copy()

    df_cand = df_cand.sort_values(
        by=["% Cubre", "EV_%"], ascending=[False, False]
    ).reset_index(drop=True)

    top_3: List[Dict[str, Any]] = []
    jugadores_vistos: Set[str] = set()
    for _, row in df_cand.iterrows():
        jug = str(row.get("Jugador", ""))
        if jug in jugadores_vistos:
            continue
        jugadores_vistos.add(jug)
        top_3.append(
            {
                "kickoff": str(row.get("Kickoff", "DOM")),
                "partido": str(row.get("Partido", "")),
                "jugador": jug,
                "equipo": str(row.get("Equipo", "")),
                "rival": str(row.get("Rival", "")),
                "posicion": str(row.get("Posición", "")),
                "metrica": str(row.get("Métrica", "")),
                "mediana_proy": float(row.get("Proyección Mediana", 0.0)),
                "std_dev": float(row.get("Desviación Estándar", 0.0)),
                "factor_dvp": float(row.get("Factor DvP Rival", 1.0)),
                "linea": float(row.get("Línea Mercado", 0.0)),
                "diff_yds": float(row.get("Diferencia_Yds", 0.0)),
                "lado": str(row.get("Lado_Recomendado", "OVER")),
                "pct_cubre": float(row.get("% Cubre", 50.0)),
                "pct_over": float(row.get("% Cubre Over", 50.0)),
                "pct_under": float(row.get("% Cubre Under", 50.0)),
                "ev_pct": float(row.get("EV_%", 0.0)),
                "senal_ev": str(row.get("Señal EV", "")),
                "notas_modelo": str(row.get("Notas_Modelo", "")),
            }
        )
        if len(top_3) == 3:
            break

    return top_3
