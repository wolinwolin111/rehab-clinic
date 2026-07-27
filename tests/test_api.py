#!/usr/bin/env python3
"""康复管理系统 - 自动化测试套件"""
import requests, json, time, random

BASE = "http://127.0.0.1:8080/api"
PASS = 0
FAIL = 0

def ok(cond, msg):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  ✓ {msg}")
    else:
        FAIL += 1; print(f"  ✗ {msg}")
    return cond

def api(method, path, data=None):
    url = BASE + path
    if method == 'GET':
        r = requests.get(url, timeout=10)
    elif method == 'POST':
        r = requests.post(url, json=data, timeout=10)
    elif method == 'PUT':
        r = requests.put(url, json=data, timeout=10)
    elif method == 'DELETE':
        r = requests.delete(url, timeout=10)
    return r

print("=" * 50)
print("测试1: 基础CRUD — 患者/预约/耗卡/充值")
print("=" * 50)

# 1a. 创建测试患者
r = api('POST', '/patients', {"name": "_TEST_AUTO_张三", "age": "30", "gender": "男"})
ok(r.status_code == 200, f"创建患者: {r.status_code}")
pid = r.json().get('id') if r.ok else None
print(f"   患者ID={pid}")

# 1b. 创建预约（含充值5000）
apt_data = {"patient_id": pid, "year": 2026, "month": 7, "day": 27, "time_slot": "10:00-11:00",
            "project": "评估+治疗", "amount": 312, "sync_to_con": True, "recharge_amount": 5000}
r = api('POST', '/appointments', apt_data)
ok(r.status_code == 200, f"创建预约(充值5000): {r.status_code}")
aid = r.json().get('id') if r.ok else None
print(f"   预约ID={aid}")

# 1c. 验证耗卡自动创建
r = api('GET', f'/consumption?patient_id={pid}')
cons = r.json()
ok(len(cons) >= 1, f"耗卡自动创建: {len(cons)}条")
cid = cons[0]['id'] if cons else None
if cons:
    ok(cons[0]['recharge_amount'] == 5000, f"耗卡充值金额={cons[0]['recharge_amount']}")
    ok(cons[0]['amount'] == 312, f"耗卡消费金额={cons[0]['amount']}")

# 1d. 验证余额
r = api('GET', '/patients')
pat = [p for p in r.json() if p['id'] == pid][0]
ok(pat['has_recharge'] == 1, f"has_recharge=1")
ok(pat['balance'] == 5000 - 312, f"余额={pat['balance']} (期望{5000-312})")

# 1e. 修改预约（改充值到3000）
r = api('PUT', f'/appointments/{aid}', {"recharge_amount": 3000})
ok(r.status_code == 200, f"修改充值3000: {r.status_code}")

# 1f. 验证耗卡同步更新
r = api('GET', f'/consumption?patient_id={pid}')
cons2 = r.json()
ok(len(cons2) >= 1 and cons2[0]['recharge_amount'] == 3000, f"耗卡充值同步={cons2[0]['recharge_amount'] if cons2 else 'N/A'}")

# 1g. 验证余额重算
r = api('GET', '/patients')
pat2 = [p for p in r.json() if p['id'] == pid][0]
ok(pat2['balance'] == 3000 - 312, f"余额={pat2['balance']} (期望{3000-312})")

# 1h. 取消充值
r = api('PUT', f'/appointments/{aid}', {"recharge_amount": 0})
ok(r.status_code == 200, f"取消充值: {r.status_code}")

r = api('GET', f'/consumption?patient_id={pid}')
ok(len(r.json()) >= 1 and r.json()[0]['recharge_amount'] == 0, f"耗卡充值清零={r.json()[0]['recharge_amount'] if r.json() else 'N/A'}")

r = api('GET', '/patients')
pat3 = [p for p in r.json() if p['id'] == pid][0]
ok(pat3['balance'] == 0 and pat3['has_recharge'] == 0, f"余额=0, has_recharge=0 (余额={pat3['balance']}, has={pat3['has_recharge']})")

print()
print("=" * 50)
print("测试2: 级联删除 — 删除预约→耗卡消失, 删除患者→全部消失")
print("=" * 50)

# 2a. 重新充值
api('PUT', f'/appointments/{aid}', {"recharge_amount": 2000})

# 2b. 删除预约
r = api('DELETE', f'/appointments/{aid}')
ok(r.status_code == 200, f"删除预约: {r.status_code}")

# 2c. 验证耗卡也删了
r = api('GET', f'/consumption?patient_id={pid}')
ok(len(r.json()) == 0, f"耗卡级联删除: {len(r.json())}条")

# 2d. 重新创建预约+耗卡
r = api('POST', '/appointments', {**apt_data, "recharge_amount": 1000, "day": 28})
ok(r.status_code == 200, f"重建预约: {r.status_code}")
aid2 = r.json().get('id') if r.ok else None

# 2e. 删除患者
r = api('DELETE', f'/patients/{pid}')
ok(r.status_code == 200, f"删除患者: {r.status_code}")

# 2f. 验证预约和耗卡都删了
r = api('GET', f'/appointments?patient_id={pid}')
ok(len(r.json()) == 0, f"预约级联删除: {len(r.json())}条")
r = api('GET', f'/consumption?patient_id={pid}')
ok(len(r.json()) == 0, f"耗卡级联删除: {len(r.json())}条")

print()
print("=" * 50)
print("测试3: 多次充值+消费场景 (余额正确性)")
print("=" * 50)

# 3a. 创建患者
r = api('POST', '/patients', {"name": "_TEST_AUTO_李四", "age": "25"})
pid = r.json()['id']
ok(r.status_code == 200, f"创建患者 id={pid}")

# 3b. 创建多条预约（逐条充值+消费）
total_recharge = 0
total_spent = 0
aids = []
for i, (day, amt, rch) in enumerate([(1, 200, 3000), (5, 300, 0), (10, 250, 0), (15, 400, 2000), (20, 350, 0)]):
    r = api('POST', '/appointments', {"patient_id": pid, "year": 2026, "month": 8, "day": day,
        "time_slot": "14:00-15:00", "project": "治疗", "amount": amt, "sync_to_con": True, "recharge_amount": rch})
    ok(r.status_code == 200, f"创建预约 day={day} amt={amt} rch={rch}")
    if r.ok: aids.append(r.json()['id'])
    total_recharge += rch
    total_spent += amt

expected_balance = max(0, total_recharge - total_spent)
print(f"   总充值={total_recharge} 总消费={total_spent} 期望余额={expected_balance}")

# 3c. 验证余额
r = api('GET', '/patients')
pat = [p for p in r.json() if p['id'] == pid][0]
ok(pat['balance'] == expected_balance, f"余额={pat['balance']} (期望{expected_balance})")
ok(pat['has_recharge'] == 1, f"has_recharge=1")

# 3d. 验证耗卡数量
r = api('GET', f'/consumption?patient_id={pid}')
ok(len(r.json()) == 5, f"耗卡数量={len(r.json())} (期望5)")

# 3e. 修改中间一条预约增加充值
r = api('PUT', f'/appointments/{aids[1]}', {"recharge_amount": 1500})
ok(r.status_code == 200, f"中间预约加充值1500")
total_recharge += 1500
expected_balance = max(0, total_recharge - total_spent)
r = api('GET', '/patients')
pat = [p for p in r.json() if p['id'] == pid][0]
ok(pat['balance'] == expected_balance, f"余额重算={pat['balance']} (期望{expected_balance})")

# 清理
api('DELETE', f'/patients/{pid}')
print(f"   清理完成")

print()
print("=" * 50)
print("测试4: 回滚操作")
print("=" * 50)

# 4a. 创建患者+预约
r = api('POST', '/patients', {"name": "_TEST_AUTO_回滚测试"})
pid = r.json()['id']
r = api('POST', '/appointments', {"patient_id": pid, "year": 2026, "month": 9, "day": 1,
    "time_slot": "16:00-17:00", "project": "治疗", "amount": 300, "sync_to_con": True, "recharge_amount": 5000})
aid = r.json()['id']

# 4b. 查看历史记录
r = api('GET', '/history')
history = r.json()
ok(len(history) >= 2, f"历史记录数={len(history)}")
last_hid = history[0]['id']
print(f"   最新操作: {history[0]['description']}")

# 4c. 回滚（恢复患者的创建）
# 找创建患者的操作
patient_create = [h for h in history if h['target_type'] == 'patient' and h['action_type'] == 'add']
if patient_create:
    hid = patient_create[0]['id']
    print(f"   回滚患者创建 (hid={hid})")
else:
    # 用创建预约的
    hid = history[1]['id'] if len(history) > 1 else history[0]['id']
    print(f"   回滚操作 (hid={hid})")

# 回滚会同时撤销之后的所有操作
# 先不做太复杂的回滚测试，简单验证回滚API可用
r = api('POST', f'/history/{hid}/restore')
ok(r.status_code == 200, f"回滚API可用: {r.status_code}")

# 清理
api('DELETE', f'/patients/{pid}')

print()
print("=" * 50)
print("测试5: 随机压力测试")
print("=" * 50)

# 创建患者
r = api('POST', '/patients', {"name": "_TEST_STRESS_" + str(random.randint(1000,9999))})
pid = r.json()['id']

aids = []
for _ in range(5):
    day = random.randint(1, 28)
    amt = random.choice([200, 300, 400])
    rch = random.choice([0, 0, 1000, 2000, 5000])
    r = api('POST', '/appointments', {"patient_id": pid, "year": 2026, "month": 10, "day": day,
        "time_slot": f"{random.randint(8,20)}:00-{random.randint(9,21)}:00", "project": "治疗",
        "amount": amt, "sync_to_con": True, "recharge_amount": rch})
    if r.ok: aids.append(r.json()['id'])

ok(len(aids) == 5, f"随机创建5条预约: {len(aids)}条")

# 随机修改
for _ in range(3):
    aid = random.choice(aids)
    rch = random.choice([0, 500, 3000])
    r = api('PUT', f'/appointments/{aid}', {"recharge_amount": rch})
    ok(r.status_code == 200, f"随机修改充值: id={aid} rch={rch}")

# 验证最终数据一致性
r = api('GET', f'/consumption?patient_id={pid}')
cons_count = len(r.json())
r2 = api('GET', f'/appointments?patient_id={pid}')
apt_count = len(r2.json())
ok(cons_count == apt_count, f"耗卡数={cons_count} == 预约数={apt_count}")

# 验证余额
total_rch_api = sum(c['recharge_amount'] for c in r.json() if c.get('recharge_amount'))
total_amt_api = sum(c['amount'] for c in r.json() if c.get('amount'))
r3 = api('GET', '/patients')
pat = [p for p in r3.json() if p['id'] == pid][0] if any(p['id']==pid for p in r3.json()) else None
if pat:
    ok(pat['balance'] == max(0, total_rch_api - total_amt_api),
       f"余额一致性: {pat['balance']} vs {max(0, total_rch_api - total_amt_api)}")

# 随机删除
aid_del = random.choice(aids)
r = api('DELETE', f'/appointments/{aid_del}')
ok(r.status_code == 200, f"随机删除预约: id={aid_del}")

# 清理
api('DELETE', f'/patients/{pid}')

print()
print("=" * 50)
print(f"测试结果: {PASS} 通过, {FAIL} 失败, 共 {PASS+FAIL} 项")
print("=" * 50)