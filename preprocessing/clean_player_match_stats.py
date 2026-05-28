import psycopg2
from config import DB_CONFIG


def clean_player_match_stats():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            u.id,
            u.understat_game_id,
            u.understat_player_id,
            u.player_name,
            u.team_name,
            u.position,
            u.minutes,
            u.goals,
            u.own_goals,
            u.shots,
            u.xg,
            u.xa,
            u.xg_chain,
            u.xg_buildup,
            u.season_label
        FROM raw_understat_player_match_stats u
        WHERE u.minutes > 0
    """)

    raw_stats = cursor.fetchall()
    print(f"Processing {len(raw_stats)} raw player match records")

    inserted = 0
    skipped = 0
    unmatched_matches = set()
    unmatched_players = set()

    for row in raw_stats:
        (raw_id, understat_game_id, understat_player_id,
         player_name, team_name, position, minutes,
         goals, own_goals, shots, xg, xa,
         xg_chain, xg_buildup, season_label) = row

        # Check already cleaned
        cursor.execute("""
            SELECT id FROM clean_player_match_stats
            WHERE raw_stat_id = %s
        """, (raw_id,))
        if cursor.fetchone():
            skipped += 1
            continue

        # Resolve match
        cursor.execute("""
            SELECT match_id FROM matches
            WHERE understat_game_id = %s
        """, (understat_game_id,))
        match_result = cursor.fetchone()
        if not match_result:
            unmatched_matches.add(understat_game_id)
            continue
        match_id = match_result[0]

        # Resolve club
        cursor.execute("""
            SELECT club_id FROM clubs
            WHERE understat_name = %s
            OR name = %s
        """, (team_name, team_name))
        club_result = cursor.fetchone()
        club_id = club_result[0] if club_result else None

        # Resolve player
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
                cursor.execute("""
                    SELECT player_id FROM players
                    WHERE name = %s
                """, (player_name,))
                result = cursor.fetchone()
                if result:
                    player_id = result[0]
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
                    if player_name not in unmatched_players:
                        unmatched_players.add(player_name)

        # Resolve appointment
        appointment_id = None
        if club_id:
            cursor.execute("""
                SELECT m.match_date FROM matches m
                WHERE m.match_id = %s
            """, (match_id,))
            match_date = cursor.fetchone()[0].date()

            cursor.execute("""
                SELECT appointment_id FROM appointments
                WHERE club_id = %s
                AND date_from <= %s
                AND (date_to IS NULL OR date_to >= %s)
            """, (club_id, match_date, match_date))
            appt_result = cursor.fetchone()
            appointment_id = appt_result[0] if appt_result else None

        # Per-90 metrics
        per_90 = (90 / minutes) if minutes and minutes > 0 else None

        cursor.execute("""
            INSERT INTO clean_player_match_stats (
                raw_stat_id, match_id, club_id, player_id,
                appointment_id, player_name, team_name,
                position, minutes,
                goals, own_goals, shots,
                xg, xa, xg_chain, xg_buildup,
                xg_per_90, xa_per_90,
                xg_chain_per_90, xg_buildup_per_90
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
        """, (
            raw_id, match_id, club_id, player_id,
            appointment_id, player_name, team_name,
            position, minutes,
            goals, own_goals, shots,
            xg, xa, xg_chain, xg_buildup,
            round(xg * per_90, 4) if xg and per_90 else None,
            round(xa * per_90, 4) if xa and per_90 else None,
            round(xg_chain * per_90, 4) if xg_chain and per_90 else None,
            round(xg_buildup * per_90, 4) if xg_buildup and per_90 else None,
        ))
        inserted += 1

        if inserted % 1000 == 0:
            conn.commit()
            print(f"Inserted {inserted} records...")

    conn.commit()

    print(f"\nUnmatched matches: {len(unmatched_matches)}")
    print(f"New players created: {len(unmatched_players)}")
    cursor.close()
    conn.close()
    print(f"\nDone. Inserted: {inserted}, Skipped: {skipped}")


if __name__ == "__main__":
    clean_player_match_stats()