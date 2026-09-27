import streamlit as st
import scipy.stats as stats
import requests

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------

st.set_page_config(
    page_title="Universal Football Analytics and Live Value Engine",
    layout="centered"
)

st.title("Universal Football Analytics and Live Value Engine")
st.markdown("---")

# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

st.sidebar.header("Subscription and Wallet Settings")

user_tier_input = st.sidebar.selectbox(
    "Your Account Plan",
    ["Free Tier", "Premium Member"]
)

user_tier = "Free Tier"

if user_tier_input == "Premium Member":
    secret_password = st.sidebar.text_input(
        "Enter Premium Member Password",
        type="password"
    )

    if secret_password == "VIP-MATH-2026":
        user_tier = "Premium Member (Unlocked)"
        st.sidebar.success("Premium Features Unlocked!")
    elif secret_password:
        st.sidebar.error("Invalid Password")

user_bankroll = st.sidebar.number_input(
    "Your Account Balance",
    min_value=10.0,
    value=1000.0,
    step=10.0
)

# --------------------------------------------------
# LEAGUES
# --------------------------------------------------

st.header("1. Select Live Global Feed")

API_KEY = st.text_input(
    "Enter Your The Odds API Key",
    type="password"
)

global_leagues_directory = {
    "International - FIFA World Cup": "soccer_fifa_world_cup",
    "International - UEFA Nations League": "soccer_uefa_nations_league",
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
    "USA - MLS": "soccer_usa_mls",
    "Australia - A-League": "soccer_australia_aleague",
    "Brazil - Serie A": "soccer_brazil_campeonato",
    "Mexico - Liga MX": "soccer_mexico_ligamx"
}

selected_league_name = st.selectbox(
    "Choose Competition Venue",
    list(global_leagues_directory.keys())
)

selected_sport_key = global_leagues_directory[selected_league_name]

# --------------------------------------------------
# FIXTURE LOADER
# --------------------------------------------------

st.header("2. Choose Active Live Fixture")

home_team = ""
away_team = ""
bookie_odds = 2.00
live_matches = []

if API_KEY:

    url = (
        f"https://api.the-odds-api.com/v4/sports/"
        f"{selected_sport_key}/odds/"
        f"?apiKey={API_KEY}"
        f"&regions=uk,eu,us,au"
        f"&markets=h2h"
        f"&oddsFormat=decimal"
    )

    try:
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            live_matches = response.json()
        else:
            st.warning(
                f"API returned status code {response.status_code}."
            )

    except Exception as e:
        st.warning(
            f"API connection problem: {e}"
        )

# --------------------------------------------------
# DEMO FIXTURES
# --------------------------------------------------

if len(live_matches) == 0:

    st.info(
        "No live fixtures detected. Running demo value engine."
    )

    demo_fixtures = {
        "International - FIFA World Cup": {
            "home": "Brazil",
            "away": "Argentina",
            "odds": 2.10
        },
        "International - UEFA Nations League": {
            "home": "France",
            "away": "England",
            "odds": 2.35
        },
        "England - Premier League": {
            "home": "Manchester City",
            "away": "Arsenal",
            "odds": 2.25
        },
        "South Africa - Premier Soccer League": {
            "home": "Mamelodi Sundowns",
            "away": "Orlando Pirates",
            "odds": 1.95
        },
        "International Clubs - UEFA Champions League": {
            "home": "Real Madrid",
            "away": "Bayern Munich",
            "odds": 2.15
        }
    }

    fixture = demo_fixtures.get(
        selected_league_name,
        {
            "home": "Home Team",
            "away": "Away Team",
            "odds": 2.00
        }
    )

    home_team = fixture["home"]
    away_team = fixture["away"]
    bookie_odds = fixture["odds"]

    st.warning(
        f"Simulated Match: {home_team} vs {away_team}"
    )

else:

    match_options = {}

    for match in live_matches:
        label = (
            f"{match['home_team']} vs "
            f"{match['away_team']}"
        )
        match_options[label] = match

    selected_match_label = st.selectbox(
        "Select Upcoming Match",
        list(match_options.keys())
    )

    target_match = match_options[selected_match_label]

    home_team = target_match["home_team"]
    away_team = target_match["away_team"]

    odds_list = []

    for bookmaker in target_match.get("bookmakers", []):
        for market in bookmaker.get("markets", []):

            if market["key"] == "h2h":

                for outcome in market["outcomes"\]:

                    if outcome["name"] == home_team:
                        odds_list.append(
                            float(outcome["price"])
                        )

    bookie_odds = max(odds_list) if odds_list else 2.00

    st.success(
        f"Live Feed Ready. Best odds for "
        f"{home_team}: {bookie_odds}"
    )

# --------------------------------------------------
# MATCH CONDITIONS
# --------------------------------------------------

st.header("3. Configuration Conditions")

col1, col2, col3 = st.columns(3)

with col1:
    is_derby = st.checkbox(
        "High-Intensity Rivalry"
    )

with col2:
    home_fatigue = st.checkbox(
        f"{home_team} Fatigue"
    )

with col3:
    away_fatigue = st.checkbox(
        f"{away_team} Fatigue"
    )

# --------------------------------------------------
# POISSON MODEL
# --------------------------------------------------

base_home_xg = (
    1.45
    * (0.85 if is_derby else 1.0)
    * (0.90 if home_fatigue else 1.0)
)

base_away_xg = (
    1.20
    * (1.15 if is_derby else 10)
    * (0.90 if away_fatigue else 1.0)
)

prob_home = 0.0
prob_draw = 0.0
prob_away = 0.0
prob_btts = 0.0
prob_over25 = 0.0

max_goals = 7

for h in range(max_goals):
    for a in range(max_goals):

        p_h = stats.poisson.pmf(h, base_home_xg)
        p_a = stats.poisson.pmf(a, base_away_xg)

        joint_prob = p_h * p_a

        if h > a:
            prob_home += joint_prob
        elif h == a:
            prob_draw += joint_prob
        else:
            prob_away += joint_prob

        if h > 0 and a > 0:
            prob_btts += joint_prob

        if h + a > 2:
            prob_over25 += joint_prob

fair_home_odds = (
    1 / prob_home if prob_home > 0 else 999.0
)

is_worth_it = bookie_odds > fair_home_odds

# --------------------------------------------------
# RESULTS
# --------------------------------------------------

st.header("4. Value Assessment Output")

if is_worth_it:
    st.success(
        "VERDICT: WORTH IT! Mathematical edge detected."
    )
else:
    st.error(
        "VERDICT: NOT WORTH IT! No clear value edge."
    )

c1, c2, c3 = st.columns(3)

c1.metric(
    "Win Probability",
    f"{prob_home * 100:.1f}%"
)

c2.metric(
    "Fair Odds",
    f"{fair_home_odds:.2f}"
)

edge = (
    ((bookie_odds / fair_home_odds) - 1) * 100
    if fair_home_odds > 0
    else 0
)

c3.metric(
    "Value Edge",
    f"{edge:.1f}%"
)

# --------------------------------------------------
# PREMIUM SECTION
# --------------------------------------------------

st.header("Premium Statistical Predictions")

if user_tier == "Free Tier":

    st.warning(
        "Correct Score, BTTS probabilities and Kelly staking are locked."
    )

    st.info(
        "Upgrade to Premium for advanced analytics."
    )

else:

    st.subheader(
        "Premium Engine Dashboard"
    )

    b = bookie_odds - 1

    raw_kelly = (
        ((prob_home * bookie_odds) - 1) / b
        if b > 0
        else 0
    )

    kelly_pct = max(0.0, raw_kelly * 0.25)

    p1, p2 = st.columns(2)

    p1.metric(
        "Kelly %",
        f"{kelly_pct * 100:.2f}%"
    )

    p2.metric(
        "Recommended Stake",
        f"{user_bankroll * kelly_pct:.2f}"
    )

    st.write(
        f"BTTS Probability: "
        f"{prob_btts * 100:.1f}%"
    )

    st.write(
        f"Over 2.5 Goals Probability: "
        f"{prob_over25 * 100:.1f}%"
    )

# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.markdown("---")

st.caption(
    "Legal Disclaimer: This application provides "
    "mathematical modelling and probability estimates. "
    "It is not financial advice and does not guarantee outcomes."
)
