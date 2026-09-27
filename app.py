import os
import math
import sqlite3
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
import streamlit as st
from scipy.stats import poisson


# ============================================================
# FOOTBALL INTELLIGENCE PLATFORM v5.0
# Data -> Ratings -> Probabilities -> Value -> Archive -> Results
# ============================================================

st.set_page_config(
    page_title="Football Intelligence Platform v5.0",
    page_icon="⚽",
    layout="wide",
)

DB_PATH = os.getenv("FOOTBALL_DB_PATH", "football_intelligence.db")

ODDS_BASE = "https://api.the-odds-api.com/v4"


# ============================================================
# COMPETITIONS
# ============================================================

LEAGUES = {
    "Premier League": "soccer_epl",
    "Champions League": "soccer_uefa_champs_league",
    "UEFA Nations League": "soccer_uefa_nations_league",
    "La Liga": "soccer_spain_la_liga",
    "Bundesliga": "soccer_germany_bundesliga",
    "Serie A": "soccer_italy_serie_a",
    "Ligue 1": "soccer_france_ligue_one",
    "Eredivisie": "soccer_netherlands_eredivisie",
    "MLS": "soccer_usa_mls",
    "Brazil Serie A": "soccer_brazil_campeonato",
    "Mexico Liga MX": "soccer_mexico_ligamx",
    "South Africa PSL": "soccer_spl",
    "AFCON": "soccer_afcon",
    "Egypt Premier League": "soccer_egyptian_premier_league",
    "Morocco Botola": "soccer_morocco_botola",
    "Nigeria NPFL": "soccer_nigeria_npfl",
    "Ghana Premier League": "soccer_ghana_npfl",
    "Kenya Premier League": "soccer_kenya_premier_league",
    "Tanzania Premier League": "soccer_tanzania_premier_league",
    "Zambia Super League": "soccer_zambia_super_league",
    "DR Congo Linafoot": "soccer_congo_dr_linafoot",
}


# ============================================================
# CSV COLUMN SUPPORT
# ============================================================

COLUMN_ALIASES = {
    "date": [
        "date",
        "Date",
        "match_date",
        "MatchDate",
    ],
    "home_team": [
        "home_team",
        "HomeTeam",
        "home",
        "Home",
    ],
    "away_team": [
        "away_team",
        "AwayTeam",
        "away",
        "Away",
    ],
    "home_goals": [
        "home_goals",
        "FTHG",
        "HG",
        "home_score",
        "HomeGoals",
    ],
    "away_goals": [
        "away_goals",
        "FTAG",
        "AG",
        "away_score",
        "AwayGoals",
    ],
    "league": [
        "league",
        "League",
        "competition",
        "Competition",
    ],
    "home_odds": [
        "home_odds",
        "B365H",
        "AvgH",
        "MaxH",
        "home_price",
    ],
    "draw_odds": [
        "draw_odds",
        "B365D",
        "AvgD",
        "MaxD",
        "draw_price",
    ],
    "away_odds": [
        "away_odds",
        "B365A",
        "AvgA",
        "MaxA",
        "away_price",
    ],
}


# ============================================================
# GENERAL HELPERS
# ============================================================

def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_team(name):
    if not isinstance(name, str):
        return ""

    return " ".join(name.strip().split())


def get_api_key():
    """
    Priority:
    1. Streamlit Secrets
    2. Environment variable
    """

    try:
        secret_key = st.secrets.get("ODDS_API_KEY", "")
    except Exception:
        secret_key = ""

    return secret_key or os.getenv("ODDS_API_KEY", "")


@st.cache_resource
def get_connection():
    conn = sqlite3.connect(
        DB_PATH,
        check_same_thread=False,
    )

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    init_db(conn)

    return conn


def init_db(conn):

    conn.executescript(
        """

        CREATE TABLE IF NOT EXISTS historical_matches (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            match_date TEXT NOT NULL,

            league TEXT NOT NULL DEFAULT '',

            home_team TEXT NOT NULL,

            away_team TEXT NOT NULL,

            home_goals INTEGER NOT NULL,

            away_goals INTEGER NOT NULL,

            home_odds REAL,

            draw_odds REAL,

            away_odds REAL,

            source TEXT NOT NULL DEFAULT 'manual',

            created_at TEXT NOT NULL,

            UNIQUE(
                match_date,
                league,
                home_team,
                away_team
            )
        );


        CREATE TABLE IF NOT EXISTS predictions (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            event_id TEXT,

            created_at TEXT NOT NULL,

            commence_time TEXT,

            league TEXT,

            home_team TEXT,

            away_team TEXT,

            prediction TEXT,

            market TEXT NOT NULL DEFAULT '1X2',

            confidence REAL,

            verdict TEXT,

            model_probability REAL,

            implied_probability REAL,

            edge REAL,

            odds REAL,

            expected_value REAL,

            home_xg REAL,

            away_xg REAL,

            home_elo REAL,

            away_elo REAL,

            form_home REAL,

            form_away REAL,

            status TEXT NOT NULL DEFAULT 'PENDING',

            actual_result TEXT,

            home_goals INTEGER,

            away_goals INTEGER,

            profit_loss REAL
        );


        CREATE INDEX IF NOT EXISTS idx_predictions_event
        ON predictions(event_id);


        CREATE INDEX IF NOT EXISTS idx_predictions_status
        ON predictions(status);


        CREATE INDEX IF NOT EXISTS idx_history_teams
        ON historical_matches(home_team, away_team);


        CREATE INDEX IF NOT EXISTS idx_history_date
        ON historical_matches(match_date);


        CREATE TABLE IF NOT EXISTS team_ratings (

            team TEXT PRIMARY KEY,

            elo REAL NOT NULL DEFAULT 1500,

            attack REAL NOT NULL DEFAULT 1.35,

            defence REAL NOT NULL DEFAULT 1.35,

            matches INTEGER NOT NULL DEFAULT 0,

            updated_at TEXT NOT NULL
        );

        """
    )

    conn.commit()


def qdf(conn, sql, params=()):
    return pd.read_sql_query(
        sql,
        conn,
        params=params,
    )


def scalar(
    conn,
    sql,
    params=(),
    default=0,
):

    row = conn.execute(
        sql,
        params,
    ).fetchone()

    if row is None or row[0] is None:
        return default

    return row[0]


# ============================================================
# HISTORICAL CSV
# ============================================================

def find_column(df, aliases):

    lower = {
        str(c).strip().lower(): c
        for c in df.columns
    }

    for alias in aliases:

        if alias.lower() in lower:
            return lower[alias.lower()]

    return None


def prepare_history_csv(
    uploaded_file,
    default_league,
):

    raw = pd.read_csv(uploaded_file)

    mapped = {}

    for key, aliases in COLUMN_ALIASES.items():

        col = find_column(
            raw,
            aliases,
        )

        if col:
            mapped[key] = col

    required = [
        "date",
        "home_team",
        "away_team",
        "home_goals",
        "away_goals",
    ]

    missing = [
        x
        for x in required
        if x not in mapped
    ]

    if missing:

        raise ValueError(
            "CSV is missing required columns: "
            + ", ".join(missing)
            + ". Supported examples: "
            + "Date, HomeTeam, AwayTeam, FTHG, FTAG."
        )

    out = pd.DataFrame()

    out["match_date"] = pd.to_datetime(
        raw[mapped["date"]],
        dayfirst=True,
        errors="coerce",
    )

    out["home_team"] = raw[
        mapped["home_team"]
    ].map(normalize_team)

    out["away_team"] = raw[
        mapped["away_team"]
    ].map(normalize_team)

    out["home_goals"] = pd.to_numeric(
        raw[mapped["home_goals"]],
        errors="coerce",
    )

    out["away_goals"] = pd.to_numeric(
        raw[mapped["away_goals"]],
        errors="coerce",
    )

    if "league" in mapped:

        out["league"] = (
            raw[mapped["league"]]
            .fillna("")
            .astype(str)
        )

    else:

        out["league"] = default_league

    for key in [
        "home_odds",
        "draw_odds",
        "away_odds",
    ]:

        if key in mapped:

            out[key] = pd.to_numeric(
                raw[mapped[key]],
                errors="coerce",
            )

        else:

            out[key] = np.nan

    out = out.dropna(
        subset=[
            "match_date",
            "home_team",
            "away_team",
            "home_goals",
            "away_goals",
        ]
    )

    out["home_goals"] = out[
        "home_goals"
    ].astype(int)

    out["away_goals"] = out[
        "away_goals"
    ].astype(int)

    out["match_date"] = (
        out["match_date"]
        .dt.strftime("%Y-%m-%d")
    )

    out = out[
        out["home_team"] != ""
    ]

    out = out[
        out["away_team"] != ""
    ]

    return out


def import_history(
    conn,
    df,
    source="CSV",
):

    inserted = 0
    skipped = 0

    for _, r in df.iterrows():

        try:

            conn.execute(
                """

                INSERT OR IGNORE INTO historical_matches

                (
                    match_date,
                    league,
                    home_team,
                    away_team,
                    home_goals,
                    away_goals,
                    home_odds,
                    draw_odds,
                    away_odds,
                    source,
                    created_at
                )

                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

                """,
                (
                    str(r["match_date"]),
                    str(r["league"]),
                    normalize_team(
                        r["home_team"]
                    ),
                    normalize_team(
                        r["away_team"]
                    ),
                    int(r["home_goals"]),
                    int(r["away_goals"]),
                    None
                    if pd.isna(r["home_odds"])
                    else float(r["home_odds"]),
                    None
                    if pd.isna(r["draw_odds"])
                    else float(r["draw_odds"]),
                    None
                    if pd.isna(r["away_odds"])
                    else float(r["away_odds"]),
                    source,
                    utc_now(),
                ),
            )

            changed = conn.execute(
                "SELECT changes()"
            ).fetchone()[0]

            if changed:
                inserted += 1
            else:
                skipped += 1

        except Exception:
            skipped += 1

    conn.commit()

    return inserted, skipped


# ============================================================
# HISTORICAL TEAM DATA
# ============================================================

def get_team_matches(
    conn,
    team,
    before_date=None,
    limit=20,
):

    if before_date:

        return qdf(
            conn,
            """
            SELECT *
            FROM historical_matches

            WHERE
                (
                    home_team = ?
                    OR away_team = ?
                )
                AND match_date < ?

            ORDER BY match_date DESC

            LIMIT ?
            """,
            (
                team,
                team,
                before_date,
                limit,
            ),
        )

    return qdf(
        conn,
        """
        SELECT *
        FROM historical_matches

        WHERE
            home_team = ?
            OR away_team = ?

        ORDER BY match_date DESC

        LIMIT ?
        """,
        (
            team,
            team,
            limit,
        ),
    )


def result_for_team(
    row,
    team,
):

    hg = int(row.home_goals)
    ag = int(row.away_goals)

    if row.home_team == team:

        gf = hg
        ga = ag

    else:

        gf = ag
        ga = hg

    if gf > ga:
        points = 3

    elif gf == ga:
        points = 1

    else:
        points = 0

    return gf, ga, points


def form_score(
    conn,
    team,
    before_date=None,
    n=10,
):

    matches = get_team_matches(
        conn,
        team,
        before_date,
        n,
    )

    if matches.empty:

        return (
            0.50,
            0.0,
            0.0,
            0,
        )

    points = 0
    gf = 0
    ga = 0

    for _, row in matches.iterrows():

        x, y, p = result_for_team(
            row,
            team,
        )

        gf += x
        ga += y
        points += p

    return (
        points / (3 * len(matches)),
        gf / len(matches),
        ga / len(matches),
        len(matches),
    )


# ============================================================
# ELO
# ============================================================

def get_elo(
    conn,
    team,
):

    row = conn.execute(
        """
        SELECT elo
        FROM team_ratings
        WHERE team = ?
        """,
        (team,),
    ).fetchone()

    if row:
        return float(row[0])

    return 1500.0


def rebuild_elo(
    conn,
    k_factor=20,
    home_advantage=55,
):

    matches = qdf(
        conn,
        """
        SELECT *
        FROM historical_matches

        ORDER BY
            match_date ASC,
            id ASC
        """,
    )

    ratings = {}
    counts = {}

    for _, r in matches.iterrows():

        home = normalize_team(
            r.home_team
        )

        away = normalize_team(
            r.away_team
        )

        ratings.setdefault(
            home,
            1500.0,
        )

        ratings.setdefault(
            away,
            1500.0,
        )

        counts.setdefault(
            home,
            0,
        )

        counts.setdefault(
            away,
            0,
        )

        rh = (
            ratings[home]
            + home_advantage
        )

        ra = ratings[away]

        expected_home = (
            1
            /
            (
                1
                +
                10
                **
                (
                    (ra - rh)
                    /
                    400
                )
            )
        )

        if r.home_goals > r.away_goals:

            actual_home = 1.0

        elif r.home_goals == r.away_goals:

            actual_home = 0.5

        else:

            actual_home = 0.0

        margin = abs(
            int(r.home_goals)
            -
            int(r.away_goals)
        )

        multiplier = (
            math.log(margin + 1) + 1
            if margin
            else 1
        )

        delta = (
            k_factor
            * multiplier
            * (
                actual_home
                -
                expected_home
            )
        )

        ratings[home] += delta
        ratings[away] -= delta

        counts[home] += 1
        counts[away] += 1

    conn.execute(
        "DELETE FROM team_ratings"
    )

    now = utc_now()

    for team, elo in ratings.items():

        conn.execute(
            """

            INSERT INTO team_ratings

            (
                team,
                elo,
                attack,
                defence,
                matches,
                updated_at
            )

            VALUES (?, ?, ?, ?, ?, ?)

            """,
            (
                team,
                elo,
                1.35,
                1.35,
                counts.get(team, 0),
                now,
            ),
        )

    conn.commit()

    return (
        len(ratings),
        len(matches),
    )


# ============================================================
# ATTACK / DEFENCE
# ============================================================

def attack_defence(
    conn,
    team,
    before_date=None,
    n=20,
):

    matches = get_team_matches(
        conn,
        team,
        before_date,
        n,
    )

    if matches.empty:

        return (
            1.35,
            1.35,
            0,
        )

    gf = 0
    ga = 0
    games = 0

    for _, row in matches.iterrows():

        x, y, _ = result_for_team(
            row,
            team,
        )

        gf += x
        ga += y
        games += 1

    league_average = scalar(
        conn,
        """
        SELECT
            AVG(home_goals + away_goals)
            / 2.0

        FROM historical_matches
        """,
        default=1.35,
    )

    league_average = max(
        float(
            league_average
            or 1.35
        ),
        0.60,
    )

    attack = max(
        0.25,
        min(
            3.50,
            (
                gf / games
            )
            /
            league_average,
        ),
    )

    defence = max(
        0.25,
        min(
            3.50,
            (
                ga / games
            )
            /
            league_average,
        ),
    )

    return (
        attack,
        defence,
        games,
    )


# ============================================================
# MODEL INPUTS
# ============================================================

def model_inputs(
    conn,
    home,
    away,
    match_date=None,
):

    home_form, home_gf, home_ga, home_n = form_score(
        conn,
        home,
        match_date,
        10,
    )

    away_form, away_gf, away_ga, away_n = form_score(
        conn,
        away,
        match_date,
        10,
    )

    home_attack, home_defence, home_games = attack_defence(
        conn,
        home,
        match_date,
        20,
    )

    away_attack, away_defence, away_games = attack_defence(
        conn,
        away,
        match_date,
        20,
    )

    home_elo = get_elo(
        conn,
        home,
    )

    away_elo = get_elo(
        conn,
        away,
    )

    home_form_factor = (
        0.85
        +
        0.30 * home_form
    )

    away_form_factor = (
        0.85
        +
        0.30 * away_form
    )

    elo_diff = (
        home_elo
        +
        55
        -
        away_elo
    )

    elo_factor = (
        10
        **
        (
            elo_diff
            /
            400
        )
    )

    league_average = scalar(
        conn,
        """
        SELECT
            AVG(home_goals + away_goals)
            / 2.0

        FROM historical_matches
        """,
        default=1.35,
    )

    league_average = max(
        float(
            league_average
            or 1.35
        ),
        0.80,
    )

    home_sample = min(
        1.0,
        home_n / 10,
    )

    away_sample = min(
        1.0,
        away_n / 10,
    )

    home_xg = (
        league_average
        *
        math.sqrt(
            max(
                home_attack,
                0.25,
            )
            *
            max(
                1 / away_defence,
                0.25,
            )
        )
    )

    away_xg = (
        league_average
        *
        math.sqrt(
            max(
                away_attack,
                0.25,
            )
            *
            max(
                1 / home_defence,
                0.25,
            )
        )
    )

    home_xg *= home_form_factor
    away_xg *= away_form_factor

    elo_adjust = max(
        0.80,
        min(
            1.25,
            math.sqrt(
                elo_factor
            ),
        ),
    )

    home_xg *= elo_adjust
    away_xg /= elo_adjust

    neutral = league_average

    home_xg = (
        home_sample
        * home_xg
        +
        (
            1
            -
            home_sample
        )
        * neutral
        * 1.05
    )

    away_xg = (
        away_sample
        * away_xg
        +
        (
            1
            -
            away_sample
        )
        * neutral
        * 0.95
    )

    return {

        "home_xg": max(
            0.10,
            min(
                5.00,
                home_xg,
            ),
        ),

        "away_xg": max(
            0.10,
            min(
                5.00,
                away_xg,
            ),
        ),

        "home_elo": home_elo,
        "away_elo": away_elo,

        "form_home": home_form,
        "form_away": away_form,

        "home_games": home_n,
        "away_games": away_n,
    }


# ============================================================
# POISSON ENGINE
# ============================================================

def poisson_1x2(
    home_xg,
    away_xg,
    max_goals=8,
):

    home_probs = [
        poisson.pmf(
            i,
            home_xg,
        )
        for i in range(
            max_goals + 1
        )
    ]

    away_probs = [
        poisson.pmf(
            i,
            away_xg,
        )
        for i in range(
            max_goals + 1
        )
    ]

    home_win = 0.0
    draw = 0.0
    away_win = 0.0

    for h, hp in enumerate(
        home_probs
    ):

        for a, ap in enumerate(
            away_probs
        ):

            probability = (
                hp * ap
            )

            if h > a:

                home_win += probability

            elif h == a:

                draw += probability

            else:

                away_win += probability

    total = (
        home_win
        +
        draw
        +
        away_win
    )

    return (
        home_win / total,
        draw / total,
        away_win / total,
    )


# ============================================================
# MARKET MATH
# ============================================================

def implied_probability(
    odds,
):

    if (
        odds is None
        or not np.isfinite(odds)
        or odds <= 1.0
    ):

        return None

    return 1.0 / float(odds)


def confidence_score(
    probabilities,
    history_games,
    edge,
):

    top = max(
        probabilities
    )

    second = sorted(
        probabilities,
        reverse=True,
    )[1]

    separation = max(
        0.0,
        top - second,
    )

    history_factor = min(
        1.0,
        history_games / 20,
    )

    edge_factor = max(
        0.0,
        min(
            1.0,
            (
                edge + 0.05
            )
            /
            0.20,
        ),
    )

    raw = (
        55
        +
        35 * top
        +
        18 * separation
        +
        8 * history_factor
        +
        5 * edge_factor
    )

    return int(
        max(
            0,
            min(
                99,
                round(raw),
            ),
        )
    )


def verdict(
    confidence,
    edge,
):

    if edge is None:

        return "⚪ INFORMATIONAL"

    if (
        edge >= 0.08
        and confidence >= 85
    ):

        return "🔥 ELITE APPROVED"

    if (
        edge >= 0.04
        and confidence >= 75
    ):

        return "✅ APPROVED"

    if (
        edge >= 0.01
        and confidence >= 65
    ):

        return "⚠ WATCHLIST"

    return "❌ NO BET"


# ============================================================
# MATCH ANALYSIS
# ============================================================

def analyze_match(
    conn,
    event,
    league_name,
):

    home = normalize_team(
        event["home_team"]
    )

    away = normalize_team(
        event["away_team"]
    )

    inputs = model_inputs(
        conn,
        home,
        away,
    )

    ph, pd, pa = poisson_1x2(
        inputs["home_xg"],
        inputs["away_xg"],
    )

    probabilities = {

        "Home Win": ph,

        "Draw": pd,

        "Away Win": pa,
    }

    prediction = max(
        probabilities,
        key=probabilities.get,
    )

    model_probability = (
        probabilities[prediction]
    )

    odds = {

        "Home Win": None,

        "Draw": None,

        "Away Win": None,
    }

    # Use the first bookmaker that supplies
    # a complete 1X2 market.
    for bookmaker in event.get(
        "bookmakers",
        [],
    ):

        market = next(
            (
                m
                for m in bookmaker.get(
                    "markets",
                    [],
                )
                if m.get("key")
                == "h2h"
            ),
            None,
        )

        if not market:
            continue

        temporary = {
            "Home Win": None,
            "Draw": None,
            "Away Win": None,
        }

        for outcome in market.get(
            "outcomes",
            [],
        ):

            name = outcome.get(
                "name"
            )

            price = outcome.get(
                "price"
            )

            if name == home:

                temporary[
                    "Home Win"
                ] = price

            elif name == away:

                temporary[
                    "Away Win"
                ] = price

            elif name == "Draw":

                temporary[
                    "Draw"
                ] = price

        if all(
            value is not None
            for value in temporary.values()
        ):

            odds = temporary
            break

    selected_odds = odds[
        prediction
    ]

    implied = implied_probability(
        selected_odds
    )

    edge = (
        None
        if implied is None
        else
        model_probability
        -
        implied
    )

    expected_value = (
        None
        if selected_odds is None
        else
        (
            model_probability
            *
            selected_odds
        )
        -
        1.0
    )

    confidence = confidence_score(
        list(
            probabilities.values()
        ),
        inputs["home_games"]
        +
        inputs["away_games"],
        0
        if edge is None
        else edge,
    )

    return {

        "event_id":
            event.get("id"),

        "commence_time":
            event.get("commence_time"),

        "league":
            league_name,

        "home_team":
            home,

        "away_team":
            away,

        "prediction":
            prediction,

        "confidence":
            confidence,

        "verdict":
            verdict(
                confidence,
                edge,
            ),

        "home_probability":
            ph,

        "draw_probability":
            pd,

        "away_probability":
            pa,

        "model_probability":
            model_probability,

        "implied_probability":
            implied,

        "edge":
            edge,

        "odds":
            selected_odds,

        "expected_value":
            expected_value,

        **inputs,
    }


# ============================================================
# ODDS API
# ============================================================

def fetch_odds(
    api_key,
    sport_key,
):

    url = (
        f"{ODDS_BASE}"
        f"/sports/"
        f"{sport_key}"
        f"/odds/"
    )

    params = {

        "apiKey":
            api_key,

        "regions":
            "uk,eu",

        "markets":
            "h2h",

        "oddsFormat":
            "decimal",
    }

    response = requests.get(
        url,
        params=params,
        timeout=20,
    )

    if response.status_code != 200:

        raise RuntimeError(
            f"Odds API error "
            f"{response.status_code}: "
            f"{response.text[:500]}"
        )

    return (
        response.json(),
        response.headers,
    )


def fetch_scores(
    api_key,
    sport_key,
    days_from=3,
):

    url = (
        f"{ODDS_BASE}"
        f"/sports/"
        f"{sport_key}"
        f"/scores/"
    )

    params = {

        "apiKey":
            api_key,

        "daysFrom":
            days_from,
    }

    response = requests.get(
        url,
        params=params,
        timeout=20,
    )

    if response.status_code != 200:

        raise RuntimeError(
            f"Scores API error "
            f"{response.status_code}: "
            f"{response.text[:500]}"
        )

    return response.json()


# ============================================================
# PREDICTION ARCHIVE
# ============================================================

def save_prediction(
    conn,
    analysis,
):

    conn.execute(
        """

        INSERT INTO predictions

        (
            event_id,
            created_at,
            commence_time,
            league,
            home_team,
            away_team,
            prediction,
            market,
            confidence,
            verdict,
            model_probability,
            implied_probability,
            edge,
            odds,
            expected_value,
            home_xg,
            away_xg,
            home_elo,
            away_elo,
            form_home,
            form_away
        )

        VALUES
        (
            ?, ?, ?, ?, ?, ?, ?, '1X2',
            ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?
        )

        """,
        (
            analysis["event_id"],
            utc_now(),
            analysis["commence_time"],
            analysis["league"],
            analysis["home_team"],
            analysis["away_team"],
            analysis["prediction"],
            analysis["confidence"],
            analysis["verdict"],
            analysis["model_probability"],
            analysis["implied_probability"],
            analysis["edge"],
            analysis["odds"],
            analysis["expected_value"],
            analysis["home_xg"],
            analysis["away_xg"],
            analysis["home_elo"],
            analysis["away_elo"],
            analysis["form_home"],
            analysis["form_away"],
        ),
    )


# ============================================================
# RESULT SETTLEMENT
# ============================================================

def settle_predictions(
    conn,
    scores,
):

    updated = 0

    for event in scores:

        if not event.get(
            "completed"
        ):

            continue

        scores_list = (
            event.get("scores")
            or []
        )

        home_goals = None
        away_goals = None

        for score in scores_list:

            if (
                score.get("name")
                ==
                event.get(
                    "home_team"
                )
            ):

                home_goals = score.get(
                    "score"
                )

            elif (
                score.get("name")
                ==
                event.get(
                    "away_team"
                )
            ):

                away_goals = score.get(
                    "score"
                )

        if (
            home_goals is None
            or
            away_goals is None
        ):

            continue

        home_goals = int(
            home_goals
        )

        away_goals = int(
            away_goals
        )

        if home_goals > away_goals:

            actual = "Home Win"

        elif home_goals == away_goals:

            actual = "Draw"

        else:

            actual = "Away Win"

        rows = conn.execute(
            """

            SELECT
                id,
                prediction,
                odds

            FROM predictions

            WHERE
                event_id = ?
                AND status = 'PENDING'

            """,
            (
                event.get("id"),
            ),
        ).fetchall()

        for (
            prediction_id,
            prediction,
            odds,
        ) in rows:

            if (
                prediction
                ==
                actual
                and
                odds
                and
                odds > 1
            ):

                profit_loss = (
                    float(odds)
                    -
                    1.0
                )

            else:

                profit_loss = -1.0

            conn.execute(
                """

                UPDATE predictions

                SET
                    status = 'SETTLED',
                    actual_result = ?,
                    home_goals = ?,
                    away_goals = ?,
                    profit_loss = ?

                WHERE id = ?

                """,
                (
                    actual,
                    home_goals,
                    away_goals,
                    profit_loss,
                    prediction_id,
                ),
            )

            updated += 1

    conn.commit()

    return updated


# ============================================================
# PERFORMANCE
# ============================================================

def prediction_metrics(
    conn,
):

    df = qdf(
        conn,
        """

        SELECT *

        FROM predictions

        WHERE
            status = 'SETTLED'

        ORDER BY
            created_at DESC

        """,
    )

    if df.empty:

        return (
            {
                "count": 0,
                "wins": 0,
                "accuracy": 0,
                "roi": 0,
                "profit": 0,
                "avg_confidence": 0,
            },
            df,
        )

    wins = int(
        (
            df["prediction"]
            ==
            df["actual_result"]
        ).sum()
    )

    profit = float(
        df["profit_loss"].sum()
    )

    count = len(df)

    return (
        {
            "count":
                count,

            "wins":
                wins,

            "accuracy":
                wins / count,

            "roi":
                profit / count,

            "profit":
                profit,

            "avg_confidence":
                float(
                    df[
                        "confidence"
                    ].mean()
                ),
        },
        df,
    )


# ============================================================
# APPLICATION
# ============================================================

st.title(
    "⚽ Football Intelligence Platform v5.0"
)

st.caption(
    "Historical Data • Form • Elo • Poisson • "
    "Market Value • Prediction Archive • "
    "Result Settlement • Calibration"
)

conn = get_connection()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header(
        "Platform Settings"
    )

    api_key = st.text_input(
        "Odds API Key",
        value=get_api_key(),
        type="password",
        help=(
            "Prefer Streamlit Secrets or "
            "the ODDS_API_KEY environment variable."
        ),
    )

    league_name = st.selectbox(
        "Competition",
        list(LEAGUES.keys()),
    )

    sport_key = LEAGUES[
        league_name
    ]

    st.divider()

    st.subheader(
        "Historical Data"
    )

    uploaded = st.file_uploader(
        "Upload historical CSV",
        type=["csv"],
        help=(
            "Football-Data style files "
            "such as Date, HomeTeam, AwayTeam, "
            "FTHG and FTAG are supported."
        ),
    )

    if uploaded is not None:

        if st.button(
            "Import Historical CSV",
            use_container_width=True,
        ):

            try:

                history = prepare_history_csv(
                    uploaded,
                    league_name,
                )

                inserted, skipped = import_history(
                    conn,
                    history,
                    source=uploaded.name,
                )

                teams, games = rebuild_elo(
                    conn
                )

                st.success(
                    f"Imported {inserted} matches; "
                    f"skipped {skipped}. "
                    f"Elo rebuilt for {teams} "
                    f"teams across {games} matches."
                )

            except Exception as e:

                st.error(
                    str(e)
                )

    if st.button(
        "Rebuild Elo Ratings",
        use_container_width=True,
    ):

        teams, games = rebuild_elo(
            conn
        )

        st.success(
            f"Elo rebuilt: "
            f"{teams} teams / "
            f"{games} matches."
        )

    st.divider()

    st.subheader(
        "Data Controls"
    )

    history_count = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM historical_matches
            """,
        )
    )

    prediction_count = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM predictions
            """,
        )
    )

    team_count = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM team_ratings
            """,
        )
    )

    st.metric(
        "Historical Matches",
        f"{history_count:,}",
    )

    st.metric(
        "Predictions Archived",
        f"{prediction_count:,}",
    )

    st.metric(
        "Teams Rated",
        f"{team_count:,}",
    )

    if st.button(
        "Refresh App",
        use_container_width=True,
    ):

        st.rerun()


# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "🔎 Live Intelligence",
        "📚 Historical Data",
        "🧠 Ratings",
        "📈 Performance",
        "⚙️ Database",
    ]
)


# ============================================================
# LIVE INTELLIGENCE
# ============================================================

with tab1:

    if not api_key:

        st.info(
            "Enter your Odds API key in the sidebar, "
            "or configure ODDS_API_KEY in Streamlit Secrets."
        )

    else:

        col1, col2 = st.columns(
            [1, 1]
        )

        with col1:

            load_live = st.button(
                "Load Upcoming Matches",
                type="primary",
            )

        with col2:

            settle = st.button(
                "Settle Archived Predictions"
            )

        if settle:

            try:

                scores = fetch_scores(
                    api_key,
                    sport_key,
                    days_from=3,
                )

                count = settle_predictions(
                    conn,
                    scores,
                )

                st.success(
                    f"Settled {count} "
                    f"prediction(s)."
                )

            except Exception as e:

                st.error(
                    str(e)
                )

        if load_live:

            try:

                with st.spinner(
                    "Loading fixtures and bookmaker odds..."
                ):

                    events, headers = fetch_odds(
                        api_key,
                        sport_key,
                    )

                remaining = headers.get(
                    "x-requests-remaining"
                )

                if remaining:

                    st.caption(
                        "Odds API requests remaining: "
                        + str(remaining)
                    )

                analyses = []

                for event in events:

                    try:

                        analyses.append(
                            analyze_match(
                                conn,
                                event,
                                league_name,
                            )
                        )

                    except Exception as e:

                        st.warning(
                            f"Could not analyse "
                            f"{event.get('home_team')} "
                            f"vs "
                            f"{event.get('away_team')}: "
                            f"{e}"
                        )

                if not analyses:

                    st.warning(
                        "No analysable matches returned."
                    )

                else:

                    df = pd.DataFrame(
                        analyses
                    )

                    df["Edge %"] = (
                        df["edge"]
                        .fillna(0)
                        * 100
                    )

                    df["Model %"] = (
                        df[
                            "model_probability"
                        ]
                        * 100
                    )

                    df["Odds"] = df[
                        "odds"
                    ]

                    df["xG"] = (
                        df[
                            "home_xg"
                        ].round(2).astype(str)
                        +
                        " - "
                        +
                        df[
                            "away_xg"
                        ].round(2).astype(str)
                    )

                    display = df[
                        [
                            "home_team",
                            "away_team",
                            "prediction",
                            "Model %",
                            "Edge %",
                            "Odds",
                            "confidence",
                            "verdict",
                            "xG",
                        ]
                    ].copy()

                    display.columns = [
                        "Home",
                        "Away",
                        "Prediction",
                        "Model Probability %",
                        "Edge %",
                        "Odds",
                        "Confidence",
                        "Verdict",
                        "xG",
                    ]

                    display = display.sort_values(
                        [
                            "Confidence",
                            "Edge %",
                        ],
                        ascending=False,
                    )

                    st.subheader(
                        "Ranked Opportunities"
                    )

                    st.dataframe(
                        display.style.format(
                            {
                                "Model Probability %":
                                    "{:.1f}",

                                "Edge %":
                                    "{:.1f}",

                                "Odds":
                                    "{:.2f}",

                                "Confidence":
                                    "{:.0f}",
                            }
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

                    selected_index = st.selectbox(
                        "Detailed Match Analysis",
                        range(len(df)),
                        format_func=lambda i:
                            (
                                f"{df.iloc[i]['home_team']} "
                                f"vs "
                                f"{df.iloc[i]['away_team']} "
                                f"— "
                                f"{df.iloc[i]['prediction']}"
                            ),
                    )

                    analysis = df.iloc[
                        selected_index
                    ].to_dict()

                    c1, c2, c3, c4 = st.columns(
                        4
                    )

                    c1.metric(
                        "Prediction",
                        analysis[
                            "prediction"
                        ],
                    )

                    c2.metric(
                        "Confidence",
                        f"{analysis['confidence']}/99",
                    )

                    c3.metric(
                        "Model Probability",
                        (
                            f"{analysis['model_probability'] * 100:.1f}%"
                        ),
                    )

                    c4.metric(
                        "Edge",
                        (
                            "N/A"
                            if pd.isna(
                                analysis["edge"]
                            )
                            else
                            f"{analysis['edge'] * 100:.1f}%"
                        ),
                    )

                    st.write(
                        f"**Verdict:** "
                        f"{analysis['verdict']}  |  "
                        f"**Expected goals:** "
                        f"{analysis['home_xg']:.2f} "
                        f"– "
                        f"{analysis['away_xg']:.2f}"
                    )

                    detail = pd.DataFrame(
                        {
                            "Metric": [

                                "Home win probability",

                                "Draw probability",

                                "Away win probability",

                                "Home Elo",

                                "Away Elo",

                                "Home last-10 form",

                                "Away last-10 form",

                                "Selected odds",

                                "Implied probability",

                                "Expected value per 1 unit",
                            ],

                            "Value": [

                                f"{analysis['home_probability'] * 100:.2f}%",

                                f"{analysis['draw_probability'] * 100:.2f}%",

                                f"{analysis['away_probability'] * 100:.2f}%",

                                f"{analysis['home_elo']:.1f}",

                                f"{analysis['away_elo']:.1f}",

                                f"{analysis['form_home'] * 100:.1f}%",

                                f"{analysis['form_away'] * 100:.1f}%",

                                (
                                    "N/A"
                                    if pd.isna(
                                        analysis["odds"]
                                    )
                                    else
                                    f"{analysis['odds']:.2f}"
                                ),

                                (
                                    "N/A"
                                    if pd.isna(
                                        analysis[
                                            "implied_probability"
                                        ]
                                    )
                                    else
                                    f"{analysis['implied_probability'] * 100:.2f}%"
                                ),

                                (
                                    "N/A"
                                    if pd.isna(
                                        analysis[
                                            "expected_value"
                                        ]
                                    )
                                    else
                                    f"{analysis['expected_value'] * 100:.2f}%"
                                ),
                            ],
                        }
                    )

                    st.dataframe(
                        detail,
                        use_container_width=True,
                        hide_index=True,
                    )

                    if st.button(
                        "Archive All Loaded Predictions"
                    ):

                        archived = 0

                        for record in analyses:

                            exists = scalar(
                                conn,
                                """
                                SELECT COUNT(*)

                                FROM predictions

                                WHERE
                                    event_id = ?
                                """,
                                (
                                    record[
                                        "event_id"
                                    ],
                                ),
                            )

                            if exists == 0:

                                save_prediction(
                                    conn,
                                    record,
                                )

                                archived += 1

                        conn.commit()

                        st.success(
                            f"Archived {archived} "
                            f"new prediction(s)."
                        )

                        st.rerun()

            except Exception as e:

                st.error(
                    str(e)
                )


# ============================================================
# HISTORICAL DATA
# ============================================================

with tab2:

    st.subheader(
        "Historical Match Database"
    )

    history_df = qdf(
        conn,
        """

        SELECT
            match_date,
            league,
            home_team,
            away_team,
            home_goals,
            away_goals,
            source

        FROM historical_matches

        ORDER BY
            match_date DESC,
            id DESC

        LIMIT 5000

        """,
    )

    if history_df.empty:

        st.info(
            "No historical matches yet. "
            "Upload a CSV from the sidebar."
        )

    else:

        st.dataframe(
            history_df,
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# RATINGS
# ============================================================

with tab3:

    st.subheader(
        "Team Ratings"
    )

    ratings = qdf(
        conn,
        """

        SELECT
            team,
            ROUND(elo, 1) AS elo,
            matches,
            updated_at

        FROM team_ratings

        ORDER BY elo DESC

        """,
    )

    if ratings.empty:

        st.info(
            "No ratings yet. Import historical "
            "results and rebuild Elo."
        )

    else:

        st.dataframe(
            ratings,
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# PERFORMANCE
# ============================================================

with tab4:

    st.subheader(
        "Prediction Performance"
    )

    metrics, settled = prediction_metrics(
        conn
    )

    c1, c2, c3, c4, c5 = st.columns(
        5
    )

    c1.metric(
        "Settled",
        f"{metrics['count']:,}",
    )

    c2.metric(
        "Wins",
        f"{metrics['wins']:,}",
    )

    c3.metric(
        "Accuracy",
        f"{metrics['accuracy'] * 100:.1f}%",
    )

    c4.metric(
        "ROI",
        f"{metrics['roi'] * 100:.2f}%",
    )

    c5.metric(
        "Profit / Unit",
        f"{metrics['profit']:.2f}",
    )

    if not settled.empty:

        st.subheader(
            "Confidence Calibration"
        )

        settled[
            "confidence_band"
        ] = pd.cut(
            settled[
                "confidence"
            ],
            bins=[
                0,
                59,
                69,
                79,
                89,
                100,
            ],
            labels=[
                "<60",
                "60-69",
                "70-79",
                "80-89",
                "90+",
            ],
            include_lowest=True,
        )

        calibration = (
            settled
            .groupby(
                "confidence_band",
                observed=False,
            )
            .agg(
                predictions=(
                    "id",
                    "count",
                ),

                accuracy=(
                    "actual_result",
                    lambda s:
                        (
                            settled.loc[
                                s.index,
                                "prediction",
                            ]
                            ==
                            s
                        ).mean(),
                ),

                avg_confidence=(
                    "confidence",
                    "mean",
                ),

                profit=(
                    "profit_loss",
                    "sum",
                ),
            )
            .reset_index()
        )

        calibration[
            "accuracy"
        ] *= 100

        calibration[
            "ROI"
        ] = (
            calibration[
                "profit"
            ]
            /
            calibration[
                "predictions"
            ]
            *
            100
        )

        st.dataframe(
            calibration.style.format(
                {
                    "accuracy":
                        "{:.1f}%",

                    "avg_confidence":
                        "{:.1f}",

                    "profit":
                        "{:.2f}",

                    "ROI":
                        "{:.2f}%",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.subheader(
            "Settled Predictions"
        )

        st.dataframe(
            settled[
                [
                    "created_at",
                    "league",
                    "home_team",
                    "away_team",
                    "prediction",
                    "confidence",
                    "odds",
                    "actual_result",
                    "home_goals",
                    "away_goals",
                    "profit_loss",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "No settled predictions yet."
        )


# ============================================================
# DATABASE
# ============================================================

with tab5:

    st.subheader(
        "Database Administration"
    )

    st.write(
        f"Database file: `{DB_PATH}`"
    )

    tables = qdf(
        conn,
        """

        SELECT name

        FROM sqlite_master

        WHERE
            type = 'table'
            AND name NOT LIKE 'sqlite_%'

        ORDER BY name

        """,
    )

    st.dataframe(
        tables,
        use_container_width=True,
        hide_index=True,
    )

    st.warning(
        "Back up football_intelligence.db regularly. "
        "The database contains your historical data "
        "and prediction archive."
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Probabilities are model outputs, not guarantees. "
    "Historical performance does not ensure future performance. "
    "Verify data quality, fixtures, odds and results."
)
