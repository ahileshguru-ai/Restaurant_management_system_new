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

    # 4b. Chef Cancellation Prohibition Check
    print("  [OK] Verifying Chef is prohibited from cancelling the order...")
    discard_attempt = http_req(f"/api/chef/order-details/{detail_id}/discard", method="POST", data={"reason": "Overcooked"}, token=chef_token)
    assert discard_attempt.get("error") == True and discard_attempt.get("status") == 403
    print(f"  [OK] Chef direct cancellation blocked with HTTP 403: {discard_attempt['detail']}")

    # 4c. Verify Chef Redo endpoint is removed
    print("  [OK] Verifying Chef Redo endpoint is removed...")
    redo_res = http_req(f"/api/chef/order-details/{detail_id}/redo", method="POST", token=chef_token)
    assert redo_res.get("status") == 404 or redo_res.get("error") == True
    print("  [OK] Chef Redo endpoint confirmed completely removed.")

    # Advance back to Ready after recooking
    r2_res = http_req(f"/api/chef/order-details/{detail_id}/status", method="PUT", data={"new_status": "Ready"}, token=chef_token)
    assert r2_res["new_status"] == "Ready"
    print("  [OK] Freshly prepared dish advanced back to Ready.")

    # 5. Out-of-Stock Atomic Transaction
    print("\n[STEP 5] Testing Out-of-Stock Atomic Transaction via API...")
    oos_res = http_req("/api/chef/menu/2/out-of-stock", method="POST", data={"reason": "Pure Ghee shortage during evening rush"}, token=chef_token)
    assert oos_res["status"] == "success"
    print(f"  [OK] Out-of-Stock transaction committed for '{oos_res['item_name']}' into Shortage_Logs.")

    # Restore back
    restore_res = http_req("/api/chef/menu/2/restore-stock", method="POST", token=chef_token)
    assert restore_res["is_available"] == True
    print(f"  [OK] Dish availability restored.")

    # 5B. Numerical Stock Tracking & Advance Alterations
    print("\n[STEP 5B] Testing Numerical Stock Tracking, Real-Time Decrement & Chef Advance Updates...")
    # Waiter checks menu: Steamed Idly has 10 portions in stock
    w_menu = http_req("/api/waiter/menu", method="GET", token=waiter_token)
    idly = next((m for m in w_menu.get("menu", []) if m["MenuItemID"] == 9), None)
    assert idly is not None, "Steamed Idly must be present on waiter menu"
    assert "StockQuantity" in idly and isinstance(idly["StockQuantity"], int) and idly["StockQuantity"] >= 0
    print(f"  [OK] Waiter menu displays real-time stock: '{idly['ItemName']}' shows {idly['StockQuantity']} portions available in advance.")

    # Chef updates stock in advance (e.g. prepared 20 idlys)
    chef_set_stock = http_req("/api/chef/menu/9/stock", method="PUT", data={"stock_quantity": 20}, token=chef_token)
    assert chef_set_stock.get("status") == "success"
    assert chef_set_stock.get("stock_quantity") == 20
    assert chef_set_stock.get("is_available") == True
    print(f"  [OK] Chef altered available idly stock in advance: {chef_set_stock['message']}")

    # Waiter menu reflects the newly prepared portions (20)
    w_menu_updated = http_req("/api/waiter/menu", method="GET", token=waiter_token)
    idly_upd = next(m for m in w_menu_updated.get("menu", []) if m["MenuItemID"] == 9)
    assert idly_upd["StockQuantity"] == 20
    print(f"  [OK] Waiter menu immediately reflects updated stock of {idly_upd['StockQuantity']} portions.")

    # Waiter adds 1 idly to existing order -> stock decrements 20 -> 19
    add_dish_res = http_req(f"/api/waiter/orders/{new_order_id}/items", method="POST", data={"menu_item_id": 9, "quantity": 1}, token=waiter_token)
    assert add_dish_res.get("status") == "success"
    w_menu_dec = http_req("/api/waiter/menu", method="GET", token=waiter_token)
    idly_dec = next(m for m in w_menu_dec.get("menu", []) if m["MenuItemID"] == 9)
    assert idly_dec["StockQuantity"] == 19
    print(f"  [OK] Ordered 1 Idly: Stock automatically decremented from 20 -> {idly_dec['StockQuantity']}.")

    # Chef sets stock to 0 -> automatically marks OUT OF STOCK
    chef_zero_stock = http_req("/api/chef/menu/9/stock", method="PUT", data={"stock_quantity": 0}, token=chef_token)
    assert chef_zero_stock.get("stock_quantity") == 0
    assert chef_zero_stock.get("is_available") == False
    # Waiter menu shows 0 left and IsAvailable = 0
    w_menu_zero = http_req("/api/waiter/menu", method="GET", token=waiter_token)
    idly_zero = next(m for m in w_menu_zero.get("menu", []) if m["MenuItemID"] == 9)
    assert idly_zero["StockQuantity"] == 0 and idly_zero["IsAvailable"] == 0
    print(f"  [OK] Stock set to 0: Dish automatically marked OUT OF STOCK on waiter menu.")

    # Waiter order attempt on 0 stock rejected
    zero_attempt = http_req(f"/api/waiter/orders/{new_order_id}/items", method="POST", data={"menu_item_id": 9, "quantity": 1}, token=waiter_token)
    assert zero_attempt.get("error") == True and zero_attempt.get("status") == 400
    print(f"  [OK] Waiter ordering rejected when stock is 0: {zero_attempt['detail']}")

    # Chef replenishes stock back to 10
    chef_replenish = http_req("/api/chef/menu/9/stock", method="PUT", data={"stock_quantity": 10}, token=chef_token)
    assert chef_replenish.get("is_available") == True
    print(f"  [OK] Chef replenished stock to 10 portions: Dish restored to available.")

    # 6. Checkout & Payment Splits
    print("\n[STEP 6] Testing Order Checkout & Payment Split Allocation...")
    bill_total = ord_res["total_estimate"] + 70.00
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
    assert len(v2['view_data']) > 0
    assert "CulinaryPerformancePoints" in v2['view_data'][0], "CulinaryPerformancePoints must be present in View_Chef_Performance"
    assert "TotalRedos" not in v2['view_data'][0], "TotalRedos must not be in View_Chef_Performance"
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
    # 10. Waiter Cancellation Endpoints & Selective Waste Log Verification
    print("\n[STEP 10] Testing Waiter Cancellation Endpoints & Waste Log Rules via HTTP API...")
    # 10a: Single dish cancellation before cooking (Pending) -> NO waste log
    w_order_1 = http_req("/api/waiter/orders", method="POST", data={
        "customer_count": 2,
        "table_numbers": [4],
        "items": [
            {"MenuItemID": 1, "Quantity": 1},  # Dish 1 (Pending)
            {"MenuItemID": 2, "Quantity": 1}   # Dish 2 (Cooking)
        ]
    }, token=waiter_token)
    w_order_1_id = w_order_1["order_id"]
    w_d1_id = w_order_1["items"][0]["OrderDetailID"]
    w_d2_id = w_order_1["items"][1]["OrderDetailID"]

    # Cancel Dish 1 while still Pending
    c_pend_api = http_req(f"/api/waiter/order-details/{w_d1_id}/cancel", method="POST", data={"reason": "Customer changed mind"}, token=waiter_token)
    assert c_pend_api["status"] == "success"
    assert c_pend_api["logged_to_waste"] is False
    assert c_pend_api["waste_id"] is None
    print(f"  [OK] Waiter cancelled dish before cooking (Pending): {c_pend_api['message']}")

    # Advance Dish 2 to Cooking via Chef
    http_req(f"/api/chef/order-details/{w_d2_id}/status", method="PUT", data={"new_status": "Cooking"}, token=chef_token)

    # Cancel Dish 2 while Cooking -> MUST log to Waste_Log
    c_cook_api = http_req(f"/api/waiter/order-details/{w_d2_id}/cancel", method="POST", data={"reason": "Customer cancelled during cooking"}, token=waiter_token)
    assert c_cook_api["status"] == "success"
    assert c_cook_api["logged_to_waste"] is True
    assert c_cook_api["waste_id"] is not None
    assert c_cook_api["order_cancelled"] is True  # All dishes cancelled -> order auto-closed
    print(f"  [OK] Waiter cancelled dish during cooking (Cooking): {c_cook_api['message']}")

    # 10b: Entire order cancellation with mixed dishes
    w_order_2 = http_req("/api/waiter/orders", method="POST", data={
        "customer_count": 3,
        "table_numbers": [6],
        "items": [
            {"MenuItemID": 1, "Quantity": 1},  # Mix 1 (Pending - before cooking)
            {"MenuItemID": 2, "Quantity": 1},  # Mix 2 (Cooking - during cooking)
            {"MenuItemID": 9, "Quantity": 1}   # Mix 3 (Ready - after cooking)
        ]
    }, token=waiter_token)
    assert "order_id" in w_order_2, f"Failed to create w_order_2: {w_order_2}"
    w_order_2_id = w_order_2["order_id"]
    m_d1 = w_order_2["items"][0]["OrderDetailID"]
    m_d2 = w_order_2["items"][1]["OrderDetailID"]
    m_d3 = w_order_2["items"][2]["OrderDetailID"]

    # Set statuses
    http_req(f"/api/chef/order-details/{m_d2}/status", method="PUT", data={"new_status": "Cooking"}, token=chef_token)
    http_req(f"/api/chef/order-details/{m_d3}/status", method="PUT", data={"new_status": "Ready"}, token=chef_token)

    # Cancel entire order via Waiter
    cancel_ord_api = http_req(f"/api/waiter/orders/{w_order_2_id}/cancel", method="POST", data={"reason": "Customer left abruptly"}, token=waiter_token)
    assert cancel_ord_api["status"] == "success"
    assert cancel_ord_api["order_status"] == "Cancelled"
    assert len(cancel_ord_api["wasted_items"]) == 2  # Cooking + Ready
    assert len(cancel_ord_api["non_wasted_items"]) == 1  # Pending
    assert 6 in cancel_ord_api["freed_tables"]
    print(f"  [OK] Entire order cancellation via API verified: {cancel_ord_api['message']}")

    # 10c: Partial quantity cancellation (e.g. 15 biriyanis -> cancel 1, 14 remain, only 1 logged to waste)
    w_order_3 = http_req("/api/waiter/orders", method="POST", data={
        "customer_count": 5,
        "table_numbers": [7],
        "items": [
            {"MenuItemID": 7, "Quantity": 15}  # 15 Biriyanis
        ]
    }, token=waiter_token)
    assert "order_id" in w_order_3
    w_d3_id = w_order_3["items"][0]["OrderDetailID"]

    # Start cooking
    http_req(f"/api/chef/order-details/{w_d3_id}/status", method="PUT", data={"new_status": "Cooking"}, token=chef_token)

    # Cancel only 1 portion
    c_part_api = http_req(f"/api/waiter/order-details/{w_d3_id}/cancel", method="POST", data={
        "reason": "Customer cancelled 1 biriyani out of 15",
        "cancel_quantity": 1
    }, token=waiter_token)
    assert c_part_api["status"] == "success"
    assert c_part_api["cancelled_quantity"] == 1
    assert c_part_api["remaining_quantity"] == 14
    assert c_part_api["logged_to_waste"] is True
    assert c_part_api["ingredient_cost"] == round(290.00 * 0.80, 2)
    print(f"  [OK] Partial cancellation via API: Cancelled 1 of 15 Biriyanis while Cooking; 14 remain Cooking; Rs {c_part_api['ingredient_cost']} logged to waste.")

    # Check Kitchen Manager Waste Log to verify entries
    km_waste = http_req("/api/kitchen/waste-log", token=mgr_token)
    assert "waste_logs" in km_waste and len(km_waste["waste_logs"]) >= 4
    print(f"  [OK] Kitchen Manager Discarded Food & Waste Log reflects waste records (Total Loss: Rs.{km_waste['total_waste_loss']}).")

    # 10d: Verify Shop Manager Expenses list and Profit/Loss includes 'wastelog'
    mgr_exp_res = http_req("/api/manager/expenses", token=mgr_token)
    assert "expenses" in mgr_exp_res
    wastelog_expenses = [e for e in mgr_exp_res["expenses"] if e.get("Description") == "wastelog"]
    assert len(wastelog_expenses) >= 4, f"Expected wastelog expenses in Shop Manager expenses list, found {len(wastelog_expenses)}"
    print(f"  [OK] Shop Manager expenses list includes {len(wastelog_expenses)} entries with description 'wastelog'.")

    # Verify Shop Manager Overview KPI reflects expenses & net profit/loss
    overview_res = http_req("/api/manager/overview", token=mgr_token)
    kpi = overview_res.get("kpi", {})
    assert kpi.get("total_expenses", 0) > 0
    print(f"  [OK] Shop Manager Dashboard calculates Profit/Loss with wastelog outlays included: Total Expenses Rs.{kpi['total_expenses']}, Net P&L Rs.{kpi['net_profit_loss']}.")

    print("\n" + "=" * 70)
    print("ALL LIVE END-TO-END WORKFLOWS & CONSTRAINTS VALIDATED WITH 100% SUCCESS!")
    print("=" * 70)


if __name__ == "__main__":
    run_e2e_test()
