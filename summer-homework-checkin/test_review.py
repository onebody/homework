#!/usr/bin/env python
"""测试打卡审核流程"""
import requests
import base64
from io import BytesIO
from PIL import Image

BASE = "http://localhost:8000"

def create_test_image():
    """创建测试图片（确保大于5KB）"""
    img = Image.new('RGB', (800, 600), color='lightblue')
    # 添加一些随机像素使图片更大
    import random
    pixels = img.load()
    for i in range(0, 800, 10):
        for j in range(0, 600, 10):
            pixels[i, j] = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    buf = BytesIO()
    img.save(buf, format='JPEG', quality=95)
    buf.seek(0)
    return buf

def test_review_workflow():
    print("=" * 60)
    print("测试打卡审核流程")
    print("=" * 60)
    
    # 1. 注册测试学生
    print("\n1. 注册测试学生...")
    r = requests.post(f"{BASE}/api/auth/register", json={
        "username": "test_student",
        "password": os.environ.get("TEST_STUDENT_PASSWORD", "test123456"),
        "nickname": "测试学生",
        "role": "student"
    })
    assert r.status_code == 200, f"注册失败: {r.text}"
    student_token = r.json()["access_token"]
    student_id = r.json()["user"]["id"]
    print(f"✓ 学生注册成功 (ID: {student_id})")
    
    # 2. 登录管理员
    print("\n2. 登录管理员...")
    admin_password = os.environ.get("ADMIN_INIT_PASSWORD", "admin123")
    r = requests.post(f"{BASE}/api/auth/login", json={
        "username": "admin",
        "password": admin_password
    })
    assert r.status_code == 200
    admin_token = r.json()["access_token"]
    print("✓ 管理员登录成功")
    
    # 3. 学生打卡（应该允许多次，且不给积分）
    print("\n3. 测试多次打卡...")
    headers_student = {"Authorization": f"Bearer {student_token}"}
    
    img1 = create_test_image()
    r = requests.post(f"{BASE}/api/checkin", 
        headers=headers_student,
        files={"photo": ("test1.jpg", img1, "image/jpeg")},
        data={"location_lat": 39.9, "location_lng": 116.4, "check_type": "normal"}
    )
    assert r.status_code == 200, f"第一次打卡失败: {r.text}"
    checkin1_id = r.json()["id"]
    print(f"✓ 第一次打卡成功 (ID: {checkin1_id})")
    
    # 检查积分 - 应该还是 0
    r = requests.get(f"{BASE}/api/auth/me", headers=headers_student)
    assert r.status_code == 200
    points_after_first = r.json()["points"]
    print(f"  第一次打卡后积分: {points_after_first} (预期: 0)")
    assert points_after_first == 0, "打卡后不应该立即获得积分"
    
    # 第二次打卡（同一天）
    img2 = create_test_image()
    r = requests.post(f"{BASE}/api/checkin",
        headers=headers_student,
        files={"photo": ("test2.jpg", img2, "image/jpeg")},
        data={"location_lat": 39.9, "location_lng": 116.4, "check_type": "normal"}
    )
    assert r.status_code == 200, f"第二次打卡失败: {r.text}"
    checkin2_id = r.json()["id"]
    print(f"✓ 第二次打卡成功 (ID: {checkin2_id})")
    
    # 4. 查看打卡历史 - 应该看到两条记录
    print("\n4. 检查打卡历史...")
    r = requests.get(f"{BASE}/api/checkin/history", headers=headers_student)
    assert r.status_code == 200
    history = r.json()
    print(f"✓ 打卡记录数: {len(history)} (预期: 2)")
    assert len(history) == 2, "应该有两条打卡记录"
    
    # 检查审核状态
    for h in history:
        assert h["review_status"] == "pending", f"记录 {h['id']} 应该是 pending 状态"
        assert h["is_effective"] == False, f"记录 {h['id']} 应该不是有效打卡"
    print("✓ 所有记录都是 pending 状态")
    
    # 5. 管理员查看打卡列表
    print("\n5. 管理员查看打卡列表...")
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    r = requests.get(f"{BASE}/api/admin/checkins", headers=headers_admin)
    assert r.status_code == 200
    checkins = r.json()
    print(f"✓ 管理员看到 {len(checkins)} 条打卡记录")
    
    # 检查待审核数量
    r = requests.get(f"{BASE}/api/admin/checkins/pending-count", headers=headers_admin)
    assert r.status_code == 200
    pending_count = r.json()["count"]
    print(f"✓ 待审核数量: {pending_count} (预期: 2)")
    assert pending_count == 2, "应该有 2 条待审核记录"
    
    # 6. 审核通过第一条
    print("\n6. 审核通过第一条打卡...")
    r = requests.put(f"{BASE}/api/admin/checkins/{checkin1_id}/review",
        headers=headers_admin,
        json={"status": "approved", "note": "照片清晰，打卡有效"}
    )
    assert r.status_code == 200, f"审核失败: {r.text}"
    print("✓ 审核通过")
    
    # 检查学生积分 - 应该增加
    r = requests.get(f"{BASE}/api/auth/me", headers=headers_student)
    points_after_approve = r.json()["points"]
    print(f"  审核通过后积分: {points_after_approve} (预期: 10)")
    assert points_after_approve == 10, "审核通过后应该获得 10 积分"
    
    # 检查有效打卡数
    r2 = requests.get(f"{BASE}/api/checkin/streak", headers=headers_student)
    effective = r2.json()["effective_checkins"]
    print(f"  有效打卡数: {effective} (预期: 1)")
    assert effective == 1, "应该有 1 次有效打卡"
    
    # 7. 拒绝第二条打卡
    print("\n7. 拒绝第二条打卡...")
    r = requests.put(f"{BASE}/api/admin/checkins/{checkin2_id}/review",
        headers=headers_admin,
        json={"status": "rejected", "note": "照片模糊，请重新打卡"}
    )
    assert r.status_code == 200
    print("✓ 已拒绝")
    
    # 积分应该不变
    r = requests.get(f"{BASE}/api/auth/me", headers=headers_student)
    points_after_reject = r.json()["points"]
    print(f"  拒绝后积分: {points_after_reject} (预期: 10)")
    assert points_after_reject == 10, "拒绝后积分不应该变化"
    
    # 8. 验证审核历史
    print("\n8. 验证审核历史...")
    r = requests.get(f"{BASE}/api/checkin/history", headers=headers_student)
    history = r.json()
    
    status_map = {h["id"]: h["review_status"] for h in history}
    assert status_map[checkin1_id] == "approved", "第一条应该是 approved"
    assert status_map[checkin2_id] == "rejected", "第二条应该是 rejected"
    print("✓ 审核状态正确")
    
    # 9. 再次打卡测试（同一天可以继续打卡）
    print("\n9. 测试同一天继续打卡...")
    img3 = create_test_image()
    r = requests.post(f"{BASE}/api/checkin",
        headers=headers_student,
        files={"photo": ("test3.jpg", img3, "image/jpeg")},
        data={"location_lat": 39.9, "location_lng": 116.4, "check_type": "normal"}
    )
    assert r.status_code == 200, f"第三次打卡失败: {r.text}"
    print(f"✓ 同一天可以多次打卡")
    
    # 检查打卡总数
    r = requests.get(f"{BASE}/api/checkin/history", headers=headers_student)
    assert len(r.json()) == 3, "应该有 3 条打卡记录"
    print("✓ 打卡记录数正确")
    
    # 10. 查看今日状态
    print("\n10. 检查今日状态...")
    r = requests.get(f"{BASE}/api/checkin/today", headers=headers_student)
    today = r.json()
    print(f"  今日打卡: {today['today_checked']}")
    print(f"  待审核: {today['today_pending']}")
    print(f"  总打卡数: {today['today_count']}")
    print(f"  已通过数: {today['approved_count']}")
    print(f"  待审核数: {today['pending_count']}")
    assert today['today_count'] == 3, "今天应该有 3 次打卡"
    assert today['approved_count'] == 1, "应该有 1 次已通过"
    assert today['pending_count'] == 1, "应该有 1 次待审核（第三次打卡）"
    print("✓ 今日状态正确")
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)
    print("\n功能总结：")
    print("✓ 每天可以多次打卡")
    print("✓ 打卡后需要管理员审核")
    print("✓ 未审核的打卡不计入有效打卡")
    print("✓ 未审核的打卡不发放积分")
    print("✓ 审核通过后自动发放积分")
    print("✓ 学生端可以看到打卡审核状态")
    print("✓ 管理端可以查看待审核列表并进行审核")
    print("=" * 60)

if __name__ == "__main__":
    test_review_workflow()
