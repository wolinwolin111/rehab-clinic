import sqlite3

DB_PATH = '/root/clinic-app/data/clinic.db'
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# Get all appointments
apts = conn.execute("SELECT * FROM appointments ORDER BY id").fetchall()
print(f'Total appointments: {len(apts)}')

created = 0
for a in apts:
    # Check if consumption already exists for this appointment
    existing = conn.execute(
        "SELECT id FROM appointment_consumption_link WHERE appointment_id=?", (a['id'],)
    ).fetchone()
    if existing:
        continue

    # Create consumption
    conn.execute(
        "INSERT INTO consumption (patient_id, month, day, time_slot, project, amount, sync_to_apt) VALUES (?,?,?,?,?,?,1)",
        (a['patient_id'], a['month'], a['day'], a['time_slot'], a['project'], a['amount'])
    )
    con_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Link
    conn.execute(
        "INSERT INTO appointment_consumption_link (appointment_id, consumption_id) VALUES (?,?)",
        (a['id'], con_id)
    )
    created += 1

conn.commit()
print(f'Created {created} consumption records')

# Verify
total_con = conn.execute("SELECT COUNT(*) as c FROM consumption").fetchone()['c']
total_links = conn.execute("SELECT COUNT(*) as c FROM appointment_consumption_link").fetchone()['c']
print(f'Total consumption: {total_con}, Total links: {total_links}')
conn.close()
