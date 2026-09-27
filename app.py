import streamlit as st
import requests
import pandas as pd
import scipy.stats as stats
from datetime import datetime, timezone

st.set_page_config(page_title="Football Analytics Global", layout="wide")

st.title("Football Analytics Global")

LEAGUES = {
    "Premier League":"soccer_epl",
    "Champions League":"soccer_uefa_champs_league",
    "UEFA Nations League":"soccer_uefa_nations_league",
    "La Liga":"soccer_spain_la_liga",
    "Bundesliga":"soccer_germany_bundesliga",
    "Serie A":"soccer_italy_serie_a",
    "Ligue 1":"soccer_france_ligue_one",
    "Eredivisie":"soccer_netherlands_eredivisie",
    "MLS":"soccer_usa_mls",
    "Brazil Serie A":"soccer_brazil_campeonato",
    "Argentina Primera":"soccer_argentina_primer_division",
    "Mexico Liga MX":"soccer_mexico_ligamx",
    "South Africa PSL":"soccer_spl",
    "AFCON":"soccer_afcon",
    "Japan J1":"soccer_japan_j_league",
    "K League":"soccer_korea_kleague1",
    "Saudi Pro League":"soccer_saudi_arabia_pro_league",
    "Australia A-League":"soccer_australia_aleague"
}

TEAM_RATINGS = {}

st.sidebar.header('Settings')
api_key = st.sidebar.text_input('Odds API Key', type='password')
league = st.selectbox('Competition', list(LEAGUES.keys()))
min_conf = st.slider('Minimum Confidence',50,95,75)

matches=[]
if api_key:
    try:
        url=f'https://api.the-odds-api.com/v4/sports/{LEAGUES[league]}/odds/?apiKey={api_key}&regions=uk,eu&markets=h2h&oddsFormat=decimal'
        r=requests.get(url,timeout=15)
        if r.status_code==200:
            matches=r.json()
    except Exception as e:
        st.error(str(e))

rankings=[]
for m in matches:
    home=m['home_team']; away=m['away_team']
    hr=TEAM_RATINGS.get(home,1.45)
    ar=TEAM_RATINGS.get(away,1.20)

    ph=pdraw=pa=0.0
    for h in range(6):
        for a in range(6):
            p=stats.poisson.pmf(h,hr)*stats.poisson.pmf(a,ar)
            if h>a: ph+=p
            elif h==a: pdraw+=p
            else: pa+=p

    confidence=min(100,round(abs(ph-pa)*100+50))
    prediction = home+' Win' if ph>max(pdraw,pa) else away+' Win' if pa>pdraw else 'Draw'
    verdict = 'APPROVED' if confidence>=min_conf else 'NO BET'

    rankings.append({
        'Match':f'{home} vs {away}',
        'Prediction':prediction,
        'Confidence':confidence,
        'Verdict':verdict
    })

st.subheader('Global Opportunities')
if rankings:
    df=pd.DataFrame(rankings).sort_values('Confidence',ascending=False)
    st.dataframe(df,use_container_width=True)

    options={row['Match']:row for row in rankings}
    chosen=st.selectbox('Match Analysis',list(options.keys()))
    st.json(options[chosen])
else:
    st.info('Load fixtures using a valid Odds API key.')

st.caption('Worldwide coverage depends on competitions available from your odds provider. Probabilities are estimates, not guarantees.')
