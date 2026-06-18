import time

import psycopg2
from psycopg2.extras import execute_values

from config import DB_CONFIG

POSSESSION_CHANGE_TYPES = {
    'BallRecovery',
    'Interception',
    'KeeperPickup',
    'KeeperSweeper',
    'Save',
    'Claim',
}

SEQUENCE_ENDING_TYPES = {
    'Goal',
    'SavedShot',
    'MissedShots',
    'BlockedPass',
    'OffsideGiven',
    'Punch',
}

EXCLUDED_TYPES = {
    'Start',
    'End',
    'FormationSet',
    'FormationChange',
    'SubstitutionOn',
    'SubstitutionOff',
    'Card',
    'OffsideProvoked',
}

KEEPER_END_TYPES = {
    'KeeperPickup',
    'KeeperSweeper',
    'Save',
    'Claim',
    'Punch',
}


def classify_zone(x):
    if x is None:
        return None
    if x <= 33:
        return 'defensive'
    if x <= 67:
        return 'middle'
    return 'final'


def identify_sequences(cursor, match_id):
    cursor.execute("""
        SELECT
            id, club_id, player_id, player_name,
            period, minute, second, expanded_minute,
            type, outcome_type, is_successful,
            x, y, end_x, end_y
        FROM clean_events
        WHERE match_id = %s
        AND period IN ('FirstHalf', 'SecondHalf',
                      'ExtraTimeFirstHalf', 'ExtraTimeSecondHalf')
        AND type NOT IN %s
        ORDER BY period, minute, second, expanded_minute
    """, (match_id, tuple(EXCLUDED_TYPES)))

    events = cursor.fetchall()

    sequences = []
    current_sequence = []
    current_team = None
    sequence_number = 0

    for event in events:
        (event_id, club_id, player_id, player_name,
         period, minute, second, expanded_minute,
         event_type, outcome_type, is_successful,
         x, y, end_x, end_y) = event

        # NOTE (correctness decision): the two opponent-event branches below
        # both fire on any club_id != current_team, so POSSESSION_CHANGE_TYPES
        # does NOT discriminate here. If "any opponent on-ball action = turnover"
        # is what you want, collapse to a single `club_id != current_team` check.
        starts_new_sequence = False
        if current_team is None:
            starts_new_sequence = True
        elif club_id != current_team:
            starts_new_sequence = True

        if starts_new_sequence:
            if current_sequence:
                sequences.append(current_sequence)
            sequence_number += 1
            current_sequence = []
            current_team = club_id

        current_event = {
            'event_id': event_id,
            'sequence_number': sequence_number,
            'club_id': club_id,
            'player_id': player_id,
            'player_name': player_name,
            'period': period,
            'minute': minute,
            'second': second,
            'event_type': event_type,
            'is_successful': is_successful,
            'x': x,
            'y': y,
            'end_x': end_x,
            'end_y': end_y,
        }
        current_sequence.append(current_event)
        current_team = club_id

        if event_type in SEQUENCE_ENDING_TYPES:
            if current_sequence:
                sequences.append(current_sequence)
            sequence_number += 1
            current_sequence = []
            current_team = None

    if current_sequence:
        sequences.append(current_sequence)

    return sequences


def store_sequences(cursor, match_id, sequences):
    cursor.execute("""
        SELECT COUNT(*) FROM proc_sequences WHERE match_id = %s
    """, (match_id,))
    if cursor.fetchone()[0] > 0:
        print(f"Sequences already stored for match {match_id}, skipping")
        return 0

    seq_rows = []
    prepared = []  # parallel list holding the event lists for each seq row

    for seq in sequences:
        if not seq:
            continue

        club_id = seq[0]['club_id']
        sequence_number = seq[0]['sequence_number']
        period = seq[0]['period']
        start_minute = seq[0]['minute']
        start_second = seq[0]['second']
        end_minute = seq[-1]['minute']
        end_second = seq[-1]['second']
        event_count = len(seq)

        x_values = [e['x'] for e in seq if e['x'] is not None]
        y_values = [e['y'] for e in seq if e['y'] is not None]

        start_x = seq[0]['x']
        start_y = seq[0]['y']
        end_x = seq[-1]['x']
        end_y = seq[-1]['y']

        max_x = max(x_values) if x_values else None
        avg_x = sum(x_values) / len(x_values) if x_values else None
        width = (max(y_values) - min(y_values)) if len(y_values) > 1 else 0

        # FIX: use `is not None`, not truthiness — x=0.0 is a real coordinate.
        x_progression = (
            end_x - start_x
            if (end_x is not None and start_x is not None)
            else None
        )

        start_zone = classify_zone(start_x)
        end_zone = classify_zone(end_x)

        last_type = seq[-1]['event_type']
        first_type = seq[0]['event_type']

        ended_with_shot = last_type in {'SavedShot', 'MissedShots'}
        ended_with_goal = last_type == 'Goal'
        ended_with_loss = not ended_with_shot and not ended_with_goal

        seq_rows.append((
            match_id, club_id, sequence_number, period,
            start_minute, start_second, end_minute, end_second,
            event_count, start_x, start_y, end_x, end_y,
            x_progression, start_zone, end_zone,
            ended_with_shot, ended_with_goal, ended_with_loss,
            max_x, avg_x, width,
            first_type, last_type
        ))
        prepared.append([e['event_id'] for e in seq])

    if not seq_rows:
        return 0

    # Batch-insert sequences, returning ids in input order so we can map
    # each returned id back to its event list.
    inserted_ids = execute_values(
        cursor,
        """
        INSERT INTO proc_sequences (
            match_id, club_id, sequence_number, period,
            start_minute, start_second, end_minute, end_second,
            event_count, start_x, start_y, end_x, end_y,
            x_progression, start_zone, end_zone,
            ended_with_shot, ended_with_goal, ended_with_loss,
            max_x, avg_x, width,
            start_event_type, end_event_type
        ) VALUES %s
        ON CONFLICT (match_id, club_id, sequence_number) DO NOTHING
        RETURNING id
        """,
        seq_rows,
        fetch=True,
    )

    # CAUTION: with ON CONFLICT DO NOTHING, conflicting rows are skipped and
    # NOT returned, so RETURNING ids may be shorter than seq_rows. We guard
    # the skip path by re-checking length; on a fresh match with no prior
    # sequences (the COUNT guard above ensures this), there are no conflicts.
    if len(inserted_ids) != len(prepared):
        raise RuntimeError(
            f"match {match_id}: expected {len(prepared)} sequence ids, "
            f"got {len(inserted_ids)} — conflict skipped rows, mapping unsafe"
        )

    event_rows = []
    for (seq_id,), event_ids in zip(inserted_ids, prepared):
        for position, clean_event_id in enumerate(event_ids):
            event_rows.append((seq_id, clean_event_id, position))

    execute_values(
        cursor,
        """
        INSERT INTO proc_sequence_events (sequence_id, clean_event_id, position)
        VALUES %s
        """,
        event_rows,
    )

    inserted = len(seq_rows)
    print(f"Stored {inserted} sequences for match {match_id}")
    return inserted


def process_all_matches():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT match_id FROM clean_events
        ORDER BY match_id
    """)
    match_ids = [row[0] for row in cursor.fetchall()]

    print(f"Processing {len(match_ids)} matches")

    t0 = time.time()
    total = 0
    failed = []

    for i, match_id in enumerate(match_ids, 1):
        try:
            sequences = identify_sequences(cursor, match_id)
            total += store_sequences(cursor, match_id, sequences)
            conn.commit()
        except Exception as e:
            conn.rollback()
            failed.append((match_id, str(e)))
            print(f"  FAILED {match_id}: {e}")

        if i % 50 == 0:
            rate = i / (time.time() - t0)
            eta = (len(match_ids) - i) / rate / 60 if rate else 0
            print(f"{i}/{len(match_ids)}  {rate:.1f} match/s  ETA {eta:.1f}m")

    cursor.close()
    conn.close()
    print(f"Done. {total} sequences across {len(match_ids) - len(failed)} matches, "
          f"{len(failed)} failed, {time.time() - t0:.0f}s")
    if failed:
        for mid, err in failed:
            print(f"  {mid}: {err}")


def process_single_match(match_id):
    """Time/validate one match before committing to the full run."""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    t0 = time.time()
    sequences = identify_sequences(cursor, match_id)
    n = store_sequences(cursor, match_id, sequences)
    conn.commit()
    cursor.close()
    conn.close()
    print(f"match {match_id}: {n} sequences in {time.time() - t0:.2f}s")
    return n


if __name__ == "__main__":
    process_all_matches()

