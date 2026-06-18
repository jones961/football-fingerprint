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
        AND ps.event_count >= 3
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


def create_role_group_demand_view():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("DROP VIEW IF EXISTS role_group_demand CASCADE")

    cursor.execute("""
        CREATE VIEW role_group_demand AS
        SELECT
            appointment_id,
            manager_name,
            club_name,
            role_group,

            -- Weighted averages across formation places
            ROUND(
                SUM(demand_avg_x * appearances) 
                / NULLIF(SUM(appearances), 0)::numeric, 2
            ) as demand_avg_x,
            ROUND(
                SUM(demand_avg_y * appearances)
                / NULLIF(SUM(appearances), 0)::numeric, 2
            ) as demand_avg_y,
            ROUND(
                SUM(demand_pct_final_third * appearances)
                / NULLIF(SUM(appearances), 0)::numeric, 2
            ) as demand_pct_final_third,
            ROUND(
                SUM(demand_pct_defensive_third * appearances)
                / NULLIF(SUM(appearances), 0)::numeric, 2
            ) as demand_pct_defensive_third,
            ROUND(
                SUM(demand_pct_high_defensive * appearances)
                / NULLIF(SUM(appearances), 0)::numeric, 2
            ) as demand_pct_high_defensive,
            ROUND(
                SUM(demand_pct_progressive * appearances)
                / NULLIF(SUM(appearances), 0)::numeric, 2
            ) as demand_pct_progressive,
            ROUND(
                SUM(demand_xg_chain * appearances)
                / NULLIF(SUM(appearances), 0)::numeric, 4
            ) as demand_xg_chain,
            ROUND(
                SUM(demand_xg_buildup * appearances)
                / NULLIF(SUM(appearances), 0)::numeric, 4
            ) as demand_xg_buildup,
            ROUND(
                SUM(demand_xg * appearances)
                / NULLIF(SUM(appearances), 0)::numeric, 4
            ) as demand_xg,
            ROUND(
                SUM(demand_xa * appearances)
                / NULLIF(SUM(appearances), 0)::numeric, 4
            ) as demand_xa,

            SUM(appearances) as total_appearances,
            ROUND(AVG(reliability_score)::numeric, 2) as reliability_score

        FROM role_demand
        GROUP BY appointment_id, manager_name, club_name, role_group
        HAVING SUM(appearances) >= 5
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("Role group demand view created")


def create_player_role_deviation_view():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("DROP VIEW IF EXISTS player_role_deviation CASCADE")

    cursor.execute("""
        CREATE VIEW player_role_deviation AS
        SELECT
            player_id,
            player_name,
            appointment_id,
            manager_name,
            club_name,
            role_group,

            SUM(appearances) as total_appearances,
            SUM(total_minutes) as total_minutes,

            -- Weighted average deviations
            ROUND(
                SUM(dev_avg_x * appearances)
                / NULLIF(SUM(appearances), 0)::numeric, 2
            ) as dev_avg_x,
            ROUND(
                SUM(dev_avg_y * appearances)
                / NULLIF(SUM(appearances), 0)::numeric, 2
            ) as dev_avg_y,
            ROUND(
                SUM(dev_pct_final_third * appearances)
                / NULLIF(SUM(appearances), 0)::numeric, 2
            ) as dev_pct_final_third,
            ROUND(
                SUM(dev_pct_progressive * appearances)
                / NULLIF(SUM(appearances), 0)::numeric, 2
            ) as dev_pct_progressive,
            ROUND(
                SUM(dev_pct_high_defensive * appearances)
                / NULLIF(SUM(appearances), 0)::numeric, 2
            ) as dev_pct_high_defensive,
            ROUND(
                SUM(dev_xg_chain * appearances)
                / NULLIF(SUM(appearances), 0)::numeric, 4
            ) as dev_xg_chain,
            ROUND(
                SUM(dev_xg_buildup * appearances)
                / NULLIF(SUM(appearances), 0)::numeric, 4
            ) as dev_xg_buildup,
            ROUND(
                SUM(dev_xg * appearances)
                / NULLIF(SUM(appearances), 0)::numeric, 4
            ) as dev_xg,
            ROUND(
                SUM(dev_xa * appearances)
                / NULLIF(SUM(appearances), 0)::numeric, 4
            ) as dev_xa,

            ROUND(AVG(role_reliability)::numeric, 2) as role_reliability,
            ROUND(AVG(player_reliability)::numeric, 2) as player_reliability

        FROM player_deviation
        GROUP BY
            player_id, player_name, appointment_id,
            manager_name, club_name, role_group
        HAVING SUM(appearances) >= 3
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("Player role deviation view created")


def create_compatibility_score_view():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("DROP VIEW IF EXISTS compatibility_score CASCADE")

    cursor.execute("""
        CREATE VIEW compatibility_score AS
        WITH cross_system_baseline AS (
            SELECT
                role_group,
                AVG(demand_avg_x) as mean_demand_avg_x,
                AVG(demand_pct_final_third) as mean_demand_pct_final_third,
                AVG(demand_pct_progressive) as mean_demand_pct_progressive,
                AVG(demand_pct_high_defensive) as mean_demand_pct_high_defensive,
                AVG(demand_xg_chain) as mean_demand_xg_chain,
                AVG(demand_xg_buildup) as mean_demand_xg_buildup,
                AVG(demand_xg) as mean_demand_xg,
                AVG(demand_xa) as mean_demand_xa,
                STDDEV(demand_avg_x) as std_avg_x,
                STDDEV(demand_pct_final_third) as std_pct_final_third,
                STDDEV(demand_pct_progressive) as std_pct_progressive,
                STDDEV(demand_pct_high_defensive) as std_pct_high_defensive,
                STDDEV(demand_xg_chain) as std_xg_chain,
                STDDEV(demand_xg_buildup) as std_xg_buildup,
                STDDEV(demand_xg) as std_xg,
                STDDEV(demand_xa) as std_xa
            FROM role_group_demand
            GROUP BY role_group
        ),
        target_premium AS (
            SELECT
                rgd.appointment_id,
                rgd.manager_name,
                rgd.club_name,
                rgd.role_group,
                rgd.total_appearances,
                rgd.reliability_score,

                -- How much does this manager demand above/below average
                -- Normalised by cross-system std dev
                CASE WHEN csb.std_avg_x > 0
                    THEN (rgd.demand_avg_x - csb.mean_demand_avg_x) / csb.std_avg_x
                    ELSE 0 END as premium_avg_x,
                CASE WHEN csb.std_pct_final_third > 0
                    THEN (rgd.demand_pct_final_third - csb.mean_demand_pct_final_third) / csb.std_pct_final_third
                    ELSE 0 END as premium_pct_final_third,
                CASE WHEN csb.std_pct_progressive > 0
                    THEN (rgd.demand_pct_progressive - csb.mean_demand_pct_progressive) / csb.std_pct_progressive
                    ELSE 0 END as premium_pct_progressive,
                CASE WHEN csb.std_pct_high_defensive > 0
                    THEN (rgd.demand_pct_high_defensive - csb.mean_demand_pct_high_defensive) / csb.std_pct_high_defensive
                    ELSE 0 END as premium_pct_high_defensive,
                CASE WHEN csb.std_xg_chain > 0
                    THEN (rgd.demand_xg_chain - csb.mean_demand_xg_chain) / csb.std_xg_chain
                    ELSE 0 END as premium_xg_chain,
                CASE WHEN csb.std_xg_buildup > 0
                    THEN (rgd.demand_xg_buildup - csb.mean_demand_xg_buildup) / csb.std_xg_buildup
                    ELSE 0 END as premium_xg_buildup,
                CASE WHEN csb.std_xg > 0
                    THEN (rgd.demand_xg - csb.mean_demand_xg) / csb.std_xg
                    ELSE 0 END as premium_xg,
                CASE WHEN csb.std_xa > 0
                    THEN (rgd.demand_xa - csb.mean_demand_xa) / csb.std_xa
                    ELSE 0 END as premium_xa
            FROM role_group_demand rgd
            JOIN cross_system_baseline csb ON rgd.role_group = csb.role_group
        ),
        player_normalised AS (
            SELECT
                prd.player_id,
                prd.player_name,
                prd.appointment_id as source_appointment_id,
                prd.manager_name as source_manager,
                prd.club_name as source_club,
                prd.role_group,
                prd.total_appearances as source_appearances,
                prd.player_reliability,
                prd.role_reliability,

                -- Normalise player deviations by cross-system std
                CASE WHEN csb.std_avg_x > 0
                    THEN prd.dev_avg_x / csb.std_avg_x
                    ELSE 0 END as norm_dev_avg_x,
                CASE WHEN csb.std_pct_final_third > 0
                    THEN prd.dev_pct_final_third / csb.std_pct_final_third
                    ELSE 0 END as norm_dev_pct_final_third,
                CASE WHEN csb.std_pct_progressive > 0
                    THEN prd.dev_pct_progressive / csb.std_pct_progressive
                    ELSE 0 END as norm_dev_pct_progressive,
                CASE WHEN csb.std_pct_high_defensive > 0
                    THEN prd.dev_pct_high_defensive / csb.std_pct_high_defensive
                    ELSE 0 END as norm_dev_pct_high_defensive,
                CASE WHEN csb.std_xg_chain > 0
                    THEN prd.dev_xg_chain / csb.std_xg_chain
                    ELSE 0 END as norm_dev_xg_chain,
                CASE WHEN csb.std_xg_buildup > 0
                    THEN prd.dev_xg_buildup / csb.std_xg_buildup
                    ELSE 0 END as norm_dev_xg_buildup,
                CASE WHEN csb.std_xg > 0
                    THEN prd.dev_xg / csb.std_xg
                    ELSE 0 END as norm_dev_xg,
                CASE WHEN csb.std_xa > 0
                    THEN prd.dev_xa / csb.std_xa
                    ELSE 0 END as norm_dev_xa

            FROM player_role_deviation prd
            JOIN cross_system_baseline csb ON prd.role_group = csb.role_group
        )
        SELECT
            pn.player_id,
            pn.player_name,
            pn.source_manager,
            pn.source_club,
            pn.role_group,
            pn.source_appearances,
            tp.manager_name as target_manager,
            tp.club_name as target_club,
            tp.total_appearances as target_role_appearances,

            -- Compatibility score per dimension
            -- Positive = player tendency aligns with target system need
            -- Negative = player tendency conflicts with target system need
            ROUND((pn.norm_dev_avg_x * tp.premium_avg_x)::numeric, 3)
                as compat_territorial,
            ROUND((pn.norm_dev_pct_final_third * tp.premium_pct_final_third)::numeric, 3)
                as compat_final_third,
            ROUND((pn.norm_dev_pct_progressive * tp.premium_pct_progressive)::numeric, 3)
                as compat_progressive,
            ROUND((pn.norm_dev_pct_high_defensive * tp.premium_pct_high_defensive)::numeric, 3)
                as compat_press,
            ROUND((pn.norm_dev_xg_chain * tp.premium_xg_chain)::numeric, 3)
                as compat_xg_chain,
            ROUND((pn.norm_dev_xg_buildup * tp.premium_xg_buildup)::numeric, 3)
                as compat_xg_buildup,
            ROUND((pn.norm_dev_xg * tp.premium_xg)::numeric, 3)
                as compat_xg,
            ROUND((pn.norm_dev_xa * tp.premium_xa)::numeric, 3)
                as compat_xa,

            -- Overall compatibility score
            ROUND((
                (pn.norm_dev_avg_x * tp.premium_avg_x) +
                (pn.norm_dev_pct_final_third * tp.premium_pct_final_third) +
                (pn.norm_dev_pct_progressive * tp.premium_pct_progressive) +
                (pn.norm_dev_pct_high_defensive * tp.premium_pct_high_defensive) +
                (pn.norm_dev_xg_chain * tp.premium_xg_chain) +
                (pn.norm_dev_xg_buildup * tp.premium_xg_buildup) +
                (pn.norm_dev_xg * tp.premium_xg) +
                (pn.norm_dev_xa * tp.premium_xa)
            )::numeric / 8, 3) as compatibility_score,

            -- Reliability weights
            ROUND((pn.player_reliability * pn.role_reliability * tp.reliability_score)::numeric, 3)
                as combined_reliability

        FROM player_normalised pn
        JOIN target_premium tp ON pn.role_group = tp.role_group
        WHERE pn.source_appointment_id != tp.appointment_id
        AND tp.reliability_score >= 0.5
        AND pn.player_reliability >= 0.5
        AND pn.role_reliability >= 0.5
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("Compatibility score view created")


def query_compatibility(player_name, target_manager):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            player_name,
            source_manager,
            role_group,
            source_appearances,
            target_manager,
            compatibility_score,
            combined_reliability,
            compat_territorial,
            compat_progressive,
            compat_press,
            compat_xg_chain,
            compat_xa
        FROM compatibility_score
        WHERE player_name ILIKE %s
        AND target_manager = %s
        ORDER BY compatibility_score DESC
    """, (f'%{player_name}%', target_manager))

    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()

    for row in rows:
        print("\n" + "="*40)
        for col, val in zip(columns, row):
            print(f"{col}: {val}")

    cursor.close()
    conn.close()


def create_defensive_fingerprint_view():
    """
    Defensive component of the player fingerprint.

    Keyed on (player_id, appointment_id) — IDENTICAL grain to player_fingerprint
    — so it joins straight onto the existing fingerprint stack.

    All action metrics are per-90, divided by minutes from clean_player_match_stats
    (the SAME minutes source player_fingerprint uses, so denominators are consistent
    across the whole fingerprint layer).

    Carries total_minutes, matches, and minutes_per_game as the reliability /
    sub-detector lens: per-90 hides sample size, so these tell you how much to
    trust the rates and whether the player is a starter or mostly a sub.

    Two-sided types are handled with is_successful:
      aerial:  is_successful = TRUE  -> won
      tackling: Tackle won vs Challenge (beaten) -> tackle success rate
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("DROP VIEW IF EXISTS defensive_fingerprint CASCADE")

    cursor.execute("""
        CREATE VIEW defensive_fingerprint AS
        WITH minutes_by_player AS (
            SELECT
                player_id,
                appointment_id,
                SUM(minutes) AS total_minutes,
                COUNT(DISTINCT match_id) AS matches
            FROM clean_player_match_stats
            WHERE minutes > 0
            GROUP BY player_id, appointment_id
        ),
        def_by_player AS (
            SELECT
                pda.player_id,
                mc.appointment_id,

                COUNT(*) AS total_def_actions,

                -- Territory: where this player defends
                ROUND(AVG(pda.x)::numeric, 2) AS avg_def_x,
                ROUND(
                    100.0 * COUNT(*) FILTER (WHERE pda.x > 67)
                    / NULLIF(COUNT(*), 0)::numeric, 2
                ) AS pct_def_actions_high,

                -- Category mix (share of this player's defending by type)
                ROUND(
                    100.0 * COUNT(*) FILTER (WHERE pda.defensive_category = 'ball_winning')
                    / NULLIF(COUNT(*), 0)::numeric, 2
                ) AS pct_ball_winning,
                ROUND(
                    100.0 * COUNT(*) FILTER (WHERE pda.defensive_category = 'tackling')
                    / NULLIF(COUNT(*), 0)::numeric, 2
                ) AS pct_tackling,
                ROUND(
                    100.0 * COUNT(*) FILTER (WHERE pda.defensive_category = 'clearing')
                    / NULLIF(COUNT(*), 0)::numeric, 2
                ) AS pct_clearing,
                ROUND(
                    100.0 * COUNT(*) FILTER (WHERE pda.defensive_category = 'aerial')
                    / NULLIF(COUNT(*), 0)::numeric, 2
                ) AS pct_aerial,
                ROUND(
                    100.0 * COUNT(*) FILTER (WHERE pda.defensive_category = 'blocking')
                    / NULLIF(COUNT(*), 0)::numeric, 2
                ) AS pct_blocking,

                -- Raw counts for the per-90 calc (done after join to minutes)
                COUNT(*) FILTER (WHERE pda.defensive_category = 'ball_winning') AS n_ball_winning,
                COUNT(*) FILTER (WHERE pda.defensive_category = 'tackling') AS n_tackling,
                COUNT(*) FILTER (WHERE pda.defensive_category = 'clearing') AS n_clearing,
                COUNT(*) FILTER (WHERE pda.defensive_category = 'blocking') AS n_blocking,

                -- Quality: tackle success (Tackle won vs total tackle attempts incl. Challenge)
                ROUND(
                    100.0 * COUNT(*) FILTER (WHERE pda.type = 'Tackle' AND pda.is_successful)
                    / NULLIF(COUNT(*) FILTER (
                        WHERE pda.type IN ('Tackle', 'Challenge')
                    ), 0)::numeric, 2
                ) AS tackle_success_pct,

                -- Quality: aerial win rate (won vs all aerials by this player)
                ROUND(
                    100.0 * COUNT(*) FILTER (WHERE pda.defensive_category = 'aerial' AND pda.is_successful)
                    / NULLIF(COUNT(*) FILTER (
                        WHERE pda.defensive_category = 'aerial'
                    ), 0)::numeric, 2
                ) AS aerial_win_pct

            FROM proc_defensive_actions pda
            JOIN match_context mc
                ON pda.match_id = mc.match_id
                AND pda.club_id = mc.club_id
            WHERE pda.player_id IS NOT NULL
            GROUP BY pda.player_id, mc.appointment_id
        )
        SELECT
            d.player_id,
            pl.name AS player_name,
            d.appointment_id,
            mgr.name AS manager_name,
            c.name AS club_name,

            m.total_minutes,
            m.matches,
            ROUND(m.total_minutes::numeric / NULLIF(m.matches, 0), 1) AS minutes_per_game,

            -- Overall defensive workload, per 90
            ROUND(d.total_def_actions::numeric * 90 / NULLIF(m.total_minutes, 0), 2)
                AS def_actions_per_90,

            -- Per-90 by category
            ROUND(d.n_ball_winning::numeric * 90 / NULLIF(m.total_minutes, 0), 2)
                AS ball_winning_per_90,
            ROUND(d.n_tackling::numeric * 90 / NULLIF(m.total_minutes, 0), 2)
                AS tackling_per_90,
            ROUND(d.n_clearing::numeric * 90 / NULLIF(m.total_minutes, 0), 2)
                AS clearing_per_90,
            ROUND(d.n_blocking::numeric * 90 / NULLIF(m.total_minutes, 0), 2)
                AS blocking_per_90,

            -- Territory
            d.avg_def_x,
            d.pct_def_actions_high,

            -- Category mix (shares)
            d.pct_ball_winning,
            d.pct_tackling,
            d.pct_clearing,
            d.pct_aerial,
            d.pct_blocking,

            -- Quality
            d.tackle_success_pct,
            d.aerial_win_pct,

            -- Reliability: low when minutes are thin (per-90 not yet trustworthy)
            ROUND(LEAST(1.0, m.total_minutes::numeric / 900)::numeric, 2) AS reliability_score

        FROM def_by_player d
        JOIN minutes_by_player m
            ON d.player_id = m.player_id
            AND d.appointment_id = m.appointment_id
        JOIN players pl ON d.player_id = pl.player_id
        JOIN appointments a ON d.appointment_id = a.appointment_id
        JOIN managers mgr ON a.manager_id = mgr.manager_id
        JOIN clubs c ON a.club_id = c.club_id
        WHERE m.total_minutes >= 180
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("Defensive fingerprint view created")


def query_defensive_fingerprint(player_name=None):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    if player_name:
        cursor.execute("""
            SELECT * FROM defensive_fingerprint
            WHERE player_name ILIKE %s
            ORDER BY total_minutes DESC
        """, (f'%{player_name}%',))
    else:
        cursor.execute("""
            SELECT * FROM defensive_fingerprint
            ORDER BY total_minutes DESC
            LIMIT 20
        """)
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    for row in rows:
        print("\n" + "=" * 40)
        for col, val in zip(columns, row):
            print(f"{col}: {val}")
    cursor.close()
    conn.close()


if __name__ == "__main__":
    create_manager_fingerprint_view()
    create_player_fingerprint_view()
    create_role_demand_view()
    create_player_deviation_view()
    create_role_group_demand_view()
    create_player_role_deviation_view()
    create_compatibility_score_view()
    create_defensive_fingerprint_view()      # <-- this line must be present
    query_defensive_fingerprint("Casemiro")