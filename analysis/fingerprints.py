import psycopg2
from config import DB_CONFIG


def create_manager_fingerprint_view():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("DROP VIEW IF EXISTS manager_fingerprint CASCADE")

    cursor.execute("""
            CREATE VIEW manager_fingerprint AS
            SELECT
                a.appointment_id,
                mgr.name as manager_name,
                c.name as club_name,
                a.date_from,
                a.date_to,
                a.is_caretaker,
                COUNT(DISTINCT ps.match_id) as matches,
                COUNT(ps.id) as total_sequences,

                -- Territorial
                ROUND(AVG(ps.start_x)::numeric, 2) as avg_start_x,
                ROUND(AVG(ps.end_x)::numeric, 2) as avg_end_x,
                ROUND(
                    100.0 * COUNT(CASE WHEN ps.start_zone = 'defensive' THEN 1 END) 
                    / NULLIF(COUNT(ps.id), 0)::numeric, 2
                ) as pct_starts_defensive,
                ROUND(
                    100.0 * COUNT(CASE WHEN ps.start_zone = 'middle' THEN 1 END) 
                    / NULLIF(COUNT(ps.id), 0)::numeric, 2
                ) as pct_starts_middle,
                ROUND(
                    100.0 * COUNT(CASE WHEN ps.start_zone = 'final' THEN 1 END) 
                    / NULLIF(COUNT(ps.id), 0)::numeric, 2
                ) as pct_starts_final,

                -- Directness
                ROUND(AVG(ps.x_progression)::numeric, 2) as avg_x_progression,
                ROUND(AVG(ps.event_count)::numeric, 2) as avg_sequence_length,
                ROUND(AVG(ps.max_x)::numeric, 2) as avg_max_x,

                -- Width
                ROUND(AVG(ps.width)::numeric, 2) as avg_width,

                -- Press intensity
                ROUND(
                    100.0 * COUNT(CASE WHEN ps.start_zone = 'final' THEN 1 END)
                    / NULLIF(COUNT(ps.id), 0)::numeric, 2
                ) as press_recovery_rate,

                -- Creation
                ROUND(
                    100.0 * COUNT(CASE WHEN ps.ended_with_shot THEN 1 END)
                    / NULLIF(COUNT(ps.id), 0)::numeric, 2
                ) as shot_sequence_rate,
                ROUND(
                    100.0 * COUNT(CASE WHEN ps.ended_with_goal THEN 1 END)
                    / NULLIF(COUNT(ps.id), 0)::numeric, 2
                ) as goal_sequence_rate,
                ROUND(
                    COUNT(CASE WHEN ps.ended_with_shot THEN 1 END)::numeric
                    / NULLIF(COUNT(DISTINCT ps.match_id), 0), 2
                ) as shot_sequences_per_match,

                -- End zone distribution
                ROUND(
                    100.0 * COUNT(CASE WHEN ps.end_zone = 'final' THEN 1 END)
                    / NULLIF(COUNT(ps.id), 0)::numeric, 2
                ) as pct_ends_final

            FROM proc_sequences ps
            JOIN matches mat ON ps.match_id = mat.match_id
            JOIN match_context mc ON mat.match_id = mc.match_id
                AND mc.club_id = ps.club_id
            JOIN appointments a ON mc.appointment_id = a.appointment_id
            JOIN managers mgr ON a.manager_id = mgr.manager_id
            JOIN clubs c ON a.club_id = c.club_id
            WHERE a.is_caretaker = FALSE
            GROUP BY
                a.appointment_id, mgr.name, c.name,
                a.date_from, a.date_to, a.is_caretaker
            HAVING COUNT(DISTINCT ps.match_id) >= 5
        """)

    conn.commit()
    cursor.close()
    conn.close()
    print("Manager fingerprint view created")


def query_manager_fingerprint(manager_name=None):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    if manager_name:
        cursor.execute("""
            SELECT * FROM manager_fingerprint
            WHERE manager_name = %s
        """, (manager_name,))
    else:
        cursor.execute("SELECT * FROM manager_fingerprint")

    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()

    for row in rows:
        print("\n" + "="*50)
        for col, val in zip(columns, row):
            print(f"{col}: {val}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    create_manager_fingerprint_view()
    query_manager_fingerprint()