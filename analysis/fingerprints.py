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

            ROUND(AVG(ps.x_progression)::numeric, 2) as avg_x_progression,
            ROUND(AVG(ps.event_count)::numeric, 2) as avg_sequence_length,
            ROUND(AVG(ps.max_x)::numeric, 2) as avg_max_x,

            ROUND(AVG(ps.width)::numeric, 2) as avg_width,

            ROUND(
                100.0 * COUNT(CASE WHEN ps.start_zone = 'final' THEN 1 END)
                / NULLIF(COUNT(ps.id), 0)::numeric, 2
            ) as press_recovery_rate,

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
            AND NOT (ce.x >= 99 AND (ce.y <= 1 OR ce.y >= 99))
            AND NOT (ce.x <= 1 AND (ce.y <= 1 OR ce.y >= 99))
            AND ce.type NOT IN ('CornerAwarded')
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

            po.total_minutes,
            po.matches,

            ps.avg_x,
            ps.avg_y,
            ps.pct_actions_final_third,
            ps.pct_actions_defensive_third,

            ps.pct_defensive_actions_high,

            ps.pct_progressive_passes,

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


def create_role_demand_view():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("DROP VIEW IF EXISTS role_demand CASCADE")

    cursor.execute("""
        CREATE VIEW role_demand AS
        WITH player_position_match AS (
            SELECT
                cl.appointment_id,
                cl.player_id,
                cl.match_id,
                cl.formation_place,
                cl.position,
                cl.role_group,
                cl.minutes_played,
                cpm.xg,
                cpm.xa,
                cpm.xg_chain,
                cpm.xg_buildup,
                cpm.shots
            FROM clean_lineups cl
            JOIN clean_player_match_stats cpm
                ON cl.player_id = cpm.player_id
                AND cl.match_id = cpm.match_id
            WHERE cl.minutes_played > 0
            AND cl.formation_place IS NOT NULL
            AND cl.appointment_id IS NOT NULL
        ),
        player_position_spatial AS (
            SELECT
                mc.appointment_id,
                ce.player_id,
                ce.match_id,
                AVG(ce.x) as avg_x,
                AVG(ce.y) as avg_y,
                100.0 * COUNT(*) FILTER (WHERE ce.x > 67)
                    / NULLIF(COUNT(*), 0) as pct_final_third,
                100.0 * COUNT(*) FILTER (WHERE ce.x < 33)
                    / NULLIF(COUNT(*), 0) as pct_defensive_third,
                100.0 * COUNT(*) FILTER (
                    WHERE ce.type IN ('Tackle','Interception',
                                     'BallRecovery','Challenge')
                    AND ce.x > 67
                ) / NULLIF(COUNT(*), 0) as pct_high_defensive,
                100.0 * COUNT(*) FILTER (
                    WHERE ce.type = 'Pass'
                    AND ce.end_x > ce.x
                    AND ce.end_x IS NOT NULL
                ) / NULLIF(
                    COUNT(*) FILTER (WHERE ce.type = 'Pass'), 0
                ) as pct_progressive_passes
            FROM clean_events ce
            JOIN match_context mc ON ce.match_id = mc.match_id
                AND ce.club_id = mc.club_id
            WHERE ce.player_id IS NOT NULL
            AND ce.period IN ('FirstHalf', 'SecondHalf')
            AND NOT (ce.x >= 99 AND (ce.y <= 1 OR ce.y >= 99))
            AND NOT (ce.x <= 1 AND (ce.y <= 1 OR ce.y >= 99))
            AND ce.type NOT IN ('CornerAwarded')
            GROUP BY mc.appointment_id, ce.player_id, ce.match_id
        ),
        combined AS (
            SELECT
                ppm.appointment_id,
                ppm.formation_place,
                ppm.position,
                ppm.role_group,
                ppm.minutes_played,
                pps.avg_x,
                pps.avg_y,
                pps.pct_final_third,
                pps.pct_defensive_third,
                pps.pct_high_defensive,
                pps.pct_progressive_passes,
                ppm.xg,
                ppm.xa,
                ppm.xg_chain,
                ppm.xg_buildup,
                ppm.shots
            FROM player_position_match ppm
            JOIN player_position_spatial pps
                ON ppm.appointment_id = pps.appointment_id
                AND ppm.player_id = pps.player_id
                AND ppm.match_id = pps.match_id
        )
        SELECT
            a.appointment_id,
            mgr.name as manager_name,
            c.name as club_name,
            combined.formation_place,
            combined.role_group,

            COUNT(*) as appearances,
            SUM(combined.minutes_played) as total_minutes,

            ROUND(AVG(combined.avg_x)::numeric, 2) as demand_avg_x,
            ROUND(AVG(combined.avg_y)::numeric, 2) as demand_avg_y,
            ROUND(AVG(combined.pct_final_third)::numeric, 2) as demand_pct_final_third,
            ROUND(AVG(combined.pct_defensive_third)::numeric, 2) as demand_pct_defensive_third,
            ROUND(AVG(combined.pct_high_defensive)::numeric, 2) as demand_pct_high_defensive,
            ROUND(AVG(combined.pct_progressive_passes)::numeric, 2) as demand_pct_progressive,
            ROUND(AVG(combined.xg_chain)::numeric, 4) as demand_xg_chain,
            ROUND(AVG(combined.xg_buildup)::numeric, 4) as demand_xg_buildup,
            ROUND(AVG(combined.xg)::numeric, 4) as demand_xg,
            ROUND(AVG(combined.xa)::numeric, 4) as demand_xa,

            ROUND(STDDEV(combined.avg_x)::numeric, 2) as stddev_avg_x,
            ROUND(STDDEV(combined.pct_final_third)::numeric, 2) as stddev_pct_final_third,
            ROUND(STDDEV(combined.pct_progressive_passes)::numeric, 2) as stddev_pct_progressive,
            ROUND(STDDEV(combined.xg_chain)::numeric, 4) as stddev_xg_chain,

            ROUND(
                LEAST(1.0, COUNT(*)::numeric / 20)::numeric, 2
            ) as reliability_score

        FROM combined
        JOIN appointments a ON combined.appointment_id = a.appointment_id
        JOIN managers mgr ON a.manager_id = mgr.manager_id
        JOIN clubs c ON a.club_id = c.club_id
        GROUP BY
            a.appointment_id, mgr.name, c.name,
            combined.formation_place, combined.role_group
        HAVING COUNT(*) >= 3
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("Role demand view created")


def query_role_demand(manager_name, formation_place=None):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    if formation_place:
        cursor.execute("""
            SELECT * FROM role_demand
            WHERE manager_name = %s
            AND formation_place = %s
            ORDER BY appearances DESC
        """, (manager_name, formation_place))
    else:
        cursor.execute("""
            SELECT * FROM role_demand
            WHERE manager_name = %s
            ORDER BY formation_place, appearances DESC
        """, (manager_name,))

    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()

    for row in rows:
        print("\n" + "="*40)
        for col, val in zip(columns, row):
            print(f"{col}: {val}")

    cursor.close()
    conn.close()


def create_player_deviation_view():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("DROP VIEW IF EXISTS player_deviation CASCADE")

    cursor.execute("""
        CREATE VIEW player_deviation AS
        WITH player_match_metrics AS (
            SELECT
                cl.player_id,
                cl.match_id,
                cl.appointment_id,
                cl.formation_place,
                cl.role_group,
                cl.minutes_played,
                pps.avg_x,
                pps.avg_y,
                pps.pct_final_third,
                pps.pct_defensive_third,
                pps.pct_high_defensive,
                pps.pct_progressive_passes,
                cpm.xg_chain,
                cpm.xg_buildup,
                cpm.xg,
                cpm.xa
            FROM clean_lineups cl
            JOIN clean_player_match_stats cpm
                ON cl.player_id = cpm.player_id
                AND cl.match_id = cpm.match_id
            JOIN (
                SELECT
                    mc.appointment_id,
                    ce.player_id,
                    ce.match_id,
                    AVG(ce.x) as avg_x,
                    AVG(ce.y) as avg_y,
                    100.0 * COUNT(*) FILTER (WHERE ce.x > 67)
                        / NULLIF(COUNT(*), 0) as pct_final_third,
                    100.0 * COUNT(*) FILTER (WHERE ce.x < 33)
                        / NULLIF(COUNT(*), 0) as pct_defensive_third,
                    100.0 * COUNT(*) FILTER (
                        WHERE ce.type IN ('Tackle','Interception',
                                         'BallRecovery','Challenge')
                        AND ce.x > 67
                    ) / NULLIF(COUNT(*), 0) as pct_high_defensive,
                    100.0 * COUNT(*) FILTER (
                        WHERE ce.type = 'Pass'
                        AND ce.end_x > ce.x
                        AND ce.end_x IS NOT NULL
                    ) / NULLIF(
                        COUNT(*) FILTER (WHERE ce.type = 'Pass'), 0
                    ) as pct_progressive_passes
                FROM clean_events ce
                JOIN match_context mc ON ce.match_id = mc.match_id
                    AND ce.club_id = mc.club_id
                WHERE ce.player_id IS NOT NULL
                AND ce.period IN ('FirstHalf', 'SecondHalf')
                AND NOT (ce.x >= 99 AND (ce.y <= 1 OR ce.y >= 99))
                AND NOT (ce.x <= 1 AND (ce.y <= 1 OR ce.y >= 99))
                AND ce.type NOT IN ('CornerAwarded')
                GROUP BY mc.appointment_id, ce.player_id, ce.match_id
            ) pps ON cl.appointment_id = pps.appointment_id
                AND cl.player_id = pps.player_id
                AND cl.match_id = pps.match_id
            WHERE cl.minutes_played > 0
            AND cl.formation_place IS NOT NULL
            AND cl.appointment_id IS NOT NULL
        ),
        player_vs_demand AS (
            SELECT
                pmm.player_id,
                pmm.appointment_id,
                pmm.formation_place,
                pmm.role_group,
                pmm.minutes_played,

                -- Raw player metrics
                pmm.avg_x,
                pmm.avg_y,
                pmm.pct_final_third,
                pmm.pct_progressive_passes,
                pmm.pct_high_defensive,
                pmm.xg_chain,
                pmm.xg_buildup,
                pmm.xg,
                pmm.xa,

                -- Role demand for this slot
                rd.demand_avg_x,
                rd.demand_avg_y,
                rd.demand_pct_final_third,
                rd.demand_pct_progressive,
                rd.demand_pct_high_defensive,
                rd.demand_xg_chain,
                rd.demand_xg_buildup,
                rd.demand_xg,
                rd.demand_xa,
                rd.reliability_score,

                -- Deviations
                pmm.avg_x - rd.demand_avg_x as dev_avg_x,
                pmm.avg_y - rd.demand_avg_y as dev_avg_y,
                pmm.pct_final_third - rd.demand_pct_final_third as dev_pct_final_third,
                pmm.pct_progressive_passes - rd.demand_pct_progressive as dev_pct_progressive,
                pmm.pct_high_defensive - rd.demand_pct_high_defensive as dev_pct_high_defensive,
                pmm.xg_chain - rd.demand_xg_chain as dev_xg_chain,
                pmm.xg_buildup - rd.demand_xg_buildup as dev_xg_buildup,
                pmm.xg - rd.demand_xg as dev_xg,
                pmm.xa - rd.demand_xa as dev_xa

            FROM player_match_metrics pmm
            JOIN role_demand rd
                ON pmm.appointment_id = rd.appointment_id
                AND pmm.formation_place = rd.formation_place
                AND pmm.role_group = rd.role_group
        )
        SELECT
            pvd.player_id,
            pl.name as player_name,
            pvd.appointment_id,
            mgr.name as manager_name,
            c.name as club_name,
            pvd.formation_place,
            pvd.role_group,

            COUNT(*) as appearances,
            SUM(pvd.minutes_played) as total_minutes,

            -- Average deviations
            ROUND(AVG(pvd.dev_avg_x)::numeric, 2) as dev_avg_x,
            ROUND(AVG(pvd.dev_avg_y)::numeric, 2) as dev_avg_y,
            ROUND(AVG(pvd.dev_pct_final_third)::numeric, 2) as dev_pct_final_third,
            ROUND(AVG(pvd.dev_pct_progressive)::numeric, 2) as dev_pct_progressive,
            ROUND(AVG(pvd.dev_pct_high_defensive)::numeric, 2) as dev_pct_high_defensive,
            ROUND(AVG(pvd.dev_xg_chain)::numeric, 4) as dev_xg_chain,
            ROUND(AVG(pvd.dev_xg_buildup)::numeric, 4) as dev_xg_buildup,
            ROUND(AVG(pvd.dev_xg)::numeric, 4) as dev_xg,
            ROUND(AVG(pvd.dev_xa)::numeric, 4) as dev_xa,

            -- Stability of deviations
            ROUND(STDDEV(pvd.dev_avg_x)::numeric, 2) as stddev_dev_avg_x,
            ROUND(STDDEV(pvd.dev_xg_chain)::numeric, 4) as stddev_dev_xg_chain,

            -- Reliability
            ROUND(AVG(pvd.reliability_score)::numeric, 2) as role_reliability,
            ROUND(LEAST(1.0, COUNT(*)::numeric / 10)::numeric, 2) as player_reliability

        FROM player_vs_demand pvd
        JOIN players pl ON pvd.player_id = pl.player_id
        JOIN appointments a ON pvd.appointment_id = a.appointment_id
        JOIN managers mgr ON a.manager_id = mgr.manager_id
        JOIN clubs c ON a.club_id = c.club_id
        GROUP BY
            pvd.player_id, pl.name, pvd.appointment_id,
            mgr.name, c.name, pvd.formation_place, pvd.role_group
        HAVING COUNT(*) >= 3
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("Player deviation view created")


def query_player_deviation(player_name):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM player_deviation
        WHERE player_name ILIKE %s
        ORDER BY total_minutes DESC
    """, (f'%{player_name}%',))

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
    create_role_demand_view()
    create_player_deviation_view()
    query_player_deviation("Bruno Fernandes")