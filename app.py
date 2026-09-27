import streamlit as st
import requests
import pandas as pd
import scipy.stats as stats
from datetime import datetime, timezone

st.set_page_config(page_title="Football Analytics Pro 3.1", layout="wide")

st.title("Football Analytics Pro 3.1")

TEAM_RATINGS = {
    "Liverpool": 2.10,
    "Arsenal": 2.00,
    "Manchester City": 2.30,
    "Real Madrid": 2.20,
    "Bayern Munich": 2.15,
    "Barcelona": 2.00,
    "PSG": 2.00,
    "England": 2.05,
    "France": 2.00,
    "Brazil": 2.10,
    "Argentina": 2.10,
    "Netherlands": 1.95
}

LEAGUES = {
    "Premier League": "soccer_epl",
    "Champions League": "soccer_uefa_champs_league",
    "UEFA Nations League": "soccer_uefa_nations_league",
    "La Liga": "soccer_spain_la_liga",
    "South Africa PSL": "soccer_spl"
}

st.sidebar.header("Settings")
api_key = st.sidebar.text_input("Odds API Key", type="password")
bankroll = st.sidebar.number_input("Bankroll", min_value=10.0, value=1000.0)
league = st.selectbox("Competition", list(LEAGUES.keys()))

matches = []
if api_key:
    try:
        url = f"https://api.the-odds-api.com/v4/sports/{LEAGUES[league]}/odds/?apiKey={api_key}&regions=uk,eu&markets=h2h&oddsFormat=decimal"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            matches = response.json()
    except Exception as e:
        st.warning(str(e))

st.header("Top Picks Scanner")
rankings = []

for match in matches:
    home = match['home_team']
    away = match['away_team']

    home_rating = TEAM_RATINGS.get(home, 1.45)
    away_rating = TEAM_RATINGS.get(away, 1.20)

    prob_home = 0.0
    prob_draw = 0.0
    prob_away = 0.0

    for h in range(6):
        for a in range(6):
            p = stats.poisson.pmf(h, home_rating) * stats.poisson.pmf(a, away_rating)
            if h > a:
                prob_home += p
            elif h == a:
                prob_draw += p
            else:
                prob_away += p

    confidence = min(100, round(abs(prob_home - prob_away) * 100 + 50))

    if prob_home > max(prob_draw, prob_away):
        pick = f"{home} Win"
    elif prob_away > prob_draw:
        pick = f"{away} Win"
    else:
        pick = "Draw"

    rankings.append({
        'Match': f'{home} vs {away}',
        'Pick': pick,
        'Confidence': confidence,
        'Risk': 'LOW' if confidence >= 85 else 'MEDIUM' if confidence >= 70 else 'HIGH',
        'Verdict': 'APPROVED' if confidence >= 75 else 'NO BET'
    })

if rankings:
    rankings_df = pd.DataFrame(rankings)
    if not rankings_df.empty:
        st.dataframe(rankings_df.sort_values('Confidence', ascending=False), use_container_width=True)

if matches:
    options = {f"{m['home_team']} vs {m['away_team']}": m for m in matches}
    selected = st.selectbox('Match Analysis', list(options.keys()))
    match = options[selected]

    home = match['home_team']
    away = match['away_team']

    if match.get('commence_time'):
        kickoff = datetime.fromisoformat(match['commence_time'].replace('Z', '+00:00'))
        st.info(f"Kick Off: {kickoff.strftime('%d %b %Y %H:%M UTC')}")
        st.info(f"Countdown: {kickoff - datetime.now(timezone.utc)}")

    home_rating = TEAM_RATINGS.get(home, 1.45)
    away_rating = TEAM_RATINGS.get(away, 1.20)

    prob_home = 0.0
    prob_draw = 0.0
    prob_away = 0.0
    scores = []

    for h in range(7):
        for a in range(7):
            p = stats.poisson.pmf(h, home_rating) * stats.poisson.pmf(a, away_rating)
            scores.append((f'{h}-{a}', p))
            if h > a:
                prob_home += p
            elif h == a:
                prob_draw += p
            else:
                prob_away += p

    scores.sort(key=lambda x: x[1], reverse=True)

    c1, c2, c3 = st.columns(3)
    c1.metric('Home', f'{prob_home*100:.1f}%')
    c2.metric('Draw', f'{prob_draw*100:.1f}%')
    c3.metric('Away', f'{prob_away*100:.1f}%')

    confidence = min(100, round(abs(prob_home - prob_away) * 100 + 50))
    st.subheader('Bet Verdict')
    st.success('APPROVED âœ…' if confidence >= 75 else 'NO BET âŒ')
    st.metric('Confidence', confidence)

    st.subheader('Most Likely Scores')
    for score, probability in scores[:5]:
        st.write(f'{score}: {probability*100:.2f}%')

st.caption('Probabilities are estimates, not guarantees.')
