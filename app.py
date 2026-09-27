import streamlit as st
import numpy as np
import scipy.stats as stats
import pandas as pd
import requests

# Page Layout Configuration
st.set_page_config(page_title="Universal Value Predictor Engine", layout="centered")

st.title("Universal Football Analytics and Live Value Engine")
st.markdown("---")

# 1. SIDEBAR: Secure Monetization and Gatekeeper Controls
st.sidebar.header("Subscription and Wallet Settings")
user_tier_input = st.sidebar.selectbox("Your Account Plan", ["Free Tier", "Premium Member"])

user_tier = "Free Tier"
if user_tier_input == "Premium Member":
    secret_password = st.sidebar.text_input("Enter Premium Member Password", type="password")
    if secret_password == "VIP-MATH-2026":
        user_tier = "Premium Member (Unlocked)"
        st.sidebar.success("Premium Features Unlocked!")
    else:
        if secret_password:
            st.sidebar.error("Invalid Password")
        user_tier = "Free Tier"

user_bankroll = st.sidebar.number_input("Your Account Balance (any currency)", min_value=10.0, value=1000.0, step=10.0)

# 2. DATA INGESTION: Massive Comprehensive Global & National Directory
st.header("1. Select Live Global Feed")
API_KEY = st.text_input("Enter Your Free The Odds API Key", value="45abb5e26fb108e9a81ca9570df8666d", type="password")

global_leagues_directory = {
    "International - FIFA World Cup": "soccer_fifa_world_cup",
    "International - UEFA Nations League": "soccer_uefa_nations_league",
    "International - Africa Cup of Nations (AFCON)": "soccer_afcon",
    "International Clubs - UEFA Champions League": "soccer_uefa_champs_league",
    "International Clubs - UEFA Europa League": "soccer_uefa_europa_league",
    "England - Premier League": "soccer_epl",
    "England - EFL Championship": "soccer_efl_champ",
    "South Africa - Premier Soccer League": "soccer_spl",
    "Spain - La Liga": "soccer_spain_la_liga",
    "Germany - Bundesliga": "soccer_germany_bundesliga",
    "Italy - Serie A": "soccer_italy_serie_a",
    "France - Ligue 1": "soccer_france_ligue_one",
    "Portugal - Primeira Liga": "soccer_portugal_primeira_liga",
    "Netherlands - Eredivisie": "soccer_netherlands_eredivisie",
    "USA - Major League Soccer (MLS)": "soccer_usa_mls",
    "Australia - A-League": "soccer_australia_aleague",
    "Brazil - Serie A": "soccer_brazil_campeonato",
    "Mexico - Liga MX": "soccer_mexico_ligamx",
    "Albania - Superliga": "soccer_albania",
    "Algeria - Ligue 1": "soccer_algeria",
    "Argentina - Primera Division": "soccer_argentina_primer_division",
    "Austria - Bundesliga": "soccer_austria_bundesliga",
    "Azerbaijan - Premier League": "soccer_azerbaijan",
    "Belarus - Premier League": "soccer_belarus",
    "Belgium - Pro League": "soccer_belgium_first_div",
    "Bhutan - Premier League": "soccer_bhutan",
    "Bolivia - Primera Division": "soccer_bolivia",
    "Bosnia and Herzegovina - Premier League": "soccer_bosnia",
    "Bulgaria - First League": "soccer_bulgaria",
    "Burkina Faso - Premier League": "soccer_burkina_faso",
    "Burundi - Premier League": "soccer_burundi",
    "Cambodia - Premier League": "soccer_cambodia",
    "Canada - Premier League": "soccer_canada_cpl",
    "Chile - Primera Division": "soccer_chile",
    "China - Super League": "soccer_china_superleague",
    "Colombia - Primera A": "soccer_colombia",
    "Costa Rica - Primera Division": "soccer_costarica",
    "Croatia - HNL": "soccer_croatia",
    "Cyprus - First Division": "soccer_cyprus",
    "Czechia - First League": "soccer_czech",
    "Denmark - Superliga": "soccer_denmark_superliga",
    "Ecuador - Serie A": "soccer_ecuador",
    "Egypt - Premier League": "soccer_egypt",
    "El Salvador - Primera Division": "soccer_elsalvador",
    "Estonia - Meistriliiga": "soccer_estonia",
    "Finland - Veikkausliiga": "soccer_finland_veikkausliiga",
    "Georgia - Erovnuli Liga": "soccer_georgia",
    "Gibraltar - National League": "soccer_gibraltar",
    "Greece - Super League": "soccer_greece",
    "Guatemala - Liga Nacional": "soccer_guatemala",
    "Honduras - Liga Nacional": "soccer_honduras",
    "Hong Kong - Premier League": "soccer_hongkong",
    "Hungary - NB I": "soccer_hungary",
    "Iceland - Besta deildin": "soccer_iceland",
    "India - Super League": "soccer_india_super_league",
    "Indonesia - Liga 1": "soccer_indonesia",
    "Iran - Pro League": "soccer_iran",
    "Ireland - Premier Division": "soccer_ireland_premier_division",
    "Israel - Premier League": "soccer_israel",
    "Ivory Coast - Ligue 1": "soccer_ivory_coast",
    "Jamaica - Premier League": "soccer_jamaica",
    "Japan - J1 League": "soccer_japan_j_league",
    "Kazakhstan - Premier League": "soccer_kazakhstan",
    "Kenya - Premier League": "soccer_kenya",
    "Latvia - Virsliga": "soccer_latvia",
    "Lithuania - A Lyga": "soccer_lithuania",
    "Luxembourg - National Division": "soccer_luxembourg",
    "Malawi - Super League": "soccer_malawi",
    "Malta - Premier League": "soccer_malta",
    "Moldova - Super Liga": "soccer_moldova",
    "Mongolia - Premier League": "soccer_mongolia",
    "Montenegro - First League": "soccer_montenegro",
    "Morocco - Botola": "soccer_morocco",
    "Myanmar - National League": "soccer_myanmar",
    "New Zealand - National League": "soccer_newzealand",
    "North Macedonia - First League": "soccer_north_macedonia",
    "Northern Ireland - Premiership": "soccer_northern_ireland",
    "Norway - Eliteserien": "soccer_norway_eliteserien",
    "Panama - Liga Panamena": "soccer_panama",
    "Paraguay - Primera Division": "soccer_paraguay",
    "Peru - Liga 1": "soccer_peru",
    "Philippines - Football League": "soccer_philippines",
    "Poland - Ekstraklasa": "soccer_poland_ekstraklasa",
    "Qatar - Stars League": "soccer_qatar",
    "Republic of Korea - K League 1": "soccer_korea_kleague1",
    "Romania - Liga I": "soccer_romania",
    "Russia - Premier League": "soccer_russia",
    "Rwanda - Premier League": "soccer_rwanda",
    "Saudi Arabia - Pro League": "soccer_saudi_arabia_pro_league",
    "Scotland - Premiership": "soccer_scotland_premiership",
    "Senegal - Premier League": "soccer_senegal",
    "Serbia - SuperLiga": "soccer_serbia",
    "Singapore - Premier League": "soccer_singapore",
    "Slovakia - Super Liga": "soccer_slovakia",
    "Slovenia - PrvaLiga": "soccer_slovenia",
    "Sweden - Allsvenskan": "soccer_sweden_allsvenskan",
    "Switzerland - Super League": "soccer_switzerland_superleague",
    "Tanzania - Premier League": "soccer_tanzania",
    "Thailand - Thai League 1": "soccer_thailand",
    "Turkiye - Super Lig": "soccer_turkey_super_lig",
    "Ukraine - Premier League": "soccer_ukraine",
    "United Arab Emirates - Pro League": "soccer_uae",
    "Uruguay - Primera Division": "soccer_uruguay",
    "Uzbekistan - Super League": "soccer_uzbekistan",
    "Venezuela - Primera Division": "soccer_venezuela",
    "Vietnam - V.League 1": "soccer_vietnam",
    "Wales - Premier League": "soccer_wales",
    "Zambia - Super League": "soccer_zambia",
    "Zanzibar - Premier League": "soccer_zanzibar"
}

selected_league_name = st.selectbox("Choose Competition Venue", list(global_leagues_directory.keys()))
selected_sport_key = global_leagues_directory[selected_league_name]

# 3. INTERACTIVE LIVE FIXTURE LOADER
st.header("2. Choose Active Live Fixture")
bookie_odds = 2.00
home_team = ""
away_team = ""

if API_KEY:
    url = f"https://the-odds-api.com{selected_sport_key}/odds/?apiKey={API_KEY}&regions=uk,eu,us,au&markets=h2h&oddsFormat=decimal"
    try:
        res = requests.get(url)
        live_matches = []
        if res.status_code == 200:
            live_matches = res.json()
            
        if len(live_matches) == 0:
            st.info("Live API matches resting for this layout. Running Simulated Value Engine:")
            
            demo_fixtures = {
                "Global - FIFA World Cup and Qualifiers": {"home": "Brazil", "away": "Argentina", "odds": 2.10},
                "Europe - UEFA Nations League": {"home": "France", "away": "England", "odds": 2.35},
                "Africa - Africa Cup of Nations (AFCON)": {"home": "South Africa", "away": "Nigeria", "odds": 2.60},
                "England - Premier League": {"home": "Manchester City", "away": "Arsenal", "odds": 2.25},
                "South Africa - Premier Soccer League": {"home": "Mamelodi Sundowns", "away": "Orlando Pirates", "odds": 1.95},
                "Europe - UEFA Champions League": {"home": "Real Madrid", "away": "Bayern Munich", "odds": 2.15}
            }
            
            default_fixture = demo_fixtures.get(selected_league_name, {"home": "Home Selection", "away": "Away Selection", "odds": 2.00})
            home_team = default_fixture["home"]
            away_team = default_fixture["away"]
            bookie_odds = default_fixture["odds"]
            
            st.warning(f"Simulated Match Active: {home_team} vs {away_team} (Live Bookmaker Benchmark Odds: {bookie_odds})")
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
            
