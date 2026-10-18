import math
import os
import numpy as np
import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# ==============================================================================
# CONFIGURACIÓN DE PÁGINA Y ARQUITECTURA CYBER-QUANT / BLOOMBERG SPORTSBOOK
# ==============================================================================
st.set_page_config(
    page_title="TERMINAL SHARP: NFL QUANT SCANNER",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==============================================================================
# ESTILOS CSS: CYBER-QUANT UI (ORBITRON + JETBRAINS MONO)
# ==============================================================================
CYBER_QUANT_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Orbitron:wght@500;600;700;800;900&family=Inter:wght@400;500;600;700&display=swap');

:root {
    --bg-main: #060A12;
    --bg-panel: #0C1322;
    --bg-card: #111A2E;
    --bg-card-alt: #0E1729;
    --cyan-neon: #00F0FF;
    --green-sharp: #00E676;
    --amber-quant: #FFB300;
    --red-alert: #FF2E63;
    --purple-prop: #B388FF;
    --text-primary: #ECF2F8;
    --text-muted: #8A99AD;
    --border-subtle: rgba(0, 240, 255, 0.18);
    --border-strong: rgba(0, 240, 255, 0.42);
}

.stApp {
    background: radial-gradient(circle at 15% 10%, #0D1B30 0%, #060A12 55%, #04070D 100%);
    color: var(--text-primary);
    font-family: 'Inter', sans-serif;
}

/* Encabezado Principal Terminal */
.terminal-banner {
    background: linear-gradient(135deg, rgba(12, 19, 34, 0.96) 0%, rgba(17, 26, 46, 0.92) 100%);
    border: 1px solid var(--border-strong);
    border-left: 5px solid var(--cyan-neon);
    border-radius: 10px;
    padding: 18px 24px;
    margin-bottom: 18px;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.55), 0 0 18px rgba(0, 240, 255, 0.08);
}

.terminal-title {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.75rem;
    font-weight: 800;
    letter-spacing: 1.8px;
    color: #FFFFFF;
    margin: 0;
    text-transform: uppercase;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.terminal-subtitle {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
    color: var(--cyan-neon);
    letter-spacing: 0.8px;
    margin-top: 6px;
}

.live-pill {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 700;
    background: rgba(0, 230, 118, 0.14);
    color: var(--green-sharp);
    border: 1px solid var(--green-sharp);
    padding: 4px 10px;
    border-radius: 999px;
    letter-spacing: 1px;
}

/* Radar Ejecutivo de la Semana */
.radar-section-title {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.08rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: var(--cyan-neon);
    text-transform: uppercase;
    margin: 14px 0 12px 0;
    border-bottom: 1px solid var(--border-subtle);
    padding-bottom: 6px;
}

.radar-card {
    background: linear-gradient(180deg, rgba(17, 26, 46, 0.96) 0%, rgba(11, 17, 30, 0.98) 100%);
    border: 1px solid var(--border-subtle);
    border-top: 3px solid var(--cyan-neon);
    border-radius: 10px;
    padding: 15px 16px;
    height: 100%;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45);
}

.radar-card.lock { border-top-color: var(--green-sharp); }
.radar-card.total { border-top-color: var(--cyan-neon); }
.radar-card.star { border-top-color: var(--amber-quant); }
.radar-card.dog { border-top-color: var(--purple-prop); }

.radar-tag {
    font-family: 'Orbitron', sans-serif;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 1.1px;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 6px;
}

.radar-pick {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.06rem;
    font-weight: 800;
    color: #FFFFFF;
    margin-bottom: 6px;
}

.radar-metrics {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.80rem;
    color: var(--cyan-neon);
    margin-bottom: 4px;
}

.radar-sub {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.73rem;
    color: var(--text-muted);
}

/* Scoreboard TV Header */
.tv-scoreboard {
    background: linear-gradient(90deg, #0B1324 0%, #13203B 50%, #0B1324 100%);
    border: 1px solid var(--border-strong);
    border-radius: 12px;
    padding: 16px 22px;
    margin-top: 22px;
    margin-bottom: 12px;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.5);
}

.tv-top-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding-bottom: 8px;
    margin-bottom: 12px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: var(--text-muted);
}

.tv-main-grid {
    display: grid;
    grid-template-columns: 1.3fr 1fr 1.3fr;
    align-items: center;
    gap: 12px;
}

.team-side {
    display: flex;
    align-items: center;
    gap: 14px;
}

.team-side.right {
    justify-content: flex-end;
    text-align: right;
}

.team-badge {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.15rem;
    font-weight: 900;
    color: #060A12;
    background: linear-gradient(135deg, var(--cyan-neon), #00A8FF);
    padding: 10px 12px;
    border-radius: 8px;
    min-width: 58px;
    text-align: center;
    box-shadow: 0 0 12px rgba(0, 240, 255, 0.35);
}

.team-badge.home {
    background: linear-gradient(135deg, var(--green-sharp), #00B862);
    box-shadow: 0 0 12px rgba(0, 230, 118, 0.35);
}

.team-name-tv {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.05rem;
    font-weight: 800;
    color: #FFFFFF;
}

.team-epa-sub {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: var(--text-muted);
}

.score-center-box {
    text-align: center;
    background: rgba(6, 10, 18, 0.75);
    border: 1px solid rgba(0, 240, 255, 0.25);
    border-radius: 10px;
    padding: 10px 14px;
}

.projected-score-tv {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.55rem;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: 2px;
}

.projected-total-pill {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: var(--amber-quant);
    margin-top: 3px;
}

/* Tarjetas de Mercados y Props */
.quant-card {
    background: var(--bg-card);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 10px;
    padding: 14px 16px;
    height: 100%;
}

.quant-card-header {
    font-family: 'Orbitron', sans-serif;
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--cyan-neon);
    letter-spacing: 1px;
    text-transform: uppercase;
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
    padding-bottom: 6px;
    margin-bottom: 10px;
}

.metric-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 0;
    border-bottom: 1px dashed rgba(255, 255, 255, 0.06);
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
}

.metric-row:last-child {
    border-bottom: none;
}

.metric-label {
    color: var(--text-muted);
}

.metric-val {
    color: #FFFFFF;
    font-weight: 700;
}

.odds-chip {
    background: rgba(0, 240, 255, 0.12);
    color: var(--cyan-neon);
    border: 1px solid rgba(0, 240, 255, 0.3);
    padding: 2px 7px;
    border-radius: 5px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.76rem;
    font-weight: 600;
}

.odds-chip.green {
    background: rgba(0, 230, 118, 0.13);
    color: var(--green-sharp);
    border-color: rgba(0, 230, 118, 0.35);
}

.odds-chip.amber {
    background: rgba(255, 179, 0, 0.13);
    color: var(--amber-quant);
    border-color: rgba(255, 179, 0, 0.35);
}

.td-prop-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    margin-top: 8px;
}

.td-prop-box {
    background: rgba(6, 10, 18, 0.65);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-left: 3px solid var(--amber-quant);
    border-radius: 7px;
    padding: 8px 10px;
    font-family: 'JetBrains Mono', monospace;
}

.td-role {
    font-size: 0.68rem;
    color: var(--text-muted);
    text-transform: uppercase;
}

.td-player {
    font-size: 0.80rem;
    font-weight: 700;
    color: #FFFFFF;
    margin: 2px 0;
}

.td-prob {
    font-size: 0.84rem;
    font-weight: 800;
    color: var(--green-sharp);
}

.td-odds {
    font-size: 0.71rem;
    color: var(--cyan-neon);
}
</style>
"""
st.markdown(CYBER_QUANT_CSS, unsafe_allow_html=True)


# ==============================================================================
# 1. CARGA DIRECTA DESDE CSV LOCAL (nfl_stats_completo.csv) CON @st.cache_data
# ==============================================================================
@st.cache_data
def cargar_dataset_nfl(csv_path: str = "nfl_stats_completo.csv") -> pd.DataFrame:
    """
    Lee directamente el archivo local nfl_stats_completo.csv y lo indexa por 'Equipo'.
    """
    if not os.path.exists(csv_path):
        st.error(
            f"⚠️ No se encontró el archivo `{csv_path}` en el directorio del proyecto. "
            "Asegúrate de subir `nfl_stats_completo.csv` junto a `app.py` en tu repositorio de GitHub."
        )
        st.stop()
    df = pd.read_csv(csv_path)
    if "Equipo" in df.columns:
        df = df.set_index("Equipo")
    return df


# ==============================================================================
# 2. CALCULADORA DE FAIR ODDS (+EV) Y UTILIDADES MATEMÁTICAS
# ==============================================================================
def prob_to_fair_odds(prob: float) -> tuple[float, str]:
    """
    Convierte una probabilidad (0 a 1) en su Momio Justo (+EV):
    - Formato Decimal (ej. 1.91)
    - Formato Americano (ej. -110 / +125)
    """
    p = float(np.clip(prob, 0.005, 0.995))
    decimal_odds = round(1.0 / p, 2)
    if p >= 0.5:
        american_val = -int(round((p / (1.0 - p)) * 100.0))
        american_str = f"{american_val}"
    else:
        american_val = int(round(((1.0 - p) / p) * 100.0))
        american_str = f"+{american_val}"
    return decimal_odds, american_str


def poisson_pmf(k: int, lam: float) -> float:
    """Probabilidad exacta P(X = k) bajo distribución de Poisson."""
    lam = max(0.05, float(lam))
    return (math.exp(-lam) * (lam ** k)) / math.factorial(k)


def poisson_over_prob(threshold: float, lam: float) -> float:
    """Probabilidad exacta P(X > threshold), ej. Over 2.5 TDs => 1 - P(X <= 2)."""
    max_k = int(math.floor(threshold))
    cdf = sum(poisson_pmf(k, lam) for k in range(max_k + 1))
    return float(np.clip(1.0 - cdf, 0.01, 0.99))


# ==============================================================================
# 3. MOTOR CUANTITATIVO SHARP NFL (EPA + MONTECARLO + KEY NUMBERS + PROPS)
# ==============================================================================
NFL_REALISTIC_SCORES = {
    0: 0.35, 2: 0.05, 3: 0.65, 6: 0.72, 7: 0.85, 9: 0.60, 10: 1.15,
    12: 0.55, 13: 1.10, 14: 1.25, 15: 0.45, 16: 1.15, 17: 1.45,
    19: 0.70, 20: 1.50, 21: 1.35, 22: 0.55, 23: 1.35, 24: 1.60,
    26: 0.85, 27: 1.55, 28: 1.35, 29: 0.55, 30: 1.20, 31: 1.45,
    33: 0.75, 34: 1.25, 35: 1.10, 37: 0.85, 38: 1.05, 40: 0.60,
    41: 0.85, 42: 0.70, 44: 0.45, 45: 0.60, 48: 0.40
}

NFL_KEY_MARGIN_WEIGHTS = {
    1: 0.55, 2: 0.50, 3: 1.85, 4: 1.22, 5: 0.58, 6: 1.30, 7: 1.72,
    8: 0.92, 9: 0.55, 10: 1.45, 11: 0.62, 12: 0.52, 13: 0.88, 14: 1.40,
    15: 0.50, 16: 0.75, 17: 1.18, 18: 0.48, 19: 0.45, 20: 0.95, 21: 1.15
}


def obtener_iniciales(equipo_nombre: str, row: pd.Series) -> str:
    if "Abrev" in row and pd.notna(row["Abrev"]):
        return str(row["Abrev"])
    palabras = equipo_nombre.split()
    return "".join(p[0] for p in palabras[-2:]).upper()


def simular_partido_nfl(
    equipo_local: str,
    equipo_visita: str,
    df: pd.DataFrame,
    clima_frio_activo: bool = False,
    linea_total_mercado: float = 45.5,
    n_sims: int = 8000,
) -> dict:
    """
    Ejecuta el modelo cuantitativo completo para un partido NFL:
    1. Implied Team Totals vía cruce EPA Ofensivo vs Defensivo + Pace + Trincheras + Zona Roja + HFA.
    2. Simulación Montecarlo vectorizada (n_sims = 8,000) + Matriz Discretizada con Key Numbers NFL.
    3. Spread Justo, Moneyline, Total Proyectado y Team Totals.
    4. Motor Poisson / Bernoulli de Touchdowns de equipo y Anytime TD para RB1, WR1, TE1 y QB Rush.
    """
    loc = df.loc[equipo_local]
    vis = df.loc[equipo_visita]

    # --- A. RITMO Y VOLUMEN DE JUGADAS (PLAYS) ---
    pace_loc = float(loc["Pace_Sec"])
    pace_vis = float(vis["Pace_Sec"])
    pace_suma = pace_loc + pace_vis
    plays_por_equipo = 63.5 * (54.8 / max(46.0, pace_suma))
    plays_totales_juego = plays_por_equipo * 2.0

    pass_rate_loc = float(loc["Pass_Rate"]) if "Pass_Rate" in loc and pd.notna(loc["Pass_Rate"]) else 0.565
    pass_rate_vis = float(vis["Pass_Rate"]) if "Pass_Rate" in vis and pd.notna(vis["Pass_Rate"]) else 0.565

    def norm_pct(val: float) -> float:
        v = float(val)
        return v / 100.0 if v > 1.0 else v

    pass_sr_loc = norm_pct(loc["Pass_Success_Rate"])
    pass_sr_vis = norm_pct(vis["Pass_Success_Rate"])
    rz_td_loc = norm_pct(loc["RedZone_TD_Pct"])
    rz_td_vis = norm_pct(vis["RedZone_TD_Pct"])
    press_loc = norm_pct(loc["Pressure_Pct"])
    press_vis = norm_pct(vis["Pressure_Pct"])
    def_rz_stop_loc = norm_pct(loc["Def_RZ_Stop_Pct"])
    def_rz_stop_vis = norm_pct(vis["Def_RZ_Stop_Pct"])

    # --- B. FACTORES DE ENTORNO Y VENTAJAS DE LOCALÍA (HFA) ---
    es_domo = int(loc["Dome"]) == 1
    hfa_base = 1.92
    hfa_mod_estadio = float(loc["HFA_Mod"]) if "HFA_Mod" in loc and pd.notna(loc["HFA_Mod"]) else 0.18
    if es_domo:
        hfa_total = np.clip(hfa_base + hfa_mod_estadio * 0.65, 1.85, 2.25)
        dome_total_boost = 0.85
        penal_clima_loc = 0.0
        penal_clima_vis = 0.0
        entorno_tag = "🏟️ DOMO TECHADO (FAST TRACK)"
    else:
        dome_total_boost = 0.0
        hfa_total = np.clip(hfa_base + hfa_mod_estadio * 0.55, 1.80, 2.20)
        if clima_frio_activo:
            penal_clima_loc = float(loc["Cold_Weather_Drop"]) * 0.65
            mult_vis_domo = 1.35 if int(vis["Dome"]) == 1 else 1.0
            penal_clima_vis = float(vis["Cold_Weather_Drop"]) * mult_vis_domo
            hfa_total = min(2.35, hfa_total + 0.18)
            entorno_tag = "❄️ AIRE LIBRE / CLIMA ADVERSO"
        else:
            penal_clima_loc = float(loc["Cold_Weather_Drop"]) * 0.15
            penal_clima_vis = float(vis["Cold_Weather_Drop"]) * 0.20
            entorno_tag = "🌤️ AIRE LIBRE (CLIMA ESTÁNDAR)"

    # --- C. CRUCE DE EFICIENCIA EPA OFENSIVA VS DEFENSIVA Y TRINCHERAS ---
    trench_mismatch_loc = (press_vis - 0.245) * 0.45
    sr_boost_loc = (pass_sr_loc - 0.480) * 0.35
    net_pass_epa_loc = (
        float(loc["Pass_EPA"]) + float(vis["Def_Pass_EPA"])
        + sr_boost_loc - trench_mismatch_loc - penal_clima_loc
    )
    net_rush_epa_loc = float(loc["Rush_EPA"]) + float(vis["Def_Rush_EPA"])
    epa_play_loc = pass_rate_loc * net_pass_epa_loc + (1.0 - pass_rate_loc) * net_rush_epa_loc

    trench_mismatch_vis = (press_loc - 0.245) * 0.45
    sr_boost_vis = (pass_sr_vis - 0.480) * 0.35
    net_pass_epa_vis = (
        float(vis["Pass_EPA"]) + float(loc["Def_Pass_EPA"])
        + sr_boost_vis - trench_mismatch_vis - penal_clima_vis
    )
    net_rush_epa_vis = float(vis["Rush_EPA"]) + float(loc["Def_Rush_EPA"])
    epa_play_vis = pass_rate_vis * net_pass_epa_vis + (1.0 - pass_rate_vis) * net_rush_epa_vis

    # --- D. AJUSTE DE ZONA ROJA Y PUNTOS PROYECTADOS (IMPLIED TEAM TOTALS) ---
    rz_eff_loc = 0.55 * rz_td_loc + 0.45 * (1.0 - def_rz_stop_vis)
    rz_eff_vis = 0.55 * rz_td_vis + 0.45 * (1.0 - def_rz_stop_loc)
    rz_pts_adj_loc = (rz_eff_loc - 0.545) * 14.5
    rz_pts_adj_vis = (rz_eff_vis - 0.545) * 14.5

    base_pts_loc = plays_por_equipo * 0.348
    base_pts_vis = plays_por_equipo * 0.348

    pts_proj_loc = (
        base_pts_loc
        + (epa_play_loc * plays_por_equipo * 0.82)
        + rz_pts_adj_loc
        + (hfa_total / 2.0)
        + dome_total_boost
    )
    pts_proj_vis = (
        base_pts_vis
        + (epa_play_vis * plays_por_equipo * 0.82)
        + rz_pts_adj_vis
        - (hfa_total / 2.0)
        + dome_total_boost
    )

    pts_proj_loc = float(np.clip(pts_proj_loc, 12.5, 36.5))
    pts_proj_vis = float(np.clip(pts_proj_vis, 11.5, 35.5))

    total_proyectado = round(pts_proj_loc + pts_proj_vis, 1)
    spread_local = round(-(pts_proj_loc - pts_proj_vis), 1)

    # --- E. SIMULACIÓN MONTECARLO (POSESIONES NFL) + MATRIZ KEY NUMBERS ---
    seed_val = abs(hash(f"{equipo_local}_{equipo_visita}_{clima_frio_activo}")) % (2**31 - 1)
    rng = np.random.default_rng(seed_val)

    n_drives = int(round(11.0 * (plays_por_equipo / 63.5)))
    n_drives = max(10, min(13, n_drives))

    def simular_drives_equipo(pts_esperados: float, rz_eff: float) -> np.ndarray:
        pts_por_drive = pts_esperados / n_drives
        p_td = np.clip((pts_por_drive * (0.62 + 0.25 * (rz_eff - 0.54))) / 6.96, 0.08, 0.38)
        p_fg = np.clip((pts_por_drive - p_td * 6.96) / 3.0, 0.06, 0.26)
        p_safety = 0.004
        p_zero = max(0.10, 1.0 - (p_td + p_fg + p_safety))
        probs = np.array([p_zero, p_safety, p_fg, p_td * 0.08, p_td * 0.89, p_td * 0.03])
        probs = probs / probs.sum()
        valores_drive = np.array([0, 2, 3, 6, 7, 8])
        drives_matrix = rng.choice(valores_drive, size=(n_sims, n_drives), p=probs)
        return drives_matrix.sum(axis=1)

    scores_mc_loc = simular_drives_equipo(pts_proj_loc, rz_eff_loc)
    scores_mc_vis = simular_drives_equipo(pts_proj_vis, rz_eff_vis)

    empates_mask = scores_mc_loc == scores_mc_vis
    n_empates = int(empates_mask.sum())
    if n_empates > 0:
        p_ot_loc = np.clip(0.51 + (pts_proj_loc - pts_proj_vis) * 0.015, 0.35, 0.65)
        gana_loc_ot = rng.random(n_empates) < p_ot_loc
        pts_ot = rng.choice([3, 6], size=n_empates, p=[0.68, 0.32])
        scores_mc_loc[empates_mask] += np.where(gana_loc_ot, pts_ot, 0)
        scores_mc_vis[empates_mask] += np.where(~gana_loc_ot, pts_ot, 0)

    grid_scores = sorted(list(NFL_REALISTIC_SCORES.keys()))
    sigma_team = 9.4
    cluster_candidates = []
    for s_loc in grid_scores:
        if s_loc < 6 or s_loc > 45:
            continue
        w_score_loc = NFL_REALISTIC_SCORES[s_loc]
        dens_loc = math.exp(-0.5 * ((s_loc - pts_proj_loc) / sigma_team) ** 2) * w_score_loc
        for s_vis in grid_scores:
            if s_vis < 6 or s_vis > 45 or s_loc == s_vis:
                continue
            w_score_vis = NFL_REALISTIC_SCORES[s_vis]
            dens_vis = math.exp(-0.5 * ((s_vis - pts_proj_vis) / sigma_team) ** 2) * w_score_vis
            margen = abs(s_loc - s_vis)
            w_margen = NFL_KEY_MARGIN_WEIGHTS.get(margen, 0.42)
            if (pts_proj_loc >= pts_proj_vis and s_loc > s_vis) or (pts_proj_vis > pts_proj_loc and s_vis > s_loc):
                fav_align = 1.25
            else:
                fav_align = 0.78
            joint_weight = dens_loc * dens_vis * w_margen * fav_align
            cluster_candidates.append((joint_weight, s_loc, s_vis))

    cluster_candidates.sort(key=lambda x: x[0], reverse=True)
    total_cluster_w = sum(c[0] for c in cluster_candidates)
    marcador_exacto_loc = cluster_candidates[0][1]
    marcador_exacto_vis = cluster_candidates[0][2]
    top_3_marcadores = [
        {
            "Marcador": f"{c[1]} - {c[2]}",
            "Prob": round((c[0] / total_cluster_w) * 100.0, 2),
        }
        for c in cluster_candidates[:3]
    ]

    # --- F. PROBABILIDADES DE MERCADOS PRINCIPALES Y FAIR ODDS ---
    prob_ml_loc = float(np.mean(scores_mc_loc > scores_mc_vis))
    prob_norm_loc = 0.5 * (1.0 + math.erf((pts_proj_loc - pts_proj_vis) / (13.45 * math.sqrt(2.0))))
    prob_win_loc = float(np.clip(0.55 * prob_ml_loc + 0.45 * prob_norm_loc, 0.05, 0.95))
    prob_win_vis = 1.0 - prob_win_loc

    ml_dec_loc, ml_am_loc = prob_to_fair_odds(prob_win_loc)
    ml_dec_vis, ml_am_vis = prob_to_fair_odds(prob_win_vis)

    lineas_std_nfl = [-14.0, -10.5, -10.0, -9.5, -7.5, -7.0, -6.5, -4.5, -3.5, -3.0, -2.5, -1.5, 1.5, 2.5, 3.0, 3.5, 4.5, 6.5, 7.0, 7.5, 9.5, 10.0, 10.5, 14.0]
    spread_mercado_ref = min(lineas_std_nfl, key=lambda x: abs(x - (spread_local * 0.84)))

    margen_mc = scores_mc_loc - scores_mc_vis
    no_push_mask = (margen_mc + spread_mercado_ref) != 0
    if no_push_mask.sum() > 0:
        prob_cover_mc = float(np.mean((margen_mc[no_push_mask] + spread_mercado_ref) > 0))
    else:
        prob_cover_mc = 0.50
    prob_cover_analit = 0.5 * (1.0 + math.erf(((pts_proj_loc - pts_proj_vis) + spread_mercado_ref) / (13.45 * math.sqrt(2.0))))
    prob_cover_loc = float(np.clip(0.50 * prob_cover_mc + 0.50 * prob_cover_analit, 0.08, 0.92))
    prob_cover_vis = 1.0 - prob_cover_loc

    sp_dec_loc, sp_am_loc = prob_to_fair_odds(prob_cover_loc)
    sp_dec_vis, sp_am_vis = prob_to_fair_odds(prob_cover_vis)

    total_mc = scores_mc_loc + scores_mc_vis
    prob_over_mc = float(np.mean(total_mc > linea_total_mercado))
    prob_over_analit = 0.5 * (1.0 + math.erf((total_proyectado - linea_total_mercado) / (13.8 * math.sqrt(2.0))))
    prob_over = float(np.clip(0.50 * prob_over_mc + 0.50 * prob_over_analit, 0.08, 0.92))
    prob_under = 1.0 - prob_over

    ou_dec_over, ou_am_over = prob_to_fair_odds(prob_over)
    ou_dec_under, ou_am_under = prob_to_fair_odds(prob_under)

    # --- G. MÓDULO DE TOUCHDOWNS (POISSON / BERNOULLI Y ANYTIME TD) ---
    td_share_pts_loc = np.clip(0.68 + (rz_eff_loc - 0.52) * 0.45, 0.60, 0.84)
    td_share_pts_vis = np.clip(0.68 + (rz_eff_vis - 0.52) * 0.45, 0.60, 0.84)

    xtd_loc = round((pts_proj_loc * td_share_pts_loc) / 6.95, 2)
    xtd_vis = round((pts_proj_vis * td_share_pts_vis) / 6.95, 2)

    qb_rush_rate_loc = norm_pct(loc["QB_Rush_TD_Rate"])
    qb_rush_rate_vis = norm_pct(vis["QB_Rush_TD_Rate"])

    pass_td_ratio_loc = np.clip(pass_rate_loc + (net_pass_epa_loc - net_rush_epa_loc) * 0.25 - qb_rush_rate_loc * 0.35, 0.42, 0.76)
    pass_td_ratio_vis = np.clip(pass_rate_vis + (net_pass_epa_vis - net_rush_epa_vis) * 0.25 - qb_rush_rate_vis * 0.35, 0.42, 0.76)

    xtd_pass_loc = round(xtd_loc * pass_td_ratio_loc, 2)
    xtd_rush_loc = round(xtd_loc * (1.0 - pass_td_ratio_loc), 2)
    xtd_pass_vis = round(xtd_vis * pass_td_ratio_vis, 2)
    xtd_rush_vis = round(xtd_vis * (1.0 - pass_td_ratio_vis), 2)

    prob_o25_td_loc = poisson_over_prob(2.5, xtd_loc)
    prob_u25_td_loc = 1.0 - prob_o25_td_loc
    prob_o25_td_vis = poisson_over_prob(2.5, xtd_vis)
    prob_u25_td_vis = 1.0 - prob_o25_td_vis

    def calcular_props_equipo(row: pd.Series, xtd_team: float, equipo_str: str, abrev_str: str) -> list[dict]:
        roles = [
            ("RB1", "RB1_TD_Rate", "RB1_Nombre", "RB1"),
            ("WR1", "WR1_TD_Rate", "WR1_Nombre", "WR1"),
            ("TE1", "TE1_TD_Rate", "TE1_Nombre", "TE1"),
            ("QB RUSH", "QB_Rush_TD_Rate", "QB_Nombre", "QB"),
        ]
        props_out = []
        for rol_label, col_rate, col_nombre, default_tag in roles:
            td_rate = norm_pct(row[col_rate])
            nombre_jug = str(row[col_nombre]) if col_nombre in row and pd.notna(row[col_nombre]) else f"{abrev_str} {default_tag}"
            lam_player = max(0.04, xtd_team * td_rate)
            prob_atd = float(np.clip(1.0 - math.exp(-lam_player), 0.04, 0.88))
            dec_odd, am_odd = prob_to_fair_odds(prob_atd)
            props_out.append({
                "Equipo": equipo_str,
                "Abrev": abrev_str,
                "Rol": rol_label,
                "Jugador": nombre_jug,
                "xTD": round(lam_player, 2),
                "Prob": round(prob_atd * 100.0, 1),
                "Prob_Raw": prob_atd,
                "Fair_Dec": dec_odd,
                "Fair_Am": am_odd,
            })
        return props_out

    abrev_loc = obtener_iniciales(equipo_local, loc)
    abrev_vis = obtener_iniciales(equipo_visita, vis)

    props_loc = calcular_props_equipo(loc, xtd_loc, equipo_local, abrev_loc)
    props_vis = calcular_props_equipo(vis, xtd_vis, equipo_visita, abrev_vis)

    key_numbers_check = [3, 7, 10, 14, 6, 4]
    key_margins_dist = {}
    margen_abs = np.abs(margen_mc)
    for kn in key_numbers_check:
        mc_freq = float(np.mean(margen_abs == kn)) * 100.0
        key_margins_dist[f"Margen {kn} pts"] = round(max(2.5, mc_freq * 1.15), 1)

    return {
        "Local": equipo_local,
        "Visita": equipo_visita,
        "Abrev_Loc": abrev_loc,
        "Abrev_Vis": abrev_vis,
        "Entorno_Tag": entorno_tag,
        "Es_Domo": es_domo,
        "HFA_Pts": round(hfa_total, 2),
        "Plays_Por_Equipo": round(plays_por_equipo, 1),
        "Plays_Totales": round(plays_totales_juego, 1),
        "Pace_Suma": round(pace_suma, 1),
        "EPA_Play_Loc": round(epa_play_loc, 3),
        "EPA_Play_Vis": round(epa_play_vis, 3),
        "Net_Pass_EPA_Loc": round(net_pass_epa_loc, 3),
        "Net_Pass_EPA_Vis": round(net_pass_epa_vis, 3),
        "Net_Rush_EPA_Loc": round(net_rush_epa_loc, 3),
        "Net_Rush_EPA_Vis": round(net_rush_epa_vis, 3),
        "Press_Loc": round(press_loc * 100.0, 1),
        "Press_Vis": round(press_vis * 100.0, 1),
        "RZ_Eff_Loc": round(rz_eff_loc * 100.0, 1),
        "RZ_Eff_Vis": round(rz_eff_vis * 100.0, 1),
        "Pts_Loc": round(pts_proj_loc, 1),
        "Pts_Vis": round(pts_proj_vis, 1),
        "Total_Proyectado": total_proyectado,
        "Linea_Total_Mercado": linea_total_mercado,
        "Spread_Justo_Loc": spread_local,
        "Spread_Mercado_Ref": spread_mercado_ref,
        "Marcador_Exacto": f"{marcador_exacto_loc} - {marcador_exacto_vis}",
        "Marcador_Loc": marcador_exacto_loc,
        "Marcador_Vis": marcador_exacto_vis,
        "Top_3_Marcadores": top_3_marcadores,
        "Prob_Win_Loc": round(prob_win_loc * 100.0, 1),
        "Prob_Win_Vis": round(prob_win_vis * 100.0, 1),
        "ML_Dec_Loc": ml_dec_loc,
        "ML_Am_Loc": ml_am_loc,
        "ML_Dec_Vis": ml_dec_vis,
        "ML_Am_Vis": ml_am_vis,
        "Prob_Cover_Loc": round(prob_cover_loc * 100.0, 1),
        "Prob_Cover_Vis": round(prob_cover_vis * 100.0, 1),
        "SP_Dec_Loc": sp_dec_loc,
        "SP_Am_Loc": sp_am_loc,
        "SP_Dec_Vis": sp_dec_vis,
        "SP_Am_Vis": sp_am_vis,
        "Prob_Over": round(prob_over * 100.0, 1),
        "Prob_Under": round(prob_under * 100.0, 1),
        "OU_Dec_Over": ou_dec_over,
        "OU_Am_Over": ou_am_over,
        "OU_Dec_Under": ou_dec_under,
        "OU_Am_Under": ou_am_under,
        "xTD_Loc": xtd_loc,
        "xTD_Vis": xtd_vis,
        "xTD_Pass_Loc": xtd_pass_loc,
        "xTD_Rush_Loc": xtd_rush_loc,
        "xTD_Pass_Vis": xtd_pass_vis,
        "xTD_Rush_Vis": xtd_rush_vis,
        "Prob_O25_TD_Loc": round(prob_o25_td_loc * 100.0, 1),
        "Prob_U25_TD_Loc": round(prob_u25_td_loc * 100.0, 1),
        "O25_TD_Loc_Dec": prob_to_fair_odds(prob_o25_td_loc)[0],
        "O25_TD_Loc_Am": prob_to_fair_odds(prob_o25_td_loc)[1],
        "U25_TD_Loc_Dec": prob_to_fair_odds(prob_u25_td_loc)[0],
        "U25_TD_Loc_Am": prob_to_fair_odds(prob_u25_td_loc)[1],
        "Prob_O25_TD_Vis": round(prob_o25_td_vis * 100.0, 1),
        "Prob_U25_TD_Vis": round(prob_u25_td_vis * 100.0, 1),
        "O25_TD_Vis_Dec": prob_to_fair_odds(prob_o25_td_vis)[0],
        "O25_TD_Vis_Am": prob_to_fair_odds(prob_o25_td_vis)[1],
        "U25_TD_Vis_Dec": prob_to_fair_odds(prob_u25_td_vis)[0],
        "U25_TD_Vis_Am": prob_to_fair_odds(prob_u25_td_vis)[1],
        "Props_Loc": props_loc,
        "Props_Vis": props_vis,
        "Key_Margins_Dist": key_margins_dist,
    }


# ==============================================================================
# 4. GESTIÓN DE SESSION STATE Y CONFIGURACIÓN INICIAL DE 16 JUEGOS
# ==============================================================================
df_nfl = cargar_dataset_nfl("nfl_stats_completo.csv")
lista_equipos = list(df_nfl.index)

DEFAULT_16_MATCHUPS = [
    ("Kansas City Chiefs", "Baltimore Ravens"),
    ("San Francisco 49ers", "Detroit Lions"),
    ("Buffalo Bills", "Miami Dolphins"),
    ("Philadelphia Eagles", "Dallas Cowboys"),
    ("Cincinnati Bengals", "New England Patriots"),
    ("Houston Texans", "Indianapolis Colts"),
    ("Green Bay Packers", "Chicago Bears"),
    ("Los Angeles Rams", "Seattle Seahawks"),
    ("Minnesota Vikings", "New York Giants"),
    ("New York Jets", "Cleveland Browns"),
    ("Pittsburgh Steelers", "Atlanta Falcons"),
    ("Tampa Bay Buccaneers", "Washington Commanders"),
    ("Jacksonville Jaguars", "Tennessee Titans"),
    ("Los Angeles Chargers", "Las Vegas Raiders"),
    ("New Orleans Saints", "Carolina Panthers"),
    ("Denver Broncos", "Arizona Cardinals"),
]

if "expander_open" not in st.session_state:
    st.session_state.expander_open = True

if "scan_ejecutado" not in st.session_state:
    st.session_state.scan_ejecutado = False

if "num_juegos_activos" not in st.session_state:
    st.session_state.num_juegos_activos = min(8, max(1, len(lista_equipos) // 2))

if "clima_invierno" not in st.session_state:
    st.session_state.clima_invierno = False

if "linea_mercado_base" not in st.session_state:
    st.session_state.linea_mercado_base = 45.5

if "partidos_seleccionados" not in st.session_state:
    partidos_init = []
    for idx in range(16):
        loc_def, vis_def = DEFAULT_16_MATCHUPS[idx % len(DEFAULT_16_MATCHUPS)]
        if loc_def not in lista_equipos:
            loc_def = lista_equipos[idx % len(lista_equipos)]
        if vis_def not in lista_equipos or vis_def == loc_def:
            vis_def = lista_equipos[(idx + 1) % len(lista_equipos)]
        partidos_init.append({"local": loc_def, "visita": vis_def})
    st.session_state.partidos_seleccionados = partidos_init


# ==============================================================================
# 5. BARRA LATERAL: CONTROLES DEL SINDICATO Y EXPLORADOR DEL CSV LOCAL
# ==============================================================================
with st.sidebar:
    st.markdown(
        """
        <div style='font-family: Orbitron, sans-serif; font-size: 1.05rem; font-weight: 800; color: #00F0FF; letter-spacing: 1px;'>
            ⚡ SHARP SYNDICATE TERMINAL
        </div>
        <div style='font-family: JetBrains Mono, monospace; font-size: 0.74rem; color: #8A99AD; margin-bottom: 14px;'>
            MOTOR: EPA/PLAY + MONTECARLO 8,000x
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("🔓 Abrir Configurador de Semana", use_container_width=True):
        st.session_state.expander_open = True

    st.markdown("### 📂 Dataset Local (`nfl_stats_completo.csv`)")
    ver_tabla_csv = st.checkbox("Mostrar tabla de equipos cargada", value=False)

    st.markdown("### 📐 Arquitectura Cuantitativa")
    st.markdown(
        """
        - **Implied Team Total**: `EPA/Play` ponderado por `Pace_Sec` + `RedZone_TD_Pct` vs `Def_RZ_Stop_Pct`.
        - **HFA Dinámico**: `1.80` a `2.25` pts según Domo, acústica y penalización climática (`Cold_Weather_Drop`).
        - **Key Numbers NFL**: Prioriza márgenes `3, 7, 10, 14, 6, 4` y penaliza marcadores muertos.
        - **Touchdowns & Props**: Motor Poisson / Bernoulli exacto (`1 - e^-λ`).
        """
    )


# ==============================================================================
# 6. ENCABEZADO DE LA TERMINAL Y VISTA DEL DATASET BASE
# ==============================================================================
st.markdown(
    """
    <div class="terminal-banner">
        <div class="terminal-title">
            <span>🏈 TERMINAL SHARP: NFL QUANT SCANNER</span>
            <span class="live-pill">● CSV ENGINE v4.5</span>
        </div>
        <div class="terminal-subtitle">
            BLOOMBERG SPORTSBOOK ANALYTICS // EPA MATCHUP MATRIX • MONTECARLO KEY-NUMBER CLUSTERING • POISSON TD PROPS • FAIR ODDS (+EV)
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if ver_tabla_csv:
    with st.expander("📂 BACKEND DATASET: `nfl_stats_completo.csv` (Indexado por Equipo)", expanded=True):
        st.dataframe(df_nfl, use_container_width=True)


# ==============================================================================
# 7. FORMULARIO DE LOS 16 JUEGOS SEMANALES (st.form + st.expander auto-close)
# ==============================================================================
def callback_cerrar_expander():
    """Cierra el st.expander automáticamente al enviar el formulario."""
    st.session_state.expander_open = False
    st.session_state.scan_ejecutado = True


with st.expander(
    "🎛️ CONFIGURADOR DEL GAME WEEK SCANNER (HASTA 16 PARTIDOS NFL)",
    expanded=st.session_state.expander_open,
):
    with st.form("form_semana_nfl"):
        col_cfg1, col_cfg2, col_cfg3 = st.columns([1.2, 1.2, 1.6])
        with col_cfg1:
            num_juegos = st.slider(
                "Número de Juegos de la Semana a Escanear",
                min_value=1,
                max_value=16,
                value=st.session_state.num_juegos_activos,
                step=1,
            )
        with col_cfg2:
            linea_total_ref = st.select_slider(
                "Línea de Mercado Referencia Over/Under (Pts)",
                options=[43.5, 44.0, 44.5, 45.0, 45.5, 46.0, 46.5, 47.0, 47.5],
                value=st.session_state.linea_mercado_base,
            )
        with col_cfg3:
            clima_frio = st.checkbox(
                "❄️ Activar Factor de Clima Invernal / Viento en Estadios Abiertos (Cold Weather Drop)",
                value=st.session_state.clima_invierno,
            )

        st.markdown("##### Selección de Cruces (Visita @ Local — 16 Slots Disponibles)")
        nuevos_partidos = []
        for row_idx in range(4):
            cols_games = st.columns(4)
            for col_idx in range(4):
                game_i = row_idx * 4 + col_idx
                with cols_games[col_idx]:
                    activo_tag = "🟢" if game_i < num_juegos else "⚪"
                    st.markdown(f"**{activo_tag} Juego #{game_i + 1}**")
                    default_vis = st.session_state.partidos_seleccionados[game_i]["visita"]
                    default_loc = st.session_state.partidos_seleccionados[game_i]["local"]
                    idx_vis = lista_equipos.index(default_vis) if default_vis in lista_equipos else 0
                    idx_loc = lista_equipos.index(default_loc) if default_loc in lista_equipos else min(1, len(lista_equipos) - 1)
                    vis_sel = st.selectbox(
                        f"Visita #{game_i + 1}",
                        options=lista_equipos,
                        index=idx_vis,
                        key=f"vis_select_{game_i}",
                    )
                    loc_sel = st.selectbox(
                        f"Local #{game_i + 1}",
                        options=lista_equipos,
                        index=idx_loc,
                        key=f"loc_select_{game_i}",
                    )
                    nuevos_partidos.append({"local": loc_sel, "visita": vis_sel})

        submitted = st.form_submit_button(
            "🚀 EJECUTAR ESCANEO CUANTITATIVO DE LA SEMANA (SHARP SCAN)",
            use_container_width=True,
            on_click=callback_cerrar_expander,
        )

        if submitted:
            st.session_state.num_juegos_activos = num_juegos
            st.session_state.linea_mercado_base = linea_total_ref
            st.session_state.clima_invierno = clima_frio
            st.session_state.partidos_seleccionados = nuevos_partidos


# ==============================================================================
# 8. VALIDACIÓN DE ERRORES Y EJECUCIÓN DEL ESCANEO SEMANAL
# ==============================================================================
juegos_a_procesar = st.session_state.partidos_seleccionados[: st.session_state.num_juegos_activos]
errores_mismo_equipo = []
partidos_validos = []

for idx, p in enumerate(juegos_a_procesar):
    if p["local"] == p["visita"]:
        errores_mismo_equipo.append(
            f"⚠️ Error en Juego #{idx + 1}: **{p['local']}** no puede jugar contra sí mismo. Selecciona un rival distinto."
        )
    else:
        partidos_validos.append((idx + 1, p["local"], p["visita"]))

if errores_mismo_equipo:
    for err_msg in errores_mismo_equipo:
        st.error(err_msg)

if not partidos_validos:
    st.warning("Configura al menos un partido válido (Local ≠ Visita) para visualizar el escaneo cuantitativo.")
    st.stop()

resultados_semana = [
    simular_partido_nfl(
        equipo_local=loc_team,
        equipo_visita=vis_team,
        df=df_nfl,
        clima_frio_activo=st.session_state.clima_invierno,
        linea_total_mercado=st.session_state.linea_mercado_base,
    )
    for _, loc_team, vis_team in partidos_validos
]


# ==============================================================================
# 9. RADAR EJECUTIVO DE LA SEMANA (TOP 4 PICKS DEL SINDICATO)
# ==============================================================================
mejor_lock = None
mejor_lock_score = -1.0
for r in resultados_semana:
    if r["Prob_Win_Loc"] >= r["Prob_Win_Vis"]:
        score_cand = 0.60 * r["Prob_Win_Loc"] + 0.40 * r["Prob_Cover_Loc"]
        cand = {
            "Equipo": r["Local"],
            "Rival": r["Visita"],
            "Mercado": f"ML ({r['ML_Am_Loc']}) / Spread {r['Spread_Mercado_Ref']:+.1f}",
            "Prob_ML": r["Prob_Win_Loc"],
            "Fair_Dec": r["ML_Dec_Loc"],
            "Fair_Am": r["ML_Am_Loc"],
            "Spread_Proj": f"{r['Spread_Justo_Loc']:+.1f}",
            "Marcador": r["Marcador_Exacto"],
        }
    else:
        score_cand = 0.60 * r["Prob_Win_Vis"] + 0.40 * r["Prob_Cover_Vis"]
        cand = {
            "Equipo": r["Visita"],
            "Rival": r["Local"],
            "Mercado": f"ML ({r['ML_Am_Vis']}) / Spread {-r['Spread_Mercado_Ref']:+.1f}",
            "Prob_ML": r["Prob_Win_Vis"],
            "Fair_Dec": r["ML_Dec_Vis"],
            "Fair_Am": r["ML_Am_Vis"],
            "Spread_Proj": f"{-r['Spread_Justo_Loc']:+.1f}",
            "Marcador": r["Marcador_Exacto"],
        }
    if score_cand > mejor_lock_score:
        mejor_lock_score = score_cand
        mejor_lock = cand

mejor_total = None
mejor_total_edge = -1.0
for r in resultados_semana:
    linea_comp = float(np.clip(r["Linea_Total_Mercado"], 43.5, 47.5))
    diff_pts = r["Total_Proyectado"] - linea_comp
    edge_abs = abs(diff_pts)
    if edge_abs > mejor_total_edge:
        mejor_total_edge = edge_abs
        es_over = diff_pts >= 0
        prob_sel = r["Prob_Over"] if es_over else r["Prob_Under"]
        dec_sel = r["OU_Dec_Over"] if es_over else r["OU_Dec_Under"]
        am_sel = r["OU_Am_Over"] if es_over else r["OU_Am_Under"]
        mejor_total = {
            "Partido": f"{r['Abrev_Vis']} @ {r['Abrev_Loc']}",
            "Pick": f"{'OVER' if es_over else 'UNDER'} {linea_comp:.1f}",
            "Proyectado": r["Total_Proyectado"],
            "Edge_Pts": round(edge_abs, 1),
            "Prob": prob_sel,
            "Fair_Dec": dec_sel,
            "Fair_Am": am_sel,
        }

todos_los_props = []
for r in resultados_semana:
    for p_item in r["Props_Loc"] + r["Props_Vis"]:
        p_copy = dict(p_item)
        p_copy["Matchup"] = f"{r['Abrev_Vis']} @ {r['Abrev_Loc']}"
        todos_los_props.append(p_copy)
anotador_estrella = max(todos_los_props, key=lambda x: x["Prob_Raw"])

mejor_underdog = None
mejor_dog_prob = -1.0
for r in resultados_semana:
    if r["Spread_Mercado_Ref"] < 0:
        dog_team = r["Visita"]
        dog_line = abs(r["Spread_Mercado_Ref"])
        dog_cover_prob = r["Prob_Cover_Vis"]
        dog_fair_spread = -r["Spread_Justo_Loc"]
        dog_dec = r["SP_Dec_Vis"]
        dog_am = r["SP_Am_Vis"]
        match_str = f"{r['Abrev_Vis']} @ {r['Abrev_Loc']}"
    else:
        dog_team = r["Local"]
        dog_line = abs(r["Spread_Mercado_Ref"])
        dog_cover_prob = r["Prob_Cover_Loc"]
        dog_fair_spread = r["Spread_Justo_Loc"]
        dog_dec = r["SP_Dec_Loc"]
        dog_am = r["SP_Am_Loc"]
        match_str = f"{r['Abrev_Vis']} @ {r['Abrev_Loc']}"

    if dog_cover_prob > mejor_dog_prob:
        mejor_dog_prob = dog_cover_prob
        mejor_underdog = {
            "Equipo": dog_team,
            "Matchup": match_str,
            "Linea_Dog": f"+{dog_line:.1f}",
            "Spread_Modelo": f"{dog_fair_spread:+.1f}",
            "Prob_Cover": dog_cover_prob,
            "Fair_Dec": dog_dec,
            "Fair_Am": dog_am,
        }

st.markdown('<div class="radar-section-title">📡 RADAR EJECUTIVO DE LA SEMANA // TOP SYNDICATE EDGES</div>', unsafe_allow_html=True)

r_col1, r_col2, r_col3, r_col4 = st.columns(4)

with r_col1:
    st.markdown(
        f"""
        <div class="radar-card lock">
            <div class="radar-tag">🔒 EL LOCK DE LA SEMANA</div>
            <div class="radar-pick">{mejor_lock['Equipo']}</div>
            <div class="radar-metrics">Win Prob: {mejor_lock['Prob_ML']}% | Fair: {mejor_lock['Fair_Dec']} ({mejor_lock['Fair_Am']})</div>
            <div class="radar-sub">Spread Modelo: {mejor_lock['Spread_Proj']} vs {mejor_lock['Rival']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with r_col2:
    st.markdown(
        f"""
        <div class="radar-card total">
            <div class="radar-tag">⚡ LA FIJA DE PUNTOS</div>
            <div class="radar-pick">{mejor_total['Partido']}: {mejor_total['Pick']}</div>
            <div class="radar-metrics">Proy: {mejor_total['Proyectado']} pts (Edge +{mejor_total['Edge_Pts']} pts)</div>
            <div class="radar-sub">Prob: {mejor_total['Prob']}% | Fair: {mejor_total['Fair_Dec']} ({mejor_total['Fair_Am']})</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with r_col3:
    st.markdown(
        f"""
        <div class="radar-card star">
            <div class="radar-tag">🎯 EL ANOTADOR ESTRELLA</div>
            <div class="radar-pick">{anotador_estrella['Jugador']} ({anotador_estrella['Abrev']} - {anotador_estrella['Rol']})</div>
            <div class="radar-metrics">Anytime TD: {anotador_estrella['Prob']}% | xTD: {anotador_estrella['xTD']}</div>
            <div class="radar-sub">Momio Justo: {anotador_estrella['Fair_Dec']} ({anotador_estrella['Fair_Am']}) • {anotador_estrella['Matchup']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with r_col4:
    st.markdown(
        f"""
        <div class="radar-card dog">
            <div class="radar-tag">🛡️ EL PERRO CON VALOR</div>
            <div class="radar-pick">{mejor_underdog['Equipo']} ({mejor_underdog['Linea_Dog']})</div>
            <div class="radar-metrics">Cobertura: {mejor_underdog['Prob_Cover']}% | Fair: {mejor_underdog['Fair_Dec']} ({mejor_underdog['Fair_Am']})</div>
            <div class="radar-sub">Línea Justa Modelo: {mejor_underdog['Spread_Modelo']} • {mejor_underdog['Matchup']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ==============================================================================
# 10. DESGLOSE POR JUEGO (SCOREBOARD TV HEADER + 3 FILAS + EXPANDER GRÁFICO)
# ==============================================================================
st.markdown('<div class="radar-section-title">📊 ESCÁNER CUANTITATIVO POR PARTIDO (GAME WEEK BOARD)</div>', unsafe_allow_html=True)

for idx_game, res in enumerate(resultados_semana, start=1):
    st.markdown(
        f"""
        <div class="tv-scoreboard">
            <div class="tv-top-bar">
                <span>JUEGO #{idx_game:02d} // {res['Entorno_Tag']}</span>
                <span>RITMO COMBINADO: {res['Pace_Suma']}s ({res['Plays_Totales']} SNAPS) // HFA LOCAL: +{res['HFA_Pts']} PTS</span>
                <span>CLUSTER KEY NUMBER: {res['Marcador_Exacto']}</span>
            </div>
            <div class="tv-main-grid">
                <div class="team-side">
                    <div class="team-badge">{res['Abrev_Vis']}</div>
                    <div>
                        <div class="team-name-tv">{res['Visita']} (VISITA)</div>
                        <div class="team-epa-sub">EPA/Play Proy: {res['EPA_Play_Vis']:+.3f} | RZ Eff: {res['RZ_Eff_Vis']}%</div>
                    </div>
                </div>
                <div class="score-center-box">
                    <div class="projected-score-tv">{res['Pts_Vis']:.1f}  —  {res['Pts_Loc']:.1f}</div>
                    <div class="projected-total-pill">MARCADOR EXACTO: {res['Marcador_Vis']} - {res['Marcador_Loc']}  |  TOTAL PROY: {res['Total_Proyectado']} PTS</div>
                </div>
                <div class="team-side right">
                    <div>
                        <div class="team-name-tv">{res['Local']} (LOCAL)</div>
                        <div class="team-epa-sub">EPA/Play Proy: {res['EPA_Play_Loc']:+.3f} | RZ Eff: {res['RZ_Eff_Loc']}%</div>
                    </div>
                    <div class="team-badge home">{res['Abrev_Loc']}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    f1_col1, f1_col2 = st.columns(2)
    with f1_col1:
        spread_vis_justo = -res["Spread_Justo_Loc"]
        spread_vis_ref = -res["Spread_Mercado_Ref"]
        st.markdown(
            f"""
            <div class="quant-card">
                <div class="quant-card-header">📏 FILA 1A // PROYECCIÓN DE SPREAD (HÁNDICAP NFL & KEY NUMBERS)</div>
                <div class="metric-row">
                    <span class="metric-label">Spread Justo Modelo ({res['Abrev_Loc']} Local)</span>
                    <span class="metric-val">{res['Spread_Justo_Loc']:+.1f} pts (Visita {spread_vis_justo:+.1f})</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">{res['Local']} cubre ({res['Spread_Mercado_Ref']:+.1f})</span>
                    <span>
                        <span class="metric-val">{res['Prob_Cover_Loc']}%</span>
                        <span class="odds-chip green">Fair: {res['SP_Dec_Loc']} ({res['SP_Am_Loc']})</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">{res['Visita']} cubre ({spread_vis_ref:+.1f})</span>
                    <span>
                        <span class="metric-val">{res['Prob_Cover_Vis']}%</span>
                        <span class="odds-chip">Fair: {res['SP_Dec_Vis']} ({res['SP_Am_Vis']})</span>
                    </span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with f1_col2:
        top_clusters_str = " | ".join([f"{m['Marcador']} ({m['Prob']}%)" for m in res["Top_3_Marcadores"]])
        st.markdown(
            f"""
            <div class="quant-card">
                <div class="quant-card-header">🏆 FILA 1B // MONEYLINE (VICTORIA DIRECTA) & CLUSTERS</div>
                <div class="metric-row">
                    <span class="metric-label">Moneyline Local ({res['Local']})</span>
                    <span>
                        <span class="metric-val">{res['Prob_Win_Loc']}%</span>
                        <span class="odds-chip green">Fair: {res['ML_Dec_Loc']} ({res['ML_Am_Loc']})</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Moneyline Visita ({res['Visita']})</span>
                    <span>
                        <span class="metric-val">{res['Prob_Win_Vis']}%</span>
                        <span class="odds-chip">Fair: {res['ML_Dec_Vis']} ({res['ML_Am_Vis']})</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Top 3 Marcadores Exactos (Key Numbers)</span>
                    <span class="odds-chip amber">{top_clusters_str}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    f2_col1, f2_col2 = st.columns(2)
    with f2_col1:
        edge_ou = round(res["Total_Proyectado"] - res["Linea_Total_Mercado"], 1)
        recomendacion_ou = f"OVER {res['Linea_Total_Mercado']}" if edge_ou >= 0 else f"UNDER {res['Linea_Total_Mercado']}"
        st.markdown(
            f"""
            <div class="quant-card">
                <div class="quant-card-header">⚡ FILA 2A // OVER / UNDER TOTAL PROYECTADO DEL JUEGO</div>
                <div class="metric-row">
                    <span class="metric-label">Total Proyectado vs Línea Ref ({res['Linea_Total_Mercado']})</span>
                    <span class="metric-val">{res['Total_Proyectado']} pts (Edge: {edge_ou:+.1f} pts → {recomendacion_ou})</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">OVER {res['Linea_Total_Mercado']} Puntos</span>
                    <span>
                        <span class="metric-val">{res['Prob_Over']}%</span>
                        <span class="odds-chip green">Fair: {res['OU_Dec_Over']} ({res['OU_Am_Over']})</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">UNDER {res['Linea_Total_Mercado']} Puntos</span>
                    <span>
                        <span class="metric-val">{res['Prob_Under']}%</span>
                        <span class="odds-chip">Fair: {res['OU_Dec_Under']} ({res['OU_Am_Under']})</span>
                    </span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with f2_col2:
        tt_ref_loc = round(res["Pts_Loc"] * 2.0) / 2.0 - 0.5 if res["Pts_Loc"] % 1 == 0 else round(res["Pts_Loc"] - 0.5) + 0.5
        tt_ref_vis = round(res["Pts_Vis"] * 2.0) / 2.0 - 0.5 if res["Pts_Vis"] % 1 == 0 else round(res["Pts_Vis"] - 0.5) + 0.5
        st.markdown(
            f"""
            <div class="quant-card">
                <div class="quant-card-header">🎯 FILA 2B // IMPLIED TEAM TOTALS (PUNTOS POR EQUIPO)</div>
                <div class="metric-row">
                    <span class="metric-label">Team Total Local ({res['Local']})</span>
                    <span>
                        <span class="metric-val">{res['Pts_Loc']:.1f} pts</span>
                        <span class="odds-chip green">Línea Justa O/U: {tt_ref_loc:.1f}</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Team Total Visita ({res['Visita']})</span>
                    <span>
                        <span class="metric-val">{res['Pts_Vis']:.1f} pts</span>
                        <span class="odds-chip">Línea Justa O/U: {tt_ref_vis:.1f}</span>
                    </span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Diferencial de Ritmo y Volumen</span>
                    <span class="metric-val">{res['Plays_Por_Equipo']} snaps/equipo ({res['Plays_Totales']} jugadas totales)</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    props_loc_html = "".join(
        [
            f"""
            <div class="td-prop-box">
                <div class="td-role">{p['Abrev']} • {p['Rol']}</div>
                <div class="td-player">{p['Jugador']}</div>
                <div class="td-prob">{p['Prob']}% (xTD {p['xTD']})</div>
                <div class="td-odds">Fair: {p['Fair_Dec']} ({p['Fair_Am']})</div>
            </div>
            """
            for p in res["Props_Loc"]
        ]
    )

    props_vis_html = "".join(
        [
            f"""
            <div class="td-prop-box">
                <div class="td-role">{p['Abrev']} • {p['Rol']}</div>
                <div class="td-player">{p['Jugador']}</div>
                <div class="td-prob">{p['Prob']}% (xTD {p['xTD']})</div>
                <div class="td-odds">Fair: {p['Fair_Dec']} ({p['Fair_Am']})</div>
            </div>
            """
            for p in res["Props_Vis"]
        ]
    )

    st.markdown(
        f"""
        <div class="quant-card">
            <div class="quant-card-header">🏈 FILA 3 // PROYECCIÓN DE TOUCHDOWNS (POISSON O/U 2.5 TDs) & PLAYER PROPS (ANYTIME TD)</div>
            <div class="metric-row">
                <span class="metric-label"><b>{res['Local']} (Local)</b> — xTD Total: <b>{res['xTD_Loc']}</b> (Pase: {res['xTD_Pass_Loc']} | Carrera: {res['xTD_Rush_Loc']})</span>
                <span>
                    <span class="odds-chip green">Over 2.5 TDs: {res['Prob_O25_TD_Loc']}% | {res['O25_TD_Loc_Dec']} ({res['O25_TD_Loc_Am']})</span>
                    <span class="odds-chip">Under 2.5 TDs: {res['Prob_U25_TD_Loc']}% | {res['U25_TD_Loc_Dec']} ({res['U25_TD_Loc_Am']})</span>
                </span>
            </div>
            <div class="td-prop-grid">{props_loc_html}</div>
            <div style="height: 10px;"></div>
            <div class="metric-row">
                <span class="metric-label"><b>{res['Visita']} (Visita)</b> — xTD Total: <b>{res['xTD_Vis']}</b> (Pase: {res['xTD_Pass_Vis']} | Carrera: {res['xTD_Rush_Vis']})</span>
                <span>
                    <span class="odds-chip green">Over 2.5 TDs: {res['Prob_O25_TD_Vis']}% | {res['O25_TD_Vis_Dec']} ({res['O25_TD_Vis_Am']})</span>
                    <span class="odds-chip">Under 2.5 TDs: {res['Prob_U25_TD_Vis']}% | {res['U25_TD_Vis_Dec']} ({res['U25_TD_Vis_Am']})</span>
                </span>
            </div>
            <div class="td-prop-grid">{props_vis_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander(f"📈 ANÁLISIS GRÁFICO DE TRINCHERAS Y DISTRIBUCIÓN DE PROBABILIDAD: {res['Abrev_Vis']} @ {res['Abrev_Loc']}"):
        g_col1, g_col2 = st.columns(2)

        with g_col1:
            if PLOTLY_AVAILABLE:
                fig_prob = go.Figure()
                categorias_prob = [
                    f"Win Prob ({res['Abrev_Loc']} vs {res['Abrev_Vis']})",
                    f"Cover Spread ({res['Spread_Mercado_Ref']:+.1f})",
                    f"Total O/U ({res['Linea_Total_Mercado']})",
                ]
                valores_loc_over = [res["Prob_Win_Loc"], res["Prob_Cover_Loc"], res["Prob_Over"]]
                valores_vis_under = [res["Prob_Win_Vis"], res["Prob_Cover_Vis"], res["Prob_Under"]]

                fig_prob.add_trace(
                    go.Bar(
                        y=categorias_prob,
                        x=valores_loc_over,
                        name=f"{res['Abrev_Loc']} / OVER",
                        orientation="h",
                        marker_color="#00E676",
                        text=[f"{v:.1f}%" for v in valores_loc_over],
                        textposition="inside",
                    )
                )
                fig_prob.add_trace(
                    go.Bar(
                        y=categorias_prob,
                        x=valores_vis_under,
                        name=f"{res['Abrev_Vis']} / UNDER",
                        orientation="h",
                        marker_color="#00F0FF",
                        text=[f"{v:.1f}%" for v in valores_vis_under],
                        textposition="inside",
                    )
                )
                fig_prob.update_layout(
                    title="Distribución de Probabilidad de Victoria, Hándicap y Total",
                    barmode="stack",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(12,19,34,0.8)",
                    font=dict(family="JetBrains Mono, monospace", color="#ECF2F8", size=11),
                    height=280,
                    margin=dict(l=10, r=10, t=40, b=10),
                    xaxis=dict(range=[0, 100], title="Probabilidad (%)"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig_prob, use_container_width=True, key=f"chart_prob_{idx_game}")
            else:
                df_prob_chart = pd.DataFrame(
                    {
                        f"{res['Abrev_Loc']} / OVER (%)": [res["Prob_Win_Loc"], res["Prob_Cover_Loc"], res["Prob_Over"]],
                        f"{res['Abrev_Vis']} / UNDER (%)": [res["Prob_Win_Vis"], res["Prob_Cover_Vis"], res["Prob_Under"]],
                    },
                    index=["Moneyline Win", "Spread Cover", "Over/Under Total"],
                )
                st.bar_chart(df_prob_chart)

        with g_col2:
            if PLOTLY_AVAILABLE:
                metricas_trench = ["Pass EPA Neto (x100)", "Rush EPA Neto (x100)", "Presión Def (%)", "Zona Roja TD (%)"]
                vals_trench_loc = [
                    res["Net_Pass_EPA_Loc"] * 100.0,
                    res["Net_Rush_EPA_Loc"] * 100.0,
                    res["Press_Loc"],
                    res["RZ_Eff_Loc"],
                ]
                vals_trench_vis = [
                    res["Net_Pass_EPA_Vis"] * 100.0,
                    res["Net_Rush_EPA_Vis"] * 100.0,
                    res["Press_Vis"],
                    res["RZ_Eff_Vis"],
                ]

                fig_trench = go.Figure()
                fig_trench.add_trace(
                    go.Bar(
                        x=metricas_trench,
                        y=vals_trench_loc,
                        name=f"{res['Abrev_Loc']} (Local)",
                        marker_color="#00E676",
                        text=[f"{v:.1f}" for v in vals_trench_loc],
                        textposition="auto",
                    )
                )
                fig_trench.add_trace(
                    go.Bar(
                        x=metricas_trench,
                        y=vals_trench_vis,
                        name=f"{res['Abrev_Vis']} (Visita)",
                        marker_color="#FFB300",
                        text=[f"{v:.1f}" for v in vals_trench_vis],
                        textposition="auto",
                    )
                )
                fig_trench.update_layout(
                    title="Duelo de Trincheras: EPA Ajustado (x100), Pressure % y Zona Roja",
                    barmode="group",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(12,19,34,0.8)",
                    font=dict(family="JetBrains Mono, monospace", color="#ECF2F8", size=11),
                    height=280,
                    margin=dict(l=10, r=10, t=40, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig_trench, use_container_width=True, key=f"chart_trench_{idx_game}")
            else:
                df_trench_chart = pd.DataFrame(
                    {
                        f"{res['Abrev_Loc']} (Local)": [
                            res["Net_Pass_EPA_Loc"] * 100.0,
                            res["Net_Rush_EPA_Loc"] * 100.0,
                            res["Press_Loc"],
                            res["RZ_Eff_Loc"],
                        ],
                        f"{res['Abrev_Vis']} (Visita)": [
                            res["Net_Pass_EPA_Vis"] * 100.0,
                            res["Net_Rush_EPA_Vis"] * 100.0,
                            res["Press_Vis"],
                            res["RZ_Eff_Vis"],
                        ],
                    },
                    index=["Pass EPA (x100)", "Rush EPA (x100)", "Pressure %", "RedZone Eff %"],
                )
                st.bar_chart(df_trench_chart)

        kn_cols = st.columns(6)
        for kn_idx, (kn_label, kn_val) in enumerate(res["Key_Margins_Dist"].items()):
            with kn_cols[kn_idx]:
                st.metric(label=f"🔑 {kn_label}", value=f"{kn_val}%")