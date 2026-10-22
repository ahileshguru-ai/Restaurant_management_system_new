"""
Shop Manager Operations & Executive Intelligence API
=====================================================
Implements Full Administrative CRUD across the 14 Relational Tables,
Payroll & Investment Tracking, Salary Adjustments, and the 4
Automated SQL Business Intelligence Views.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from database.db import get_connection, transaction
from app.auth import require_roles

router = APIRouter(prefix="/api/manager", tags=["Shop Manager Executive Intelligence"])
mgr_guard = require_roles(["Shop Manager"])


class SalaryAdjustmentRequest(BaseModel):
    new_salary: float = Field(..., ge=0)


class CreateStaffRequest(BaseModel):
    name: str = Field(..., min_length=2)
    role: str = Field(..., description="'Chef', 'Waiter', 'Kitchen Manager', 'Shop Manager'")
    shift: str = "Morning Shift"
    salary: float = Field(30000.00, ge=0)


class ExpenseLogRequest(BaseModel):
    expense_date: str = Field(..., description="YYYY-MM-DD")
    expense_amount: float = Field(..., gt=0)
    expense_type: str = Field(..., description="'Raw Materials', 'Other Investments', 'Payroll'")
    description: Optional[str] = None


class CreateMenuItemRequest(BaseModel):
    item_name: str = Field(..., min_length=2)
    category: str = Field(..., min_length=2)
    price: float = Field(..., gt=0)
    assigned_chef_id: int


class UpdateTableRequest(BaseModel):
    seating_capacity: int = Field(..., gt=0)
    current_status: str = Field(..., description="'Available', 'Occupied', 'Reserved'")


# =====================================================================
# SECTION 5: The 4 Automated SQL Business Intelligence Views
# =====================================================================

@router.get("/views/waiter-performance")
def get_view_waiter_performance(current_user: Dict[str, Any] = Depends(mgr_guard)):
    """Returns View_Waiter_Performance (Total Customers Handled × Avg Service Rating)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM View_Waiter_Performance ORDER BY TotalPerformancePoints DESC;")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"view_data": rows}


@router.get("/views/chef-performance")
def get_view_chef_performance(current_user: Dict[str, Any] = Depends(mgr_guard)):
    """Returns View_Chef_Performance (Total Dishes Prepared × Avg Food Rating)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM View_Chef_Performance ORDER BY CulinaryPerformancePoints DESC;")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"view_data": rows}


@router.get("/views/daily-collections")
def get_view_daily_collections(current_user: Dict[str, Any] = Depends(mgr_guard)):
    """Returns View_Daily_Waiter_Collections (Cash vs UPI collections per waiter per day)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM View_Daily_Waiter_Collections ORDER BY CollectionDate DESC, TotalShiftCollection DESC;")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"view_data": rows}


@router.get("/views/monthly-profit-loss")
def get_view_monthly_profit_loss(current_user: Dict[str, Any] = Depends(mgr_guard)):
    """Returns View_Monthly_Profit_Loss (Incoming Revenue vs Outgoing Expenses)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM View_Monthly_Profit_Loss ORDER BY ReportingMonth DESC;")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"view_data": rows}


@router.get("/overview")
def get_executive_overview(current_user: Dict[str, Any] = Depends(mgr_guard)):
    """Summary KPI cards for the Executive Shop Manager dashboard."""
    conn = get_connection()
    cursor = conn.cursor()

    # Total Completed Revenue
    cursor.execute("SELECT COALESCE(SUM(CashAmount + UPIAmount), 0) AS TotalRevenue, COUNT(*) AS TotalCompletedOrders FROM Orders WHERE OrderStatus = 'Completed';")
    rev = cursor.fetchone()

    # Total Expenses
    cursor.execute("SELECT COALESCE(SUM(ExpenseAmount), 0) AS TotalExpenses FROM Purchase_Expenses;")
    exp = cursor.fetchone()

    # Table Occupancy
    cursor.execute("SELECT COUNT(*) AS TotalTables, SUM(CASE WHEN CurrentStatus = 'Occupied' THEN 1 ELSE 0 END) AS OccupiedTables FROM Tables;")
    tbl = cursor.fetchone()

    # Total Active Personnel
    cursor.execute("SELECT COUNT(*) AS ActiveStaff FROM Staff WHERE IsActive = 1;")
    stf = cursor.fetchone()

    # Total Customer Feedbacks
    cursor.execute("SELECT COUNT(*) AS TotalReviews, ROUND(AVG(ServiceRating), 2) AS AvgService, ROUND(AVG(FoodRating), 2) AS AvgFood FROM Feedback WHERE ServiceRating IS NOT NULL;")
    fb = cursor.fetchone()

    conn.close()

    net_profit = rev["TotalRevenue"] - exp["TotalExpenses"]
    margin = round((net_profit / exp["TotalExpenses"] * 100), 2) if exp["TotalExpenses"] > 0 else 0.0

    return {
        "kpi": {
            "total_revenue": rev["TotalRevenue"],
            "total_completed_orders": rev["TotalCompletedOrders"],
            "total_expenses": exp["TotalExpenses"],
            "net_profit_loss": round(net_profit, 2),
            "profit_margin_pct": margin,
            "total_tables": tbl["TotalTables"],
            "occupied_tables": tbl["OccupiedTables"] or 0,
            "active_staff": stf["ActiveStaff"],
            "avg_service_rating": fb["AvgService"] or 0.0,
            "avg_food_rating": fb["AvgFood"] or 0.0,
            "verified_reviews": fb["TotalReviews"]
        }
    }


# =====================================================================
# Personnel, Payroll & CRUD Operations
# =====================================================================

@router.get("/staff")
def list_staff(current_user: Dict[str, Any] = Depends(mgr_guard)):
    """Lists all staff members including role, shift, active status, and salary."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.EmployeeID, s.Name, s.Role, s.Shift, s.IsActive, s.Salary,
               u.Username, u.UserID
        FROM Staff s
        LEFT JOIN Users u ON s.EmployeeID = u.EmployeeID
        ORDER BY s.IsActive DESC, s.EmployeeID ASC;
    """)
    staff = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"staff": staff}


@router.put("/staff/{employee_id}/salary")
def adjust_staff_salary(
    employee_id: int,
    req: SalaryAdjustmentRequest,
    current_user: Dict[str, Any] = Depends(mgr_guard)
):
    """Executes salary increment/decrement for personnel."""
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT Name, Salary FROM Staff WHERE EmployeeID = ?;", (employee_id,))
        emp = cursor.fetchone()
        if not emp:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found.")

        old_salary = emp["Salary"]
        cursor.execute("UPDATE Staff SET Salary = ? WHERE EmployeeID = ?;", (req.new_salary, employee_id))

    return {
        "status": "success",
        "employee_id": employee_id,
        "name": emp["Name"],
        "old_salary": old_salary,
        "new_salary": req.new_salary,
        "message": f"Salary for {emp['Name']} updated from Rs.{old_salary:.2f} to Rs.{req.new_salary:.2f}."
    }


@router.delete("/staff/{employee_id}")
def delete_or_retire_staff(
    employee_id: int,
    current_user: Dict[str, Any] = Depends(mgr_guard)
):
    """
    Removes or retires an employee (Waiter, Chef, or Kitchen Manager).
    - If the employee has historical orders or cooking assignments:
      Deletes their login credentials from Users and marks Staff as retired (IsActive = 0)
      to maintain 3NF foreign key integrity and Jim Gray transaction audits.
    - If the employee has no associated historical records:
      Hard-deletes both their Users credentials and Staff record completely.
    """
    if employee_id == current_user["employee_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot remove yourself while logged in as the active Shop Manager. Use the Handover Protocol to transfer management."
        )

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT EmployeeID, Name, Role, IsActive FROM Staff WHERE EmployeeID = ?;", (employee_id,))
    emp = cursor.fetchone()
    if not emp:
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found.")

    # Check for historical references in Orders, Order_Details, or Menu_Items
    cursor.execute("SELECT COUNT(*) AS Cnt FROM Orders WHERE WaiterID = ?;", (employee_id,))
    orders_cnt = cursor.fetchone()["Cnt"]

    cursor.execute("SELECT COUNT(*) AS Cnt FROM Order_Details WHERE PreparedBy_EmployeeID = ?;", (employee_id,))
    prep_cnt = cursor.fetchone()["Cnt"]

    cursor.execute("SELECT COUNT(*) AS Cnt FROM Menu_Items WHERE AssignedChefID = ?;", (employee_id,))
    menu_cnt = cursor.fetchone()["Cnt"]

    has_history = (orders_cnt > 0) or (prep_cnt > 0) or (menu_cnt > 0)
    conn.close()

    with transaction() as tx_conn:
        tx_cur = tx_conn.cursor()
        # Revoke and hard-delete user login credentials so they can never authenticate again
        tx_cur.execute("DELETE FROM Users WHERE EmployeeID = ?;", (employee_id,))

        if has_history:
            # Soft-retire in Staff to protect historical order data and 3NF foreign keys
            tx_cur.execute("UPDATE Staff SET IsActive = 0 WHERE EmployeeID = ?;", (employee_id,))
            msg = f"{emp['Role']} '{emp['Name']}' has been retired and their login access revoked. Historical order records are safely preserved."
        else:
            # Hard delete if clean record
            tx_cur.execute("DELETE FROM Staff WHERE EmployeeID = ?;", (employee_id,))
            msg = f"{emp['Role']} '{emp['Name']}' and their login account have been completely deleted from the database."

    return {
        "status": "success",
        "employee_id": employee_id,
        "name": emp["Name"],
        "role": emp["Role"],
        "has_history": has_history,
        "message": msg
    }


@router.get("/expenses")
def list_expenses(current_user: Dict[str, Any] = Depends(mgr_guard)):
    """Lists all purchase expenses (Raw Materials, Payroll, Other Investments)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Purchase_Expenses ORDER BY ExpenseDate DESC, ExpenseID DESC;")
    expenses = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"expenses": expenses}


@router.post("/expenses")
def log_expense(
    req: ExpenseLogRequest,
    current_user: Dict[str, Any] = Depends(mgr_guard)
):
    """Logs non-kitchen investments or payroll outlays into Purchase_Expenses."""
    if req.expense_type not in ('Raw Materials', 'Other Investments', 'Payroll'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ExpenseType must be 'Raw Materials', 'Other Investments', or 'Payroll'."
        )

    desc = req.description.strip() if req.description and req.description.strip() else None

    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Purchase_Expenses (ExpenseDate, ExpenseAmount, ExpenseType, Description)
            VALUES (?, ?, ?, ?);
        """, (req.expense_date, req.expense_amount, req.expense_type, desc))
        exp_id = cursor.lastrowid

    return {
        "status": "success",
        "expense_id": exp_id,
        "amount": req.expense_amount,
        "type": req.expense_type,
        "description": desc,
        "message": f"Expense of Rs.{req.expense_amount:.2f} under '{req.expense_type}' successfully logged."
    }


@router.get("/feedbacks")
def list_customer_feedbacks(current_user: Dict[str, Any] = Depends(mgr_guard)):
    """Lists verified customer feedback entries."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT f.*, o.WaiterID, s.Name AS WaiterName, o.CustomerCount, o.OrderTimestamp
        FROM Feedback f
        JOIN Orders o ON f.OrderID = o.OrderID
        JOIN Staff s ON o.WaiterID = s.EmployeeID
        ORDER BY f.FeedbackID DESC;
    """)
    feedbacks = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"feedbacks": feedbacks}


@router.get("/shortage-logs")
def list_shortage_logs(current_user: Dict[str, Any] = Depends(mgr_guard)):
    """Lists out-of-stock incident logs generated by chefs."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sl.LogID, sl.MenuItemID, m.ItemName, sl.ChefID, s.Name AS ChefName,
               sl.Reason, sl.LogTimestamp
        FROM Shortage_Logs sl
        JOIN Menu_Items m ON sl.MenuItemID = m.MenuItemID
        JOIN Staff s ON sl.ChefID = s.EmployeeID
        ORDER BY sl.LogTimestamp DESC;
    """)
    logs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"shortage_logs": logs}
