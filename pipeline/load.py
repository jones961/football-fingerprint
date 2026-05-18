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

def reset_match_context():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("TRUNCATE TABLE match_context")
    conn.commit()
    cursor.close()
    conn.close()
    print("match_context cleared")

def backfill_match_context():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT club_id, ws_name FROM clubs 
        WHERE ws_name IN ('Arsenal', 'Manchester United', 'Chelsea', 'Brentford')
    """)
    poc_clubs = {row[1]: row[0] for row in cursor.fetchall()}

    print("Loading cached schedule data...")
    seasons = [
        "2020/2021", "2021/2022", "2022/2023",
        "2023/2024", "2024/2025", "2025/2026"
    ]

    game_lookup = {}
    for season in seasons:
        ws = sd.WhoScored(leagues="ENG-Premier League", seasons=season)
        schedule = ws.read_schedule()
        for _, row in schedule.iterrows():
            game_lookup[int(row['game_id'])] = {
                'home_team': row['home_team'],
                'away_team': row['away_team']
            }

    print(f"Loaded {len(game_lookup)} matches from schedule cache")

    inserted = 0
    skipped = 0

    for club_ws_name, club_id in poc_clubs.items():
        print(f"\nProcessing {club_ws_name}...")

        cursor.execute("""
            SELECT m.match_id, m.match_date, m.ws_game_id, c.ws_name as opponent_name
            FROM matches m
            JOIN clubs c ON m.opponent_id = c.club_id
        """)

        all_matches = cursor.fetchall()

        for match_id, match_date, ws_game_id, opponent_name in all_matches:
            if not ws_game_id or ws_game_id not in game_lookup:
                skipped += 1
                continue

            game = game_lookup[ws_game_id]

            # Only process if this club actually played in this match
            if game['home_team'] != club_ws_name and game['away_team'] != club_ws_name:
                continue

            venue = 'home' if game['home_team'] == club_ws_name else 'away'
            match_date_only = match_date.date() if hasattr(match_date, 'date') else match_date

            cursor.execute("""
                SELECT appointment_id FROM appointments
                WHERE club_id = %s
                AND date_from <= %s
                AND (date_to IS NULL OR date_to >= %s)
            """, (club_id, match_date_only, match_date_only))

            result = cursor.fetchone()
            if not result:
                print(f"No appointment found for {club_ws_name} on {match_date_only}")
                skipped += 1
                continue

            appointment_id = result[0]

            cursor.execute("""
                INSERT INTO match_context 
                    (match_id, club_id, appointment_id, venue)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (match_id, club_id) DO NOTHING
            """, (match_id, club_id, appointment_id, venue))

            if cursor.rowcount > 0:
                inserted += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"\nBackfill complete. Inserted: {inserted}, Skipped: {skipped}")

def verify_match_context():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Check total counts per club
    cursor.execute("""
        SELECT c.name, COUNT(*) as matches, 
               COUNT(CASE WHEN mc.venue = 'home' THEN 1 END) as home,
               COUNT(CASE WHEN mc.venue = 'away' THEN 1 END) as away,
               COUNT(CASE WHEN mc.venue IS NULL THEN 1 END) as no_venue
        FROM match_context mc
        JOIN clubs c ON mc.club_id = c.club_id
        GROUP BY c.name
        ORDER BY c.name
    """)
    print("Match context counts per club:")
    for row in cursor.fetchall():
        print(row)

    # Check appointment distribution for Man United
    # Should show multiple appointments reflecting manager changes
    cursor.execute("""
        SELECT m.name as manager, COUNT(*) as matches
        FROM match_context mc
        JOIN appointments a ON mc.appointment_id = a.appointment_id
        JOIN managers m ON a.manager_id = m.manager_id
        JOIN clubs c ON a.club_id = c.club_id
        WHERE c.name = 'Manchester United'
        GROUP BY m.name
        ORDER BY COUNT(*) DESC
    """)
    print("\nMan United matches by manager:")
    for row in cursor.fetchall():
        print(row)

    cursor.close()
    conn.close()

def debug_match_context():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT m.ws_game_id, mc.venue, m.match_date
        FROM match_context mc
        JOIN matches m ON mc.match_id = m.match_id
        JOIN clubs c ON mc.club_id = c.club_id
        WHERE c.name = 'Arsenal'
        ORDER BY m.match_date
        LIMIT 10
    """)
    print("Arsenal match context sample:")
    for row in cursor.fetchall():
        print(row)

    cursor.close()
    conn.close()

if __name__ == "__main__":
    reset_match_context()
    backfill_match_context()
    verify_match_context()