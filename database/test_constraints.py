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
    create_order_with_tables_and_items, chef_review_cancel_consent,
    checkout_order, submit_order_feedback
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
    print("  [OK] 3NF Columns Verified: Staff.RoleID (FK) and Order_Details.UnitPrice (Snapshot).")
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
    cursor.execute("SELECT IsAvailable FROM Menu_Items WHERE MenuItemID = 3;")
    assert cursor.fetchone()["IsAvailable"] == 0
    # Verify Shortage_Logs updated
    cursor.execute("SELECT * FROM Shortage_Logs WHERE MenuItemID = 3 AND ChefID = 3;")
    s_log = cursor.fetchone()
    assert s_log is not None
    print(f"  [OK] Dish #{oos_res['menu_item_id']} ({oos_res['item_name']}) set offline and logged in Shortage_Logs: '{s_log['Reason']}'")
    print("[OK] TEST 7 PASSED: Out-of-Stock Atomic Transaction Verified.")

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
