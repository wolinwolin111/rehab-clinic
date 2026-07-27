#!/usr/bin/env python3
"""测试诊所系统 CRUD 操作 — 匹配实际 API"""

import requests, json, sys, time

BASE_URL = "http://66.154.101.204"

def api(path, method='get', data=None):
    url = f"{BASE_URL}{path}"
    if method == 'get':
        return requests.get(url, timeout=15)
    elif method == 'post':
        return requests.post(url, json=data, timeout=15)
    elif method == 'put':
        return requests.put(url, json=data, timeout=15)
    elif method == 'delete':
        return requests.delete(url, timeout=15)

def test_patient_crud():
    print("\n=== 测试患者 CRUD ===")
    ts = int(time.time())
    
    resp = api('/api/patients', 'post', {"name":f"测试患者_A_{ts}","gender":"男","phone":f"139{ts:010d}","age":30})
    if resp.status_code != 200:
        print(f"创建失败: {resp.status_code} {resp.text}")
        return False
    pid = resp.json().get('id')
    print(f"创建患者 ID={pid}")
    
    resp = api('/api/patients')
    all_p = resp.json()
    found = any(p['id'] == pid for p in all_p)
    print(f"列表中能找到: {found}")
    
    resp = api(f'/api/patients/{pid}', 'put', {"name":f"测试患者_A_{ts}(改)","gender":"女","phone":f"139{ts:010d}","age":31})
    if resp.status_code != 200:
        print(f"更新失败: {resp.status_code} {resp.text}")
        return False
    print("更新成功")
    
    resp = api(f'/api/patients/{pid}', 'delete')
    if resp.status_code != 200:
        print(f"删除失败: {resp.status_code} {resp.text}")
        return False
    print("删除成功")
    
    resp = api('/api/patients')
    all_p = resp.json()
    found = any(p['id'] == pid for p in all_p)
    print(f"数据库已删除: {not found}")
    return True

def test_appointment_crud():
    print("\n=== 测试预约 CRUD ===")
    ts = int(time.time())
    
    resp = api('/api/patients', 'post', {"name":f"预约测试患者_{ts}","gender":"女","phone":f"139{ts:010d}","age":25})
    if resp.status_code != 200:
        print(f"创建患者失败: {resp.text}")
        return False
    pid = resp.json()['id']
    
    resp = api('/api/appointments', 'post', {
        "patient_id": pid, "year": 2026, "month": 7,
        "day": 15, "time_slot": "14:00-15:00",
        "project": "复诊", "amount": 150, "remark": "测试就诊"
    })
    if resp.status_code != 200:
        print(f"创建预约失败: {resp.status_code} {resp.text}")
        api(f'/api/patients/{pid}', 'delete')
        return False
    aid = resp.json().get('id')
    print(f"创建预约 ID={aid}")
    
    resp = api('/api/appointments')
    apts = resp.json()
    found = any(a['id'] == aid for a in apts)
    print(f"列表中找到预约: {found}")
    
    resp = api(f'/api/appointments/{aid}', 'put', {
        "patient_id": pid, "year": 2026, "month": 7,
        "day": 16, "time_slot": "16:00-17:00",
        "project": "理疗", "amount": 200, "remark": "改期"
    })
    if resp.status_code != 200:
        print(f"更新失败: {resp.status_code} {resp.text}")
        return False
    print("更新成功")
    
    resp = api(f'/api/appointments/{aid}', 'delete')
    if resp.status_code != 200:
        print(f"删除失败: {resp.status_code} {resp.text}")
        return False
    print("删除成功")
    
    api(f'/api/patients/{pid}', 'delete')
    return True

def test_consumption_crud():
    print("\n=== 测试消费记录 CRUD ===")
    ts = int(time.time())
    
    resp = api('/api/patients', 'post', {"name":f"消费测试患者_{ts}","gender":"男","phone":f"139{ts:010d}","age":40})
    if resp.status_code != 200:
        print(f"创建患者失败: {resp.text}")
        return False
    pid = resp.json()['id']
    
    resp = api('/api/consumption', 'post', {
        "patient_id": pid, "month": 7, "day": 20,
        "project": "治疗", "amount": 300,
        "time_slot": "10:00-11:00", "sync_to_apt": 0
    })
    if resp.status_code != 200:
        print(f"创建消费失败: {resp.status_code} {resp.text}")
        api(f'/api/patients/{pid}', 'delete')
        return False
    cid = resp.json().get('id')
    print(f"创建消费 ID={cid}")
    
    resp = api(f'/api/consumption?patient_id={pid}')
    items = resp.json()
    found = any(c['id'] == cid for c in items)
    print(f"列表中找到消费: {found}")
    
    resp = api(f'/api/consumption/{cid}', 'put', {
        "patient_id": pid, "month": 7, "day": 21,
        "project": "项目更新", "amount": 500,
        "time_slot": "11:00-12:00", "sync_to_apt": 0
    })
    if resp.status_code != 200:
        print(f"更新失败: {resp.status_code} {resp.text}")
        return False
    print("更新成功")
    
    resp = api(f'/api/consumption/{cid}', 'delete')
    if resp.status_code != 200:
        print(f"删除失败: {resp.status_code} {resp.text}")
        return False
    print("删除成功")
    
    api(f'/api/patients/{pid}', 'delete')
    return True

def test_fk_cascade():
    print("\n=== 测试外键级联删除 ===")
    ts = int(time.time())
    
    resp = api('/api/patients', 'post', {"name":f"级联测试_{ts}","gender":"男","phone":f"139{ts:010d}","age":35})
    if resp.status_code != 200:
        print(f"创建患者失败: {resp.text}")
        return False
    pid = resp.json()['id']
    
    resp = api('/api/appointments', 'post', {
        "patient_id": pid, "year": 2026, "month": 8,
        "day": 5, "time_slot": "09:00-10:00",
        "project": "手术", "amount": 2000
    })
    if resp.status_code != 200:
        print(f"创建预约失败: {resp.text}")
        api(f'/api/patients/{pid}', 'delete')
        return False
    aid = resp.json()['id']
    
    resp = api('/api/consumption', 'post', {
        "patient_id": pid, "month": 8, "day": 5,
        "project": "手术费", "amount": 2000,
        "time_slot": "09:00-10:00", "sync_to_apt": 1
    })
    if resp.status_code != 200:
        print(f"创建消费失败: {resp.text}")
        api(f'/api/patients/{pid}', 'delete')
        return False
    cid = resp.json().get('id')
    
    resp = api(f'/api/patients/{pid}', 'delete')
    if resp.status_code != 200:
        print(f"删除患者失败: {resp.text}")
        return False
    print("患者已删除，验证级联...")
    
    resp = api('/api/appointments')
    apts = resp.json()
    found_apt = any(a['id'] == aid for a in apts)
    print(f"预约级联删除: {'FAIL - 还存在!' if found_apt else 'PASS'}")
    
    resp = api(f'/api/consumption?patient_id={pid}')
    items = resp.json()
    found_con = any(c['id'] == cid for c in items)
    print(f"消费级联删除: {'FAIL - 还存在!' if found_con else 'PASS'}")
    
    return not found_apt and not found_con

def test_validation():
    print("\n=== 输入验证 ===")
    
    resp = api('/api/patients', 'post', {"name":"","gender":"男","phone":"123","age":30})
    r1 = resp.status_code == 400
    print(f"空名称拒绝: {'PASS' if r1 else 'FAIL (accepted)'}")
    
    resp = api('/api/patients', 'post', {"name":"测试","gender":"男","phone":"","age":30})
    r2 = resp.status_code == 400
    print(f"空电话拒绝: {'PASS' if r2 else 'FAIL (accepted)'}")
    
    resp = api('/api/patients', 'post', {"name":"测试","gender":"男","phone":"123456","age":150})
    r3 = resp.status_code == 400
    print(f"无效年龄拒绝: {'PASS' if r3 else 'FAIL (accepted)'}")
    
    return r1 and r2 and r3

def main():
    ts = int(time.time())
    print(f"诊所系统测试 — {BASE_URL} (时间戳: {ts})")
    print("=" * 50)
    
    tests = [
        ("患者 CRUD", test_patient_crud),
        ("预约 CRUD", test_appointment_crud),
        ("消费记录 CRUD", test_consumption_crud),
        ("外键级联删除", test_fk_cascade),
        ("输入验证", test_validation),
    ]
    
    results = []
    for name, func in tests:
        try:
            ok = func()
            results.append((name, ok))
            print(f">>> {name}: {'PASS' if ok else 'FAIL'}\n")
        except Exception as e:
            print(f">>> {name}: ERROR - {e}\n")
            results.append((name, False))
    
    print("=" * 50)
    print("测试汇总")
    print("=" * 50)
    all_pass = True
    for n, ok in results:
        print(f"  {n:20s} {'PASS' if ok else 'FAIL'}")
        if not ok: all_pass = False
    print("=" * 50)
    if all_pass:
        print("全部通过!")
    else:
        print("部分失败!")
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
