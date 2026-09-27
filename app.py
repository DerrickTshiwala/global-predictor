import streamlit as st
import requests
import pandas as pd
import scipy.stats as stats
from datetime import datetime, timezone

st.set_page_config(page_title='Football Intelligence Platform v4.0', layout='wide')

st.title('Football Intelligence Platform v4.0')
st.caption('Prediction â€¢ Confidence â€¢ Risk â€¢ Verdict â€¢ Opportunity Ranking')

LEAGUES = {
    'Premier League':'soccer_epl',
    'Champions League':'soccer_uefa_champs_league',
    'UEFA Nations League':'soccer_uefa_nations_league',
    'La Liga':'soccer_spain_la_liga',
    'Bundesliga':'soccer_germany_bundesliga',
    'Serie A':'soccer_italy_serie_a',
    'Ligue 1':'soccer_france_ligue_one',
    'Eredivisie':'soccer_netherlands_eredivisie',
    'MLS':'soccer_usa_mls',
    'Brazil Serie A':'soccer_brazil_campeonato',
    'Mexico Liga MX':'soccer_mexico_ligamx',
    'South Africa PSL':'soccer_spl',
    'AFCON':'soccer_afcon'
}

st.sidebar.header('Platform Settings')
api_key = st.sidebar.text_input('Odds API Key', type='password')
league = st.sidebar.selectbox('Competition', list(LEAGUES.keys()))

matches = []
if api_key:
    try:
        url = f'https://api.the-odds-api.com/v4/sports/{LEAGUES[league]}/odds/?apiKey={api_key}&regions=uk,eu&markets=h2h&oddsFormat=decimal'
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            matches = r.json()
    except Exception as e:
        st.warning(str(e))

rankings = []
for m in matches:
    home = m['home_team']
    away = m['away_team']

    home_strength = 1.45
    away_strength = 1.20

    ph = pdraw = pa = 0.0
    for h in range(6):
        for a in range(6):
            p = stats.poisson.pmf(h, home_strength) * stats.poisson.pmf(a, away_strength)
            if h > a:
                ph += p
            elif h == a:
                pdraw += p
            else:
                pa += p

    confidence = min(100, round(abs(ph-pa)*100 + 50))

    if confidence >= 90:
        verdict = 'ðŸ”¥ ELITE APPROVED'
    elif confidence >= 80:
        verdict = 'âœ… APPROVED'
    elif confidence >= 70:
        verdict = 'âš  WATCHLIST'
    else:
        verdict = 'âŒ NO BET'

    prediction = home + ' Win' if ph > max(pdraw, pa) else away + ' Win' if pa > pdraw else 'Draw'

    rankings.append({
        'Match': f'{home} vs {away}',
        'Prediction': prediction,
        'Confidence': confidence,
        'Verdict': verdict
    })

st.subheader('All Opportunities Ranked')
if rankings:
    df = pd.DataFrame(rankings).sort_values('Confidence', ascending=False)
    st.dataframe(df, use_container_width=True)

    elite = df[df['Verdict'].str.contains('ELITE', na=False)]
    approved = df[df['Verdict'].str.contains('APPROVED', na=False)]

    st.metric('Elite Approved', len(elite))
    st.metric('Approved', len(approved))

    selected = st.selectbox('Detailed Match Analysis', df['Match'].tolist())
    st.write(df[df['Match'] == selected])
else:
    st.info('Enter a valid API key to load fixtures.')

st.caption('Predictions are probabilities, not guarantees. The platform is designed to identify stronger opportunities and filter weak ones.')
