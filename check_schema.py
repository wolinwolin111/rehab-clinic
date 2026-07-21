import sqlite3
conn = sqlite3.connect('/root/clinic-app/data/clinic.db')
c = conn.cursor()
for table in ['patients', 'appointments', 'consumption', 'appointment_consumption_link']:
    c.execute(f'PRAGMA table_info({table})')
    print(f'{table}: {[r for r in c.fetchall()]}')
conn.close()
