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

    # Ensure StockQuantity column exists on Menu_Items (dynamic portion-level inventory tracking)
    cursor.execute("PRAGMA table_info(Menu_Items);")
    item_cols_now = [c["name"] for c in cursor.fetchall()]
    if "StockQuantity" not in item_cols_now:
        cursor.execute("ALTER TABLE Menu_Items ADD COLUMN StockQuantity INTEGER NOT NULL DEFAULT 10 CHECK (StockQuantity >= 0);")
        cursor.execute("UPDATE Menu_Items SET StockQuantity = 10 WHERE StockQuantity IS NULL;")
        cursor.execute("UPDATE Menu_Items SET IsAvailable = CASE WHEN StockQuantity > 0 THEN 1 ELSE 0 END;")
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

    # Ensure View_Chef_Performance and triggers are loaded
    with open(SCHEMA_SQL_PATH, "r", encoding="utf-8") as f:
        schema_script = f.read()
    view_statements = [stmt.strip() for stmt in schema_script.split(";") if "CREATE VIEW" in stmt or "DROP VIEW" in stmt]
    for stmt in view_statements:
        if stmt:
            conn.execute(stmt)

    # Ensure pre-cooking edit block trigger allows quantity reduction for partial cancellation
    cursor.execute("DROP TRIGGER IF EXISTS trg_block_order_detail_update;")
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_block_order_detail_update
        BEFORE UPDATE ON Order_Details
        FOR EACH ROW
        WHEN OLD.ItemStatus != 'Pending' AND (OLD.MenuItemID != NEW.MenuItemID OR OLD.UnitPrice != NEW.UnitPrice OR NEW.Quantity > OLD.Quantity)
        BEGIN
            SELECT RAISE(ABORT, 'Pre-Cooking Edit Block: Cannot modify dish, unit price, or increase quantity once status moves past Pending.');
        END;
    """)
    # Ensure automated trigger trg_sync_wastelog_to_expenses is active
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_sync_wastelog_to_expenses
        AFTER INSERT ON Waste_Log
        FOR EACH ROW
        WHEN NEW.IngredientCost > 0
        BEGIN
            INSERT INTO Purchase_Expenses (ExpenseDate, ExpenseAmount, ExpenseType, Description)
            VALUES (DATE(COALESCE(NEW.LogTimestamp, 'now')), NEW.IngredientCost, 'Raw Materials', 'wastelog');
        END;
    """)
    conn.commit()

    # Backfill any pre-existing Waste_Log rows into Purchase_Expenses (description 'wastelog')
    cursor.execute("SELECT COUNT(*) FROM Purchase_Expenses WHERE Description = 'wastelog';")
    existing_waste_exp_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM Waste_Log WHERE IngredientCost > 0;")
    waste_log_count = cursor.fetchone()[0]

    if existing_waste_exp_count < waste_log_count:
        missing_count = waste_log_count - existing_waste_exp_count
        cursor.execute("""
            INSERT INTO Purchase_Expenses (ExpenseDate, ExpenseAmount, ExpenseType, Description)
            SELECT DATE(COALESCE(wl.LogTimestamp, 'now')), wl.IngredientCost, 'Raw Materials', 'wastelog'
            FROM Waste_Log wl
            WHERE wl.IngredientCost > 0
            LIMIT ?;
        """, (missing_count,))
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


def update_menu_item_stock(menu_item_id: int, stock_quantity: int, chef_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Updates the available stock quantity for a menu item.
    - Validates stock_quantity >= 0.
    - If stock_quantity == 0, sets IsAvailable = 0 (automatically out of stock).
    - If stock_quantity > 0, sets IsAvailable = 1 (automatically in stock).
    - Can be altered by the chef at any time to replenish or adjust portions in advance.
    """
    if stock_quantity < 0:
        raise ValueError("Stock quantity cannot be negative.")

    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT MenuItemID, ItemName, AssignedChefID, StockQuantity, IsAvailable FROM Menu_Items WHERE MenuItemID = ?;", (menu_item_id,))
        item = cursor.fetchone()
        if not item:
            raise ValueError(f"MenuItemID {menu_item_id} not found.")

        if chef_id is not None and item["AssignedChefID"] != chef_id:
            raise PermissionError("You can only manage stock for dishes assigned to your culinary station.")

        new_is_available = 1 if stock_quantity > 0 else 0
        cursor.execute("""
            UPDATE Menu_Items 
            SET StockQuantity = ?, IsAvailable = ?
            WHERE MenuItemID = ?;
        """, (stock_quantity, new_is_available, menu_item_id))

        return {
            "status": "success",
            "menu_item_id": menu_item_id,
            "item_name": item["ItemName"],
            "previous_stock": item["StockQuantity"],
            "stock_quantity": stock_quantity,
            "is_available": bool(new_is_available),
            "message": f"Stock for '{item['ItemName']}' updated to {stock_quantity} portions (Status: {'IN STOCK' if new_is_available else 'OUT OF STOCK'})."
        }


def out_of_stock_atomic_transaction(menu_item_id: int, chef_id: int, shortage_reason: str) -> Dict[str, Any]:
    """
    4.3 Out-of-Stock Atomic Transaction (Page 6 of Constraints):
    BEGIN TRANSACTION;
    UPDATE Menu_Items SET StockQuantity = 0, IsAvailable = FALSE WHERE MenuItemID = :item_id;
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

        cursor.execute("UPDATE Menu_Items SET StockQuantity = 0, IsAvailable = 0 WHERE MenuItemID = ?;", (menu_item_id,))
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

            cursor.execute("SELECT Price, AssignedChefID, ItemName, StockQuantity, IsAvailable FROM Menu_Items WHERE MenuItemID = ?;", (menu_item_id,))
            menu_row = cursor.fetchone()
            if not menu_row:
                raise ValueError(f"MenuItemID {menu_item_id} not found.")

            stock_qty = menu_row["StockQuantity"] if menu_row["StockQuantity"] is not None else 0
            if not menu_row["IsAvailable"] or stock_qty <= 0:
                raise ValueError(f"Dish '{menu_row['ItemName']}' is currently OUT OF STOCK.")

            if quantity > stock_qty:
                raise ValueError(f"Insufficient stock for '{menu_row['ItemName']}'. Only {stock_qty} portion(s) remaining in stock.")

            # Decrement stock count and auto-flag out-of-stock when reaching 0
            cursor.execute("""
                UPDATE Menu_Items
                SET StockQuantity = StockQuantity - ?,
                    IsAvailable = CASE WHEN StockQuantity - ? <= 0 THEN 0 ELSE 1 END
                WHERE MenuItemID = ?;
            """, (quantity, quantity, menu_item_id))

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

        cursor.execute("SELECT Price, AssignedChefID, ItemName, StockQuantity, IsAvailable FROM Menu_Items WHERE MenuItemID = ?;", (menu_item_id,))
        menu_row = cursor.fetchone()
        if not menu_row:
            raise ValueError(f"MenuItemID {menu_item_id} not found.")

        stock_qty = menu_row["StockQuantity"] if menu_row["StockQuantity"] is not None else 0
        if not menu_row["IsAvailable"] or stock_qty <= 0:
            raise ValueError(f"Dish '{menu_row['ItemName']}' is currently OUT OF STOCK.")

        if quantity > stock_qty:
            raise ValueError(f"Insufficient stock for '{menu_row['ItemName']}'. Only {stock_qty} portion(s) remaining in stock.")

        # Decrement stock count and auto-flag out-of-stock when reaching 0
        cursor.execute("""
            UPDATE Menu_Items
            SET StockQuantity = StockQuantity - ?,
                IsAvailable = CASE WHEN StockQuantity - ? <= 0 THEN 0 ELSE 1 END
            WHERE MenuItemID = ?;
        """, (quantity, quantity, menu_item_id))

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
            # Estimate raw ingredient waste cost (~80% of item subtotal)
            ingredient_cost = round(od["Subtotal"] * 0.80, 2)
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
    2. Calculates estimated raw ingredient waste cost (~80% of item subtotal).
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

        # Estimate raw ingredient waste cost (~80% of item subtotal)
        subtotal = od["Subtotal"] if od["Subtotal"] and od["Subtotal"] > 0 else (od["Price"] * od["Quantity"])
        ingredient_cost = round(subtotal * 0.80, 2)

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


def waiter_cancel_order_item(
    order_detail_id: int,
    reason: Optional[str] = None,
    waiter_id: Optional[int] = None,
    cancel_quantity: Optional[int] = None
) -> Dict[str, Any]:
    """
    Waiter Food Item Cancellation Flow:
    - Supports full cancellation or partial quantity cancellation (e.g. 1 out of 15 biriyanis).
    - If cancelled BEFORE cooking ('Pending' / 'Cancel Requested'):
      Cancelled portions are restored to stock inventory; does NOT go to Waste_Log.
    - If cancelled DURING or AFTER cooking ('Cooking' / 'Ready'):
      ONLY the cancelled portion goes to Waste_Log with raw ingredient cost (~80% of item subtotal).
    - If all items in the order become cancelled, the order is automatically marked Cancelled and tables freed.
    """
    with transaction() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT od.OrderDetailID, od.OrderID, od.MenuItemID, od.Subtotal, od.UnitPrice, od.Quantity,
                   od.ItemStatus, od.PreparedBy_EmployeeID, m.ItemName, m.Price, o.OrderStatus, o.WaiterID
            FROM Order_Details od
            JOIN Menu_Items m ON od.MenuItemID = m.MenuItemID
            JOIN Orders o ON od.OrderID = o.OrderID
            WHERE od.OrderDetailID = ?;
        """, (order_detail_id,))
        od = cursor.fetchone()
        if not od:
            raise ValueError(f"OrderDetailID #{order_detail_id} not found.")

        if od["OrderStatus"] != 'In Progress':
            raise ValueError(f"Cannot cancel item because order #{od['OrderID']} is '{od['OrderStatus']}'.")

        if waiter_id is not None and od["WaiterID"] != waiter_id:
            raise PermissionError("You can only cancel items for orders assigned to your shift.")

        if od["ItemStatus"] == 'Cancelled':
            raise ValueError(f"Dish '{od['ItemName']}' is already cancelled.")

        available_qty = od["Quantity"]
        if cancel_quantity is None:
            qty_to_cancel = available_qty
        else:
            try:
                qty_to_cancel = int(cancel_quantity)
            except (ValueError, TypeError):
                raise ValueError("Cancel quantity must be a positive integer.")
            if qty_to_cancel <= 0:
                raise ValueError("Cancel quantity must be at least 1.")
            if qty_to_cancel > available_qty:
                raise ValueError(f"Cannot cancel {qty_to_cancel} portions; only {available_qty} portion(s) available in this dish.")

        unit_price = od["UnitPrice"] if od["UnitPrice"] is not None and od["UnitPrice"] > 0 else od["Price"]
        logged_to_waste = False
        waste_id = None
        ingredient_cost = 0.0

        if qty_to_cancel == available_qty:
            # Full item cancellation
            cancelled_detail_id = order_detail_id
            remaining_qty = 0

            if od["ItemStatus"] in ('Cooking', 'Ready'):
                # During or after cooking: log full dish to Waste_Log
                subtotal = round(unit_price * qty_to_cancel, 2)
                ingredient_cost = round(subtotal * 0.80, 2)
                logged_to_waste = True
                cancellation_reason = reason.strip() if (reason and reason.strip()) else f"Cancelled by waiter during/after cooking ({od['ItemStatus']})"

                cursor.execute("""
                    UPDATE Order_Details
                    SET ItemStatus = 'Cancelled', CancellationReason = ?
                    WHERE OrderDetailID = ?;
                """, (cancellation_reason, order_detail_id))

                cursor.execute("""
                    INSERT INTO Waste_Log (OrderDetailID, IngredientCost, LogTimestamp)
                    VALUES (?, ?, CURRENT_TIMESTAMP);
                """, (order_detail_id, ingredient_cost))
                waste_id = cursor.lastrowid
                msg = f"'{od['ItemName']}' ({qty_to_cancel} portion(s)) cancelled during/after cooking ({od['ItemStatus']}). Discard logged to Waste Log (loss Rs.{ingredient_cost:.2f})."
            else:
                # Before cooking: restore all portions to stock
                cursor.execute("""
                    UPDATE Menu_Items
                    SET StockQuantity = StockQuantity + ?,
                        IsAvailable = 1
                    WHERE MenuItemID = ?;
                """, (qty_to_cancel, od["MenuItemID"]))

                cancellation_reason = reason.strip() if (reason and reason.strip()) else "Cancelled by waiter before cooking"
                cursor.execute("""
                    UPDATE Order_Details
                    SET ItemStatus = 'Cancelled', CancellationReason = ?
                    WHERE OrderDetailID = ?;
                """, (cancellation_reason, order_detail_id))
                msg = f"'{od['ItemName']}' ({qty_to_cancel} portion(s)) cancelled before cooking. Restored {qty_to_cancel} portion(s) to stock. Not logged to Waste Log."
        else:
            # Partial cancellation (e.g. 1 out of 15)
            remaining_qty = available_qty - qty_to_cancel
            remaining_subtotal = round(unit_price * remaining_qty, 2)
            cancelled_subtotal = round(unit_price * qty_to_cancel, 2)

            # 1. Update the existing row to reflect the remaining portion(s)
            cursor.execute("""
                UPDATE Order_Details
                SET Quantity = ?, Subtotal = ?
                WHERE OrderDetailID = ?;
            """, (remaining_qty, remaining_subtotal, order_detail_id))

            cancellation_reason = reason.strip() if (reason and reason.strip()) else f"Cancelled {qty_to_cancel} portion(s) by waiter ({od['ItemStatus']})"

            # 2. Insert a new row representing only the cancelled portion(s)
            cursor.execute("""
                INSERT INTO Order_Details (
                    OrderID, MenuItemID, Quantity, UnitPrice, Subtotal,
                    PreparedBy_EmployeeID, ItemStatus, CancellationReason
                ) VALUES (?, ?, ?, ?, ?, ?, 'Cancelled', ?);
            """, (
                od["OrderID"],
                od["MenuItemID"],
                qty_to_cancel,
                unit_price,
                cancelled_subtotal,
                od["PreparedBy_EmployeeID"],
                cancellation_reason
            ))
            cancelled_detail_id = cursor.lastrowid

            if od["ItemStatus"] in ('Cooking', 'Ready'):
                # ONLY the cancelled portion goes to Waste_Log
                ingredient_cost = round(cancelled_subtotal * 0.80, 2)
                logged_to_waste = True
                cursor.execute("""
                    INSERT INTO Waste_Log (OrderDetailID, IngredientCost, LogTimestamp)
                    VALUES (?, ?, CURRENT_TIMESTAMP);
                """, (cancelled_detail_id, ingredient_cost))
                waste_id = cursor.lastrowid
                msg = (f"Cancelled {qty_to_cancel} of {available_qty} '{od['ItemName']}' during/after cooking ({od['ItemStatus']}). "
                       f"Only cancelled portion logged to Waste Log (loss Rs.{ingredient_cost:.2f}). "
                       f"Remaining {remaining_qty} portion(s) continue preparation.")
            else:
                # Before cooking: restore only the cancelled portion(s) to stock
                cursor.execute("""
                    UPDATE Menu_Items
                    SET StockQuantity = StockQuantity + ?,
                        IsAvailable = 1
                    WHERE MenuItemID = ?;
                """, (qty_to_cancel, od["MenuItemID"]))
                msg = (f"Cancelled {qty_to_cancel} of {available_qty} '{od['ItemName']}' before cooking. "
                       f"Restored {qty_to_cancel} portion(s) to stock. Not logged to Waste Log. "
                       f"Remaining {remaining_qty} portion(s) remain on ticket.")

        # Check if all items in this order are now cancelled
        cursor.execute("""
            SELECT COUNT(*) AS active_count
            FROM Order_Details
            WHERE OrderID = ? AND ItemStatus != 'Cancelled';
        """, (od["OrderID"],))
        rem = cursor.fetchone()
        active_remaining = rem["active_count"] if rem else 0
        order_auto_cancelled = False

        if active_remaining == 0:
            cursor.execute("UPDATE Orders SET OrderStatus = 'Cancelled' WHERE OrderID = ?;", (od["OrderID"],))
            # Free tables
            cursor.execute("SELECT TableNumber FROM Order_Tables WHERE OrderID = ?;", (od["OrderID"],))
            for t in cursor.fetchall():
                cursor.execute("""
                    SELECT COUNT(*) as cnt FROM Order_Tables ot
                    JOIN Orders o ON ot.OrderID = o.OrderID
                    WHERE ot.TableNumber = ? AND o.OrderID != ? AND o.OrderStatus = 'In Progress';
                """, (t["TableNumber"], od["OrderID"]))
                if cursor.fetchone()["cnt"] == 0:
                    cursor.execute("UPDATE Tables SET CurrentStatus = 'Available' WHERE TableNumber = ?;", (t["TableNumber"],))
            order_auto_cancelled = True
            msg += f" All items cancelled; Order #{od['OrderID']} marked Cancelled and tables freed."

        return {
            "status": "success",
            "order_detail_id": order_detail_id,
            "cancelled_detail_id": cancelled_detail_id,
            "order_id": od["OrderID"],
            "item_name": od["ItemName"],
            "status_before": od["ItemStatus"],
            "cancelled_quantity": qty_to_cancel,
            "remaining_quantity": remaining_qty,
            "new_status": "Cancelled",
            "logged_to_waste": logged_to_waste,
            "ingredient_cost": ingredient_cost,
            "waste_id": waste_id,
            "order_cancelled": order_auto_cancelled,
            "message": msg
        }


def waiter_cancel_order(order_id: int, reason: Optional[str] = None, waiter_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Waiter Entire Order Cancellation Flow:
    - If an entire order is cancelled:
      * Dishes during or after cooking ('Cooking', 'Ready') alone go to Waste_Log.
      * Dishes before cooking ('Pending') do NOT go to Waste_Log.
      * Order status transitions to 'Cancelled'.
      * Assigned floor tables are freed back to 'Available'.
    """
    with transaction() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT OrderID, WaiterID, OrderStatus FROM Orders WHERE OrderID = ?;", (order_id,))
        order = cursor.fetchone()
        if not order:
            raise ValueError(f"Order #{order_id} not found.")

        if order["OrderStatus"] != 'In Progress':
            raise ValueError(f"Cannot cancel order #{order_id} because it is '{order['OrderStatus']}'.")

        if waiter_id is not None and order["WaiterID"] != waiter_id:
            raise PermissionError("You can only cancel orders assigned to your shift.")

        cursor.execute("""
            SELECT od.OrderDetailID, od.MenuItemID, m.ItemName, od.Quantity, od.UnitPrice, od.Subtotal, od.ItemStatus
            FROM Order_Details od
            JOIN Menu_Items m ON od.MenuItemID = m.MenuItemID
            WHERE od.OrderID = ?;
        """, (order_id,))
        items = cursor.fetchall()

        wasted_items = []
        non_wasted_items = []
        total_waste_cost = 0.0

        for it in items:
            if it["ItemStatus"] == 'Cancelled':
                continue

            subtotal = it["Subtotal"] if it["Subtotal"] and it["Subtotal"] > 0 else (it["UnitPrice"] * it["Quantity"])

            if it["ItemStatus"] in ('Cooking', 'Ready'):
                # During or after cooking: goes to Waste_Log
                cost = round(subtotal * 0.80, 2)
                item_reason = f"Order #{order_id} cancelled by waiter - dish was {it['ItemStatus']}"
                if reason and reason.strip():
                    item_reason += f" ({reason.strip()})"

                cursor.execute("""
                    UPDATE Order_Details
                    SET ItemStatus = 'Cancelled', CancellationReason = ?
                    WHERE OrderDetailID = ?;
                """, (item_reason, it["OrderDetailID"]))

                cursor.execute("""
                    INSERT INTO Waste_Log (OrderDetailID, IngredientCost, LogTimestamp)
                    VALUES (?, ?, CURRENT_TIMESTAMP);
                """, (it["OrderDetailID"], cost))
                waste_id = cursor.lastrowid

                wasted_items.append({
                    "order_detail_id": it["OrderDetailID"],
                    "item_name": it["ItemName"],
                    "status_before": it["ItemStatus"],
                    "ingredient_cost": cost,
                    "waste_id": waste_id
                })
                total_waste_cost += cost
            else:
                # Before cooking (Pending, etc.): does NOT go to Waste_Log
                # Restore stock quantity back to Menu_Items catalog
                cursor.execute("""
                    UPDATE Menu_Items
                    SET StockQuantity = StockQuantity + ?,
                        IsAvailable = 1
                    WHERE MenuItemID = ?;
                """, (it["Quantity"], it["MenuItemID"]))

                item_reason = f"Order #{order_id} cancelled by waiter - dish before cooking"
                if reason and reason.strip():
                    item_reason += f" ({reason.strip()})"

                cursor.execute("""
                    UPDATE Order_Details
                    SET ItemStatus = 'Cancelled', CancellationReason = ?
                    WHERE OrderDetailID = ?;
                """, (item_reason, it["OrderDetailID"]))

                non_wasted_items.append({
                    "order_detail_id": it["OrderDetailID"],
                    "item_name": it["ItemName"],
                    "status_before": it["ItemStatus"]
                })

        # Mark order as Cancelled
        cursor.execute("UPDATE Orders SET OrderStatus = 'Cancelled' WHERE OrderID = ?;", (order_id,))

        # Free all tables linked to this order
        cursor.execute("SELECT TableNumber FROM Order_Tables WHERE OrderID = ?;", (order_id,))
        tbls = cursor.fetchall()
        freed_tables = []
        for t in tbls:
            cursor.execute("""
                SELECT COUNT(*) as cnt 
                FROM Order_Tables ot 
                JOIN Orders o ON ot.OrderID = o.OrderID 
                WHERE ot.TableNumber = ? AND o.OrderID != ? AND o.OrderStatus = 'In Progress';
            """, (t["TableNumber"], order_id))
            if cursor.fetchone()["cnt"] == 0:
                cursor.execute("UPDATE Tables SET CurrentStatus = 'Available' WHERE TableNumber = ?;", (t["TableNumber"],))
                freed_tables.append(t["TableNumber"])

        return {
            "status": "success",
            "order_id": order_id,
            "order_status": "Cancelled",
            "wasted_items": wasted_items,
            "non_wasted_items": non_wasted_items,
            "total_waste_cost": round(total_waste_cost, 2),
            "freed_tables": freed_tables,
            "message": f"Order #{order_id} cancelled. {len(wasted_items)} dish(es) during/after cooking sent to Waste Log (loss Rs.{total_waste_cost:.2f}). {len(non_wasted_items)} dish(es) before cooking cancelled without waste."
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
