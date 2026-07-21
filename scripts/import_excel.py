import sqlite3, openpyxl, re, os, sys

# ========== CONFIG ==========
DB_PATH = '/root/clinic-app/data/clinic.db'
EXCEL_DIR = '/root/clinic-app/data/import_excel'
YEAR = 2026
# ============================

def extract_month(filename):
    m = re.search(r'(\d+)月', filename)
    return int(m.group(1)) if m else None

def parse_remark(remark):
    remark_clean = remark.replace('\n', ' ').strip()
    amount = 0
    nums = re.findall(r'\d+', remark_clean)
    if nums:
        amount = int(nums[-1])
    project = re.sub(r'[\d\s+]+$', '', remark_clean).strip()
    if not project:
        project = '治疗'
    return project, amount, remark

def import_all(db_path=DB_PATH, excel_dir=EXCEL_DIR, year=YEAR):
    if not os.path.exists(excel_dir):
        print(f'ERROR: Directory not found: {excel_dir}')
        return

    # Remove old DB if exists
    for p in [db_path]:
        if os.path.exists(p):
            os.remove(p)
            print(f'Removed old DB: {p}')

    conn = sqlite3.connect(db_path)
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
        CREATE TABLE IF NOT EXISTS treatment_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            default_price INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    for col in ['age', 'gender']:
        try: conn.execute(f"ALTER TABLE patients ADD COLUMN {col} TEXT DEFAULT ''")
        except: pass
    try: conn.execute("ALTER TABLE consumption ADD COLUMN time_slot TEXT DEFAULT ''")
    except: pass
    try: conn.execute("ALTER TABLE consumption ADD COLUMN sync_to_apt INTEGER DEFAULT 0")
    except: pass

    total = 0
    for fn in sorted(os.listdir(excel_dir)):
        if not fn.endswith('.xlsx') or fn.startswith('~$'):
            continue
        month = extract_month(fn)
        if not month:
            print(f'  SKIP {fn}: cannot parse month')
            continue
        fp = os.path.join(excel_dir, fn)
        wb = openpyxl.load_workbook(fp)
        file_count = 0

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
                    project, amount, _ = parse_remark(remark)

                    conn.execute("INSERT OR IGNORE INTO patients (name) VALUES (?)", (name,))
                    pid = conn.execute("SELECT id FROM patients WHERE name=?", (name,)).fetchone()[0]
                    conn.execute(
                        "INSERT INTO appointments (patient_id, year, month, day, time_slot, project, amount, remark) VALUES (?,?,?,?,?,?,?,?)",
                        (pid, year, month, day, ts, project, amount, remark)
                    )
                    aid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    # 同步生成耗卡
                    conn.execute(
                        "INSERT INTO consumption (patient_id, month, day, time_slot, project, amount, sync_to_apt) VALUES (?,?,?,?,?,?,1)",
                        (pid, month, day, ts, project, amount)
                    )
                    con_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    conn.execute(
                        "INSERT INTO appointment_consumption_link (appointment_id, consumption_id) VALUES (?,?)",
                        (aid, con_id)
                    )
                    file_count += 1
                    total += 1

        wb.close()
        print(f'  {fn} (month {month}): {file_count} records')

    conn.commit()
    conn.close()
    print(f'\nDone! Total: {total} appointments')
    return total

if __name__ == '__main__':
    import_all()
