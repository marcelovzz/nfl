#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MÓDULO 2: engine_nfl.py
Motor Cuantitativo NFL (5,000 iteraciones Poisson / Monte Carlo con ventaja de
localía y diferenciales de EPA) y Parser/Validador de archivos Excel (.xlsx).
"""

import io
import math
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd

from sync_espn_nfl import NFL_FRANCHISE_NAMES, normalizar_abbr_nfl

REQUIRED_EXCEL_COLUMNS: List[str] = [
    "Team_Abbr",
    "QB_Name",
    "EPA_Pass_Off",
    "EPA_Rush_Off",
    "EPA_Pass_Def",
    "EPA_Rush_Def",
    "Success_Rate_Off",
    "Success_Rate_Def",
    "Pace_Sec",
]

# Dataset base realista para las 32 franquicias NFL (usado como plantilla inicial
# y respaldo inmediato antes de cargar un archivo nfl_stats.xlsx personalizado)
DEFAULT_NFL_STATS_ROWS: List[Dict[str, Any]] = [
    {"Team_Abbr": "KC",  "QB_Name": "P. Mahomes",       "EPA_Pass_Off": 0.195, "EPA_Rush_Off": 0.015, "EPA_Pass_Def": -0.065, "EPA_Rush_Def": -0.040, "Success_Rate_Off": 0.505, "Success_Rate_Def": 0.415, "Pace_Sec": 26.8},
    {"Team_Abbr": "SF",  "QB_Name": "B. Purdy",         "EPA_Pass_Off": 0.210, "EPA_Rush_Off": 0.065, "EPA_Pass_Def": -0.070, "EPA_Rush_Def": -0.055, "Success_Rate_Off": 0.515, "Success_Rate_Def": 0.410, "Pace_Sec": 28.4},
    {"Team_Abbr": "BUF", "QB_Name": "J. Allen",         "EPA_Pass_Off": 0.180, "EPA_Rush_Off": 0.045, "EPA_Pass_Def": -0.040, "EPA_Rush_Def": -0.025, "Success_Rate_Off": 0.498, "Success_Rate_Def": 0.430, "Pace_Sec": 26.5},
    {"Team_Abbr": "BAL", "QB_Name": "L. Jackson",       "EPA_Pass_Off": 0.165, "EPA_Rush_Off": 0.095, "EPA_Pass_Def": -0.085, "EPA_Rush_Def": -0.060, "Success_Rate_Off": 0.502, "Success_Rate_Def": 0.405, "Pace_Sec": 27.9},
    {"Team_Abbr": "DET", "QB_Name": "J. Goff",          "EPA_Pass_Off": 0.175, "EPA_Rush_Off": 0.055, "EPA_Pass_Def": -0.020, "EPA_Rush_Def": -0.050, "Success_Rate_Off": 0.508, "Success_Rate_Def": 0.435, "Pace_Sec": 26.9},
    {"Team_Abbr": "PHI", "QB_Name": "J. Hurts",         "EPA_Pass_Off": 0.145, "EPA_Rush_Off": 0.075, "EPA_Pass_Def": -0.035, "EPA_Rush_Def": -0.045, "Success_Rate_Off": 0.492, "Success_Rate_Def": 0.428, "Pace_Sec": 26.6},
    {"Team_Abbr": "DAL", "QB_Name": "D. Prescott",      "EPA_Pass_Off": 0.150, "EPA_Rush_Off": -0.010, "EPA_Pass_Def": -0.030, "EPA_Rush_Def": 0.010, "Success_Rate_Off": 0.485, "Success_Rate_Def": 0.440, "Pace_Sec": 26.1},
    {"Team_Abbr": "CIN", "QB_Name": "J. Burrow",        "EPA_Pass_Off": 0.170, "EPA_Rush_Off": -0.015, "EPA_Pass_Def": 0.010,  "EPA_Rush_Def": 0.005, "Success_Rate_Off": 0.490, "Success_Rate_Def": 0.452, "Pace_Sec": 26.7},
    {"Team_Abbr": "HOU", "QB_Name": "C. Stroud",        "EPA_Pass_Off": 0.155, "EPA_Rush_Off": -0.005, "EPA_Pass_Def": -0.035, "EPA_Rush_Def": -0.030, "Success_Rate_Off": 0.482, "Success_Rate_Def": 0.432, "Pace_Sec": 27.1},
    {"Team_Abbr": "GB",  "QB_Name": "J. Love",          "EPA_Pass_Off": 0.160, "EPA_Rush_Off": 0.025, "EPA_Pass_Def": -0.015, "EPA_Rush_Def": 0.010, "Success_Rate_Off": 0.488, "Success_Rate_Def": 0.445, "Pace_Sec": 27.3},
    {"Team_Abbr": "MIA", "QB_Name": "T. Tagovailoa",    "EPA_Pass_Off": 0.165, "EPA_Rush_Off": 0.035, "EPA_Pass_Def": -0.010, "EPA_Rush_Def": -0.015, "Success_Rate_Off": 0.494, "Success_Rate_Def": 0.442, "Pace_Sec": 25.9},
    {"Team_Abbr": "LA",  "QB_Name": "M. Stafford",      "EPA_Pass_Off": 0.135, "EPA_Rush_Off": 0.020, "EPA_Pass_Def": 0.015,  "EPA_Rush_Def": 0.005, "Success_Rate_Off": 0.480, "Success_Rate_Def": 0.450, "Pace_Sec": 27.2},
    {"Team_Abbr": "MIN", "QB_Name": "S. Darnold",       "EPA_Pass_Off": 0.115, "EPA_Rush_Off": -0.010, "EPA_Pass_Def": -0.045, "EPA_Rush_Def": -0.030, "Success_Rate_Off": 0.472, "Success_Rate_Def": 0.425, "Pace_Sec": 26.8},
    {"Team_Abbr": "NYJ", "QB_Name": "A. Rodgers",       "EPA_Pass_Off": 0.085, "EPA_Rush_Off": -0.015, "EPA_Pass_Def": -0.080, "EPA_Rush_Def": -0.045, "Success_Rate_Off": 0.455, "Success_Rate_Def": 0.408, "Pace_Sec": 28.1},
    {"Team_Abbr": "CLE", "QB_Name": "J. Winston",       "EPA_Pass_Off": 0.040, "EPA_Rush_Off": -0.020, "EPA_Pass_Def": -0.075, "EPA_Rush_Def": -0.050, "Success_Rate_Off": 0.442, "Success_Rate_Def": 0.412, "Pace_Sec": 27.6},
    {"Team_Abbr": "PIT", "QB_Name": "R. Wilson",        "EPA_Pass_Off": 0.075, "EPA_Rush_Off": 0.015, "EPA_Pass_Def": -0.065, "EPA_Rush_Def": -0.040, "Success_Rate_Off": 0.458, "Success_Rate_Def": 0.418, "Pace_Sec": 28.0},
    {"Team_Abbr": "ATL", "QB_Name": "K. Cousins",       "EPA_Pass_Off": 0.110, "EPA_Rush_Off": 0.020, "EPA_Pass_Def": 0.010,  "EPA_Rush_Def": 0.005, "Success_Rate_Off": 0.475, "Success_Rate_Def": 0.448, "Pace_Sec": 27.0},
    {"Team_Abbr": "CHI", "QB_Name": "C. Williams",      "EPA_Pass_Off": 0.055, "EPA_Rush_Off": 0.005, "EPA_Pass_Def": -0.040, "EPA_Rush_Def": -0.035, "Success_Rate_Off": 0.452, "Success_Rate_Def": 0.428, "Pace_Sec": 27.4},
    {"Team_Abbr": "JAX", "QB_Name": "T. Lawrence",      "EPA_Pass_Off": 0.080, "EPA_Rush_Off": -0.010, "EPA_Pass_Def": 0.025,  "EPA_Rush_Def": 0.010, "Success_Rate_Off": 0.464, "Success_Rate_Def": 0.458, "Pace_Sec": 26.9},
    {"Team_Abbr": "IND", "QB_Name": "A. Richardson",    "EPA_Pass_Off": 0.065, "EPA_Rush_Off": 0.040, "EPA_Pass_Def": 0.020,  "EPA_Rush_Def": 0.015, "Success_Rate_Off": 0.460, "Success_Rate_Def": 0.455, "Pace_Sec": 26.3},
    {"Team_Abbr": "SEA", "QB_Name": "G. Smith",         "EPA_Pass_Off": 0.095, "EPA_Rush_Off": 0.005, "EPA_Pass_Def": 0.015,  "EPA_Rush_Def": 0.020, "Success_Rate_Off": 0.470, "Success_Rate_Def": 0.456, "Pace_Sec": 26.7},
    {"Team_Abbr": "TB",  "QB_Name": "B. Mayfield",      "EPA_Pass_Off": 0.125, "EPA_Rush_Off": -0.005, "EPA_Pass_Def": 0.010,  "EPA_Rush_Def": -0.020, "Success_Rate_Off": 0.478, "Success_Rate_Def": 0.445, "Pace_Sec": 26.8},
    {"Team_Abbr": "WAS", "QB_Name": "J. Daniels",       "EPA_Pass_Off": 0.140, "EPA_Rush_Off": 0.060, "EPA_Pass_Def": 0.035,  "EPA_Rush_Def": 0.025, "Success_Rate_Off": 0.488, "Success_Rate_Def": 0.465, "Pace_Sec": 26.2},
    {"Team_Abbr": "ARI", "QB_Name": "K. Murray",        "EPA_Pass_Off": 0.090, "EPA_Rush_Off": 0.045, "EPA_Pass_Def": 0.045,  "EPA_Rush_Def": 0.035, "Success_Rate_Off": 0.468, "Success_Rate_Def": 0.472, "Pace_Sec": 26.6},
    {"Team_Abbr": "LAC", "QB_Name": "J. Herbert",       "EPA_Pass_Off": 0.120, "EPA_Rush_Off": 0.015, "EPA_Pass_Def": -0.030, "EPA_Rush_Def": -0.025, "Success_Rate_Off": 0.474, "Success_Rate_Def": 0.432, "Pace_Sec": 27.8},
    {"Team_Abbr": "NO",  "QB_Name": "D. Carr",          "EPA_Pass_Off": 0.070, "EPA_Rush_Off": -0.010, "EPA_Pass_Def": -0.025, "EPA_Rush_Def": -0.015, "Success_Rate_Off": 0.456, "Success_Rate_Def": 0.436, "Pace_Sec": 27.3},
    {"Team_Abbr": "LV",  "QB_Name": "G. Minshew",       "EPA_Pass_Off": -0.015,"EPA_Rush_Off": -0.030, "EPA_Pass_Def": 0.005,  "EPA_Rush_Def": 0.010, "Success_Rate_Off": 0.432, "Success_Rate_Def": 0.448, "Pace_Sec": 27.5},
    {"Team_Abbr": "DEN", "QB_Name": "B. Nix",           "EPA_Pass_Off": 0.045, "EPA_Rush_Off": 0.010, "EPA_Pass_Def": -0.055, "EPA_Rush_Def": -0.030, "Success_Rate_Off": 0.448, "Success_Rate_Def": 0.422, "Pace_Sec": 27.4},
    {"Team_Abbr": "TEN", "QB_Name": "W. Levis",         "EPA_Pass_Off": -0.025,"EPA_Rush_Off": -0.015, "EPA_Pass_Def": 0.015,  "EPA_Rush_Def": -0.010, "Success_Rate_Off": 0.428, "Success_Rate_Def": 0.446, "Pace_Sec": 27.9},
    {"Team_Abbr": "NE",  "QB_Name": "D. Maye",          "EPA_Pass_Off": -0.010,"EPA_Rush_Off": -0.020, "EPA_Pass_Def": 0.010,  "EPA_Rush_Def": -0.015, "Success_Rate_Off": 0.435, "Success_Rate_Def": 0.442, "Pace_Sec": 28.2},
    {"Team_Abbr": "NYG", "QB_Name": "D. Jones",         "EPA_Pass_Off": -0.035,"EPA_Rush_Off": -0.025, "EPA_Pass_Def": 0.025,  "EPA_Rush_Def": 0.020, "Success_Rate_Off": 0.425, "Success_Rate_Def": 0.458, "Pace_Sec": 27.7},
    {"Team_Abbr": "CAR", "QB_Name": "B. Young",         "EPA_Pass_Off": -0.055,"EPA_Rush_Off": -0.030, "EPA_Pass_Def": 0.050,  "EPA_Rush_Def": 0.040, "Success_Rate_Off": 0.415, "Success_Rate_Def": 0.475, "Pace_Sec": 28.1},
]


def _normalizar_tasa(valor: float) -> float:
    """Convierte porcentajes en escala 0-100 a decimal 0-1 si es necesario."""
    v = float(valor)
    return v / 100.0 if v > 1.5 else v


def prob_a_fair_odds(prob: float) -> Tuple[float, str]:
    """Convierte una probabilidad (0 a 1) en Momio Justo Decimal y Americano."""
    p = float(np.clip(prob, 0.01, 0.99))
    dec = round(1.0 / p, 2)
    if p >= 0.5:
        am = -int(round((p / (1.0 - p)) * 100.0))
        return dec, f"{am}"
    am = int(round(((1.0 - p) / p) * 100.0))
    return dec, f"+{am}"


def validar_y_parsear_excel_nfl(df_excel: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """
    Valida que el DataFrame proveniente de 'nfl_stats.xlsx' contenga las columnas:
    ['Team_Abbr', 'QB_Name', 'EPA_Pass_Off', 'EPA_Rush_Off', 'EPA_Pass_Def',
     'EPA_Rush_Def', 'Success_Rate_Off', 'Success_Rate_Def', 'Pace_Sec']
    Retorna un diccionario indexado por 'Team_Abbr' estandarizado para consulta rápida.
    """
    if df_excel is None or df_excel.empty:
        raise ValueError("El archivo Excel proporcionado está vacío.")

    df = df_excel.copy()
    df.columns = [str(c).strip() for c in df.columns]

    faltantes = [col for col in REQUIRED_EXCEL_COLUMNS if col not in df.columns]
    if faltantes:
        raise ValueError(
            f"El archivo Excel no contiene las columnas obligatorias: {', '.join(faltantes)}. "
            f"Columnas requeridas: {', '.join(REQUIRED_EXCEL_COLUMNS)}"
        )

    stats_dict: Dict[str, Dict[str, Any]] = {}
    for _, row in df.dropna(subset=["Team_Abbr"]).iterrows():
        raw_abbr = str(row["Team_Abbr"]).strip().upper()
        std_abbr = normalizar_abbr_nfl(raw_abbr)

        entry = {
            "Team_Abbr": std_abbr,
            "Team_Name": str(row.get("Team_Name", NFL_FRANCHISE_NAMES.get(std_abbr, std_abbr))),
            "QB_Name": str(row["QB_Name"]).strip() if pd.notna(row["QB_Name"]) else f"{std_abbr} QB1",
            "EPA_Pass_Off": float(row["EPA_Pass_Off"]),
            "EPA_Rush_Off": float(row["EPA_Rush_Off"]),
            "EPA_Pass_Def": float(row["EPA_Pass_Def"]),
            "EPA_Rush_Def": float(row["EPA_Rush_Def"]),
            "Success_Rate_Off": _normalizar_tasa(float(row["Success_Rate_Off"])),
            "Success_Rate_Def": _normalizar_tasa(float(row["Success_Rate_Def"])),
            "Pace_Sec": float(np.clip(float(row["Pace_Sec"]), 22.0, 33.0)),
        }
        stats_dict[std_abbr] = entry
        # Guardar también alias comunes (ej. LAR / LA, WSH / WAS) para evitar KeyErrors
        if std_abbr == "LA":
            stats_dict["LAR"] = entry
        elif std_abbr == "WAS":
            stats_dict["WSH"] = entry

    return stats_dict


def obtener_stats_nfl_default() -> Dict[str, Dict[str, Any]]:
    """Retorna el diccionario base validado para las 32 franquicias de la NFL."""
    df_def = pd.DataFrame(DEFAULT_NFL_STATS_ROWS)
    return validar_y_parsear_excel_nfl(df_def)


def generar_plantilla_excel_bytes(nfl_stats_dict: Dict[str, Dict[str, Any]]) -> bytes:
    """Genera un archivo Excel (.xlsx) en memoria con la estructura exacta requerida."""
    filas = []
    vistos = set()
    for abbr, data in nfl_stats_dict.items():
        std_abbr = normalizar_abbr_nfl(abbr)
        if std_abbr in vistos:
            continue
        vistos.add(std_abbr)
        filas.append({col: data[col] for col in REQUIRED_EXCEL_COLUMNS})
    df_export = pd.DataFrame(filas)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_export.to_excel(writer, index=False, sheet_name="NFL_Stats")
    return buffer.getvalue()


def run_simulacion_nfl(
    away_abbr: str,
    home_abbr: str,
    nfl_stats_dict: Dict[str, Dict[str, Any]],
    n_sims: int = 5000,
) -> Dict[str, Any]:
    """
    Corre 5,000 iteraciones (Poisson / Monte Carlo por posesiones NFL) con ventaja
    de localía (~1.8 pts) y diferenciales de EPA y Success Rate.
    Retorna:
      - away_pts, home_pts, win_home_pct, spread_proyectado, total_ou, QBs titulares
      - y métricas extendidas para el Expediente Cuantitativo (Vista B).
    """
    away_key = normalizar_abbr_nfl(away_abbr)
    home_key = normalizar_abbr_nfl(home_abbr)

    default_pool = obtener_stats_nfl_default()
    away_st = nfl_stats_dict.get(away_key) or nfl_stats_dict.get(away_abbr) or default_pool.get(away_key, DEFAULT_NFL_STATS_ROWS[0])
    home_st = nfl_stats_dict.get(home_key) or nfl_stats_dict.get(home_abbr) or default_pool.get(home_key, DEFAULT_NFL_STATS_ROWS[1])

    away_qb = str(away_st.get("QB_Name", f"{away_key} QB1"))
    home_qb = str(home_st.get("QB_Name", f"{home_key} QB1"))

    # 1. Ritmo de juego y volumen proyectado de jugadas (Pace_Sec)
    pace_away = float(away_st["Pace_Sec"])
    pace_home = float(home_st["Pace_Sec"])
    pace_promedio = (pace_away + pace_home) / 2.0
    snaps_por_equipo = 63.5 * (27.2 / max(23.5, pace_promedio))

    # 2. Diferenciales de EPA (Pase 58% / Carrera 42%) y Success Rate
    pass_weight = 0.58
    rush_weight = 0.42

    net_pass_epa_away = float(away_st["EPA_Pass_Off"]) + float(home_st["EPA_Pass_Def"])
    net_rush_epa_away = float(away_st["EPA_Rush_Off"]) + float(home_st["EPA_Rush_Def"])
    sr_edge_away = (_normalizar_tasa(away_st["Success_Rate_Off"]) - _normalizar_tasa(home_st["Success_Rate_Def"])) * 0.45
    epa_comp_away = pass_weight * net_pass_epa_away + rush_weight * net_rush_epa_away + sr_edge_away

    net_pass_epa_home = float(home_st["EPA_Pass_Off"]) + float(away_st["EPA_Pass_Def"])
    net_rush_epa_home = float(home_st["EPA_Rush_Off"]) + float(away_st["EPA_Rush_Def"])
    sr_edge_home = (_normalizar_tasa(home_st["Success_Rate_Off"]) - _normalizar_tasa(away_st["Success_Rate_Def"])) * 0.45
    epa_comp_home = pass_weight * net_pass_epa_home + rush_weight * net_rush_epa_home + sr_edge_home

    # 3. Puntos esperados con ventaja de localía NFL (~1.8 puntos base)
    hfa_nfl = 1.80
    base_pts = snaps_por_equipo * 0.352

    expected_away_pts = base_pts + (epa_comp_away * snaps_por_equipo * 0.85) - (hfa_nfl / 2.0)
    expected_home_pts = base_pts + (epa_comp_home * snaps_por_equipo * 0.85) + (hfa_nfl / 2.0)

    expected_away_pts = float(np.clip(expected_away_pts, 12.0, 37.5))
    expected_home_pts = float(np.clip(expected_home_pts, 13.0, 38.5))

    # 4. Simulación híbrida Poisson / Monte Carlo (5,000 iteraciones)
    seed_val = abs(hash(f"{away_key}_{home_key}_{expected_away_pts:.3f}_{expected_home_pts:.3f}_{n_sims}")) % (2**31 - 1)
    rng = np.random.default_rng(seed_val)

    # Tasas Poisson de Touchdowns (~7 pts) y Field Goals (~3 pts)
    lam_td_away = max(0.65, (expected_away_pts * 0.71) / 6.96)
    lam_fg_away = max(0.45, (expected_away_pts * 0.29) / 3.00)

    lam_td_home = max(0.70, (expected_home_pts * 0.71) / 6.96)
    lam_fg_home = max(0.45, (expected_home_pts * 0.29) / 3.00)

    tds_away = rng.poisson(lam=lam_td_away, size=n_sims)
    fgs_away = rng.poisson(lam=lam_fg_away, size=n_sims)
    safeties_away = rng.binomial(1, 0.018, size=n_sims) * 2
    sim_away = tds_away * 7 + fgs_away * 3 + safeties_away

    tds_home = rng.poisson(lam=lam_td_home, size=n_sims)
    fgs_home = rng.poisson(lam=lam_fg_home, size=n_sims)
    safeties_home = rng.binomial(1, 0.018, size=n_sims) * 2
    sim_home = tds_home * 7 + fgs_home * 3 + safeties_home

    # Resolución de empates en Tiempo Extra (Overtime NFL)
    ties_mask = sim_away == sim_home
    n_ties = int(ties_mask.sum())
    ot_pct = round((n_ties / float(n_sims)) * 100.0, 1)
    if n_ties > 0:
        p_home_ot = float(np.clip(0.51 + (expected_home_pts - expected_away_pts) * 0.015, 0.35, 0.65))
        home_wins_ot = rng.random(n_ties) < p_home_ot
        ot_pts = rng.choice([3, 6], size=n_ties, p=[0.66, 0.34])
        sim_home[ties_mask] += np.where(home_wins_ot, ot_pts, 0)
        sim_away[ties_mask] += np.where(~home_wins_ot, ot_pts, 0)

    away_pts = round(float(np.mean(sim_away)), 1)
    home_pts = round(float(np.mean(sim_home)), 1)

    win_home_raw = float(np.mean(sim_home > sim_away))
    win_home_pct = round(win_home_raw * 100.0, 1)
    win_away_pct = round((1.0 - win_home_raw) * 100.0, 1)

    # Spread proyectado desde la perspectiva del equipo Local (negativo = Local favorito)
    spread_proyectado = round(-(home_pts - away_pts), 1)
    total_ou = round(home_pts + away_pts, 1)

    # Línea de referencia estándar NFL para cálculo de cobertura (Spread Cover %)
    lineas_nfl_std = [-14.0, -10.5, -10.0, -7.5, -7.0, -6.5, -4.5, -3.5, -3.0, -2.5, -1.5, 1.5, 2.5, 3.0, 3.5, 4.5, 6.5, 7.0, 7.5, 10.0, 10.5, 14.0]
    spread_ref_line = min(lineas_nfl_std, key=lambda x: abs(x - (spread_proyectado * 0.88)))
    margen_sim = sim_home - sim_away
    valid_cover = (margen_sim + spread_ref_line) != 0
    cover_home_raw = float(np.mean((margen_sim[valid_cover] + spread_ref_line) > 0)) if valid_cover.sum() > 0 else 0.50
    cover_home_pct = round(cover_home_raw * 100.0, 1)
    cover_away_pct = round((1.0 - cover_home_raw) * 100.0, 1)

    # Línea de referencia Total O/U para probabilidad Over/Under
    total_ref_line = round((total_ou * 0.96) * 2.0) / 2.0
    if total_ref_line % 1.0 == 0:
        total_ref_line -= 0.5
    total_sim = sim_home + sim_away
    over_raw = float(np.mean(total_sim > total_ref_line))
    over_pct = round(over_raw * 100.0, 1)
    under_pct = round((1.0 - over_raw) * 100.0, 1)

    # Fair Odds (+EV)
    ml_home_dec, ml_home_am = prob_a_fair_odds(win_home_raw)
    ml_away_dec, ml_away_am = prob_a_fair_odds(1.0 - win_home_raw)
    sp_home_dec, sp_home_am = prob_a_fair_odds(cover_home_raw)
    sp_away_dec, sp_away_am = prob_a_fair_odds(1.0 - cover_home_raw)
    ou_over_dec, ou_over_am = prob_a_fair_odds(over_raw)
    ou_under_dec, ou_under_am = prob_a_fair_odds(1.0 - over_raw)

    # Marcador entero representativo (Key Numbers NFL)
    nfl_scores_grid = [10, 13, 14, 16, 17, 20, 21, 23, 24, 27, 28, 30, 31, 34, 35, 38]
    exact_away = min(nfl_scores_grid, key=lambda s: abs(s - away_pts))
    exact_home = min(nfl_scores_grid, key=lambda s: abs(s - home_pts))
    if exact_away == exact_home:
        if home_pts >= away_pts:
            exact_home += 3
        else:
            exact_away += 3

    # Frecuencia de Key Numbers NFL (3, 7, 10, 14, 6, 4)
    margen_abs = np.abs(margen_sim)
    key_numbers_freq = {
        f"Margen {kn} pts": round(max(2.4, float(np.mean(margen_abs == kn)) * 100.0), 1)
        for kn in [3, 7, 10, 14, 6, 4]
    }

    return {
        "away_abbr": away_key,
        "home_abbr": home_key,
        "away_name": NFL_FRANCHISE_NAMES.get(away_key, away_key),
        "home_name": NFL_FRANCHISE_NAMES.get(home_key, home_key),
        "away_qb": away_qb,
        "home_qb": home_qb,
        "away_pts": away_pts,
        "home_pts": home_pts,
        "exact_away": exact_away,
        "exact_home": exact_home,
        "win_home_pct": win_home_pct,
        "win_away_pct": win_away_pct,
        "spread_proyectado": spread_proyectado,
        "spread_ref_line": spread_ref_line,
        "cover_home_pct": cover_home_pct,
        "cover_away_pct": cover_away_pct,
        "total_ou": total_ou,
        "total_ref_line": total_ref_line,
        "over_pct": over_pct,
        "under_pct": under_pct,
        "ml_home_dec": ml_home_dec,
        "ml_home_am": ml_home_am,
        "ml_away_dec": ml_away_dec,
        "ml_away_am": ml_away_am,
        "sp_home_dec": sp_home_dec,
        "sp_home_am": sp_home_am,
        "sp_away_dec": sp_away_dec,
        "sp_away_am": sp_away_am,
        "ou_over_dec": ou_over_dec,
        "ou_over_am": ou_over_am,
        "ou_under_dec": ou_under_dec,
        "ou_under_am": ou_under_am,
        "epa_comp_away": round(epa_comp_away, 3),
        "epa_comp_home": round(epa_comp_home, 3),
        "net_pass_epa_away": round(net_pass_epa_away, 3),
        "net_pass_epa_home": round(net_pass_epa_home, 3),
        "net_rush_epa_away": round(net_rush_epa_away, 3),
        "net_rush_epa_home": round(net_rush_epa_home, 3),
        "sr_off_away": round(_normalizar_tasa(away_st["Success_Rate_Off"]) * 100.0, 1),
        "sr_off_home": round(_normalizar_tasa(home_st["Success_Rate_Off"]) * 100.0, 1),
        "pace_away": pace_away,
        "pace_home": pace_home,
        "snaps_por_equipo": round(snaps_por_equipo, 1),
        "hfa_pts": hfa_nfl,
        "n_sims": n_sims,
        "mc_p10_total": round(float(np.percentile(total_sim, 10)), 1),
        "mc_p50_total": round(float(np.percentile(total_sim, 50)), 1),
        "mc_p90_total": round(float(np.percentile(total_sim, 90)), 1),
        "mc_std_margin": round(float(np.std(margen_sim)), 1),
        "ot_pct": ot_pct,
        "lam_td_away": round(lam_td_away, 2),
        "lam_td_home": round(lam_td_home, 2),
        "key_numbers_freq": key_numbers_freq,
    }