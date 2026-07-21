#!/usr/bin/env python3
"""
Full CRUD + Mixed Scenarios + Rollback Test Suite
Tests: Patient/Appointment/Consumption CRUD, sync links, mixed ops, rollback
"""
import requests
import json
import time
import sys

BASE = "http://127.0.0.1:8080"

passed = 0
failed = 0
errors = []

def log_pass(name):
    global passed
    passed += 1
    print(f"  [PASS] {name}")

def log_fail(name, detail=""):
    global failed
    failed += 1
    msg = f"  [FAIL] {name}"
    if detail:
        msg += f" -- {detail}"
    print(msg)
    errors.append(f"{name}: {detail}")

def api(method, path, data=None, expected_status=None):
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
        else:
            raise ValueError(f"Unknown method {method}")
        if expected_status and r.status_code != expected_status:
            return None, f"status={r.status_code}, expected={expected_status}, body={r.text[:200]}"
        if r.text.strip():
            return r.json(), None
        return {}, None
    except Exception as e:
        return None, str(e)

def find_in_list(data_list, key, value):
    if not data_list:
        return None
    for item in data_list:
        if item.get(key) == value:
            return item
    return None

def ts():
    return int(time.time() * 1000)

def log_history(action_type, target_type, target_id, data, description):
    api("POST", "/api/history", {
        "action_type": action_type,
        "target_type": target_type,
        "target_id": target_id,
        "data": data,
        "description": description
    })

# ============================================================
# Section 1: Patient CRUD
# ============================================================
def test_patient_crud():
    print("\n" + "="*60)
    print("Section 1: Patient CRUD")
    print("="*60)
    uid = ts()
    name = f"test_pat_{uid}"
    updated_name = f"test_pat_{uid}_renamed"

    data, err = api("POST", "/api/patients", {"name": name, "age": "35", "gender": "male"})
    if err or not data or not data.get("id"):
        log_fail("Create patient", err or "no id")
        return None
    pid = data["id"]
    log_pass("Create patient")

    data, err = api("GET", "/api/patients")
    if err:
        log_fail("List patients", err)
    pat = find_in_list(data, "id", pid)
    if pat and pat["name"] == name and pat["age"] == "35":
        log_pass("Find patient in list (verify fields)")
    else:
        log_fail("Find patient in list", f"expected name={name}, got {pat}")

    data, err = api("PUT", f"/api/patients/{pid}", {"name": updated_name, "age": "40"})
    if err:
        log_fail("Update patient", err)
    elif data and data["name"] == updated_name and data["age"] == "40":
        log_pass("Update patient")
    else:
        log_fail("Update patient", f"got {data}")

    data, err = api("GET", "/api/patients")
    pat = find_in_list(data, "id", pid)
    if pat and pat["name"] == updated_name:
        log_pass("Verify update persisted in list")
    else:
        log_fail("Verify update persisted", f"got {pat}")

    return pid

# ============================================================
# Section 2: Appointment CRUD
# ============================================================
def test_appointment_crud(patient_id):
    print("\n" + "="*60)
    print("Section 2: Appointment CRUD")
    print("="*60)
    results = []

    data, err = api("POST", "/api/appointments", {
        "patient_id": patient_id, "month": 7, "day": 15,
        "time_slot": "9:00-10:00", "project": "治疗", "amount": 300
    })
    if err or not data or not data.get("id"):
        log_fail("Create appointment", err or "no id")
        return results
    aid1 = data["id"]
    log_pass("Create appointment")

    data, err = api("GET", "/api/appointments")
    if err:
        log_fail("List appointments", err)
    elif find_in_list(data, "id", aid1):
        log_pass("List appointments (includes new)")
    else:
        log_fail("List appointments", "new apt not found")

    data, err = api("PUT", f"/api/appointments/{aid1}", {"time_slot": "10:00-11:00", "amount": 350})
    if err:
        log_fail("Update appointment", err)
    elif data and data["time_slot"] == "10:00-11:00" and data["amount"] == 350:
        log_pass("Update appointment")
    else:
        log_fail("Update appointment", f"got {data}")

    data, err = api("GET", "/api/appointments")
    apt = find_in_list(data, "id", aid1)
    if apt and apt["time_slot"] == "10:00-11:00":
        log_pass("Verify update persisted in list")
    else:
        log_fail("Verify update persisted", f"got {apt}")

    results.append(aid1)
    return results

# ============================================================
# Section 3: Consumption CRUD
# ============================================================
def test_consumption_crud(patient_id):
    print("\n" + "="*60)
    print("Section 3: Consumption CRUD")
    print("="*60)
    results = []

    data, err = api("POST", "/api/consumption", {
        "patient_id": patient_id, "month": 7, "day": 16,
        "project": "治疗", "amount": 200, "time_slot": "", "sync_to_apt": 0
    })
    if err or not data or not data.get("id"):
        log_fail("Create consumption (no time_slot)", err or "no id")
        return results
    cid = data["id"]
    log_pass("Create consumption without time_slot")

    data, err = api("GET", "/api/consumption")
    if err:
        log_fail("List consumptions", err)
    elif find_in_list(data, "id", cid):
        log_pass("List consumptions (includes new)")
    else:
        log_fail("List consumptions", "new con not found")

    data, err = api("PUT", f"/api/consumption/{cid}", {"time_slot": "14:00-15:00", "sync_to_apt": 1})
    if err:
        log_fail("Update consumption with time_slot + sync", err)
    elif data and data["time_slot"] == "14:00-15:00" and data["sync_to_apt"] == 1:
        log_pass("Update consumption - add time_slot + sync_to_apt")
    else:
        log_fail("Update consumption", f"got {data}")

    link_data, err = api("GET", f"/api/consumption/{cid}/links")
    if err:
        log_fail("Check consumption links", err)
    elif link_data and link_data.get("appointment_id"):
        log_pass("Consumption linked to appointment after sync")
    else:
        log_fail("Consumption linked", f"no link found: {link_data}")

    # Verify via list endpoint
    data, err = api("GET", "/api/consumption")
    con = find_in_list(data, "id", cid)
    if con and con["time_slot"] == "14:00-15:00":
        log_pass("Verify consumption update in list")
    else:
        log_fail("Verify consumption update in list", f"got {con}")

    results.append(cid)
    return results

# ============================================================
# Section 4: Mixed Scenarios
# ============================================================
def test_mixed_scenarios(patient_id):
    print("\n" + "="*60)
    print("Section 4: Mixed Scenarios")
    print("="*60)

    # 4a: Appointment WITH sync_to_con -> auto-create consumption
    print("\n[4a] Appointment -> Consumption sync")
    data, err = api("POST", "/api/appointments", {
        "patient_id": patient_id, "month": 8, "day": 1,
        "time_slot": "9:00-10:00", "project": "上门治疗", "amount": 500,
        "sync_to_con": True
    })
    if err or not data or not data.get("id"):
        log_fail("Create appointment with sync_to_con", err or "no id")
        return
    aid_sync = data["id"]
    linked_con_id = data.get("linked_con_id")
    if linked_con_id:
        log_pass(f"Appointment sync_to_con created linked consumption (id={linked_con_id})")
    else:
        log_fail("Appointment sync_to_con", "no linked_con_id in response")
        return

    link_data, err = api("GET", f"/api/consumption/{linked_con_id}/links")
    if err:
        log_fail("Verify link via consumption", err)
    elif link_data.get("appointment_id") == aid_sync:
        log_pass("Link verified: consumption <-> appointment")
    else:
        log_fail("Link verified", f"expected apt {aid_sync}, got {link_data}")

    # 4b: Update linked appointment -> linked consumption should sync
    print("\n[4b] Update appointment -> consumption sync")
    data, err = api("PUT", f"/api/appointments/{aid_sync}", {"time_slot": "10:00-11:00", "amount": 550})
    if err:
        log_fail("Update appointment (with link)", err)
    elif data["time_slot"] == "10:00-11:00":
        log_pass("Update appointment (with link)")
    else:
        log_fail("Update appointment (with link)", f"got {data}")

    cons_list, _ = api("GET", "/api/consumption")
    con = find_in_list(cons_list, "id", linked_con_id)
    if con and con["time_slot"] == "10:00-11:00" and con["amount"] == 550:
        log_pass("Linked consumption auto-updated after appointment change")
    else:
        log_fail("Linked consumption auto-updated", f"got {con}")

    # 4c: Delete consumption with link -> appointment cascade deletes
    print("\n[4c] Delete consumption -> appointment cascade delete")
    apts_before, _ = api("GET", "/api/appointments")
    if find_in_list(apts_before, "id", aid_sync):
        log_pass("Appointment exists before consumption delete")

    log_history("delete", "consumption", linked_con_id,
                {"id": linked_con_id, "patient_id": patient_id},
                f"删除耗卡 {linked_con_id}")
    data, err = api("DELETE", f"/api/consumption/{linked_con_id}")
    if err or not data.get("success"):
        log_fail("Delete consumption (with link)", err or "no success")
    else:
        log_pass("Delete consumption (with link)")

    apts_after, _ = api("GET", "/api/appointments")
    if not find_in_list(apts_after, "id", aid_sync):
        log_pass("Linked appointment cascade deleted")
    else:
        log_fail("Linked appointment cascade deleted", "still exists")

    link_check, _ = api("GET", f"/api/consumption/{linked_con_id}/links")
    if not link_check or not link_check.get("appointment_id"):
        log_pass("Appointment_consumption_link cleaned up")
    else:
        log_fail("Appointment_consumption_link cleaned up", "still exists")

    # 4d: Consumption without time_slot -> add time_slot + sync -> appointment created
    print("\n[4d] Consumption (no time_slot) -> add time_slot -> appointment created")
    data, err = api("POST", "/api/consumption", {
        "patient_id": patient_id, "month": 8, "day": 5,
        "project": "评估", "amount": 100, "time_slot": "", "sync_to_apt": 0
    })
    if err or not data.get("id"):
        log_fail("Create consumption (no time_slot)", err or "no id")
        return
    cid_sync = data["id"]
    log_pass("Create consumption without time_slot")

    data, err = api("PUT", f"/api/consumption/{cid_sync}", {"time_slot": "15:00-16:00", "sync_to_apt": 1})
    if err:
        log_fail("Add time_slot to consumption with sync_to_apt", err)
    else:
        log_pass("Add time_slot to consumption with sync_to_apt")

    link_data, err = api("GET", f"/api/consumption/{cid_sync}/links")
    if err:
        log_fail("Verify appointment auto-created", err)
    elif link_data and link_data.get("appointment_id"):
        log_pass(f"New appointment auto-created and linked (id={link_data['appointment_id']})")
    else:
        log_fail("New appointment auto-created", f"no link: {link_data}")

    # 4e: Delete patient -> cascade all appointments + consumptions
    print("\n[4e] Delete patient -> cascade all related records")
    uid = ts()
    data, err = api("POST", "/api/patients", {"name": f"cascade_pat_{uid}", "age": "50"})
    if err or not data.get("id"):
        log_fail("Create cascade test patient", err or "no id")
        return
    c_pid = data["id"]
    log_pass("Create cascade test patient")

    data, _ = api("POST", "/api/appointments", {
        "patient_id": c_pid, "month": 9, "day": 10,
        "time_slot": "9:00-10:00", "project": "治疗", "amount": 400
    })
    c_aid = data.get("id")
    data, _ = api("POST", "/api/consumption", {
        "patient_id": c_pid, "month": 9, "day": 10,
        "project": "治疗", "amount": 400, "time_slot": "", "sync_to_apt": 0
    })
    c_cid = data.get("id")
    if not c_aid or not c_cid:
        log_fail("Create apt+con for cascade", "missing ids")
        return
    log_pass("Create appointment + consumption for cascade test")

    log_history("delete", "patient", c_pid,
                {"name": f"cascade_pat_{uid}", "appointments": [{"id": c_aid}], "consumptions": [{"id": c_cid}]},
                f"删除患者 {c_pid}")
    data, err = api("DELETE", f"/api/patients/{c_pid}")
    if err or not data.get("success"):
        log_fail("Delete patient (cascade)", err or "no success")
    else:
        log_pass("Delete patient")

    apts_check, _ = api("GET", "/api/appointments")
    if not find_in_list(apts_check, "id", c_aid):
        log_pass("Cascaded appointment deleted")
    else:
        log_fail("Cascaded appointment deleted", "still exists")

    cons_check, _ = api("GET", "/api/consumption")
    if not find_in_list(cons_check, "id", c_cid):
        log_pass("Cascaded consumption deleted")
    else:
        log_fail("Cascaded consumption deleted", "still exists")

# ============================================================
# Section 5: Rollback Mixed Scenarios
# ============================================================
def test_rollback():
    print("\n" + "="*60)
    print("Section 5: Rollback - Mixed Scenario Restore")
    print("="*60)

    uid = ts()
    data, err = api("POST", "/api/patients", {"name": f"rollback_pat_{uid}", "age": "45"})
    if err or not data.get("id"):
        log_fail("[Setup] Create rollback patient", err or "no id")
        return
    rb_pid = data["id"]
    log_pass(f"[Setup] Create rollback patient id={rb_pid}")

    data, _ = api("POST", "/api/appointments", {
        "patient_id": rb_pid, "month": 10, "day": 5,
        "time_slot": "9:00-10:00", "project": "评估+治疗", "amount": 400,
        "sync_to_con": True
    })
    rb_aid = data.get("id")
    if not rb_aid:
        log_fail("[Setup] Create rollback appointment", "no id")
        return
    log_pass(f"[Setup] Create rollback appointment id={rb_aid}")

    linked_cid = data.get("linked_con_id")
    if linked_cid:
        log_pass(f"[Setup] Linked consumption auto-created id={linked_cid}")
    else:
        log_fail("[Setup] Linked consumption", "not auto-created")
        return

    # Log history via API (as frontend would - spread all consumption fields + linkedAppointment)
    log_history("delete", "consumption", linked_cid,
                {"id": linked_cid, "patient_id": rb_pid, "month": 10, "day": 5,
                 "project": "评估+治疗", "amount": 400, "time_slot": "9:00-10:00",
                 "sync_to_apt": 1,
                 "linkedAppointment": {"id": rb_aid, "patient_id": rb_pid,
                                       "year": 2026, "month": 10, "day": 5,
                                       "time_slot": "9:00-10:00",
                                       "project": "评估+治疗", "amount": 400,
                                       "remark": "评估+治疗\n400",
                                       "patient_name": f"rollback_pat_{uid}"}},
                f"删除耗卡 {linked_cid} 及关联预约")

    data, err = api("DELETE", f"/api/consumption/{linked_cid}")
    if err or not data.get("success"):
        log_fail("[Setup] Delete consumption", err or "no success")
        return
    log_pass("[Setup] Delete consumption (link chain broken)")

    # Find history entry for our specific consumption delete
    history, err = api("GET", "/api/history")
    if err:
        log_fail("Get history list", err)
        return

    restore_entry = None
    for h in history:
        if h.get("target_type") == "consumption" and h.get("target_id") == linked_cid and h.get("action_type") == "delete":
            restore_entry = h
            break
    if not restore_entry:
        log_fail("Find delete history entry", f"no entry for consumption id={linked_cid}")
        return
    restore_id = restore_entry["id"]
    log_pass(f"Found history delete entry id={restore_id} (consumption {linked_cid})")

    data, err = api("POST", f"/api/history/{restore_id}/restore")
    if err:
        log_fail("Restore history (delete -> undo)", err)
    elif data.get("success") or data.get("reversed") is not None:
        log_pass(f"History restore succeeded (reversed {data.get('reversed', 0)} entries)")
    else:
        log_fail("History restore", f"unexpected: {data}")

    link_check, _ = api("GET", f"/api/consumption/{linked_cid}/links")
    if link_check and link_check.get("appointment_id"):
        log_pass("Consumption and linked appointment restored correctly (original id)")
    else:
        # After restore, IDs may change (SQLite AUTOINCREMENT).
        # Verify by checking rollback patient has a consumption with time_slot + linked apt.
        cons_list, _ = api("GET", "/api/consumption")
        con = find_in_list(cons_list, "patient_id", rb_pid)
        if con and con.get("time_slot") and con.get("sync_to_apt") == 1:
            link2, _ = api("GET", f"/api/consumption/{con['id']}/links")
            if link2 and link2.get("appointment_id"):
                log_pass("Consumption and linked appointment restored (new id={})".format(con['id']))
            else:
                log_fail("Restored consumption has no link", f"con={con}")
        else:
            log_fail("Restored consumption not found", f"patient_id={rb_pid}")

# ============================================================
# Section 7: Issue 1 - Consumption clear time_slot -> appointment removed
# ============================================================
def test_issue1_clear_timeslot():
    print("\n" + "="*60)
    print("Section 7: Consumption clear time_slot -> appointment removed")
    print("="*60)

    uid = ts()
    data, err = api("POST", "/api/patients", {"name": f"clear_ts_pat_{uid}", "age": "40"})
    if err or not data.get("id"):
        log_fail("[Setup] Create patient", err or "no id")
        return
    pid = data["id"]
    log_pass(f"[Setup] Create patient id={pid}")

    data, err = api("POST", "/api/consumption", {
        "patient_id": pid, "month": 8, "day": 15,
        "project": "治疗", "amount": 300, "time_slot": "9:00-10:00"
    })
    if err or not data.get("id"):
        log_fail("[Setup] Create consumption with time_slot", err or "no id")
        return
    cid = data["id"]
    log_pass(f"[Setup] Create consumption id={cid} with time_slot")

    # Wait for sync (backend auto-syncs)
    link_data, _ = api("GET", f"/api/consumption/{cid}/links")
    if link_data and link_data.get("appointment_id"):
        log_pass(f"Appointment auto-created and linked (id={link_data['appointment_id']})")
    else:
        log_fail("Appointment auto-created", "no link found")
        return
    old_aid = link_data["appointment_id"]

    # Now clear the time_slot
    data, err = api("PUT", f"/api/consumption/{cid}", {"time_slot": ""})
    if err:
        log_fail("Clear time_slot on consumption", err)
    elif data and data["time_slot"] == "" and data["sync_to_apt"] == 0:
        log_pass("Clear time_slot - consumption updated (sync_to_apt=0)")
    else:
        log_fail("Clear time_slot", f"got {data}")

    link_after, _ = api("GET", f"/api/consumption/{cid}/links")
    if not link_after or not link_after.get("appointment_id"):
        log_pass("Linked appointment deleted after clearing time_slot")
    else:
        log_fail("Linked appointment still exists", f"link: {link_after}")

    apts, _ = api("GET", "/api/appointments")
    if not find_in_list(apts, "id", old_aid):
        log_pass("Appointment record removed")
    else:
        log_fail("Appointment record still exists")

    # Re-add time_slot -> appointment should be recreated
    data, err = api("PUT", f"/api/consumption/{cid}", {"time_slot": "14:00-15:00"})
    if err:
        log_fail("Re-add time_slot", err)
    else:
        log_pass("Re-add time_slot to consumption")

    link_again, _ = api("GET", f"/api/consumption/{cid}/links")
    if link_again and link_again.get("appointment_id"):
        log_pass(f"Appointment recreated after re-adding time_slot (id={link_again['appointment_id']})")
    else:
        log_fail("Appointment recreated", "no link found")


# ============================================================
# Section 8: Multi-step rollback
# ============================================================
def test_multi_step_rollback():
    print("\n" + "="*60)
    print("Section 8: Multi-step rollback")
    print("="*60)

    uid = ts()
    # Create patient
    data, err = api("POST", "/api/patients", {"name": f"multi_pat_{uid}", "age": "35"})
    if err or not data.get("id"):
        log_fail("[Setup] Create patient", err or "no id")
        return
    pid = data["id"]
    log_history("add", "patient", pid, data, f"新增患者 {pid}")
    log_pass(f"[Setup] Create patient id={pid}")

    # Step 1: Create appointment
    data, err = api("POST", "/api/appointments", {
        "patient_id": pid, "month": 7, "day": 10,
        "time_slot": "9:00-10:00", "project": "治疗", "amount": 300
    })
    if err or not data.get("id"):
        log_fail("[Step1] Create appointment", err or "no id")
        return
    aid1 = data["id"]
    log_history("add", "appointment", aid1, data, f"新增预约 {aid1}")
    log_pass(f"[Step1] Create appointment id={aid1}")

    # Step 2: Update appointment
    data, err = api("PUT", f"/api/appointments/{aid1}", {"time_slot": "10:00-11:00", "amount": 350})
    if err:
        log_fail("[Step2] Update appointment", err)
        return
    log_history("update", "appointment", aid1,
                {"old": {"time_slot": "9:00-10:00", "amount": 300, "project": "治疗", "remark": "治疗\n300",
                         "month": 7, "day": 10, "year": 2026, "patient_id": pid},
                 "new": {"time_slot": "10:00-11:00", "amount": 350, "project": "治疗", "remark": "治疗\n350",
                         "month": 7, "day": 10, "year": 2026, "patient_id": pid}},
                f"修改预约 {aid1}")
    log_pass("[Step2] Update appointment (9:00→10:00, 300→350)")

    # Step 3: Delete appointment
    data, err = api("DELETE", f"/api/appointments/{aid1}")
    if err or not data.get("success"):
        log_fail("[Step3] Delete appointment", err or "no success")
        return
    log_history("delete", "appointment", aid1,
                {"id": aid1, "patient_id": pid, "month": 7, "day": 10,
                 "time_slot": "10:00-11:00", "project": "治疗", "amount": 350,
                 "remark": "治疗\n350", "year": 2026},
                f"删除预约 {aid1}")
    log_pass("[Step3] Delete appointment")

    # Now rollback to Step2 state (undo the delete)
    history, _ = api("GET", "/api/history")
    target = None
    for h in history:
        if h.get("action_type") == "delete" and h.get("target_type") == "appointment" and h.get("target_id") == aid1:
            target = h
            break
    if not target:
        log_fail("Find delete history entry for rollback", f"aid={aid1}")
        return
    rid = target["id"]
    log_pass(f"Rollback to history id={rid} (undo delete)")

    data, err = api("POST", f"/api/history/{rid}/restore")
    if err:
        log_fail("Rollback", err)
    elif data.get("success"):
        log_pass(f"Rollback succeeded (reversed {data.get('reversed', 0)} entries)")
    else:
        log_fail("Rollback", f"unexpected: {data}")

    apts, _ = api("GET", "/api/appointments")
    found = find_in_list(apts, "id", aid1) or find_in_list(apts, "patient_id", pid)
    if found:
        log_pass(f"Appointment restored after rollback (id={found['id']}, time_slot={found['time_slot']})")
    else:
        log_fail("Appointment restored", "not found")

    # Now test rollback to Step1 state (undo update + delete)
    history, _ = api("GET", "/api/history")
    target = None
    for h in history:
        if h.get("action_type") == "add" and h.get("target_type") == "appointment" and h.get("target_id") == aid1:
            target = h
            break
    if not target:
        log_fail("Find add history entry for 2nd rollback", f"aid={aid1}")
        return
    rid2 = target["id"]
    log_pass(f"Rollback to history id={rid2} (undo update+delete, revert to add)")

    data, err = api("POST", f"/api/history/{rid2}/restore")
    if err:
        log_fail("2nd rollback", err)
    elif data.get("success"):
        log_pass(f"2nd rollback succeeded (reversed {data.get('reversed', 0)} entries)")
    else:
        log_fail("2nd rollback", f"unexpected: {data}")

    apts, _ = api("GET", "/api/appointments")
    if not find_in_list(apts, "id", aid1):
        log_pass(f"Appointment id={aid1} deleted (rolled back to before creation)")
    else:
        log_fail(f"Appointment id={aid1} still exists after rollback to add state")

    # ==== Test: consumption with sync → update → delete → rollback to mid state ====
    print("\n[8b] Consumption + sync + update → rollback to middle state")
    data, err = api("POST", "/api/appointments", {
        "patient_id": pid, "month": 9, "day": 1,
        "time_slot": "9:00-10:00", "project": "上门治疗", "amount": 500,
        "sync_to_con": True
    })
    if err or not data.get("id"):
        log_fail("[Setup] Create apt with sync_to_con", err or "no id")
        return
    aid2 = data["id"]
    cid2 = data.get("linked_con_id")
    log_history("add", "appointment", aid2, data, f"新增预约 {aid2} (同步耗卡)")
    log_pass(f"[Setup] Apt id={aid2} + linked con id={cid2}")

    # Delete consumption (cascades to appointment)
    log_history("delete", "consumption", cid2,
                {"id": cid2, "patient_id": pid, "month": 9, "day": 1,
                 "project": "上门治疗", "amount": 500, "time_slot": "9:00-10:00",
                 "sync_to_apt": 1,
                 "linkedAppointment": {"id": aid2, "patient_id": pid, "year": 2026,
                                       "month": 9, "day": 1, "time_slot": "9:00-10:00",
                                       "project": "上门治疗", "amount": 500,
                                       "remark": "上门治疗\n500", "patient_name": f"multi_pat_{uid}"}},
                f"删除耗卡 {cid2}")
    data, err = api("DELETE", f"/api/consumption/{cid2}")
    if err or not data.get("success"):
        log_fail("[Setup] Delete consumption", err or "no success")
        return
    log_pass("[Setup] Consumption deleted (appointment cascaded)")

    # Rollback to before consumption delete (restore consumption + appointment)
    history, _ = api("GET", "/api/history")
    target = None
    for h in history:
        if h.get("action_type") == "delete" and h.get("target_type") == "consumption" and h.get("target_id") == cid2:
            target = h
            break
    if not target:
        log_fail("Find consumption delete history", f"cid={cid2}")
        return
    rid3 = target["id"]

    data, err = api("POST", f"/api/history/{rid3}/restore")
    if err:
        log_fail("Rollback consumption delete", err)
    elif data.get("success"):
        log_pass(f"Rollback consumption delete succeeded ({data.get('reversed', 0)} entries)")
    else:
        log_fail("Rollback consumption delete", f"unexpected: {data}")

    cons_list, _ = api("GET", "/api/consumption")
    con = find_in_list(cons_list, "patient_id", pid)
    if con:
        link_check, _ = api("GET", f"/api/consumption/{con['id']}/links")
        if link_check and link_check.get("appointment_id"):
            log_pass(f"Consumption and linked appointment restored (con_id={con['id']})")
        else:
            log_fail("Consumption restored but no linked appointment", f"link={link_check}")
    else:
        log_fail("Consumption not restored", f"patient_id={pid}")


# ============================================================
# Section 6: Edge Cases
# ============================================================
def test_edge_cases():
    print("\n" + "="*60)
    print("Section 6: Edge Cases")
    print("="*60)

    data, err = api("DELETE", "/api/appointments/99999")
    if err:
        log_fail("Delete non-existent appointment", err)
    elif data.get("success"):
        log_pass("Delete non-existent appointment (idempotent)")
    else:
        log_fail("Delete non-existent appointment", f"got {data}")

    data, err = api("DELETE", "/api/consumption/99999")
    if err:
        log_fail("Delete non-existent consumption", err)
    elif data.get("success"):
        log_pass("Delete non-existent consumption (idempotent)")
    else:
        log_fail("Delete non-existent consumption", f"got {data}")

    data, err = api("DELETE", "/api/patients/99999")
    if err:
        log_fail("Delete non-existent patient", err)
    elif data.get("success"):
        log_pass("Delete non-existent patient (idempotent)")
    else:
        log_fail("Delete non-existent patient", f"got {data}")


# ============================================================
# Run all tests
# ============================================================
if __name__ == "__main__":
    print("="*60)
    print("Full CRUD + Mixed Scenarios + Rollback Test Suite")
    print("="*60)

    pid = test_patient_crud()
    test_appointment_crud(pid)
    test_consumption_crud(pid)
    test_mixed_scenarios(pid)
    test_rollback()
    test_issue1_clear_timeslot()
    test_multi_step_rollback()
    test_edge_cases()

    print("\n" + "="*60)
    print("Results: {} passed, {} failed".format(passed, failed))
    print("="*60)
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
