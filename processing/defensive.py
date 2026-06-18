"""
processing/defensive.py

Extracts defensive actions from clean_events into two separate tables:

  proc_defensive_actions  — outfield defending
  proc_keeper_actions     — goalkeeper defensive actions (NOT distribution)

Design notes:
  - These read DIRECTLY from clean_events, not from proc_sequences. The
    minimum-length sequence filter does NOT apply here. Every defensive
    event counts, including those in single-touch possessions — that is
    exactly where pressing and instant recoveries show up.
  - Two-sided types (Aerial, Foul) are stored RAW with is_successful, which
    encodes the side. WhoScored logs both perspectives of a duel as separate
    rows, so is_successful is the disambiguator, applied later in views:
        Aerial: is_successful=True  -> duel won
        Foul:   is_successful=False -> foul committed (the defensive one)
  - Keeper distribution/possession is deliberately out of scope (future
    proc_keeper_distribution from Pass events).

Run:  venv312\\Scripts\\python.exe -m processing.defensive
"""

import time

import psycopg2
from psycopg2.extras import execute_values

from config import DB_CONFIG


# ---- Outfield: raw type -> defensive_category -------------------------------
OUTFIELD_CATEGORY = {
    'BallRecovery': 'ball_winning',
    'Interception': 'ball_winning',
    'Tackle':       'tackling',
    'Challenge':    'tackling',     # the "beaten" event; pairs with Tackle
    'BlockedPass':  'blocking',
    'Clearance':    'clearing',
    'ShieldBallOpp': 'clearing',    # folded in, low volume
    'Aerial':       'aerial',
    'Foul':         'foul',
    'Error':        'error',
}

# ---- Keeper: raw type -> keeper_category ------------------------------------
KEEPER_CATEGORY = {
    'Save':          'shot_stopping',
    'Smother':       'shot_stopping',
    'PenaltyFaced':  'shot_stopping',
    'Claim':         'claiming',
    'Punch':         'claiming',
    'CrossNotClaimed': 'claiming',
    'KeeperSweeper': 'sweeping',
    'KeeperPickup':  'handling',
}


def _extract(cursor, target_table, category_map, category_col):
    """Generic extractor: pull all clean_events whose type is in category_map,
    tag each with its category, batch-insert into target_table.
    Idempotent: ON CONFLICT (clean_event_id) DO NOTHING."""
    types = tuple(category_map.keys())

    cursor.execute("""
        SELECT id, match_id, club_id, player_id, player_name,
               type, is_successful, period, minute, second, x, y
        FROM clean_events
        WHERE type IN %s
        AND period IN ('FirstHalf', 'SecondHalf',
                       'ExtraTimeFirstHalf', 'ExtraTimeSecondHalf')
        ORDER BY id
    """, (types,))
    rows = cursor.fetchall()

    out = []
    for (cid, match_id, club_id, player_id, player_name,
         etype, is_successful, period, minute, second, x, y) in rows:
        category = category_map[etype]
        out.append((
            cid, match_id, club_id, player_id, player_name,
            etype, category, is_successful, period, minute, second, x, y
        ))

    if not out:
        print(f"  {target_table}: no rows found")
        return 0

    execute_values(
        cursor,
        f"""
        INSERT INTO {target_table} (
            clean_event_id, match_id, club_id, player_id, player_name,
            type, {category_col}, is_successful, period, minute, second, x, y
        ) VALUES %s
        ON CONFLICT (clean_event_id) DO NOTHING
        """,
        out,
    )
    return len(out)


def extract_outfield(cursor):
    n = _extract(cursor, 'proc_defensive_actions',
                 OUTFIELD_CATEGORY, 'defensive_category')
    print(f"  proc_defensive_actions: {n} rows processed")
    return n


def extract_keeper(cursor):
    n = _extract(cursor, 'proc_keeper_actions',
                 KEEPER_CATEGORY, 'keeper_category')
    print(f"  proc_keeper_actions: {n} rows processed")
    return n


def build_all():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    t0 = time.time()
    print("Extracting defensive actions...")
    try:
        extract_outfield(cursor)
        extract_keeper(cursor)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"FAILED, rolled back: {e}")
        raise
    finally:
        cursor.close()
        conn.close()
    print(f"Done in {time.time() - t0:.1f}s")


# ---- Quick sanity readouts so you can eyeball the result --------------------
def summary():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    print("\n=== Outfield defensive actions by category ===")
    cursor.execute("""
        SELECT defensive_category, COUNT(*) AS n,
               ROUND(AVG(x)::numeric, 1) AS avg_x
        FROM proc_defensive_actions
        GROUP BY defensive_category
        ORDER BY n DESC
    """)
    for cat, n, avg_x in cursor.fetchall():
        print(f"  {cat:<14} {n:>8}   avg_x={avg_x}")

    print("\n=== Keeper actions by category ===")
    cursor.execute("""
        SELECT keeper_category, COUNT(*) AS n,
               ROUND(AVG(x)::numeric, 1) AS avg_x
        FROM proc_keeper_actions
        GROUP BY keeper_category
        ORDER BY n DESC
    """)
    for cat, n, avg_x in cursor.fetchall():
        print(f"  {cat:<14} {n:>8}   avg_x={avg_x}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    build_all()
    summary()