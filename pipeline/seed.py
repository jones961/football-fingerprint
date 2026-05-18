import psycopg2
from config import DB_CONFIG


def seed_reference_tables():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Clubs - four POC clubs plus placeholder for opponents
    clubs = [
        ('Arsenal', 'Arsenal', 'Arsenal', 'Arsenal'),
        ('Manchester United', 'Man Utd', 'Manchester United', 'Manchester United'),
        ('Chelsea', 'Chelsea', 'Chelsea', 'Chelsea'),
        ('Brentford', 'Brentford', 'Brentford', 'Brentford'),
    ]

    cursor.executemany("""
        INSERT INTO clubs (name, ws_name, espn_name, understat_name)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (name) DO NOTHING
    """, clubs)

    # Seasons
    seasons = [
        ('2020/21', '2021', '2020', 2020, 2021),
        ('2021/22', '2122', '2021', 2021, 2022),
        ('2022/23', '2223', '2022', 2022, 2023),
        ('2023/24', '2324', '2023', 2023, 2024),
        ('2024/25', '2425', '2024', 2024, 2025),
        ('2025/26', '2526', '2025', 2025, 2026),
    ]

    cursor.executemany("""
        INSERT INTO seasons (label, ws_code, understat_code, start_year, end_year)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (label) DO NOTHING
    """, seasons)

    conn.commit()
    cursor.close()
    conn.close()
    print("Reference tables seeded successfully")


if __name__ == "__main__":
    seed_reference_tables()