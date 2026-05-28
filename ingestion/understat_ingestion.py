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


def load_understat_player_stats(season_label, understat_code):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    understat = sd.Understat(
        leagues="ENG-Premier League",
        seasons=season_label
    )

    player_stats = understat.read_player_season_stats()

    inserted = 0
    skipped = 0

    for (league, season, team, player), row in player_stats.iterrows():

        cursor.execute("""
            SELECT COUNT(*) FROM raw_understat_player_stats
            WHERE season_label = %s
            AND team_name = %s
            AND player_name = %s
        """, (season_label, team, player))

        if cursor.fetchone()[0] > 0:
            skipped += 1
            continue

        cursor.execute("""
            INSERT INTO raw_understat_player_stats (
                season_label, team_name, player_name,
                understat_player_id, understat_team_id,
                position, matches, minutes,
                goals, np_goals, assists, shots, key_passes,
                yellow_cards, red_cards,
                xg, np_xg, xa, xg_chain, xg_buildup
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
        """, (
            season_label,
            team,
            player,
            safe_int(row.get('player_id')),
            safe_int(row.get('team_id')),
            row.get('position'),
            safe_int(row.get('matches')),
            safe_int(row.get('minutes')),
            safe_int(row.get('goals')),
            safe_int(row.get('np_goals')),
            safe_int(row.get('assists')),
            safe_int(row.get('shots')),
            safe_int(row.get('key_passes')),
            safe_int(row.get('yellow_cards')),
            safe_int(row.get('red_cards')),
            safe_float(row.get('xg')),
            safe_float(row.get('np_xg')),
            safe_float(row.get('xa')),
            safe_float(row.get('xg_chain')),
            safe_float(row.get('xg_buildup')),
        ))
        inserted += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Season {season_label}: inserted {inserted}, skipped {skipped}")


def load_all_understat_stats():
    seasons = [
        ("2020/2021", "2020"),
        ("2021/2022", "2021"),
        ("2022/2023", "2022"),
        ("2023/2024", "2023"),
        ("2024/2025", "2024"),
        ("2025/2026", "2025"),
    ]

    for season_label, understat_code in seasons:
        print(f"Pulling {season_label}...")
        load_understat_player_stats(season_label, understat_code)

def load_understat_player_match_stats(season_label):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    understat = sd.Understat(
        leagues="ENG-Premier League",
        seasons=season_label
    )

    player_match_stats = understat.read_player_match_stats()

    inserted = 0
    skipped = 0

    for (league, season, game, team, player), row in player_match_stats.iterrows():

        cursor.execute("""
            SELECT id FROM raw_understat_player_match_stats
            WHERE season_label = %s
            AND understat_game_id = %s
            AND understat_player_id = %s
        """, (
            season_label,
            safe_int(row.get('game_id')),
            safe_int(row.get('player_id'))
        ))

        if cursor.fetchone():
            skipped += 1
            continue

        cursor.execute("""
            INSERT INTO raw_understat_player_match_stats (
                season_label, understat_game_id, understat_team_id,
                understat_player_id, player_name, team_name,
                position, position_id, minutes, goals, own_goals,
                shots, xg, xa, xg_chain, xg_buildup
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (season_label, understat_game_id, understat_player_id)
            DO NOTHING
        """, (
            season_label,
            safe_int(row.get('game_id')),
            safe_int(row.get('team_id')),
            safe_int(row.get('player_id')),
            player,
            team,
            row.get('position'),
            safe_int(row.get('position_id')),
            safe_int(row.get('minutes')),
            safe_int(row.get('goals')),
            safe_int(row.get('own_goals')),
            safe_int(row.get('shots')),
            safe_float(row.get('xg')),
            safe_float(row.get('xa')),
            safe_float(row.get('xg_chain')),
            safe_float(row.get('xg_buildup')),
        ))

        if cursor.rowcount > 0:
            inserted += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Season {season_label}: inserted {inserted}, skipped {skipped}")


def load_all_understat_match_stats():
    seasons = [
        "2020/2021",
        "2021/2022",
        "2022/2023",
        "2023/2024",
        "2024/2025",
        "2025/2026",
    ]

    for season_label in seasons:
        print(f"Pulling {season_label}...")
        load_understat_player_match_stats(season_label)

if __name__ == "__main__":
    load_all_understat_stats()