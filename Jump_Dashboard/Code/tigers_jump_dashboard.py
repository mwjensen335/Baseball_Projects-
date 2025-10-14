
import numpy as np
import pandas as pd
from datetime import timedelta
import matplotlib.pyplot as plt
import streamlit as st

from sklearn.metrics import r2_score, mean_absolute_error

# Helpers, there next definitions are just returning and looping through each CSV files to put each pitcher into each category
def standardize_columns(df):
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    return df

def find_col(df, keywords, preferred=None):
    cols = df.columns
    if preferred and preferred.lower() in cols:
        return preferred.lower()
    for c in cols:
        if all(k in c for k in keywords):
            return c
    for c in cols:
        if any(k in c for k in keywords):
            return c
    return None

def coerce_datetime(series):
    return pd.to_datetime(series, errors="coerce", infer_datetime_format=True, utc=False)

def normalize_pitcher(s):
    s = s.astype(str).str.strip().str.upper()
    return s.replace({"PITCHER A":"A", "PITCHER B":"B", "PITCHERA":"A", "PITCHERB":"B", "A":"A","B":"B"})

def nearest_prior(left_times, right_times):
    if len(right_times) == 0:
        return np.full(len(left_times), -1, dtype=int)
    result = np.full(len(left_times), -1, dtype=int)
    j = 0
    for i, t in enumerate(left_times):
        while j + 1 < len(right_times) and right_times[j + 1] <= t:
            j += 1
        if right_times[j] <= t:
            result[i] = j
    return result

def nearest_any(left_times, right_times):
    if len(right_times) == 0:
        return np.full(len(left_times), -1, dtype=int)
    result = np.zeros(len(left_times), dtype=int)
    j = 0
    for i, t in enumerate(left_times):
        while j + 1 < len(right_times) and abs((right_times[j + 1] - t)) <= abs((right_times[j] - t)):
            j += 1
        result[i] = j
    return result

def build_pitch_summary(pitch, date_col_p, velo_col, pitcher_col_p=None):
    pitch = pitch.dropna(subset=[date_col_p, velo_col]).copy()
    pitch["game_date"] = pitch[date_col_p].dt.floor("D")
    if pitcher_col_p is not None:
        pitch["_pitcher_norm"] = normalize_pitcher(pitch[pitcher_col_p])
    elif "_pitcher_norm" not in pitch.columns:
        pitch["_pitcher_norm"] = np.nan
    pitch_agg = (
        pitch.groupby(["game_date", "_pitcher_norm"], dropna=False)[velo_col]
             .agg(game_velo_mean="mean", game_velo_median="median", game_velo_sd="std", n_pitches="count")
             .reset_index()
    )
    return pitch_agg

def build_jump_trials_long(jump, date_col_j, pitcher_col_j=None, name_col="name", value_col_guess=None):
    # Expect a 'name' column with metric names and a 'value' column with numeric values.
    # If value column isn't literally named 'value', try to detect likely alternatives.
    jump = jump.dropna(subset=[date_col_j]).copy()
    jump["session_date"] = jump[date_col_j].dt.floor("D")
    if pitcher_col_j is not None:
        jump["_pitcher_norm"] = normalize_pitcher(jump[pitcher_col_j])
    elif "_pitcher_norm" not in jump.columns:
        jump["_pitcher_norm"] = np.nan

    # Locate the 'name' column and the 'value' column
    name_col = find_col(jump, ["name"]) or name_col
    if value_col_guess is None:
        value_col = find_col(jump, ["value"]) or find_col(jump, ["metric","value"]) or find_col(jump, ["measurement"]) or find_col(jump, ["result"])
    else:
        value_col = value_col_guess
    if name_col not in jump.columns:
        raise ValueError("Jump data must include a 'name' column with metric names.")
    if value_col not in jump.columns:
        raise ValueError("Jump data must include a numeric 'value' column for metric values.")

    # Keep minimal columns for long-form trials
    long_cols = ["session_date", "_pitcher_norm", name_col, value_col]
    keep = [c for c in long_cols if c in jump.columns]
    jumps_long = jump[keep].copy()
    jumps_long.rename(columns={name_col: "metric_name", value_col: "metric_value"}, inplace=True)

    # Ensure numeric
    jumps_long["metric_value"] = pd.to_numeric(jumps_long["metric_value"], errors="coerce")
    # Drop rows missing metric_value
    jumps_long = jumps_long.dropna(subset=["metric_value"])

    return jumps_long

def align_games_to_jump_sessions(pitch_agg, jumps_long, window_days=30, strategy="prior"):
    # Use unique session dates per pitcher from jumps_long, then join ALL trials from matched session.
    window = timedelta(days=window_days)
    sessions = (jumps_long[["_pitcher_norm","session_date"]]
                .dropna()
                .drop_duplicates()
                .sort_values(["_pitcher_norm","session_date"])
                .reset_index(drop=True))

    merged_list = []
    for p_label, g in pitch_agg.groupby("_pitcher_norm", dropna=False):
        g = g.sort_values("game_date").reset_index(drop=True)
        s = sessions[sessions["_pitcher_norm"] == p_label].reset_index(drop=True)

        if len(s) == 0:
            g2 = g.copy()
            g2["matched_session_date"] = pd.NaT
            merged_list.append(g2)
            continue

        left_times = g["game_date"].to_numpy()
        right_times = s["session_date"].to_numpy()

        if strategy == "prior":
            idx = nearest_prior(left_times, right_times)
            matched_dates = []
            for i, j_idx in enumerate(idx):
                if j_idx == -1:
                    matched_dates.append(pd.NaT)
                else:
                    if (g.loc[i, "game_date"] - s.loc[j_idx, "session_date"]) <= window:
                        matched_dates.append(s.loc[j_idx, "session_date"])
                    else:
                        matched_dates.append(pd.NaT)
        else:
            idx = nearest_any(left_times, right_times)
            matched_dates = []
            for i, j_idx in enumerate(idx):
                if j_idx == -1:
                    matched_dates.append(pd.NaT)
                else:
                    if abs(g.loc[i, "game_date"] - s.loc[j_idx, "session_date"]) <= window:
                        matched_dates.append(s.loc[j_idx, "session_date"])
                    else:
                        matched_dates.append(pd.NaT)

        g2 = g.copy()
        g2["matched_session_date"] = matched_dates
        merged_list.append(g2)

    matched_games = pd.concat(merged_list, ignore_index=True)

    # Expand to all trials from matched sessions (long form)
    merged_trials = matched_games.merge(
        jumps_long,
        left_on=["_pitcher_norm", "matched_session_date"],
        right_on=["_pitcher_norm", "session_date"],
        how="left",
        suffixes=("", "_jump")
    )
    merged_trials = merged_trials[~merged_trials["matched_session_date"].isna()].copy()
    return matched_games, merged_trials

def cohen_d(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    x = x[np.isfinite(x)]
    y = y[np.isfinite(y)]
    if len(x) < 2 or len(y) < 2:
        return np.nan
    nx, ny = len(x), len(y)
    s2x = np.var(x, ddof=1); s2y = np.var(y, ddof=1)
    sp = np.sqrt(((nx - 1) * s2x + (ny - 1) * s2y) / (nx + ny - 2)) if (nx + ny - 2) > 0 else np.nan
    if sp == 0 or not np.isfinite(sp):
        return np.nan
    return (np.mean(x) - np.mean(y)) / sp

def per_player_trial_insights_long(merged_trials, pitcher, high_quantile=0.75):
    df = merged_trials.copy()
    if pitcher is not None:
        df = df[df["_pitcher_norm"] == pitcher].copy()
    if len(df) < 3:
        return None, None, None

    # Per pitcher high-velo threshold
    thr = df["game_velo_mean"].quantile(high_quantile)
    df["is_high_velo_day"] = df["game_velo_mean"] >= thr

    rows = []
    for mname, sub in df.groupby("metric_name"):
        vals = sub["metric_value"]
        if vals.isna().all():
            continue

        try:
            rho = vals.corr(sub["game_velo_mean"], method="spearman")
        except Exception:
            rho = np.nan

        hv = vals[sub["is_high_velo_day"]]
        lv = vals[~sub["is_high_velo_day"]]
        d = cohen_d(hv, lv)

        hv_mean = np.nanmean(hv)
        hv_sd   = np.nanstd(hv, ddof=1) if np.sum(np.isfinite(hv)) > 1 else np.nan
        hv_p25  = np.nanpercentile(hv, 25) if np.sum(np.isfinite(hv)) > 0 else np.nan
        hv_p75  = np.nanpercentile(hv, 75) if np.sum(np.isfinite(hv)) > 0 else np.nan

        rows.append({
            "metric_name": mname,
            "spearman_rho": rho,
            "effect_size_d (high - other)": d,
            "high_velo_mean": hv_mean,
            "high_velo_sd": hv_sd,
            "high_velo_p25": hv_p25,
            "high_velo_p75": hv_p75,
            "n_trials": int(vals.dropna().shape[0]),
            "n_high_trials": int(hv.dropna().shape[0])
        })

    out = pd.DataFrame(rows).sort_values(["spearman_rho"], ascending=False)
    return out, df, thr


# Streamlit UI, take it into a URL and allow accesibility 

st.set_page_config(page_title="Jump → Pitch Velo Dashboard", layout="wide")
st.title("Jump Performance → Pitch Velocity: Trial-Level (Long-Form 'name'/'value')")

with st.sidebar:
    st.header("1) Upload Data")
    pitch_file = st.file_uploader("Pitch data CSV (.csv)", type=["csv"])
    jump_file  = st.file_uploader("Jump data CSV (.csv)", type=["csv"])

    st.header("2) Pairing Options")
    pair_strategy = st.selectbox("Pair jumps to games using:", ["prior (same or earlier, within window)", "nearest (before/after, within window)"])
    window_days   = st.slider("Match window (days)", min_value=3, max_value=60, value=30, step=1)

if pitch_file and jump_file:
    # Load/standardize
    pitch = pd.read_csv(pitch_file); jump = pd.read_csv(jump_file)
    pitch = standardize_columns(pitch); jump = standardize_columns(jump)

    # Identify key columns
    pitcher_col_p = find_col(pitch, ["pitcher"]) or find_col(pitch, ["player"]) or find_col(pitch, ["name"])
    date_col_p    = find_col(pitch, ["date"]) or find_col(pitch, ["game","date"])
    velo_col      = find_col(pitch, ["release","speed"]) or find_col(pitch, ["velo"]) or find_col(pitch, ["velocity"]) or find_col(pitch, ["speed"])

    pitcher_col_j = find_col(jump, ["pitcher"]) or find_col(jump, ["athlete"]) or find_col(jump, ["player"]) or find_col(jump, ["name"])
    date_col_j    = find_col(jump, ["time"]) or find_col(jump, ["timestamp"]) or find_col(jump, ["date"])

    # Parse fields
    pitch[date_col_p] = coerce_datetime(pitch[date_col_p]).dt.tz_localize(None)
    jump[date_col_j]  = coerce_datetime(jump[date_col_j]).dt.tz_localize(None)
    if velo_col:
        pitch[velo_col] = pd.to_numeric(pitch[velo_col], errors="coerce")

    # Pitch per-game summary
    pitch_agg = build_pitch_summary(pitch, date_col_p, velo_col, pitcher_col_p)

    # Long-form jumps using 'name' and 'value'
    jumps_long = build_jump_trials_long(jump, date_col_j, pitcher_col_j)

    # Pitcher filter
    pitchers = sorted([p for p in pitch_agg["_pitcher_norm"].dropna().unique()])
    pick_pitchers = st.sidebar.multiselect("Filter pitcher(s):", pitchers, default=pitchers)

    if pick_pitchers:
        pitch_view = pitch_agg[pitch_agg["_pitcher_norm"].isin(pick_pitchers)].copy()
        jumps_view = jumps_long[jumps_long["_pitcher_norm"].isin(pick_pitchers)].copy()
    else:
        pitch_view, jumps_view = pitch_agg.copy(), jumps_long.copy()

    # Pairing
    strategy_key = "prior" if pair_strategy.startswith("prior") else "nearest"
    matched_games, merged_trials = align_games_to_jump_sessions(pitch_view, jumps_view, window_days=window_days, strategy=strategy_key)

    st.subheader("Merged trial-level dataset (long-form 'name'/'value' joined to games)")
    st.dataframe(merged_trials.sort_values(["_pitcher_norm","game_date","metric_name"]).reset_index(drop=True))

    # Insights per player (trial-level, by exact metric names)
    st.markdown("### Per-Player Trial-Level Insights (by exact 'name')")
    pitcher_sel = st.selectbox("Choose pitcher", options=[None] + pitchers, format_func=lambda x: "All" if x is None else x)
    q = st.slider("Define 'high velo' as this percentile of that pitcher's game velocity", min_value=0.5, max_value=0.95, value=0.75, step=0.05)

    insights, df_player, thr = per_player_trial_insights_long(merged_trials, pitcher_sel, high_quantile=q)

    if insights is None:
        st.warning("Not enough paired trials for this selection. Try a different pitcher/window.")
    else:
        st.write(f"High-velo threshold: **{thr:.2f}** (game mean velocity)")
        st.dataframe(insights.round(4))

        # Choose an exact metric name to visualize
        metric_names = insights["metric_name"].tolist()
        metric_pick = st.selectbox("Pick a metric name to visualize (from your 'name' column)", metric_names)
        sub = df_player[df_player["metric_name"] == metric_pick].sort_values("game_date").copy()
        if len(sub) > 0:
            fig = plt.figure()
            ax1 = plt.gca()
            ax1.plot(sub["game_date"], sub["metric_value"], marker="o")
            ax1.set_xlabel("Game date")
            ax1.set_ylabel(metric_pick)
            ax1.tick_params(axis='x', rotation=45)

            ax2 = ax1.twinx()
            ax2.plot(sub["game_date"], sub["game_velo_mean"], marker="x")
            ax2.set_ylabel("Game mean velo")

            plt.title(f"{metric_pick} (trial-level) vs. Game Velocity")
            plt.tight_layout()
            st.pyplot(fig)

        # Downloads
        st.download_button("Download merged trials CSV", merged_trials.to_csv(index=False), file_name="merged_trials_jump_to_velo.csv")
        st.download_button("Download per-player trial insights (CSV)", insights.to_csv(index=False), file_name="per_player_trial_insights.csv")
else:
    st.info("Upload pitch and jump CSVs in the sidebar to get started.")
