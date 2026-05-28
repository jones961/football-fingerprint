import psycopg2
from config import DB_CONFIG


def match_understat_to_matches():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            understat_game_id,
            home_team,
            away_team,
            match_date,
            season_label
        FROM raw_understat_schedule
        WHERE understat_game_id IS NOT NULL
    """)

    schedule_rows = cursor.fetchall()
    print(f"Processing {len(schedule_rows)} Understat schedule records")

    matched = 0
    unmatched = []

    for understat_game_id, home_team, away_team, match_date, season_label in schedule_rows:

        # Already matched
        cursor.execute("""
            SELECT match_id FROM matches
            WHERE understat_game_id = %s
        """, (understat_game_id,))
        if cursor.fetchone():
            matched += 1
            continue

        # Convert season label to our format
        season_label_short = season_label[:4] + '/' + season_label[7:9]

        # Try matching by date and team names
        match_date_only = match_date.date() if hasattr(match_date, 'date') else match_date

        cursor.execute("""
                    SELECT DISTINCT m.match_id
                    FROM matches m
                    JOIN match_context mc ON m.match_id = mc.match_id
                    JOIN clubs tracked_club ON mc.club_id = tracked_club.club_id
                    JOIN clubs opp_club ON m.opponent_id = opp_club.club_id
                    WHERE DATE(m.match_date) = %s
                    AND (
                        (mc.venue = 'home' AND (
                            tracked_club.understat_name = %s
                            OR tracked_club.name = %s
                        ))
                        OR
                        (mc.venue = 'away' AND (
                            opp_club.understat_name = %s
                            OR opp_club.name = %s
                        ))
                    )
                """, (
            match_date_only,
            home_team, home_team,
            home_team, home_team
        ))

        result = cursor.fetchone()

        if result:
            match_id = result[0]
            cursor.execute("""
                UPDATE matches
                SET understat_game_id = %s
                WHERE match_id = %s
            """, (understat_game_id, match_id))
            matched += 1
        else:
            unmatched.append((understat_game_id, home_team, away_team, match_date_only))

    conn.commit()

    if unmatched:
        print(f"\nUnmatched records: {len(unmatched)}")
        for row in unmatched[:10]:
            print(f"  {row}")

    cursor.close()
    conn.close()
    print(f"\nMatched: {matched} out of {len(schedule_rows)}")


if __name__ == "__main__":
    match_understat_to_matches()