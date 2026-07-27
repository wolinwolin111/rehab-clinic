#!/usr/bin/env python3
"""导入Excel预约表 - 适配新版数据库结构（含recharge_amount, balance, has_recharge等）"""
import sqlite3, openpyxl, re, os, sys

DB_PATH = '/opt/clinic/backend/data/clinic.db'
EXCEL_DIR = '/opt/clinic/data/import_excel'
YEAR = 2026

# ====== 先停止 gunicorn ======
import subprocess
subprocess.run(['systemctl', 'stop', 'clinic-app'], capture_output=True)
print('stopped clinic-app')

# ====== 删除旧数据库 ======
for p in [DB_PATH, DB_PATH+'-shm', DB_PATH+'-wal']:
    if os.path.exists(p):
        os.remove(p)
        print(f'removed: {p}')

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON")

# 新版完整表结构
conn.executescript("""
    CREATE TABLE patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        phone TEXT DEFAULT '',
        age TEXT DEFAULT '',
        gender TEXT DEFAULT '',
        balance REAL DEFAULT 0,
        has_recharge INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        day INTEGER NOT NULL,
        time_slot TEXT DEFAULT '',
        project TEXT NOT NULL,
        amount REAL DEFAULT 0,
        remark TEXT DEFAULT '',
        recharge_amount REAL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
    );
    CREATE TABLE consumption (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        month INTEGER NOT NULL,
        day INTEGER NOT NULL,
        project TEXT NOT NULL,
        amount REAL DEFAULT 0,
        time_slot TEXT DEFAULT '',
        sync_to_apt INTEGER DEFAULT 0,
        recharge_amount REAL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
    );
    CREATE TABLE treatment_projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        default_price REAL DEFAULT 0,
        sort_order INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE appointment_consumption_link (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        appointment_id INTEGER NOT NULL,
        consumption_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE,
        FOREIGN KEY (consumption_id) REFERENCES consumption(id) ON DELETE CASCADE
    );
    CREATE TABLE operation_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action_type TEXT NOT NULL,
        target_type TEXT NOT NULL,
        target_id INTEGER,
        data TEXT,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")
print('tables created')

# ====== 解析Excel ======
# 已知患者名→项目→金额映射（从F列备注解析）
TIME_SLOTS = ['8:00-9:00','9:00-10:00','10:00-11:00','11:00-12:00','12:00-13:00',
              '13:00-14:00','14:00-15:00','15:00-16:00','16:00-17:00','17:00-18:00',
              '18:00-19:00','19:00-20:00','20:00-21:00','21:00-22:00']

def parse_cell(val):
    """解析单元格：返回 (patient_name, project, amount)"""
    if not val: return None
    val = str(val).strip()
    if not val or val == 'None': return None
    
    # 多行内容：第一行是姓名，后面可能有项目/金额
    lines = [l.strip() for l in val.split('\n') if l.strip()]
    if not lines: return None
    
    name = lines[0]
    project = ''
    amount = 0
    
    for line in lines[1:]:
        line_upper = line.upper().strip()
        # 查找金额
        nums = re.findall(r'\d+', line)
        if nums:
            amount = int(nums[-1])
        # 剩余作为项目名
        proj = re.sub(r'[\d\s]+$', '', line).strip()
        if proj and proj not in ('备注', '预约', '治疗'):
            if not project:
                project = proj
    
    return (name, project or '治疗', amount)

def get_or_create_patient(conn, name):
    cur = conn.execute("SELECT id FROM patients WHERE name=?", (name,))
    row = cur.fetchone()
    if row: return row[0]
    conn.execute("INSERT INTO patients (name) VALUES (?)", (name,))
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

# ====== 遍历所有Excel文件 ======
total_apt = 0
total_con = 0
patient_recharge = {}  # pid -> total recharge
patient_spent = {}     # pid -> total spent

for fname in sorted(os.listdir(EXCEL_DIR)):
    if not fname.endswith('.xlsx'): continue
    month = None
    m = re.search(r'(\d+)月', fname)
    if m: month = int(m.group(1))
    if not month: continue
    
    fpath = os.path.join(EXCEL_DIR, fname)
    wb = openpyxl.load_workbook(fpath)
    print(f'\n{fname} (month={month}, sheets={len(wb.sheetnames)})')
    
    for sname in wb.sheetnames:
        ws = wb[sname]
        # 解析day range: 如 "1-7" 或 "1-1"
        parts = sname.split('-')
        if len(parts) != 2: continue
        try:
            start_day = int(parts[0])
            end_day = int(parts[1])
        except: continue
        
        # 行2: 日期头 (每2列一个日期)
        row2 = [c.value for c in ws[2]]
        # 行4开始: 时段行（对应 TIME_SLOTS）
        
        for row_idx in range(4, ws.max_row + 1):
            time_slot_idx = row_idx - 4
            if time_slot_idx >= len(TIME_SLOTS): break
            
            row_data = [c.value for c in ws[row_idx]]
            ts = row_data[0]
            if not ts or str(ts).strip() not in TIME_SLOTS:
                # 可能是空的或者时段名不同
                continue
            
            col = 1  # 从第2列开始（B列=预约列）
            for day_offset in range(end_day - start_day + 1):
                day = start_day + day_offset
                apt_col = 1 + day_offset * 2  # 预约列
                remark_col = apt_col + 1       # 备注列
                
                apt_val = row_data[apt_col] if apt_col < len(row_data) else None
                remark_val = row_data[remark_col] if remark_col < len(row_data) else None
                
                if not apt_val: continue
                
                parsed = parse_cell(apt_val)
                if not parsed: continue
                
                name, project, apt_amount = parsed
                
                # 从备注提取额外信息
                remark_extra = ''
                remark_amount = 0
                if remark_val:
                    remark_str = str(remark_val).strip()
                    remark_extra = remark_str
                    nums = re.findall(r'\d+', remark_str)
                    if nums:
                        remark_amount = int(nums[-1])
                
                final_amount = remark_amount if remark_amount > 0 else apt_amount
                if final_amount == 0:
                    final_amount = 300  # 默认金额
                
                pid = get_or_create_patient(conn, name)
                
                conn.execute(
                    "INSERT INTO appointments (patient_id, year, month, day, time_slot, project, amount, remark) VALUES (?,?,?,?,?,?,?,?)",
                    (pid, YEAR, month, day, TIME_SLOTS[time_slot_idx], project, final_amount, remark_extra)
                )
                aid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                
                # 创建关联耗卡
                conn.execute(
                    "INSERT INTO consumption (patient_id, month, day, project, amount, time_slot, sync_to_apt) VALUES (?,?,?,?,?,?,?)",
                    (pid, month, day, project, final_amount, TIME_SLOTS[time_slot_idx], 1)
                )
                cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                
                # 创建关联
                conn.execute(
                    "INSERT INTO appointment_consumption_link (appointment_id, consumption_id) VALUES (?,?)",
                    (aid, cid)
                )
                
                patient_spent[pid] = patient_spent.get(pid, 0) + final_amount
                
                total_apt += 1
                total_con += 1
                print(f"  {month}/{day} {TIME_SLOTS[time_slot_idx]} {name} {project} ¥{final_amount}")

conn.commit()

# ====== 更新患者余额 ======
for pid in patient_spent:
    rch = patient_recharge.get(pid, 0)
    spent = patient_spent.get(pid, 0)
    balance = max(0, rch - spent)
    has_rch = 1 if rch > 0 else 0
    conn.execute("UPDATE patients SET balance=?, has_recharge=? WHERE id=?", (balance, has_rch, pid))

conn.commit()
conn.close()

print(f'\n=== DONE ===')
print(f'Appointments: {total_apt}')
print(f'Consumption: {total_con}')
print(f'Patients: {len(patient_spent)}')

# ====== 重启 ======
subprocess.run(['systemctl', 'start', 'clinic-app'], capture_output=True)
print('restarted clinic-app')