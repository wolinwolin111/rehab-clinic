import sqlite3

DB_PATH = '/root/clinic-app/data/clinic.db'
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# Count distinct vs total
total = conn.execute("SELECT COUNT(*) as c FROM appointments").fetchone()['c']
distinct = conn.execute("""
    SELECT COUNT(*) as c FROM (
        SELECT DISTINCT patient_id, month, day, time_slot, project, amount
        FROM appointments
    )
""").fetchone()['c']
print(f'Total appointments: {total}, Distinct: {distinct}')

# Delete duplicates keeping the lowest ID
conn.execute("""
    DELETE FROM appointments WHERE id NOT IN (
        SELECT MIN(id) FROM appointments
        GROUP BY patient_id, month, day, time_slot, project, amount
    )
""")
removed = conn.execute("SELECT changes()").fetchone()[0]
print(f'Removed {removed} duplicates')

# Also cleanup patients that have no appointments
conn.execute("""
    DELETE FROM patients WHERE id NOT IN (
        SELECT DISTINCT patient_id FROM appointments
    )
""")
removed_p = conn.execute("SELECT changes()").fetchone()[0]
print(f'Removed {removed_p} orphaned patients')

conn.commit()
print(f'Final: appointments={conn.execute("SELECT COUNT(*) as c FROM appointments").fetchone()["c"]}, patients={conn.execute("SELECT COUNT(*) as c FROM patients").fetchone()["c"]}')
conn.close()
