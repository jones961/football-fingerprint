def add_caretaker_column():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        ALTER TABLE appointments 
        ADD COLUMN IF NOT EXISTS is_caretaker BOOLEAN NOT NULL DEFAULT FALSE
    """)
    conn.commit()
    cursor.close()
    conn.close()
    print("is_caretaker column added successfully")