#!/usr/bin/env python3
"""导入Excel - 时段用实际值匹配"""
import sqlite3, openpyxl, re, os, subprocess

DB_PATH = '/opt/clinic/backend/data/clinic.db'
EXCEL_DIR = '/opt/clinic/data/import_excel'
YEAR = 2026

print('stopping clinic-app...')
subprocess.run(['systemctl', 'stop', 'clinic-app'], capture_output=True)

for p in [DB_PATH, DB_PATH+'-shm', DB_PATH+'-wal']:
    if os.path.exists(p): os.remove(p)

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON")
conn.executescript("""
    CREATE TABLE patients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, phone TEXT DEFAULT '', age TEXT DEFAULT '', gender TEXT DEFAULT '', balance REAL DEFAULT 0, has_recharge INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE appointments (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER NOT NULL, year INTEGER NOT NULL, month INTEGER NOT NULL, day INTEGER NOT NULL, time_slot TEXT DEFAULT '', project TEXT NOT NULL, amount REAL DEFAULT 0, remark TEXT DEFAULT '', recharge_amount REAL DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE);
    CREATE TABLE consumption (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER NOT NULL, month INTEGER NOT NULL, day INTEGER NOT NULL, project TEXT NOT NULL, amount REAL DEFAULT 0, time_slot TEXT DEFAULT '', sync_to_apt INTEGER DEFAULT 0, recharge_amount REAL DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE);
    CREATE TABLE treatment_projects (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, default_price REAL DEFAULT 0, sort_order INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE appointment_consumption_link (id INTEGER PRIMARY KEY AUTOINCREMENT, appointment_id INTEGER NOT NULL, consumption_id INTEGER NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE, FOREIGN KEY (consumption_id) REFERENCES consumption(id) ON DELETE CASCADE);
    CREATE TABLE operation_history (id INTEGER PRIMARY KEY AUTOINCREMENT, action_type TEXT NOT NULL, target_type TEXT NOT NULL, target_id INTEGER, data TEXT, description TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
""")

ALL_SLOTS = ['8:00-9:00','9:00-10:00','10:00-11:00','11:00-12:00','12:00-13:00','13:00-14:00','14:00-15:00','15:00-16:00','16:00-17:00','17:00-18:00','18:00-19:00','19:00-20:00','20:00-21:00','21:00-22:00']

def parse_remark(val):
    if not val: return ('治疗', 0, '')
    lines = str(val).strip().split('\n')
    lines = [l.strip() for l in lines if l.strip()]
    project = lines[0] if lines else '治疗'
    amount = 0
    for l in lines[1:]:
        nums = re.findall(r'\d+', l)
        if nums: amount = int(nums[-1])
    return (project, amount, str(val).strip())

def get_patient(conn, name):
    r = conn.execute("SELECT id FROM patients WHERE name=?", (name,)).fetchone()
    if r: return r[0]
    conn.execute("INSERT INTO patients (name) VALUES (?)", (name,))
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

total = 0
known_projects = set()

for fname in sorted(os.listdir(EXCEL_DIR)):
    if not fname.endswith('.xlsx'): continue
    m = re.search(r'(\d+)月', fname)
    if not m: continue
    month = int(m.group(1))
    
    wb = openpyxl.load_workbook(os.path.join(EXCEL_DIR, fname))
    print(f'{fname} month={month}')
    
    for sname in wb.sheetnames:
        parts = sname.split('-')
        if len(parts) != 2: continue
        try:
            start_day = int(parts[0])
            end_day = int(parts[1])
        except: continue
        
        ws = wb[sname]
        
        # 遍历4-17行（时段行）
        for row_idx in range(4, 18):
            ts_val = ws.cell(row=row_idx, column=1).value
            if not ts_val: continue
            ts = str(ts_val).strip()
            if ts not in ALL_SLOTS: continue
            
            row = [ws.cell(row=row_idx, column=c).value for c in range(1, ws.max_column + 1)]
            
            for day_off in range(end_day - start_day + 1):
                day = start_day + day_off
                apt_col = 1 + day_off * 2
                rem_col = apt_col + 1
                
                if apt_col >= len(row): continue
                name_val = row[apt_col]
                if not name_val: continue
                
                name = str(name_val).strip()
                if not name or name == 'None': continue
                
                remark_val = row[rem_col] if rem_col < len(row) else None
                project, amount, remark = parse_remark(remark_val)
                
                if amount == 0:
                    amount = 300
                
                known_projects.add(project)
                pid = get_patient(conn, name)
                
                conn.execute(
                    "INSERT INTO appointments (patient_id,year,month,day,time_slot,project,amount,remark) VALUES (?,?,?,?,?,?,?,?)",
                    (pid, YEAR, month, day, ts, project, amount, remark))
                aid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                
                conn.execute(
                    "INSERT INTO consumption (patient_id,month,day,project,amount,time_slot,sync_to_apt) VALUES (?,?,?,?,?,?,?)",
                    (pid, month, day, project, amount, ts, 1))
                cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                
                conn.execute(
                    "INSERT INTO appointment_consumption_link (appointment_id,consumption_id) VALUES (?,?)",
                    (aid, cid))
                
                total += 1
                print(f"  {month}/{day} {ts} {name} | {project} | ¥{amount}")

conn.commit()

for i, proj in enumerate(sorted(known_projects)):
    conn.execute("INSERT OR IGNORE INTO treatment_projects (name, default_price, sort_order) VALUES (?,?,?)", (proj, 300, i))
conn.commit()
conn.close()

print(f'\nTotal: {total}')
print(f'Projects: {sorted(known_projects)}')

subprocess.run(['systemctl', 'start', 'clinic-app'], capture_output=True)
print('restarted')