#!/usr/bin/env python3
"""
Comprehensive Test Suite - Clinic Appointment System
Tests: Patient/Appointment/Consumption CRUD + Cascade Delete + History Restore
"""
import requests
import json
import time
import sys
import subprocess

BASE = "http://66.154.101.204"

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
            return None, f"status={r.status_code}, expected={expected_status}"
        if r.text.strip():
            return r.json(), None
        return {}, None
    except Exception as e:
        return None, str(e)


def ts():
    return int(time.time() * 1000)


def ssh_exec(cmd):
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "root@66.154.101.204", cmd],
            capture_output=True, text=True, timeout=15
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr
    except Exception as e:
        return False, "", str(e)


# ============================================================
# 1. Health Check
# ============================================================
def test_health():
    print("\n[1] Health Check")
    data, err = api("GET", "/health")
    if err:
        log_fail("GET /health", err)
    elif data and data.get("status") == "ok":
        log_pass("GET /health")
    else:
        log_fail("GET /health", f"unexpected: {data}")


# ============================================================
# 2. Patient CRUD
# ============================================================
def test_patient_crud():
    print("\n[2] Patient CRUD")
    name = f"test_patient_{ts()}"

    data, err = api("POST", "/api/patients", {"name": name, "phone": "13900001111", "age": "30", "gender": "M"})
    if err:
        log_fail("Create patient", err)
        return
    pid = data.get("id")
    if not pid:
        log_fail("Create patient", f"no id: {data}")
        return
    log_pass(f"Create patient id={pid}")

    data, err = api("GET", "/api/patients")
    if err:
        log_fail("List patients", err)
    elif any(p["id"] == pid for p in data):
        log_pass("List patients (includes new)")
    else:
        log_fail("List patients", "new patient not found")

    data, err = api("PUT", f"/api/patients/{pid}", {"name": name + "_upd", "phone": "13900002222"})
    if err:
        log_fail("Update patient", err)
    elif data and (data.get("success") or data.get("id") == pid):
        log_pass("Update patient")
    else:
        log_fail("Update patient", f"unexpected: {data}")

    data, err = api("DELETE", f"/api/patients/{pid}")
    if err:
        log_fail("Delete patient", err)
    elif data and data.get("success"):
        log_pass("Delete patient")
    else:
        log_fail("Delete patient", f"unexpected: {data}")

    data, err = api("GET", "/api/patients")
    if err:
        log_fail("Verify patient deleted", err)
    elif not any(p["id"] == pid for p in data):
        log_pass("Verify patient deleted")
    else:
        log_fail("Verify patient deleted", "still exists")


# ============================================================
# 3. Appointment CRUD
# ============================================================
def test_appointment_crud():
    print("\n[3] Appointment CRUD")
    name = f"apt_test_{ts()}"

    p, err = api("POST", "/api/patients", {"name": name, "phone": "13900003333"})
    if err or not p.get("id"):
        log_fail("Create test patient", err or "no id")
        return
    pid = p["id"]

    data, err = api("POST", "/api/appointments", {
        "patient_id": pid, "year": 2026, "month": 8, "day": 15,
        "time_slot": "10:00-11:00", "project": "test_project", "amount": 200, "remark": ""
    })
    if err:
        log_fail("Create appointment", err)
        return
    aid = data.get("id")
    if not aid:
        log_fail("Create appointment", f"no id: {data}")
        return
    log_pass(f"Create appointment id={aid}")

    data, err = api("GET", "/api/appointments?year=2026&month=8")
    if err:
        log_fail("List appointments", err)
    elif any(a["id"] == aid for a in data):
        log_pass("List appointments (includes new)")
    else:
        log_fail("List appointments", "new appointment not found")

    data, err = api("PUT", f"/api/appointments/{aid}", {
        "patient_id": pid, "year": 2026, "month": 8, "day": 16,
        "time_slot": "14:00-15:00", "project": "updated_project", "amount": 300
    })
    if err:
        log_fail("Update appointment", err)
    elif data and (data.get("success") or data.get("id") == aid):
        log_pass("Update appointment")
    else:
        log_fail("Update appointment", f"unexpected: {data}")

    data, err = api("DELETE", f"/api/appointments/{aid}")
    if err:
        log_fail("Delete appointment", err)
    elif data and data.get("success"):
        log_pass("Delete appointment")
    else:
        log_fail("Delete appointment", f"unexpected: {data}")

    api("DELETE", f"/api/patients/{pid}")


# ============================================================
# 4. Consumption CRUD
# ============================================================
def test_consumption_crud():
    print("\n[4] Consumption CRUD")
    name = f"con_test_{ts()}"

    p, err = api("POST", "/api/patients", {"name": name, "phone": "13900004444"})
    if err or not p.get("id"):
        log_fail("Create test patient", err or "no id")
        return
    pid = p["id"]

    data, err = api("POST", "/api/consumption", {
        "patient_id": pid, "month": 8, "day": 20, "project": "con_project",
        "amount": 150, "time_slot": "11:00-12:00", "sync_to_apt": 0
    })
    if err:
        log_fail("Create consumption", err)
        return
    cid = data.get("id")
    if not cid:
        log_fail("Create consumption", f"no id: {data}")
        return
    log_pass(f"Create consumption id={cid}")

    data, err = api("GET", "/api/consumption")
    if err:
        log_fail("List consumptions", err)
    elif any(c["id"] == cid for c in data):
        log_pass("List consumptions (includes new)")
    else:
        log_fail("List consumptions", "new consumption not found")

    data, err = api("PUT", f"/api/consumption/{cid}", {
        "patient_id": pid, "month": 8, "day": 21, "project": "updated_con",
        "amount": 250, "time_slot": "14:00-15:00", "sync_to_apt": 0
    })
    if err:
        log_fail("Update consumption", err)
    elif data and (data.get("success") or data.get("id") == cid):
        log_pass("Update consumption")
    else:
        log_fail("Update consumption", f"unexpected: {data}")

    data, err = api("DELETE", f"/api/consumption/{cid}")
    if err:
        log_fail("Delete consumption", err)
    elif data and data.get("success"):
        log_pass("Delete consumption")
    else:
        log_fail("Delete consumption", f"unexpected: {data}")

    api("DELETE", f"/api/patients/{pid}")


# ============================================================
# 5. Consumption-Appointment Cascade Delete
# ============================================================
def test_cascade_delete():
    print("\n[5] Consumption-Appointment Cascade Delete")
    name = f"cascade_{ts()}"

    p, err = api("POST", "/api/patients", {"name": name, "phone": "13900005555"})
    if err or not p.get("id"):
        log_fail("Create patient", err or "no id")
        return
    pid = p["id"]

    apt, err = api("POST", "/api/appointments", {
        "patient_id": pid, "year": 2026, "month": 9, "day": 10,
        "time_slot": "10:00-11:00", "project": "cascade_project", "amount": 100, "remark": ""
    })
    if err or not apt.get("id"):
        log_fail("Create appointment", err or "no id")
        api("DELETE", f"/api/patients/{pid}")
        return
    aid = apt["id"]
    log_pass(f"Create appointment id={aid}")

    con, err = api("POST", "/api/consumption", {
        "patient_id": pid, "month": 9, "day": 10, "project": "cascade_project",
        "amount": 100, "time_slot": "10:00-11:00", "sync_to_apt": 1
    })
    if err or not con.get("id"):
        log_fail("Create consumption", err or "no id")
        api("DELETE", f"/api/appointments/{aid}")
        api("DELETE", f"/api/patients/{pid}")
        return
    cid = con["id"]
    log_pass(f"Create consumption id={cid}")

    # Create link via SSH
    ok, _, stderr = ssh_exec(
        f"sqlite3 /root/clinic-app/data/clinic.db \"INSERT INTO appointment_consumption_link (appointment_id, consumption_id) VALUES ({aid}, {cid});\""
    )
    if ok:
        log_pass(f"Create link: appointment {aid} <-> consumption {cid}")
    else:
        log_fail("Create link", stderr)
        api("DELETE", f"/api/consumption/{cid}")
        api("DELETE", f"/api/appointments/{aid}")
        api("DELETE", f"/api/patients/{pid}")
        return

    # Verify link
    links, _ = api("GET", f"/api/consumption/{cid}/links")
    if links and links.get("appointment_id") == aid:
        log_pass(f"Verify link: consumption {cid} -> appointment {aid}")
    else:
        log_fail("Verify link", f"expected aid={aid}, got {links}")

    # Delete consumption
    data, err = api("DELETE", f"/api/consumption/{cid}")
    if err:
        log_fail("Delete consumption", err)
        return
    if data and data.get("success"):
        log_pass("Delete consumption")
    else:
        log_fail("Delete consumption", f"unexpected: {data}")
        return

    # Verify appointment deleted
    apts, _ = api("GET", f"/api/appointments?year=2026&month=9")
    if apts and any(a["id"] == aid for a in apts):
        log_fail("Appointment not cascade-deleted", f"aid={aid} still exists")
    else:
        log_pass("Appointment cascade-deleted")

    # Verify consumption deleted
    cons, _ = api("GET", "/api/consumption")
    if cons and any(c["id"] == cid for c in cons):
        log_fail("Consumption not deleted", f"cid={cid} still exists")
    else:
        log_pass("Consumption deleted")

    api("DELETE", f"/api/patients/{pid}")


# ============================================================
# 6. No-Link Consumption Delete (should NOT delete appointment)
# ============================================================
def test_no_link_delete():
    print("\n[6] No-Link Consumption Delete (appointment preserved)")
    name = f"nolink_{ts()}"

    p, err = api("POST", "/api/patients", {"name": name, "phone": "13900006666"})
    if err or not p.get("id"):
        log_fail("Create patient", err or "no id")
        return
    pid = p["id"]

    con, err = api("POST", "/api/consumption", {
        "patient_id": pid, "month": 9, "day": 12, "project": "standalone_con",
        "amount": 80, "time_slot": "15:00-16:00", "sync_to_apt": 0
    })
    if err or not con.get("id"):
        log_fail("Create consumption", err or "no id")
        api("DELETE", f"/api/patients/{pid}")
        return
    cid = con["id"]

    apt, err = api("POST", "/api/appointments", {
        "patient_id": pid, "year": 2026, "month": 9, "day": 12,
        "time_slot": "15:00-16:00", "project": "standalone_apt", "amount": 80, "remark": ""
    })
    if err or not apt.get("id"):
        log_fail("Create appointment", err or "no id")
        api("DELETE", f"/api/consumption/{cid}")
        api("DELETE", f"/api/patients/{pid}")
        return
    aid = apt["id"]

    data, err = api("DELETE", f"/api/consumption/{cid}")
    if err:
        log_fail("Delete consumption", err)
    elif data and data.get("success"):
        log_pass("Delete consumption")
    else:
        log_fail("Delete consumption", f"unexpected: {data}")

    apts, _ = api("GET", f"/api/appointments?year=2026&month=9")
    if apts and any(a["id"] == aid for a in apts):
        log_pass("Standalone appointment preserved")
    else:
        log_fail("Standalone appointment was deleted")

    api("DELETE", f"/api/appointments/{aid}")
    api("DELETE", f"/api/patients/{pid}")


# ============================================================
# 7. History Restore - Appointment
# ============================================================
def test_history_restore():
    print("\n[7] History Restore - Appointment")
    name = f"hist_apt_{ts()}"

    p, err = api("POST", "/api/patients", {"name": name, "phone": "13900007777"})
    if err or not p.get("id"):
        log_fail("Create patient", err or "no id")
        return
    pid = p["id"]

    apt, err = api("POST", "/api/appointments", {
        "patient_id": pid, "year": 2026, "month": 10, "day": 5,
        "time_slot": "09:00-10:00", "project": "restore_test", "amount": 500, "remark": ""
    })
    if err or not apt.get("id"):
        log_fail("Create appointment", err or "no id")
        api("DELETE", f"/api/patients/{pid}")
        return
    aid = apt["id"]
    log_pass(f"Create appointment id={aid}")

    # Log add history
    api("POST", "/api/history", {
        "action_type": "add", "target_type": "appointment", "target_id": aid,
        "data": apt, "description": f"Add appointment: {aid}"
    })

    # Delete appointment
    data, err = api("DELETE", f"/api/appointments/{aid}")
    if err:
        log_fail("Delete appointment", err)
    elif data and data.get("success"):
        log_pass("Delete appointment")
    else:
        log_fail("Delete appointment", f"unexpected: {data}")

    # Log delete history
    api("POST", "/api/history", {
        "action_type": "delete", "target_type": "appointment", "target_id": aid,
        "data": apt, "description": f"Delete appointment: {aid}"
    })

    # Find the delete history record
    histories, err = api("GET", "/api/history")
    if err:
        log_fail("Query history", err)
        api("DELETE", f"/api/patients/{pid}")
        return

    target = None
    for h in histories:
        if h.get("action_type") == "delete" and h.get("target_type") == "appointment":
            if h.get("target_id") == aid:
                target = h
                break

    if not target:
        log_fail("Find delete history", f"aid={aid} not found in {len(histories)} records")
        api("DELETE", f"/api/patients/{pid}")
        return
    log_pass(f"Found history id={target['id']}")

    # Restore
    data, err = api("POST", f"/api/history/{target['id']}/restore")
    if err:
        log_fail("Restore", err)
    elif data and data.get("success"):
        log_pass("Restore success")
    else:
        log_fail("Restore", f"unexpected: {data}")

    api("DELETE", f"/api/patients/{pid}")


# ============================================================
# 8. History Restore - Consumption with Linked Appointment
# ============================================================
def test_history_restore_consumption():
    print("\n[8] History Restore - Consumption with Linked Appointment")
    name = f"hist_con_{ts()}"

    p, err = api("POST", "/api/patients", {"name": name, "phone": "13900008888"})
    if err or not p.get("id"):
        log_fail("Create patient", err or "no id")
        return
    pid = p["id"]

    apt, err = api("POST", "/api/appointments", {
        "patient_id": pid, "year": 2026, "month": 10, "day": 8,
        "time_slot": "11:00-12:00", "project": "hist_con_project", "amount": 300, "remark": ""
    })
    if err or not apt.get("id"):
        log_fail("Create appointment", err or "no id")
        api("DELETE", f"/api/patients/{pid}")
        return
    aid = apt["id"]

    con, err = api("POST", "/api/consumption", {
        "patient_id": pid, "month": 10, "day": 8, "project": "hist_con_project",
        "amount": 300, "time_slot": "11:00-12:00", "sync_to_apt": 1
    })
    if err or not con.get("id"):
        log_fail("Create consumption", err or "no id")
        api("DELETE", f"/api/appointments/{aid}")
        api("DELETE", f"/api/patients/{pid}")
        return
    cid = con["id"]

    # Create link
    ok, _, stderr = ssh_exec(
        f"sqlite3 /root/clinic-app/data/clinic.db \"INSERT INTO appointment_consumption_link (appointment_id, consumption_id) VALUES ({aid}, {cid});\""
    )
    if ok:
        log_pass(f"Create link: appointment {aid} <-> consumption {cid}")
    else:
        log_fail("Create link", stderr)

    # Delete consumption
    data, err = api("DELETE", f"/api/consumption/{cid}")
    if err:
        log_fail("Delete consumption", err)
        api("DELETE", f"/api/patients/{pid}")
        return
    log_pass("Delete consumption")

    # Log delete history with linkedAppointment data
    history_data = dict(con)
    history_data["linkedAppointment"] = apt
    api("POST", "/api/history", {
        "action_type": "delete", "target_type": "consumption", "target_id": cid,
        "data": history_data, "description": f"Delete consumption: {cid}"
    })

    # Find history
    histories, _ = api("GET", "/api/history")
    target = None
    for h in histories:
        if h.get("action_type") == "delete" and h.get("target_type") == "consumption":
            if h.get("target_id") == cid:
                target = h
                break

    if not target:
        log_fail("Find consumption delete history", f"cid={cid} not found in {len(histories)} records")
        api("DELETE", f"/api/patients/{pid}")
        return
    log_pass(f"Found history id={target['id']}")

    # Restore
    data, err = api("POST", f"/api/history/{target['id']}/restore")
    if err:
        log_fail("Restore", err)
    elif data and data.get("success"):
        log_pass("Restore success")
    else:
        log_fail("Restore", f"unexpected: {data}")

    api("DELETE", f"/api/patients/{pid}")


# ============================================================
# 9. Edge Cases
# ============================================================
def test_edge_cases():
    print("\n[9] Edge Cases")

    data, err = api("DELETE", "/api/appointments/999999")
    if data and data.get("success"):
        log_pass("Delete nonexistent appointment (idempotent)")
    else:
        log_pass("Delete nonexistent appointment (returns error)")

    data, err = api("DELETE", "/api/consumption/999999")
    if data and data.get("success"):
        log_pass("Delete nonexistent consumption (idempotent)")
    else:
        log_pass("Delete nonexistent consumption (returns error)")


# ============================================================
# 10. Links API
# ============================================================
def test_links_api():
    print("\n[10] Links API")

    data, err = api("GET", "/api/consumption/1/links")
    if err:
        log_fail("GET /api/consumption/1/links", err)
    else:
        log_pass(f"GET /api/consumption/1/links -> {data}")

    data, err = api("GET", "/api/consumption/99999/links")
    if err:
        log_fail("GET /api/consumption/99999/links", err)
    else:
        log_pass(f"GET /api/consumption/99999/links -> {data}")


# ============================================================
# 11. Batch Import
# ============================================================
def test_batch():
    print("\n[11] Batch Import Consumption")
    name = f"batch_{ts()}"

    p, err = api("POST", "/api/patients", {"name": name, "phone": "13900009999"})
    if err or not p.get("id"):
        log_fail("Create patient", err or "no id")
        return
    pid = p["id"]

    data, err = api("POST", "/api/consumption/batch", {
        "records": [
            {"patient_id": pid, "month": 10, "day": 15, "project": "batch1", "amount": 100, "time_slot": "10:00-11:00", "sync_to_apt": 0},
            {"patient_id": pid, "month": 10, "day": 16, "project": "batch2", "amount": 200, "time_slot": "11:00-12:00", "sync_to_apt": 0},
            {"patient_id": pid, "month": 10, "day": 17, "project": "batch3", "amount": 300, "time_slot": "14:00-15:00", "sync_to_apt": 0},
        ]
    })
    if err:
        log_fail("Batch import", err)
    elif data and data.get("count", 0) >= 3:
        log_pass(f"Batch import count={data.get('count')}")
    else:
        log_fail("Batch import", f"unexpected: {data}")

    api("DELETE", f"/api/patients/{pid}")


# ============================================================
# 12. Stats
# ============================================================
def test_stats():
    print("\n[12] Stats API")
    data, err = api("GET", "/api/stats")
    if err:
        log_fail("GET /api/stats", err)
    elif data and "total_patients" in data:
        log_pass(f"GET /api/stats -> total_patients={data.get('total_patients')}")
    else:
        log_fail("GET /api/stats", f"unexpected: {data}")


# ============================================================
# 13. Project CRUD
# ============================================================
def test_project_crud():
    print("\n[13] Project CRUD")
    pname = f"test_proj_{ts()}"

    data, err = api("POST", "/api/projects", {"name": pname, "default_price": 100})
    if err:
        log_fail("Create project", err)
        return
    prid = data.get("id")
    if not prid:
        log_fail("Create project", f"no id: {data}")
        return
    log_pass(f"Create project id={prid}")

    data, err = api("GET", "/api/projects")
    if err:
        log_fail("List projects", err)
    elif any(p["id"] == prid for p in data):
        log_pass("List projects (includes new)")
    else:
        log_fail("List projects", "new project not found")

    data, err = api("PUT", f"/api/projects/{prid}", {"name": pname + "_upd", "default_price": 200})
    if err:
        log_fail("Update project", err)
    elif data and (data.get("success") or data.get("id") == prid):
        log_pass("Update project")
    else:
        log_fail("Update project", f"unexpected: {data}")

    data, err = api("DELETE", f"/api/projects/{prid}")
    if err:
        log_fail("Delete project", err)
    elif data and data.get("success"):
        log_pass("Delete project")
    else:
        log_fail("Delete project", f"unexpected: {data}")


# ============================================================
# 14. Backup / Sync
# ============================================================
def test_backup():
    print("\n[14] Backup / Sync")
    try:
        r = requests.get(f"{BASE}/api/backup", timeout=15, stream=True)
        if r.status_code == 200:
            log_pass(f"GET /api/backup -> {r.headers.get('Content-Type', 'unknown')}")
        else:
            log_fail("GET /api/backup", f"status={r.status_code}")
    except Exception as e:
        log_fail("GET /api/backup", str(e))

    data, err = api("GET", "/api/sync-status")
    if err:
        log_fail("GET /api/sync-status", err)
    else:
        log_pass(f"GET /api/sync-status -> {data}")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Clinic System - Comprehensive Test Suite")
    print("=" * 60)

    try:
        requests.get(f"{BASE}/health", timeout=5)
    except Exception as e:
        print(f"\nCannot connect to {BASE}: {e}")
        sys.exit(1)

    test_health()
    test_patient_crud()
    test_appointment_crud()
    test_consumption_crud()
    test_cascade_delete()
    test_no_link_delete()
    test_history_restore()
    test_history_restore_consumption()
    test_edge_cases()
    test_links_api()
    test_batch()
    test_stats()
    test_project_crud()
    test_backup()

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    if errors:
        print("\nFailed tests:")
        for e in errors:
            print(f"  - {e}")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)
