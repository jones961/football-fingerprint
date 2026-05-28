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

def add_caretaker_column():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        ALTER TABLE appointments 
        ADD COLUMN IF NOT EXISTS is_caretaker BOOLEAN NOT NULL DEFAULT FALSE
    """)
    conn.commit()
    cursor.close()
    conn.close()
    print("is_caretaker column added successfully")


def add_match_context_table():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS match_context (
            context_id      SERIAL PRIMARY KEY,
            match_id        INTEGER NOT NULL REFERENCES matches(match_id),
            club_id         INTEGER NOT NULL REFERENCES clubs(club_id),
            appointment_id  INTEGER NOT NULL REFERENCES appointments(appointment_id),
            venue           VARCHAR(10),
            UNIQUE(match_id, club_id)
        )
    """)

    cursor.execute("""
        ALTER TABLE matches 
        DROP COLUMN IF EXISTS appointment_id,
        DROP COLUMN IF EXISTS venue
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("match_context table created, matches table updated")

def fix_match_events_constraints():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        ALTER TABLE match_events 
        ALTER COLUMN team_id DROP NOT NULL,
        ALTER COLUMN player_id DROP NOT NULL
    """)
    conn.commit()
    cursor.close()
    conn.close()
    print("match_events constraints updated")


def create_raw_tables():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS match_events")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_ws_events (
            id                  SERIAL PRIMARY KEY,
            match_id            INTEGER NOT NULL REFERENCES matches(match_id),
            ws_event_id         INTEGER,
            ws_player_id        INTEGER,
            ws_team_id          INTEGER,
            player_name         VARCHAR(100),
            team_name           VARCHAR(100),
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
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_ws_matches (
            id                  SERIAL PRIMARY KEY,
            match_id            INTEGER REFERENCES matches(match_id),
            ws_game_id          INTEGER UNIQUE,
            ws_home_team_id     INTEGER,
            ws_away_team_id     INTEGER,
            home_team           VARCHAR(100),
            away_team           VARCHAR(100),
            season_label        VARCHAR(10),
            match_date          TIMESTAMP WITH TIME ZONE,
            home_score          INTEGER,
            away_score          INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_espn_lineups (
            id                  SERIAL PRIMARY KEY,
            match_id            INTEGER REFERENCES matches(match_id),
            espn_game_id        INTEGER,
            espn_player_id      VARCHAR(50),
            player_name         VARCHAR(100),
            team_name           VARCHAR(100),
            is_home             BOOLEAN,
            position            VARCHAR(50),
            formation_place     VARCHAR(10),
            sub_in              VARCHAR(10),
            sub_out             VARCHAR(10),
            appearances         FLOAT,
            fouls_committed     FLOAT,
            fouls_suffered      FLOAT,
            own_goals           FLOAT,
            red_cards           FLOAT,
            sub_ins             FLOAT,
            yellow_cards        FLOAT,
            goals_conceded      FLOAT,
            saves               FLOAT,
            shots_faced         FLOAT,
            goal_assists        FLOAT,
            shots_on_target     FLOAT,
            total_goals         FLOAT,
            total_shots         FLOAT,
            offsides            FLOAT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_understat_player_stats (
            id                  SERIAL PRIMARY KEY,
            season_label        VARCHAR(10),
            team_name           VARCHAR(100),
            player_name         VARCHAR(100),
            understat_player_id INTEGER,
            understat_team_id   INTEGER,
            position            VARCHAR(20),
            matches             INTEGER,
            minutes             INTEGER,
            goals               INTEGER,
            np_goals            INTEGER,
            assists             INTEGER,
            shots               INTEGER,
            key_passes          INTEGER,
            yellow_cards        INTEGER,
            red_cards           INTEGER,
            xg                  FLOAT,
            np_xg               FLOAT,
            xa                  FLOAT,
            xg_chain            FLOAT,
            xg_buildup          FLOAT
        )
    """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS raw_espn_matches (
                id              SERIAL PRIMARY KEY,
                espn_game_id    INTEGER UNIQUE,
                home_team       VARCHAR(100),
                away_team       VARCHAR(100),
                match_date      TIMESTAMP WITH TIME ZONE,
                season_label    VARCHAR(10)
            )
        """)

    conn.commit()
    cursor.close()
    conn.close()
    print("Raw tables created successfully")


def add_ws_team_id_to_clubs():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        ALTER TABLE clubs 
        ADD COLUMN IF NOT EXISTS ws_team_id INTEGER
    """)
    conn.commit()
    cursor.close()
    conn.close()
    print("ws_team_id column added to clubs")


def add_ws_event_name_to_clubs():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        ALTER TABLE clubs 
        ADD COLUMN IF NOT EXISTS ws_event_name VARCHAR(100)
    """)
    conn.commit()
    cursor.close()
    conn.close()
    print("ws_event_name column added to clubs")

def create_clean_tables():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clean_events (
            id                  SERIAL PRIMARY KEY,
            raw_event_id        INTEGER REFERENCES raw_ws_events(id),
            match_id            INTEGER NOT NULL REFERENCES matches(match_id),
            club_id             INTEGER REFERENCES clubs(club_id),
            player_id           INTEGER REFERENCES players(player_id),
            ws_player_id        INTEGER,
            ws_team_id          INTEGER,
            player_name         VARCHAR(100),
            team_name           VARCHAR(100),
            period              VARCHAR(20),
            minute              INTEGER,
            second              FLOAT,
            expanded_minute     INTEGER,
            type                VARCHAR(50),
            outcome_type        VARCHAR(50),
            is_successful       BOOLEAN,
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
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clean_lineups (
            id                  SERIAL PRIMARY KEY,
            raw_lineup_id       INTEGER REFERENCES raw_espn_lineups(id),
            match_id            INTEGER REFERENCES matches(match_id),
            club_id             INTEGER REFERENCES clubs(club_id),
            player_id           INTEGER REFERENCES players(player_id),
            player_name         VARCHAR(100),
            team_name           VARCHAR(100),
            is_home             BOOLEAN,
            position            VARCHAR(50),
            formation_place     INTEGER,
            sub_in              VARCHAR(10),
            sub_out             VARCHAR(10),
            started             BOOLEAN,
            minutes_played      INTEGER,
            appearances         FLOAT,
            fouls_committed     FLOAT,
            fouls_suffered      FLOAT,
            own_goals           FLOAT,
            red_cards           FLOAT,
            sub_ins             FLOAT,
            yellow_cards        FLOAT,
            goals_conceded      FLOAT,
            saves               FLOAT,
            shots_faced         FLOAT,
            goal_assists        FLOAT,
            shots_on_target     FLOAT,
            total_goals         FLOAT,
            total_shots         FLOAT,
            offsides            FLOAT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clean_player_stats (
            id                      SERIAL PRIMARY KEY,
            raw_stat_id             INTEGER REFERENCES raw_understat_player_stats(id),
            season_id               INTEGER REFERENCES seasons(season_id),
            club_id                 INTEGER REFERENCES clubs(club_id),
            player_id               INTEGER REFERENCES players(player_id),
            appointment_id          INTEGER REFERENCES appointments(appointment_id),
            player_name             VARCHAR(100),
            team_name               VARCHAR(100),
            position                VARCHAR(20),
            matches                 INTEGER,
            minutes                 INTEGER,
            goals                   INTEGER,
            np_goals                INTEGER,
            assists                 INTEGER,
            shots                   INTEGER,
            key_passes              INTEGER,
            yellow_cards            INTEGER,
            red_cards               INTEGER,
            xg                      FLOAT,
            np_xg                   FLOAT,
            xa                      FLOAT,
            xg_chain                FLOAT,
            xg_buildup              FLOAT,
            xg_per_90               FLOAT,
            np_xg_per_90            FLOAT,
            xa_per_90               FLOAT,
            xg_chain_per_90         FLOAT,
            xg_buildup_per_90       FLOAT
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("Clean tables created successfully")

def create_processed_tables():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS proc_sequences (
            id                  SERIAL PRIMARY KEY,
            match_id            INTEGER NOT NULL REFERENCES matches(match_id),
            club_id             INTEGER REFERENCES clubs(club_id),
            sequence_number     INTEGER NOT NULL,
            period              VARCHAR(20),
            start_minute        INTEGER,
            start_second        FLOAT,
            end_minute          INTEGER,
            end_second          FLOAT,
            event_count         INTEGER,
            start_x             FLOAT,
            start_y             FLOAT,
            end_x               FLOAT,
            end_y               FLOAT,
            x_progression       FLOAT,
            start_zone          VARCHAR(20),
            end_zone            VARCHAR(20),
            ended_with_shot     BOOLEAN,
            ended_with_goal     BOOLEAN,
            ended_with_loss     BOOLEAN,
            max_x               FLOAT,
            avg_x               FLOAT,
            width               FLOAT,
            UNIQUE(match_id, club_id, sequence_number)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS proc_sequence_events (
            id              SERIAL PRIMARY KEY,
            sequence_id     INTEGER NOT NULL REFERENCES proc_sequences(id),
            clean_event_id  INTEGER NOT NULL REFERENCES clean_events(id),
            position        INTEGER NOT NULL
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("Processed tables created successfully")

def add_end_event_type_to_sequences():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        ALTER TABLE proc_sequences
        ADD COLUMN IF NOT EXISTS end_event_type VARCHAR(50),
        ADD COLUMN IF NOT EXISTS start_event_type VARCHAR(50)
    """)
    conn.commit()
    cursor.close()
    conn.close()
    print("end_event_type and start_event_type columns added to proc_sequences")

def create_understat_match_stats_table():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_understat_player_match_stats (
            id                  SERIAL PRIMARY KEY,
            season_label        VARCHAR(10),
            understat_game_id   INTEGER,
            understat_team_id   INTEGER,
            understat_player_id INTEGER,
            player_name         VARCHAR(100),
            team_name           VARCHAR(100),
            position            VARCHAR(10),
            position_id         INTEGER,
            minutes             INTEGER,
            goals               INTEGER,
            own_goals           INTEGER,
            shots               INTEGER,
            xg                  FLOAT,
            xa                  FLOAT,
            xg_chain            FLOAT,
            xg_buildup          FLOAT,
            UNIQUE(season_label, understat_game_id, understat_player_id)
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("raw_understat_player_match_stats table created")


def create_understat_schedule_table():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_understat_schedule (
            id                  SERIAL PRIMARY KEY,
            season_label        VARCHAR(10),
            understat_game_id   INTEGER UNIQUE,
            home_team           VARCHAR(100),
            away_team           VARCHAR(100),
            match_date          TIMESTAMP WITH TIME ZONE,
            home_goals          INTEGER,
            away_goals          INTEGER,
            home_xg             FLOAT,
            away_xg             FLOAT
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("raw_understat_schedule table created")


def add_understat_game_id_to_matches():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        ALTER TABLE matches
        ADD COLUMN IF NOT EXISTS understat_game_id INTEGER
    """)
    conn.commit()
    cursor.close()
    conn.close()
    print("understat_game_id added to matches")


def create_clean_player_match_stats_table():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clean_player_match_stats (
            id                  SERIAL PRIMARY KEY,
            raw_stat_id         INTEGER REFERENCES raw_understat_player_match_stats(id),
            match_id            INTEGER REFERENCES matches(match_id),
            club_id             INTEGER REFERENCES clubs(club_id),
            player_id           INTEGER REFERENCES players(player_id),
            appointment_id      INTEGER REFERENCES appointments(appointment_id),
            player_name         VARCHAR(100),
            team_name           VARCHAR(100),
            position            VARCHAR(10),
            minutes             INTEGER,
            goals               INTEGER,
            own_goals           INTEGER,
            shots               INTEGER,
            xg                  FLOAT,
            xa                  FLOAT,
            xg_chain            FLOAT,
            xg_buildup          FLOAT,
            xg_per_90           FLOAT,
            xa_per_90           FLOAT,
            xg_chain_per_90     FLOAT,
            xg_buildup_per_90   FLOAT
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("clean_player_match_stats table created")


if __name__ == "__main__":
    create_tables()
    add_caretaker_column()
    add_match_context_table()
    fix_match_events_constraints()
    create_raw_tables()
    add_ws_team_id_to_clubs()
    add_ws_event_name_to_clubs()
    create_clean_tables()
    create_processed_tables()
    add_end_event_type_to_sequences()
    create_understat_match_stats_table()
    create_understat_schedule_table()
    add_understat_game_id_to_matches()
    create_clean_player_match_stats_table()