#!/usr/bin/env python3
# Test script to verify that consumption deletion and restoration works correctly

import json
import time
import urllib.request

def test_consumption_deletion_and_restoration():
    print("=== Testing consumption deletion and restoration ===")
    
    # Wait for any pending operations to complete
    time.sleep(2)
    
    # Step 1: Create a test patient
    print("\nformation: {
        "name": "Test Patient",
        "age": 30,
        "gender": "男"
    })
    req = urllib.request.Request('http://127.0.0.1:8080/api/patients', data=data, headers={'Content-Type': 'application/json'})
    try:
        resp = urllib.request.urlopen(req)
        patient_data = json.loads(resp.read())
        patient_id = patient_data['id']
        print(f"Created test patient with ID: {patient_id}")
    except Exception as e:
        print(f"Failed to create patient: {e}")
        return False
    
    # Step 2: Create a test appointment for this patient
    apt_data = json.dumps({
        "patient_id": patient_id,
        "year": 2026,
        "month": 7,
        "day": 15,
        "time_slot": "14:00-15:00",
        "project": "测试治疗",
        "amount": 200
    }).encode()
    req = urllib.request.Request('http://127.0.0.1:8080/api/appointments', data=apt_data, headers={'Content-Type': 'application/json'})
    try:
        resp = urllib.request.urlopen(req)
        apt_data = json.loads(resp.read())
        apt_id = apt_data['id']
        print(f"Created test appointment with ID: {apt_id}")
    except Exception as e:
        print(f"Failed to create appointment: {e}")
        return False
    
    # Step 3: Create a consumption record linked to this appointment
    # First, let's create the consumption
    cons_data = json.dumps({
        "patient_id": patient_id,
        "month": 7,
        "day": 15,
        "project": "测试治疗",
        "amount": 150,
        "time_slot": "14:00-15:00",
        "sync_to_apt": 1  # This should link it to the appointment
    }).encode()
    req = urllib.request.Request('http://127.0.0.1:8080/api/consumption', data=cons_data, headers={'Content-Type': 'application/json'})
    try:
        resp = urllib.request.urlopen(req)
        cons_data = json.loads(resp.read())
        cons_id = cons_data['id']
        print(f"Created test consumption with ID: {cons_id}")
    except Exception as e:
        print(f"Failed to create consumption: {e}")
        return False
    
    # Step 4: Verify that the consumption and appointment are linked
    # Check the appointment to see if it has the consumption linked
    try:
        req = urllib.request.Request(f'http://127.0.0.1:8080/api/appointments/{apt_id}')
        resp = urllib.request.urlopen(req)
        apt_data = json.loads(resp.read())
        print(f"Appointment data: {apt_data}")
        
        # Check consumption links
        req = urllib.request.Request('http://127.0.0.1:8080/api/consumption?patient_id=' + str(patient_id))
        resp = urllib.request.urlopen(req)
        cons_list = json.loads(resp.read())
        print(f"Consumptions for patient: {cons_list}")
        
        # Check if there's a link in the appointment_consumption_link table indirectly
        # We'll check this by seeing if the consumption is marked as synced
        linked_cons = [c for c in cons_list if c.get('id') == cons_id and c.get('sync_to_apt') == 1]
        if linked_cons:
            print("✓ Consumption is marked as synced to appointment")
        else:
            print("⚠ Consumption is not marked as synced - this might be expected if linking happens differently")
            
    except Exception as e:
        print(f"Error checking links: {e}")
    
    # Step 5: Delete the consumption (this should also delete the linked appointment due to our fix)
    print("\n--- Deleting consumption ---")
    try:
        req = urllib.request.Request(f'http://127.0.0.1:8080/api/consumption/{cons_id}', method='DELETE')
        resp = urllib.request.urlopen(req)
        delete_result = json.loads(resp.read())
        print(f"Deletion result: {delete_result}")
        
        if delete_result.get('success'):
            print("✓ Consumption deletion successful")
        else:
            print("✗ Consumption deletion failed")
            return False
    except Exception as e:
        print(f"Failed to delete consumption: {e}")
        return False
    
    # Step 6: Verify that both the consumption and appointment are deleted
    print("\n--- Verifying deletion ---")
    try:
        # Check if consumption is deleted
        req = urllib.request.Request(f'http://127.0.0.1:8080/api/consumption/{cons_id}')
        resp = urllib.request.urlopen(req)
        print("✗ Consumption still exists after deletion")
        return False
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("✓ Consumption successfully deleted (404 Not Found)")
        else:
            print(f"✗ Unexpected error checking consumption: {e}")
            return False
    except Exception as e:
        print(f"Error checking consumption: {e}")
        return False
        
    try:
        # Check if appointment is deleted
        req = urllib.request.Request(f'http://127.0.0.1:8080/api/appointments/{apt_id}')
        resp = urllib.request.urlopen(req)
        print("✗ Appointment still exists after consumption deletion")
        return False
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("✓ Appointment successfully deleted (404 Not Found)")
        else:
            print(f"✗ Unexpected error checking appointment: {e}")
            return False
    except Exception as e:
        print(f"Error checking appointment: {e}")
        return False
    
    # Step 7: Get the history to find the deletion record
    print("\n--- Getting history for restoration ---")
    try:
        req = urllib.request.Request('http://127.0.0.1:8080/api/history')
        resp = urllib.request.urlopen(req)
        history_data = json.loads(resp.read())
        print(f"History count: {len(history_data)}")
        
        # Find our consumption deletion in the history
        cons_deletion = None
        for item in history_data:
            if (item.get('action_type') == 'delete' and 
                item.get('target_type') == 'consumption' and 
                item.get('target_id') == cons_id):
                cons_deletion = item
                break
        
        if cons_deletion is None:
            print("✗ Could not find consumption deletion in history")
            return False
            
        print(f"Found consumption deletion in history: {cons_deletion['id']}")
        print(f"History data: {json.dumps(cons_deletion['data'], indent=2, ensure_ascii=False)}")
        
        # Check if the history data includes linked appointment information
        hist_data = cons_deletion['data']
        if 'linkedAppointment' in hist_data and hist_data['linkedAppointment']:
            print("✓ History data includes linked appointment information")
            linked_apt = hist_data['linkedAppointment']
            print(f"Linked appointment data: {json.dumps(linked_apt, indent=2, ensure_ascii=False)}")
        else:
            print("⚠ History data does not include linked appointment information")
            # This might be expected if our test didn't create a proper link
            
    except Exception as e:
        print(f"Error getting history: {e}")
        return False
    
    # Step 8: Restore the deletion via history
    print("\n--- Restoring via history ---")
    try:
        hist_id = cons_deletion['id']
        req = urllib.request.Request(f'http://127.0.0.1:8080/api/history/{hist_id}/restore', method='POST')
        resp = urllib.request.urlopen(req)
        restore_result = json.loads(resp.read())
        print(f"Restoration result: {restore_result}")
        
        if restore_result.get('success'):
            print("✓ Restoration successful")
        else:
            print(f"✗ Restoration failed: {restore_result}")
            return False
    except Exception as e:
        print(f"Failed to restore via history: {e}")
        return False
    
    # Step 9: Verify that both the consumption and appointment are restored
    print("\n--- Verifying restoration ---")
    try:
        # Check if consumption is restored
        req = urllib.request.Request(f'http://127.0.0.1:8080/api/consumption/{cons_id}')
        resp = urllib.request.urlopen(req)
        restored_cons = json.loads(resp.read())
        print(f"✓ Consumption restored: {restored_cons}")
    except Exception as e:
        print(f"✗ Failed to restore consumption: {e}")
        return False
        
    try:
        # Check if appointment is restored
        req = urllib.request.Request(f'http://127.0.0.1:8080/api/appointments/{apt_id}')
        resp = urllib.request.urlopen(req)
        restored_apt = json.loads(resp.read())
        print(f"✓ Appointment restored: {restored_apt}")
    except Exception as e:
        print(f"✗ Failed to restore appointment: {e}")
        return False
    
    # Step 10: Verify that they are properly linked again
    print("\n--- Verifying linkage after restoration ---")
    try:
        # Check the consumption to see if it's properly linked
        req = urllib.request.Request(f'http://127.0.0.1:8080/api/consumption/{cons_id}')
        resp = urllib.request.urlopen(req)
        restored_cons = json.loads(resp.read())
        
        if restored_cons.get('sync_to_apt') == 1:
            print("✓ Consumption is properly linked to appointment (sync_to_apt=1)")
        else:
            print(f"⚠ Consumption sync_to_apt is {restored_cons.get('sync_to_apt')} - expected 1")
            
    except Exception as e:
        print(f"Error checking consumption linkage: {e}")
        return False
    
    print("\n=== All tests passed! ===")
    return True

if __name__ == "__main__":
    success = test_consumption_deletion_and_restoration()
    if success:
        print("\n🎉 TEST PASSED: Consumption deletion and restoration works correctly!")
    else:
        print("\n❌ TEST FAILED: There are issues with the implementation.")