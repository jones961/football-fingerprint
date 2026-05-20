import psycopg2
from psycopg2.extras import Json
from config import DB_CONFIG


def get_club_id_from_ws_team_id(cursor, ws_team_id):
    cursor.execute("""
        SELECT club_id FROM clubs WHERE ws_team_id = %s
    """, (ws_team_id,))
    result = cursor.fetchone()
    return result[0] if result else None


def get_or_create_player(cursor, ws_player_id, player_name):
    if ws_player_id is None:
        return None

    cursor.execute("""
        SELECT player_id FROM players WHERE ws_player_id = %s
    """, (ws_player_id,))
    result = cursor.fetchone()
    if result:
        return result[0]

    cursor.execute("""
        INSERT INTO players (name, ws_player_id)
        VALUES (%s, %s)
        RETURNING player_id
    """, (player_name, ws_player_id))
    return cursor.fetchone()[0]


def clean_events(match_id=None):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    if match_id:
        cursor.execute("""
            SELECT id, match_id, ws_player_id, ws_team_id,
                   player_name, team_name, period, minute, second,
                   expanded_minute, type, outcome_type, x, y,
                   end_x, end_y, goal_mouth_y, goal_mouth_z,
                   blocked_x, blocked_y, is_touch, is_shot, is_goal,
                   card_type, related_event_id, related_player_id, qualifiers
            FROM raw_ws_events
            WHERE match_id = %s
            AND period NOT IN ('PreMatch', 'PostGame')
        """, (match_id,))
    else:
        cursor.execute("""
            SELECT id, match_id, ws_player_id, ws_team_id,
                   player_name, team_name, period, minute, second,
                   expanded_minute, type, outcome_type, x, y,
                   end_x, end_y, goal_mouth_y, goal_mouth_z,
                   blocked_x, blocked_y, is_touch, is_shot, is_goal,
                   card_type, related_event_id, related_player_id, qualifiers
            FROM raw_ws_events
            WHERE period NOT IN ('PreMatch', 'PostGame')
        """)

    raw_events = cursor.fetchall()
    print(f"Processing {len(raw_events)} raw events")

    inserted = 0
    skipped = 0
    unmatched_teams = set()

    for row in raw_events:
        (raw_id, match_id, ws_player_id, ws_team_id,
         player_name, team_name, period, minute, second,
         expanded_minute, event_type, outcome_type, x, y,
         end_x, end_y, goal_mouth_y, goal_mouth_z,
         blocked_x, blocked_y, is_touch, is_shot, is_goal,
         card_type, related_event_id, related_player_id, qualifiers) = row

        cursor.execute("""
            SELECT id FROM clean_events WHERE raw_event_id = %s
        """, (raw_id,))
        if cursor.fetchone():
            skipped += 1
            continue

        club_id = get_club_id_from_ws_team_id(cursor, ws_team_id)
        if not club_id and ws_team_id:
            unmatched_teams.add((team_name, ws_team_id))

        player_id = get_or_create_player(cursor, ws_player_id, player_name)

        is_successful = outcome_type == 'Successful' if outcome_type else None

        cursor.execute("""
            INSERT INTO clean_events (
                raw_event_id, match_id, club_id, player_id,
                ws_player_id, ws_team_id, player_name, team_name,
                period, minute, second, expanded_minute,
                type, outcome_type, is_successful,
                x, y, end_x, end_y,
                goal_mouth_y, goal_mouth_z,
                blocked_x, blocked_y,
                is_touch, is_shot, is_goal,
                card_type, related_event_id, related_player_id,
                qualifiers
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            raw_id, match_id, club_id, player_id,
            ws_player_id, ws_team_id, player_name, team_name,
            period, minute, second, expanded_minute,
            event_type, outcome_type, is_successful,
            x, y, end_x, end_y,
            goal_mouth_y, goal_mouth_z,
            blocked_x, blocked_y,
            is_touch, is_shot, is_goal,
            card_type, related_event_id, related_player_id,
            Json(qualifiers) if qualifiers is not None else None,
        ))
        inserted += 1

        if inserted % 1000 == 0:
            conn.commit()
            print(f"Inserted {inserted} events so far...")

    conn.commit()

    if unmatched_teams:
        print(f"Unmatched teams: {unmatched_teams}")

    cursor.close()
    conn.close()
    print(f"Done. Inserted: {inserted}, Skipped: {skipped}")


if __name__ == "__main__":
    clean_events()