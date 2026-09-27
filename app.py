import streamlit as st
import requests
import scipy.stats as stats
import pandas as pd
import os
from datetime import datetime, timezone

st.set_page_config(page_title="Universal Football Analytics and Live Value Engine", layout="wide")

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

st.title("Universal Football Analytics and Live Value Engine")

st.sidebar.header("Subscription and Wallet Settings")
plan = st.sidebar.selectbox("Account Plan", ["Free Tier", "Premium Member"])
password = ""
user_tier = "Free Tier"

if plan == "Premium Member":
    password = st.sidebar.text_input("Premium Password", type="password")
    premium_password = st.secrets.get("PREMIUM_PASSWORD", "")
    if password and password == premium_password:
        user_tier = "Premium"
        st.sidebar.success("Premium Unlocked")

bankroll = st.sidebar.number_input("Bankroll", min_value=10.0, value=1000.0)

api_key = st.text_input("Odds API Key", type="password")

leagues = {
    "UEFA Nations League": "soccer_uefa_nations_league",
    "Premier League": "soccer_epl",
    "Champions League": "soccer_uefa_champs_league",
    "La Liga": "soccer_spain_la_liga"
}

league = st.selectbox("Competition", list(leagues.keys()))

live_matches = []
home_team = "Home Team"
away_team = "Away Team"
bookie_odds = 2.0
kickoff = None

if api_key:
    url = (
        f"https://api.the-odds-api.com/v4/sports/{leagues[league]}/odds/"
        f"?apiKey={api_key}&regions=uk,eu&markets=h2h&oddsFormat=decimal"
    )

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            live_matches = response.json()
    except Exception:
        pass

if live_matches:
    options = {
        f"{m['home_team']} vs {m['away_team']}": m
        for m in live_matches
    }

    selected = st.selectbox("Match", list(options.keys()))
    match = options[selected]

    home_team = match["home_team"]
    away_team = match["away_team"]

    commence = match.get("commence_time")
    if commence:
        kickoff = datetime.fromisoformat(commence.replace("Z", "+00:00"))

    odds = []
    for bookmaker in match.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            if market.get("key") == "h2h":
                for outcome in market.get("outcomes", []):
                    if outcome.get("name") == home_team:
                        odds.append(float(outcome.get("price", 0)))

    if odds:
        bookie_odds = max(odds)
else:
    home_team = "Real Madrid"
    away_team = "Bayern Munich"

if kickoff:
    st.info(f"Kick Off: {kickoff.strftime('%d %b %Y %H:%M UTC')}")
    st.info(f"Countdown: {kickoff - datetime.now(timezone.utc)}")

is_derby = st.checkbox("Derby")
home_fatigue = st.checkbox(f"{home_team} Fatigue")
away_fatigue = st.checkbox(f"{away_team} Fatigue")

home_rating = TEAM_RATINGS.get(home_team, 1.45)
away_rating = TEAM_RATINGS.get(away_team, 1.20)

home_xg = home_rating * (0.85 if is_derby else 1.0) * (0.9 if home_fatigue else 1.0)
away_xg = away_rating * (1.15 if is_derby else 1.0) * (0.9 if away_fatigue else 1.0)

prob_home = prob_draw = prob_away = prob_btts = prob_over25 = 0.0
score_probs = []

for h in range(7):
    for a in range(7):
        p = stats.poisson.pmf(h, home_xg) * stats.poisson.pmf(a, away_xg)
        score_probs.append((f"{h}-{a}", p))

        if h > a:
            prob_home += p
        elif h == a:
            prob_draw += p
        else:
            prob_away += p

        if h > 0 and a > 0:
            prob_btts += p

        if h + a > 2:
            prob_over25 += p

score_probs.sort(key=lambda x: x[1], reverse=True)

fair_home = 1 / prob_home if prob_home > 0 else 999
fair_draw = 1 / prob_draw if prob_draw > 0 else 999
fair_away = 1 / prob_away if prob_away > 0 else 999

st.subheader("Probability Matrix")

c1, c2, c3 = st.columns(3)
c1.metric("Home", f"{prob_home*100:.1f}%")
c2.metric("Draw", f"{prob_draw*100:.1f}%")
c3.metric("Away", f"{prob_away*100:.1f}%")

prediction = home_team + " Win"
if prob_away > prob_home and prob_away > prob_draw:
    prediction = away_team + " Win"
elif prob_draw > prob_home and prob_draw > prob_away:
    prediction = "Draw"

confidence = min(100, round(abs(prob_home - prob_away) * 100 + 50))

st.success(f"Recommended Selection: {prediction}")
st.metric("Confidence", f"{confidence}/100")
st.metric("Best Home Odds", f"{bookie_odds:.2f}")
st.metric("Fair Home Odds", f"{fair_home:.2f}")

st.subheader("Most Likely Scores")
for score, p in score_probs[:5]:
    st.write(f"{score} : {p*100:.2f}%")

if user_tier == "Premium":
    b = bookie_odds - 1
    kelly = (((prob_home * bookie_odds) - 1) / b) if b > 0 else 0
    kelly = max(0, kelly * 0.25)

    st.subheader("Premium Dashboard")
    st.write(f"BTTS: {prob_btts*100:.1f}%")
    st.write(f"Over 2.5 Goals: {prob_over25*100:.1f}%")
    st.write(f"Kelly %: {kelly*100:.2f}%")
    st.write(f"Suggested Stake: {bankroll*kelly:.2f}")

history = pd.DataFrame([{
    'Home': home_team,
    'Away': away_team,
    'Prediction': prediction,
    'Confidence': confidence
}])

file_name = 'prediction_history.csv'
if os.path.exists(file_name):
    history.to_csv(file_name, mode='a', header=False, index=False)
else:
    history.to_csv(file_name, index=False)
