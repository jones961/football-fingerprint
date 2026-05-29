import soccerdata as sd
import psycopg2
import math
from config import DB_CONFIG


def safe_float(val):
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def safe_int(val):
    if val is None:
        return None
    try:
        if math.isnan(float(val)):
            return None
        return int(val)
    except (TypeError, ValueError):
        return None


def load_espn_schedule(season_label, espn_format):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    espn = sd.ESPN(leagues="ENG-Premier League", seasons=espn_format)
    schedule = espn.read_schedule()

    inserted = 0
    skipped = 0

    for _, row in schedule.iterrows():
        cursor.execute("""
            INSERT INTO raw_espn_matches (
                espn_game_id, home_team, away_team,
                match_date, season_label
            ) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (espn_game_id) DO NOTHING
        """, (
            int(row['game_id']),
            row['home_team'],
            row['away_team'],
            row['date'],
            season_label,
        ))

        if cursor.rowcount > 0:
            inserted += 1
        else:
            skipped += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Season {season_label}: inserted {inserted}, skipped {skipped}")


def load_all_espn_schedules():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("TRUNCATE TABLE raw_espn_matches")
    conn.commit()
    cursor.close()
    conn.close()
    print("Cleared raw_espn_matches")

    season_formats = [
        ("2021/22", "21-22"),
        ("2022/23", 2022),
        ("2023/24", 2023),
        ("2024/25", 2024),
        ("2025/26", 2025),
    ]

    for season_label, espn_format in season_formats:
        load_espn_schedule(season_label, espn_format)

def load_espn_lineups_for_matched_matches():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT match_id, espn_game_id
        FROM matches
        WHERE espn_game_id IS NOT NULL
        ORDER BY match_id
    """)

    matches = cursor.fetchall()
    print(f"Found {len(matches)} matches with ESPN game IDs")

    season_cache = {}

    total_inserted = 0
    total_skipped = 0

    for match_id, espn_game_id in matches:

        # Check if already loaded
        cursor.execute("""
            SELECT COUNT(*) FROM raw_espn_lineups
            WHERE match_id = %s
        """, (match_id,))
        if cursor.fetchone()[0] > 0:
            total_skipped += 1
            continue

        # Get season for this match
        cursor.execute("""
            SELECT s.label FROM matches m
            JOIN seasons s ON m.season_id = s.season_id
            WHERE m.match_id = %s
        """, (match_id,))
        season_label = cursor.fetchone()[0]

        # Get or create ESPN instance for this season
        if season_label not in season_cache:
            season_map = {
                '2021/22': '21-22',
                '2022/23': 2022,
                '2023/24': 2023,
                '2024/25': 2024,
                '2025/26': 2025,
            }
            espn_format = season_map.get(season_label)
            if not espn_format:
                print(f"No ESPN format for season {season_label}, skipping")
                total_skipped += 1
                continue
            season_cache[season_label] = sd.ESPN(
                leagues="ENG-Premier League",
                seasons=espn_format
            )

        espn = season_cache[season_label]

        try:
            lineups = espn.read_lineup(match_id=int(espn_game_id))
        except Exception as e:
            print(f"Failed to pull lineup for ESPN match {espn_game_id}: {e}")
            total_skipped += 1
            continue

        inserted = 0
        for (league, season, game, team, player), row in lineups.iterrows():
            cursor.execute("""
                INSERT INTO raw_espn_lineups (
                    match_id, espn_game_id, player_name, team_name,
                    is_home, position, formation_place, sub_in, sub_out,
                    appearances, fouls_committed, fouls_suffered, own_goals,
                    red_cards, sub_ins, yellow_cards, goals_conceded,
                    saves, shots_faced, goal_assists, shots_on_target,
                    total_goals, total_shots, offsides
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                match_id,
                espn_game_id,
                player,
                team,
                bool(row.get('is_home')),
                row.get('position'),
                row.get('formation_place'),
                str(row.get('sub_in')) if row.get('sub_in') is not None else None,
                str(row.get('sub_out')) if row.get('sub_out') is not None else None,
                safe_float(row.get('appearances')),
                safe_float(row.get('fouls_committed')),
                safe_float(row.get('fouls_suffered')),
                safe_float(row.get('own_goals')),
                safe_float(row.get('red_cards')),
                safe_float(row.get('sub_ins')),
                safe_float(row.get('yellow_cards')),
                safe_float(row.get('goals_conceded')),
                safe_float(row.get('saves')),
                safe_float(row.get('shots_faced')),
                safe_float(row.get('goal_assists')),
                safe_float(row.get('shots_on_target')),
                safe_float(row.get('total_goals')),
                safe_float(row.get('total_shots')),
                safe_float(row.get('offsides')),
            ))
            inserted += 1

        conn.commit()
        total_inserted += inserted
        if total_inserted % 500 == 0 and total_inserted > 0:
            print(f"Inserted {total_inserted} lineup rows so far...")

    cursor.close()
    conn.close()
    print(f"\nDone. Inserted: {total_inserted}, Skipped: {total_skipped}")


if __name__ == "__main__":
    load_all_espn_schedules()