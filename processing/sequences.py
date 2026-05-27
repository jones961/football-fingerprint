import psycopg2
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


def identify_sequences(match_id):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

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
    cursor.close()
    conn.close()

    sequences = []
    current_sequence = []
    current_team = None
    sequence_number = 0

    for event in events:
        (event_id, club_id, player_id, player_name,
         period, minute, second, expanded_minute,
         event_type, outcome_type, is_successful,
         x, y, end_x, end_y) = event

        starts_new_sequence = False

        if current_team is None:
            starts_new_sequence = True
        elif event_type in POSSESSION_CHANGE_TYPES and club_id != current_team:
            starts_new_sequence = True
        elif club_id != current_team and event_type not in POSSESSION_CHANGE_TYPES:
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


def store_sequences(match_id, sequences):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) FROM proc_sequences WHERE match_id = %s
    """, (match_id,))
    if cursor.fetchone()[0] > 0:
        print(f"Sequences already stored for match {match_id}, skipping")
        cursor.close()
        conn.close()
        return

    inserted = 0

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

        x_progression = (end_x - start_x) if (end_x and start_x) else None

        start_zone = classify_zone(start_x)
        end_zone = classify_zone(end_x)

        last_type = seq[-1]['event_type']
        first_type = seq[0]['event_type']

        ended_with_shot = last_type in {'SavedShot', 'MissedShots'}
        ended_with_goal = last_type == 'Goal'
        ended_with_loss = not ended_with_shot and not ended_with_goal

        cursor.execute("""
            INSERT INTO proc_sequences (
                match_id, club_id, sequence_number, period,
                start_minute, start_second, end_minute, end_second,
                event_count, start_x, start_y, end_x, end_y,
                x_progression, start_zone, end_zone,
                ended_with_shot, ended_with_goal, ended_with_loss,
                max_x, avg_x, width,
                start_event_type, end_event_type
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (match_id, club_id, sequence_number) DO NOTHING
            RETURNING id
        """, (
            match_id, club_id, sequence_number, period,
            start_minute, start_second, end_minute, end_second,
            event_count, start_x, start_y, end_x, end_y,
            x_progression, start_zone, end_zone,
            ended_with_shot, ended_with_goal, ended_with_loss,
            max_x, avg_x, width,
            first_type, last_type
        ))

        result = cursor.fetchone()
        if not result:
            continue

        sequence_id = result[0]

        for position, event in enumerate(seq):
            cursor.execute("""
                INSERT INTO proc_sequence_events (
                    sequence_id, clean_event_id, position
                ) VALUES (%s, %s, %s)
            """, (sequence_id, event['event_id'], position))

        inserted += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Stored {inserted} sequences for match {match_id}")


def backfill_event_types():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id FROM proc_sequences
        WHERE start_event_type IS NULL
        OR end_event_type IS NULL
    """)
    sequence_ids = [row[0] for row in cursor.fetchall()]
    print(f"Backfilling {len(sequence_ids)} sequences")

    updated = 0

    for seq_id in sequence_ids:
        cursor.execute("""
            SELECT ce.type
            FROM proc_sequence_events pse
            JOIN clean_events ce ON pse.clean_event_id = ce.id
            WHERE pse.sequence_id = %s
            ORDER BY pse.position ASC
            LIMIT 1
        """, (seq_id,))
        first = cursor.fetchone()

        cursor.execute("""
            SELECT ce.type
            FROM proc_sequence_events pse
            JOIN clean_events ce ON pse.clean_event_id = ce.id
            WHERE pse.sequence_id = %s
            ORDER BY pse.position DESC
            LIMIT 1
        """, (seq_id,))
        last = cursor.fetchone()

        if first and last:
            cursor.execute("""
                UPDATE proc_sequences
                SET start_event_type = %s,
                    end_event_type = %s
                WHERE id = %s
            """, (first[0], last[0], seq_id))
            updated += 1

        if updated % 1000 == 0 and updated > 0:
            conn.commit()
            print(f"Updated {updated} sequences...")

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Backfill complete. Updated {updated} sequences")


def process_all_matches():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT match_id FROM clean_events
        ORDER BY match_id
    """)
    match_ids = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    print(f"Processing {len(match_ids)} matches")

    for match_id in match_ids:
        sequences = identify_sequences(match_id)
        store_sequences(match_id, sequences)


if __name__ == "__main__":
    backfill_event_types()