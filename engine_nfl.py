#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MÓDULO 2: engine_nfl.py
Motor Cuantitativo NFL (5,000 iteraciones Poisson / Monte Carlo), Parser de Excel
y Detectores de Valor Matemático (+EV) estrictamente en FORMATO DECIMAL europeo.
"""

import io
import math
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from sync_espn_nfl import NFL_FRANCHISE_NAMES, americano_a_decimal, normalizar_abbr_nfl

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


def prob_a_cuota_decimal(prob: float) -> float:
    """
    Convierte una probabilidad (0 a 1) estrictamente en su Cuota Justa DECIMAL
    europea con 2 decimales (ej. 0.524 -> 1.91).
    """
    p = float(np.clip(prob, 0.01, 0.99))
    return round(1.0 / p, 2)


# ==============================================================================
# DETECTORES CUANTITATIVOS DE VALOR MATEMÁTICO (+EV) EN FORMATO DECIMAL
# ==============================================================================
def evaluar_valor_totales(
    total_modelo: float,
    total_mercado: float,
    cuota_over: float = 1.91,
    cuota_under: float = 1.91,
    prob_over_mc: Optional[float] = None,
    sigma_total: float = 13.5,
) -> Dict[str, Any]:
    """
    Evalúa si existe Valor Esperado Positivo (+EV) en el mercado de TOTALES (Over/Under)
    manejando todas las cuotas estrictamente en FORMATO DECIMAL:
      - Calcula la probabilidad del modelo para OVER y UNDER respecto a 'total_mercado'.
      - Calcula la Cuota Justa Decimal (Fair Odd = 1 / Prob).
      - Calcula EV% = ((Prob_Modelo * Cuota_Decimal_Mercado) - 1) * 100.
    """
    t_mod = float(total_modelo)
    t_mkt = float(total_mercado)
    c_over = americano_a_decimal(cuota_over, 1.91)
    c_under = americano_a_decimal(cuota_under, 1.91)

    diff_pts = round(t_mod - t_mkt, 1)

    # Probabilidad analítica normalizada + combinación opcional con Monte Carlo directo
    prob_over_norm = 0.5 * (1.0 + math.erf((t_mod - t_mkt) / (sigma_total * math.sqrt(2.0))))
    if prob_over_mc is not None:
        p_mc = float(prob_over_mc) / 100.0 if float(prob_over_mc) > 1.0 else float(prob_over_mc)
        prob_over = float(np.clip(0.55 * p_mc + 0.45 * prob_over_norm, 0.05, 0.95))
    else:
        prob_over = float(np.clip(prob_over_norm, 0.05, 0.95))

    prob_under = 1.0 - prob_over

    fair_over_decimal = prob_a_cuota_decimal(prob_over)
    fair_under_decimal = prob_a_cuota_decimal(prob_under)

    ev_over_pct = round(((prob_over * c_over) - 1.0) * 100.0, 1)
    ev_under_pct = round(((prob_under * c_under) - 1.0) * 100.0, 1)

    if ev_over_pct >= ev_under_pct:
        lado_mejor = "OVER"
        prob_mejor_pct = round(prob_over * 100.0, 1)
        cuota_mkt_mejor = c_over
        fair_mejor_dec = fair_over_decimal
        ev_mejor_pct = ev_over_pct
    else:
        lado_mejor = "UNDER"
        prob_mejor_pct = round(prob_under * 100.0, 1)
        cuota_mkt_mejor = c_under
        fair_mejor_dec = fair_under_decimal
        ev_mejor_pct = ev_under_pct

    # Criterio Sharp: EV >= +1.5% (o ventaja clara >= 1.5 pts con EV > 0%)
    hay_valor = (ev_mejor_pct >= 1.5) or (abs(diff_pts) >= 1.5 and ev_mejor_pct > 0.0)

    if hay_valor:
        recomendacion = f"{lado_mejor} {t_mkt:.1f}"
        etiqueta_ev = f"🔥 +EV {lado_mejor} {t_mkt:.1f} @ {cuota_mkt_mejor:.2f} (EV {ev_mejor_pct:+.1f}%)"
    else:
        recomendacion = f"PASS / SIN VALOR ({lado_mejor} {t_mkt:.1f})"
        etiqueta_ev = f"⚖️ SIN VALOR ({lado_mejor} {t_mkt:.1f} @ {cuota_mkt_mejor:.2f} | EV {ev_mejor_pct:+.1f}%)"

    return {
        "hay_valor": hay_valor,
        "lado": lado_mejor,
        "recomendacion": recomendacion,
        "etiqueta_ev": etiqueta_ev,
        "total_modelo": round(t_mod, 1),
        "total_mercado": round(t_mkt, 1),
        "edge_pts": diff_pts,
        "prob_over_pct": round(prob_over * 100.0, 1),
        "prob_under_pct": round(prob_under * 100.0, 1),
        "prob_mejor_pct": prob_mejor_pct,
        "cuota_over_decimal": c_over,
        "cuota_under_decimal": c_under,
        "cuota_mercado_decimal": cuota_mkt_mejor,
        "fair_over_decimal": fair_over_decimal,
        "fair_under_decimal": fair_under_decimal,
        "fair_decimal": fair_mejor_dec,
        "ev_over_pct": ev_over_pct,
        "ev_under_pct": ev_under_pct,
        "ev_pct": ev_mejor_pct,
    }


def evaluar_valor_spread(
    spread_modelo_home: float,
    spread_mercado_home: float,
    cuota_spread_home: float = 1.91,
    cuota_spread_away: float = 1.91,
    home_abbr: str = "LOCAL",
    away_abbr: str = "VISITA",
    prob_cover_home_mc: Optional[float] = None,
    sigma_margin: float = 13.2,
) -> Dict[str, Any]:
    """
    Evalúa si existe Valor Esperado Positivo (+EV) en el mercado de HÁNDICAP (Spread)
    manejando todas las cuotas estrictamente en FORMATO DECIMAL:
      - Compara 'spread_modelo_home' (ej. -5.8) contra 'spread_mercado_home' (ej. -3.5).
      - Calcula la probabilidad de cubrir la línea para Local y Visita.
      - Calcula la Cuota Justa Decimal (Fair Odd = 1 / Prob_Cover).
      - Calcula EV% = ((Prob_Cover * Cuota_Decimal_Mercado) - 1) * 100.
    """
    sp_mod_h = float(spread_modelo_home)
    sp_mkt_h = float(spread_mercado_home)
    sp_mkt_a = -sp_mkt_h

    c_home = americano_a_decimal(cuota_spread_home, 1.91)
    c_away = americano_a_decimal(cuota_spread_away, 1.91)

    # Si spread_mercado_home es -3.5 y spread_modelo_home es -6.0, el local tiene +2.5 pts de ventaja
    edge_pts_home = round(sp_mkt_h - sp_mod_h, 1)

    prob_cov_h_norm = 0.5 * (1.0 + math.erf((sp_mkt_h - sp_mod_h) / (sigma_margin * math.sqrt(2.0))))
    if prob_cover_home_mc is not None:
        p_mc = float(prob_cover_home_mc) / 100.0 if float(prob_cover_home_mc) > 1.0 else float(prob_cover_home_mc)
        prob_cover_home = float(np.clip(0.55 * p_mc + 0.45 * prob_cov_h_norm, 0.05, 0.95))
    else:
        prob_cover_home = float(np.clip(prob_cov_h_norm, 0.05, 0.95))

    prob_cover_away = 1.0 - prob_cover_home

    fair_home_decimal = prob_a_cuota_decimal(prob_cover_home)
    fair_away_decimal = prob_a_cuota_decimal(prob_cover_away)

    ev_home_pct = round(((prob_cover_home * c_home) - 1.0) * 100.0, 1)
    ev_away_pct = round(((prob_cover_away * c_away) - 1.0) * 100.0, 1)

    if ev_home_pct >= ev_away_pct:
        equipo_pick = home_abbr
        lado_pick = "HOME"
        linea_pick = sp_mkt_h
        prob_mejor_pct = round(prob_cover_home * 100.0, 1)
        cuota_mkt_mejor = c_home
        fair_mejor_dec = fair_home_decimal
        ev_mejor_pct = ev_home_pct
        edge_pts_pick = edge_pts_home
    else:
        equipo_pick = away_abbr
        lado_pick = "AWAY"
        linea_pick = sp_mkt_a
        prob_mejor_pct = round(prob_cover_away * 100.0, 1)
        cuota_mkt_mejor = c_away
        fair_mejor_dec = fair_away_decimal
        ev_mejor_pct = ev_away_pct
        edge_pts_pick = round(-edge_pts_home, 1)

    hay_valor = (ev_mejor_pct >= 1.5) or (edge_pts_pick >= 1.2 and ev_mejor_pct > 0.0)
    pick_corto = f"{equipo_pick} {linea_pick:+.1f}"

    if hay_valor:
        etiqueta_ev = f"🔥 +EV {pick_corto} @ {cuota_mkt_mejor:.2f} (EV {ev_mejor_pct:+.1f}%)"
    else:
        etiqueta_ev = f"⚖️ SIN VALOR ({pick_corto} @ {cuota_mkt_mejor:.2f} | EV {ev_mejor_pct:+.1f}%)"

    return {
        "hay_valor": hay_valor,
        "lado": lado_pick,
        "equipo_pick": equipo_pick,
        "linea_pick": round(linea_pick, 1),
        "recomendacion": pick_corto,
        "etiqueta_ev": etiqueta_ev,
        "spread_modelo_home": round(sp_mod_h, 1),
        "spread_mercado_home": round(sp_mkt_h, 1),
        "spread_mercado_away": round(sp_mkt_a, 1),
        "edge_pts": edge_pts_pick,
        "prob_cover_home_pct": round(prob_cover_home * 100.0, 1),
        "prob_cover_away_pct": round(prob_cover_away * 100.0, 1),
        "prob_mejor_pct": prob_mejor_pct,
        "cuota_spread_home_decimal": c_home,
        "cuota_spread_away_decimal": c_away,
        "cuota_mercado_decimal": cuota_mkt_mejor,
        "fair_home_decimal": fair_home_decimal,
        "fair_away_decimal": fair_away_decimal,
        "fair_decimal": fair_mejor_dec,
        "ev_home_pct": ev_home_pct,
        "ev_away_pct": ev_away_pct,
        "ev_pct": ev_mejor_pct,
    }


def validar_y_parsear_excel_nfl(df_excel: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """
    Valida que el DataFrame proveniente de 'nfl_stats.xlsx' contenga las columnas:
    ['Team_Abbr', 'QB_Name', 'EPA_Pass_Off', 'EPA_Rush_Off', 'EPA_Pass_Def',
     'EPA_Rush_Def', 'Success_Rate_Off', 'Success_Rate_Def', 'Pace_Sec']
    Retorna un diccionario indexado por 'Team_Abbr' para consulta rápida.
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
    lineas_mercado: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Corre 5,000 iteraciones (Poisson / Monte Carlo) con ventaja de localía (~1.8 pts)
    y diferenciales de EPA, y audita el mercado en FORMATO DECIMAL contra las líneas
    de Totales (Over/Under) y Hándicap (Spread).
    """
    away_key = normalizar_abbr_nfl(away_abbr)
    home_key = normalizar_abbr_nfl(home_abbr)

    default_pool = obtener_stats_nfl_default()
    away_st = (
        nfl_stats_dict.get(away_key)
        or nfl_stats_dict.get(away_abbr)
        or default_pool.get(away_key, DEFAULT_NFL_STATS_ROWS[0])
    )
    home_st = (
        nfl_stats_dict.get(home_key)
        or nfl_stats_dict.get(home_abbr)
        or default_pool.get(home_key, DEFAULT_NFL_STATS_ROWS[1])
    )

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

    # Cuotas justas Moneyline estrictamente en FORMATO DECIMAL
    ml_home_decimal = prob_a_cuota_decimal(win_home_raw)
    ml_away_decimal = prob_a_cuota_decimal(1.0 - win_home_raw)

    # Spread proyectado desde la perspectiva del Local y Total proyectado
    spread_proyectado = round(-(home_pts - away_pts), 1)
    total_ou = round(home_pts + away_pts, 1)

    # 5. Líneas de mercado en formato decimal (recibidas de sync_espn_nfl o fallback)
    mkt = lineas_mercado or {}
    total_mercado = float(mkt.get("total_mercado", round(total_ou) - 0.5))
    cuota_over_dec = americano_a_decimal(mkt.get("cuota_over_decimal", 1.91), 1.91)
    cuota_under_dec = americano_a_decimal(mkt.get("cuota_under_decimal", 1.91), 1.91)

    lineas_nfl_std = [-14.0, -10.5, -10.0, -7.5, -7.0, -6.5, -4.5, -3.5, -3.0, -2.5, -1.5, 1.5, 2.5, 3.0, 3.5, 4.5, 6.5, 7.0, 7.5, 10.0, 10.5, 14.0]
    default_sp_mkt = min(lineas_nfl_std, key=lambda x: abs(x - (spread_proyectado * 0.88)))
    spread_mercado_home = float(mkt.get("spread_mercado_home", default_sp_mkt))
    cuota_sp_home_dec = americano_a_decimal(mkt.get("cuota_spread_home_decimal", 1.91), 1.91)
    cuota_sp_away_dec = americano_a_decimal(mkt.get("cuota_spread_away_decimal", 1.91), 1.91)

    # Probabilidades empíricas de las 5,000 simulaciones contra la línea real del mercado
    total_sim = sim_home + sim_away
    no_push_tot = total_sim != total_mercado
    prob_over_mc_raw = float(np.mean(total_sim[no_push_tot] > total_mercado)) if no_push_tot.sum() > 0 else 0.50

    margen_sim = sim_home - sim_away
    no_push_sp = (margen_sim + spread_mercado_home) != 0
    prob_cover_home_mc_raw = (
        float(np.mean((margen_sim[no_push_sp] + spread_mercado_home) > 0)) if no_push_sp.sum() > 0 else 0.50
    )

    # 6. Evaluación cuantitativa de Valor (+EV) en Totales y Spread (100% Decimal)
    ev_totales = evaluar_valor_totales(
        total_modelo=total_ou,
        total_mercado=total_mercado,
        cuota_over=cuota_over_dec,
        cuota_under=cuota_under_dec,
        prob_over_mc=prob_over_mc_raw,
    )

    ev_spread = evaluar_valor_spread(
        spread_modelo_home=spread_proyectado,
        spread_mercado_home=spread_mercado_home,
        cuota_spread_home=cuota_sp_home_dec,
        cuota_spread_away=cuota_sp_away_dec,
        home_abbr=home_key,
        away_abbr=away_key,
        prob_cover_home_mc=prob_cover_home_mc_raw,
    )

    # Marcador entero representativo (Key Numbers NFL)
    nfl_scores_grid = [10, 13, 14, 16, 17, 20, 21, 23, 24, 27, 28, 30, 31, 34, 35, 38]
    exact_away = min(nfl_scores_grid, key=lambda s: abs(s - away_pts))
    exact_home = min(nfl_scores_grid, key=lambda s: abs(s - home_pts))
    if exact_away == exact_home:
        if home_pts >= away_pts:
            exact_home += 3
        else:
            exact_away += 3

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
        "ml_home_decimal": ml_home_decimal,
        "ml_away_decimal": ml_away_decimal,
        "spread_proyectado": spread_proyectado,
        "spread_mercado_home": spread_mercado_home,
        "cuota_spread_home_decimal": cuota_sp_home_dec,
        "cuota_spread_away_decimal": cuota_sp_away_dec,
        "cover_home_pct": ev_spread["prob_cover_home_pct"],
        "cover_away_pct": ev_spread["prob_cover_away_pct"],
        "fair_spread_home_decimal": ev_spread["fair_home_decimal"],
        "fair_spread_away_decimal": ev_spread["fair_away_decimal"],
        "total_ou": total_ou,
        "total_mercado": total_mercado,
        "cuota_over_decimal": cuota_over_dec,
        "cuota_under_decimal": cuota_under_dec,
        "over_pct": ev_totales["prob_over_pct"],
        "under_pct": ev_totales["prob_under_pct"],
        "fair_over_decimal": ev_totales["fair_over_decimal"],
        "fair_under_decimal": ev_totales["fair_under_decimal"],
        "ev_totales": ev_totales,
        "ev_spread": ev_spread,
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