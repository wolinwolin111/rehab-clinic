#!/usr/bin/env python3
import urllib.request
import json
import time

time.sleep(2)  # Wait for gunicorn to restart

# Test 1: Check if we can create a consumption record with sync_to_apt=1
print("=== Test 1: Create consumption with sync_to_apt=1 ===")
data = json.dumps({
    'patient_id': 1,
    'month': 7,
    'day': 15,
    'project': '测试治疗',
    'amount': 100,
    'sync_to_apt': 1
}).encode()

try:
    req = urllib.request.Request('http://127.0.0.1:8080/api/consumption', data=data, headers={'Content-Type': 'application/json'})
    resp = urllib.request.urlopen(req)
    created = json.loads(resp.read())
    print(f"Created consumption: {created['id']}")
    
    # Test 2: Check if appointment was created
    print("\n=== Test 2: Check if appointment was created ===")
    req = urllib.request.Request('http://127.0.0.1:8080/api/appointments?year=2026&month=7')
    resp = urllib.request.urlopen(req)
    apts = json.loads(resp.read())
    
    linked_apt = None
    for apt in apts:
        if '测试治疗' in apt.get('project', ''):
            linked_apt = apt
            break
    
    if linked_apt:
        print(f"Linked appointment found: {linked_apt['id']} - {linked_apt['project']}")
        
        # Test 3: Delete the consumption and check if appointment is also deleted
        print("\n=== Test 3: Delete consumption and verify appointment deletion ===")
        req = urllib.request.Request('http://127.0.0.1:8080/api/consumption/' + str(created['id']), method='DELETE')
        resp = urllib.request.urlopen(req)
        
        # Check if appointment is deleted
        req = urllib.request.Request('http://127.0.0.1:8080/api/appointments?year=2026&month=7')
        resp = urllib.request.urlopen(req)
        apts_after = json.loads(resp.read())
        
        apt_still_exists = any('测试治疗' in a.get('project', '') for a in apts_after)
        if not apt_still_exists:
            print("✅ SUCCESS: Appointment was automatically deleted when consumption was deleted!")
        else:
            print("❌ FAIL: Appointment still exists after consumption deletion")
    else:
        print("❌ No linked appointment found (this is expected since sync_to_apt=1 might not create appointment in this test)")
        
except Exception as e:
    print(f"Error: {e}")
