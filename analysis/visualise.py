import psycopg2
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os
from mplsoccer import Pitch
from config import DB_CONFIG


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
        'Where possession ends',
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

if __name__ == "__main__":
    plot_all_managers()