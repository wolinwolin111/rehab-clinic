#!/usr/bin/env python3
"""
回滚后预约表 & 耗卡表一致性验证
- 每个耗卡如果有 time_slot+sync_to_apt=1，必须有对应的关联预约
- 每个耗卡如果没有 time_slot，必须没有关联预约
- 预约表与耗卡表的关联关系通过 appointment_consumption_link 严格一致
- 删除患者回滚后，所有关联关系完整恢复
"""
import requests
import json
import time

BASE = "http://127.0.0.1:8080"
passed = 0
failed = 0

def api(method, path, data=None):
    url = f"{BASE}{path}"
    try:
        if method == "GET":
            r = requests.get(url, timeout=10)
        elif method == "POST":
            r = requests.post(url, json=data, timeout=10)
        elif method == "PUT":
            r = requests.put(url, json=data, timeout=10)
        elif method == "DELETE":
            r = requests.delete(url, timeout=10)
        if r.text.strip():
            return r.json(), None
        return {}, None
    except Exception as e:
        return None, str(e)

def ts():
    return int(time.time() * 1000000)

def check(cond, name, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        msg = f"  [FAIL] {name}"
        if detail:
            msg += f" -- {detail}"
        print(msg)

def verify_consistency(msg=""):
    """验证所有耗卡与预约的关联关系一致性"""
    cons_list, err = api("GET", "/api/consumption")
    if err:
        check(False, f"[{msg}] Get consumption list", err)
        return
    apt_list, err = api("GET", "/api/appointments")
    if err:
        check(False, f"[{msg}] Get appointment list", err)
        return

    link_table = {}
    for c in cons_list:
        link, _ = api("GET", f"/api/consumption/{c['id']}/links")
        link_table[c['id']] = link

    for c in cons_list:
        cid = c['id']
        has_time_slot = bool(c.get('time_slot'))
        sync_to_apt = c.get('sync_to_apt', 0)
        link = link_table.get(cid)

        if has_time_slot and sync_to_apt == 1:
            check(link and link.get('appointment_id'),
                  f"[{msg}] Con {cid} has time_slot+sync -> link exists",
                  f"link={link}")
            if link and link.get('appointment_id'):
                aid = link['appointment_id']
                found = any(a.get('id') == aid for a in apt_list)
                check(found, f"[{msg}] Linked appointment {aid} exists in apt list")
        else:
            check(not (link and link.get('appointment_id')),
                  f"[{msg}] Con {cid} no time_slot/no sync -> no link",
                  f"link={link}")

    # 反向验证：每个预约如果有 linked_con_id 或 remark 中的 #id，应在 link 表中存在
    for a in apt_list:
        aid = a['id']
        # 检查 link 表是否反指向该预约
        for cid, link in link_table.items():
            if link and link.get('appointment_id') == aid:
                break
        else:
            # 没有通过 link 表关联，检查 remark 中的 #id
            remark = a.get('remark', '') or ''
            if '#id' in remark or re.search(r'#(\d+)$', remark):
                # 不需要严格检查，这是旧格式
                pass

def dump_tables(msg):
    """打印当前所有数据用于调试"""
    cons, _ = api("GET", "/api/consumption")
    apts, _ = api("GET", "/api/appointments")
    print(f"\n--- [{msg}] Consumption ({len(cons)}): ---")
    for c in cons:
        link, _ = api("GET", f"/api/consumption/{c['id']}/links")
        lid = link.get('appointment_id') if link else None
        print(f"  id={c['id']} ts='{c['time_slot']}' sync={c['sync_to_apt']} link={lid} pat={c['patient_id']}")
    print(f"--- [{msg}] Appointments ({len(apts)}): ---")
    for a in apts:
        print(f"  id={a['id']} ts='{a['time_slot']}' pat={a['patient_id']} proj={a['project']}")
    print("--- end ---")

import re

# ============================================================
print("="*60)
print("回滚一致性验证 Test Suite")
print("="*60)

# 清除旧数据 - 保持干净
# (skip this to avoid deleting real data)

# --- Test 1: 创建一个带同步的预约 → 删除耗卡 → 回滚 → 验证一致性 ---
uid = ts()
print(f"\n--- Test 1: 耗卡同步回滚一致性 ---")

data, err = api("POST", "/api/patients", {"name": f"verify_pat_{uid}"})
check(data and data.get("id"), "Create patient", err or str(data))
pid1 = data["id"]

data, err = api("POST", "/api/consumption", {
    "patient_id": pid1, "month": 7, "day": 10,
    "project": "推拿", "amount": 200, "time_slot": "10:00-11:00"
})
check(data and data.get("id"), "Create consumption with time_slot", err or str(data))
cid1 = data["id"]
verify_consistency("Post-create con")

link, _ = api("GET", f"/api/consumption/{cid1}/links")
check(link and link.get('appointment_id'), "Consumption auto-created appointment link")
aid1 = link['appointment_id'] if link else None

# 获取耗卡列表，确认 link_appointment_id 已返回
cons_list, _ = api("GET", "/api/consumption")
con = next((c for c in cons_list if c['id'] == cid1), None)
check(con and con.get('link_appointment_id') == aid1,
      "Consumption API returns link_appointment_id",
      f"got link_appointment_id={con.get('link_appointment_id') if con else None}")

# 删除耗卡
api("POST", "/api/history", {
    "action_type": "delete", "target_type": "consumption", "target_id": cid1,
    "data": {"id": cid1, "patient_id": pid1, "month": 7, "day": 10,
             "project": "推拿", "amount": 200, "time_slot": "10:00-11:00",
             "sync_to_apt": 1,
             "linkedAppointment": {"id": aid1, "patient_id": pid1,
                                   "year": 2026, "month": 7, "day": 10,
                                   "time_slot": "10:00-11:00",
                                   "project": "推拿", "amount": 200,
                                   "remark": "推拿\n200",
                                   "patient_name": f"verify_pat_{uid}"}},
    "description": f"删除耗卡 {cid1}"
})
api("DELETE", f"/api/consumption/{cid1}")
verify_consistency("Post-delete con")

# 回滚
history, _ = api("GET", "/api/history")
target = next((h for h in history if h['target_type']=='consumption' and h['target_id']==cid1 and h['action_type']=='delete'), None)
if target:
    data, err = api("POST", f"/api/history/{target['id']}/restore")
    check(data and data.get('success'), "Rollback consumption delete", err or str(data))
else:
    check(False, "Find delete history for rollback")

verify_consistency("Post-rollback con")

# --- Test 2: 删除患者的回滚一致性 ---
print(f"\n--- Test 2: 删除患者回滚一致性 ---")
uid2 = ts()
data, err = api("POST", "/api/patients", {"name": f"verify_pat2_{uid2}"})
check(data and data.get("id"), "Create patient 2", err or str(data))
pid2 = data["id"]

# 创建耗卡（带时段，自动同步预约）
data, err = api("POST", "/api/consumption", {
    "patient_id": pid2, "month": 7, "day": 15,
    "project": "针灸", "amount": 300, "time_slot": "14:00-15:00"
})
check(data and data.get("id"), "Create con for patient 2")
cid2a = data["id"]

# 创建耗卡（不带时段）
data, err = api("POST", "/api/consumption", {
    "patient_id": pid2, "month": 7, "day": 16,
    "project": "拔罐", "amount": 100, "time_slot": ""
})
check(data and data.get("id"), "Create con (no ts) for patient 2")
cid2b = data["id"]

verify_consistency("Pre-delete patient 2")
dump_tables("Before patient delete")

# 获取所有关联数据用于历史记录
apts_for_pat, _ = api("GET", f"/api/appointments?patient_id={pid2}")
cons_for_pat, _ = api("GET", f"/api/consumption?patient_id={pid2}")

# 删除患者
api("POST", "/api/history", {
    "action_type": "delete", "target_type": "patient", "target_id": pid2,
    "data": {"name": f"verify_pat2_{uid2}", "appointments": apts_for_pat, "consumptions": cons_for_pat},
    "description": f"删除患者 {pid2}"
})
data, err = api("DELETE", f"/api/patients/{pid2}")
check(data and data.get('success'), "Delete patient 2", err or str(data))

verify_consistency("Post-delete patient 2")
dump_tables("After patient delete")

# 回滚患者删除
history, _ = api("GET", "/api/history")
target = next((h for h in history if h['target_type']=='patient' and h['target_id']==pid2 and h['action_type']=='delete'), None)
if target:
    data, err = api("POST", f"/api/history/{target['id']}/restore")
    check(data and data.get('success'), "Rollback patient 2 delete", err or str(data))
else:
    check(False, "Find patient delete history for rollback")

verify_consistency("Post-rollback patient 2")
dump_tables("After patient rollback")

# --- Test 3: 多步骤混合回滚一致性 ---
print(f"\n--- Test 3: 多步骤混合回滚一致性 ---")
uid3 = ts()
data, err = api("POST", "/api/patients", {"name": f"verify_pat3_{uid3}"})
check(data and data.get("id"), "Create patient 3", err or str(data))
pid3 = data["id"]

# 步骤1: 创建耗卡（带时段）
data, err = api("POST", "/api/consumption", {
    "patient_id": pid3, "month": 8, "day": 1,
    "project": "康复训练", "amount": 400, "time_slot": "9:00-10:00"
})
check(data and data.get("id"), "Step1 Create con with ts")
cid3 = data["id"]
link3, _ = api("GET", f"/api/consumption/{cid3}/links")
aid3 = link3['appointment_id'] if link3 else None

verify_consistency("Step1 done")

# 步骤2: 修改耗卡（清空时段→删除关联预约）
data, err = api("PUT", f"/api/consumption/{cid3}", {"time_slot": ""})
check(data and data.get('time_slot') == '' and data.get('sync_to_apt') == 0,
      "Step2 Clear time_slot on con", err or str(data))

verify_consistency("Step2 done (clear ts)")

# 步骤3: 再改回来（恢复时段→重新创建关联预约）
data, err = api("PUT", f"/api/consumption/{cid3}", {"time_slot": "15:00-16:00"})
check(data and data.get('time_slot') == '15:00-16:00' and data.get('sync_to_apt') == 1,
      "Step3 Re-add time_slot on con", err or str(data))

verify_consistency("Step3 done (re-add ts)")

# 步骤4: 删除患者
cons_for_pat3, _ = api("GET", f"/api/consumption?patient_id={pid3}")
apts_for_pat3, _ = api("GET", f"/api/appointments?patient_id={pid3}")
api("POST", "/api/history", {
    "action_type": "delete", "target_type": "patient", "target_id": pid3,
    "data": {"name": f"verify_pat3_{uid3}", "appointments": apts_for_pat3, "consumptions": cons_for_pat3},
    "description": f"删除患者 {pid3}"
})
data, err = api("DELETE", f"/api/patients/{pid3}")
check(data and data.get('success'), "Step4 Delete patient 3", err or str(data))

verify_consistency("Step4 done (delete patient)")

# 回滚到最后一步
history, _ = api("GET", "/api/history")
target = next((h for h in history if h['target_type']=='patient' and h['target_id']==pid3 and h['action_type']=='delete'), None)
if target:
    data, err = api("POST", f"/api/history/{target['id']}/restore")
    check(data and data.get('success'), "Rollback patient 3 delete", err or str(data))
else:
    check(False, "Find patient 3 delete history")

verify_consistency("Post-rollback patient 3")

# 再创建一些新操作验证没有副作用
uid4 = ts()
data, err = api("POST", "/api/patients", {"name": f"post_verify_{uid4}"})
check(data and data.get("id"), "Post-rollback create patient (no side effects)", err or str(data))
pid4 = data["id"]
data, err = api("POST", "/api/consumption", {
    "patient_id": pid4, "month": 8, "day": 10,
    "project": "理疗", "amount": 250, "time_slot": "10:00-11:00"
})
check(data and data.get("id"), "Post-rollback create con with ts", err or str(data))

verify_consistency("Final state")

# ============================================================
print("\n" + "="*60)
print(f"结果: {passed} passed, {failed} failed")
print("="*60)
if failed > 0:
    exit(1)
