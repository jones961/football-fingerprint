import psycopg2
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os
from mplsoccer import Pitch
from config import DB_CONFIG
from fingerprints import create_manager_fingerprint_view, create_player_fingerprint_view

def get_manager_fingerprint_data(manager_name=None):
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
    cursor.close()
    conn.close()

    return [dict(zip(columns, row)) for row in rows]


def get_manager_sequence_starts(appointment_id):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ps.start_x, ps.start_y
        FROM proc_sequences ps
        JOIN match_context mc ON ps.match_id = mc.match_id
            AND mc.club_id = ps.club_id
        JOIN appointments a ON mc.appointment_id = a.appointment_id
        WHERE a.appointment_id = %s
        AND ps.start_x IS NOT NULL
        AND ps.start_y IS NOT NULL
    """, (appointment_id,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return [r[0] for r in rows], [r[1] for r in rows]

def get_manager_sequence_ends(appointment_id):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ps.end_x, ps.end_y
        FROM proc_sequences ps
        JOIN match_context mc ON ps.match_id = mc.match_id
            AND mc.club_id = ps.club_id
        JOIN appointments a ON mc.appointment_id = a.appointment_id
        WHERE a.appointment_id = %s
        AND ps.end_x IS NOT NULL
        AND ps.end_y IS NOT NULL
        AND ps.end_event_type NOT IN (
            'KeeperPickup', 'KeeperSweeper', 'Save', 
            'Claim', 'Punch', 'Clearance'
        )
    """, (appointment_id,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return [r[0] for r in rows], [r[1] for r in rows]

    cursor.execute("""
        SELECT ps.end_x, ps.end_y
        FROM proc_sequences ps
        JOIN match_context mc ON ps.match_id = mc.match_id
            AND mc.club_id = ps.club_id
        JOIN appointments a ON mc.appointment_id = a.appointment_id
        WHERE a.appointment_id = %s
        AND ps.end_x IS NOT NULL
        AND ps.end_y IS NOT NULL
    """, (appointment_id,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return [r[0] for r in rows], [r[1] for r in rows]

def plot_manager_fingerprint(manager_data, save_path=None):
    pitch = Pitch(
        pitch_type='custom',
        pitch_length=100,
        pitch_width=100,
        pitch_color='#1a1a2e',
        line_color='#ffffff',
        line_alpha=0.7,
    )

    fig, axes = pitch.draw(figsize=(14, 9), nrows=1, ncols=2)
    ax_start = axes[0]
    ax_end = axes[1]

    manager_name = manager_data['manager_name']
    club_name = manager_data['club_name']
    matches = manager_data['matches']
    appointment_id = manager_data['appointment_id']

    x_starts, y_starts = get_manager_sequence_starts(appointment_id)
    x_ends, y_ends = get_manager_sequence_ends(appointment_id)

    # Left plot - sequence starts heatmap
    if x_starts:
        pitch.kdeplot(
            x_starts, y_starts,
            ax=ax_start,
            cmap='Reds',
            fill=True,
            alpha=0.6,
            levels=10,
            zorder=1,
        )

    ax_start.set_title(
        'Where possession begins',
        color='white', fontsize=11, pad=8
    )

    # Right plot - sequence ends heatmap
    if x_ends:
        pitch.kdeplot(
            x_ends, y_ends,
            ax=ax_end,
            cmap='Blues',
            fill=True,
            alpha=0.6,
            levels=10,
            zorder=1,
        )

    ax_end.set_title(
        'Where attacking sequences end',
        color='white', fontsize=11, pad=8
    )

    # Add third zone lines to both plots
    for ax in [ax_start, ax_end]:
        for x_line in [33, 67]:
            ax.axvline(
                x=x_line, color='white',
                linestyle='--', alpha=0.3, lw=1
            )

    # Date range
    date_from = manager_data['date_from'].strftime('%b %Y')
    date_to = manager_data['date_to'].strftime('%b %Y') if manager_data['date_to'] else 'Present'

    fig.suptitle(
        f'{manager_name}  —  {club_name}  ({date_from} to {date_to})',
        fontsize=14, fontweight='bold', color='white', y=0.98
    )

    stats_text = (
        f'Matches: {matches}  |  '
        f'Press recovery: {manager_data["press_recovery_rate"]}%  |  '
        f'Avg progression: {manager_data["avg_x_progression"]}  |  '
        f'Shot seq/match: {manager_data["shot_sequences_per_match"]}  |  '
        f'Goal seq rate: {manager_data["goal_sequence_rate"]}%'
    )

    fig.text(
        0.5, 0.02, stats_text,
        ha='center', fontsize=10, color='white',
        bbox=dict(
            boxstyle='round',
            facecolor='#0d0d1a',
            alpha=0.9,
            edgecolor='white',
            linewidth=0.5
        )
    )

    fig.patch.set_facecolor('#1a1a2e')
    plt.tight_layout(rect=[0, 0.06, 1, 0.95])

    if save_path:
        plt.savefig(
            save_path, dpi=150,
            bbox_inches='tight',
            facecolor='#1a1a2e'
        )
        print(f"Saved to {save_path}")
    else:
        plt.show()

    plt.close()
    return fig

def plot_all_managers(save_dir=None):
    import os
    if save_dir is None:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        save_dir = os.path.join(project_root, 'outputs')
    os.makedirs(save_dir, exist_ok=True)

    managers = get_manager_fingerprint_data()
    print(f"Plotting {len(managers)} manager fingerprints")

    for manager in managers:
        safe_name = manager['manager_name'].replace(' ', '_')
        safe_club = manager['club_name'].replace(' ', '_')
        filename = os.path.join(save_dir, f"{safe_name}_{safe_club}.png")
        print(f"Plotting {manager['manager_name']} at {manager['club_name']}...")
        plot_manager_fingerprint(manager, save_path=filename)


def get_player_spatial_data(player_id, appointment_id):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ce.x, ce.y, ce.type
        FROM clean_events ce
        JOIN match_context mc ON ce.match_id = mc.match_id
            AND ce.club_id = mc.club_id
        WHERE ce.player_id = %s
        AND mc.appointment_id = %s
        AND ce.period IN ('FirstHalf', 'SecondHalf')
        AND ce.x IS NOT NULL
        AND ce.y IS NOT NULL
        AND NOT (
            ce.x >= 99 AND (ce.y <= 1 OR ce.y >= 99)
        )
        AND NOT (
            ce.x <= 1 AND (ce.y <= 1 OR ce.y >= 99)
        )
    """, (player_id, appointment_id))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    x = [r[0] for r in rows]
    y = [r[1] for r in rows]
    types = [r[2] for r in rows]
    return x, y, types


def plot_player_fingerprint(player_data, save_path=None):
    import os

    pitch = Pitch(
        pitch_type='custom',
        pitch_length=100,
        pitch_width=100,
        pitch_color='#1a1a2e',
        line_color='#ffffff',
        line_alpha=0.7,
    )

    fig, ax = pitch.draw(figsize=(12, 8))

    player_name = player_data['player_name']
    manager_name = player_data['manager_name']
    club_name = player_data['club_name']
    player_id = player_data['player_id']
    appointment_id = player_data['appointment_id']

    x, y, types = get_player_spatial_data(player_id, appointment_id)

    # Full action heatmap
    if x:
        pitch.kdeplot(
            x, y,
            ax=ax,
            cmap='Reds',
            fill=True,
            alpha=0.6,
            levels=10,
            zorder=1,
        )

    # Overlay defensive actions in a different colour
    def_x = [x[i] for i, t in enumerate(types)
              if t in ('Tackle', 'Interception', 'BallRecovery', 'Challenge')]
    def_y = [y[i] for i, t in enumerate(types)
              if t in ('Tackle', 'Interception', 'BallRecovery', 'Challenge')]

    if len(def_x) > 10:
        pitch.kdeplot(
            def_x, def_y,
            ax=ax,
            cmap='Blues',
            fill=True,
            alpha=0.4,
            levels=5,
            zorder=2,
        )

    # Third zone lines
    for x_line in [33, 67]:
        ax.axvline(
            x=x_line, color='white',
            linestyle='--', alpha=0.3, lw=1
        )

    # Average position dot
    if x:
        avg_x = sum(x) / len(x)
        avg_y = sum(y) / len(y)
        ax.scatter(
            avg_x, avg_y,
            color='yellow', s=200,
            zorder=6, label=f'Avg position'
        )

    date_from = player_data['date_from'].strftime('%b %Y')
    date_to = player_data['date_to'].strftime('%b %Y') if player_data['date_to'] else 'Present'

    fig.suptitle(
        f'{player_name}  —  {club_name} under {manager_name}',
        fontsize=14, fontweight='bold', color='white', y=0.98
    )

    minutes = player_data['total_minutes']
    matches = player_data['matches']

    stats_text = (
        f"Mins: {minutes}  |  "
        f"Matches: {matches}  |  "
        f"Avg X: {player_data['avg_x']}  |  "
        f"Final 3rd: {player_data['pct_actions_final_third']}%  |  "
        f"Prog passes: {player_data['pct_progressive_passes']}%  |  "
        f"xG chain/90: {player_data['avg_xg_chain_per_90']}  |  "
        f"xG/90: {player_data['avg_xg_per_90']}"
    )

    fig.text(
        0.5, 0.02, stats_text,
        ha='center', fontsize=9, color='white',
        bbox=dict(
            boxstyle='round',
            facecolor='#0d0d1a',
            alpha=0.9,
            edgecolor='white',
            linewidth=0.5
        )
    )

    ax.legend(
        loc='upper right',
        facecolor='#1a1a2e',
        labelcolor='white',
        fontsize=9,
        framealpha=0.8,
    )

    fig.patch.set_facecolor('#1a1a2e')
    plt.tight_layout(rect=[0, 0.06, 1, 0.95])

    if save_path:
        plt.savefig(
            save_path, dpi=150,
            bbox_inches='tight',
            facecolor='#1a1a2e'
        )
        print(f"Saved to {save_path}")
    else:
        plt.show()

    plt.close()
    return fig


def plot_squad_fingerprints(manager_name, save_dir=None):
    import os
    if save_dir is None:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        save_dir = os.path.join(project_root, 'outputs', 'players')
    os.makedirs(save_dir, exist_ok=True)

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM player_fingerprint
        WHERE manager_name = %s
        AND total_minutes >= 900
        ORDER BY total_minutes DESC
    """, (manager_name,))

    columns = [desc[0] for desc in cursor.description]
    players = [dict(zip(columns, row)) for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    print(f"Plotting {len(players)} players under {manager_name}")

    for player in players:
        safe_name = player['player_name'].replace(' ', '_')
        filename = os.path.join(save_dir, f"{safe_name}.png")
        print(f"Plotting {player['player_name']}...")
        plot_player_fingerprint(player, save_path=filename)


if __name__ == "__main__":
    create_manager_fingerprint_view()
    create_player_fingerprint_view()
    plot_squad_fingerprints("Mikel Arteta")