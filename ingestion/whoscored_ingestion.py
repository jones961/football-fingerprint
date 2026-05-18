import soccerdata as sd
import psycopg2
import math
from config import DB_CONFIG


def safe_int(value):
    if value is None:
        return None
    try:
        if math.isnan(value):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


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
            safe_int(row['home_score']),
            safe_int(row['away_score']),
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
    clubs_and_seasons = [
        ("Arsenal", "2020/2021", "2021"),
        ("Arsenal", "2021/2022", "2122"),
        ("Arsenal", "2022/2023", "2223"),
        ("Arsenal", "2023/2024", "2324"),
        ("Arsenal", "2024/2025", "2425"),
        ("Arsenal", "2025/2026", "2526"),
        ("Manchester United", "2020/2021", "2021"),
        ("Manchester United", "2021/2022", "2122"),
        ("Manchester United", "2022/2023", "2223"),
        ("Manchester United", "2023/2024", "2324"),
        ("Manchester United", "2024/2025", "2425"),
        ("Manchester United", "2025/2026", "2526"),
        ("Chelsea", "2020/2021", "2021"),
        ("Chelsea", "2021/2022", "2122"),
        ("Chelsea", "2022/2023", "2223"),
        ("Chelsea", "2023/2024", "2324"),
        ("Chelsea", "2024/2025", "2425"),
        ("Chelsea", "2025/2026", "2526"),
        ("Brentford", "2020/2021", "2021"),
        ("Brentford", "2021/2022", "2122"),
        ("Brentford", "2022/2023", "2223"),
        ("Brentford", "2023/2024", "2324"),
        ("Brentford", "2024/2025", "2425"),
        ("Brentford", "2025/2026", "2526"),
    ]

    for club, season_label, ws_code in clubs_and_seasons:
        print(f"\n--- {club} {season_label} ---")
        load_matches(club, season_label, ws_code)