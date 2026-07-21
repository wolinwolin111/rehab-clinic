import sqlite3
conn = sqlite3.connect('/root/clinic-app/data/clinic.db')
c = conn.cursor()
for t in ['consumption', 'appointments', 'patients', 'appointment_consumption_link']:
    c.execute(f'DELETE FROM {t}')
conn.commit()
conn.close()
print('Cleared')
