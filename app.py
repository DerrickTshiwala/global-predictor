# FIX THESE LINES IN YOUR CURRENT APP.PY

# --------------------------------------------------
# REPLACE BROKEN URL BLOCK
# --------------------------------------------------

url = (
    f"https://api.the-odds-api.com/v4/sports/"
    f"{selected_sport_key}/odds/"
    f"?apiKey={API_KEY}"
    f"&regions=uk,eu,us,au"
    f"&markets=h2h"
    f"&oddsFormat=decimal"
)

# --------------------------------------------------
# REPLACE ALL HTML ENTITIES
# --------------------------------------------------

# Change every:
# &gt;
# to:
# >

# Examples:

if h > a:
    prob_home += joint_prob
elif h == a:
    prob_draw += joint_prob
else:
    prob_away += joint_prob

if h > 0 and a > 0:
    prob_btts += joint_prob

if h + a > 2:
    prob_over25 += joint_prob

fair_home_odds = (
    1 / prob_home
    if prob_home > 0
    else 999.0
)

is_worth_it = bookie_odds > fair_home_odds

raw_kelly = (
    ((prob_home * bookie_odds) - 1) / b
    if b > 0
    else 0
)

# --------------------------------------------------
# IMPORTS
# --------------------------------------------------

import streamlit as st
import scipy.stats as stats
import pandas as pd
import numpy as np
import requests
import os

from datetime import (
    datetime,
    timezone
)

# --------------------------------------------------
# STREAMLIT SECRETS PASSWORD
# --------------------------------------------------

PREMIUM_PASSWORD = st.secrets.get(
    "PREMIUM_PASSWORD",
    ""
)

if user_tier_input == "Premium Member":

    secret_password = st.sidebar.text_input(
        "Enter Premium Member Password",
        type="password"
    )

    if secret_password == PREMIUM_PASSWORD:
        user_tier = "Premium Member (Unlocked)"
        st.sidebar.success(
            "Premium Features Unlocked!"
        )

    elif secret_password:
        st.sidebar.error(
            "Invalid Password"
        )

# --------------------------------------------------
# TEAM RATINGS
# --------------------------------------------------

TEAM_RATINGS = {
    "Argentina": 2.10,
    "Brazil": 2.10,
    "England": 2.05,
    "France": 2.00,
    "Spain": 1.95,
    "Germany": 1.90,
    "Portugal": 1.90,
    "Netherlands": 1.95,
    "Belgium": 1.85,
    "Croatia": 1.75,
    "Serbia": 1.35,
    "South Africa": 1.10,
    "Manchester City": 2.30,
    "Arsenal": 2.00,
    "Liverpool": 2.05,
    "Bayern Munich": 2.15,
    "Real Madrid": 2.20
}

home_rating = TEAM_RATINGS.get(
    home_team,
    1.45
)

away_rating = TEAM_RATINGS.get(
    away_team,
    1.20
)

base_home_xg = (
    home_rating
    * (0.85 if is_derby else 1.0)
    * (0.90 if home_fatigue else 1.0)
)

base_away_xg = (
    away_rating
    * (1.15 if is_derby else 1.0)
    * (0.90 if away_fatigue else 1.0)
)

# --------------------------------------------------
# FIXTURE INFORMATION
# --------------------------------------------------

if live_matches:

    commence_time = target_match.get(
        "commence_time"
    )

    if commence_time:

        kickoff = datetime.fromisoformat(
            commence_time.replace(
                "Z",
                "+00:00"
            )
        )

        now = datetime.now(
            timezone.utc
        )

        remaining = kickoff - now

        st.subheader(
            "Fixture Information"
        )

        st.write(
            f"Competition: {selected_league_name}"
        )

        st.write(
            f"Kick-off: "
            f"{kickoff.strftime('%d %b %Y %H:%M UTC')}"
        )

        st.info(
            f"Kick-off In: {remaining}"
        )

# --------------------------------------------------
# FAIR ODDS ALL OUTCOMES
# --------------------------------------------------

fair_draw_odds = (
    1 / prob_draw
    if prob_draw > 0
    else 999
)

fair_away_odds = (
    1 / prob_away
    if prob_away > 0
    else 999
)

# --------------------------------------------------
# FULL PROBABILITY MATRIX
# --------------------------------------------------

st.subheader(
    "1X2 Probability Matrix"
)

p1, p2, p3 = st.columns(3)

p1.metric(
    "Home",
    f"{prob_home * 100:.1f}%"
)

p2.metric(
    "Draw",
    f"{prob_draw * 100:.1f}%"
)

p3.metric(
    "Away",
    f"{prob_away * 100:.1f}%"
)

# --------------------------------------------------
# CORRECT SCORE MATRIX
# --------------------------------------------------

score_probs = []

for h in range(6):
    for a in range(6):

        p = (
            stats.poisson.pmf(
                h,
                base_home_xg
            )
            *
            stats.poisson.pmf(
                a,
                base_away_xg
            )
        )

        score_probs.append(
            (
                f"{h}-{a}",
                p
            )
        )

score_probs.sort(
    key=lambda x: x[1],
    reverse=True
)

predicted_score = score_probs[0][0]

st.subheader(
    "Predicted Scoreline"
)

st.success(
    predicted_score
)

# --------------------------------------------------
# CONFIDENCE SCORE
# --------------------------------------------------

confidence = min(
    100,
    round(
        abs(
            prob_home - prob_away
        )
        * 100
        + 50
    )
)

st.metric(
    "Confidence Score",
    f"{confidence}/100"
)

# --------------------------------------------------
# RECOMMENDED SELECTION
# --------------------------------------------------

if prob_home > prob_draw and prob_home > prob_away:

    recommendation = (
        f"{home_team} Win"
    )

elif prob_away > prob_home:

    recommendation = (
        f"{away_team} Win"
    )

else:

    recommendation = "Draw"

st.subheader(
    "Recommended Selection"
)

st.success(
    recommendation
)

# --------------------------------------------------
# TOP CORRECT SCORES
# --------------------------------------------------

st.subheader(
    "Most Likely Scores"
)

for score, probability in score_probs[:5\]:
    st.write(
        f"{score}: "
        f"{probability * 100:.2f}%"
    )

# --------------------------------------------------
# PREDICTION HISTORY LOG
# --------------------------------------------------

history_file = (
    "prediction_istory.csv"
)

record = pd.DataFrame([
    {
        "Home": home_team,
        "Away": away_team,
        "Prediction": recommendation,
        "Score": predicted_score,
        "Confidence": confidence
    }
])

if os.path.exists(
    history_file
):

    record.to_csv(
        history_file,
        mode="a",
        index=False,
        header=False
    )

else:

    record.to_csv(
        history_file,
        index=False
    )

# --------------------------------------------------
# PREMIUM DASHBOARD
# --------------------------------------------------

if user_tier != "Free Tier":

    st.subheader(
        "Premium Engine Dashboard"
    )

    b = bookie_odds - 1

    raw_kelly = (
        ((prob_home * bookie_odds) - 1)
        / b
        if b > 0
        else 0
    )

    kelly_pct = max(
        0.0,
        raw_kelly * 0.25
    )

    c1, c2 = st.columns(2)

    c1.metric(
        "Kelly %",
        f"{kelly_pct * 100:.2f}%"
    )

    c2.metric(
        "Stake",
        f"{user_bankroll * kelly_pct:.2f}"
    )

    st.write(
        f"BTTS Probability: "
        f"{prob_btts * 100:.1f}%"
    )

    st.write(
        f"Over 2.5 Goals: "
        f"{prob_over25 * 100:.1f}%"
    )

    st.write(
        f"Fair Home Odds: "
        f"{fair_home_odds:.2f}"
    )

    st.write(
        f"Fair Draw Odds: "
        f"{fair_draw_odds:.2f}"
    )

    st.write(
        f"Fair Away Odds: "
        f"{fair_away_odds:.2f}"
    )
