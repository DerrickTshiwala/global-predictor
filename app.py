import math, re, sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import streamlit as st
from scipy.stats import poisson

APP_VERSION = "6.1"
DB = "football_intelligence.db"
ODDS = "https://api.the-odds-api.com/v4"
OF_RAW = "https://raw.githubusercontent.com/openfootball/football.json/master"
OF_TREE = "https://api.github.com/repos/openfootball/football.json/git/trees/master?recursive=1"

st.set_page_config(page_title=f"Football Intelligence v{APP_VERSION}", layout="wide")

# ---------- database ----------
def conn():
    c = sqlite3.connect(DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS historical_matches(
      id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL,
      source_key TEXT NOT NULL UNIQUE, match_date TEXT NOT NULL,
      competition TEXT, season TEXT, home_team TEXT NOT NULL,
      away_team TEXT NOT NULL, home_goals INTEGER NOT NULL,
      away_goals INTEGER NOT NULL, round_name TEXT, imported_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS predictions(
      id INTEGER PRIMARY KEY AUTOINCREMENT, prediction_time TEXT,
      event_id TEXT, sport_key TEXT, competition TEXT, commence_time TEXT,
      home_team TEXT, away_team TEXT,
      p_home REAL, p_draw REAL, p_away REAL,
      pick TEXT, model_odds REAL, market_odds REAL,
      edge REAL, ev REAL, verdict TEXT, model_version TEXT,
      status TEXT DEFAULT 'OPEN', actual_result TEXT, profit_units REAL);
    CREATE TABLE IF NOT EXISTS odds_snapshots(
      id INTEGER PRIMARY KEY AUTOINCREMENT, captured_at TEXT NOT NULL,
      event_id TEXT NOT NULL, sport_key TEXT, competition TEXT,
      commence_time TEXT, home_team TEXT, away_team TEXT, bookmaker TEXT,
      market TEXT, outcome TEXT, price REAL);
    CREATE INDEX IF NOT EXISTS ix_hist_date ON historical_matches(match_date);
    CREATE INDEX IF NOT EXISTS ix_pred_status ON predictions(status);
    CREATE INDEX IF NOT EXISTS ix_odds_event ON odds_snapshots(event_id);
    """)

    # CREATE TABLE IF NOT EXISTS does not modify an existing SQLite table.
    # Migrate databases created by v4/v5/v6 automatically.
    existing = {row[1] for row in c.execute("PRAGMA table_info(predictions)").fetchall()}
    columns = {
        "prediction_time": "TEXT",
        "event_id": "TEXT",
        "sport_key": "TEXT",
        "competition": "TEXT",
        "commence_time": "TEXT",
        "home_team": "TEXT",
        "away_team": "TEXT",
        "p_home": "REAL",
        "p_draw": "REAL",
        "p_away": "REAL",
        "pick": "TEXT",
        "model_odds": "REAL",
        "market_odds": "REAL",
        "edge": "REAL",
        "ev": "REAL",
        "verdict": "TEXT",
        "model_version": "TEXT",
        "status": "TEXT",
        "actual_result": "TEXT",
        "profit_units": "REAL",
    }
    for name, definition in columns.items():
        if name not in existing:
            c.execute(f"ALTER TABLE predictions ADD COLUMN {name} {definition}")

    c.execute("UPDATE predictions SET status='OPEN' WHERE status IS NULL OR TRIM(status)=''")
    c.execute("UPDATE predictions SET model_version=? WHERE model_version IS NULL OR TRIM(model_version)=''", (APP_VERSION,))
    c.commit()
    c.close()

init_db()

def now():
    return datetime.now(timezone.utc).isoformat()

def team_key(x):
    x = str(x or "").lower().strip()
    x = re.sub(r"\b(fc|afc|cf|sc|ac|fk|sk|sv|bv|ud|cd|ca|club|football|futbol)\b", " ", x)
    x = re.sub(r"[^a-z0-9]+", " ", x)
    return re.sub(r"\s+", " ", x).strip()

def result(h,a):
    return "H" if h>a else "D" if h==a else "A"

def probs(lh,la):
    p=np.zeros(3)
    for h in range(9):
        for a in range(9):
            q=poisson.pmf(h,lh)*poisson.pmf(a,la)
            p[0 if h>a else 1 if h==a else 2]+=q
    return p/p.sum()

def pick(p):
    return ("HOME","DRAW","AWAY")[int(np.argmax(p))]

def fair(p):
    return 1/p if p>0 else np.nan

def ev(p,odds):
    return p*odds-1 if odds and odds>1 else np.nan

# ---------- Odds API: discover real keys, never hard-code them ----------
@st.cache_data(ttl=3600, show_spinner=False)
def sports(api_key):
    r=requests.get(f"{ODDS}/sports",params={"apiKey":api_key},timeout=25)
    if r.status_code!=200: raise RuntimeError(f"Sports API {r.status_code}: {r.text[:500]}")
    return r.json()

def soccer(api_key):
    return [x for x in sports(api_key) if str(x.get("group","")).lower()=="soccer"]

def live_odds(api_key,sport):
    r=requests.get(f"{ODDS}/sports/{sport}/odds",
        params={"apiKey":api_key,"regions":"eu,uk","markets":"h2h","oddsFormat":"decimal"},timeout=25)
    if r.status_code!=200: raise RuntimeError(f"Odds API {r.status_code}: {r.text[:700]}")
    return r.json(),dict(r.headers)

def market(event):
    out={"HOME":[],"DRAW":[],"AWAY":[]}
    for b in event.get("bookmakers",[]):
        for m in b.get("markets",[]):
            if m.get("key")!="h2h": continue
            for o in m.get("outcomes",[]):
                n=o.get("name"); v=float(o.get("price",0) or 0)
                k="HOME" if n==event.get("home_team") else "AWAY" if n==event.get("away_team") else "DRAW" if str(n).lower()=="draw" else None
                if k: out[k].append((b.get("key",""),v))
    return out

def best_odds(event):
    m=market(event)
    return {k:max(v,key=lambda x:x[1])[1] for k,v in m.items() if v}

def save_snapshots(events,sport):
    c=conn(); ts=now()
    rows=[]
    for e in events:
        for b in e.get("bookmakers",[]):
            for m in b.get("markets",[]):
                if m.get("key")!="h2h": continue
                for o in m.get("outcomes",[]):
                    rows.append((ts,e.get("id"),sport,e.get("sport_title"),e.get("commence_time"),
                                 e.get("home_team"),e.get("away_team"),b.get("key"),"h2h",o.get("name"),o.get("price")))
    c.executemany("""INSERT OR IGNORE INTO odds_snapshots
      (captured_at,event_id,sport_key,competition,commence_time,home_team,away_team,
       bookmaker,market,outcome,price) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",rows)
    c.commit(); c.close()

# ---------- free public-domain historical results ----------
@st.cache_data(ttl=86400, show_spinner=False)
def openfootball_paths():
    r=requests.get(OF_TREE,timeout=35,headers={"User-Agent":"Football-Intelligence-6.1"})
    if r.status_code!=200:
        raise RuntimeError(f"OpenFootball discovery {r.status_code}: {r.text[:500]}")
    paths=[]
    for x in r.json().get("tree",[]):
        p=x.get("path","")
        if x.get("type")!="blob" or not p.endswith(".json"):
            continue
        # Actual football.json paths are typically 2025-26/en.1.json,
        # 2025-26/de.1.json, etc. The old regex incorrectly required
        # a leading slash before the season directory.
        if re.search(r"(^|/)\d{4}(?:-\d{2})?/[^/]+\.json$",p):
            paths.append(p)
    return sorted(set(paths))

def season_from_path(p):
    for x in p.split("/"):
        if re.fullmatch(r"\d{4}(-\d{2})?",x): return x
    return ""

def parse_match(m,competition,season,path):
    s=m.get("score",{})
    ft=s.get("ft") if isinstance(s,dict) else s if isinstance(s,list) else None
    if not isinstance(ft,list) or len(ft)<2: return None
    try: hg,ag=int(ft[0]),int(ft[1])
    except: return None
    d=str(m.get("date",""))[:10]
    h,a=m.get("team1"),m.get("team2")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",d) or not h or not a: return None
    key=f"openfootball:{path}|{d}|{team_key(h)}|{team_key(a)}|{hg}-{ag}"
    return ("openfootball",key,d,competition,season,str(h).strip(),str(a).strip(),hg,ag,m.get("round"),now())

def import_history(seasons_back=6):
    current=datetime.now().year
    paths=[]
    for p in openfootball_paths():
        s=season_from_path(p)
        y=int(s[:4]) if s else 0
        if y>=current-seasons_back-1: paths.append(p)
    paths=sorted(set(paths))
    c=conn(); files=0; rows=0; errors=[]
    for p in paths:
        try:
            r=requests.get(f"{OF_RAW}/{p}",timeout=25)
            if r.status_code!=200: continue
            data=r.json()
            competition=data.get("name") or Path(p).stem
            season=season_from_path(p)
            batch=[parse_match(m,competition,season,p) for m in data.get("matches",[])]
            batch=[x for x in batch if x]
            if batch:
                c.executemany("""INSERT OR IGNORE INTO historical_matches
                (source,source_key,match_date,competition,season,home_team,away_team,
                 home_goals,away_goals,round_name,imported_at)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?)""",batch)
                rows+=len(batch); files+=1
        except Exception as e: errors.append(f"{p}: {e}")
    c.commit(); c.close()
    return files,rows,errors

def history():
    c=conn()
    d=pd.read_sql_query("SELECT * FROM historical_matches ORDER BY match_date,id",c)
    c.close()
    if not d.empty: d["match_date"]=pd.to_datetime(d["match_date"],utc=True,errors="coerce")
    return d.dropna(subset=["match_date"]) if not d.empty else d

# ---------- leakage-safe model ----------
def state(h,before=None,competition=None):
    x=h.copy()
    if competition and competition!="ALL": x=x[x.competition==competition]
    if before is not None: x=x[x.match_date<before]
    elo={}; st={}
    for r in x.sort_values(["match_date","id"]).itertuples():
        ht,at=team_key(r.home_team),team_key(r.away_team)
        eh,ea=elo.get(ht,1500.),elo.get(at,1500.)
        exp=1/(1+10**((ea+35-eh)/400))
        actual=1 if r.home_goals>r.away_goals else .5 if r.home_goals==r.away_goals else 0
        k=28 if st.get(ht,{}).get("n",0)+st.get(at,{}).get("n",0)<20 else 20
        d=k*(actual-exp); elo[ht]=eh+d; elo[at]=ea-d
        for t,gf,ga,side in [(ht,r.home_goals,r.away_goals,"home"),(at,r.away_goals,r.home_goals,"away")]:
            q=st.setdefault(t,{"n":0,"gf":0,"ga":0,"hg":0,"ha":0,"hn":0,"ag":0,"aa":0,"an":0,"recent":[]})
            q["n"]+=1;q["gf"]+=gf;q["ga"]+=ga;q["recent"]=(q["recent"]+[(gf,ga)])[-8:]
            if side=="home": q["hg"]+=gf;q["ha"]+=ga;q["hn"]+=1
            else: q["ag"]+=gf;q["aa"]+=ga;q["an"]+=1
    return elo,st,x

def model(h,home,away,competition=None,before=None):
    elo,st,x=state(h,before,competition)
    hk,ak=team_key(home),team_key(away)
    eh,ea=elo.get(hk,1500),elo.get(ak,1500)
    sh,sa=st.get(hk,{}),st.get(ak,{})
    bh=max(.65,float(x.home_goals.mean())) if len(x) else 1.35
    ba=max(.55,float(x.away_goals.mean())) if len(x) else 1.05
    def attack(q,side,base):
        n=q.get(side[0]+"n",0)
        gf=q.get(side[0]+"g",0)/n if n else q.get("gf",0)/max(1,q.get("n",0))
        return float(np.clip(gf/max(.4,base),.55,1.7)) if q else 1.
    def defence(q,side,base):
        n=q.get(side[0]+"n",0)
        ga=q.get(side[0]+"a",0)/n if n else q.get("ga",0)/max(1,q.get("n",0))
        return float(np.clip(base/max(.4,ga),.55,1.7)) if q else 1.
    ah=attack(sh,"home",bh); aa=attack(sa,"away",ba)
    dh=defence(sh,"home",ba); da=defence(sa,"away",bh)
    def form(q):
        z=q.get("recent",[])[-5:]
        return np.mean([3 if g>a else 1 if g==a else 0 for g,a in z])/3 if z else .5
    fh,fa=form(sh),form(sa)
    ed=(eh-ea)/400
    lh=np.clip(bh*ah*da*np.exp(np.clip(.28*ed+.08*(fh-fa),-.45,.45)),.2,3.8)
    la=np.clip(ba*aa*dh*np.exp(np.clip(-.20*ed+.06*(fa-fh),-.35,.35)),.15,3.4)
    return probs(lh,la),float(lh),float(la)

def confidence(p):
    ent=-sum(float(x)*math.log(max(float(x),1e-12),3) for x in p)
    return round(float(np.clip((1-ent)*100,0,100)),1)

def decision(p,odds,min_edge=.035,min_ev=.04):
    k=pick(p); i={"HOME":0,"DRAW":1,"AWAY":2}[k]
    e=v=np.nan
    if k in odds:
        e=float(p[i]-1/odds[k]); v=float(ev(p[i],odds[k]))
    verdict="VALUE CANDIDATE" if np.isfinite(e) and np.isfinite(v) and e>=min_edge and v>=min_ev else "MODEL LEAN" if confidence(p)>=55 else "NO BET"
    return k,e,v,verdict

# ---------- chronological backtest ----------
def backtest(h,competition="ALL",n_test=400,min_train=80):
    x=h if competition=="ALL" else h[h.competition==competition]
    x=x.sort_values(["match_date","id"]).reset_index(drop=True)
    if len(x)<=min_train: return pd.DataFrame(),{"error":f"Need >{min_train} matches; found {len(x)}."}
    start=max(min_train,len(x)-n_test); rows=[]
    for i in range(start,len(x)):
        r=x.iloc[i]
        p,xh,xa=model(x,r.home_team,r.away_team,competition,r.match_date)
        y=result(int(r.home_goals),int(r.away_goals))
        one=np.array([y=="H",y=="D",y=="A"],dtype=float)
        rows.append({"date":r.match_date.date().isoformat(),"competition":r.competition,
                     "home":r.home_team,"away":r.away_team,"p_home":p[0],"p_draw":p[1],"p_away":p[2],
                     "pick":pick(p),"actual":y,"correct":int(pick(p)==y),
                     "brier":float(np.sum((p-one)**2)),
                     "log_loss":float(-math.log(max(p[["H","D","A"].index(y)],1e-12))),
                     "xg_home":xh,"xg_away":xa})
    d=pd.DataFrame(rows)
    return d,{"matches":len(d),"accuracy":d.correct.mean(),"brier":d.brier.mean(),"log_loss":d.log_loss.mean()}

# ---------- settlement ----------
def settle(api_key,sport):
    r=requests.get(f"{ODDS}/sports/{sport}/scores",params={"apiKey":api_key,"daysFrom":3},timeout=25)
    if r.status_code!=200: raise RuntimeError(f"Scores API {r.status_code}: {r.text[:500]}")
    events=r.json(); c=conn()
    p=pd.read_sql_query("SELECT * FROM predictions WHERE status='OPEN'",c)
    done=0
    for e in events:
        if not e.get("completed"): continue
        vals={z.get("name"):int(z.get("score")) for z in e.get("scores",[]) if str(z.get("score","")).isdigit()}
        if e.get("home_team") not in vals or e.get("away_team") not in vals: continue
        actual=result(vals[e["home_team"]],vals[e["away_team"]])
        for r in p[p.event_id==e.get("id")].itertuples():
            won=(r.pick=="HOME" and actual=="H") or (r.pick=="DRAW" and actual=="D") or (r.pick=="AWAY" and actual=="A")
            profit=(r.market_odds-1) if won and r.market_odds and r.market_odds>1 else -1 if r.market_odds else None
            c.execute("UPDATE predictions SET status='SETTLED',actual_result=?,profit_units=? WHERE id=?",(actual,profit,r.id)); done+=1
    c.commit();c.close();return done

# ---------- UI ----------
st.title(f"⚽ Football Intelligence Platform v{APP_VERSION}")
st.caption("Automated public-domain results • dynamically discovered live odds • leakage-safe modelling • backtesting • EV • paper ROI")

with st.sidebar:
    key=st.text_input("The Odds API key",value=st.secrets.get("ODDS_API_KEY","") if hasattr(st,"secrets") else "",type="password")
    seasons=st.slider("Historical seasons",2,12,6)
    min_edge=st.slider("Minimum edge",0.00,0.20,0.035,0.005)
    min_ev=.04
    st.caption("Historical odds are deliberately NOT required: The Odds API historical odds are a paid feature. The platform builds its own live odds history from deployment onward.")

h=history()
a,b,c,d=st.columns(4)
a.metric("Historical matches",f"{len(h):,}")
b.metric("Teams",f"{len(set(h.home_team)|set(h.away_team)):,}" if len(h) else "0")
cc=conn()
pred_count=cc.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
open_count=cc.execute("SELECT COUNT(*) FROM predictions WHERE status='OPEN'").fetchone()[0]
cc.close()
c.metric("Archived predictions",f"{pred_count:,}")
d.metric("Open predictions",f"{open_count:,}")

live, hist, bt, perf, dbtab=st.tabs(["Live Intelligence","Historical Data","Backtest","Performance","Database"])

with live:
    if not key:
        st.info("Enter the API key. The app will discover valid soccer sport keys automatically, so invalid hard-coded keys cannot cause the old UNKNOWN_SPORT problem.")
    else:
        try:
            ss=soccer(key)
            if not ss: st.warning("No soccer competitions are currently returned by the API.")
            else:
                opts={f"{x['title']} [{x['key']}]":x for x in ss}
                label=st.selectbox("Competition",list(opts))
                sport=opts[label]["key"]
                events,headers=live_odds(key,sport)
                st.caption(f"{len(events)} events • API credits remaining: {headers.get('x-requests-remaining','?')}")
                save_snapshots(events,sport)
                rows=[]
                for e in events:
                    p,xh,xa=model(h,e["home_team"],e["away_team"])
                    odds=best_odds(e); k,edge,v,ver=decision(p,odds,min_edge,min_ev)
                    i={"HOME":0,"DRAW":1,"AWAY":2}[k]
                    rows.append({"Match":f"{e['home_team']} vs {e['away_team']}","Start":e.get("commence_time"),
                                 "Pick":k,"P(Home)":round(p[0],3),"P(Draw)":round(p[1],3),"P(Away)":round(p[2],3),
                                 "Fair odds":round(fair(p[i]),2),"Market odds":round(odds[k],2) if k in odds else np.nan,
                                 "Edge":round(edge,3) if np.isfinite(edge) else np.nan,"EV":round(v,3) if np.isfinite(v) else np.nan,
                                 "Strength":confidence(p),"Verdict":ver})
                df=pd.DataFrame(rows)
                if not df.empty: st.dataframe(df,use_container_width=True,hide_index=True)
                x1,x2=st.columns(2)
                with x1:
                    if st.button("Archive predictions"):
                        c=conn();ts=now()
                        for e in events:
                            p,_,_=model(h,e["home_team"],e["away_team"]);od=best_odds(e);k,edge,v,ver=decision(p,od,min_edge,min_ev);i={"HOME":0,"DRAW":1,"AWAY":2}[k]
                            c.execute("""INSERT OR IGNORE INTO predictions
                            (prediction_time,event_id,sport_key,competition,commence_time,home_team,away_team,
                             p_home,p_draw,p_away,pick,model_odds,market_odds,edge,ev,verdict,model_version)
                             VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                             (ts,e.get("id"),sport,e.get("sport_title"),e.get("commence_time"),e["home_team"],e["away_team"],
                              float(p[0]),float(p[1]),float(p[2]),k,float(fair(p[i])),od.get(k),
                              float(edge) if np.isfinite(edge) else None,float(v) if np.isfinite(v) else None,ver,APP_VERSION))
                        c.commit();c.close();st.success("Archived.")
                with x2:
                    if st.button("Settle recent predictions"):
                        st.success(f"Settled {settle(key,sport)} prediction(s).")
        except Exception as e: st.error(str(e))

with hist:
    st.subheader("Automatic historical data")
    st.write("Primary workflow: no CSV upload. The app discovers OpenFootball JSON season files and imports them into SQLite.")
    if st.button("Download / update history"):
        try:
            with st.spinner("Downloading and indexing public-domain results..."):
                files,rows,errors=import_history(seasons)
            st.success(f"Processed {files} source files and indexed {rows:,} result records.")
            if errors: st.warning("Some files were skipped: "+" | ".join(errors[:5]))
            st.rerun()
        except Exception as e: st.error(str(e))
    if len(h):
        st.dataframe(h.tail(200).sort_values("match_date",ascending=False),use_container_width=True,hide_index=True)

with bt:
    st.subheader("Walk-forward out-of-sample backtest")
    if h.empty:
        st.info("Historical data is empty. Open Historical Data and click Download / update history first.")
    elif len(h) <= 80:
        st.warning(f"Only {len(h):,} historical matches are available. More than 80 are required for the current backtest.")
    else:
        comps=["ALL"]+sorted(h.competition.dropna().unique().tolist())
        comp=st.selectbox("Competition",comps)
        available=len(h) if comp=="ALL" else int((h.competition==comp).sum())
        max_test=max(1,min(1000,available-80))
        default_test=min(300,max_test)
        ntest=st.slider("Test matches",1,max_test,default_test)
        st.caption(f"{available:,} matches available; {max(0,available-80):,} available after the minimum training window.")
        if st.button("Run backtest"):
            with st.spinner("Running chronological predictions without future-data leakage..."):
                out,m=backtest(h,comp,ntest)
            if "error" in m: st.warning(m["error"])
            else:
                q1,q2,q3,q4=st.columns(4)
                q1.metric("Matches",m["matches"]);q2.metric("Accuracy",f"{m['accuracy']*100:.2f}%")
                q3.metric("Brier",f"{m['brier']:.4f}");q4.metric("Log loss",f"{m['log_loss']:.4f}")
                st.dataframe(out,use_container_width=True,hide_index=True)

with perf:
    st.subheader("Archived prediction performance")
    c=conn()
    p=pd.read_sql_query("SELECT * FROM predictions ORDER BY COALESCE(prediction_time,'') DESC, id DESC",c)
    c.close()
    if p.empty:
        st.info("No archived predictions yet.")
    else:
        s=p[p["status"].fillna("OPEN")=="SETTLED"].copy()
        s["profit_units"]=pd.to_numeric(s["profit_units"],errors="coerce")
        priced=s.dropna(subset=["profit_units"])
        profit=float(priced["profit_units"].sum()) if len(priced) else 0.0
        roi=profit/len(priced) if len(priced) else np.nan
        z1,z2,z3,z4=st.columns(4)
        z1.metric("Settled",len(s));z2.metric("Priced settled",len(priced))
        z3.metric("Wins",int((priced["profit_units"]>0).sum()) if len(priced) else 0)
        z4.metric("ROI / unit",f"{roi*100:.2f}%" if np.isfinite(roi) else "—")
        st.dataframe(p,use_container_width=True,hide_index=True)

with dbtab:
    c=conn()
    for t in ["historical_matches","predictions","odds_snapshots"]:
        st.write(f"**{t}:** {c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:,}")
    c.close()
    st.code(DB)
    st.info("SQLite schema migration is automatic. Existing databases are upgraded when this app starts.")
    st.warning("Keep the API key in Streamlit secrets. Never commit secrets.toml to a public repository.")

st.caption("Model outputs are estimates, not guarantees. VALUE CANDIDATE means the model/market thresholds were met; it does not mean a profitable outcome is certain.")
