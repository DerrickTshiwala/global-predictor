import streamlit as st
import requests
import pandas as pd
import scipy.stats as stats
from datetime import datetime, timezone

st.set_page_config(page_title="Football Analytics Pro 3.0", layout="wide")

st.title("Football Analytics Pro 3.0")

TEAM_RATINGS = {
    "Liverpool":2.1,"Arsenal":2.0,"Manchester City":2.3,
    "Real Madrid":2.2,"Bayern Munich":2.15,"Barcelona":2.0,
    "PSG":2.0,"England":2.05,"France":2.0,
    "Brazil":2.1,"Argentina":2.1,"Netherlands":1.95
}

leagues = {
    "Premier League":"soccer_epl",
    "Champions League":"soccer_uefa_champs_league",
    "UEFA Nations League":"soccer_uefa_nations_league",
    "La Liga":"soccer_spain_la_liga",
    "South Africa PSL":"soccer_spl"
}

st.sidebar.header("Settings")
api_key = st.sidebar.text_input("Odds API Key", type="password")
bankroll = st.sidebar.number_input("Bankroll", min_value=10.0, value=1000.0)
league = st.selectbox("Competition", list(leagues.keys()))

matches=[]
if api_key:
    try:
        url=f"https://api.the-odds-api.com/v4/sports/{leagues[league]}/odds/?apiKey={api_key}&regions=uk,eu&markets=h2h&oddsFormat=decimal"
        r=requests.get(url,timeout=10)
        if r.status_code==200:
            matches=r.json()
    except Exception as e:
        st.warning(str(e))

st.header("Top Picks Scanner")
rankings=[]
for m in matches:
    home=m['home_team']; away=m['away_team']
    hr=TEAM_RATINGS.get(home,1.45); ar=TEAM_RATINGS.get(away,1.20)
    ph=pd=pa=0
    for h in range(6):
      for a in range(6):
        p=stats.poisson.pmf(h,hr)*stats.poisson.pmf(a,ar)
        if h>a: ph+=p
        elif h==a: pd+=p
        else: pa+=p
    conf=min(100,round(abs(ph-pa)*100+50))
    pick=home+" Win" if ph>max(pd,pa) else away+" Win" if pa>pd else "Draw"
    risk='LOW' if conf>=85 else 'MEDIUM' if conf>=70 else 'HIGH'
    verdict='APPROVED' if conf>=75 else 'NO BET'
    rankings.append({'Match':f'{home} vs {away}','Pick':pick,'Confidence':conf,'Risk':risk,'Verdict':verdict})

if rankings:
    st.dataframe(pd.DataFrame(rankings).sort_values('Confidence',ascending=False),use_container_width=True)

if matches:
    options={f"{m['home_team']} vs {m['away_team']}":m for m in matches}
    selected=st.selectbox('Match Analysis',list(options.keys()))
    m=options[selected]
    home=m['home_team']; away=m['away_team']
    hr=TEAM_RATINGS.get(home,1.45); ar=TEAM_RATINGS.get(away,1.2)

    if m.get('commence_time'):
        dt=datetime.fromisoformat(m['commence_time'].replace('Z','+00:00'))
        st.info(f'Kick Off: {dt.strftime("%d %b %Y %H:%M UTC")}')
        st.info(f'Countdown: {dt-datetime.now(timezone.utc)}')

    ph=pdraw=pa=0.0
    scores=[]
    for h in range(7):
      for a in range(7):
        p=stats.poisson.pmf(h,hr)*stats.poisson.pmf(a,ar)
        scores.append((f'{h}-{a}',p))
        if h>a: ph+=p
        elif h==a: pdraw+=p
        else: pa+=p

    scores.sort(key=lambda x:x[1],reverse=True)
    fair_home=1/ph if ph else 999
    fair_draw=1/pdraw if pdraw else 999
    fair_away=1/pa if pa else 999

    c1,c2,c3=st.columns(3)
    c1.metric('Home',f'{ph*100:.1f}%')
    c2.metric('Draw',f'{pdraw*100:.1f}%')
    c3.metric('Away',f'{pa*100:.1f}%')

    confidence=min(100,round(abs(ph-pa)*100+50))
    verdict='APPROVED âœ…' if confidence>=75 else 'NO BET âŒ'

    st.subheader('Bet Verdict')
    st.success(verdict)
    st.metric('Confidence',confidence)

    st.subheader('Fair Odds')
    f1,f2,f3=st.columns(3)
    f1.metric('Home Fair',f'{fair_home:.2f}')
    f2.metric('Draw Fair',f'{fair_draw:.2f}')
    f3.metric('Away Fair',f'{fair_away:.2f}')

    st.subheader('Most Likely Scores')
    for s,p in scores[:5]:
        st.write(f'{s}: {p*100:.2f}%')

st.caption('Probabilities are estimates only and are not guarantees of outcomes.')
