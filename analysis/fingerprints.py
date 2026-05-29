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

def create_player_fingerprint_view():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("DROP VIEW IF EXISTS player_fingerprint CASCADE")

    cursor.execute("""
        CREATE VIEW player_fingerprint AS
        WITH player_spatial AS (
            SELECT
                ce.player_id,
                mc.appointment_id,
                COUNT(*) as total_actions,
                ROUND(AVG(ce.x)::numeric, 2) as avg_x,
                ROUND(AVG(ce.y)::numeric, 2) as avg_y,
                ROUND(AVG(ce.x) FILTER (WHERE ce.x > 67)::numeric, 2) as avg_x_final_third,
                ROUND(
                    100.0 * COUNT(*) FILTER (WHERE ce.x > 67)
                    / NULLIF(COUNT(*), 0)::numeric, 2
                ) as pct_actions_final_third,
                ROUND(
                    100.0 * COUNT(*) FILTER (WHERE ce.x < 33)
                    / NULLIF(COUNT(*), 0)::numeric, 2
                ) as pct_actions_defensive_third,
                ROUND(
                    100.0 * COUNT(*) FILTER (
                        WHERE ce.type IN ('Tackle', 'Interception', 
                                         'BallRecovery', 'Challenge')
                        AND ce.x > 67
                    ) / NULLIF(COUNT(*), 0)::numeric, 2
                ) as pct_defensive_actions_high,
                ROUND(
                    100.0 * COUNT(*) FILTER (
                        WHERE ce.type IN ('Pass') 
                        AND ce.end_x > ce.x
                        AND ce.end_x IS NOT NULL
                    ) / NULLIF(
                        COUNT(*) FILTER (WHERE ce.type = 'Pass'), 0
                    )::numeric, 2
                ) as pct_progressive_passes
            FROM clean_events ce
            JOIN match_context mc ON ce.match_id = mc.match_id
                AND ce.club_id = mc.club_id
            WHERE ce.player_id IS NOT NULL
            AND ce.period IN ('FirstHalf', 'SecondHalf')
            GROUP BY ce.player_id, mc.appointment_id
        ),
        player_output AS (
            SELECT
                cpm.player_id,
                cpm.appointment_id,
                SUM(cpm.minutes) as total_minutes,
                COUNT(DISTINCT cpm.match_id) as matches,
                ROUND(AVG(cpm.xg_chain_per_90)::numeric, 4) as avg_xg_chain_per_90,
                ROUND(AVG(cpm.xg_buildup_per_90)::numeric, 4) as avg_xg_buildup_per_90,
                ROUND(AVG(cpm.xg_per_90)::numeric, 4) as avg_xg_per_90,
                ROUND(AVG(cpm.xa_per_90)::numeric, 4) as avg_xa_per_90,
                ROUND(
                    SUM(cpm.shots)::numeric * 90 
                    / NULLIF(SUM(cpm.minutes), 0), 4
                ) as shots_per_90,
                ROUND(
                    SUM(cpm.goals)::numeric * 90
                    / NULLIF(SUM(cpm.minutes), 0), 4
                ) as goals_per_90
            FROM clean_player_match_stats cpm
            WHERE cpm.player_id IS NOT NULL
            AND cpm.minutes > 0
            GROUP BY cpm.player_id, cpm.appointment_id
        )
        SELECT
            p.player_id,
            pl.name as player_name,
            a.appointment_id,
            mgr.name as manager_name,
            c.name as club_name,
            a.date_from,
            a.date_to,

            -- Playing time
            po.total_minutes,
            po.matches,

            -- Territorial
            ps.avg_x,
            ps.avg_y,
            ps.pct_actions_final_third,
            ps.pct_actions_defensive_third,

            -- Press contribution
            ps.pct_defensive_actions_high,

            -- Directness
            ps.pct_progressive_passes,

            -- Output quality
            po.avg_xg_per_90,
            po.avg_xa_per_90,
            po.avg_xg_chain_per_90,
            po.avg_xg_buildup_per_90,
            po.shots_per_90,
            po.goals_per_90

        FROM player_spatial ps
        JOIN player_output po ON ps.player_id = po.player_id
            AND ps.appointment_id = po.appointment_id
        JOIN players pl ON ps.player_id = pl.player_id
        JOIN appointments a ON ps.appointment_id = a.appointment_id
        JOIN managers mgr ON a.manager_id = mgr.manager_id
        JOIN clubs c ON a.club_id = c.club_id
        CROSS JOIN LATERAL (SELECT ps.player_id) p(player_id)
        WHERE po.total_minutes >= 90
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("Player fingerprint view created")


def query_player_fingerprint(player_name=None, manager_name=None):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    if player_name:
        cursor.execute("""
            SELECT * FROM player_fingerprint
            WHERE player_name ILIKE %s
            ORDER BY total_minutes DESC
        """, (f'%{player_name}%',))
    elif manager_name:
        cursor.execute("""
            SELECT * FROM player_fingerprint
            WHERE manager_name = %s
            ORDER BY total_minutes DESC
            LIMIT 20
        """, (manager_name,))
    else:
        cursor.execute("""
            SELECT * FROM player_fingerprint
            ORDER BY total_minutes DESC
            LIMIT 20
        """)

    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()

    for row in rows:
        print("\n" + "="*40)
        for col, val in zip(columns, row):
            print(f"{col}: {val}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    create_manager_fingerprint_view()
    create_player_fingerprint_view()
    query_player_fingerprint(manager_name="Mikel Arteta")