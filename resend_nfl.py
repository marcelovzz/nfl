#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MÓDULO 4: resend_nfl.py
Pipeline Automatizado Desatendido de "TERMINAL SHARP: NFL QUANT"
  - Consulta la cartelera activa de la semana en curso desde ESPN Scoreboard API / The Odds API
    (vía sync_espn_nfl.py) y audita el reporte oficial de bajas de ESPN (especialmente QBs
    titulares y jugadores clave) para alimentar el factor de reemplazo de QB.
  - Ejecuta las 5,000 simulaciones de Monte Carlo por partido mediante el generador
    discreto de anotaciones (TD=7/6/8, FG=3), filtro de situaciones competitivas (WP 5%-95%)
    y anclaje bayesiano al spread de consenso (engine_nfl.py).
  - Construye el DataFrame general de proyecciones y la hoja adicional
    'Ranking_Alta_Probabilidad' ordenada estrictamente de mayor a menor probabilidad
    de ocurrencia en los tres mercados principales (Moneyline, Spreads y Totales).
  - Empaqueta el libro Excel en memoria ('nfl_quant_projections.xlsx') con openpyxl,
    lo codifica en base64 y redacta un memorando ejecutivo institucional con los 3 mejores
    picks de la jornada (análisis de EPA/play competitivo, ventaja en trincheras y edge sin vig).
  - Envía el reporte HTML oscuro (#0d1117 con bordes #00ffcc) mediante un POST a
    https://api.resend.com/emails usando las variables de entorno RESEND_API_KEY y TO_EMAIL.
"""

import base64
import io
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import requests

from sync_espn_nfl import (
    ESPN_NFL_SCOREBOARD_URL,
    NFL_FRANCHISE_NAMES,
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
    simular_player_props_jornada,
)

RESEND_API_URL = "https://api.resend.com/emails"
ESPN_NFL_INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
DEFAULT_STATS_FILE = "nfl_stats.xlsx"
ATTACHMENT_FILENAME = "nfl_quant_projections.xlsx"


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

        sim_record = dict(sim)
        sim_record["semana"] = semana_activa
        sim_record["hora"] = p.get("hora", "DOM 13:00 ET")
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
    Genera el archivo Excel ('nfl_quant_projections.xlsx') en memoria con openpyxl
    incluyendo las hojas:
      1) 'Proyecciones_Generales'
      2) 'Ranking_Alta_Probabilidad' (ordenada estrictamente de mayor a menor probabilidad)
      3) 'Player_Props_Ranking' (ordenada multinivel: 1. Kickoff ASC, 2. Partido ASC,
         3. '% Cubre' DESC, con sombreado alternado y borde inferior por juego)
    Retorna los bytes crudos y la cadena codificada en base64 para la API de Resend.
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


def generar_memorando_ejecutivo_top3(
    resultados_simulados: List[Dict[str, Any]],
    nfl_stats: Dict[str, Dict[str, Any]],
    semana: int,
) -> List[Dict[str, Any]]:
    """
    Selecciona los 3 mejores picks cuantitativos de la jornada priorizando el Valor
    Esperado (+EV %) y la probabilidad calibrada, y redacta un memorando técnico
    fundamentado en:
      - EPA/play neto en situaciones competitivas (excluyendo garbage time WP < 5% o > 95%).
      - Diferencial en trincheras (Success Rate Ofensivo vs Defensivo y EPA Rush).
      - Valor de mercado desvigilado (No-Vig Fair Odds vs Línea de Consenso).
    """
    candidatos_picks: List[Dict[str, Any]] = []

    for sim in resultados_simulados:
        away = sim["away_abbr"]
        home = sim["home_abbr"]
        away_st = nfl_stats.get(away, {})
        home_st = nfl_stats.get(home, {})
        ev_spr = sim["ev_spread"]
        ev_tot = sim["ev_totales"]

        # Candidato Spread
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

        qb_nota = ""
        if sim.get("qb_descuento_away_pts", 0.0) > 0 or sim.get("qb_descuento_home_pts", 0.0) > 0:
            qb_nota = (
                f" Ajuste activo por reemplazo de QB titular "
                f"(Away: -{sim.get('qb_descuento_away_pts', 0.0):.1f} pts | "
                f"Home: -{sim.get('qb_descuento_home_pts', 0.0):.1f} pts)."
            )

        tesis_spread = (
            f"En situaciones competitivas (WP 5%–95%, depurando garbage time), {eq_pick} registra un "
            f"diferencial neto de EPA/dropback de {epa_pass_ventaja:+.3f} frente a la secundaria de {eq_rival}. "
            f"En las trincheras, la ofensiva de {eq_pick} sostiene un Success Rate de {sr_pick:.1f}% contra "
            f"{sr_def_rival:.1f}% permitido por la frontal de {eq_rival} (diferencial terrestre EPA/rush {epa_rush_ventaja:+.3f}). "
            f"Tras aplicar el anclaje bayesiano 40/60 al consenso, el modelo proyecta una línea justa de "
            f"{home} {sim['spread_proyectado']:+.1f} (cuota justa sin vig {ev_spr['fair_decimal']:.2f} vs mercado "
            f"{ev_spr['cuota_mercado_decimal']:.2f}), generando un edge de {ev_spr['edge_pts']:+.1f} pts "
            f"({ev_spr['key_number_tag']}).{qb_nota}"
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

        # Candidato Totales
        lado_tot = ev_tot["lado"]
        ritmo_desc = (
            f"ritmo combinado de {sim['pace_combinado']:.1f}s/play ({sim['drives_combinados']:.1f} series totales)"
        )
        tesis_total = (
            f"El cruce de eficiencia neta sin tiempo basura proyecta {sim['pts_por_drive_away']:.2f} pts/serie para {away} "
            f"(TD {sim['drive_td_pct_away']:.1f}%) y {sim['pts_por_drive_home']:.2f} pts/serie para {home} "
            f"(TD {sim['drive_td_pct_home']:.1f}%) bajo un {ritmo_desc}. "
            f"En trincheras y conversión de 3er down, el Success Rate combinado ({sim['sr_off_away']:.1f}% / {sim['sr_off_home']:.1f}%) "
            f"sitúa la media Monte Carlo en {sim['total_ou']:.1f} puntos frente a la línea de {ev_tot['total_mercado']:.1f} "
            f"(desviación de {ev_tot['edge_pts']:+.1f} pts). La probabilidad calibrada de {lado_tot} es de "
            f"{ev_tot['prob_mejor_pct']:.1f}% (cuota justa desvigilada {ev_tot['fair_decimal']:.2f} vs "
            f"{ev_tot['cuota_mercado_decimal']:.2f})."
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

    # Garantizar 3 partidos distintos en el Top 3 Ejecutivo
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
) -> str:
    """
    Construye el reporte ejecutivo HTML con estética institucional oscura (#0d1117),
    bordes en #00ffcc, memorando analítico de los Top 3 Picks y tabla completa
    de proyecciones y señales +EV (>= 4.0%).
    """
    fecha_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total_partidos = len(resultados_simulados)
    oportunidades_ev = sum(
        1
        for s in resultados_simulados
        if s["ev_spread"]["hay_valor"] or s["ev_totales"]["hay_valor"]
    )

    bloques_top3_html = ""
    for idx, item in enumerate(top_3_picks, start=1):
        ev_badge_color = "#00ffcc" if item["ev_pct"] >= 4.0 else "#38bdf8"
        bloques_top3_html += (
            f'<div style="background-color:#131922; border:1px solid rgba(0,255,204,0.35); '
            f'border-left:4px solid #00ffcc; border-radius:8px; padding:14px 16px; margin-bottom:12px;">'
            f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">'
            f'<span style="color:#00ffcc; font-family:monospace; font-size:13px; font-weight:800;">'
            f'PICK #{idx} · {item["partido"]} ({item["horario"]}) — {item["mercado"]}'
            f'</span>'
            f'<span style="background:rgba(0,255,204,0.14); color:{ev_badge_color}; border:1px solid {ev_badge_color}; '
            f'padding:2px 8px; border-radius:4px; font-family:monospace; font-size:12px; font-weight:700;">'
            f'{item["pick"]} | Prob: {item["prob_pct"]:.1f}% | EV: {item["ev_pct"]:+.1f}%'
            f'</span>'
            f'</div>'
            f'<div style="color:#94a3b8; font-family:monospace; font-size:12px; margin-bottom:6px;">'
            f'Proyección Calibrada: <b style="color:#f8fafc;">{item["marcador_proy"]}</b> · '
            f'Cuota Justa No-Vig: <b style="color:#00ffcc;">{item["fair_odds"]:.2f}</b> vs Casa: <b>{item["mkt_odds"]:.2f}</b>'
            f'</div>'
            f'<p style="color:#e6edf3; font-size:13px; line-height:1.5; margin:0;">{item["tesis"]}</p>'
            f'</div>'
        )

    filas_tabla_html = ""
    for s in resultados_simulados:
        away = s["away_abbr"]
        home = s["home_abbr"]
        ev_sp = s["ev_spread"]
        ev_to = s["ev_totales"]

        sp_cov_html = float(s.get("spread_cover_pct", ev_sp.get("spread_cover_pct", ev_sp.get("prob_mejor_pct", 50.0))))
        to_cov_html = float(s.get("total_cover_pct", ev_to.get("total_cover_pct", ev_to.get("prob_mejor_pct", 50.0))))

        if ev_sp["hay_valor"]:
            sp_cell = (
                f'<span style="color:#00ffcc; font-weight:700;">🔥 {ev_sp["recomendacion"]} '
                f'({ev_sp["cuota_mercado_decimal"]:.2f}) | Cubre: {sp_cov_html:.1f}% | EV: {ev_sp["ev_pct"]:+.1f}%</span>'
            )
        else:
            sp_cell = (
                f'<span style="color:#94a3b8;">⚪ {ev_sp["recomendacion"]} '
                f'| Cubre: {sp_cov_html:.1f}%</span>'
            )

        if ev_to["hay_valor"]:
            to_cell = (
                f'<span style="color:#00ffcc; font-weight:700;">🔥 {ev_to["lado"]} {ev_to["total_mercado"]:.1f} '
                f'({ev_to["cuota_mercado_decimal"]:.2f}) | Cubre: {to_cov_html:.1f}% | EV: {ev_to["ev_pct"]:+.1f}%</span>'
            )
        else:
            to_cell = (
                f'<span style="color:#94a3b8;">⚪ {ev_to["lado"]} {ev_to["total_mercado"]:.1f} '
                f'| Cubre: {to_cov_html:.1f}%</span>'
            )

        filas_tabla_html += (
            f'<tr style="border-bottom:1px solid #1e293b;">'
            f'<td style="padding:10px 8px; font-family:monospace; color:#f8fafc; font-weight:700;">'
            f'{away} @ {home}<br><span style="font-size:11px; color:#64748b; font-weight:400;">{s.get("hora", "")}</span></td>'
            f'<td style="padding:10px 8px; font-family:monospace; color:#10b981; font-weight:700;">'
            f'{away} {s["away_pts"]:.1f} - {s["home_pts"]:.1f} {home}</td>'
            f'<td style="padding:10px 8px; font-family:monospace; color:#e2e8f0;">'
            f'{home} {s["spread_proyectado"]:+.1f}<br>'
            f'<span style="font-size:11px; color:#94a3b8;">Mkt: {home} {s["spread_mercado_home"]:+.1f}</span></td>'
            f'<td style="padding:10px 8px; font-family:monospace; color:#e2e8f0;">'
            f'{s["total_ou"]:.1f} pts<br>'
            f'<span style="font-size:11px; color:#94a3b8;">Mkt: {s["total_mercado"]:.1f}</span></td>'
            f'<td style="padding:10px 8px; font-family:monospace; color:#38bdf8;">'
            f'{s["ml_fav_abbr"]} {s["ml_fav_model_pct"]:.1f}%<br>'
            f'<span style="font-size:11px; color:#94a3b8;">Fair: {min(s["ml_home_decimal"], s["ml_away_decimal"]):.2f}</span></td>'
            f'<td style="padding:10px 8px; font-family:monospace; font-size:12px;">{sp_cell}</td>'
            f'<td style="padding:10px 8px; font-family:monospace; font-size:12px;">{to_cell}</td>'
            f'</tr>'
        )

    bloques_top3_props_html = ""
    if top_3_props:
        items_props_html = ""
        for idx_p, prop in enumerate(top_3_props, start=1):
            items_props_html += (
                f'<div style="background-color:#131922; border:1px solid rgba(0,255,204,0.35); '
                f'border-left:4px solid #00ffcc; border-radius:8px; padding:12px 15px; margin-bottom:10px;">'
                f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">'
                f'<span style="color:#00ffcc; font-family:monospace; font-size:13px; font-weight:800;">'
                f'PROP #{idx_p} · {prop["jugador"]} ({prop["equipo"]} — {prop["posicion"]} · {prop["metrica"]}) | {prop["partido"]}'
                f'</span>'
                f'<span style="background:rgba(0,255,204,0.14); color:#00ffcc; border:1px solid #00ffcc; '
                f'padding:2px 8px; border-radius:4px; font-family:monospace; font-size:12px; font-weight:700;">'
                f'{prop["senal_ev"]}'
                f'</span>'
                f'</div>'
                f'<div style="color:#e2e8f0; font-family:monospace; font-size:12px;">'
                f'Línea: <b style="color:#f8fafc;">{prop["lado"]} {prop["linea"]:.1f}</b> · '
                f'Mediana Proyectada: <b style="color:#10b981;">{prop["mediana_proy"]:.1f}</b> (±{prop["std_dev"]:.1f}) · '
                f'Simulación Monte Carlo: <b style="color:#00ffcc;">{prop["pct_cubre"]:.1f}% cubre</b> · '
                f'Factor DvP Defensivo ({prop["rival"]}): <b style="color:#38bdf8;">{prop["factor_dvp"]:.3f}x</b>'
                f'</div>'
                f'</div>'
            )
        filas_cartera_props_html = ""
        if df_props_ranking is not None and not df_props_ranking.empty:
            df_pr_iter = df_props_ranking.reset_index(drop=True)
            total_pr = len(df_pr_iter)
            partido_prev = None
            bloque_idx = -1
            for idx_r, rp in df_pr_iter.iterrows():
                partido_act = str(rp.get("Partido", ""))
                kickoff_act = str(rp.get("Kickoff", "DOM"))
                partido_sig = (
                    str(df_pr_iter.iloc[idx_r + 1].get("Partido", ""))
                    if (idx_r + 1) < total_pr
                    else None
                )
                if partido_act != partido_prev:
                    bloque_idx += 1
                    n_juego = int((df_pr_iter["Partido"] == partido_act).sum())
                    filas_cartera_props_html += (
                        f'<tr style="background-color:#162235; border-top:2px solid #00ffcc; border-bottom:1px solid rgba(0,255,204,0.4);">'
                        f'<td colspan="9" style="padding:6px 10px; font-family:monospace; color:#00ffcc; font-weight:800; font-size:11px;">'
                        f'🏈 {partido_act} · Kickoff: {kickoff_act} — {n_juego} Props con Ventaja Matemática (+EV)'
                        f'</td></tr>'
                    )
                    partido_prev = partido_act

                bg_row = "#0b0f17" if (bloque_idx % 2 == 0) else "#111827"
                borde_inf = (
                    "2px solid #00ffcc"
                    if (partido_sig != partido_act)
                    else "1px solid #1e293b"
                )
                filas_cartera_props_html += (
                    f'<tr style="background-color:{bg_row}; border-bottom:{borde_inf};">'
                    f'<td style="padding:6px 8px; font-family:monospace; color:#00ffcc; font-weight:700;">#{int(rp["Rank"])}</td>'
                    f'<td style="padding:6px 8px; font-family:monospace; color:#94a3b8;">{kickoff_act}</td>'
                    f'<td style="padding:6px 8px; font-family:monospace; color:#f8fafc; font-weight:700;">{partido_act}</td>'
                    f'<td style="padding:6px 8px; font-family:monospace; color:#f8fafc; font-weight:700;">{rp["Jugador"]} ({rp["Posición"]})</td>'
                    f'<td style="padding:6px 8px; font-family:monospace; color:#94a3b8;">{rp["Métrica"]}</td>'
                    f'<td style="padding:6px 8px; font-family:monospace; color:#10b981; font-weight:700;">{float(rp["Proyección Mediana"]):.1f}</td>'
                    f'<td style="padding:6px 8px; font-family:monospace; color:#e2e8f0;">{float(rp["Línea Mercado"]):.1f} ({float(rp.get("Diferencia_Yds", 0.0)):+.1f})</td>'
                    f'<td style="padding:6px 8px; font-family:monospace; color:#38bdf8;">{float(rp["Factor DvP Rival"]):.3f}x</td>'
                    f'<td style="padding:6px 8px; font-family:monospace; color:#00ffcc; font-weight:700;">{rp["Señal EV"]}</td>'
                    f'</tr>'
                )

        tabla_cartera_inst_html = ""
        if filas_cartera_props_html:
            tabla_cartera_inst_html = (
                f'<h3 style="font-family:monospace; font-size:13px; color:#38bdf8; text-transform:uppercase; margin:16px 0 8px 0;">'
                f'📋 Player Props con Valor Positivo (+EV > 0% · Cubre ≥ 54.5%) Agrupados por Juego ({len(df_props_ranking)} Props Activos)'
                f'</h3>'
                f'<div style="overflow-x:auto;">'
                f'<table style="width:100%; border-collapse:collapse; background-color:#0b0f17; border:1px solid rgba(0,255,204,0.25); font-size:11px;">'
                f'<thead>'
                f'<tr style="background-color:#131b29; color:#00ffcc; font-family:monospace; text-align:left; border-bottom:1px solid #00ffcc;">'
                f'<th style="padding:7px 8px;">#</th>'
                f'<th style="padding:7px 8px;">Kickoff</th>'
                f'<th style="padding:7px 8px;">Partido</th>'
                f'<th style="padding:7px 8px;">Jugador</th>'
                f'<th style="padding:7px 8px;">Métrica</th>'
                f'<th style="padding:7px 8px;">Mediana Proy.</th>'
                f'<th style="padding:7px 8px;">Línea (Diff)</th>'
                f'<th style="padding:7px 8px;">DvP Rival</th>'
                f'<th style="padding:7px 8px;">Señal Cuantitativa (+EV)</th>'
                f'</tr>'
                f'</thead>'
                f'<tbody>{filas_cartera_props_html}</tbody>'
                f'</table>'
                f'</div>'
            )

        bloques_top3_props_html = (
            f'<h2 style="font-family:monospace; font-size:15px; color:#00ffcc; text-transform:uppercase; margin:22px 0 10px 0;">'
            f'🎯 Top 3 Player Props & Matchups Defensivos (5,000 Simulaciones Log-Normal)'
            f'</h2>'
            f'{items_props_html}'
            f'{tabla_cartera_inst_html}'
        )

    filas_top_prob_html = ""
    if not df_ranking.empty:
        for _, r in df_ranking.head(8).iterrows():
            filas_top_prob_html += (
                f'<tr style="border-bottom:1px solid #1e293b;">'
                f'<td style="padding:7px 8px; font-family:monospace; color:#00ffcc; font-weight:700;">#{int(r["Rank"])}</td>'
                f'<td style="padding:7px 8px; font-family:monospace; color:#f8fafc;">{r["Partido"]}</td>'
                f'<td style="padding:7px 8px; font-family:monospace; color:#94a3b8;">{r["Mercado"]}</td>'
                f'<td style="padding:7px 8px; font-family:monospace; color:#e2e8f0; font-weight:700;">{r["Seleccion"]}</td>'
                f'<td style="padding:7px 8px; font-family:monospace; color:#00ffcc; font-weight:800;">{float(r["Probabilidad_%"]):.1f}%</td>'
                f'<td style="padding:7px 8px; font-family:monospace; color:#38bdf8;">{float(r["EV_%"]):+.1f}%</td>'
                f'</tr>'
            )

    html = (
        f'<!DOCTYPE html>'
        f'<html><head><meta charset="utf-8"></head>'
        f'<body style="margin:0; padding:20px; background-color:#070a10; color:#e6edf3; font-family:Inter,Segoe UI,Arial,sans-serif;">'
        f'<div style="max-width:960px; margin:0 auto; background-color:#0d1117; border:2px solid #00ffcc; '
        f'border-radius:12px; padding:24px; box-shadow:0 12px 32px rgba(0,0,0,0.65);">'
        f'<div style="border-bottom:1px solid rgba(0,255,204,0.30); padding-bottom:14px; margin-bottom:18px;">'
        f'<div style="color:#00ffcc; font-family:monospace; font-size:12px; font-weight:700; letter-spacing:1px;">'
        f'QUANTITATIVE SPORTS MODELING DESK · MONTE CARLO DRIVE ENGINE (5,000 SIMS)'
        f'</div>'
        f'<h1 style="margin:6px 0 4px 0; font-family:monospace; font-size:22px; color:#f8fafc;">'
        f'🏈 TERMINAL SHARP: NFL QUANT — REPORTE EJECUTIVO SEMANA {semana}'
        f'</h1>'
        f'<div style="color:#94a3b8; font-size:12px; font-family:monospace;">'
        f'Generado: {fecha_utc} · Partidos Auditados: {total_partidos} · '
        f'Señales Activas (+EV ≥ 4.0%): <b style="color:#00ffcc;">{oportunidades_ev}</b> · '
        f'Anclaje Bayesiano 40/60 + Filtro WP (5%–95%)'
        f'</div>'
        f'</div>'
        f'<h2 style="font-family:monospace; font-size:15px; color:#00ffcc; text-transform:uppercase; margin:16px 0 10px 0;">'
        f'📌 Memorando Analítico: Top 3 Oportunidades Cuantitativas de la Jornada'
        f'</h2>'
        f'{bloques_top3_html}'
        f'<h2 style="font-family:monospace; font-size:15px; color:#00ffcc; text-transform:uppercase; margin:22px 0 10px 0;">'
        f'📊 Cartelera Completa, Proyecciones Discretas y Auditoría de Líneas (+EV ≥ 4.0%)'
        f'</h2>'
        f'<div style="overflow-x:auto;">'
        f'<table style="width:100%; border-collapse:collapse; background-color:#0b0f17; border:1px solid rgba(0,255,204,0.25); font-size:12px;">'
        f'<thead>'
        f'<tr style="background-color:#131b29; color:#00ffcc; font-family:monospace; text-align:left; border-bottom:1px solid #00ffcc;">'
        f'<th style="padding:10px 8px;">Encuentro</th>'
        f'<th style="padding:10px 8px;">Marcador Proy.</th>'
        f'<th style="padding:10px 8px;">Spread (Mod / Mkt)</th>'
        f'<th style="padding:10px 8px;">Total (Mod / Mkt)</th>'
        f'<th style="padding:10px 8px;">Moneyline Fav</th>'
        f'<th style="padding:10px 8px;">Señal Spread (+EV)</th>'
        f'<th style="padding:10px 8px;">Señal Totales (+EV)</th>'
        f'</tr>'
        f'</thead>'
        f'<tbody>{filas_tabla_html}</tbody>'
        f'</table>'
        f'</div>'
        f'<h2 style="font-family:monospace; font-size:15px; color:#00ffcc; text-transform:uppercase; margin:22px 0 10px 0;">'
        f'🏆 Extracto Hoja "Ranking_Alta_Probabilidad" (Top 8 Selecciones por Probabilidad)'
        f'</h2>'
        f'<div style="overflow-x:auto;">'
        f'<table style="width:100%; border-collapse:collapse; background-color:#0b0f17; border:1px solid rgba(0,255,204,0.25); font-size:12px;">'
        f'<thead>'
        f'<tr style="background-color:#131b29; color:#00ffcc; font-family:monospace; text-align:left; border-bottom:1px solid #00ffcc;">'
        f'<th style="padding:8px;">Rank</th>'
        f'<th style="padding:8px;">Partido</th>'
        f'<th style="padding:8px;">Mercado</th>'
        f'<th style="padding:8px;">Selección</th>'
        f'<th style="padding:8px;">Probabilidad</th>'
        f'<th style="padding:8px;">Edge / EV %</th>'
        f'</tr>'
        f'</thead>'
        f'<tbody>{filas_top_prob_html}</tbody>'
        f'</table>'
        f'</div>'
        f'{bloques_top3_props_html}'
        f'<div style="margin-top:18px; padding-top:12px; border-top:1px solid #1e293b; color:#64748b; font-size:11px; font-family:monospace;">'
        f'Adjunto: <b>{ATTACHMENT_FILENAME}</b> (Hojas: Proyecciones_Generales, Ranking_Alta_Probabilidad y Player_Props_Ranking). '
        f'Generado automáticamente por el pipeline desatendido de TERMINAL SHARP: NFL QUANT.'
        f'</div>'
        f'</div>'
        f'</body></html>'
    )
    return html


def enviar_reporte_resend_nfl(semana: Optional[int] = None) -> Dict[str, Any]:
    """
    Ejecuta el flujo completo de simulación, empaquetado Excel en base64 y
    despacho vía POST a 'https://api.resend.com/emails'.
    """
    sem, resultados, df_general, df_ranking, nfl_stats = ejecutar_pipeline_simulaciones_nfl(semana=semana)
    df_props_raw = simular_player_props_jornada(resultados, incluir_anytime_td=False)
    df_props_ranking = build_player_props_ranking_export_df(df_props_raw)
    top_3_props = obtener_top_3_player_props_jornada(df_props_raw)

    _, excel_b64 = empaquetar_excel_en_memoria(df_general, df_ranking, df_props_ranking)
    top_3 = generar_memorando_ejecutivo_top3(resultados, nfl_stats, semana=sem)
    html_body = construir_html_reporte_nfl(
        sem,
        resultados,
        top_3,
        df_ranking,
        top_3_props=top_3_props,
        df_props_ranking=df_props_ranking,
    )

    print(f"[TERMINAL SHARP NFL] Semana {sem} | Partidos simulados: {len(resultados)} | Player Props: {len(df_props_ranking)}")
    for idx, pick in enumerate(top_3, start=1):
        print(f"  Top #{idx}: {pick['partido']} -> {pick['pick']} (Prob: {pick['prob_pct']:.1f}% | EV: {pick['ev_pct']:+.1f}%)")
    for idx_p, prop in enumerate(top_3_props, start=1):
        print(
            f"  Prop #{idx_p}: {prop['jugador']} ({prop['partido']}) -> {prop['senal_ev']} | DvP: {prop['factor_dvp']:.3f}x"
        )

    resend_api_key = os.environ.get("RESEND_API_KEY", "").strip()
    to_email_raw = os.environ.get("TO_EMAIL", "").strip()

    if not resend_api_key or not to_email_raw:
        print(
            "[WARN] Variables de entorno RESEND_API_KEY o TO_EMAIL no definidas. "
            "Simulación y generación de Excel completadas correctamente en modo dry-run."
        )
        return {
            "enviado": False,
            "semana": sem,
            "partidos": len(resultados),
            "top_3": top_3,
        }

    destinatarios = [e.strip() for e in to_email_raw.split(",") if e.strip()]
    payload = {
        "from": "Terminal Sharp NFL <onboarding@resend.dev>",
        "to": destinatarios,
        "subject": f"🏈 TERMINAL SHARP: NFL QUANT — Semana {sem} | Proyecciones Monte Carlo & +EV",
        "html": html_body,
        "attachments": [
            {
                "filename": ATTACHMENT_FILENAME,
                "content": excel_b64,
            }
        ],
    }

    headers = {
        "Authorization": f"Bearer {resend_api_key}",
        "Content-Type": "application/json",
    }

    response = requests.post(RESEND_API_URL, headers=headers, json=payload, timeout=20)
    if response.status_code in (200, 201, 202):
        resp_data = response.json()
        print(f"[OK] Reporte NFL enviado exitosamente vía Resend. ID: {resp_data.get('id')}")
        return {
            "enviado": True,
            "id": resp_data.get("id"),
            "semana": sem,
            "partidos": len(resultados),
        }

    raise RuntimeError(
        f"Error al enviar correo en Resend API (HTTP {response.status_code}): {response.text}"
    )


if __name__ == "__main__":
    enviar_reporte_resend_nfl()
