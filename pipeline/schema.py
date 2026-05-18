import psycopg2
from config import DB_CONFIG


def create_tables():
    commands = [

        """
        CREATE TABLE IF NOT EXISTS clubs (
            club_id     SERIAL PRIMARY KEY,
            name        VARCHAR(100) NOT NULL UNIQUE,
            ws_name     VARCHAR(100),
            espn_name   VARCHAR(100),
            understat_name VARCHAR(100)
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS managers (
            manager_id  SERIAL PRIMARY KEY,
            name        VARCHAR(100) NOT NULL,
            nationality VARCHAR(100)
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS players (
            player_id       SERIAL PRIMARY KEY,
            name            VARCHAR(100) NOT NULL,
            ws_player_id    INTEGER,
            understat_id    INTEGER,
            nationality     VARCHAR(100),
            date_of_birth   DATE
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS seasons (
            season_id       SERIAL PRIMARY KEY,
            label           VARCHAR(10) NOT NULL UNIQUE,
            ws_code         VARCHAR(10),
            understat_code  VARCHAR(10),
            start_year      INTEGER NOT NULL,
            end_year        INTEGER NOT NULL
        )
        """,

        """
                CREATE TABLE IF NOT EXISTS appointments (
                    appointment_id  SERIAL PRIMARY KEY,
                    club_id         INTEGER NOT NULL REFERENCES clubs(club_id),
                    manager_id      INTEGER NOT NULL REFERENCES managers(manager_id),
                    date_from       DATE NOT NULL,
                    date_to         DATE,
                    season_id       INTEGER REFERENCES seasons(season_id)
                )
                """,

        """
        CREATE TABLE IF NOT EXISTS matches (
            match_id        SERIAL PRIMARY KEY,
            ws_game_id      INTEGER UNIQUE,
            espn_game_id    INTEGER,
            appointment_id  INTEGER NOT NULL REFERENCES appointments(appointment_id),
            season_id       INTEGER NOT NULL REFERENCES seasons(season_id),
            opponent_id     INTEGER NOT NULL REFERENCES clubs(club_id),
            match_date      TIMESTAMP WITH TIME ZONE,
            venue           VARCHAR(10),
            home_score      INTEGER,
            away_score      INTEGER
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS match_events (
            event_id            SERIAL PRIMARY KEY,
            match_id            INTEGER NOT NULL REFERENCES matches(match_id),
            ws_event_id         INTEGER,
            player_id           INTEGER REFERENCES players(player_id),
            team_id             INTEGER NOT NULL REFERENCES clubs(club_id),
            period              VARCHAR(20),
            minute              INTEGER,
            second              FLOAT,
            expanded_minute     INTEGER,
            type                VARCHAR(50),
            outcome_type        VARCHAR(50),
            x                   FLOAT,
            y                   FLOAT,
            end_x               FLOAT,
            end_y               FLOAT,
            goal_mouth_y        FLOAT,
            goal_mouth_z        FLOAT,
            blocked_x           FLOAT,
            blocked_y           FLOAT,
            is_touch            BOOLEAN,
            is_shot             BOOLEAN,
            is_goal             BOOLEAN,
            card_type           VARCHAR(20),
            related_event_id    INTEGER,
            related_player_id   INTEGER,
            qualifiers          JSONB
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS match_lineups (
            lineup_id           SERIAL PRIMARY KEY,
            match_id            INTEGER NOT NULL REFERENCES matches(match_id),
            player_id           INTEGER NOT NULL REFERENCES players(player_id),
            appointment_id      INTEGER NOT NULL REFERENCES appointments(appointment_id),
            is_home             BOOLEAN,
            position            VARCHAR(50),
            formation_place     INTEGER,
            sub_in              VARCHAR(10),
            sub_out             VARCHAR(10),
            fouls_committed     FLOAT,
            fouls_suffered      FLOAT,
            yellow_cards        FLOAT,
            red_cards           FLOAT,
            goals               FLOAT,
            assists             FLOAT,
            shots               FLOAT,
            shots_on_target     FLOAT,
            saves               FLOAT,
            own_goals           FLOAT,
            offsides            FLOAT
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS player_season_stats (
            stat_id         SERIAL PRIMARY KEY,
            player_id       INTEGER NOT NULL REFERENCES players(player_id),
            season_id       INTEGER NOT NULL REFERENCES seasons(season_id),
            appointment_id  INTEGER NOT NULL REFERENCES appointments(appointment_id),
            team_id         INTEGER NOT NULL REFERENCES clubs(club_id),
            matches         INTEGER,
            minutes         INTEGER,
            goals           INTEGER,
            np_goals        INTEGER,
            assists         INTEGER,
            shots           INTEGER,
            key_passes      INTEGER,
            yellow_cards    INTEGER,
            red_cards       INTEGER,
            xg              FLOAT,
            np_xg           FLOAT,
            xa              FLOAT,
            xg_chain        FLOAT,
            xg_buildup      FLOAT
        )
        """
    ]

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    for command in commands:
        cursor.execute(command)

    conn.commit()
    cursor.close()
    conn.close()
    print("Reference tables created successfully")


if __name__ == "__main__":
    create_tables()