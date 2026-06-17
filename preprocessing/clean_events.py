import psycopg2
from config import DB_CONFIG

# Periods that are not real phases of play
EXCLUDED_PERIODS = ('PreMatch', 'PostGame')


def clean_events(batch_size=50000):
    """
    Set-based rebuild of clean_events.

    Instead of looping in Python with a SELECT + INSERT per row, this does
    everything in SQL:
      1. Bulk-create any players that appear in raw events but not in players.
      2. INSERT ... SELECT the full transform in batches, skipping rows
         that already exist via a LEFT JOIN anti-join (no per-row SELECT).

    Safe to stop and restart: the anti-join means already-cleaned rows are
    skipped, so a rerun resumes where it left off.
    """
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cursor = conn.cursor()

    # ------------------------------------------------------------------
    # Step 1: bulk-create missing players in ONE statement.
    # Pick the most common name per ws_player_id to avoid duplicate rows.
    # ------------------------------------------------------------------
    print("Creating any missing players...")
    cursor.execute("""
        INSERT INTO players (name, ws_player_id)
        SELECT DISTINCT ON (rwe.ws_player_id)
               rwe.player_name, rwe.ws_player_id
        FROM raw_ws_events rwe
        WHERE rwe.ws_player_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM players p
              WHERE p.ws_player_id = rwe.ws_player_id
          )
        ORDER BY rwe.ws_player_id, rwe.player_name
        ON CONFLICT DO NOTHING
    """)
    print(f"  Players created: {cursor.rowcount}")
    conn.commit()

    # ------------------------------------------------------------------
    # Step 2: figure out how many raw events still need cleaning.
    # ------------------------------------------------------------------
    cursor.execute("""
        SELECT MIN(rwe.id), MAX(rwe.id)
        FROM raw_ws_events rwe
        WHERE rwe.period NOT IN %s
    """, (EXCLUDED_PERIODS,))
    min_id, max_id = cursor.fetchone()

    if min_id is None:
        print("No raw events to process.")
        cursor.close()
        conn.close()
        return

    print(f"Raw event id range: {min_id} to {max_id}")

    # ------------------------------------------------------------------
    # Step 3: batched INSERT ... SELECT.
    # We walk the raw_ws_events.id range in chunks. The LEFT JOIN against
    # clean_events.raw_event_id is the anti-join that makes reruns safe
    # and lets us skip the ~400k rows already done.
    # ------------------------------------------------------------------
    total_inserted = 0
    lo = min_id
    while lo <= max_id:
        hi = lo + batch_size - 1

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
            )
            SELECT
                rwe.id,
                rwe.match_id,
                c.club_id,
                p.player_id,
                rwe.ws_player_id,
                rwe.ws_team_id,
                rwe.player_name,
                rwe.team_name,
                rwe.period,
                rwe.minute,
                rwe.second,
                rwe.expanded_minute,
                rwe.type,
                rwe.outcome_type,
                (rwe.outcome_type = 'Successful'),
                rwe.x, rwe.y, rwe.end_x, rwe.end_y,
                rwe.goal_mouth_y, rwe.goal_mouth_z,
                rwe.blocked_x, rwe.blocked_y,
                rwe.is_touch, rwe.is_shot, rwe.is_goal,
                rwe.card_type, rwe.related_event_id, rwe.related_player_id,
                rwe.qualifiers
            FROM raw_ws_events rwe
            LEFT JOIN clubs c   ON c.ws_team_id = rwe.ws_team_id
            LEFT JOIN players p ON p.ws_player_id = rwe.ws_player_id
            LEFT JOIN clean_events ce ON ce.raw_event_id = rwe.id
            WHERE rwe.id BETWEEN %s AND %s
              AND rwe.period NOT IN %s
              AND ce.id IS NULL
        """, (lo, hi, EXCLUDED_PERIODS))

        inserted = cursor.rowcount
        total_inserted += inserted
        conn.commit()
        print(f"  ids {lo}-{hi}: inserted {inserted} (running total {total_inserted})")

        lo = hi + 1

    cursor.close()
    conn.close()
    print(f"\nDone. Total inserted this run: {total_inserted}")


if __name__ == "__main__":
    clean_events()