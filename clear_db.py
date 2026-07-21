import sqlite3, os
db_path = os.path.join(os.path.dirname(__file__), 'data', 'clinic.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()
for t in ['consumption', 'appointments', 'patients', 'history', 'appointment_consumption_link']:
    try:
        c.execute(f'DELETE FROM {t}')
        print(f'Cleared {t}: {c.rowcount} rows')
    except Exception as e:
        print(f'Skip {t}: {e}')
conn.commit()
conn.close()
print('Done')
