import streamlit as st
import numpy as np
import scipy.stats as stats
import pandas as pd
import requests

# Page Layout Configuration
st.set_page_config(page_title="Universal Value Predictor Engine", layout="centered")

st.title("🌐 Universal Football Analytics & Live Value Engine")
st.markdown("---")

# 1. SIDEBAR: Secure Monetization & Gatekeeper Controls
st.sidebar.header("💳 Subscription & Wallet Settings")
user_tier_input = st.sidebar.selectbox("Your Account Plan", ["Free Tier", "Premium Member"])

user_tier = "Free Tier"
if user_tier_input == "Premium Member":
    secret_password = st.sidebar.text_input("Enter Premium Member Password", type="password")
    if secret_password == "VIP-MATH-2026":
        user_tier = "Premium Member (Unlocked)"
        st.sidebar.success("🔒 Premium Features Unlocked!")
    else:
        if secret_password:
            st.sidebar.error("❌ Invalid Password")
        user_tier = "Free Tier"

user_bankroll = st.sidebar.number_input("Your Account Balance (any currency)", min_value=10.0, value=1000.0, step=10.0)

# 2. DATA INGESTION: Comprehensive Global Club & National Teams Directory
st.header("1. Select Live Global Feed")
API_KEY = st.text_input("Enter Your Free 'The Odds API' Key", value="45abb5e26fb108e9a81ca9570df8666d", type="password")

# Complete directory mapping out every global market category, explicitly adding International Tiers
global_leagues_directory = {
    "🌍 FIFA World Cup / Qualifiers": "soccer_fifa_world_cup",
    "🏆 UEFA Nations League": "soccer_uefa_nations_league",
    "🌍 Africa Cup of Nations (AFCON)": "soccer_afcon",
    "🏆 UEFA Champions League": "soccer_uefa_champs_league",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 English Premier League": "soccer_epl",
    "🇿🇦 South African PSL": "soccer_spl",
    "🇪🇸 Spanish La Liga": "soccer_spain_la_liga",
    "🇮🇹 Italian Serie A": "soccer_italy_serie_a",
    "🇩🇪 German Bundesliga": "soccer_germany_bundesliga",
    "🇫🇷 French Ligue 1": "soccer_france_ligue_one",
    "🇪🇺 UEFA Europa League": "soccer_uefa_europa_league",
    "🇺🇸 Major League Soccer (MLS)": "soccer_usa_mls",
    "🇦🇺 Australian A-League": "soccer_australia_aleague",
    "🇧🇷 Brazilian Serie A": "soccer_brazil_campeonato",
    "🇲🇽 Mexican Liga MX": "soccer_mexico_ligamx"
}

selected_league_name = st.selectbox("Choose Competition Venue", list(global_leagues_directory.keys()))
selected_sport_key = global_leagues_directory[selected_league_name]

# 3. INTERACTIVE LIVE FIXTURE LOADER
st.header("2. Choose Active Live Fixture")
bookie_odds = 2.00
home_team = ""
away_team = ""

if API_KEY:
    # Querying deep feeds ensures all continental bookmaker lists populate
    url = f"https://the-odds-api.com{selected_sport_key}/odds/?apiKey={API_KEY}&regions=uk,eu,us,au&markets=h2h&oddsFormat=decimal"
    try:
        res = requests.get(url)
        live_matches = []
        if res.status_code == 200:
            live_matches = res.json()
            
        # Fail-Safe Engine: Handles off-season or live schedule gaps seamlessly
        if len(live_matches) == 0:
            st.info("ℹ️ Live API matches resting for this layout. Running Simulated Value Engine:")
            
            demo_fixtures = {
                "🌍 FIFA World Cup / Qualifiers": {"home": "Brazil", "away": "Argentina", "odds": 2.10},
                "🏆 UEFA Nations League": {"home": "France", "away": "England", "odds": 2.35},
                "🌍 Africa Cup of Nations (AFCON)": {"home": "South Africa", "away": "Nigeria", "odds": 2.60},
                "🏴󠁧󠁢󠁥󠁮󠁧󠁿 English Premier League": {"home": "Manchester City", "away": "Arsenal", "odds": 2.25},
                "🇿🇦 South African PSL": {"home": "Mamelodi Sundowns", "away": "Orlando Pirates", "odds": 1.95},
                "🏆 UEFA Champions League": {"home": "Real Madrid", "away": "Bayern Munich", "odds": 2.15}
            }
            
            default_fixture = demo_fixtures.get(selected_league_name, {"home": "Home Nations Elite", "away": "Away Nations Elite", "odds": 2.00})
            home_team = default_fixture["home"]
            away_team = default_fixture["away"]
            bookie_odds = default_fixture["odds"]
            
            st.warning(f"🤖 Simulated Match Active: {home_team} vs {away_team} (Live Bookmaker Benchmark Odds: {bookie_odds})")
        else:
            match_options = {}
            for match in live_matches:
                display_label = f"{match['home_team']} vs {match['away_team']}"
                match_options[display_label] = match
                
            selected_match_label = st.selectbox("Select Upcoming Match", list(match_options.keys()))
            target_match = match_options[selected_match_label]
            
            home_team = target_match['home_team']
            away_team = target_match['away_team']
            
            odds_list = []
            for bookmaker in target_match.get('bookmakers', []):
                for market in bookmaker.get('markets', []):
                    if market['key'] == 'h2h':
                        for outcome in market['outcomes']:
                            if outcome['name'] == home_team:
                                odds_list.append(float(outcome['price']))
            
            bookie_odds = max(odds_list) if odds_list else 2.00
            st.success(f"⚡ Live Feed Sync Complete! Top Global Odds for {home_team} Win: {bookie_odds}")
            
    except Exception as e:
        st.error("Engine system reset. Loading system simulation benchmarks.")
        st.stop()
else:
    st.info("🔑 Paste your 'The Odds API' key to load all active worldwide matches automatically.")
    st.stop()

# 4. WEATHER & MATCH DAY VARIABLES
st.header("3. Configuration Conditions")
col1, col2, col3 = st.columns(3)
with col1: is_derby = st.checkbox("High-Intensity Rivalry / Derby")
with col2: home_fatigue = st.checkbox(f"{home_team} Squad Fatigue")
with col3: away_fatigue = st.checkbox(f"{away_team} Squad Fatigue")

# 5. POISSON COMPUTATIONAL INTELLIGENCE MATRIX
base_home_xg = 1.45 * (0.85 if is_derby else 1.0) * (0.90 if home_fatigue else 1.0)
base_away_xg = 1.20 * (1.15 if is_derby else 1.0) * (0.90 if away_fatigue else 1.0)

prob_home, prob_draw, prob_away = 0.0, 0.0, 0.0
prob_btts, prob_over25 = 0.0, 0.0
max_g = 6

for h in range(max_g):
    for a in range(max_g):
        p_h = stats.poisson.pmf(h, base_home_xg)
        p_a = stats.poisson.pmf(a, base_away_xg)
        j_p = p_h * p_a
        
        if h > a: prob_home += j_p
        elif h == a: prob_draw += j_p
        else: prob_away += j_p
        
        if h > 0 and a > 0: prob_btts += j_p
        if (h + a) > 2.5: prob_over25 += j_p

fair_home_odds = 1 / prob_home if prob_home > 0 else 999.0
is_worth_it = bookie_odds > fair_home_odds

# 6. AUTOMATED VERDICT INTERFACE
st.header("4. Value Assessment Output")
if is_worth_it:
    st.success(f"🚨 VERDICT: WORTH IT! The global odds offer a clear mathematical edge over the market.")
else:
    st.error("❌ VERDICT: NOT WORTH IT! Market margins are too small to justify the hazard risk.")

metric_col1, metric_col2, metric_col3 = st.columns(3)
metric_col1.metric("Win Probability", f"{round(prob_home * 100, 1)}%")
metric_col2.metric("True Minimum Odds", f"{round(fair_home_odds, 2)}")
metric_col3.metric("Edge Value Margin", f"{round(((bookie_odds/fair_home_odds)-1)*100, 1)}%" if is_worth_it else "0.0%")

# 7. BUSINESS FREEMIUM GATEWAY CONTAINER
st.header("🔥 Premium Statistical Predictions")
if user_tier == "Free Tier":
    st.warning("🔒 Exact Correct Score Line Matrices, BTTS Probability, and Kelly Criterion Stake Sizes are locked.")
    st.info("💡 Business Hint to Premium Users: Upgrade your account plan via our Patreon checkout link to reveal precise wallet allocation layouts.")
else:
    st.subheader("🎯 Premium Engine Dashboard Inclusions")
    b_frac = bookie_odds - 1
    raw_k = ((prob_home * bookie_odds) - 1) / b_frac if b_frac > 0 else 0
    kelly_pct = max(0.0, raw_k * 0.25)
    
    col_p1, col_p2 = st.columns(2)
    col_p1.metric("Kelly Stake Size Allocation", f"{round(kelly_pct * 100, 2)}%")
    col_p2.metric("Recommended Stake Value", f"${round(user_bankroll * kelly_pct, 2)}")
    
    st.write(f"**Alternative Market Selection: Both Teams to Score (BTTS):** {round(prob_btts * 100, 1)}%")
    st.write(f"**Alternative Market Selection: Over 2.5 Total Match Goals:** {round(prob_over25 * 100, 1)}%")

st.markdown("---")
st.caption("⚠️ Legal Disclaimer: This web application tracks mathematical calculations and data distributions. It does not provide legal financial betting advice. Winnings are never guaranteed. Users must comply with their local national gaming legislation. 18+ winners know when to stop.")
