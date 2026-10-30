"""
Chef Operations & Kitchen Display System (KDS) API
===================================================
Implements Assigned Chef Queue Filtering (AssignedChefID),
Production Status Progressions (Pending -> Cooking -> Ready),
Chef Deletion-Consent Flow with Waste Auditing, Out-of-Stock Atomic
Transactions into Shortage_Logs, and Menu Alteration Requests.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from database.db import (
    get_connection, transaction, chef_review_cancel_consent,
    chef_discard_order_item, out_of_stock_atomic_transaction,
    update_menu_item_stock
)
from app.auth import require_roles

router = APIRouter(prefix="/api/chef", tags=["Chef KDS Operations"])
chef_guard = require_roles(["Chef", "Kitchen Manager", "Shop Manager"])


class StatusUpdateRequest(BaseModel):
    new_status: str = Field(..., description="'Cooking' or 'Ready'")


class CancelConsentRequest(BaseModel):
    approved: bool = Field(..., description="True if cancellation accepted; False if denied")


class DiscardItemRequest(BaseModel):
    reason: Optional[str] = Field(default="Food discarded during cooking", description="Reason for cancellation and waste audit")


class OutOfStockRequest(BaseModel):
    reason: str = Field(..., min_length=3)


class ToggleStockRequest(BaseModel):
    is_available: bool
    reason: Optional[str] = "Restocked"


class UpdateStockRequest(BaseModel):
    stock_quantity: int = Field(..., ge=0, description="Available portions present in stock")


class MenuProposalRequest(BaseModel):
    dish_name: str = Field(..., min_length=1)
    request_type: str = Field(..., description="'Add' or 'Remove'")
    reason: Optional[str] = Field(default="", description="Operational justification")


class RestockFlagRequest(BaseModel):
    needs_restock: bool


@router.get("/queue")
def get_chef_assigned_queue(current_user: Dict[str, Any] = Depends(chef_guard)):
    """
    Returns active dish queue filtered by AssignedChefID.
    Chef Vikram sees South Indian/Curries, Chef Meera sees Biryanis/Breads.
    """
    chef_id = current_user["EmployeeID"]
    is_admin = current_user["RoleName"] in ("Kitchen Manager", "Shop Manager")

    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT od.OrderDetailID, od.OrderID, od.MenuItemID, m.ItemName, m.Category,
               od.Quantity, od.Subtotal, od.ItemStatus, od.CancellationReason,
               o.OrderTimestamp, o.CustomerCount,
               s_waiter.Name AS WaiterName,
               GROUP_CONCAT(ot.TableNumber) AS TablesStr
        FROM Order_Details od
        JOIN Menu_Items m ON od.MenuItemID = m.MenuItemID
        JOIN Orders o ON od.OrderID = o.OrderID
        JOIN Staff s_waiter ON o.WaiterID = s_waiter.EmployeeID
        LEFT JOIN Order_Tables ot ON o.OrderID = ot.OrderID
        WHERE o.OrderStatus = 'In Progress' AND od.ItemStatus != 'Cancelled'
    """
    params = []
    if not is_admin:
        sql += " AND od.PreparedBy_EmployeeID = ?"
        params.append(chef_id)

    sql += """
        GROUP BY od.OrderDetailID
        ORDER BY 
            CASE od.ItemStatus 
                WHEN 'Cancel Requested' THEN 1
                WHEN 'Pending' THEN 2
                WHEN 'Cooking' THEN 3
                WHEN 'Ready' THEN 4
                ELSE 5
            END,
            od.OrderDetailID ASC;
    """

    cursor.execute(sql, tuple(params))
    queue = [dict(r) for r in cursor.fetchall()]
    conn.close()

    for item in queue:
        item["tables"] = [int(t) for t in item["TablesStr"].split(",")] if item["TablesStr"] else []

    return {"queue": queue, "assigned_chef_id": chef_id}


@router.put("/order-details/{detail_id}/status")
def update_dish_status(
    detail_id: int,
    req: StatusUpdateRequest,
    current_user: Dict[str, Any] = Depends(chef_guard)
):
    """Updates assigned item status along the kitchen lifecycle (Pending -> Cooking -> Ready)."""
    if req.new_status not in ('Pending', 'Cooking', 'Ready'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status must be one of 'Pending', 'Cooking', or 'Ready'."
        )

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT od.OrderDetailID, od.ItemStatus, m.ItemName, od.PreparedBy_EmployeeID
        FROM Order_Details od
        JOIN Menu_Items m ON od.MenuItemID = m.MenuItemID
        WHERE od.OrderDetailID = ?;
    """, (detail_id,))
    item = cursor.fetchone()

    if not item:
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order detail not found.")

    # Verify authorization
    chef_id = current_user["EmployeeID"]
    if current_user["RoleName"] == "Chef" and item["PreparedBy_EmployeeID"] != chef_id:
        conn.close()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dish is assigned to a different chef.")

    cursor.execute("UPDATE Order_Details SET ItemStatus = ? WHERE OrderDetailID = ?;", (req.new_status, detail_id))
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "detail_id": detail_id,
        "item_name": item["ItemName"],
        "new_status": req.new_status
    }


@router.post("/order-details/{detail_id}/consent")
def handle_cancellation_consent(
    detail_id: int,
    req: CancelConsentRequest,
    current_user: Dict[str, Any] = Depends(chef_guard)
):
    """
    Chef Deletion-Consent Flow:
    Approved -> Status 'Cancelled' + log to Waste_Log
    Denied -> Status 'Cooking' / 'Ready' (retained on bill)
    """
    try:
        res = chef_review_cancel_consent(detail_id, req.approved)
        return res
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/order-details/{detail_id}/discard")
def discard_order_item(
    detail_id: int,
    req: DiscardItemRequest,
    current_user: Dict[str, Any] = Depends(chef_guard)
):
    """
    Direct Chef Food Discard / Cancellation Flow:
    Marks dish as 'Cancelled', logs estimated raw ingredient loss to Waste_Log,
    and removes it from active cooking queue. Discard immediately appears in
    Kitchen Manager's Discarded Food & Waste Log.
    """
    chef_id = current_user["EmployeeID"]
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT od.OrderDetailID, od.PreparedBy_EmployeeID, m.ItemName
        FROM Order_Details od
        JOIN Menu_Items m ON od.MenuItemID = m.MenuItemID
        WHERE od.OrderDetailID = ?;
    """, (detail_id,))
    item = cursor.fetchone()
    conn.close()

    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order detail not found.")

    is_admin = current_user["RoleName"] in ("Kitchen Manager", "Shop Manager")
    if not is_admin and item["PreparedBy_EmployeeID"] != chef_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dish is assigned to a different chef station.")

    # Chefs cannot cancel orders directly. Waiters handle customer cancellations.
    if current_user["RoleName"] == "Chef":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chefs are not permitted to cancel orders. Only waiters can process cancellations for customer orders."
        )

    try:
        res = chef_discard_order_item(detail_id, req.reason or "Food discarded during cooking", chef_id)
        return res
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/menu")
def get_chef_menu(current_user: Dict[str, Any] = Depends(chef_guard)):
    """Returns dishes prepared by this chef, with stock availability controls."""
    chef_id = current_user["EmployeeID"]
    is_admin = current_user["RoleName"] in ("Kitchen Manager", "Shop Manager")

    conn = get_connection()
    cursor = conn.cursor()
    if is_admin:
        cursor.execute("SELECT * FROM Menu_Items WHERE IsActive = 1 ORDER BY Category, ItemName;")
    else:
        cursor.execute("SELECT * FROM Menu_Items WHERE AssignedChefID = ? AND IsActive = 1 ORDER BY Category, ItemName;", (chef_id,))
    dishes = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"dishes": dishes}


@router.get("/active-menu-dishes")
def get_active_menu_dishes(current_user: Dict[str, Any] = Depends(chef_guard)):
    """Returns all active dishes currently on the menu for selection in removal proposals."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.MenuItemID, m.ItemName, m.Category, m.Price, m.StockQuantity, m.IsAvailable,
               s.Name AS AssignedChefName
        FROM Menu_Items m
        LEFT JOIN Staff s ON m.AssignedChefID = s.EmployeeID
        WHERE m.IsActive = 1
        ORDER BY m.Category, m.ItemName;
    """)
    dishes = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"dishes": dishes}


@router.put("/menu/{item_id}/stock")
def set_dish_stock(
    item_id: int,
    req: UpdateStockRequest,
    current_user: Dict[str, Any] = Depends(chef_guard)
):
    """
    Updates the numerical stock quantity for a dish in advance.
    - Automatically marks dish as in-stock if stock > 0.
    - Automatically marks dish as out-of-stock if stock == 0.
    - Can be updated at any time by the assigned chef or kitchen manager.
    """
    chef_id = current_user["EmployeeID"]
    is_admin = current_user["RoleName"] in ("Kitchen Manager", "Shop Manager")
    try:
        res = update_menu_item_stock(item_id, req.stock_quantity, None if is_admin else chef_id)
        return res
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/menu/{item_id}/out-of-stock")
def flag_dish_out_of_stock(
    item_id: int,
    req: OutOfStockRequest,
    current_user: Dict[str, Any] = Depends(chef_guard)
):
    """
    Executes Out-of-Stock Atomic Transaction:
    Toggles IsAvailable = FALSE, sets StockQuantity = 0, and atomically inserts shortage incident into Shortage_Logs.
    """
    chef_id = current_user["EmployeeID"]
    try:
        res = out_of_stock_atomic_transaction(item_id, chef_id, req.reason)
        return res
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/menu/{item_id}/restore-stock")
def restore_dish_stock(
    item_id: int,
    current_user: Dict[str, Any] = Depends(chef_guard)
):
    """Restores dish back to available with a default replenished stock of 10 portions."""
    chef_id = current_user["EmployeeID"]
    is_admin = current_user["RoleName"] in ("Kitchen Manager", "Shop Manager")
    try:
        res = update_menu_item_stock(item_id, 10, None if is_admin else chef_id)
        return res
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/menu-requests")
def submit_menu_alteration_request(
    req: MenuProposalRequest,
    current_user: Dict[str, Any] = Depends(chef_guard)
):
    """Submits a dish addition or removal request for Kitchen Manager review."""
    if req.request_type not in ('Add', 'Remove'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request type must be 'Add' or 'Remove'.")

    chef_id = current_user["EmployeeID"]
    dish_name = req.dish_name.strip()
    reason_clean = (req.reason or "").strip()
    if not reason_clean:
        reason_clean = "Operational menu review"

    if req.request_type == 'Remove':
        # Verify the dish actually exists on the active menu
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ItemName FROM Menu_Items 
            WHERE LOWER(TRIM(ItemName)) = LOWER(TRIM(?)) AND IsActive = 1;
        """, (dish_name,))
        existing_dish = cursor.fetchone()
        conn.close()
        if not existing_dish:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Dish '{dish_name}' is not currently present on the active restaurant menu."
            )
        dish_name = existing_dish["ItemName"]

    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Menu_Requests (ChefID, DishName, RequestType, Reason, Status, CreatedAt)
            VALUES (?, ?, ?, ?, 'Pending', CURRENT_TIMESTAMP);
        """, (chef_id, dish_name, req.request_type, reason_clean))
        req_id = cursor.lastrowid

    return {
        "status": "success",
        "request_id": req_id,
        "message": f"Menu request for '{dish_name}' submitted for Kitchen Manager approval."
    }


@router.get("/inventory")
def get_chef_inventory(current_user: Dict[str, Any] = Depends(chef_guard)):
    """Lists ingredients assigned specifically to the logged-in chef (or shared items)."""
    chef_id = current_user["EmployeeID"]
    is_admin = current_user["RoleName"] in ("Kitchen Manager", "Shop Manager")

    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT i.IngredientID, i.IngredientName, i.NeedsRestock, i.AssignedChefID,
               s_assigned.Name AS AssignedChefName,
               i.ReportedBy_ChefID, s_rep.Name AS ReporterName, i.LastUpdated
        FROM Inventory i
        LEFT JOIN Staff s_assigned ON i.AssignedChefID = s_assigned.EmployeeID
        LEFT JOIN Staff s_rep ON i.ReportedBy_ChefID = s_rep.EmployeeID
    """
    params = []
    if not is_admin:
        sql += " WHERE (i.AssignedChefID = ? OR i.AssignedChefID IS NULL)"
        params.append(chef_id)

    sql += " ORDER BY i.NeedsRestock DESC, i.IngredientName ASC;"

    cursor.execute(sql, tuple(params))
    items = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"inventory": items, "assigned_chef_id": chef_id}


@router.put("/inventory/{ingredient_id}/restock-flag")
def toggle_ingredient_restock_flag(
    ingredient_id: int,
    req: RestockFlagRequest,
    current_user: Dict[str, Any] = Depends(chef_guard)
):
    """Chefs can flag ingredients as needing restock."""
    chef_id = current_user["EmployeeID"]
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Inventory 
            SET NeedsRestock = ?, ReportedBy_ChefID = ?, LastUpdated = CURRENT_TIMESTAMP
            WHERE IngredientID = ?;
        """, (1 if req.needs_restock else 0, chef_id if req.needs_restock else None, ingredient_id))

    return {
        "status": "success",
        "ingredient_id": ingredient_id,
        "needs_restock": req.needs_restock
    }
