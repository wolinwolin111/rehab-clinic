import sqlite3, openpyxl, re, os

DB_PATH = '/root/clinic-app/data/clinic.db'
IMPORT_DIR = '/root/clinic-app/data/import_excel'

# Also clean the root db if exists
for p in [DB_PATH, '/root/clinic-app/clinic.db']:
    if os.path.exists(p):
        os.remove(p)
        print(f'Removed {p}')

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON")
conn.executescript("""
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        phone TEXT DEFAULT '',
        age TEXT DEFAULT '',
        gender TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        day INTEGER NOT NULL,
        time_slot TEXT DEFAULT '',
        project TEXT NOT NULL,
        amount INTEGER DEFAULT 0,
        remark TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS consumption (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        month INTEGER NOT NULL,
        day INTEGER NOT NULL,
        time_slot TEXT DEFAULT '',
        project TEXT NOT NULL,
        amount INTEGER DEFAULT 0,
        sync_to_apt INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS appointment_consumption_link (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        appointment_id INTEGER NOT NULL,
        consumption_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE,
        FOREIGN KEY (consumption_id) REFERENCES consumption(id) ON DELETE CASCADE,
        UNIQUE(appointment_id, consumption_id)
    );
    CREATE TABLE IF NOT EXISTS treatment_projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        default_price INTEGER DEFAULT 0,
        sort_order INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")

total = 0

for fn in sorted(os.listdir(IMPORT_DIR)):
    if not fn.endswith('.xlsx'):
        continue
    mm = re.search(r'(\d+)月', fn)
    if not mm:
        print(f'SKIP {fn}: no month')
        continue
    month = int(mm.group(1))
    fp = os.path.join(IMPORT_DIR, fn)
    wb = openpyxl.load_workbook(fp)

    for sn in wb.sheetnames:
        ws = wb[sn]
        dates = {}
        for col in range(2, 30, 2):
            v = ws.cell(2, col).value
            if v:
                dm = re.search(r'(\d{2})-(\d{2})', str(v).replace('\n', ' '))
                if dm:
                    dates[col] = int(dm.group(2))

        for row in range(4, 16):
            ts = ws.cell(row, 1).value
            if not ts:
                continue
            ts = str(ts).strip()

            for dc, day in dates.items():
                nv = ws.cell(row, dc).value
                if not nv:
                    continue
                name = str(nv).strip()

                rv = ws.cell(row, dc + 1).value
                remark = str(rv).strip() if rv is not None else ''
                remark_clean = remark.replace('\n', ' ').strip()

                amount = 0
                am = re.search(r'(\d+)\s*$', remark_clean)
                if am:
                    amount = int(am.group(1))

                project = re.sub(r'\d+\s*$', '', remark_clean).strip()
                if not project:
                    project = '治疗'

                conn.execute("INSERT OR IGNORE INTO patients (name) VALUES (?)", (name,))
                pid = conn.execute("SELECT id FROM patients WHERE name=?", (name,)).fetchone()[0]

                conn.execute(
                    "INSERT OR IGNORE INTO appointments (patient_id, year, month, day, time_slot, project, amount, remark) VALUES (?,?,?,?,?,?,?,?)",
                    (pid, 2026, month, day, ts, project, amount, remark)
                )
                if conn.execute("SELECT changes()").fetchone()[0] > 0:
                    total += 1

    wb.close()

conn.commit()
conn.close()

print(f'Imported {total} appointments total')

# Verify
conn2 = sqlite3.connect(DB_PATH)
c = conn2.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
p = conn2.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
print(f'DB now has: {c} appointments, {p} patients')
conn2.close()
