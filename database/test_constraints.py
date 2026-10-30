"""
Integrity & Constraint Verification Suite
=========================================
Tests Edgar F. Codd's 3NF normalization, Ferraiolo & Kuhn's RBAC,
Jim Gray's ACID transactions, and anti-fraud SQL constraints.
"""

import sys
import os
import sqlite3

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import (
    init_db, get_connection, transaction,
    execute_handover_protocol, out_of_stock_atomic_transaction,
    create_order_with_tables_and_items, add_item_to_order, chef_review_cancel_consent,
    checkout_order, submit_order_feedback,
    waiter_cancel_order_item, waiter_cancel_order, update_menu_item_stock
)


def run_tests():
    print("=" * 70)
    print("RUNNING RESTAURANT DBMS CONSTRAINTS & ACID VERIFICATION SUITE")
    print("=" * 70)

    # Step 1: Initialize database
    print("\n[TEST 1] Initializing SQLite database and loading 3NF schema...")
    init_db(force_reset=True)
    conn = get_connection()
    cursor = conn.cursor()

    # Step 2: Verify all 14 tables
    expected_tables = [
        "Roles", "Staff", "Users", "Menu_Items", "Inventory",
        "Shortage_Logs", "Menu_Requests", "Tables", "Orders",
        "Order_Tables", "Order_Details", "Feedback", "Waste_Log", "Purchase_Expenses"
    ]
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    existing_tables = [r["name"] for r in cursor.fetchall()]
    print(f"Found {len(existing_tables)} tables in database.")
    for tbl in expected_tables:
        assert tbl in existing_tables, f"Missing table: {tbl}"
        cursor.execute(f"SELECT COUNT(*) AS cnt FROM {tbl};")
        cnt = cursor.fetchone()["cnt"]
        print(f"  [OK] Table '{tbl}': {cnt} initial rows")

    # Check 3NF schema enhancements (Staff.RoleID and Order_Details.UnitPrice)
    cursor.execute("PRAGMA table_info(Staff);")
    staff_cols = [c["name"] for c in cursor.fetchall()]
    assert "RoleID" in staff_cols, "Staff table must contain RoleID foreign key!"

    cursor.execute("PRAGMA table_info(Order_Details);")
    od_cols = [c["name"] for c in cursor.fetchall()]
    assert "UnitPrice" in od_cols, "Order_Details table must contain UnitPrice snapshot column!"

    cursor.execute("PRAGMA table_info(Menu_Items);")
    menu_cols = [c["name"] for c in cursor.fetchall()]
    assert "StockQuantity" in menu_cols, "Menu_Items table must contain StockQuantity column!"
    print("  [OK] 3NF & Dynamic Stock Columns Verified: Staff.RoleID, Order_Details.UnitPrice, Menu_Items.StockQuantity.")
    print("[OK] TEST 1 PASSED: All 14 Core and Bridge Tables Successfully Created.")

    # Step 3: Verify the 4 Automated SQL Views
    print("\n[TEST 2] Verifying the 4 Automated Business Intelligence SQL Views...")
    views = [
        ("View_Waiter_Performance", ["WaiterID", "WaiterName", "TotalCustomersHandled", "AvgServiceRating", "TotalPerformancePoints"]),
        ("View_Chef_Performance", ["ChefID", "ChefName", "TotalDishesPrepared", "AvgFoodRating", "CulinaryPerformancePoints"]),
        ("View_Daily_Waiter_Collections", ["WaiterID", "WaiterName", "CollectionDate", "TotalCashCollected", "TotalUPICollected", "TotalShiftCollection"]),
        ("View_Monthly_Profit_Loss", ["ReportingMonth", "TotalIncomingRevenue", "TotalOutgoingExpenses", "NetProfitLoss", "ProfitPercentage", "ProfitMarginPercentage"])
    ]
    for view_name, cols in views:
        cursor.execute(f"SELECT * FROM {view_name};")
        rows = cursor.fetchall()
        print(f"  [OK] View '{view_name}': {len(rows)} records returned")
        if rows:
            first = rows[0]
            for c in cols:
                assert c in first.keys(), f"Column '{c}' missing in view '{view_name}'"
            print(f"    Sample row: {dict(first)}")
    print("[OK] TEST 2 PASSED: All 4 SQL Business Intelligence Views Function Correctly.")

    # Step 4: Verify Anti-Fraud Feedback Gatekeeper Constraint
    print("\n[TEST 3] Testing Anti-Fraud Feedback SQL Gatekeeper Constraint...")
    # Attempt 3a: Fraudulent submission (Rating provided, but CustomerName and Phone are NULL)
    fraud_caught = False
    try:
        # Create a dummy completed order first
        cursor.execute("INSERT INTO Orders (WaiterID, CustomerCount, CashAmount, UPIAmount, OrderStatus) VALUES (5, 2, 200, 0, 'Completed');")
        fraud_order_id = cursor.lastrowid
        conn.commit()

        # Direct SQL insert violating check constraint
        cursor.execute("""
            INSERT INTO Feedback (OrderID, CustomerName, PhoneNumber, ServiceRating)
            VALUES (?, NULL, NULL, 5);
        """, (fraud_order_id,))
        conn.commit()
    except sqlite3.IntegrityError as e:
        fraud_caught = True
        conn.rollback()
        print(f"  [OK] Anti-Fraud constraint triggered on fraudulent padded review: {e}")

    assert fraud_caught, "FAIL: Anti-Fraud Gatekeeper constraint failed to catch NULL customer name/phone with rating!"

    # Attempt 3b: Legitimate feedback submission
    submit_order_feedback(
        order_id=fraud_order_id,
        customer_name="Rohan Verma",
        phone_number="9988776655",
        service_rating=5,
        food_rating=5,
        ambience_rating=4,
        cleanliness_rating=5,
        review_text="Prompt and hygienic dining."
    )
    print("  [OK] Legitimate feedback with verified phone and name successfully recorded.")
    print("[OK] TEST 3 PASSED: Anti-Fraud Feedback Gatekeeper Physically Prevents Data Padding.")

    # Step 5: Verify Multi-Table Concurrent Order Execution
    print("\n[TEST 4] Testing Multi-Table Association & Bridge Tables...")
    res = create_order_with_tables_and_items(
        waiter_id=5,
        customer_count=8,
        table_numbers=[1, 2],
        items=[
            {"MenuItemID": 1, "Quantity": 2}, # Masala Dosa -> Chef Vikram (3)
            {"MenuItemID": 4, "Quantity": 2}  # Chicken Biryani -> Chef Meera (4)
        ]
    )
    new_order_id = res["order_id"]
    print(f"  [OK] Multi-table order #{new_order_id} created with Tables {res['tables']} and {len(res['items'])} dishes.")

    # Verify bridge tables
    cursor.execute("SELECT * FROM Order_Tables WHERE OrderID = ?;", (new_order_id,))
    ot_rows = cursor.fetchall()
    assert len(ot_rows) == 2, f"Expected 2 rows in Order_Tables, found {len(ot_rows)}"

    cursor.execute("SELECT * FROM Order_Details WHERE OrderID = ?;", (new_order_id,))
    od_rows = cursor.fetchall()
    assert len(od_rows) == 2, f"Expected 2 rows in Order_Details, found {len(od_rows)}"
    print(f"  [OK] Bridge tables Order_Tables ({len(ot_rows)} rows) and Order_Details ({len(od_rows)} rows) verified.")
    print("[OK] TEST 4 PASSED: Multi-Table M:N Bridge Architecture Operational.")

    # Step 6: Verify Chef Cancellation-Consent Flow
    print("\n[TEST 5] Testing Chef Deletion-Consent Flow & Waste Logging...")
    cancel_od_id = od_rows[0]["OrderDetailID"]
    # Waiter flags cancel requested
    cursor.execute("UPDATE Order_Details SET ItemStatus = 'Cancel Requested' WHERE OrderDetailID = ?;", (cancel_od_id,))
    conn.commit()

    # Chef approves cancel (food not started)
    consent_res = chef_review_cancel_consent(cancel_od_id, approved=True)
    assert consent_res["new_status"] == 'Cancelled'
    assert consent_res["waste_id"] is not None
    print(f"  [OK] Chef approved cancellation: {consent_res['message']}")

    # Verify Waste_Log entry
    cursor.execute("SELECT * FROM Waste_Log WHERE OrderDetailID = ?;", (cancel_od_id,))
    waste_entry = cursor.fetchone()
    assert waste_entry is not None
    print(f"  [OK] Discard successfully logged in Waste_Log: WasteID {waste_entry['WasteID']}, Cost Rs {waste_entry['IngredientCost']}")
    print("[OK] TEST 5 PASSED: Chef Cancellation Consent Flow & Waste Auditing Operational.")

    # Step 6b: Verify Partial Dish Cancellation & Selective Waste Logging
    print("\n[TEST 5B] Testing Partial Dish Cancellation & Waste Log Isolation (e.g. 1 of 15 Biriyanis)...")
    
    # 1. Test partial cancellation during cooking (15 biriyanis -> cancel 1, 14 continue cooking, only 1 logged to waste)
    cursor.execute("""
        INSERT INTO Orders (WaiterID, CustomerCount, CashAmount, UPIAmount, OrderStatus)
        VALUES (5, 4, 0, 0, 'In Progress');
    """)
    partial_order_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO Order_Details (OrderID, MenuItemID, Quantity, UnitPrice, Subtotal, PreparedBy_EmployeeID, ItemStatus)
        VALUES (?, 7, 15, 290.00, 4350.00, 4, 'Cooking');
    """, (partial_order_id,))
    partial_cooking_od_id = cursor.lastrowid
    conn.commit()

    # Waiter cancels 1 portion out of 15
    partial_cancel_res = waiter_cancel_order_item(partial_cooking_od_id, reason="Customer cancelled 1 biriyani", waiter_id=5, cancel_quantity=1)
    assert partial_cancel_res["status"] == "success"
    assert partial_cancel_res["cancelled_quantity"] == 1
    assert partial_cancel_res["remaining_quantity"] == 14
    assert partial_cancel_res["logged_to_waste"] is True
    expected_single_waste = round(290.00 * 0.80, 2)
    assert partial_cancel_res["ingredient_cost"] == expected_single_waste

    # Verify original order detail was updated to 14 portions
    cursor.execute("SELECT Quantity, Subtotal, ItemStatus FROM Order_Details WHERE OrderDetailID = ?;", (partial_cooking_od_id,))
    rem_od = cursor.fetchone()
    assert rem_od["Quantity"] == 14
    assert rem_od["Subtotal"] == 4060.00
    assert rem_od["ItemStatus"] == "Cooking"

    # Verify new cancelled order detail was created for 1 portion
    cursor.execute("SELECT OrderDetailID, Quantity, Subtotal, ItemStatus, CancellationReason FROM Order_Details WHERE OrderDetailID = ?;", (partial_cancel_res["cancelled_detail_id"],))
    canc_od = cursor.fetchone()
    assert canc_od["Quantity"] == 1
    assert canc_od["Subtotal"] == 290.00
    assert canc_od["ItemStatus"] == "Cancelled"

    # Verify Waste_Log contains ONLY the 1 cancelled biriyani
    cursor.execute("SELECT * FROM Waste_Log WHERE WasteID = ?;", (partial_cancel_res["waste_id"],))
    waste_entry = cursor.fetchone()
    assert waste_entry is not None
    assert waste_entry["OrderDetailID"] == partial_cancel_res["cancelled_detail_id"]
    assert waste_entry["IngredientCost"] == expected_single_waste
    print(f"  [OK] During Cooking: Cancelled 1 of 15 Biriyanis. 14 remain Cooking. Waste Log: Rs {waste_entry['IngredientCost']}")

    # 2. Test partial cancellation before cooking (5 Idlys in Pending -> cancel 2, 3 remain, 2 restored to stock, 0 waste)
    cursor.execute("SELECT StockQuantity FROM Menu_Items WHERE MenuItemID = 1;")
    stock_before = cursor.fetchone()["StockQuantity"]
    cursor.execute("""
        INSERT INTO Order_Details (OrderID, MenuItemID, Quantity, UnitPrice, Subtotal, PreparedBy_EmployeeID, ItemStatus)
        VALUES (?, 1, 5, 50.00, 250.00, 3, 'Pending');
    """, (partial_order_id,))
    partial_pending_od_id = cursor.lastrowid
    conn.commit()

    partial_pending_cancel_res = waiter_cancel_order_item(partial_pending_od_id, reason="Customer cancelled 2 idlys", waiter_id=5, cancel_quantity=2)
    assert partial_pending_cancel_res["status"] == "success"
    assert partial_pending_cancel_res["cancelled_quantity"] == 2
    assert partial_pending_cancel_res["remaining_quantity"] == 3
    assert partial_pending_cancel_res["logged_to_waste"] is False

    cursor.execute("SELECT StockQuantity FROM Menu_Items WHERE MenuItemID = 1;")
    stock_after = cursor.fetchone()["StockQuantity"]
    assert stock_after == stock_before + 2, f"Expected stock {stock_before + 2}, got {stock_after}"
    print(f"  [OK] Before Cooking: Cancelled 2 of 5 Idlys. 3 remain Pending. Stock restored by +2. No waste logged.")
    print("[OK] TEST 5B PASSED: Partial Dish Cancellation & Selective Waste Logging Fully Verified.")

    # Step 6c: Verify Waiter Cancel Options (Individual Dish & Entire Order with Waste Log Rules)
    print("\n[TEST 5C] Testing Waiter Cancellation Options & Waste Log Invariants...")
    # Setup test order for Waiter cancellation checks
    waiter_test_order = create_order_with_tables_and_items(
        waiter_id=5,
        customer_count=3,
        table_numbers=[4],
        items=[
            {"MenuItemID": 1, "Quantity": 1},  # Dish A (Pending -> Cancelled, NO waste)
            {"MenuItemID": 2, "Quantity": 1},  # Dish B (Cooking -> Cancelled, WITH waste)
            {"MenuItemID": 3, "Quantity": 1}   # Dish C (Ready -> Cancelled, WITH waste)
        ]
    )
    w_ord_id = waiter_test_order["order_id"]
    cursor.execute("SELECT OrderDetailID, ItemStatus FROM Order_Details WHERE OrderID = ? ORDER BY OrderDetailID;", (w_ord_id,))
    w_details = cursor.fetchall()
    d_pending_id = w_details[0]["OrderDetailID"]
    d_cooking_id = w_details[1]["OrderDetailID"]
    d_ready_id = w_details[2]["OrderDetailID"]

    # 1. Waiter cancels Dish A BEFORE cooking (Pending)
    cancel_pending_res = waiter_cancel_order_item(d_pending_id, reason="Customer changed mind before preparation")
    assert cancel_pending_res["status"] == "success"
    assert cancel_pending_res["logged_to_waste"] is False
    assert cancel_pending_res["waste_id"] is None
    # Verify no Waste_Log entry exists for this detail
    cursor.execute("SELECT COUNT(*) AS cnt FROM Waste_Log WHERE OrderDetailID = ?;", (d_pending_id,))
    assert cursor.fetchone()["cnt"] == 0, "FAIL: Dish cancelled before cooking was logged to Waste_Log!"
    print("  [OK] Item cancelled before cooking (Pending): ItemStatus = 'Cancelled', NOT logged to Waste_Log.")

    # 2. Waiter cancels Dish B DURING cooking (Cooking)
    cursor.execute("UPDATE Order_Details SET ItemStatus = 'Cooking' WHERE OrderDetailID = ?;", (d_cooking_id,))
    conn.commit()
    cancel_cooking_res = waiter_cancel_order_item(d_cooking_id, reason="Customer cancelled while cooking")
    assert cancel_cooking_res["status"] == "success"
    assert cancel_cooking_res["logged_to_waste"] is True
    assert cancel_cooking_res["waste_id"] is not None
    # Verify Waste_Log entry exists
    cursor.execute("SELECT * FROM Waste_Log WHERE WasteID = ?;", (cancel_cooking_res["waste_id"],))
    w_entry = cursor.fetchone()
    assert w_entry is not None and w_entry["OrderDetailID"] == d_cooking_id
    assert w_entry["IngredientCost"] > 0
    print(f"  [OK] Item cancelled during cooking (Cooking): ItemStatus = 'Cancelled', logged to Waste_Log (Cost Rs.{w_entry['IngredientCost']}).")

    # 3. Setup fresh order with mixed dishes to verify ENTIRE ORDER CANCELLATION
    mix_order = create_order_with_tables_and_items(
        waiter_id=5,
        customer_count=4,
        table_numbers=[6, 8],
        items=[
            {"MenuItemID": 1, "Quantity": 1},  # Mix Dish 1: Before cooking (Pending)
            {"MenuItemID": 2, "Quantity": 1},  # Mix Dish 2: During cooking (Cooking)
            {"MenuItemID": 3, "Quantity": 1}   # Mix Dish 3: After cooking (Ready)
        ]
    )
    mix_ord_id = mix_order["order_id"]
    cursor.execute("SELECT OrderDetailID FROM Order_Details WHERE OrderID = ? ORDER BY OrderDetailID;", (mix_ord_id,))
    mix_details = [r["OrderDetailID"] for r in cursor.fetchall()]
    mix_pending_id, mix_cooking_id, mix_ready_id = mix_details

    # Set statuses
    cursor.execute("UPDATE Order_Details SET ItemStatus = 'Cooking' WHERE OrderDetailID = ?;", (mix_cooking_id,))
    cursor.execute("UPDATE Order_Details SET ItemStatus = 'Ready' WHERE OrderDetailID = ?;", (mix_ready_id,))
    conn.commit()

    # Cancel entire order
    cancel_entire_res = waiter_cancel_order(mix_ord_id, reason="Emergency table departure")
    assert cancel_entire_res["status"] == "success"
    assert cancel_entire_res["order_status"] == "Cancelled"
    assert len(cancel_entire_res["wasted_items"]) == 2, f"Expected 2 wasted items, got {len(cancel_entire_res['wasted_items'])}"
    assert len(cancel_entire_res["non_wasted_items"]) == 1, f"Expected 1 non-wasted item, got {len(cancel_entire_res['non_wasted_items'])}"

    # Verify database state
    cursor.execute("SELECT OrderStatus FROM Orders WHERE OrderID = ?;", (mix_ord_id,))
    assert cursor.fetchone()["OrderStatus"] == "Cancelled"

    # Verify tables 6 & 8 are freed back to Available
    cursor.execute("SELECT TableNumber, CurrentStatus FROM Tables WHERE TableNumber IN (6, 8);")
    for tbl in cursor.fetchall():
        assert tbl["CurrentStatus"] == "Available", f"Table {tbl['TableNumber']} status was {tbl['CurrentStatus']}, expected Available"

    # Verify Waste_Log for the entire order dishes:
    # Pending dish must NOT be in Waste_Log
    cursor.execute("SELECT COUNT(*) AS cnt FROM Waste_Log WHERE OrderDetailID = ?;", (mix_pending_id,))
    assert cursor.fetchone()["cnt"] == 0, "FAIL: Pending dish in cancelled order was logged to Waste_Log!"

    # Cooking dish MUST be in Waste_Log
    cursor.execute("SELECT COUNT(*) AS cnt FROM Waste_Log WHERE OrderDetailID = ?;", (mix_cooking_id,))
    assert cursor.fetchone()["cnt"] == 1, "FAIL: Cooking dish in cancelled order was NOT logged to Waste_Log!"

    # Ready dish MUST be in Waste_Log
    cursor.execute("SELECT COUNT(*) AS cnt FROM Waste_Log WHERE OrderDetailID = ?;", (mix_ready_id,))
    assert cursor.fetchone()["cnt"] == 1, "FAIL: Ready dish in cancelled order was NOT logged to Waste_Log!"

    print(f"  [OK] Entire order cancellation verified: Order #{mix_ord_id} Cancelled, Tables freed.")
    print(f"  [OK] Waste log selective routing confirmed: Dishes during/after cooking (Cooking, Ready) alone logged to Waste_Log; before cooking (Pending) excluded.")
    print("[OK] TEST 5C PASSED: Waiter Cancellation Architecture & Waste Log Invariants Fully Verified.")

    # Step 6d: Verify Waste Log Synchronization with Purchase_Expenses (description = 'wastelog')
    print("\n[TEST 5D] Testing Automated Waste Log to Expenses List Synchronization...")
    cursor.execute("SELECT * FROM Purchase_Expenses WHERE Description = 'wastelog' ORDER BY ExpenseID DESC;")
    waste_expenses = cursor.fetchall()
    assert len(waste_expenses) >= 3, f"Expected at least 3 wastelog expenses, found {len(waste_expenses)}"
    for we in waste_expenses:
        assert we["Description"] == "wastelog"
        assert we["ExpenseAmount"] > 0
        assert we["ExpenseType"] == "Raw Materials"
    print(f"  [OK] Found {len(waste_expenses)} synchronized wastelog records in Purchase_Expenses with description 'wastelog'.")

    # Verify that total expenses for calculating profit/loss includes these wastelog amounts
    cursor.execute("SELECT SUM(ExpenseAmount) as TotalAllExpenses FROM Purchase_Expenses;")
    total_all_exp = cursor.fetchone()["TotalAllExpenses"]
    cursor.execute("SELECT SUM(ExpenseAmount) as WasteExpenses FROM Purchase_Expenses WHERE Description = 'wastelog';")
    total_waste_exp = cursor.fetchone()["WasteExpenses"]
    cursor.execute("SELECT SUM(IngredientCost) as TotalWasteLogCost FROM Waste_Log WHERE IngredientCost > 0;")
    total_wl_cost = cursor.fetchone()["TotalWasteLogCost"]
    assert abs(total_waste_exp - total_wl_cost) < 0.01, f"Mismatch: Waste expenses Rs {total_waste_exp} != Waste Log Rs {total_wl_cost}"
    print(f"  [OK] Profit/Loss expense total (Rs {total_all_exp:.2f}) seamlessly incorporates wastelog loss of Rs {total_waste_exp:.2f}.")
    print("[OK] TEST 5D PASSED: Waste Log Amount Added into Expenses List with Description 'wastelog'.")

    # Step 7: Verify Pre-Cooking Edit Block Database Trigger
    print("\n[TEST 6] Testing Pre-Cooking Edit Block Database Trigger...")
    cursor.execute("INSERT INTO Orders (WaiterID, CustomerCount, CashAmount, UPIAmount, OrderStatus) VALUES (5, 1, 0, 0, 'In Progress');")
    trigger_test_order_id = cursor.lastrowid

    # Attempt 6a: Waiter attempts direct DELETE on an item that has moved past 'Pending' (e.g. 'Cooking')
    cursor.execute("""
        INSERT INTO Order_Details (OrderID, MenuItemID, Quantity, UnitPrice, Subtotal, PreparedBy_EmployeeID, ItemStatus)
        VALUES (?, 1, 1, 130.00, 130.00, 3, 'Cooking');
    """, (trigger_test_order_id,))
    cooking_od_id = cursor.lastrowid
    conn.commit()

    delete_blocked = False
    try:
        cursor.execute("DELETE FROM Order_Details WHERE OrderDetailID = ?;", (cooking_od_id,))
        conn.commit()
    except sqlite3.DatabaseError as e:
        delete_blocked = True
        conn.rollback()
        print(f"  [OK] Database trigger blocked direct DELETE on 'Cooking' item: {e}")
    assert delete_blocked, "FAIL: Database trigger allowed deleting an item in 'Cooking' status!"

    # Attempt 6b: Waiter attempts direct UPDATE of quantity on an item in 'Cooking' status
    update_blocked = False
    try:
        cursor.execute("UPDATE Order_Details SET Quantity = 5 WHERE OrderDetailID = ?;", (cooking_od_id,))
        conn.commit()
    except sqlite3.DatabaseError as e:
        update_blocked = True
        conn.rollback()
        print(f"  [OK] Database trigger blocked direct UPDATE of quantity on 'Cooking' item: {e}")
    assert update_blocked, "FAIL: Database trigger allowed modifying quantity on an item in 'Cooking' status!"

    # Attempt 6c: Deleting a 'Pending' item succeeds
    cursor.execute("""
        INSERT INTO Order_Details (OrderID, MenuItemID, Quantity, UnitPrice, Subtotal, PreparedBy_EmployeeID, ItemStatus)
        VALUES (?, 1, 1, 130.00, 130.00, 3, 'Pending');
    """, (trigger_test_order_id,))
    pending_od_id = cursor.lastrowid
    conn.commit()
    cursor.execute("DELETE FROM Order_Details WHERE OrderDetailID = ?;", (pending_od_id,))
    conn.commit()
    print("  [OK] Deleting 'Pending' item succeeded before kitchen processing.")
    print("[OK] TEST 6 PASSED: Pre-Cooking Edit Block Database Trigger Enforces Kitchen Isolation.")

    # Step 8: Verify Out-of-Stock Atomic Transaction
    print("\n[TEST 7] Testing Out-of-Stock Atomic Transaction...")
    oos_res = out_of_stock_atomic_transaction(
        menu_item_id=3,
        chef_id=3,
        shortage_reason="Urad dal supplies exhausted in morning rush"
    )
    # Verify Menu_Items updated
    cursor.execute("SELECT IsAvailable, StockQuantity FROM Menu_Items WHERE MenuItemID = 3;")
    item3 = cursor.fetchone()
    assert item3["IsAvailable"] == 0
    assert item3["StockQuantity"] == 0
    # Verify Shortage_Logs updated
    cursor.execute("SELECT * FROM Shortage_Logs WHERE MenuItemID = 3 AND ChefID = 3;")
    s_log = cursor.fetchone()
    assert s_log is not None
    print(f"  [OK] Dish #{oos_res['menu_item_id']} ({oos_res['item_name']}) set offline and logged in Shortage_Logs: '{s_log['Reason']}'")
    print("[OK] TEST 7 PASSED: Out-of-Stock Atomic Transaction Verified.")

    # Step 8B: Verify Dynamic Portion Stock Tracking & Auto-OOS Thresholds
    print("\n[TEST 7B] Testing Dynamic Portion Stock Tracking, Auto-OOS, and Chef Replenishment...")
    # 1. Verify Steamed Idly initial stock
    cursor.execute("SELECT MenuItemID, ItemName, StockQuantity, IsAvailable FROM Menu_Items WHERE MenuItemID = 9;")
    idly_item = cursor.fetchone()
    assert idly_item is not None, "Steamed Idly (MenuItemID 9) must exist in seed data"
    assert idly_item["StockQuantity"] == 10, f"Expected 10 idlys in stock, got {idly_item['StockQuantity']}"
    assert idly_item["IsAvailable"] == 1, "Expected idly to be available initially"
    print(f"  [OK] Initial stock verified: '{idly_item['ItemName']}' has {idly_item['StockQuantity']} portions in stock (Available: {bool(idly_item['IsAvailable'])}).")

    # 2. Waiter places order for 1 idly (10 -> 9)
    order_idly = create_order_with_tables_and_items(
        waiter_id=5,
        customer_count=2,
        table_numbers=[8],
        items=[{"MenuItemID": 9, "Quantity": 1}]
    )
    cursor.execute("SELECT StockQuantity, IsAvailable FROM Menu_Items WHERE MenuItemID = 9;")
    idly_stock_after_1 = cursor.fetchone()
    assert idly_stock_after_1["StockQuantity"] == 9, f"Expected 9 idlys left, got {idly_stock_after_1['StockQuantity']}"
    assert idly_stock_after_1["IsAvailable"] == 1
    print(f"  [OK] Waiter ordered 1 Idly: Stock atomically decremented 10 -> {idly_stock_after_1['StockQuantity']} (Available: True).")

    # 3. Waiter adds remaining 9 idlys to order (9 -> 0, auto transitions to OUT OF STOCK)
    add_item_to_order(order_id=order_idly["order_id"], menu_item_id=9, quantity=9)
    cursor.execute("SELECT StockQuantity, IsAvailable FROM Menu_Items WHERE MenuItemID = 9;")
    idly_stock_zero = cursor.fetchone()
    assert idly_stock_zero["StockQuantity"] == 0, f"Expected 0 idlys left, got {idly_stock_zero['StockQuantity']}"
    assert idly_stock_zero["IsAvailable"] == 0, "Expected dish to automatically transition to OUT OF STOCK (IsAvailable = 0)"
    print(f"  [OK] Remaining 9 Idlys ordered: Stock reached 0 -> Auto-transitioned to OUT OF STOCK (IsAvailable = {idly_stock_zero['IsAvailable']}).")

    # 4. Attempting to order when stock is 0 raises error
    try:
        add_item_to_order(order_id=order_idly["order_id"], menu_item_id=9, quantity=1)
        assert False, "Should have raised ValueError when ordering out-of-stock item"
    except ValueError as e:
        assert "OUT OF STOCK" in str(e)
        print(f"  [OK] Prevented order on 0 stock: '{e}'")

    # 5. Chef prepares fresh batch and replenishes stock in advance (0 -> 12)
    chef_update = update_menu_item_stock(menu_item_id=9, stock_quantity=12, chef_id=3)
    cursor.execute("SELECT StockQuantity, IsAvailable FROM Menu_Items WHERE MenuItemID = 9;")
    idly_replenished = cursor.fetchone()
    assert idly_replenished["StockQuantity"] == 12
    assert idly_replenished["IsAvailable"] == 1
    print(f"  [OK] Chef replenished stock in advance: {chef_update['message']}")

    # 6. Chef alters stock while already in stock (12 -> 15)
    chef_alter = update_menu_item_stock(menu_item_id=9, stock_quantity=15, chef_id=3)
    cursor.execute("SELECT StockQuantity, IsAvailable FROM Menu_Items WHERE MenuItemID = 9;")
    assert cursor.fetchone()["StockQuantity"] == 15
    print(f"  [OK] Chef altered in-stock quantity to 15 portions: {chef_alter['message']}")

    # 7. Attempting to order more portions than available stock raises error
    try:
        add_item_to_order(order_id=order_idly["order_id"], menu_item_id=9, quantity=20)
        assert False, "Should have raised ValueError when requesting quantity exceeding stock"
    except ValueError as e:
        assert "Insufficient stock" in str(e)
        print(f"  [OK] Prevented over-ordering portions: '{e}'")

    # 8. Waiter cancels the 1-idly item before cooking (Pending): stock recovers by +1 (15 -> 16)
    detail_1_idly = order_idly["items"][0]["OrderDetailID"]
    cancel_res = waiter_cancel_order_item(detail_1_idly, reason="Guest changed mind", waiter_id=5)
    cursor.execute("SELECT StockQuantity FROM Menu_Items WHERE MenuItemID = 9;")
    idly_stock_restored = cursor.fetchone()["StockQuantity"]
    assert idly_stock_restored == 16, f"Expected 16 idlys after pre-cooking cancellation, got {idly_stock_restored}"
    print(f"  [OK] Pre-cooking cancellation recovered portions to stock: 15 -> {idly_stock_restored} portions.")
    print("[OK] TEST 7B PASSED: Dynamic Portion Stock Tracking, Auto-OOS, and Chef Replenishment Fully Verified.")

    # Step 9: Verify Single-Seat Handover Protocol
    print("\n[TEST 8] Testing Single-Seat Handover Protocol (Kitchen Manager)...")
    # Verify current Kitchen Manager
    cursor.execute("SELECT u.UserID, u.Username, s.EmployeeID, s.Name, s.IsActive FROM Users u JOIN Staff s ON u.EmployeeID = s.EmployeeID WHERE u.RoleID = 2;")
    orig_km = cursor.fetchone()
    print(f"  Current active Kitchen Manager: {orig_km['Name']} (Username: {orig_km['Username']}, Staff ID: {orig_km['EmployeeID']})")

    handover_res = execute_handover_protocol(
        admin_role_name="Kitchen Manager",
        new_employee_name="Chef Sangeeta Balan",
        new_username="kitchenmgr_sangeeta",
        new_password_hash="$2b$12$newHashExampleStringForTestingHandoverProtocol123",
        shift="Morning Shift",
        salary=52000.00
    )
    print(f"  [OK] Handover Protocol executed: {handover_res['message']}")

    # Verify 1: Previous manager is soft-retired (IsActive = 0)
    cursor.execute("SELECT IsActive, Role FROM Staff WHERE EmployeeID = ?;", (orig_km["EmployeeID"],))
    retired_staff = cursor.fetchone()
    assert retired_staff["IsActive"] == 0, "Retired manager must have IsActive = 0"
    print(f"  [OK] Historical staff record preserved: {orig_km['Name']} IsActive = {retired_staff['IsActive']}")

    # Verify 2: Old user row is hard deleted from Users
    cursor.execute("SELECT * FROM Users WHERE UserID = ?;", (orig_km["UserID"],))
    assert cursor.fetchone() is None, "Old manager user credentials must be hard-deleted"
    print("  [OK] Old manager login credentials hard-deleted from Users table.")

    # Verify 3: Exactly 1 active user for Kitchen Manager (Single-Seat constraint)
    cursor.execute("SELECT COUNT(*) AS cnt FROM Users WHERE RoleID = 2;")
    km_count = cursor.fetchone()["cnt"]
    assert km_count == 1, f"Expected strictly 1 Kitchen Manager user, found {km_count}"
    print(f"  [OK] Strictly single-seat confirmed: Exactly {km_count} active account for Kitchen Manager.")
    print("[OK] TEST 8 PASSED: Single-Seat Handover Protocol Complies with Audit Requirements.")

    # Step 10: Verify Checkout and Payment Splits
    print("\n[TEST 9] Testing Order Checkout & Payment Splits...")
    checkout_res = checkout_order(order_id=new_order_id, cash_amount=300.00, upi_amount=400.00)
    print(f"  [OK] Checkout finalized: Bill Rs {checkout_res['bill_total']}, Cash Rs {checkout_res['cash_amount']}, UPI Rs {checkout_res['upi_amount']}")
    print(f"  [OK] Freed tables: {checkout_res['freed_tables']}")
    cursor.execute("SELECT OrderStatus FROM Orders WHERE OrderID = ?;", (new_order_id,))
    assert cursor.fetchone()["OrderStatus"] == 'Completed'
    print("[OK] TEST 9 PASSED: Checkout & Payment Splits Successfully Processed.")

    conn.close()
    print("\n" + "=" * 70)
    print("ALL 9 DBMS INTEGRITY & CONSTRAINTS TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
