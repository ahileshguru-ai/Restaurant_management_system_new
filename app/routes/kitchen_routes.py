"""
Kitchen Manager Operations & Back-of-House API
===============================================
Implements Raw Material Inventory Alerts (NeedsRestock = 1),
Structural Menu Proposal Approvals (Menu_Requests), Dish Waste Audits,
and Raw Material Expense Procurement Logging.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from database.db import get_connection, transaction
from app.auth import require_roles

router = APIRouter(prefix="/api/kitchen", tags=["Kitchen Manager Back-of-House"])
km_guard = require_roles(["Kitchen Manager", "Shop Manager"])


class RestockStatusRequest(BaseModel):
    needs_restock: bool


class AddIngredientRequest(BaseModel):
    ingredient_name: str = Field(..., min_length=2)
    needs_restock: bool = False
    assigned_chef_id: Optional[int] = None


class MenuRequestAction(BaseModel):
    action: str = Field(..., description="'Approved' or 'Rejected'")
    category: Optional[str] = "Main Course"
    price: Optional[float] = 150.00
    assigned_chef_id: Optional[int] = None


class LogExpenseRequest(BaseModel):
    expense_date: str = Field(..., description="YYYY-MM-DD")
    expense_amount: float = Field(..., gt=0)
    notes: Optional[str] = "Raw Material Restock"
    description: Optional[str] = None


@router.get("/chefs")
def get_kitchen_chefs(current_user: Dict[str, Any] = Depends(km_guard)):
    """Returns active chefs for station-specific ingredient assignment."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT EmployeeID, Name, Shift
        FROM Staff
        WHERE Role = 'Chef' AND IsActive = 1
        ORDER BY EmployeeID ASC;
    """)
    chefs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"chefs": chefs}


@router.get("/inventory")
def get_raw_inventory(current_user: Dict[str, Any] = Depends(km_guard)):
    """Returns raw materials inventory with station assignment and shortage alert counters."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.IngredientID, i.IngredientName, i.NeedsRestock, i.AssignedChefID,
               s_assigned.Name AS AssignedChefName,
               i.ReportedBy_ChefID, s_rep.Name AS ReporterChefName, i.LastUpdated
        FROM Inventory i
        LEFT JOIN Staff s_assigned ON i.AssignedChefID = s_assigned.EmployeeID
        LEFT JOIN Staff s_rep ON i.ReportedBy_ChefID = s_rep.EmployeeID
        ORDER BY i.NeedsRestock DESC, i.IngredientName ASC;
    """)
    inventory = [dict(r) for r in cursor.fetchall()]

    # Shortages queue
    shortages = [item for item in inventory if item["NeedsRestock"] == 1]
    conn.close()

    return {
        "inventory": inventory,
        "shortages_count": len(shortages),
        "shortages": shortages
    }


@router.put("/inventory/{ingredient_id}/restock")
def update_ingredient_restock(
    ingredient_id: int,
    req: RestockStatusRequest,
    current_user: Dict[str, Any] = Depends(km_guard)
):
    """Marks ingredient restock status resolved (0) or active (1)."""
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Inventory 
            SET NeedsRestock = ?, ReportedBy_ChefID = NULL, LastUpdated = CURRENT_TIMESTAMP
            WHERE IngredientID = ?;
        """, (1 if req.needs_restock else 0, ingredient_id))

    return {"status": "success", "ingredient_id": ingredient_id, "needs_restock": req.needs_restock}


@router.post("/inventory")
def add_new_ingredient(
    req: AddIngredientRequest,
    current_user: Dict[str, Any] = Depends(km_guard)
):
    """Registers a new ingredient stock item into raw material inventory with chef assignment."""
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Inventory (IngredientName, NeedsRestock, AssignedChefID, LastUpdated)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP);
        """, (req.ingredient_name.strip(), 1 if req.needs_restock else 0, req.assigned_chef_id))
        ing_id = cursor.lastrowid

    return {
        "status": "success",
        "ingredient_id": ing_id,
        "ingredient_name": req.ingredient_name,
        "assigned_chef_id": req.assigned_chef_id
    }


@router.delete("/inventory/{ingredient_id}")
def delete_ingredient(
    ingredient_id: int,
    current_user: Dict[str, Any] = Depends(km_guard)
):
    """Removes an ingredient completely from raw material inventory."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT IngredientName FROM Inventory WHERE IngredientID = ?;", (ingredient_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Ingredient not found")
    ing_name = row["IngredientName"]
    conn.close()

    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Inventory WHERE IngredientID = ?;", (ingredient_id,))

    return {"status": "success", "ingredient_id": ingredient_id, "message": f"'{ing_name}' successfully removed from inventory."}


@router.get("/menu-requests")
def get_menu_requests(current_user: Dict[str, Any] = Depends(km_guard)):
    """Lists chef menu alteration proposals."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT mr.RequestID, mr.ChefID, s.Name AS ChefName, mr.DishName,
               mr.RequestType, mr.Reason, mr.Status, mr.CreatedAt
        FROM Menu_Requests mr
        JOIN Staff s ON mr.ChefID = s.EmployeeID
        ORDER BY CASE mr.Status WHEN 'Pending' THEN 1 ELSE 2 END, mr.CreatedAt DESC;
    """)
    requests = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"requests": requests}


@router.post("/menu-requests/{request_id}/action")
def process_menu_request(
    request_id: int,
    req: MenuRequestAction,
    current_user: Dict[str, Any] = Depends(km_guard)
):
    """
    Approves or Rejects a chef menu request.
    If Approved and RequestType is 'Add', adds the new dish into Menu_Items.
    If Approved and RequestType is 'Remove', sets IsAvailable = 0 for that dish.
    """
    if req.action not in ('Approved', 'Rejected'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Action must be 'Approved' or 'Rejected'.")

    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT RequestID, ChefID, DishName, RequestType, Status 
            FROM Menu_Requests 
            WHERE RequestID = ?;
        """, (request_id,))
        mr = cursor.fetchone()
        if not mr:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu request not found.")

        # Update Request Status
        cursor.execute("UPDATE Menu_Requests SET Status = ? WHERE RequestID = ?;", (req.action, request_id))

        msg = f"Request for '{mr['DishName']}' marked as {req.action}."

        # If Approved, update Menu_Items table
        if req.action == 'Approved':
            if mr["RequestType"] == 'Add':
                chef_id = req.assigned_chef_id or mr["ChefID"]
                cursor.execute("""
                    SELECT MenuItemID FROM Menu_Items WHERE LOWER(TRIM(ItemName)) = LOWER(TRIM(?));
                """, (mr["DishName"],))
                existing = cursor.fetchone()
                if existing:
                    cursor.execute("""
                        UPDATE Menu_Items 
                        SET Category = ?, Price = ?, StockQuantity = 10, IsAvailable = 1, AssignedChefID = ?, IsActive = 1
                        WHERE MenuItemID = ?;
                    """, (req.category, req.price, chef_id, existing["MenuItemID"]))
                else:
                    cursor.execute("""
                        INSERT INTO Menu_Items (ItemName, Category, Price, StockQuantity, IsAvailable, AssignedChefID, IsActive)
                        VALUES (?, ?, ?, 10, 1, ?, 1);
                    """, (mr["DishName"], req.category, req.price, chef_id))
                msg += f" Added to active menu under category '{req.category}' at Rs.{req.price}."
            elif mr["RequestType"] == 'Remove':
                cursor.execute("""
                    SELECT MenuItemID, ItemName FROM Menu_Items 
                    WHERE LOWER(TRIM(ItemName)) = LOWER(TRIM(?));
                """, (mr["DishName"],))
                matched = cursor.fetchone()
                if matched:
                    item_id = matched["MenuItemID"]
                    # Check if referenced in Order_Details
                    cursor.execute("SELECT COUNT(*) AS cnt FROM Order_Details WHERE MenuItemID = ?;", (item_id,))
                    order_count = cursor.fetchone()["cnt"]
                    if order_count == 0:
                        cursor.execute("DELETE FROM Shortage_Logs WHERE MenuItemID = ?;", (item_id,))
                        cursor.execute("DELETE FROM Menu_Items WHERE MenuItemID = ?;", (item_id,))
                        msg += f" Dish '{matched['ItemName']}' permanently removed from menu catalog."
                    else:
                        cursor.execute("""
                            UPDATE Menu_Items 
                            SET IsActive = 0, IsAvailable = 0 
                            WHERE MenuItemID = ?;
                        """, (item_id,))
                        msg += f" Dish '{matched['ItemName']}' removed from active menu."
                else:
                    msg += f" Dish '{mr['DishName']}' was not found in the active menu."

    return {"status": "success", "request_id": request_id, "action": req.action, "message": msg}


@router.get("/waste-log")
def get_waste_logs(current_user: Dict[str, Any] = Depends(km_guard)):
    """Returns waste tracking records and total financial losses from discarded dishes."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT w.WasteID, w.OrderDetailID, w.IngredientCost, w.LogTimestamp,
               m.ItemName, od.Quantity, od.CancellationReason,
               s_chef.Name AS ChefName, s_waiter.Name AS WaiterName
        FROM Waste_Log w
        LEFT JOIN Order_Details od ON w.OrderDetailID = od.OrderDetailID
        LEFT JOIN Menu_Items m ON od.MenuItemID = m.MenuItemID
        LEFT JOIN Staff s_chef ON od.PreparedBy_EmployeeID = s_chef.EmployeeID
        LEFT JOIN Orders o ON od.OrderID = o.OrderID
        LEFT JOIN Staff s_waiter ON o.WaiterID = s_waiter.EmployeeID
        ORDER BY w.LogTimestamp DESC;
    """)
    logs = [dict(r) for r in cursor.fetchall()]
    total_waste_loss = sum(item["IngredientCost"] for item in logs)
    conn.close()

    return {"waste_logs": logs, "total_waste_loss": round(total_waste_loss, 2)}


@router.post("/expenses")
def log_raw_material_purchase(
    req: LogExpenseRequest,
    current_user: Dict[str, Any] = Depends(km_guard)
):
    """Logs raw material inventory procurement costs into Purchase_Expenses."""
    desc = req.description.strip() if req.description and req.description.strip() else (req.notes.strip() if req.notes else "Raw Material Restock")
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Purchase_Expenses (ExpenseDate, ExpenseAmount, ExpenseType, Description)
            VALUES (?, ?, 'Raw Materials', ?);
        """, (req.expense_date, req.expense_amount, desc))
        exp_id = cursor.lastrowid

    return {
        "status": "success",
        "expense_id": exp_id,
        "amount": req.expense_amount,
        "expense_type": "Raw Materials",
        "description": desc,
        "message": f"Procurement expense of Rs.{req.expense_amount:.2f} logged."
    }


@router.get("/chef-ratings")
def get_kitchen_chef_ratings(current_user: Dict[str, Any] = Depends(km_guard)):
    """Returns chef production statistics and culinary scores from View_Chef_Performance."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM View_Chef_Performance ORDER BY CulinaryPerformancePoints DESC;")
    ratings = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"chef_ratings": ratings}
