"""
Database Connection & Transaction Management Layer
===================================================
Enforces:
  1. 3NF Relational Integrity & Foreign Key Cascades
  2. ACID Transaction Boundaries (Jim Gray)
  3. Single-Seat Administrative Handover Protocol
  4. Out-of-Stock Atomic Transactions
  5. Anti-Fraud SQL Gatekeeper Constraints
"""

import os
import sqlite3
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "restaurant.db")
SCHEMA_SQL_PATH = os.path.join(BASE_DIR, "database", "schema_sqlite.sql")
SEED_SQL_PATH = os.path.join(BASE_DIR, "database", "seed_data.sql")


def get_connection() -> sqlite3.Connection:
    """Creates a connection to SQLite with foreign keys and dict row factory enabled."""
    conn = sqlite3.connect(DB_PATH, timeout=20.0, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def transaction():
    """ACID Transaction context manager with automatic commit and rollback."""
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE;")
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_db(force_reset: bool = False):
    """Initializes the database schema and seeds initial data if not present."""
    if force_reset and os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except OSError:
            pass

    conn = get_connection()
    cursor = conn.cursor()

    # Check if Roles table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Roles';")
    exists = cursor.fetchone()

    if not exists or force_reset:
        print("[Database] Initializing 3NF schema...")
        with open(SCHEMA_SQL_PATH, "r", encoding="utf-8") as f:
            schema_script = f.read()
        conn.executescript(schema_script)

        print("[Database] Seeding initial dataset...")
        with open(SEED_SQL_PATH, "r", encoding="utf-8") as f:
            seed_script = f.read()
        conn.executescript(seed_script)
        conn.commit()
        print("[Database] Schema and seed data successfully loaded.")
    else:
        # Ensure views exist even on reconnect
        with open(SCHEMA_SQL_PATH, "r", encoding="utf-8") as f:
            schema_script = f.read()
        # Execute only CREATE VIEW statements
        view_statements = [stmt.strip() for stmt in schema_script.split(";") if "CREATE VIEW" in stmt or "DROP VIEW" in stmt]
        for stmt in view_statements:
            if stmt:
                conn.execute(stmt)
        conn.commit()

    # Ensure IsActive column exists on Menu_Items (dynamic schema migration support)
    cursor.execute("PRAGMA table_info(Menu_Items);")
    item_cols = [c["name"] for c in cursor.fetchall()]
    if "IsActive" not in item_cols:
        cursor.execute("ALTER TABLE Menu_Items ADD COLUMN IsActive INTEGER DEFAULT 1 NOT NULL CHECK (IsActive IN (0, 1));")
        conn.commit()

    # Ensure AssignedChefID column exists on Inventory (station-specific ingredient inventory)
    cursor.execute("PRAGMA table_info(Inventory);")
    inv_cols = [c["name"] for c in cursor.fetchall()]
    if "AssignedChefID" not in inv_cols:
        cursor.execute("ALTER TABLE Inventory ADD COLUMN AssignedChefID INTEGER REFERENCES Staff(EmployeeID);")
        # Backfill standard ingredients to specific chefs
        cursor.execute("UPDATE Inventory SET AssignedChefID = 3 WHERE IngredientID IN (1, 3, 5);")
        cursor.execute("UPDATE Inventory SET AssignedChefID = 4 WHERE IngredientID IN (2, 4, 6, 7);")
        conn.commit()
    # Ensure Description column exists on Purchase_Expenses (Itemized details & particulars)
    cursor.execute("PRAGMA table_info(Purchase_Expenses);")
    exp_cols = [c["name"] for c in cursor.fetchall()]
    if "Description" not in exp_cols:
        cursor.execute("ALTER TABLE Purchase_Expenses ADD COLUMN Description TEXT;")
        # Backfill meaningful descriptions for existing records
        cursor.execute("UPDATE Purchase_Expenses SET Description = 'Bulk Grains, Dosa Batter & Dairy Procurement' WHERE ExpenseID = 1;")
        cursor.execute("UPDATE Purchase_Expenses SET Description = 'September Month Staff Salary & Benefits Disbursement' WHERE ExpenseID = 2;")
        cursor.execute("UPDATE Purchase_Expenses SET Description = 'Commercial Induction Cooktops & Heavy Cookware' WHERE ExpenseID = 3;")
        cursor.execute("UPDATE Purchase_Expenses SET Description = 'Fresh Vegetables & Whole Spices Delivery' WHERE ExpenseID = 4;")
        cursor.execute("UPDATE Purchase_Expenses SET Description = 'Weekly Poultry & Dairy Farm Supplies' WHERE ExpenseID = 5;")
        cursor.execute("UPDATE Purchase_Expenses SET Description = 'October Month Staff Salary & Benefits Disbursement' WHERE ExpenseID = 6;")
        cursor.execute("UPDATE Purchase_Expenses SET Description = 'Bulk Basmati Rice & Desi Ghee Procurement' WHERE ExpenseID = 7;")
        cursor.execute("UPDATE Purchase_Expenses SET Description = 'Dining Furniture & Lighting Maintenance' WHERE ExpenseID = 8;")
        conn.commit()

    conn.close()


# =====================================================================
# Operational Workflows & Business Logic (ACID Transactions)
# =====================================================================

def execute_handover_protocol(
    admin_role_name: str,
    new_employee_name: str,
    new_username: str,
    new_password_hash: str,
    shift: str = "General Shift",
    salary: float = 55000.00
) -> Dict[str, Any]:
    """
    Single-Seat Handover Protocol (Page 3 of Constraints):
    1. Hard DELETE of specific row in Users matching administrative role.
    2. Soft-retire manager in Staff by setting IsActive = 0 (preserving audit footprints).
    3. INSERT incoming employee into Staff.
    4. INSERT new credentials into Users pointing to new EmployeeID and administrative RoleID.
    """
    if admin_role_name not in ('Shop Manager', 'Kitchen Manager'):
        raise ValueError("Single-seat handover is strictly restricted to Shop Manager or Kitchen Manager.")

    with transaction() as conn:
        cursor = conn.cursor()

        # Step 0: Find RoleID and current active manager
        cursor.execute("SELECT RoleID FROM Roles WHERE RoleName = ?;", (admin_role_name,))
        role_row = cursor.fetchone()
        if not role_row:
            raise ValueError(f"Role '{admin_role_name}' not found.")
        role_id = role_row["RoleID"]

        # Find current user for this role
        cursor.execute("""
            SELECT u.UserID, u.EmployeeID, s.Name 
            FROM Users u
            JOIN Staff s ON u.EmployeeID = s.EmployeeID
            WHERE u.RoleID = ?;
        """, (role_id,))
        current_user = cursor.fetchone()

        departing_name = None
        departing_emp_id = None

        if current_user:
            departing_emp_id = current_user["EmployeeID"]
            departing_name = current_user["Name"]

            # 1. Hard DELETE from Users
            cursor.execute("DELETE FROM Users WHERE UserID = ?;", (current_user["UserID"],))

            # 2. Soft-retire manager in Staff
            cursor.execute("UPDATE Staff SET IsActive = 0 WHERE EmployeeID = ?;", (departing_emp_id,))

        # 3. INSERT incoming employee into Staff
        cursor.execute("""
            INSERT INTO Staff (Name, RoleID, Role, Shift, IsActive, Salary)
            VALUES (?, ?, ?, ?, 1, ?);
        """, (new_employee_name, role_id, admin_role_name, shift, salary))
        new_employee_id = cursor.lastrowid

        # 4. INSERT new credentials into Users
        cursor.execute("""
            INSERT INTO Users (EmployeeID, Username, PasswordHash, RoleID)
            VALUES (?, ?, ?, ?);
        """, (new_employee_id, new_username, new_password_hash, role_id))
        new_user_id = cursor.lastrowid

        return {
            "status": "success",
            "message": f"Single-seat handover completed for {admin_role_name}",
            "retired_employee": {"EmployeeID": departing_emp_id, "Name": departing_name},
            "new_employee": {"EmployeeID": new_employee_id, "Name": new_employee_name},
            "new_user": {"UserID": new_user_id, "Username": new_username}
        }


def out_of_stock_atomic_transaction(menu_item_id: int, chef_id: int, shortage_reason: str) -> Dict[str, Any]:
    """
    4.3 Out-of-Stock Atomic Transaction (Page 6 of Constraints):
    BEGIN TRANSACTION;
    UPDATE Menu_Items SET IsAvailable = FALSE WHERE MenuItemID = :item_id;
    INSERT INTO Shortage_Logs (MenuItemID, ChefID, Reason) VALUES (:item_id, :chef_id, :shortage_reason);
    COMMIT;
    """
    with transaction() as conn:
        cursor = conn.cursor()

        # Check item exists
        cursor.execute("SELECT ItemName FROM Menu_Items WHERE MenuItemID = ?;", (menu_item_id,))
        item = cursor.fetchone()
        if not item:
            raise ValueError(f"MenuItemID {menu_item_id} not found.")

        cursor.execute("UPDATE Menu_Items SET IsAvailable = 0 WHERE MenuItemID = ?;", (menu_item_id,))
        cursor.execute("""
            INSERT INTO Shortage_Logs (MenuItemID, ChefID, Reason, LogTimestamp)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP);
        """, (menu_item_id, chef_id, shortage_reason))

        return {
            "status": "success",
            "menu_item_id": menu_item_id,
            "item_name": item["ItemName"],
            "reason": shortage_reason
        }


def create_order_with_tables_and_items(
    waiter_id: int,
    customer_count: int,
    table_numbers: List[int],
    items: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    4.1 Multi-Table & Concurrent Order Execution:
    Creates 1 Order record, N Order_Tables records, and M Order_Details records.
    Tables are marked as 'Occupied'.
    """
    if not table_numbers:
        raise ValueError("At least one table number must be assigned.")
    if customer_count <= 0:
        raise ValueError("Customer count must be greater than 0.")
    if not items:
        raise ValueError("Order must contain at least one menu item.")

    with transaction() as conn:
        cursor = conn.cursor()

        # Verify waiter
        cursor.execute("SELECT EmployeeID, Name FROM Staff WHERE EmployeeID = ? AND Role = 'Waiter' AND IsActive = 1;", (waiter_id,))
        waiter = cursor.fetchone()
        if not waiter:
            raise ValueError(f"Active waiter with EmployeeID {waiter_id} not found.")

        # Verify tables exist and mark them Occupied
        for t_num in table_numbers:
            cursor.execute("SELECT TableNumber, CurrentStatus FROM Tables WHERE TableNumber = ?;", (t_num,))
            tbl = cursor.fetchone()
            if not tbl:
                raise ValueError(f"Table {t_num} does not exist.")
            cursor.execute("UPDATE Tables SET CurrentStatus = 'Occupied' WHERE TableNumber = ?;", (t_num,))

        # 1. Insert Order
        cursor.execute("""
            INSERT INTO Orders (WaiterID, CustomerCount, CashAmount, UPIAmount, OrderStatus, OrderTimestamp)
            VALUES (?, ?, 0.00, 0.00, 'In Progress', CURRENT_TIMESTAMP);
        """, (waiter_id, customer_count))
        order_id = cursor.lastrowid

        # 2. Insert Order_Tables bridge records
        for t_num in table_numbers:
            cursor.execute("INSERT INTO Order_Tables (OrderID, TableNumber) VALUES (?, ?);", (order_id, t_num))

        # 3. Insert Order_Details
        total_bill = 0.0
        details_list = []
        for it in items:
            menu_item_id = it["MenuItemID"]
            quantity = int(it.get("Quantity", 1))
            if quantity <= 0:
                raise ValueError("Item quantity must be greater than 0.")

            cursor.execute("SELECT Price, AssignedChefID, ItemName FROM Menu_Items WHERE MenuItemID = ?;", (menu_item_id,))
            menu_row = cursor.fetchone()
            if not menu_row:
                raise ValueError(f"MenuItemID {menu_item_id} not found.")

            price = menu_row["Price"]
            assigned_chef_id = menu_row["AssignedChefID"]
            subtotal = round(price * quantity, 2)
            total_bill += subtotal

            cursor.execute("""
                INSERT INTO Order_Details (OrderID, MenuItemID, Quantity, UnitPrice, Subtotal, PreparedBy_EmployeeID, ItemStatus)
                VALUES (?, ?, ?, ?, ?, ?, 'Pending');
            """, (order_id, menu_item_id, quantity, price, subtotal, assigned_chef_id))
            od_id = cursor.lastrowid
            details_list.append({
                "OrderDetailID": od_id,
                "ItemName": menu_row["ItemName"],
                "Quantity": quantity,
                "UnitPrice": price,
                "Subtotal": subtotal,
                "AssignedChefID": assigned_chef_id,
                "ItemStatus": "Pending"
            })

        return {
            "status": "success",
            "order_id": order_id,
            "waiter_id": waiter_id,
            "customer_count": customer_count,
            "tables": table_numbers,
            "total_estimate": round(total_bill, 2),
            "items": details_list
        }


def add_item_to_order(order_id: int, menu_item_id: int, quantity: int = 1) -> Dict[str, Any]:
    """Adds an item to an existing in-progress order without recreating the ticket."""
    if quantity <= 0:
        raise ValueError("Quantity must be greater than 0.")

    with transaction() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT OrderStatus FROM Orders WHERE OrderID = ?;", (order_id,))
        order = cursor.fetchone()
        if not order:
            raise ValueError(f"Order #{order_id} not found.")
        if order["OrderStatus"] != 'In Progress':
            raise ValueError(f"Cannot add items to order #{order_id} because it is '{order['OrderStatus']}'.")

        cursor.execute("SELECT Price, AssignedChefID, ItemName FROM Menu_Items WHERE MenuItemID = ?;", (menu_item_id,))
        menu_row = cursor.fetchone()
        if not menu_row:
            raise ValueError(f"MenuItemID {menu_item_id} not found.")

        price = menu_row["Price"]
        subtotal = round(price * quantity, 2)
        cursor.execute("""
            INSERT INTO Order_Details (OrderID, MenuItemID, Quantity, UnitPrice, Subtotal, PreparedBy_EmployeeID, ItemStatus)
            VALUES (?, ?, ?, ?, ?, ?, 'Pending');
        """, (order_id, menu_item_id, quantity, price, subtotal, menu_row["AssignedChefID"]))
        od_id = cursor.lastrowid

        return {
            "status": "success",
            "order_detail_id": od_id,
            "order_id": order_id,
            "item_name": menu_row["ItemName"],
            "quantity": quantity,
            "unit_price": price,
            "subtotal": subtotal,
            "item_status": "Pending"
        }


def chef_review_cancel_consent(order_detail_id: int, approved: bool) -> Dict[str, Any]:
    """
    4.2 Chef Deletion-Consent Flow:
    Approved (Not started) -> ItemStatus = 'Cancelled' -> Log to Waste_Log (IngredientCost calculated)
    Denied (Already prepared) -> ItemStatus = 'Cooking' or 'Ready' -> Retained on Bill
    """
    with transaction() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT od.OrderDetailID, od.OrderID, od.Subtotal, od.ItemStatus, m.ItemName, m.Price, od.Quantity
            FROM Order_Details od
            JOIN Menu_Items m ON od.MenuItemID = m.MenuItemID
            WHERE od.OrderDetailID = ?;
        """, (order_detail_id,))
        od = cursor.fetchone()
        if not od:
            raise ValueError(f"OrderDetailID {order_detail_id} not found.")

        if approved:
            new_status = 'Cancelled'
            # Estimate raw ingredient waste cost (~40% of item subtotal)
            ingredient_cost = round(od["Subtotal"] * 0.40, 2)
            cursor.execute("UPDATE Order_Details SET ItemStatus = ? WHERE OrderDetailID = ?;", (new_status, order_detail_id))
            cursor.execute("""
                INSERT INTO Waste_Log (OrderDetailID, IngredientCost, LogTimestamp)
                VALUES (?, ?, CURRENT_TIMESTAMP);
            """, (order_detail_id, ingredient_cost))
            waste_id = cursor.lastrowid
            msg = f"Cancellation approved for {od['ItemName']}. Discard logged to Waste_Log with cost Rs.{ingredient_cost}."
        else:
            new_status = 'Cooking'
            cursor.execute("UPDATE Order_Details SET ItemStatus = ? WHERE OrderDetailID = ?;", (new_status, order_detail_id))
            waste_id = None
            msg = f"Cancellation denied for {od['ItemName']} (preparation underway). Retained on customer bill."

        return {
            "status": "success",
            "order_detail_id": order_detail_id,
            "item_name": od["ItemName"],
            "decision": "Approved" if approved else "Denied",
            "new_status": new_status,
            "waste_id": waste_id,
            "message": msg
        }


def chef_discard_order_item(order_detail_id: int, reason: str, chef_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Direct Chef Food Discard / Cancellation Flow:
    1. Updates Order_Details: ItemStatus = 'Cancelled', CancellationReason = reason.
    2. Calculates estimated raw ingredient waste cost (~40% of item subtotal).
    3. Pushes entry into Waste_Log (OrderDetailID, IngredientCost, LogTimestamp).
    4. Dish is removed from Chef Live Production Queue and immediately reflected
       in the Kitchen Manager's Discarded Food & Waste Log.
    """
    with transaction() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT od.OrderDetailID, od.OrderID, od.Subtotal, od.ItemStatus, m.ItemName, m.Price, od.Quantity,
                   od.PreparedBy_EmployeeID
            FROM Order_Details od
            JOIN Menu_Items m ON od.MenuItemID = m.MenuItemID
            WHERE od.OrderDetailID = ?;
        """, (order_detail_id,))
        od = cursor.fetchone()
        if not od:
            raise ValueError(f"OrderDetailID #{order_detail_id} not found.")

        if od["ItemStatus"] == 'Cancelled':
            raise ValueError(f"Dish '{od['ItemName']}' is already cancelled.")

        # Estimate raw ingredient waste cost (~40% of item subtotal)
        subtotal = od["Subtotal"] if od["Subtotal"] and od["Subtotal"] > 0 else (od["Price"] * od["Quantity"])
        ingredient_cost = round(subtotal * 0.40, 2)

        reason_clean = (reason or "").strip() or "Food discarded during cooking"

        cursor.execute("""
            UPDATE Order_Details 
            SET ItemStatus = 'Cancelled', CancellationReason = ?
            WHERE OrderDetailID = ?;
        """, (reason_clean, order_detail_id))

        cursor.execute("""
            INSERT INTO Waste_Log (OrderDetailID, IngredientCost, LogTimestamp)
            VALUES (?, ?, CURRENT_TIMESTAMP);
        """, (order_detail_id, ingredient_cost))
        waste_id = cursor.lastrowid

        return {
            "status": "success",
            "order_detail_id": order_detail_id,
            "order_id": od["OrderID"],
            "item_name": od["ItemName"],
            "ingredient_cost": ingredient_cost,
            "waste_id": waste_id,
            "message": f"'{od['ItemName']}' cancelled & discarded. Loss Rs.{ingredient_cost:.2f} logged to Waste Log."
        }


def checkout_order(order_id: int, cash_amount: float, upi_amount: float) -> Dict[str, Any]:
    """
    Completes checkout with exact payment splits (CashAmount & UPIAmount).
    Frees up associated tables back to 'Available'.
    """
    if cash_amount < 0 or upi_amount < 0:
        raise ValueError("Cash and UPI amounts must be non-negative.")

    with transaction() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT OrderID, OrderStatus FROM Orders WHERE OrderID = ?;", (order_id,))
        order = cursor.fetchone()
        if not order:
            raise ValueError(f"Order #{order_id} not found.")
        if order["OrderStatus"] != 'In Progress':
            raise ValueError(f"Order #{order_id} is already '{order['OrderStatus']}'.")

        # Calculate active items bill (excluding Cancelled items)
        cursor.execute("""
            SELECT COALESCE(SUM(Subtotal), 0) AS BillTotal 
            FROM Order_Details 
            WHERE OrderID = ? AND ItemStatus != 'Cancelled';
        """, (order_id,))
        bill_row = cursor.fetchone()
        bill_total = bill_row["BillTotal"] if bill_row else 0.0

        paid_total = round(cash_amount + upi_amount, 2)
        if paid_total < round(bill_total, 2):
            raise ValueError(f"Total payment Rs.{paid_total:.2f} is less than total bill Rs.{bill_total:.2f}.")

        # Update order to Completed with payment split
        cursor.execute("""
            UPDATE Orders 
            SET CashAmount = ?, UPIAmount = ?, OrderStatus = 'Completed'
            WHERE OrderID = ?;
        """, (cash_amount, upi_amount, order_id))

        # Free all tables linked to this order
        cursor.execute("SELECT TableNumber FROM Order_Tables WHERE OrderID = ?;", (order_id,))
        tbls = cursor.fetchall()
        for t in tbls:
            cursor.execute("UPDATE Tables SET CurrentStatus = 'Available' WHERE TableNumber = ?;", (t["TableNumber"],))

        return {
            "status": "success",
            "order_id": order_id,
            "bill_total": bill_total,
            "cash_amount": cash_amount,
            "upi_amount": upi_amount,
            "freed_tables": [t["TableNumber"] for t in tbls],
            "message": f"Order #{order_id} successfully paid and finalized."
        }


def submit_order_feedback(
    order_id: int,
    customer_name: Optional[str] = None,
    phone_number: Optional[str] = None,
    service_rating: Optional[int] = None,
    food_rating: Optional[int] = None,
    ambience_rating: Optional[int] = None,
    cleanliness_rating: Optional[int] = None,
    review_text: Optional[str] = None
) -> Dict[str, Any]:
    """
    Submits feedback enforcing the Anti-Fraud Gatekeeper Constraint:
    CHECK (
      (ServiceRating IS NULL AND CustomerName IS NULL AND PhoneNumber IS NULL)
      OR
      (ServiceRating IS NOT NULL AND CustomerName IS NOT NULL AND PhoneNumber IS NOT NULL)
    )
    """
    with transaction() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT OrderID, OrderStatus FROM Orders WHERE OrderID = ?;", (order_id,))
        order = cursor.fetchone()
        if not order:
            raise ValueError(f"Order #{order_id} not found.")

        # Check for existing feedback
        cursor.execute("SELECT FeedbackID FROM Feedback WHERE OrderID = ?;", (order_id,))
        if cursor.fetchone():
            raise ValueError(f"Feedback for Order #{order_id} already exists.")

        # Anti-fraud verification (Python level check that mirrors SQL CHECK constraint)
        has_rating = service_rating is not None
        has_name = bool(customer_name and customer_name.strip())
        has_phone = bool(phone_number and phone_number.strip())

        if (has_rating and (not has_name or not has_phone)) or ((has_name or has_phone) and not has_rating):
            raise ValueError(
                "Anti-Fraud Gatekeeper Triggered: Customer Name and Phone Number are strictly mandatory "
                "when submitting operational ratings (ServiceRating)."
            )

        cust_name_val = customer_name.strip() if customer_name else None
        phone_val = phone_number.strip() if phone_number else None

        cursor.execute("""
            INSERT INTO Feedback (
                OrderID, CustomerName, PhoneNumber, 
                ServiceRating, FoodRating, AmbienceRating, CleanlinessRating, ReviewText
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            order_id, cust_name_val, phone_val,
            service_rating, food_rating, ambience_rating, cleanliness_rating, review_text
        ))
        feedback_id = cursor.lastrowid

        return {
            "status": "success",
            "feedback_id": feedback_id,
            "order_id": order_id,
            "message": "Feedback verified and successfully recorded."
        }
