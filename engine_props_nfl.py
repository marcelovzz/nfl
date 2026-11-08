"""
engine_props_nfl.py — Motor Cuantitativo de Simulación de Player Props NFL (5,000 Iteraciones)
Cruza la línea base individual ('Player_Props_Baseline') con los factores defensivos
por posición ('Def_DvP_RB', 'Def_DvP_WR1', 'Def_DvP_WR2', 'Def_DvP_TE' y 'EPA_Pass_Def')
desde 'nfl_stats1.xlsx' mediante simulaciones de Monte Carlo con distribución Log-Normal.
"""

from __future__ import annotations

import hashlib
import math
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

DEFAULT_PROPS_EXCEL_PATH = "nfl_stats1.xlsx"
FALLBACK_PROPS_EXCEL_PATH = "nfl_stats.xlsx"

DEFAULT_MARKET_ODDS_DEC = 1.91  # -110 Americano
BREAKEVEN_IMPLIED_PROB_PCT = 52.38  # 1 / 1.9091 (~52.38% sin vig estándar -110)

# Dispersión Log-Normal (sigma en espacio logarítmico) calibrada por posición NFL
LOGNORMAL_SIGMA_BY_POS: Dict[str, float] = {
    "QB": 0.25,
    "RB": 0.34,
    "WR": 0.38,
    "WR1": 0.38,
    "WR2": 0.40,
    "TE": 0.36,
}

METRICA_POR_POSICION: Dict[str, str] = {
    "QB": "Pass Yds",
    "RB": "Rush Yds",
    "WR": "Rec Yds",
    "WR1": "Rec Yds",
    "WR2": "Rec Yds",
    "TE": "Rec Yds",
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


def cargar_datos_props_nfl(
    excel_path: Optional[str] = None,
) -> Tuple[Dict[str, Dict[str, Any]], pd.DataFrame]:
    """
    Carga las hojas 'NFL_Stats' y 'Player_Props_Baseline' desde 'nfl_stats1.xlsx'.

    Retorna:
      - stats_por_equipo: Diccionario indexado por 'Team_Abbr' con métricas de equipo y Def_DvP.
      - df_props_baseline: DataFrame con ['Team', 'Player', 'Pos', 'Role_Share',
        'Catch_Rate', 'Yds_Per_Unit', 'Baseline_Yds', 'TD_Rate'].
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
        stats_por_equipo[abbr] = {
            "Team_Abbr": abbr,
            "QB_Name": str(row.get("QB_Name", "")),
            "EPA_Pass_Off": float(row.get("EPA_Pass_Off", 0.0) or 0.0),
            "EPA_Rush_Off": float(row.get("EPA_Rush_Off", 0.0) or 0.0),
            "EPA_Pass_Def": float(row.get("EPA_Pass_Def", 0.0) or 0.0),
            "EPA_Rush_Def": float(row.get("EPA_Rush_Def", 0.0) or 0.0),
            "Success_Rate_Off": float(row.get("Success_Rate_Off", 0.44) or 0.44),
            "Success_Rate_Def": float(row.get("Success_Rate_Def", 0.44) or 0.44),
            "Pace_Sec": float(row.get("Pace_Sec", 27.5) or 27.5),
            "Def_DvP_RB": float(row.get("Def_DvP_RB", 1.0) or 1.0),
            "Def_DvP_WR1": float(row.get("Def_DvP_WR1", 1.0) or 1.0),
            "Def_DvP_WR2": float(row.get("Def_DvP_WR2", 1.0) or 1.0),
            "Def_DvP_TE": float(row.get("Def_DvP_TE", 1.0) or 1.0),
            "Def_RZ_Stop_Pct": float(row.get("Def_RZ_Stop_Pct", 0.45) or 0.45),
        }

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
    linea_mercado_externa: Optional[float] = None,
    cuota_over_dec: float = DEFAULT_MARKET_ODDS_DEC,
    cuota_under_dec: float = DEFAULT_MARKET_ODDS_DEC,
    n_sims: int = 5000,
    wr_rank: int = 1,
) -> Dict[str, Any]:
    """
    Ejecuta 5,000 simulaciones de Monte Carlo con distribución Log-Normal para las
    yardas individuales del jugador:
      - Mediana proyectada = Baseline_Yds * Factor_DvP
      - mu_ln = ln(Mediana_Proyectada)
      - Evalúa % Cubre Over, % Cubre Under, Desviación Estándar y Edge (+EV %) contra
        la probabilidad implícita (52.38% a cuota 1.91 / -110).
    """
    pos_clean = pos.strip().upper()
    metrica = METRICA_POR_POSICION.get(pos_clean, "Rec Yds")

    base_yds = max(5.0, float(baseline_yds))
    mult_dvp = float(np.clip(factor_dvp, 0.60, 1.65))
    mediana_proyectada = round(base_yds * mult_dvp, 1)

    # Si no hay línea externa, los sportsbooks fijan la línea estándar anclada al
    # baseline del jugador con un ajuste parcial (25%) al matchup en medio punto (.5)
    if linea_mercado_externa is not None and linea_mercado_externa > 0:
        linea_mercado = float(linea_mercado_externa)
    else:
        ref_raw = (0.75 * base_yds) + (0.25 * mediana_proyectada)
        linea_mercado = _redondear_a_medio_punto(ref_raw)

    sigma_ln = float(LOGNORMAL_SIGMA_BY_POS.get(pos_clean, 0.36))
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

    # Suavizado bayesiano conservador para evitar probabilidades extremas irreales en cola
    over_prob = float(np.clip(0.50 + 0.72 * (over_emp - 0.50), 0.12, 0.88))
    under_prob = float(np.clip(1.0 - over_prob, 0.12, 0.88))

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

    edge_implicito_pct = round(pct_cubre_mejor - BREAKEVEN_IMPLIED_PROB_PCT, 1)
    es_destacado = (pct_cubre_mejor >= 56.0) or (ev_mejor_pct >= 5.0)

    if es_destacado:
        senal_ev = f"🔥 {lado_mejor} {linea_mercado:.1f} | Cubre: {pct_cubre_mejor:.1f}% | EV: {ev_mejor_pct:+.1f}%"
    else:
        senal_ev = f"⚪ {lado_mejor} {linea_mercado:.1f} | Cubre: {pct_cubre_mejor:.1f}% | EV: {ev_mejor_pct:+.1f}%"

    return {
        "Partido": partido_label,
        "Equipo": team_abbr,
        "Rival": opp_abbr,
        "Jugador": player_name,
        "Posición": pos_clean,
        "Métrica": metrica,
        "Baseline_Yds": round(base_yds, 1),
        "Factor DvP Rival": round(mult_dvp, 3),
        "Proyección Mediana": mediana_proyectada,
        "Media_MC": media_mc,
        "Desviación Estándar": std_mc,
        "Línea Mercado": round(linea_mercado, 1),
        "Cuota_Decimal": round(cuota_mejor, 2),
        "% Cubre Over": over_cover_pct,
        "% Cubre Under": under_cover_pct,
        "% Cubre": pct_cubre_mejor,
        "Lado_Recomendado": lado_mejor,
        "EV_%": ev_mejor_pct,
        "Edge_Implicito_%": edge_implicito_pct,
        "Es_Destacado": es_destacado,
        "Señal EV": senal_ev,
        "Role_Share": round(float(role_share), 3),
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
    n_sims: int = 5000,
) -> Dict[str, Any]:
    """
    Simula 5,000 iteraciones Poisson/Bernoulli para el mercado 'Anytime TD' (Línea 0.5 TD)
    ajustando la tasa base de TD del jugador ('TD_Rate') por el factor DvP defensivo rival.
    """
    pos_clean = pos.strip().upper()
    base_td = float(np.clip(td_rate, 0.05, 0.85))
    mult_dvp = float(np.clip(factor_dvp, 0.65, 1.55))

    # Tasa esperada de TD ajustada por el matchup defensivo
    lambda_td = max(0.04, base_td * (0.65 + 0.35 * mult_dvp))

    seed = _generar_semilla_jugador(team_abbr, opp_abbr, player_name, "Anytime_TD")
    rng = np.random.default_rng(seed)
    sim_tds = rng.poisson(lam=lambda_td, size=int(n_sims))

    prob_over_td = float(np.clip(np.mean(sim_tds >= 1), 0.08, 0.85))
    prob_under_td = float(np.clip(1.0 - prob_over_td, 0.15, 0.92))

    over_pct = round(prob_over_td * 100.0, 1)
    under_pct = round(prob_under_td * 100.0, 1)

    # Cuota de mercado de referencia para Anytime TD (OVER 0.5 TD) basada en TD_Rate base
    prob_base_mkt = float(np.clip(1.0 - math.exp(-base_td), 0.08, 0.75))
    cuota_over_mkt = round(max(1.30, (1.0 / prob_base_mkt) * 0.96), 2)

    ev_over_pct = round(((prob_over_td * cuota_over_mkt) - 1.0) * 100.0, 1)
    lado_mejor = "OVER"
    pct_cubre_mejor = over_pct
    ev_mejor_pct = ev_over_pct
    cuota_mejor = cuota_over_mkt

    linea_td = 0.5
    es_destacado = (pct_cubre_mejor >= 32.0 and ev_mejor_pct >= 5.0) or (ev_mejor_pct >= 5.0)
    if es_destacado:
        senal_ev = f"🔥 OVER {linea_td:.1f} TD ({cuota_mejor:.2f}) | Cubre: {pct_cubre_mejor:.1f}% | EV: {ev_mejor_pct:+.1f}%"
    else:
        senal_ev = f"⚪ OVER {linea_td:.1f} TD ({cuota_mejor:.2f}) | Cubre: {pct_cubre_mejor:.1f}% | EV: {ev_mejor_pct:+.1f}%"

    return {
        "Partido": partido_label,
        "Equipo": team_abbr,
        "Rival": opp_abbr,
        "Jugador": player_name,
        "Posición": pos_clean,
        "Métrica": "Anytime TD",
        "Baseline_Yds": round(base_td, 2),
        "Factor DvP Rival": round(mult_dvp, 3),
        "Proyección Mediana": round(lambda_td, 2),
        "Media_MC": round(float(np.mean(sim_tds)), 2),
        "Desviación Estándar": round(float(np.std(sim_tds)), 2),
        "Línea Mercado": linea_td,
        "Cuota_Decimal": cuota_mejor,
        "% Cubre Over": over_pct,
        "% Cubre Under": under_pct,
        "% Cubre": pct_cubre_mejor,
        "Lado_Recomendado": lado_mejor,
        "EV_%": ev_mejor_pct,
        "Edge_Implicito_%": round((prob_over_td - prob_base_mkt) * 100.0, 1),
        "Es_Destacado": es_destacado,
        "Señal EV": senal_ev,
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
    n_sims: int = 5000,
    incluir_anytime_td: bool = False,
) -> List[Dict[str, Any]]:
    """
    Simula los Player Props (5,000 iteraciones de Monte Carlo) para todos los titulares
    de Visitante (Team A) vs Local (Team B), cruzando cada jugador contra los factores
    defensivos 'Def_DvP' del equipo rival.
    """
    away = away_abbr.strip().upper()
    home = home_abbr.strip().upper()
    partido_label = f"{away} @ {home}"

    def_home = stats_por_equipo.get(home, {})
    def_away = stats_por_equipo.get(away, {})
    lineas_ext = lineas_mercado_props or {}

    resultados: List[Dict[str, Any]] = []
    if df_props_baseline is None or df_props_baseline.empty:
        return resultados

    for team_actual, opp_actual, def_rival in [
        (away, home, def_home),
        (home, away, def_away),
    ]:
        df_team = df_props_baseline[df_props_baseline["Team"] == team_actual]
        wr_counter = 0
        for _, row in df_team.iterrows():
            player_name = str(row.get("Player", "")).strip()
            pos = str(row.get("Pos", "WR")).strip().upper()
            baseline_yds = float(row.get("Baseline_Yds", 45.0) or 45.0)
            td_rate = float(row.get("TD_Rate", 0.20) or 0.20)
            role_share = float(row.get("Role_Share", 0.25) or 0.25)
            catch_rate = float(row.get("Catch_Rate", 0.65) or 0.65)
            yds_per_unit = float(row.get("Yds_Per_Unit", 7.5) or 7.5)

            if pos.startswith("WR"):
                wr_counter += 1
            wr_rank = wr_counter if pos.startswith("WR") else 1

            factor_dvp = obtener_factor_dvp_posicion(pos, def_rival, wr_rank=wr_rank)
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
                    n_sims=n_sims,
                )
                resultados.append(prop_td)

    return resultados


def simular_player_props_jornada(
    partidos_jornada: List[Dict[str, Any]],
    excel_path: Optional[str] = None,
    n_sims: int = 5000,
    incluir_anytime_td: bool = False,
) -> pd.DataFrame:
    """
    Ejecuta las 5,000 simulaciones de Monte Carlo de Player Props para todos los
    partidos de la jornada y retorna un DataFrame ordenado de forma estrictamente
    descendente por '% Cubre' (y desempate por 'EV_%').
    """
    stats_por_equipo, df_props_baseline = cargar_datos_props_nfl(excel_path=excel_path)
    todas_las_filas: List[Dict[str, Any]] = []

    for partido in partidos_jornada or []:
        away = str(partido.get("away_abbr", "")).strip().upper()
        home = str(partido.get("home_abbr", "")).strip().upper()
        if not away or not home:
            continue
        filas_partido = simular_player_props_partido(
            away_abbr=away,
            home_abbr=home,
            stats_por_equipo=stats_por_equipo,
            df_props_baseline=df_props_baseline,
            n_sims=n_sims,
            incluir_anytime_td=incluir_anytime_td,
        )
        todas_las_filas.extend(filas_partido)

    if not todas_las_filas:
        return pd.DataFrame(
            columns=[
                "Rank",
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
                "% Cubre Over",
                "% Cubre Under",
                "% Cubre",
                "EV_%",
                "Señal EV",
            ]
        )

    df_res = pd.DataFrame(todas_las_filas)
    df_res = df_res.sort_values(
        by=["% Cubre", "EV_%"], ascending=[False, False]
    ).reset_index(drop=True)
    df_res.insert(0, "Rank", range(1, len(df_res) + 1))
    return df_res


def build_player_props_ranking_export_df(df_props: pd.DataFrame) -> pd.DataFrame:
    """
    Formatea el DataFrame de Player Props para la hoja de Excel 'Player_Props_Ranking',
    ordenado de forma estrictamente descendente por '% Cubre'.
    """
    cols_export = [
        "Rank",
        "Partido",
        "Jugador",
        "Equipo",
        "Rival",
        "Posición",
        "Métrica",
        "Baseline_Yds",
        "Proyección Mediana",
        "Desviación Estándar",
        "Factor DvP Rival",
        "Línea Mercado",
        "% Cubre Over",
        "% Cubre Under",
        "% Cubre",
        "Lado_Recomendado",
        "EV_%",
        "Señal EV",
    ]
    if df_props is None or df_props.empty:
        return pd.DataFrame(columns=cols_export)

    df_out = df_props.copy()
    if "Métrica" in df_out.columns:
        # Priorizar props de yardas (Pass Yds / Rush Yds / Rec Yds) en el ranking principal de Excel
        df_yds = df_out[df_out["Métrica"] != "Anytime TD"]
        if not df_yds.empty:
            df_out = df_yds.copy()

    df_out = df_out.sort_values(
        by=["% Cubre", "EV_%"], ascending=[False, False]
    ).reset_index(drop=True)
    df_out["Rank"] = range(1, len(df_out) + 1)

    cols_presentes = [c for c in cols_export if c in df_out.columns]
    return df_out[cols_presentes]


def obtener_top_3_player_props_jornada(df_props: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Selecciona los 3 Player Props más sólidos de la jornada (ordenados por '% Cubre' y 'EV_%')
    para incluir en el reporte ejecutivo HTML enviado por Resend.
    """
    if df_props is None or df_props.empty:
        return []

    df_cand = df_props.copy()
    if "Métrica" in df_cand.columns:
        df_yds = df_cand[df_cand["Métrica"] != "Anytime TD"]
        if not df_yds.empty:
            df_cand = df_yds

    df_cand = df_cand.sort_values(
        by=["% Cubre", "EV_%"], ascending=[False, False]
    ).reset_index(drop=True)

    top_3: List[Dict[str, Any]] = []
    jugadores_vistos = set()
    for _, row in df_cand.iterrows():
        jug = str(row.get("Jugador", ""))
        if jug in jugadores_vistos:
            continue
        jugadores_vistos.add(jug)
        top_3.append(
            {
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
                "lado": str(row.get("Lado_Recomendado", "OVER")),
                "pct_cubre": float(row.get("% Cubre", 50.0)),
                "pct_over": float(row.get("% Cubre Over", 50.0)),
                "pct_under": float(row.get("% Cubre Under", 50.0)),
                "ev_pct": float(row.get("EV_%", 0.0)),
                "senal_ev": str(row.get("Señal EV", "")),
            }
        )
        if len(top_3) == 3:
            break

    return top_3
