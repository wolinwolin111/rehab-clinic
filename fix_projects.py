import sqlite3
conn = sqlite3.connect('/root/clinic-app/data/clinic.db')
c = conn.cursor()

# 清空现有项目
c.execute('DELETE FROM treatment_projects')

# 插入正确的3个项目
projects = [
    ('康复', 400, 1),
    ('放松', 169, 2),
    ('评估', 99, 3),
]
for name, price, sort in projects:
    c.execute('INSERT INTO treatment_projects (name, default_price, sort_order) VALUES (?,?,?)', (name, price, sort))

conn.commit()

# 验证
c.execute('SELECT name, default_price FROM treatment_projects ORDER BY sort_order')
print('治疗项目:')
for row in c.fetchall():
    print(f'  {row[0]}: {row[1]}元')

conn.close()
