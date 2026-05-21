import psycopg2
from config import DB_CONFIG


def clean_player_stats():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, season_label, team_name, player_name,
               understat_player_id, understat_team_id, position,
               matches, minutes, goals, np_goals, assists,
               shots, key_passes, yellow_cards, red_cards,
               xg, np_xg, xa, xg_chain, xg_buildup
        FROM raw_understat_player_stats
    """)

    raw_stats = cursor.fetchall()
    print(f"Processing {len(raw_stats)} raw player stat records")

    inserted = 0
    skipped = 0
    unmatched = []

    for row in raw_stats:
        (raw_id, season_label, team_name, player_name,
         understat_player_id, understat_team_id, position,
         matches, minutes, goals, np_goals, assists,
         shots, key_passes, yellow_cards, red_cards,
         xg, np_xg, xa, xg_chain, xg_buildup) = row

        # Check already cleaned
        cursor.execute("""
            SELECT id FROM clean_player_stats WHERE raw_stat_id = %s
        """, (raw_id,))
        if cursor.fetchone():
            skipped += 1
            continue

        # Resolve season
        cursor.execute("""
            SELECT season_id FROM seasons
            WHERE label = %s
        """, (season_label.replace('/20', '/'),))
        season_result = cursor.fetchone()
        if not season_result:
            # Try direct match
            cursor.execute("""
                SELECT season_id FROM seasons
                WHERE ws_code = %s OR understat_code = %s
            """, (season_label[-4:], season_label[:4],))
            season_result = cursor.fetchone()

        season_id = season_result[0] if season_result else None

        # Resolve club from understat team name
        cursor.execute("""
            SELECT club_id FROM clubs
            WHERE understat_name = %s
            OR name = %s
        """, (team_name, team_name))
        club_result = cursor.fetchone()
        club_id = club_result[0] if club_result else None

        if not club_id:
            unmatched.append(team_name)

        # Resolve or create player
        player_id = None
        if understat_player_id:
            cursor.execute("""
                SELECT player_id FROM players
                WHERE understat_id = %s
            """, (understat_player_id,))
            result = cursor.fetchone()
            if result:
                player_id = result[0]
            else:
                # Try matching by name
                cursor.execute("""
                    SELECT player_id FROM players WHERE name = %s
                """, (player_name,))
                result = cursor.fetchone()
                if result:
                    player_id = result[0]
                    # Update understat_id
                    cursor.execute("""
                        UPDATE players SET understat_id = %s
                        WHERE player_id = %s
                    """, (understat_player_id, player_id))
                else:
                    cursor.execute("""
                        INSERT INTO players (name, understat_id)
                        VALUES (%s, %s)
                        RETURNING player_id
                    """, (player_name, understat_player_id))
                    player_id = cursor.fetchone()[0]

        # Resolve appointment
        appointment_id = None
        if club_id and season_id:
            cursor.execute("""
                SELECT season_id, start_year, end_year
                FROM seasons WHERE season_id = %s
            """, (season_id,))
            season_row = cursor.fetchone()
            if season_row:
                mid_season = f"{season_row[1]}-12-01"
                cursor.execute("""
                    SELECT appointment_id FROM appointments
                    WHERE club_id = %s
                    AND date_from <= %s
                    AND (date_to IS NULL OR date_to >= %s)
                """, (club_id, mid_season, mid_season))
                appt_result = cursor.fetchone()
                appointment_id = appt_result[0] if appt_result else None

        # Compute per-90 metrics
        minutes_safe = minutes if minutes and minutes > 0 else None
        per_90 = (90 / minutes_safe) if minutes_safe else None

        xg_per_90 = round(xg * per_90, 4) if xg and per_90 else None
        np_xg_per_90 = round(np_xg * per_90, 4) if np_xg and per_90 else None
        xa_per_90 = round(xa * per_90, 4) if xa and per_90 else None
        xg_chain_per_90 = round(xg_chain * per_90, 4) if xg_chain and per_90 else None
        xg_buildup_per_90 = round(xg_buildup * per_90, 4) if xg_buildup and per_90 else None

        cursor.execute("""
            INSERT INTO clean_player_stats (
                raw_stat_id, season_id, club_id, player_id,
                appointment_id, player_name, team_name, position,
                matches, minutes, goals, np_goals, assists,
                shots, key_passes, yellow_cards, red_cards,
                xg, np_xg, xa, xg_chain, xg_buildup,
                xg_per_90, np_xg_per_90, xa_per_90,
                xg_chain_per_90, xg_buildup_per_90
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            raw_id, season_id, club_id, player_id,
            appointment_id, player_name, team_name, position,
            matches, minutes, goals, np_goals, assists,
            shots, key_passes, yellow_cards, red_cards,
            xg, np_xg, xa, xg_chain, xg_buildup,
            xg_per_90, np_xg_per_90, xa_per_90,
            xg_chain_per_90, xg_buildup_per_90
        ))
        inserted += 1

        if inserted % 500 == 0:
            conn.commit()
            print(f"Inserted {inserted} records so far...")

    conn.commit()

    if unmatched:
        unique_unmatched = list(set(unmatched))
        print(f"\nUnmatched clubs: {unique_unmatched}")

    cursor.close()
    conn.close()
    print(f"\nDone. Inserted: {inserted}, Skipped: {skipped}")

def fix_unmatched_clubs():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Fix Wolves and Newcastle records that had null club_id
    corrections = [
        ('Wolverhampton Wanderers', 'Wolves'),
        ('Newcastle United', 'Newcastle'),
    ]

    for understat_name, ws_name in corrections:
        cursor.execute("""
            SELECT club_id FROM clubs WHERE ws_name = %s
        """, (ws_name,))
        result = cursor.fetchone()
        if not result:
            print(f"Club not found: {ws_name}")
            continue

        club_id = result[0]

        cursor.execute("""
            UPDATE clean_player_stats
            SET club_id = %s
            WHERE team_name = %s
            AND club_id IS NULL
        """, (club_id, understat_name))

        print(f"Updated {cursor.rowcount} records for {understat_name}")

    conn.commit()
    cursor.close()
    conn.close()
    print("Done")

if __name__ == "__main__":
    clean_player_stats()
    fix_unmatched_clubs()