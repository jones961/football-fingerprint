import psycopg2
from config import DB_CONFIG
import soccerdata as sd


def get_or_create_club(cursor, ws_name):
    cursor.execute("""
        SELECT club_id FROM clubs WHERE ws_name = %s
    """, (ws_name,))
    result = cursor.fetchone()
    if result:
        return result[0]
    cursor.execute("""
        INSERT INTO clubs (name, ws_name)
        VALUES (%s, %s)
        RETURNING club_id
    """, (ws_name, ws_name))
    return cursor.fetchone()[0]


def get_or_create_manager(cursor, manager_name):
    cursor.execute("""
        SELECT manager_id FROM managers WHERE name = %s
    """, (manager_name,))
    result = cursor.fetchone()
    if result:
        return result[0]
    cursor.execute("""
        INSERT INTO managers (name)
        VALUES (%s)
        RETURNING manager_id
    """, (manager_name,))
    return cursor.fetchone()[0]


def get_or_create_appointment(cursor, club_id, manager_id, match_date):
    cursor.execute("""
        SELECT appointment_id FROM appointments
        WHERE club_id = %s AND manager_id = %s
        AND date_from <= %s
        AND (date_to IS NULL OR date_to >= %s)
    """, (club_id, manager_id, match_date, match_date))
    result = cursor.fetchone()
    if result:
        return result[0]
    cursor.execute("""
        INSERT INTO appointments (club_id, manager_id, date_from)
        VALUES (%s, %s, %s)
        RETURNING appointment_id
    """, (club_id, manager_id, match_date))
    return cursor.fetchone()[0]


def load_matches(club_ws_name, seasons):
    ws = sd.WhoScored(leagues="ENG-Premier League", seasons=seasons)
    schedule = ws.read_schedule()

    club_games = schedule[
        (schedule['home_team'] == club_ws_name) |
        (schedule['away_team'] == club_ws_name)
        ]

    first_game_id = int(club_games['game_id'].iloc[0])
    print(f"Testing loader with match_id: {first_game_id}")

    loader = ws.read_events(match_id=first_game_id, output_fmt="loader")

    games = loader.games(
        competition_id="ENG-Premier League",
        season_id="2425"
    )

    print(f"\nColumns: {games.columns.tolist()}")
    print(f"\nSample:\n{games.head(3)}")

if __name__ == "__main__":
    load_matches("Arsenal", "2024/2025")