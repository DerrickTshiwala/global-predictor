import streamlit as st
import requests
import scipy.stats as stats
import pandas as pd
import os
from datetime import datetime, timezone

st.set_page_config(page_title='Universal Football Analytics Pro', layout='wide')

TEAM_RATINGS = {
    'Liverpool': 2.1,'Arsenal':2.0,'Manchester City':2.3,'Real Madrid':2.2,
    'Bayern Munich':2.15,'Barcelona':2.0,'PSG':2.0,'Netherlands':1.95,
    'England':2.05,'France':2.0,'Brazil':2.1,'Argentina':2.1
}

st.title('Universal Football Analytics Pro v2.0')

st.sidebar.header('Account')
plan = st.sidebar.selectbox('Plan',['Free','Premium'])
user_tier='Free'
if plan=='Premium':
    pw=st.sidebar.text_input('Premium Password',type='password')
    if pw and pw==st.secrets.get('PREMIUM_PASSWORD',''):
        user_tier='Premium'
        st.sidebar.success('Premium Active')

bankroll=st.sidebar.number_input('Bankroll',10.0,1000000.0,1000.0)
api_key=st.text_input('Odds API Key',type='password')

leagues={'Premier League':'soccer_epl','Champions League':'soccer_uefa_champs_league','UEFA Nations League':'soccer_uefa_nations_league','La Liga':'soccer_spain_la_liga'}
league=st.selectbox('Competition',list(leagues.keys()))

matches=[]
if api_key:
    try:
        url=f"https://api.the-odds-api.com/v4/sports/{leagues[league]}/odds/?apiKey={api_key}&regions=uk,eu&markets=h2h&oddsFormat=decimal"
        r=requests.get(url,timeout=10)
        if r.status_code==200:
            matches=r.json()
    except Exception:
        pass

st.header('Top Predictions Today')
rank=[]
for m in matches:
    h=m['home_team']; a=m['away_team']
    hr=TEAM_RATINGS.get(h,1.45); ar=TEAM_RATINGS.get(a,1.2)
    ph=pdw=pa=0.0
    for x in range(6):
      for y in range(6):
        p=stats.poisson.pmf(x,hr)*stats.poisson.pmf(y,ar)
        if x>y: ph+=p
        elif x==y: pdw+=p
        else: pa+=p
    conf=min(100,round(abs(ph-pa)*100+50))
    pick=h+' Win' if ph>max(pdw,pa) else (a+' Win' if pa>pdw else 'Draw')
    rank.append({'Match':f'{h} vs {a}','Pick':pick,'Confidence':conf})
if rank:
    st.dataframe(pd.DataFrame(rank).sort_values('Confidence',ascending=False))

if matches:
    opts={f"{m['home_team']} vs {m['away_team']}":m for m in matches}
    sel=st.selectbox('Match Analysis',list(opts.keys()))
    match=opts[sel]
    home=match['home_team']; away=match['away_team']
    hr=TEAM_RATINGS.get(home,1.45); ar=TEAM_RATINGS.get(away,1.2)

    kickoff=match.get('commence_time')
    if kickoff:
        dt=datetime.fromisoformat(kickoff.replace('Z','+00:00'))
        st.info(f'Kick Off: {dt}')

    ph=pdw=pa=btts=o25=0.0; scores=[]
    for x in range(7):
      for y in range(7):
        p=stats.poisson.pmf(x,hr)*stats.poisson.pmf(y,ar)
        scores.append((f'{x}-{y}',p))
        if x>y: ph+=p
        elif x==y: pdw+=p
        else: pa+=p
        if x>0 and y>0: btts+=p
        if x+y>2: o25+=p

    scores.sort(key=lambda z:z[1],reverse=True)
    confidence=min(100,round(abs(ph-pa)*100+50))

    c1,c2,c3=st.columns(3)
    c1.metric('Home',f'{ph*100:.1f}%')
    c2.metric('Draw',f'{pdw*100:.1f}%')
    c3.metric('Away',f'{pa*100:.1f}%')

    st.success(f'Best Pick: {home if ph>pa else away} Win')
    st.metric('Confidence',confidence)

    st.subheader('Most Likely Scores')
    for s,p in scores[:5]:
        st.write(f'{s} : {p*100:.2f}%')

    if user_tier=='Premium':
        st.subheader('Premium Analytics')
        st.write(f'BTTS: {btts*100:.1f}%')
        st.write(f'Over 2.5: {o25*100:.1f}%')
        st.write(f'Suggested Stake: {bankroll*0.02:.2f}')
