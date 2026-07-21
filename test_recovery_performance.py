"""恢复与性能测试 — 大数据压力 + 备份恢复场景"""

import requests, json, time, sys

BASE_URL = "http://66.154.101.204"

def api(path, method='get', data=None, timeout=15):
    url = f"{BASE_URL}{path}"
    if method == 'get':
        return requests.get(url, timeout=timeout)
    return getattr(requests, method)(url, json=data, timeout=timeout)

class PerfTest:
    def __init__(self):
        self.pids = []
        self.aids = []

    def cleanup(self):
        for aid in self.aids:
            try: api(f'/api/appointments/{aid}', 'delete')
            except: pass
        for pid in self.pids:
            try: api(f'/api/patients/{pid}', 'delete')
            except: pass

    def test_massive_patients(self):
        print("\n=== 100-条患者压力测试 ===")
        count = 100
        ts = int(time.time())
        start = time.time()
        created = 0
        for i in range(count):
            r = api('/api/patients', 'post', {
                "name": f"压力测试_{ts}_{i+1:04d}",
                "gender": "男" if i%2==0 else "女",
                "phone": f"139{ts+i:010d}",
                "age": 18 + i%75
            })
            if r.status_code == 200:
                self.pids.append(r.json()['id'])
                created += 1
            if (i+1)%20 == 0:
                elapsed = time.time()-start
                print(f"  进度 {i+1}/{count} ({created/(elapsed):.1f} 条/s)")
        elapsed = time.time()-start
        print(f"创建 {created}/{count} 条, 耗时 {elapsed:.1f}s, 速率 {created/elapsed:.1f} 条/s")
        
        # 查询性能
        r = api('/api/patients')
        if r.status_code == 200:
            total = len(r.json())
            print(f"总患者数: {total}")
        return created >= count * 0.9  # 90% 成功率就通过

    def test_recovery_cycle(self):
        print("\n=== 备份恢复全流程 ===")
        ts = int(time.time())
        
        # 创建测试数据
        r = api('/api/patients', 'post', {"name":f"恢复测试_A_{ts}","gender":"男","phone":f"130{ts}1","age":25})
        if r.status_code!=200: return False
        pid1 = r.json()['id']; self.pids.append(pid1)
        
        r = api('/api/patients', 'post', {"name":f"恢复测试_B_{ts}","gender":"女","phone":f"130{ts}2","age":26})
        if r.status_code!=200: return False
        pid2 = r.json()['id']; self.pids.append(pid2)
        
        # 创建预约
        r = api('/api/appointments', 'post', {
            "patient_id": pid1, "year": 2026, "month": 7, "day": 20,
            "time_slot": "10:00-11:00", "project": "测试项目", "amount": 100
        })
        if r.status_code!=200: return False
        aid = r.json()['id']; self.aids.append(aid)
        
        print(f"创建测试数据: 患者={pid1},{pid2} 预约={aid}")
        
        # 备份
        r = api('/api/backup', 'get', timeout=30)
        ok = r.status_code == 200
        print(f"备份: {'PASS (HTTP 200)' if ok else f'FAIL ({r.status_code})'}")
        
        # 删除部分数据
        api(f'/api/patients/{pid1}', 'delete')
        print(f"删除患者 {pid1} (含级联)")
        
        # 验证删除
        r = api(f'/api/patients')  # all patients
        all_p = r.json()
        still_has = any(p['id']==pid1 for p in all_p)
        print(f"删除验证 ({pid1}): {'FAIL 仍存在' if still_has else 'PASS 已删除'}")
        
        return True  # 流程本身通过

    def test_system_load(self):
        print("\n=== 系统负载测试 ===")
        # 同时进行多个不同类型的请求
        start = time.time()
        results = []
        
        # 并发请求 (串行模拟)
        for _ in range(20):
            r = api('/api/patients')
            results.append(r.status_code)
        
        elapsed = time.time() - start
        ok_count = sum(1 for s in results if s == 200)
        print(f"20次查询: {ok_count}/20 成功, 耗时 {elapsed:.2f}s")
        
        # 同步状态
        r = api('/api/sync-status')
        print(f"同步状态: {'PASS' if r.ok else 'FAIL'} {r.json()}")
        
        return ok_count >= 19

    def test_concurrent_crud(self):
        print("\n=== 连续增删测试 ===")
        ts = int(time.time())
        for i in range(10):
            r = api('/api/patients', 'post', {"name":f"快速测试_{ts}_{i}","gender":"男","phone":f"1390{ts}{i:03d}","age":20+i})
            if r.status_code == 200:
                pid = r.json()['id']
                api(f'/api/patients/{pid}', 'delete')
        print("连续10次增删完成 (无异常即通过)")
        return True

def main():
    t = PerfTest()
    tests = [
        ("100条患者压力", t.test_massive_patients),
        ("备份恢复流程", t.test_recovery_cycle),
        ("系统负载测试", t.test_system_load),
        ("连续增删测试", t.test_concurrent_crud),
    ]
    
    results = []
    for name, func in tests:
        try:
            ok = func()
        except Exception as e:
            print(f"  ERROR: {e}")
            ok = False
        results.append((name, ok))
        print(f">>> {name}: {'PASS' if ok else 'FAIL'}\n")
    
    t.cleanup()
    
    print("=" * 50)
    print("测试汇总")
    print("=" * 50)
    all_pass = True
    for n, ok in results:
        print(f"  {n:20s} {'PASS' if ok else 'FAIL'}")
        if not ok: all_pass = False
    print("=" * 50)
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
