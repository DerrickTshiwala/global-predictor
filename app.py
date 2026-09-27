import streamlit as st
import numpy as np
import scipy.stats as stats
import pandas as pd
import requests

# Page Layout Configuration
st.set_page_config(page_title="Global Value Bet Predictor", layout="centered")

st.title("🌐 Global Football Analytics & Value Predictor Engine")
st.markdown("---")

# 1. SIDEBAR: Monetization & Wallet Controls
st.sidebar.header("💳 Subscription & Wallet Settings")
user_tier = st.sidebar.selectbox("Your Account Plan", ["Free Tier", "Premium Member (Unlocked)"])
user_bankroll = st.sidebar.number_input("Your Total Wallet Balance (any currency)", min_value=10.0, value=1000.0, step=10.0)

# 2. DATA INGESTION: The Odds API Global Integration
API_KEY = st.text_input("Enter Free 'The Odds API' Key (Leave blank to use simulated demo data)", type="password")
region = st.selectbox("Select Target Global Region for Odds", ["uk", "eu", "us", "au"])

# Simulated Global Database
global_league_db = {
    "English Premier League": {
        "Manchester City": {"attack": 1.8, "defense": 0.6},
        "Arsenal": {"attack": 1.7, "defense": 0.65},
        "Liverpool": {"attack": 1.75, "defense": 0.70}
    },
    "South African PSL": {
        "Mamelodi Sundowns": {"attack": 1.65, "defense": 0.55},
        "Orlando Pirates": {"attack": 1.40, "defense": 0.80},
        "Kaizer Chiefs": {"attack": 1.05, "defense": 1.10}
    }
}

selected_league = st.selectbox("Select League Venue", list(global_league_db.keys()))
home_team = st.selectbox("Select Home Team", list(global_league_db[selected_league].keys()))
away_teams = [team for team in global_league_db[selected_league].keys() if team != home_team]
away_team = st.selectbox("Select Away Team", away_teams)

# Fetching real-time global odds if API key is provided
bookie_odds = 2.15 # Default fallback
if API_KEY:
    # Use standard upcoming soccer filter endpoint to match variants safely
    SPORT = "soccer_epl" if selected_league == "English Premier League" else "soccer_spl"
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds/?apiKey={API_KEY}&regions={region}&markets=h2h&oddsFormat=decimal"
    
    try:
        res = requests.get(url)
        if res.status_code == 200:
            response = res.json()
            match_found = False
            
            # Clean string parsing to prevent strict text alignment failures
            for match in response:
                h_api = match['home_team'].lower().replace(" ", "")
                a_api = match['away_team'].lower().replace(" ", "")
                h_local = home_team.lower().replace(" ", "")
                a_local = away_team.lower().replace(" ", "")
                
                if h_local in h_api or a_local in a_api:
                    # Look inside the returned list of bookmakers
                    for bookmaker in match.get('bookmakers', []):
                        for market in bookmaker.get('markets', []):
                            if market['key'] == 'h2h':
                                for outcome in market['outcomes']:
                                    if outcome['name'].lower().replace(" ", "") == h_local:
                                        bookie_odds = float(outcome['price'])
                                        st.success(f"⚡ Live feed matched via {bookmaker['title']}! Live Odds for {home_team}: {bookie_odds}")
                                        match_found = True
                                        break
                        if match_found: break
                if match_found: break
            
            if not match_found:
                st.info("⚠️ Fixture match not active in live API feed yet. Running on template database odds.")
        else:
            st.error(f"API Server Error: Status Code {res.status_code}. Checking your credit logs.")
    except Exception as e:
        st.warning("Connection timeout. Running engine on default baseline odds.")

# 3. ADVANCED ANALYSIS VARIABLES
st.header("Match Day Conditions")
col1, col2, col3 = st.columns(3)
with col1: is_derby = st.checkbox("Local Derby Match")
with col2: home_fatigue = st.checkbox(f"{home_team} Mid-week Travel")
with col3: away_fatigue = st.checkbox(f"{away_team} Mid-week Travel")

# 4. MATHEMATICAL COMPUTATION ENGINE (Poisson Modeling)
home_stats = global_league_db[selected_league][home_team]
away_stats = global_league_db[selected_league][away_team]

home_attack = home_stats["attack"] * (0.85 if is_derby else 1.0) * (0.90 if home_fatigue else 1.0)
away_attack = away_stats["attack"] * (1.15 if is_derby else 1.0) * (0.90 if away_fatigue else 1.0)
home_defense = home_stats["defense"]
away_defense = away_stats["defense"]

base_home_avg, base_away_avg = 1.35, 1.15
home_xg = home_attack * away_defense * base_home_avg
away_xg = away_attack * home_defense * base_away_avg

prob_home, prob_draw, prob_away = 0.0, 0.0, 0.0
prob_btts, prob_over25 = 0.0, 0.0
max_g = 6

for h in range(max_g):
    for a in range(max_g):
        p_h = stats.poisson.pmf(h, home_xg)
        p_a = stats.poisson.pmf(a, away_xg)
        j_p = p_h * p_a
        
        if h > a: prob_home += j_p
        elif h == a: prob_draw += j_p
        else: prob_away += j_p
        
        if h > 0 and a > 0: prob_btts += j_p
        if (h + a) > 2.5: prob_over25 += j_p

fair_home_odds = 1 / prob_home if prob_home > 0 else 999.0
is_worth_it = bookie_odds > fair_home_odds

# 5. RENDERING RESULTS
st.header("Automated Selection & Verdict")
if is_worth_it:
    st.success(f"🚨 VERDICT: WORTH IT! The global odds offer a mathematical edge over the bookmaker market margin.")
else:
    st.error("❌ VERDICT: NOT WORTH IT! Payout margins are too small to justify the hazard risk.")

metric_col1, metric_col2, metric_col3 = st.columns(3)
metric_col1.metric("Win Probability", f"{round(prob_home * 100, 1)}%")
metric_col2.metric("True Minimum Odds", f"{round(fair_home_odds, 2)}")
metric_col3.metric("Edge Value Margin", f"{round(((bookie_odds/fair_home_odds)-1)*100, 1)}%" if is_worth_it else "0.0%")

# 6. BUSINESS FREEMIUM GATEWAY (FIXED CRASH TYPO HERE)
st.header("🔥 Premium Statistical Predictions")
if user_tier == "Free Tier":
    st.warning("🔒 Exact Correct Score Matrices, BTTS Probability, and Kelly Criterion Stake Sizes are locked.")
    st.info("💡 Business Hint to Premium Users: Upgrade your account via our Patreon link to see exactly how much capital to risk on this value edge.")
else:
    st.subheader("🎯 Premium Engine Dashboard Inclusions")
    b_frac = bookie_odds - 1
    raw_k = ((prob_home * bookie_odds) - 1) / b_frac if b_frac > 0 else 0
    kelly_pct = max(0.0, raw_k * 0.25) # Fractional Kelly Guardrail
    
    col_p1, col_p2 = st.columns(2)
    col_p1.metric("Kelly Stake Size Allocation", f"{round(kelly_pct * 100, 2)}%")
    col_p2.metric("Exact Capital Stake Risk Size", f"${round(user_bankroll * kelly_pct, 2)}")
    
    st.write(f"**Alternative Market: Both Teams to Score (BTTS):** {round(prob_btts * 100, 1)}%")
    st.write(f"**Alternative Market: Over 2.5 Total Match Goals:** {round(prob_over25 * 100, 1)}%")

st.markdown("---")
st.caption("⚠️ Legal Disclaimer: This web application tracks mathematical calculations and data distributions. It does not provide legal financial betting advice. Winnings are never guaranteed. Users must comply with their local national gaming legislation. 18+ winners know when to stop.")
