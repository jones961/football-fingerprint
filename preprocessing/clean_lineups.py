import psycopg2
from config import DB_CONFIG


def clean_lineups():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            rel.id,
            rel.match_id,
            rel.espn_game_id,
            rel.player_name,
            rel.team_name,
            rel.is_home,
            rel.position,
            rel.formation_place,
            rel.sub_in,
            rel.sub_out,
            rel.appearances,
            rel.fouls_committed,
            rel.fouls_suffered,
            rel.own_goals,
            rel.red_cards,
            rel.sub_ins,
            rel.yellow_cards,
            rel.goals_conceded,
            rel.saves,
            rel.shots_faced,
            rel.goal_assists,
            rel.shots_on_target,
            rel.total_goals,
            rel.total_shots,
            rel.offsides,
            pr.role_group
        FROM raw_espn_lineups rel
        LEFT JOIN position_roles pr ON rel.position = pr.espn_position
        WHERE rel.position != 'Substitute'
        AND rel.position IS NOT NULL
        AND rel.position != 'NaN'
    """)

    raw_lineups = cursor.fetchall()
    print(f"Processing {len(raw_lineups)} raw lineup records")

    inserted = 0
    skipped = 0
    unmatched_players = []

    for row in raw_lineups:
        (raw_id, match_id, espn_game_id, player_name, team_name,
         is_home, position, formation_place, sub_in, sub_out,
         appearances, fouls_committed, fouls_suffered, own_goals,
         red_cards, sub_ins, yellow_cards, goals_conceded,
         saves, shots_faced, goal_assists, shots_on_target,
         total_goals, total_shots, offsides, role_group) = row

        cursor.execute("""
            SELECT id FROM clean_lineups WHERE raw_lineup_id = %s
        """, (raw_id,))
        if cursor.fetchone():
            skipped += 1
            continue

        cursor.execute("""
            SELECT club_id FROM clubs
            WHERE espn_name = %s OR name = %s
        """, (team_name, team_name))
        club_result = cursor.fetchone()
        club_id = club_result[0] if club_result else None

        player_id = None
        cursor.execute("""
            SELECT player_id FROM players
            WHERE name = %s
        """, (player_name,))
        result = cursor.fetchone()
        if result:
            player_id = result[0]
        else:
            name_parts = player_name.split()
            if len(name_parts) >= 2:
                cursor.execute("""
                    SELECT player_id FROM players
                    WHERE name ILIKE %s
                    LIMIT 1
                """, (f'%{name_parts[-1]}%',))
                result = cursor.fetchone()
                if result:
                    player_id = result[0]

            if not player_id:
                cursor.execute("""
                    INSERT INTO players (name)
                    VALUES (%s)
                    RETURNING player_id
                """, (player_name,))
                player_id = cursor.fetchone()[0]
                unmatched_players.append(player_name)

        appointment_id = None
        if club_id and match_id:
            cursor.execute("""
                SELECT m.match_date FROM matches m
                WHERE m.match_id = %s
            """, (match_id,))
            date_result = cursor.fetchone()
            if date_result:
                match_date = date_result[0].date()
                cursor.execute("""
                    SELECT appointment_id FROM appointments
                    WHERE club_id = %s
                    AND date_from <= %s
                    AND (date_to IS NULL OR date_to >= %s)
                """, (club_id, match_date, match_date))
                appt_result = cursor.fetchone()
                appointment_id = appt_result[0] if appt_result else None

        started = sub_in == 'start' if sub_in else False
        minutes_played = None
        if sub_in and sub_out:
            try:
                start = 0 if sub_in == 'start' else int(float(sub_in))
                end = 90 if sub_out == 'end' else int(float(sub_out))
                minutes_played = end - start
            except (ValueError, TypeError):
                pass

        formation_place_int = None
        if formation_place and formation_place != 'None':
            try:
                formation_place_int = int(formation_place)
            except (ValueError, TypeError):
                pass

        cursor.execute("""
            INSERT INTO clean_lineups (
                raw_lineup_id, match_id, club_id, player_id,
                appointment_id, player_name, team_name,
                is_home, position, role_group, formation_place,
                sub_in, sub_out, started, minutes_played,
                appearances, fouls_committed, fouls_suffered,
                own_goals, red_cards, sub_ins, yellow_cards,
                goals_conceded, saves, shots_faced,
                goal_assists, shots_on_target,
                total_goals, total_shots, offsides
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s
            )
        """, (
            raw_id, match_id, club_id, player_id,
            appointment_id, player_name, team_name,
            is_home, position, role_group, formation_place_int,
            sub_in, sub_out, started, minutes_played,
            appearances, fouls_committed, fouls_suffered,
            own_goals, red_cards, sub_ins, yellow_cards,
            goals_conceded, saves, shots_faced,
            goal_assists, shots_on_target,
            total_goals, total_shots, offsides
        ))
        inserted += 1

        if inserted % 1000 == 0:
            conn.commit()
            print(f"Inserted {inserted} records...")

    conn.commit()

    print(f"\nNew players created: {len(unmatched_players)}")
    cursor.close()
    conn.close()
    print(f"\nDone. Inserted: {inserted}, Skipped: {skipped}")


if __name__ == "__main__":
    clean_lineups()