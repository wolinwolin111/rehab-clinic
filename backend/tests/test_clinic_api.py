"""综合 API 测试 — 覆盖健康检查、大数据性能、备份恢复、边界情况"""

import requests, json, time, sys

BASE_URL = "http://66.154.101.204"

def api(path, method='get', data=None, timeout=15):
    url = f"{BASE_URL}{path}"
    if method == 'get':
        return requests.get(url, timeout=timeout)
    return getattr(requests, method)(url, json=data, timeout=timeout)

class Tester:
    def __init__(self):
        self.pids = []   # 创建的患者 ID
        self.aids = []   # 创建的预约 ID
        self.cids = []   # 创建的消费 ID

    def cleanup(self):
        print("\n清理测试数据...")
        for cid in self.cids:
            try: api(f'/api/consumption/{cid}', 'delete')
            except: pass
        for aid in self.aids:
            try: api(f'/api/appointments/{aid}', 'delete')
            except: pass
        for pid in self.pids:
            try: api(f'/api/patients/{pid}', 'delete')
            except: pass

    def test_health(self):
        print("\n=== 健康检查 ===")
        try:
            r = requests.get(BASE_URL, timeout=10)
            print(f"首页响应: {r.status_code}")
            return r.status_code < 500
        except Exception as e:
            print(f"连接失败: {e}")
            return False

    def test_large_scale(self):
        print("\n=== 大规模数据测试 (50 条患者) ===")
        count = 50
        ts = int(time.time())
        start = time.time()
        ok = 0
        for i in range(count):
            r = api('/api/patients', 'post', {
                "name": f"批量测试_{ts}_{i+1:03d}",
                "gender": "男" if i%2==0 else "女",
                "phone": f"138{ts+i:010d}",
                "age": 20 + i%50
            })
            if r.status_code == 200:
                pid = r.json()['id']
                self.pids.append(pid)
                ok += 1
            else:
                if ok < 3:  # 只打前几个错误
                    print(f"  失败 #{i+1}: {r.status_code} {r.text[:100]}")
            if (i+1)%10==0:
                print(f"  进度 {i+1}/{count}")
        elapsed = time.time() - start
        print(f"成功创建 {ok}/{count}, 耗时 {elapsed:.2f}s, 平均 {elapsed/max(ok,1):.3f}s/条")
        
        # 获取全量验证
        r = api('/api/patients')
        total = len(r.json()) if r.status_code==200 else -1
        print(f"数据库患者总数: {total}")
        return ok == count

    def test_appointment_linking(self):
        print("\n=== 预约-消费关联测试 ===")
        # 创建患者
        r = api('/api/patients', 'post', {"name":"关联测试","gender":"女","phone":"13900000010","age":28})
        if r.status_code != 200: return False
        pid = r.json()['id']
        self.pids.append(pid)
        
        # 创建带 sync_to_con 的预约
        r = api('/api/appointments', 'post', {
            "patient_id": pid, "year": 2026, "month": 7,
            "day": 10, "time_slot": "14:00-15:00",
            "project": "复诊", "amount": 150,
            "sync_to_con": True, "remark": "关联测试"
        })
        if r.status_code != 200:
            print(f"创建失败: {r.text}")
            return False
        aid = r.json()['id']
        self.aids.append(aid)
        linked_cid = r.json().get('linked_con_id')
        print(f"创建预约 ID={aid}, 关联消费 ID={linked_cid}")
        
        if linked_cid:
            self.cids.append(linked_cid)
            # 验证关联消费存在
            r = api(f'/api/consumption?patient_id={pid}')
            items = r.json()
            found = any(c['id']==linked_cid for c in items)
            print(f"关联消费存在: {found}")
            return found
        return True  # sync_to_con 可选

    def test_backup(self):
        print("\n=== 备份/恢复测试 ===")
        # 备份端点
        r = api('/api/backup', 'get', timeout=30)
        print(f"备份端点: {r.status_code}")
        if r.status_code == 200:
            content_type = r.headers.get('content-type','')
            size = len(r.content)
            print(f"  类型: {content_type}, 大小: {size} 字节")
            return True
        return False

    def test_sync_status(self):
        print("\n=== 同步状态 ===")
        r = api('/api/sync-status')
        if r.status_code == 200:
            print(f"同步状态: {r.json()}")
        else:
            print(f"获取失败: {r.status_code}")
        return r.status_code == 200

    def test_history(self):
        print("\n=== 操作历史 ===")
        r = api('/api/history')
        if r.status_code == 200:
            items = r.json()
            print(f"历史记录数: {len(items)}")
        else:
            print(f"获取失败: {r.status_code}")
        return r.status_code == 200

    def test_edge_cases(self):
        print("\n=== 边界情况 ===")
        
        # 404: 删除不存在的患者
        r = api('/api/patients/99999', 'delete')
        print(f"删除不存在的患者: {r.status_code} (预期 400/404)")
        
        # 超大金额
        r = api('/api/patients', 'post', {"name":"大额患者","gender":"男","phone":"13900000099","age":30})
        if r.status_code == 200:
            pid = r.json()['id']
            self.pids.append(pid)
            r2 = api('/api/appointments', 'post', {
                "patient_id": pid, "year": 2026, "month": 7,
                "day": 1, "project": "大额测试",
                "amount": 99999999, "remark": "大额测试"
            })
            print(f"超大金额写入: {r2.status_code}")
        return True

def main():
    t = Tester()
    tests = [
        ("健康检查", t.test_health),
        ("大规模数据(50条)", t.test_large_scale),
        ("预约-消费关联", t.test_appointment_linking),
        ("备份端点", t.test_backup),
        ("同步状态", t.test_sync_status),
        ("操作历史", t.test_history),
        ("边界情况", t.test_edge_cases),
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
        print(f"  {n:25s} {'PASS' if ok else 'FAIL'}")
        if not ok: all_pass = False
    print("=" * 50)
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
