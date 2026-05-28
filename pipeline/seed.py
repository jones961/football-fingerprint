import psycopg2
from config import DB_CONFIG


def seed_reference_tables():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Clubs
    clubs = [
        ('Arsenal', 'Arsenal', 'Arsenal', 'Arsenal'),
        ('Manchester United', 'Manchester United', 'Manchester United', 'Manchester United'),
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

    # Managers
    managers = [
        ('Mikel Arteta', 'Spanish'),
        ('Thomas Frank', 'Danish'),
        ('Keith Andrews', 'Irish'),
        ('Ole Gunnar Solskjaer', 'Norwegian'),
        ('Michael Carrick', 'English'),
        ('Ralf Rangnick', 'German'),
        ('Erik ten Hag', 'Dutch'),
        ('Ruud van Nistelrooy', 'Dutch'),
        ('Ruben Amorim', 'Portuguese'),
        ('Darren Fletcher', 'Scottish'),
        ('Thomas Tuchel', 'German'),
        ('Graham Potter', 'English'),
        ('Bruno Saltor', 'Spanish'),
        ('Frank Lampard', 'English'),
        ('Mauricio Pochettino', 'Argentine'),
        ('Enzo Maresca', 'Italian'),
        ('Calum McFarlane', 'English'),
        ('Liam Rosenior', 'English'),
    ]

    cursor.executemany("""
        INSERT INTO managers (name, nationality)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
    """, managers)

    conn.commit()

    # Appointments - need club and manager IDs so fetch them first
    def get_club_id(name):
        cursor.execute("SELECT club_id FROM clubs WHERE name = %s", (name,))
        return cursor.fetchone()[0]

    def get_manager_id(name):
        cursor.execute("SELECT manager_id FROM managers WHERE name = %s", (name,))
        return cursor.fetchone()[0]

    appointments = [
        # Arsenal
        (get_club_id('Arsenal'), get_manager_id('Mikel Arteta'), '2019-12-22', None, False),

        # Brentford
        (get_club_id('Brentford'), get_manager_id('Thomas Frank'), '2018-10-16', '2025-06-12', False),
        (get_club_id('Brentford'), get_manager_id('Keith Andrews'), '2025-06-27', None, False),

        # Manchester United
        (get_club_id('Manchester United'), get_manager_id('Ole Gunnar Solskjaer'), '2018-12-19', '2021-11-21', False),
        (get_club_id('Manchester United'), get_manager_id('Michael Carrick'), '2021-11-21', '2021-12-02', True),
        (get_club_id('Manchester United'), get_manager_id('Ralf Rangnick'), '2021-12-03', '2022-05-22', True),
        (get_club_id('Manchester United'), get_manager_id('Erik ten Hag'), '2022-05-23', '2024-10-28', False),
        (get_club_id('Manchester United'), get_manager_id('Ruud van Nistelrooy'), '2024-10-28', '2024-11-10', True),
        (get_club_id('Manchester United'), get_manager_id('Ruben Amorim'), '2024-11-11', '2026-01-05', False),
        (get_club_id('Manchester United'), get_manager_id('Darren Fletcher'), '2026-01-05', '2026-01-13', True),
        (get_club_id('Manchester United'), get_manager_id('Michael Carrick'), '2026-01-13', None, False),

        # Chelsea
        (get_club_id('Chelsea'), get_manager_id('Frank Lampard'), '2019-07-04', '2021-01-25', False),
        (get_club_id('Chelsea'), get_manager_id('Thomas Tuchel'), '2021-01-26', '2022-09-07', False),
        (get_club_id('Chelsea'), get_manager_id('Graham Potter'), '2022-09-08', '2023-04-02', False),
        (get_club_id('Chelsea'), get_manager_id('Bruno Saltor'), '2023-04-02', '2023-04-06', True),
        (get_club_id('Chelsea'), get_manager_id('Frank Lampard'), '2023-04-06', '2023-06-30', True),
        (get_club_id('Chelsea'), get_manager_id('Mauricio Pochettino'), '2023-07-01', '2024-05-21', False),
        (get_club_id('Chelsea'), get_manager_id('Enzo Maresca'), '2024-07-01', '2026-01-01', False),
        (get_club_id('Chelsea'), get_manager_id('Calum McFarlane'), '2026-01-01', '2026-01-08', True),
        (get_club_id('Chelsea'), get_manager_id('Liam Rosenior'), '2026-01-08', '2026-04-22', False),
        (get_club_id('Chelsea'), get_manager_id('Calum McFarlane'), '2026-04-22', None, True),
    ]

    cursor.executemany("""
        INSERT INTO appointments 
            (club_id, manager_id, date_from, date_to, is_caretaker)
        VALUES (%s, %s, %s, %s, %s)
    """, appointments)

    conn.commit()
    cursor.close()
    conn.close()
    print("Reference tables seeded successfully")


def populate_ws_team_ids():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Step 1 - handle known mismatches first
    known_mappings = [
        ('Man Utd', 32, 'Manchester United'),
        ('Man City', 167, 'Manchester City'),
        ('Sheff Utd', 163, 'Sheffield United'),
    ]

    for ws_event_name, ws_team_id, ws_name in known_mappings:
        cursor.execute("""
            UPDATE clubs
            SET ws_team_id = %s,
                ws_event_name = %s
            WHERE ws_name = %s
        """, (ws_team_id, ws_event_name, ws_name))
        if cursor.rowcount > 0:
            print(f"Manually mapped {ws_name} -> {ws_event_name} (ws_team_id: {ws_team_id})")

    conn.commit()

    # Step 2 - auto map remaining clubs from raw events
    cursor.execute("""
        SELECT DISTINCT team_name, ws_team_id
        FROM raw_ws_events
        WHERE team_name IS NOT NULL
        AND ws_team_id IS NOT NULL
        ORDER BY team_name
    """)

    mappings = cursor.fetchall()
    print(f"Found {len(mappings)} team mappings in raw events")

    updated = 0
    not_found = []

    for team_name, ws_team_id in mappings:
        # Skip already mapped clubs
        cursor.execute("""
            SELECT club_id FROM clubs 
            WHERE ws_team_id = %s
        """, (ws_team_id,))
        if cursor.fetchone():
            continue

        # Try matching on ws_name
        cursor.execute("""
            UPDATE clubs 
            SET ws_team_id = %s,
                ws_event_name = %s
            WHERE ws_name = %s
        """, (ws_team_id, team_name, team_name))

        if cursor.rowcount > 0:
            updated += 1
            continue

        # Try matching on name
        cursor.execute("""
            UPDATE clubs 
            SET ws_team_id = %s,
                ws_event_name = %s
            WHERE name = %s
        """, (ws_team_id, team_name, team_name))

        if cursor.rowcount > 0:
            updated += 1
            continue

        not_found.append((team_name, ws_team_id))

    conn.commit()

    print(f"Updated {updated} additional clubs with ws_team_id and ws_event_name")
    if not_found:
        print(f"Could not match: {not_found}")

    cursor.close()
    conn.close()

def fix_understat_names():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    corrections = [
        ('Wolves', 'Wolverhampton Wanderers'),
        ('Newcastle', 'Newcastle United'),
        ('Manchester United', 'Manchester United'),
        ('Manchester City', 'Manchester City'),
        ('Nottingham Forest', 'Nottingham Forest'),
        ('Tottenham', 'Tottenham'),
    ]

    for ws_name, understat_name in corrections:
        cursor.execute("""
            UPDATE clubs SET understat_name = %s
            WHERE ws_name = %s
        """, (understat_name, ws_name))
        if cursor.rowcount > 0:
            print(f"Updated understat_name for {ws_name} to {understat_name}")

    conn.commit()
    cursor.close()
    conn.close()


def populate_understat_names():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    understat_name_map = [
        ('Arsenal', 'Arsenal'),
        ('Aston Villa', 'Aston Villa'),
        ('Bournemouth', 'Bournemouth'),
        ('Brentford', 'Brentford'),
        ('Brighton', 'Brighton'),
        ('Burnley', 'Burnley'),
        ('Chelsea', 'Chelsea'),
        ('Crystal Palace', 'Crystal Palace'),
        ('Everton', 'Everton'),
        ('Fulham', 'Fulham'),
        ('Ipswich', 'Ipswich'),
        ('Leeds', 'Leeds'),
        ('Leicester', 'Leicester'),
        ('Liverpool', 'Liverpool'),
        ('Luton', 'Luton'),
        ('Manchester City', 'Manchester City'),
        ('Manchester United', 'Manchester United'),
        ('Newcastle', 'Newcastle United'),
        ('Norwich', 'Norwich'),
        ('Nottingham Forest', 'Nottingham Forest'),
        ('Sheffield United', 'Sheffield United'),
        ('Southampton', 'Southampton'),
        ('Sunderland', 'Sunderland'),
        ('Tottenham', 'Tottenham'),
        ('Watford', 'Watford'),
        ('West Bromwich Albion', 'West Bromwich Albion'),
        ('West Ham', 'West Ham'),
        ('Wolves', 'Wolverhampton Wanderers'),
    ]

    updated = 0
    for name, understat_name in understat_name_map:
        cursor.execute("""
            UPDATE clubs SET understat_name = %s
            WHERE name = %s
        """, (understat_name, name))
        if cursor.rowcount > 0:
            updated += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Updated understat_name for {updated} clubs")


if __name__ == "__main__":
    seed_reference_tables()
    populate_ws_team_ids()
    fix_understat_names()
    populate_understat_names()

if __name__ == "__main__":
    seed_reference_tables()
    populate_ws_team_ids()
    fix_understat_names()
    populate_understat_names()