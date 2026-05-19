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


if __name__ == "__main__":
    load_all_espn_schedules()