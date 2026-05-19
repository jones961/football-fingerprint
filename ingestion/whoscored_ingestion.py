import soccerdata as sd
import psycopg2
import math
import json
from psycopg2.extras import Json
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

def season_label_to_ws(label):
    # Converts '2024/25' to '2024/2025'
    parts = label.split('/')
    start_year = parts[0]
    end_year_short = parts[1]
    end_year_full = start_year[:2] + end_year_short
    return f"{start_year}/{end_year_full}"

def load_events(club_ws_name, season_label):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT m.match_id, m.ws_game_id
        FROM matches m
        JOIN match_context mc ON m.match_id = mc.match_id
        JOIN clubs c ON mc.club_id = c.club_id
        JOIN seasons s ON m.season_id = s.season_id
        WHERE c.ws_name = %s
        AND s.label = %s
    """, (club_ws_name, season_label))

    matches = cursor.fetchall()
    print(f"Found {len(matches)} matches for {club_ws_name} {season_label}")

    ws = sd.WhoScored(
        leagues="ENG-Premier League",
        seasons=season_label_to_ws(season_label)
    )

    total_inserted = 0
    total_skipped = 0

    for match_id, ws_game_id in matches:
        if not ws_game_id:
            print(f"No ws_game_id for match_id {match_id}, skipping")
            continue

        cursor.execute("""
            SELECT COUNT(*) FROM raw_ws_events WHERE match_id = %s
        """, (match_id,))
        if cursor.fetchone()[0] > 0:
            total_skipped += 1
            continue

        try:
            events = ws.read_events(match_id=int(ws_game_id))
        except Exception as e:
            print(f"Failed to pull events for match {ws_game_id}: {e}")
            continue

        inserted = 0
        for _, row in events.iterrows():

            def safe_float(val):
                if val is None:
                    return None
                try:
                    f = float(val)
                    return None if math.isnan(f) else f
                except (TypeError, ValueError):
                    return None

            def safe_bool(val):
                if val is True:
                    return True
                if val is False:
                    return False
                return False

            cursor.execute("""
                INSERT INTO raw_ws_events (
                    match_id, ws_event_id, ws_player_id, ws_team_id,
                    player_name, team_name,
                    period, minute, second, expanded_minute,
                    type, outcome_type,
                    x, y, end_x, end_y,
                    goal_mouth_y, goal_mouth_z,
                    blocked_x, blocked_y,
                    is_touch, is_shot, is_goal,
                    card_type, related_event_id, related_player_id,
                    qualifiers
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
            """, (
                match_id,
                safe_int(row.get('id')),
                safe_int(row.get('player_id')),
                safe_int(row.get('team_id')),
                row.get('player') if row.get('player') not in [None, float('nan')] else None,
                row.get('team') if row.get('team') not in [None, float('nan')] else None,
                row.get('period'),
                safe_int(row.get('minute')),
                safe_float(row.get('second')),
                safe_int(row.get('expanded_minute')),
                row.get('type'),
                row.get('outcome_type'),
                safe_float(row.get('x')),
                safe_float(row.get('y')),
                safe_float(row.get('end_x')),
                safe_float(row.get('end_y')),
                safe_float(row.get('goal_mouth_y')),
                safe_float(row.get('goal_mouth_z')),
                safe_float(row.get('blocked_x')),
                safe_float(row.get('blocked_y')),
                safe_bool(row.get('is_touch')),
                safe_bool(row.get('is_shot')),
                safe_bool(row.get('is_goal')),
                row.get('card_type') if row.get('card_type') not in [None, 'NaN', float('nan')] else None,
                safe_int(row.get('related_event_id')),
                safe_int(row.get('related_player_id')),
                Json(row.get('qualifiers')) if row.get('qualifiers') is not None else None,
            ))
            inserted += 1

        conn.commit()
        total_inserted += inserted
        print(f"Match {ws_game_id}: inserted {inserted} events")

    cursor.close()
    conn.close()
    print(f"\nTotal inserted: {total_inserted}, Skipped matches: {total_skipped}")

if __name__ == "__main__":
    load_events("Arsenal", "2024/25")
    load_events("Manchester United", "2023/24")
    load_events("Manchester United", "2024/25")


