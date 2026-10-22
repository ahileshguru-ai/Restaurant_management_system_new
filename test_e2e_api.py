"""
End-to-End HTTP API & Workflow Verification
============================================
Tests live FastAPI server endpoints on http://127.0.0.1:8000:
  1. Frontend index.html and static asset delivery
  2. Ferraiolo-Kuhn RBAC authentication and JWT tokens
  3. Multi-table order dispatch and floor isolation
  4. Chef KDS queue retrieval and status lifecycle
  5. Checkout with payment splits and table liberation
  6. Verified customer feedback with Anti-Fraud Gatekeeper
  7. Jim Gray Single-Seat Handover Protocol
  8. All 4 Automated SQL BI Views
"""

import urllib.request
import urllib.parse
import json
import sys

BASE_URL = "http://127.0.0.1:8000"


def http_req(path, method="GET", data=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Accept": "application/json"}
    body = None

    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read()
            if path == "/":
                return {"status": response.status, "content_type": response.headers.get("Content-Type"), "length": len(res_body)}
            return json.loads(res_body.decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            return {"error": True, "status": e.code, "detail": json.loads(err_body).get("detail", err_body)}
        except Exception:
            return {"error": True, "status": e.code, "detail": err_body}
    except urllib.error.URLError as e:
        print(f"\n[ERROR] Connection failed to {url}: {e.reason}")
        print(" -> The FastAPI server is not currently running.")
        print(" -> Please start the server first in another terminal:")
        print("    .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000\n")
        sys.exit(1)


def run_e2e_test():
    print("=" * 70)
    print("RUNNING LIVE END-TO-END HTTP RESTAURANT DBMS TESTS ON PORT 8000")
    print("=" * 70)

    # 1. Health & Root HTML Check
    print("\n[STEP 1] Probing Root UI and Health Check...")
    root_res = http_req("/")
    assert root_res["status"] == 200
    print(f"  [OK] GET / returned 200 OK (HTML presentation layer {root_res['length']} bytes)")

    health_res = http_req("/api/health")
    assert health_res["status"] == "healthy"
    print(f"  [OK] Health check passed: {health_res}")

    # 2. RBAC Login Verification
    print("\n[STEP 2] Testing Cryptographic Password Authentication & JWT...")
    # 2a. Shop Manager login
    mgr_login = http_req("/api/auth/login", method="POST", data={"username": "shopmanager", "password": "manager123"})
    assert "access_token" in mgr_login, f"Login failed: {mgr_login}"
    mgr_token = mgr_login["access_token"]
    print(f"  [OK] Shop Manager authenticated: {mgr_login['user']['staff_name']} (Role: {mgr_login['user']['role']})")

    # 2b. Waiter login
    waiter_login = http_req("/api/auth/login", method="POST", data={"username": "waiter_rahul", "password": "waiter123"})
    waiter_token = waiter_login["access_token"]
    print(f"  [OK] Waiter authenticated: {waiter_login['user']['staff_name']} (Role: {waiter_login['user']['role']})")

    # 2c. Chef login
    chef_login = http_req("/api/auth/login", method="POST", data={"username": "chef_vikram", "password": "chef123"})
    chef_token = chef_login["access_token"]
    print(f"  [OK] Chef authenticated: {chef_login['user']['staff_name']} (Role: {chef_login['user']['role']})")

    # 3. Waiter Operations
    print("\n[STEP 3] Testing Waiter Multi-Table Order Dispatch...")
    # Create order across Table 7 and Table 8
    order_payload = {
        "customer_count": 5,
        "table_numbers": [7, 8],
        "items": [
            {"MenuItemID": 1, "Quantity": 2}, # Masala Dosa -> Chef Vikram
            {"MenuItemID": 2, "Quantity": 1}  # Ghee Roast Dosa -> Chef Vikram
        ]
    }
    ord_res = http_req("/api/waiter/orders", method="POST", data=order_payload, token=waiter_token)
    assert "order_id" in ord_res, f"Order creation failed: {ord_res}"
    new_order_id = ord_res["order_id"]
    print(f"  [OK] Order #{new_order_id} created across Tables {ord_res['tables']} (Estimate: Rs.{ord_res['total_estimate']})")

    # 4. Chef KDS Operations
    print("\n[STEP 4] Testing Chef KDS Queue & Lifecycle (Pending -> Cooking -> Ready)...")
    kds_res = http_req("/api/chef/queue", token=chef_token)
    queue = kds_res.get("queue", [])
    print(f"  [OK] Chef Vikram sees {len(queue)} assigned dishes in live KDS queue.")
    
    # Find one of our newly ordered dishes
    my_dish = next((d for d in queue if d["OrderID"] == new_order_id), None)
    assert my_dish is not None, "Newly created dish not found in Chef Vikram queue!"
    detail_id = my_dish["OrderDetailID"]
    print(f"  [OK] Advancing '{my_dish['ItemName']}' (Detail #{detail_id}): Pending -> Cooking...")
    
    c_res = http_req(f"/api/chef/order-details/{detail_id}/status", method="PUT", data={"new_status": "Cooking"}, token=chef_token)
    assert c_res["new_status"] == "Cooking"

    # Pre-Cooking Edit Block Trigger verification
    del_res = http_req(f"/api/waiter/order-details/{detail_id}", method="DELETE", token=waiter_token)
    assert del_res.get("error") == True and del_res.get("status") == 400
    print(f"  [OK] Pre-Cooking Edit Block database trigger blocked deletion of 'Cooking' dish: {del_res['detail']}")

    print(f"  [OK] Advancing to Ready...")
    r_res = http_req(f"/api/chef/order-details/{detail_id}/status", method="PUT", data={"new_status": "Ready"}, token=chef_token)
    assert r_res["new_status"] == "Ready"
    print("  [OK] Dish marked Ready for waitstaff pickup.")

    # 5. Out-of-Stock Atomic Transaction
    print("\n[STEP 5] Testing Out-of-Stock Atomic Transaction via API...")
    oos_res = http_req("/api/chef/menu/2/out-of-stock", method="POST", data={"reason": "Pure Ghee shortage during evening rush"}, token=chef_token)
    assert oos_res["status"] == "success"
    print(f"  [OK] Out-of-Stock transaction committed for '{oos_res['item_name']}' into Shortage_Logs.")

    # Restore back
    restore_res = http_req("/api/chef/menu/2/restore-stock", method="POST", token=chef_token)
    assert restore_res["is_available"] == True
    print(f"  [OK] Dish availability restored.")

    # 6. Checkout & Payment Splits
    print("\n[STEP 6] Testing Order Checkout & Payment Split Allocation...")
    bill_total = ord_res["total_estimate"]
    cash_part = 200.00
    upi_part = bill_total - cash_part
    chk_res = http_req(f"/api/waiter/orders/{new_order_id}/checkout", method="POST", data={"cash_amount": cash_part, "upi_amount": upi_part}, token=waiter_token)
    assert chk_res["status"] == "success"
    print(f"  [OK] Checkout complete: Cash Rs.{cash_part}, UPI Rs.{upi_part}. Tables {chk_res['freed_tables']} freed.")

    # 7. Anti-Fraud Gatekeeper Feedback Verification
    print("\n[STEP 7] Testing Anti-Fraud Database Gatekeeper Feedback API...")
    # 7a: Fraudulent attempt without name/phone
    fraud_attempt = http_req(f"/api/waiter/orders/{new_order_id}/feedback", method="POST", data={"service_rating": 5}, token=waiter_token)
    assert "error" in fraud_attempt and fraud_attempt["status"] == 400
    print(f"  [OK] Anti-Fraud constraint caught fraudulent padding attempt: {fraud_attempt['detail']}")

    # 7b: Authentic customer feedback
    legit_fb = http_req(f"/api/waiter/orders/{new_order_id}/feedback", method="POST", data={
        "customer_name": "Siddharth Verma",
        "phone_number": "9876501234",
        "service_rating": 5,
        "food_rating": 5,
        "ambience_rating": 5,
        "cleanliness_rating": 5,
        "review_text": "Live test customer experience was seamless and delicious!"
    }, token=waiter_token)
    assert legit_fb["status"] == "success"
    print(f"  [OK] Verified customer feedback stored with FeedbackID {legit_fb['feedback_id']}.")

    # 8. Automated SQL BI Views Verification via HTTP
    print("\n[STEP 8] Verifying 4 Automated Business Intelligence SQL Views...")
    v1 = http_req("/api/manager/views/waiter-performance", token=mgr_token)
    print(f"  [OK] View 5.1 (View_Waiter_Performance): {len(v1['view_data'])} rows (Top Waiter: {v1['view_data'][0]['WaiterName']} with {v1['view_data'][0]['TotalPerformancePoints']} pts)")

    v2 = http_req("/api/manager/views/chef-performance", token=mgr_token)
    print(f"  [OK] View 5.2 (View_Chef_Performance): {len(v2['view_data'])} rows (Top Chef: {v2['view_data'][0]['ChefName']} with {v2['view_data'][0]['CulinaryPerformancePoints']} pts)")

    v3 = http_req("/api/manager/views/daily-collections", token=mgr_token)
    print(f"  [OK] View 5.3 (View_Daily_Waiter_Collections): {len(v3['view_data'])} daily shift records")

    v4 = http_req("/api/manager/views/monthly-profit-loss", token=mgr_token)
    print(f"  [OK] View 5.4 (View_Monthly_Profit_Loss): {len(v4['view_data'])} monthly fiscal reports (P&L: Rs.{v4['view_data'][0]['NetProfitLoss']})")

    # 9. Single-Seat Handover Protocol
    print("\n[STEP 9] Testing Single-Seat Handover Protocol over HTTP...")
    handover_call = http_req("/api/auth/handover", method="POST", data={
        "admin_role_name": "Kitchen Manager",
        "new_employee_name": "Chef Karthik Raman",
        "new_username": "kitchenmgr_karthik",
        "new_password": "newSecurePassword456",
        "shift": "Morning Shift",
        "salary": 52000.00
    }, token=mgr_token)
    assert handover_call["status"] == "success"
    print(f"  [OK] Handover Protocol executed: {handover_call['message']}")
    print(f"       Retired Staff: {handover_call['retired_employee']['Name']}")
    print(f"       New Active User: {handover_call['new_user']['Username']}")

    print("\n" + "=" * 70)
    print("ALL LIVE END-TO-END WORKFLOWS & CONSTRAINTS VALIDATED WITH 100% SUCCESS!")
    print("=" * 70)


if __name__ == "__main__":
    run_e2e_test()
