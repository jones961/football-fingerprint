import psycopg2
from config import DB_CONFIG


def inspect_event_sequence():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            me.period,
            me.minute,
            me.second,
            me.type,
            me.outcome_type,
            me.x,
            me.y,
            me.end_x,
            me.end_y,
            me.team_id
        FROM match_events me
        JOIN matches m ON me.match_id = m.match_id
        WHERE m.ws_game_id = (
            SELECT ws_game_id FROM matches 
            JOIN match_context mc ON matches.match_id = mc.match_id
            JOIN clubs c ON mc.club_id = c.club_id
            WHERE c.name = 'Arsenal'
            LIMIT 1
        )
        AND me.period = 'FirstHalf'
        ORDER BY me.minute, me.second
        LIMIT 50
    """)

    rows = cursor.fetchall()
    for row in rows:
        print(row)

    cursor.close()
    conn.close()


def inspect_qualifiers():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT qualifiers, type
        FROM match_events
        WHERE qualifiers != '[]'::jsonb
        AND type = 'Pass'
        LIMIT 5
    """)

    rows = cursor.fetchall()
    for row in rows:
        print(row)

    cursor.close()
    conn.close()


def verify_raw_events():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            ws_team_id,
            team_name,
            ws_player_id,
            player_name,
            type,
            x,
            y
        FROM raw_ws_events
        WHERE match_id = (
            SELECT matches.match_id FROM matches 
            JOIN match_context mc ON matches.match_id = mc.match_id
            JOIN clubs c ON mc.club_id = c.club_id
            WHERE c.name = 'Arsenal'
            LIMIT 1
        )
        AND type = 'Pass'
        LIMIT 10
    """)

    for row in cursor.fetchall():
        print(row)

    cursor.close()
    conn.close()

if __name__ == "__main__":
    verify_raw_events()