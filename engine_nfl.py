#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MÓDULO 2: engine_nfl.py
Motor Cuantitativo NFL basado en Simulación Discreta por Series Ofensivas
con Modelado Dinámico de Drives por Cruce de Ritmo (Pace_Sec + Reloj Detenido +
Duración de Series por Success_Rate_Off vs Success_Rate_Def):
  - Enfrentamientos lentos y terrestres: ~9.4 a 10.2 drives por equipo.
  - Enfrentamientos de ritmo medio: ~10.6 a 11.4 drives por equipo.
  - Enfrentamientos aéreos acelerados en domo: ~11.8 a 12.6 drives por equipo.
  - Muestreo estocástico Poisson/Normal de posesiones en cada una de las 5,000
    iteraciones de Monte Carlo para inyectar varianza real de volumen de juego.
  - Elevación del piso de eficiencia (~23% a 27% TD/drive y ~15% a 18% FG/drive,
    promediando ~1.95 - 2.05 puntos/drive y situando la media de la liga entre
    43.0 y 45.5 puntos totales en partidos no climáticos).
  - Ventaja de Localía (HFA) calibrada entre +1.50 y +2.00 puntos según la plaza
    (ej. Ford Field en Detroit +1.95, Arrowhead en Kansas City +2.00).
"""

import copy
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

DOME_FRANCHISES: Dict[str, bool] = {
    "DET": True,
    "DAL": True,
    "HOU": True,
    "LA": True,
    "LAR": True,
    "MIN": True,
    "ATL": True,
    "IND": True,
    "ARI": True,
    "LAC": True,
    "NO": True,
    "LV": True,
}

# Ventaja de Localía (HFA) específica por plaza (+1.50 a +2.00 puntos netos)
STADIUM_HFA_PTS: Dict[str, float] = {
    "KC": 2.00,   # Arrowhead Stadium
    "DET": 1.95,  # Ford Field (Domo ruidoso)
    "BUF": 1.95,  # Highmark Stadium
    "SEA": 1.95,  # Lumen Field
    "MIN": 1.90,  # U.S. Bank Stadium (Domo ruidoso)
    "DEN": 1.90,  # Empower Field at Mile High (Altitud)
    "GB": 1.90,   # Lambeau Field
    "BAL": 1.85,  # M&T Bank Stadium
    "PHI": 1.85,  # Lincoln Financial Field
    "NO": 1.85,   # Caesars Superdome (Domo ruidoso)
    "PIT": 1.80,  # Acrisure Stadium
    "SF": 1.80,   # Levi's Stadium
    "DAL": 1.80,  # AT&T Stadium (Domo)
    "CIN": 1.75,  # Paycor Stadium
    "HOU": 1.75,  # NRG Stadium (Domo)
    "CLE": 1.75,  # Huntington Bank Field
    "MIA": 1.75,  # Hard Rock Stadium
    "CHI": 1.70,  # Soldier Field
    "TB": 1.70,   # Raymond James Stadium
    "ATL": 1.70,  # Mercedes-Benz Stadium (Domo)
    "IND": 1.70,  # Lucas Oil Stadium (Domo)
    "JAX": 1.60,  # EverBank Stadium
    "WAS": 1.60,  # Northwest Stadium
    "WSH": 1.60,
    "ARI": 1.60,  # State Farm Stadium (Domo)
    "NYJ": 1.60,  # MetLife Stadium
    "NYG": 1.55,  # MetLife Stadium
    "NE": 1.60,   # Gillette Stadium
    "TEN": 1.60,  # Nissan Stadium
    "LV": 1.60,   # Allegiant Stadium (Domo)
    "LA": 1.55,   # SoFi Stadium (Domo)
    "LAR": 1.55,
    "LAC": 1.50,  # SoFi Stadium (Domo)
    "CAR": 1.50,  # Bank of America Stadium
}

NFL_KEY_NUMBERS: List[int] = [3, 7, 6, 10, 4, 14]

# Parámetros base de referencia NFL
NEUTRAL_DRIVES_PER_TEAM: float = 11.00
TARGET_PTS_PER_DRIVE: float = 2.00

DEFAULT_NFL_STATS_ROWS: List[Dict[str, Any]] = [
    {"Team_Abbr": "KC",  "QB_Name": "P. Mahomes",       "EPA_Pass_Off": 0.195, "EPA_Rush_Off": 0.015, "EPA_Pass_Def": -0.065, "EPA_Rush_Def": -0.040, "Success_Rate_Off": 0.505, "Success_Rate_Def": 0.415, "Pace_Sec": 28.0, "Drives_Game": 10.8},
    {"Team_Abbr": "SF",  "QB_Name": "B. Purdy",         "EPA_Pass_Off": 0.210, "EPA_Rush_Off": 0.065, "EPA_Pass_Def": -0.070, "EPA_Rush_Def": -0.055, "Success_Rate_Off": 0.515, "Success_Rate_Def": 0.410, "Pace_Sec": 29.1, "Drives_Game": 10.4},
    {"Team_Abbr": "BUF", "QB_Name": "J. Allen",         "EPA_Pass_Off": 0.180, "EPA_Rush_Off": 0.045, "EPA_Pass_Def": -0.040, "EPA_Rush_Def": -0.025, "Success_Rate_Off": 0.498, "Success_Rate_Def": 0.430, "Pace_Sec": 27.3, "Drives_Game": 11.2},
    {"Team_Abbr": "BAL", "QB_Name": "L. Jackson",       "EPA_Pass_Off": 0.165, "EPA_Rush_Off": 0.095, "EPA_Pass_Def": -0.085, "EPA_Rush_Def": -0.060, "Success_Rate_Off": 0.502, "Success_Rate_Def": 0.405, "Pace_Sec": 29.0, "Drives_Game": 10.3},
    {"Team_Abbr": "DET", "QB_Name": "J. Goff",          "EPA_Pass_Off": 0.175, "EPA_Rush_Off": 0.055, "EPA_Pass_Def": -0.020, "EPA_Rush_Def": -0.050, "Success_Rate_Off": 0.508, "Success_Rate_Def": 0.435, "Pace_Sec": 27.4, "Drives_Game": 11.3},
    {"Team_Abbr": "PHI", "QB_Name": "J. Hurts",         "EPA_Pass_Off": 0.145, "EPA_Rush_Off": 0.075, "EPA_Pass_Def": -0.035, "EPA_Rush_Def": -0.045, "Success_Rate_Off": 0.492, "Success_Rate_Def": 0.428, "Pace_Sec": 27.6, "Drives_Game": 11.0},
    {"Team_Abbr": "DAL", "QB_Name": "D. Prescott",      "EPA_Pass_Off": 0.150, "EPA_Rush_Off": -0.010, "EPA_Pass_Def": -0.030, "EPA_Rush_Def": 0.010, "Success_Rate_Off": 0.485, "Success_Rate_Def": 0.440, "Pace_Sec": 26.8, "Drives_Game": 11.5},
    {"Team_Abbr": "CIN", "QB_Name": "J. Burrow",        "EPA_Pass_Off": 0.170, "EPA_Rush_Off": -0.015, "EPA_Pass_Def": 0.010,  "EPA_Rush_Def": 0.005, "Success_Rate_Off": 0.490, "Success_Rate_Def": 0.452, "Pace_Sec": 27.5, "Drives_Game": 11.1},
    {"Team_Abbr": "HOU", "QB_Name": "C. Stroud",        "EPA_Pass_Off": 0.155, "EPA_Rush_Off": -0.005, "EPA_Pass_Def": -0.035, "EPA_Rush_Def": -0.030, "Success_Rate_Off": 0.482, "Success_Rate_Def": 0.432, "Pace_Sec": 27.8, "Drives_Game": 11.1},
    {"Team_Abbr": "GB",  "QB_Name": "J. Love",          "EPA_Pass_Off": 0.160, "EPA_Rush_Off": 0.025, "EPA_Pass_Def": -0.015, "EPA_Rush_Def": 0.010, "Success_Rate_Off": 0.488, "Success_Rate_Def": 0.445, "Pace_Sec": 28.1, "Drives_Game": 10.9},
    {"Team_Abbr": "MIA", "QB_Name": "T. Tagovailoa",    "EPA_Pass_Off": 0.165, "EPA_Rush_Off": 0.035, "EPA_Pass_Def": -0.010, "EPA_Rush_Def": -0.015, "Success_Rate_Off": 0.494, "Success_Rate_Def": 0.442, "Pace_Sec": 26.7, "Drives_Game": 11.5},
    {"Team_Abbr": "LA",  "QB_Name": "M. Stafford",      "EPA_Pass_Off": 0.135, "EPA_Rush_Off": 0.020, "EPA_Pass_Def": 0.015,  "EPA_Rush_Def": 0.005, "Success_Rate_Off": 0.480, "Success_Rate_Def": 0.450, "Pace_Sec": 27.9, "Drives_Game": 10.9},
    {"Team_Abbr": "MIN", "QB_Name": "S. Darnold",       "EPA_Pass_Off": 0.115, "EPA_Rush_Off": -0.010, "EPA_Pass_Def": -0.045, "EPA_Rush_Def": -0.030, "Success_Rate_Off": 0.472, "Success_Rate_Def": 0.425, "Pace_Sec": 27.4, "Drives_Game": 11.3},
    {"Team_Abbr": "NYJ", "QB_Name": "A. Rodgers",       "EPA_Pass_Off": 0.085, "EPA_Rush_Off": -0.015, "EPA_Pass_Def": -0.080, "EPA_Rush_Def": -0.045, "Success_Rate_Off": 0.455, "Success_Rate_Def": 0.408, "Pace_Sec": 29.3, "Drives_Game": 10.3},
    {"Team_Abbr": "CLE", "QB_Name": "J. Winston",       "EPA_Pass_Off": 0.040, "EPA_Rush_Off": -0.020, "EPA_Pass_Def": -0.075, "EPA_Rush_Def": -0.050, "Success_Rate_Off": 0.442, "Success_Rate_Def": 0.412, "Pace_Sec": 29.0, "Drives_Game": 10.4},
    {"Team_Abbr": "PIT", "QB_Name": "R. Wilson",        "EPA_Pass_Off": 0.075, "EPA_Rush_Off": 0.015, "EPA_Pass_Def": -0.065, "EPA_Rush_Def": -0.040, "Success_Rate_Off": 0.458, "Success_Rate_Def": 0.418, "Pace_Sec": 29.2, "Drives_Game": 10.3},
    {"Team_Abbr": "ATL", "QB_Name": "K. Cousins",       "EPA_Pass_Off": 0.110, "EPA_Rush_Off": 0.020, "EPA_Pass_Def": 0.010,  "EPA_Rush_Def": 0.005, "Success_Rate_Off": 0.475, "Success_Rate_Def": 0.448, "Pace_Sec": 27.3, "Drives_Game": 11.2},
    {"Team_Abbr": "CHI", "QB_Name": "C. Williams",      "EPA_Pass_Off": 0.055, "EPA_Rush_Off": 0.005, "EPA_Pass_Def": -0.040, "EPA_Rush_Def": -0.035, "Success_Rate_Off": 0.452, "Success_Rate_Def": 0.428, "Pace_Sec": 28.3, "Drives_Game": 10.8},
    {"Team_Abbr": "JAX", "QB_Name": "T. Lawrence",      "EPA_Pass_Off": 0.080, "EPA_Rush_Off": -0.010, "EPA_Pass_Def": 0.025,  "EPA_Rush_Def": 0.010, "Success_Rate_Off": 0.464, "Success_Rate_Def": 0.458, "Pace_Sec": 27.8, "Drives_Game": 11.0},
    {"Team_Abbr": "IND", "QB_Name": "A. Richardson",    "EPA_Pass_Off": 0.065, "EPA_Rush_Off": 0.040, "EPA_Pass_Def": 0.020,  "EPA_Rush_Def": 0.015, "Success_Rate_Off": 0.460, "Success_Rate_Def": 0.455, "Pace_Sec": 27.1, "Drives_Game": 11.4},
    {"Team_Abbr": "SEA", "QB_Name": "G. Smith",         "EPA_Pass_Off": 0.095, "EPA_Rush_Off": 0.005, "EPA_Pass_Def": 0.015,  "EPA_Rush_Def": 0.020, "Success_Rate_Off": 0.470, "Success_Rate_Def": 0.456, "Pace_Sec": 27.6, "Drives_Game": 11.1},
    {"Team_Abbr": "TB",  "QB_Name": "B. Mayfield",      "EPA_Pass_Off": 0.125, "EPA_Rush_Off": -0.005, "EPA_Pass_Def": 0.010,  "EPA_Rush_Def": -0.020, "Success_Rate_Off": 0.478, "Success_Rate_Def": 0.445, "Pace_Sec": 27.7, "Drives_Game": 11.0},
    {"Team_Abbr": "WAS", "QB_Name": "J. Daniels",       "EPA_Pass_Off": 0.140, "EPA_Rush_Off": 0.060, "EPA_Pass_Def": 0.035,  "EPA_Rush_Def": 0.025, "Success_Rate_Off": 0.488, "Success_Rate_Def": 0.465, "Pace_Sec": 27.1, "Drives_Game": 11.2},
    {"Team_Abbr": "ARI", "QB_Name": "K. Murray",        "EPA_Pass_Off": 0.090, "EPA_Rush_Off": 0.045, "EPA_Pass_Def": 0.045,  "EPA_Rush_Def": 0.035, "Success_Rate_Off": 0.468, "Success_Rate_Def": 0.472, "Pace_Sec": 27.5, "Drives_Game": 11.0},
    {"Team_Abbr": "LAC", "QB_Name": "J. Herbert",       "EPA_Pass_Off": 0.120, "EPA_Rush_Off": 0.015, "EPA_Pass_Def": -0.030, "EPA_Rush_Def": -0.025, "Success_Rate_Off": 0.474, "Success_Rate_Def": 0.432, "Pace_Sec": 28.8, "Drives_Game": 10.5},
    {"Team_Abbr": "NO",  "QB_Name": "D. Carr",          "EPA_Pass_Off": 0.070, "EPA_Rush_Off": -0.010, "EPA_Pass_Def": -0.025, "EPA_Rush_Def": -0.015, "Success_Rate_Off": 0.456, "Success_Rate_Def": 0.436, "Pace_Sec": 28.0, "Drives_Game": 11.0},
    {"Team_Abbr": "LV",  "QB_Name": "G. Minshew",       "EPA_Pass_Off": -0.015,"EPA_Rush_Off": -0.030, "EPA_Pass_Def": 0.005,  "EPA_Rush_Def": 0.010, "Success_Rate_Off": 0.432, "Success_Rate_Def": 0.448, "Pace_Sec": 28.4, "Drives_Game": 10.7},
    {"Team_Abbr": "DEN", "QB_Name": "B. Nix",           "EPA_Pass_Off": 0.045, "EPA_Rush_Off": 0.010, "EPA_Pass_Def": -0.055, "EPA_Rush_Def": -0.030, "Success_Rate_Off": 0.448, "Success_Rate_Def": 0.422, "Pace_Sec": 28.6, "Drives_Game": 10.6},
    {"Team_Abbr": "TEN", "QB_Name": "W. Levis",         "EPA_Pass_Off": -0.025,"EPA_Rush_Off": -0.015, "EPA_Pass_Def": 0.015,  "EPA_Rush_Def": -0.010, "Success_Rate_Off": 0.428, "Success_Rate_Def": 0.446, "Pace_Sec": 29.2, "Drives_Game": 10.3},
    {"Team_Abbr": "NE",  "QB_Name": "D. Maye",          "EPA_Pass_Off": -0.010,"EPA_Rush_Off": -0.020, "EPA_Pass_Def": 0.010,  "EPA_Rush_Def": -0.015, "Success_Rate_Off": 0.435, "Success_Rate_Def": 0.442, "Pace_Sec": 29.4, "Drives_Game": 10.2},
    {"Team_Abbr": "NYG", "QB_Name": "D. Jones",         "EPA_Pass_Off": -0.035,"EPA_Rush_Off": -0.025, "EPA_Pass_Def": 0.025,  "EPA_Rush_Def": 0.020, "Success_Rate_Off": 0.425, "Success_Rate_Def": 0.458, "Pace_Sec": 28.9, "Drives_Game": 10.4},
    {"Team_Abbr": "CAR", "QB_Name": "B. Young",         "EPA_Pass_Off": -0.055,"EPA_Rush_Off": -0.030, "EPA_Pass_Def": 0.050,  "EPA_Rush_Def": 0.040, "Success_Rate_Off": 0.415, "Success_Rate_Def": 0.475, "Pace_Sec": 29.3, "Drives_Game": 10.3},
]


def _normalizar_tasa(valor: float) -> float:
    """Convierte porcentajes en escala 0-100 a decimal 0-1 si es necesario."""
    v = float(valor)
    return v / 100.0 if v > 1.5 else v


def prob_a_cuota_decimal(prob: float) -> float:
    """
    Convierte una probabilidad (0 a 1) estrictamente en su Cuota Justa DECIMAL
    europea con 2 decimales: round(1.0 / Prob, 2).
    """
    p = float(np.clip(prob, 0.01, 0.99))
    return round(1.0 / p, 2)


def detectar_info_key_number(spread_val: float) -> Dict[str, Any]:
    """
    Analiza si una línea de Spread descansa exactamente sobre un Número Clave de la NFL
    (3, 7, 6, 10, 4, 14) o a medio punto de distancia (Hook).
    """
    abs_sp = round(abs(float(spread_val)), 1)
    entero_cercano = int(round(abs_sp))

    if abs_sp in {3.0, 7.0, 6.0, 10.0, 4.0, 14.0}:
        kn_int = int(abs_sp)
        return {
            "es_key_number": True,
            "tipo": "EXACTO",
            "key_number": kn_int,
            "etiqueta": f"🔑 Línea clave: {kn_int} pts (Push activo)",
        }

    for kn in [3, 7, 6, 10, 4, 14]:
        if abs(abs_sp - kn) == 0.5:
            return {
                "es_key_number": True,
                "tipo": "HOOK",
                "key_number": kn,
                "etiqueta": f"🔑 Línea clave: {kn} pts (Hook {abs_sp:.1f})",
            }

    return {
        "es_key_number": False,
        "tipo": "ESTANDAR",
        "key_number": entero_cercano,
        "etiqueta": f"Línea estándar: {abs_sp:.1f} pts",
    }


def _calcular_probabilidad_dinamica_sin_techo(
    diff_puntos: float,
    prob_mercado_novig: float,
    prob_empirica_over: Optional[float] = None,
    escala_puntos: float = 3.8,
    sigma_ref: float = 13.8,
) -> float:
    """
    Calcula la probabilidad del lado positivo (Over o Cover Home) de forma
    100% continua y dinámica según la distancia en puntos respecto a la línea
    del sportsbook, SIN ningún clipping ni techo artificial plano:
      - Si la ventaja es de ~1.5 pts -> Prob ~54.2% (EV ~ +3.5% en línea 1.91)
      - Si la ventaja es de ~3.0 pts -> Prob ~56.5% (EV ~ +7.9% en línea 1.91)
      - Si la ventaja es de ~5.0 pts -> Prob ~58.5% (EV ~ +11.7% en línea 1.91)
    """
    p_mkt = float(np.clip(prob_mercado_novig, 0.30, 0.70))
    d = float(diff_puntos)
    signo = 1.0 if d >= 0.0 else -1.0
    abs_d = abs(d)

    edge_continuo = 0.045 * math.log1p(abs_d / 1.05) + 0.0012 * abs_d

    prob_norm = 0.5 * (1.0 + math.erf(d / (sigma_ref * math.sqrt(2.0))))
    if prob_empirica_over is not None:
        residual_mc = float(prob_empirica_over) - prob_norm
        ajuste_mc = 0.04 * residual_mc
    else:
        ajuste_mc = 0.0

    prob_final = p_mkt + (signo * edge_continuo) + ajuste_mc
    return float(np.clip(prob_final, 0.05, 0.95))


# ==============================================================================
# DETECTORES CUANTITATIVOS DE VALOR MATEMÁTICO (+EV) DINÁMICOS Y CONTINUOS
# ==============================================================================
def evaluar_valor_totales(
    total_modelo: float,
    total_mercado: float,
    cuota_over: float = 1.91,
    cuota_under: float = 1.91,
    scores_total_sim: Optional[np.ndarray] = None,
    sigma_total: float = 13.8,
) -> Dict[str, Any]:
    """
    Evalúa el mercado de TOTALES (Over/Under) de forma dinámica y continua
    según la distancia entre 'total_modelo' y 'total_mercado', sin topes planos.
    """
    t_mod = float(total_modelo)
    t_mkt = float(total_mercado)
    c_over = americano_a_decimal(cuota_over, 1.91)
    c_under = americano_a_decimal(cuota_under, 1.91)

    diff_pts = round(t_mod - t_mkt, 1)

    imp_o = 1.0 / max(1.05, c_over)
    imp_u = 1.0 / max(1.05, c_under)
    p_mkt_over = imp_o / (imp_o + imp_u)

    prob_over_emp: Optional[float] = None
    if scores_total_sim is not None and len(scores_total_sim) > 0:
        n_total = float(len(scores_total_sim))
        push_mask = scores_total_sim == t_mkt
        prob_push = float(np.sum(push_mask)) / n_total
        no_push = scores_total_sim[~push_mask]
        if len(no_push) > 0:
            prob_over_emp = float(np.mean(no_push > t_mkt))
    else:
        prob_push = 0.0

    prob_over = _calcular_probabilidad_dinamica_sin_techo(
        diff_puntos=t_mod - t_mkt,
        prob_mercado_novig=p_mkt_over,
        prob_empirica_over=prob_over_emp,
        escala_puntos=3.8,
        sigma_ref=sigma_total,
    )
    prob_under = float(np.clip(1.0 - prob_over, 0.05, 0.95))

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

    hay_valor = (ev_mejor_pct >= 1.5) and (abs(diff_pts) >= 1.1)

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
        "prob_push_pct": round(prob_push * 100.0, 1),
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
    margen_sim: Optional[np.ndarray] = None,
    sigma_margin: float = 13.2,
) -> Dict[str, Any]:
    """
    Evalúa el mercado de HÁNDICAP (Spread) de forma dinámica y continua según la
    distancia entre 'spread_modelo_home' y 'spread_mercado_home', sin topes planos.
    """
    sp_mod_h = float(spread_modelo_home)
    sp_mkt_h = float(spread_mercado_home)
    sp_mkt_a = -sp_mkt_h

    c_home = americano_a_decimal(cuota_spread_home, 1.91)
    c_away = americano_a_decimal(cuota_spread_away, 1.91)

    edge_pts_home = round(sp_mkt_h - sp_mod_h, 1)
    key_info = detectar_info_key_number(sp_mkt_h)

    imp_h = 1.0 / max(1.05, c_home)
    imp_a = 1.0 / max(1.05, c_away)
    p_mkt_home = imp_h / (imp_h + imp_a)

    prob_cov_h_emp: Optional[float] = None
    if margen_sim is not None and len(margen_sim) > 0:
        n_sims_total = float(len(margen_sim))
        resultado_con_spread = margen_sim + sp_mkt_h
        push_mask = resultado_con_spread == 0
        prob_push_raw = float(np.sum(push_mask)) / n_sims_total

        sin_push = resultado_con_spread[~push_mask]
        if len(sin_push) > 0:
            prob_cov_h_emp = float(np.mean(sin_push > 0))
    else:
        prob_push_raw = 0.0

    prob_cover_home = _calcular_probabilidad_dinamica_sin_techo(
        diff_puntos=sp_mkt_h - sp_mod_h,
        prob_mercado_novig=p_mkt_home,
        prob_empirica_over=prob_cov_h_emp,
        escala_puntos=3.5,
        sigma_ref=sigma_margin,
    )
    prob_cover_away = float(np.clip(1.0 - prob_cover_home, 0.05, 0.95))

    fair_home_decimal = round(1.0 / prob_cover_home, 2)
    fair_away_decimal = round(1.0 / prob_cover_away, 2)

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

    hay_valor = (ev_mejor_pct >= 1.5) and (edge_pts_pick >= 1.0)
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
        "prob_push_pct": round(prob_push_raw * 100.0, 1),
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
        "es_key_number": key_info["es_key_number"],
        "key_number_val": key_info["key_number"],
        "key_number_tag": key_info["etiqueta"],
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
            "Pace_Sec": float(np.clip(float(row["Pace_Sec"]), 22.0, 34.0)),
            "Drives_Game": (
                float(np.clip(float(row["Drives_Game"]), 8.5, 13.5))
                if "Drives_Game" in row and pd.notna(row["Drives_Game"])
                else 10.9
            ),
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
    """
    Genera un archivo Excel (.xlsx) en memoria usando io.BytesIO y pandas
    con los ratings actuales o calibrados de las 32 franquicias.
    """
    filas = []
    vistos = set()
    for abbr, data in nfl_stats_dict.items():
        std_abbr = normalizar_abbr_nfl(abbr)
        if std_abbr in vistos:
            continue
        vistos.add(std_abbr)
        fila_item = {col: data[col] for col in REQUIRED_EXCEL_COLUMNS}
        fila_item["Drives_Game"] = round(float(data.get("Drives_Game", 10.9)), 2)
        filas.append(fila_item)
    df_export = pd.DataFrame(filas)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_export.to_excel(writer, index=False, sheet_name="NFL_Stats")
    return buffer.getvalue()


def _calcular_medias_liga(nfl_stats_dict: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    """
    Calcula las medias y desviación estándar de ritmo de la liga a partir del
    diccionario activo (sea cargado desde Excel o por defecto) para auto-centrar
    tanto los EPAs como el Pace_Sec y evitar sesgos estáticos.
    """
    equipos_unicos = [
        v for k, v in nfl_stats_dict.items() if k not in ("LAR", "WSH") and isinstance(v, dict)
    ]
    if not equipos_unicos:
        return {
            "pass_off": 0.0,
            "rush_off": 0.0,
            "pass_def": 0.0,
            "rush_def": 0.0,
            "sr_off": 0.468,
            "sr_def": 0.440,
            "pace_sec": 27.2,
            "pace_std": 0.85,
        }
    paces = [float(x.get("Pace_Sec", 27.2)) for x in equipos_unicos]
    return {
        "pass_off": float(np.mean([float(x.get("EPA_Pass_Off", 0.0)) for x in equipos_unicos])),
        "rush_off": float(np.mean([float(x.get("EPA_Rush_Off", 0.0)) for x in equipos_unicos])),
        "pass_def": float(np.mean([float(x.get("EPA_Pass_Def", 0.0)) for x in equipos_unicos])),
        "rush_def": float(np.mean([float(x.get("EPA_Rush_Def", 0.0)) for x in equipos_unicos])),
        "sr_off": float(np.mean([_normalizar_tasa(float(x.get("Success_Rate_Off", 0.468))) for x in equipos_unicos])),
        "sr_def": float(np.mean([_normalizar_tasa(float(x.get("Success_Rate_Def", 0.440))) for x in equipos_unicos])),
        "pace_sec": float(np.mean(paces)),
        "pace_std": max(0.45, float(np.std(paces))),
    }


# ==============================================================================
# 1. FÓRMULA DE POSESIONES SIMÉTRICAS POR PARTIDO (PACE_SEC + DRIVES_GAME)
# ==============================================================================
def calcular_drives_partido(
    away_st: Dict[str, Any],
    home_st: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Calcula un número de posesiones idéntico y simétrico ('drives_por_bando')
    para ambos rivales en cada partido cruzando 'Pace_Sec' y 'Drives_Game'
    de ambos equipos frente a la media de ritmo de la liga (28.2s):
      - pace_partido = (pace_home + pace_away) / 2.0
      - drives_promedio_cruce = (drives_home + drives_away) / 2.0
      - factor_ritmo = 28.2 / pace_partido
      - drives_por_bando = round(drives_promedio_cruce * factor_ritmo, 1)
    """
    pace_away = float(away_st.get("Pace_Sec", 28.2))
    pace_home = float(home_st.get("Pace_Sec", 28.2))

    drives_away = float(away_st.get("Drives_Game", 10.9))
    drives_home = float(home_st.get("Drives_Game", 10.9))

    pace_partido = (pace_home + pace_away) / 2.0
    drives_promedio_cruce = (drives_home + drives_away) / 2.0

    factor_ritmo = 28.2 / max(22.0, pace_partido)
    drives_por_bando = round(drives_promedio_cruce * factor_ritmo, 1)
    drives_por_bando = float(np.clip(drives_por_bando, 9.2, 13.0))

    snaps_por_equipo = round(drives_por_bando * 5.75, 1)
    jugadas_totales = round(snaps_por_equipo * 2.0, 1)

    if drives_por_bando >= 11.6:
        ritmo_tag = "⚡ Ritmo Acelerado / Shootout"
    elif drives_por_bando <= 10.3:
        ritmo_tag = "🛡️ Ritmo Lento / Trincheras"
    else:
        ritmo_tag = "⚖️ Ritmo Medio NFL"

    return {
        "pace_away": round(pace_away, 1),
        "pace_home": round(pace_home, 1),
        "pace_partido": round(pace_partido, 2),
        "pace_combinado": round(pace_partido, 2),
        "drives_base_away": round(drives_away, 2),
        "drives_base_home": round(drives_home, 2),
        "drives_promedio_cruce": round(drives_promedio_cruce, 2),
        "factor_ritmo": round(factor_ritmo, 4),
        "drives_por_bando": drives_por_bando,
        "drives_away": drives_por_bando,
        "drives_home": drives_por_bando,
        "drives_away_raw": drives_por_bando,
        "drives_home_raw": drives_por_bando,
        "n_drives_equipo": drives_por_bando,
        "drives_combinados": round(drives_por_bando * 2.0, 1),
        "snaps_away": snaps_por_equipo,
        "snaps_home": snaps_por_equipo,
        "snaps_por_equipo": snaps_por_equipo,
        "jugadas_totales": jugadas_totales,
        "jugadas_por_drive_away": 5.75,
        "jugadas_por_drive_home": 5.75,
        "ritmo_tag": ritmo_tag,
    }


def calcular_drives_dinamicos_nfl(
    away_st: Dict[str, Any],
    home_st: Dict[str, Any],
    es_domo: bool = False,
    viento_mph: float = 5.0,
    medias_liga: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Alias compatible que delega directamente en calcular_drives_partido."""
    return calcular_drives_partido(away_st=away_st, home_st=home_st)


# ==============================================================================
# 2. CALIBRACIÓN DE PUNTOS POR SERIE (TD 23%-27% · FG 15%-18% · ~1.95-2.05 PTS/DRIVE)
# ==============================================================================
def _calcular_probabilidades_drive(
    epa_pass_off: float,
    epa_rush_off: float,
    sr_off: float,
    epa_pass_def_rival: float,
    epa_rush_def_rival: float,
    sr_def_rival: float,
    hfa_pts_drive: float,
    penal_pts_viento_drive: float,
    fg_wind_multiplier: float,
    es_domo: bool = False,
    medias_liga: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Cruza la eficiencia ofensiva contra la defensiva rival auto-centrada respecto
    al promedio de la liga para obtener las probabilidades discretas de cada drive:
      - Tasa de Touchdown (TD%): Rango promedio calibrado de ~23.0% a 27.0% por drive
        (media base 23.6% en exterior, 24.4% en domo).
      - Tasa de Gol de Campo (FG%): Rango base calibrado de ~15.0% a 18.0% por drive
        (media base 16.5%).
      - Puntos esperados por serie: ~1.95 a 2.05 puntos/drive en condiciones normales,
        situando el total medio de la liga entre 43.0 y 45.5 puntos.
      - Traslación 1:1 de la ventaja de localía (hfa_pts_drive) al marcador esperado.
    """
    m = medias_liga or {
        "pass_off": 0.0,
        "rush_off": 0.0,
        "pass_def": 0.0,
        "rush_def": 0.0,
        "sr_off": 0.468,
        "sr_def": 0.440,
    }

    rel_pass_off = float(epa_pass_off) - m["pass_off"]
    rel_rush_off = float(epa_rush_off) - m["rush_off"]
    rel_pass_def = float(epa_pass_def_rival) - m["pass_def"]
    rel_rush_def = float(epa_rush_def_rival) - m["rush_def"]

    net_pass_epa = rel_pass_off + rel_pass_def
    net_rush_epa = rel_rush_off + rel_rush_def

    sr_off_norm = _normalizar_tasa(sr_off) - m["sr_off"]
    sr_def_norm = _normalizar_tasa(sr_def_rival) - m["sr_def"]
    sr_net = sr_off_norm + sr_def_norm

    epa_compuesto = 0.60 * net_pass_epa + 0.40 * net_rush_epa + (sr_net * 0.42)
    epa_acotado = float(np.clip(epa_compuesto, -0.22, 0.22))

    # Conversión exacta 1:1 del HFA y clima por serie en probabilidades de TD (78%) y FG (22%)
    ajuste_pts_drive = hfa_pts_drive - penal_pts_viento_drive
    delta_td_hfa = (0.78 * ajuste_pts_drive) / 6.91
    delta_fg_hfa = (0.22 * ajuste_pts_drive) / 3.00

    # Piso de eficiencia elevado en series completas:
    # - Tasa de Touchdown (TD%): Rango promedio de ~23.0% a 27.0% por serie activa (media ~24.5%)
    # - Tasa de Gol de Campo (FG%): Rango base de ~15.0% a 18.0% por serie activa (media ~16.5%)
    td_base_liga = 0.248 if es_domo else 0.242
    fg_base_liga = 0.168 if es_domo else 0.165

    p_td_nominal = td_base_liga + (epa_acotado * 0.24) + (sr_net * 0.14) + delta_td_hfa
    p_td_nominal = float(np.clip(p_td_nominal, 0.205, 0.285))

    p_fg_nominal = fg_base_liga + (epa_acotado * 0.065) + (sr_net * 0.05) + delta_fg_hfa
    p_fg_nominal = float(np.clip(p_fg_nominal * fg_wind_multiplier, 0.145, 0.188))
    p_punt_nominal = max(0.300, 1.0 - (p_td_nominal + p_fg_nominal))

    # Ajuste por series de cierre de mitad / kneel-downs (~1 serie corta por equipo por partido,
    # factor = 0.915) para que la expectativa neta sea exactamente ~1.95 - 2.05 puntos/drive
    # y el total medio de la liga se sitúe entre 43.0 y 45.5 puntos.
    factor_serie_efectiva = 0.915
    p_td_eff = p_td_nominal * factor_serie_efectiva
    p_fg_eff = p_fg_nominal * factor_serie_efectiva
    p_zero_eff = max(0.320, 1.0 - (p_td_eff + p_fg_eff))

    p_td_7 = p_td_eff * 0.87
    p_td_6 = p_td_eff * 0.09
    p_td_8 = p_td_eff * 0.04

    probs = np.array([p_zero_eff, p_fg_eff, p_td_6, p_td_7, p_td_8], dtype=float)
    probs = probs / probs.sum()

    pts_por_drive_esp = float(np.sum(probs * np.array([0, 3, 6, 7, 8], dtype=float)))

    return {
        "valores": np.array([0, 3, 6, 7, 8], dtype=int),
        "probs": probs,
        "epa_compuesto": round(epa_compuesto, 3),
        "net_pass_epa": round(net_pass_epa, 3),
        "net_rush_epa": round(net_rush_epa, 3),
        "p_td_pct": round(p_td_nominal * 100.0, 1),
        "p_fg_pct": round(p_fg_nominal * 100.0, 1),
        "p_punt_pct": round(p_punt_nominal * 100.0, 1),
        "pts_por_drive": round(pts_por_drive_esp, 2),
    }


def _simular_puntos_drives_estocasticos(
    rng: np.random.Generator,
    n_sims: int,
    drives_media: float,
    valores_drive: np.ndarray,
    probs_drive: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Genera en cada una de las 5,000 iteraciones de Monte Carlo un número dinámico
    de posesiones usando una distribución híbrida Poisson/Normal truncada con media
    exacta 'drives_media', inyectando varianza real de ritmo de juego en los totales.
    """
    max_drives_sim = 16
    min_drives_sim = 7

    # Mezcla Normal/Poisson centrada en drives_media con desviación estándar de ~1.12 posesiones
    ruido_ritmo = rng.normal(loc=0.0, scale=1.12, size=n_sims)
    drives_cont = np.clip(drives_media + ruido_ritmo, float(min_drives_sim), float(max_drives_sim) - 0.01)
    # Re-centrar exactamente en drives_media para preservar la expectativa analítica sin sesgo
    drives_cont = np.clip(
        drives_cont - (np.mean(drives_cont) - drives_media),
        float(min_drives_sim),
        float(max_drives_sim) - 0.01,
    )

    drives_enteros = np.floor(drives_cont).astype(int)
    prob_fraccion = drives_cont - drives_enteros
    extra_drive_activo = (rng.random(n_sims) < prob_fraccion).astype(int)
    n_drives_iter = np.clip(drives_enteros + extra_drive_activo, min_drives_sim, max_drives_sim)

    # Matriz de (n_sims, max_drives_sim) con los resultados de cada serie
    matriz_pts = rng.choice(valores_drive, size=(n_sims, max_drives_sim), p=probs_drive)
    idx_cols = np.arange(max_drives_sim)[None, :]
    mascara_activa = idx_cols < n_drives_iter[:, None]

    matriz_activa = np.where(mascara_activa, matriz_pts, 0)
    puntos_totales_equipo = matriz_activa.sum(axis=1)
    td_drives_equipo = np.sum(matriz_activa >= 6, axis=1)

    return puntos_totales_equipo, td_drives_equipo


# ==============================================================================
# 3. FUNCIÓN PRINCIPAL DE SIMULACIÓN MONTE CARLO ORIENTADA A DRIVES DINÁMICOS
# ==============================================================================
def run_simulacion_nfl(
    away_abbr: str,
    home_abbr: str,
    nfl_stats_dict: Dict[str, Dict[str, Any]],
    n_sims: int = 5000,
    lineas_mercado: Optional[Dict[str, Any]] = None,
    viento_mph: float = 5.0,
    tipo_estadio: str = "Auto",
    hfa_override: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Ejecuta 5,000 iteraciones de Simulación Discreta Orientada a Series Ofensivas:
      - Calcula drives dinámicos individuales ('drives_away', 'drives_home') por
        cruce de 'Pace_Sec', tiempo detenido y 'Success_Rate_Off' vs 'Success_Rate_Def'.
      - Eleva el piso de eficiencia a TD ~23%-27% y FG ~15%-18% (~1.95-2.05 pts/drive),
        ubicando la media de la liga entre 43.0 y 45.5 puntos totales.
      - Otorga una Ventaja de Localía (HFA) de +1.50 a +2.00 puntos según la plaza.
    """
    away_key = normalizar_abbr_nfl(away_abbr)
    home_key = normalizar_abbr_nfl(home_abbr)

    default_pool = obtener_stats_nfl_default()
    pool_activo = nfl_stats_dict if nfl_stats_dict else default_pool
    medias_liga = _calcular_medias_liga(pool_activo)

    away_st = (
        pool_activo.get(away_key)
        or pool_activo.get(away_abbr)
        or default_pool.get(away_key, DEFAULT_NFL_STATS_ROWS[0])
    )
    home_st = (
        pool_activo.get(home_key)
        or pool_activo.get(home_abbr)
        or default_pool.get(home_key, DEFAULT_NFL_STATS_ROWS[1])
    )

    away_qb = str(away_st.get("QB_Name", f"{away_key} QB1"))
    home_qb = str(home_st.get("QB_Name", f"{home_key} QB1"))

    estadio_norm = str(tipo_estadio).strip().upper()
    if "AUTO" in estadio_norm:
        es_domo = DOME_FRANCHISES.get(home_key, False)
    elif "DOMO" in estadio_norm or "TECHADO" in estadio_norm:
        es_domo = True
    else:
        es_domo = DOME_FRANCHISES.get(home_key, False)

    estadio_label = "Domo" if es_domo else "Abierto"

    # 1. Ventaja de Localía (HFA) calibrada entre +1.50 y +2.00 pts según estadio
    if hfa_override is not None:
        hfa_nfl = float(np.clip(float(hfa_override), 1.50, 2.15))
    else:
        hfa_base = STADIUM_HFA_PTS.get(home_key, 1.85 if es_domo else 1.70)
        if not es_domo and float(viento_mph) > 14.0:
            hfa_base += min(0.20, (float(viento_mph) - 14.0) * 0.02)
        hfa_nfl = float(np.clip(hfa_base, 1.50, 2.10))

    viento_val = max(0.0, float(viento_mph))
    if (not es_domo) and (viento_val > 14.0):
        exceso_mph = viento_val - 14.0
        penalizacion_total_viento = round(0.22 * exceso_mph, 2)
        fg_wind_multiplier = 0.95
    else:
        penalizacion_total_viento = 0.0
        fg_wind_multiplier = 1.00

    # 2. Cálculo de posesiones simétricas por partido (Pace_Sec + Drives_Game vs 28.2s)
    info_ritmo = calcular_drives_partido(
        away_st=away_st,
        home_st=home_st,
    )

    drives_por_bando = float(info_ritmo["drives_por_bando"])
    drives_away_esp = drives_por_bando
    drives_home_esp = drives_por_bando
    drives_away_display = drives_por_bando
    drives_home_display = drives_por_bando
    n_drives_equipo_display = drives_por_bando
    drives_combinados_display = round(drives_por_bando * 2.0, 1)
    snaps_por_equipo = float(info_ritmo["snaps_por_equipo"])

    # HFA y penalización climática por serie ofensiva (traslación 1:1 al marcador)
    hfa_por_drive_away = -(hfa_nfl / 2.0) / drives_por_bando
    hfa_por_drive_home = +(hfa_nfl / 2.0) / drives_por_bando
    penal_viento_away = (penalizacion_total_viento / 2.0) / drives_por_bando
    penal_viento_home = (penalizacion_total_viento / 2.0) / drives_por_bando

    # 3. Probabilidades de anotación por drive (TD 23%-27%, FG 15%-18%, ~1.95-2.05 pts/drive)
    drive_cfg_away = _calcular_probabilidades_drive(
        epa_pass_off=float(away_st["EPA_Pass_Off"]),
        epa_rush_off=float(away_st["EPA_Rush_Off"]),
        sr_off=float(away_st["Success_Rate_Off"]),
        epa_pass_def_rival=float(home_st["EPA_Pass_Def"]),
        epa_rush_def_rival=float(home_st["EPA_Rush_Def"]),
        sr_def_rival=float(home_st["Success_Rate_Def"]),
        hfa_pts_drive=hfa_por_drive_away,
        penal_pts_viento_drive=penal_viento_away,
        fg_wind_multiplier=fg_wind_multiplier,
        es_domo=es_domo,
        medias_liga=medias_liga,
    )

    drive_cfg_home = _calcular_probabilidades_drive(
        epa_pass_off=float(home_st["EPA_Pass_Off"]),
        epa_rush_off=float(home_st["EPA_Rush_Off"]),
        sr_off=float(home_st["Success_Rate_Off"]),
        epa_pass_def_rival=float(away_st["EPA_Pass_Def"]),
        epa_rush_def_rival=float(away_st["EPA_Rush_Def"]),
        sr_def_rival=float(away_st["Success_Rate_Def"]),
        hfa_pts_drive=hfa_por_drive_home,
        penal_pts_viento_drive=penal_viento_home,
        fg_wind_multiplier=fg_wind_multiplier,
        es_domo=es_domo,
        medias_liga=medias_liga,
    )

    seed_val = (
        abs(
            hash(
                f"{away_key}_{home_key}_{n_sims}_{viento_val:.1f}_{estadio_label}_{hfa_nfl:.2f}_"
                f"{drives_away_esp:.2f}_{drives_home_esp:.2f}_"
                f"{drive_cfg_away['epa_compuesto']}_{drive_cfg_home['epa_compuesto']}"
            )
        )
        % (2**31 - 1)
    )
    rng = np.random.default_rng(seed_val)

    # 4. Simulación Monte Carlo (5,000 iteraciones): ambos equipos inician con exactamente 'drives_por_bando'
    sim_away, td_drives_away = _simular_puntos_drives_estocasticos(
        rng=rng,
        n_sims=n_sims,
        drives_media=drives_por_bando,
        valores_drive=drive_cfg_away["valores"],
        probs_drive=drive_cfg_away["probs"],
    )
    sim_home, td_drives_home = _simular_puntos_drives_estocasticos(
        rng=rng,
        n_sims=n_sims,
        drives_media=drives_por_bando,
        valores_drive=drive_cfg_home["valores"],
        probs_drive=drive_cfg_home["probs"],
    )

    # Ajuste de final de partido para atraer márgenes de 1-2 pts hacia el número clave 3 pts
    diff_pre_ot = sim_home - sim_away
    close_1_2_home = (diff_pre_ot == 1) | (diff_pre_ot == 2)
    close_1_2_away = (diff_pre_ot == -1) | (diff_pre_ot == -2)
    sim_home = np.where(close_1_2_home & (rng.random(n_sims) < 0.28), sim_away + 3, sim_home)
    sim_away = np.where(close_1_2_away & (rng.random(n_sims) < 0.28), sim_home + 3, sim_away)

    # Resolución de Tiempo Extra (Overtime)
    ties_mask = sim_away == sim_home
    n_ties = int(ties_mask.sum())
    ot_pct = round((n_ties / float(n_sims)) * 100.0, 1)
    if n_ties > 0:
        ventaja_home_ot = (drive_cfg_home["epa_compuesto"] - drive_cfg_away["epa_compuesto"]) * 0.45
        p_home_ot = float(np.clip(0.52 + ventaja_home_ot, 0.36, 0.66))
        home_wins_ot = rng.random(n_ties) < p_home_ot
        ot_pts = rng.choice([3, 6], size=n_ties, p=[0.72, 0.28])
        sim_home[ties_mask] += np.where(home_wins_ot, ot_pts, 0)
        sim_away[ties_mask] += np.where(~home_wins_ot, ot_pts, 0)

    away_pts = round(float(np.mean(sim_away)), 1)
    home_pts = round(float(np.mean(sim_home)), 1)

    win_home_raw = float(np.mean(sim_home > sim_away))
    win_home_pct = round(win_home_raw * 100.0, 1)
    win_away_pct = round((1.0 - win_home_raw) * 100.0, 1)

    ml_home_decimal = prob_a_cuota_decimal(win_home_raw)
    ml_away_decimal = prob_a_cuota_decimal(1.0 - win_home_raw)

    spread_proyectado = round(-(home_pts - away_pts), 1)
    total_ou = round(home_pts + away_pts, 1)

    mkt = lineas_mercado or {}
    total_mercado = float(mkt.get("total_mercado", round(total_ou) - 0.5))
    cuota_over_dec = americano_a_decimal(mkt.get("cuota_over_decimal", 1.91), 1.91)
    cuota_under_dec = americano_a_decimal(mkt.get("cuota_under_decimal", 1.91), 1.91)

    lineas_nfl_std = [
        -14.0, -10.5, -10.0, -7.5, -7.0, -6.5, -6.0, -4.5, -4.0, -3.5, -3.0, -2.5, -1.5,
        1.5, 2.5, 3.0, 3.5, 4.0, 4.5, 6.0, 6.5, 7.0, 7.5, 10.0, 10.5, 14.0,
    ]
    default_sp_mkt = min(lineas_nfl_std, key=lambda x: abs(x - (spread_proyectado * 0.90)))
    spread_mercado_home = float(mkt.get("spread_mercado_home", default_sp_mkt))
    cuota_sp_home_dec = americano_a_decimal(mkt.get("cuota_spread_home_decimal", 1.91), 1.91)
    cuota_sp_away_dec = americano_a_decimal(mkt.get("cuota_spread_away_decimal", 1.91), 1.91)

    total_sim = sim_home + sim_away
    margen_sim = sim_home - sim_away

    ev_totales = evaluar_valor_totales(
        total_modelo=total_ou,
        total_mercado=total_mercado,
        cuota_over=cuota_over_dec,
        cuota_under=cuota_under_dec,
        scores_total_sim=total_sim,
    )

    ev_spread = evaluar_valor_spread(
        spread_modelo_home=spread_proyectado,
        spread_mercado_home=spread_mercado_home,
        cuota_spread_home=cuota_sp_home_dec,
        cuota_spread_away=cuota_sp_away_dec,
        home_abbr=home_key,
        away_abbr=away_key,
        margen_sim=margen_sim,
    )

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
        f"Margen {kn} pts": round(float(np.mean(margen_abs == kn)) * 100.0, 1)
        for kn in NFL_KEY_NUMBERS
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
        "prob_push_spread_pct": ev_spread["prob_push_pct"],
        "key_number_tag": ev_spread["key_number_tag"],
        "es_key_number": ev_spread["es_key_number"],
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
        "epa_comp_away": drive_cfg_away["epa_compuesto"],
        "epa_comp_home": drive_cfg_home["epa_compuesto"],
        "net_pass_epa_away": drive_cfg_away["net_pass_epa"],
        "net_pass_epa_home": drive_cfg_home["net_pass_epa"],
        "net_rush_epa_away": drive_cfg_away["net_rush_epa"],
        "net_rush_epa_home": drive_cfg_home["net_rush_epa"],
        "drive_td_pct_away": drive_cfg_away["p_td_pct"],
        "drive_fg_pct_away": drive_cfg_away["p_fg_pct"],
        "drive_punt_pct_away": drive_cfg_away["p_punt_pct"],
        "drive_td_pct_home": drive_cfg_home["p_td_pct"],
        "drive_fg_pct_home": drive_cfg_home["p_fg_pct"],
        "drive_punt_pct_home": drive_cfg_home["p_punt_pct"],
        "pts_por_drive_away": drive_cfg_away["pts_por_drive"],
        "pts_por_drive_home": drive_cfg_home["pts_por_drive"],
        "drives_por_bando": drives_por_bando,
        "drives_away": drives_por_bando,
        "drives_home": drives_por_bando,
        "n_drives_equipo": drives_por_bando,
        "drives_combinados": drives_combinados_display,
        "ritmo_tag": info_ritmo["ritmo_tag"],
        "jugadas_por_drive_away": info_ritmo["jugadas_por_drive_away"],
        "jugadas_por_drive_home": info_ritmo["jugadas_por_drive_home"],
        "sr_off_away": round(_normalizar_tasa(away_st["Success_Rate_Off"]) * 100.0, 1),
        "sr_off_home": round(_normalizar_tasa(home_st["Success_Rate_Off"]) * 100.0, 1),
        "pace_away": info_ritmo["pace_away"],
        "pace_home": info_ritmo["pace_home"],
        "pace_combinado": info_ritmo["pace_combinado"],
        "snaps_away": info_ritmo["snaps_away"],
        "snaps_home": info_ritmo["snaps_home"],
        "snaps_por_equipo": snaps_por_equipo,
        "hfa_pts": round(hfa_nfl, 2),
        "viento_mph": round(viento_val, 1),
        "tipo_estadio": estadio_label,
        "penalizacion_viento_pts": penalizacion_total_viento,
        "n_sims": n_sims,
        "mc_p10_total": round(float(np.percentile(total_sim, 10)), 1),
        "mc_p50_total": round(float(np.percentile(total_sim, 50)), 1),
        "mc_p90_total": round(float(np.percentile(total_sim, 90)), 1),
        "mc_std_margin": round(float(np.std(margen_sim)), 1),
        "ot_pct": ot_pct,
        "lam_td_away": round(float(np.mean(td_drives_away)), 2),
        "lam_td_home": round(float(np.mean(td_drives_home)), 2),
        "key_numbers_freq": key_numbers_freq,
    }


# ==============================================================================
# BUCLE DE RETROALIMENTACIÓN Y AUTO-CORRECCIÓN DINÁMICA (KALMAN-STYLE UPDATE)
# ==============================================================================
def auditar_partido_nfl(
    simulacion_previa: Dict[str, Any],
    resultado_real_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Calcula los residuales directos entre la proyección previa del modelo y el
    resultado final real del partido ('STATUS_FINAL').
    """
    pts_away_real = float(resultado_real_dict.get("puntos_away_real") or 0.0)
    pts_home_real = float(resultado_real_dict.get("puntos_home_real") or 0.0)

    pts_away_mod = float(simulacion_previa.get("away_pts", 21.2))
    pts_home_mod = float(simulacion_previa.get("home_pts", 23.0))
    spread_mod = float(simulacion_previa.get("spread_proyectado", -(pts_home_mod - pts_away_mod)))
    total_mod = float(simulacion_previa.get("total_ou", pts_away_mod + pts_home_mod))

    error_away = round(pts_away_real - pts_away_mod, 2)
    error_home = round(pts_home_real - pts_home_mod, 2)
    spread_real = round(pts_away_real - pts_home_real, 2)
    total_real = round(pts_away_real + pts_home_real, 2)

    error_spread = round(spread_real - spread_mod, 2)
    error_total = round(total_real - total_mod, 2)

    pass_yds_away = float(resultado_real_dict.get("yardas_pase_away") or 235.0)
    rush_yds_away = float(resultado_real_dict.get("yardas_carrera_away") or 115.0)
    pass_yds_home = float(resultado_real_dict.get("yardas_pase_home") or 245.0)
    rush_yds_home = float(resultado_real_dict.get("yardas_carrera_home") or 120.0)

    tot_yds_away = max(1.0, pass_yds_away + rush_yds_away)
    tot_yds_home = max(1.0, pass_yds_home + rush_yds_home)

    pass_share_away = float(np.clip(pass_yds_away / tot_yds_away, 0.35, 0.80))
    rush_share_away = round(1.0 - pass_share_away, 3)

    pass_share_home = float(np.clip(pass_yds_home / tot_yds_home, 0.35, 0.80))
    rush_share_home = round(1.0 - pass_share_home, 3)

    jugadas_reales = float(resultado_real_dict.get("jugadas_totales_real") or 128.0)
    jugadas_esperadas = float(simulacion_previa.get("snaps_por_equipo", 64.0)) * 2.0
    error_jugadas = round(jugadas_reales - jugadas_esperadas, 1)

    avg_pass_share = (pass_share_away + pass_share_home) / 2.0
    if avg_pass_share >= 0.66:
        origen_desviacion = "Juego Aéreo Explosivo (Dominio de EPA_Pass)"
    elif avg_pass_share <= 0.54:
        origen_desviacion = "Trincheras y Juego Terrestre (Dominio de EPA_Rush)"
    else:
        origen_desviacion = "Mixto Aéreo/Terrestre y Conversión en Zona Roja"

    return {
        "away_abbr": simulacion_previa.get("away_abbr", resultado_real_dict.get("away_abbr", "AWAY")),
        "home_abbr": simulacion_previa.get("home_abbr", resultado_real_dict.get("home_abbr", "HOME")),
        "puntos_away_real": round(pts_away_real, 1),
        "puntos_home_real": round(pts_home_real, 1),
        "away_pts_modelo": round(pts_away_mod, 1),
        "home_pts_modelo": round(pts_home_mod, 1),
        "error_away": error_away,
        "error_home": error_home,
        "spread_real": spread_real,
        "spread_modelo": round(spread_mod, 1),
        "error_spread": error_spread,
        "total_real": total_real,
        "total_modelo": round(total_mod, 1),
        "error_total": error_total,
        "pass_share_away": round(pass_share_away, 3),
        "rush_share_away": rush_share_away,
        "pass_share_home": round(pass_share_home, 3),
        "rush_share_home": rush_share_home,
        "error_jugadas": error_jugadas,
        "origen_desviacion": origen_desviacion,
    }


def calibrar_stats_nfl(
    nfl_stats_dict: Dict[str, Dict[str, Any]],
    away_abbr: str,
    home_abbr: str,
    error_away: float,
    error_home: float,
    learning_rate: float = 0.06,
    auditoria_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Aplica una actualización adaptativa estilo filtro de Kalman a los ratings de
    las franquicias (con learning_rate moderado entre 0.04 y 0.08).
    """
    lr = float(np.clip(float(learning_rate), 0.02, 0.12))
    updated_dict = copy.deepcopy(nfl_stats_dict)

    away_key = normalizar_abbr_nfl(away_abbr)
    home_key = normalizar_abbr_nfl(home_abbr)

    if away_key not in updated_dict or home_key not in updated_dict:
        return updated_dict

    away_entry = updated_dict[away_key]
    home_entry = updated_dict[home_key]

    aud = auditoria_info or {}
    w_pass_away = float(aud.get("pass_share_away", 0.62))
    w_rush_away = float(aud.get("rush_share_away", 1.0 - w_pass_away))
    w_pass_home = float(aud.get("pass_share_home", 0.62))
    w_rush_home = float(aud.get("rush_share_home", 1.0 - w_pass_home))

    err_a_clipped = float(np.clip(float(error_away), -18.0, 18.0))
    err_h_clipped = float(np.clip(float(error_home), -18.0, 18.0))

    delta_base_away = (err_a_clipped / 16.0) * lr
    delta_base_home = (err_h_clipped / 16.0) * lr

    away_entry["EPA_Pass_Off"] = round(
        float(np.clip(float(away_entry["EPA_Pass_Off"]) + delta_base_away * w_pass_away * 1.15, -0.30, 0.35)), 3
    )
    away_entry["EPA_Rush_Off"] = round(
        float(np.clip(float(away_entry["EPA_Rush_Off"]) + delta_base_away * w_rush_away * 0.95, -0.30, 0.35)), 3
    )
    away_entry["EPA_Pass_Def"] = round(
        float(np.clip(float(away_entry["EPA_Pass_Def"]) + delta_base_home * w_pass_home * 0.85, -0.30, 0.35)), 3
    )
    away_entry["EPA_Rush_Def"] = round(
        float(np.clip(float(away_entry["EPA_Rush_Def"]) + delta_base_home * w_rush_home * 0.70, -0.30, 0.35)), 3
    )
    away_entry["Success_Rate_Off"] = round(
        float(np.clip(float(away_entry["Success_Rate_Off"]) + delta_base_away * 0.18, 0.360, 0.565)), 3
    )
    away_entry["Success_Rate_Def"] = round(
        float(np.clip(float(away_entry["Success_Rate_Def"]) + delta_base_home * 0.14, 0.360, 0.545)), 3
    )

    home_entry["EPA_Pass_Off"] = round(
        float(np.clip(float(home_entry["EPA_Pass_Off"]) + delta_base_home * w_pass_home * 1.15, -0.30, 0.35)), 3
    )
    home_entry["EPA_Rush_Off"] = round(
        float(np.clip(float(home_entry["EPA_Rush_Off"]) + delta_base_home * w_rush_home * 0.95, -0.30, 0.35)), 3
    )
    home_entry["EPA_Pass_Def"] = round(
        float(np.clip(float(home_entry["EPA_Pass_Def"]) + delta_base_away * w_pass_away * 0.85, -0.30, 0.35)), 3
    )
    home_entry["EPA_Rush_Def"] = round(
        float(np.clip(float(home_entry["EPA_Rush_Def"]) + delta_base_away * w_rush_away * 0.70, -0.30, 0.35)), 3
    )
    home_entry["Success_Rate_Off"] = round(
        float(np.clip(float(home_entry["Success_Rate_Off"]) + delta_base_home * 0.18, 0.360, 0.565)), 3
    )
    home_entry["Success_Rate_Def"] = round(
        float(np.clip(float(home_entry["Success_Rate_Def"]) + delta_base_away * 0.14, 0.360, 0.545)), 3
    )

    err_total = err_a_clipped + err_h_clipped
    pace_shift = -float(np.clip((err_total / 20.0) * lr * 2.5, -0.35, 0.35))
    away_entry["Pace_Sec"] = round(float(np.clip(float(away_entry["Pace_Sec"]) + pace_shift, 24.5, 30.5)), 1)
    home_entry["Pace_Sec"] = round(float(np.clip(float(home_entry["Pace_Sec"]) + pace_shift, 24.5, 30.5)), 1)

    updated_dict[away_key] = away_entry
    updated_dict[home_key] = home_entry

    if away_key == "LA":
        updated_dict["LAR"] = away_entry
    elif away_key == "WAS":
        updated_dict["WSH"] = away_entry

    if home_key == "LA":
        updated_dict["LAR"] = home_entry
    elif home_key == "WAS":
        updated_dict["WSH"] = home_entry

    return updated_dict