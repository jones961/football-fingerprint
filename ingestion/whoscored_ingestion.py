import soccerdata as sd
import psycopg2
from config import DB_CONFIG


def get_club_id(cursor, ws_name):
    cursor.execute("""
        SELECT club_id FROM clubs WHERE ws_name = %s
    """, (ws_name,))
    result = cursor.fetchone()
    return result[0] if result else None


def get_or_create_club(cursor, ws_name):
    club_id = get_club_id(cursor, ws_name)
    if club_id:
        return club_id
    cursor.execute("""
        INSERT INTO clubs (name, ws_name)
        VALUES (%s, %s)
        ON CONFLICT (name) DO UPDATE SET ws_name = EXCLUDED.ws_name
        RETURNING club_id
    """, (ws_name, ws_name))
    return cursor.fetchone()[0]


def get_appointment_id(cursor, club_id, match_date):
    cursor.execute("""
        SELECT appointment_id FROM appointments
        WHERE club_id = %s
        AND date_from <= %s
        AND (date_to IS NULL OR date_to >= %s)
    """, (club_id, match_date, match_date))
    result = cursor.fetchone()
    return result[0] if result else None


def get_season_id(cursor, ws_code):
    cursor.execute("""
        SELECT season_id FROM seasons WHERE ws_code = %s
    """, (ws_code,))
    result = cursor.fetchone()
    return result[0] if result else None


def load_matches(club_ws_name, season_label, ws_code):
    ws = sd.WhoScored(
        leagues="ENG-Premier League",
        seasons=season_label
    )
    schedule = ws.read_schedule()

    club_games = schedule[
        (schedule['home_team'] == club_ws_name) |
        (schedule['away_team'] == club_ws_name)
    ].copy()

    print(f"Found {len(club_games)} matches for {club_ws_name} in {season_label}")

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    club_id = get_club_id(cursor, club_ws_name)
    season_id = get_season_id(cursor, ws_code)

    if not club_id:
        print(f"Club not found in database: {club_ws_name}")
        return

    if not season_id:
        print(f"Season not found in database: {ws_code}")
        return

    inserted = 0
    skipped = 0

    for _, row in club_games.iterrows():
        match_date = row['date'].date()
        is_home = row['home_team'] == club_ws_name
        opponent_ws_name = row['away_team'] if is_home else row['home_team']

        appointment_id = get_appointment_id(cursor, club_id, match_date)

        if not appointment_id:
            print(f"No appointment found for {club_ws_name} on {match_date}")
            skipped += 1
            continue

        opponent_id = get_or_create_club(cursor, opponent_ws_name)

        cursor.execute("""
            INSERT INTO matches 
                (ws_game_id, appointment_id, season_id, opponent_id, 
                 match_date, venue, home_score, away_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (ws_game_id) DO NOTHING
        """, (
            int(row['game_id']),
            appointment_id,
            season_id,
            opponent_id,
            match_date,
            'home' if is_home else 'away',
            int(row['home_score']) if row['home_score'] is not None else None,
            int(row['away_score']) if row['away_score'] is not None else None,
        ))

        if cursor.rowcount > 0:
            inserted += 1

    conn.commit()
    cursor.close()
    conn.close()

    print(f"Inserted: {inserted} matches, Skipped: {skipped}")

def verify_matches(club_ws_name):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            m.match_date,
            m.venue,
            c.ws_name as opponent,
            m.home_score,
            m.away_score,
            m.appointment_id
        FROM matches m
        JOIN clubs c ON m.opponent_id = c.club_id
        JOIN appointments a ON m.appointment_id = a.appointment_id
        JOIN clubs home_club ON a.club_id = home_club.club_id
        WHERE home_club.ws_name = %s
        ORDER BY m.match_date
        LIMIT 5
    """, (club_ws_name,))
    rows = cursor.fetchall()
    for row in rows:
        print(row)
    cursor.close()
    conn.close()

if __name__ == "__main__":
    load_matches("Arsenal", "2024/2025", "2425")
    verify_matches("Arsenal")