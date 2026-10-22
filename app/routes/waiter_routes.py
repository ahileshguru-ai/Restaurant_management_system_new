"""
Waiter Operations & Floor Management API
=========================================
Implements Concurrency Isolation (Orders.WaiterID = :current_user_id),
Multi-Table Associations (Order_Tables M:N bridge), Item Additions,
Cancellation Triggers, Checkout Splits, and Verified Feedback Submission.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from database.db import (
    get_connection, create_order_with_tables_and_items,
    add_item_to_order, checkout_order, submit_order_feedback
)
from app.auth import require_roles

router = APIRouter(prefix="/api/waiter", tags=["Waiter Floor Operations"])
waiter_guard = require_roles(["Waiter", "Shop Manager"])


class CreateOrderItem(BaseModel):
    MenuItemID: int
    Quantity: int = 1


class CreateOrderRequest(BaseModel):
    customer_count: int = Field(..., gt=0)
    table_numbers: List[int] = Field(..., min_items=1)
    items: List[CreateOrderItem] = Field(..., min_items=1)


class AddItemRequest(BaseModel):
    menu_item_id: int
    quantity: int = Field(1, gt=0)


class CancelRequest(BaseModel):
    reason: str = Field(..., min_length=2)


class CheckoutRequest(BaseModel):
    cash_amount: float = Field(..., ge=0)
    upi_amount: float = Field(..., ge=0)


class FeedbackRequest(BaseModel):
    customer_name: Optional[str] = None
    phone_number: Optional[str] = None
    service_rating: Optional[int] = Field(None, ge=1, le=5)
    food_rating: Optional[int] = Field(None, ge=1, le=5)
    ambience_rating: Optional[int] = Field(None, ge=1, le=5)
    cleanliness_rating: Optional[int] = Field(None, ge=1, le=5)
    review_text: Optional[str] = None


@router.get("/menu")
def get_centralized_menu(current_user: Dict[str, Any] = Depends(waiter_guard)):
    """Returns centralized restaurant menu with availability and assigned chef info."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.MenuItemID, m.ItemName, m.Category, m.Price, m.IsAvailable,
               m.AssignedChefID, s.Name AS AssignedChefName
        FROM Menu_Items m
        JOIN Staff s ON m.AssignedChefID = s.EmployeeID
        WHERE m.IsActive = 1
        ORDER BY m.Category, m.ItemName;
    """)
    items = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"menu": items}


@router.get("/tables")
def get_tables_status(current_user: Dict[str, Any] = Depends(waiter_guard)):
    """Returns all floor tables, seating capacities, and real-time statuses."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.TableNumber, t.SeatingCapacity, t.CurrentStatus,
               GROUP_CONCAT(ot.OrderID) AS ActiveOrderIDs
        FROM Tables t
        LEFT JOIN Order_Tables ot ON t.TableNumber = ot.TableNumber
        LEFT JOIN Orders o ON ot.OrderID = o.OrderID AND o.OrderStatus = 'In Progress'
        GROUP BY t.TableNumber
        ORDER BY t.TableNumber;
    """)
    tables = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"tables": tables}


@router.get("/orders")
def get_waiter_active_orders(current_user: Dict[str, Any] = Depends(waiter_guard)):
    """
    Returns open tickets isolated strictly to the calling waiter:
    Filtered by Orders.WaiterID = :current_user_id (David Ferraiolo RBAC & Jim Gray Isolation).
    Shop Manager can view all orders.
    """
    waiter_id = current_user["EmployeeID"]
    is_shop_manager = current_user["RoleName"] == "Shop Manager"

    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT o.OrderID, o.WaiterID, s.Name AS WaiterName, o.CustomerCount,
               o.OrderTimestamp, o.CashAmount, o.UPIAmount, o.OrderStatus,
               GROUP_CONCAT(DISTINCT ot.TableNumber) AS TableNumbersStr,
               COALESCE(SUM(CASE WHEN od.ItemStatus != 'Cancelled' THEN od.Subtotal ELSE 0 END), 0) AS BillTotal
        FROM Orders o
        JOIN Staff s ON o.WaiterID = s.EmployeeID
        LEFT JOIN Order_Tables ot ON o.OrderID = ot.OrderID
        LEFT JOIN Order_Details od ON o.OrderID = od.OrderID
        WHERE o.OrderStatus = 'In Progress'
    """
    params = []
    if not is_shop_manager:
        sql += " AND o.WaiterID = ?"
        params.append(waiter_id)

    sql += " GROUP BY o.OrderID ORDER BY o.OrderTimestamp DESC;"

    cursor.execute(sql, tuple(params))
    orders = [dict(r) for r in cursor.fetchall()]

    # Fetch detailed line items for each order
    for ord_obj in orders:
        ord_id = ord_obj["OrderID"]
        cursor.execute("""
            SELECT od.OrderDetailID, od.MenuItemID, m.ItemName, od.Quantity,
                   od.Subtotal, od.PreparedBy_EmployeeID, s.Name AS ChefName,
                   od.ItemStatus, od.CancellationReason
            FROM Order_Details od
            JOIN Menu_Items m ON od.MenuItemID = m.MenuItemID
            JOIN Staff s ON od.PreparedBy_EmployeeID = s.EmployeeID
            WHERE od.OrderID = ?
            ORDER BY od.OrderDetailID;
        """, (ord_id,))
        ord_obj["items"] = [dict(r) for r in cursor.fetchall()]
        ord_obj["tables"] = [int(t) for t in ord_obj["TableNumbersStr"].split(",")] if ord_obj["TableNumbersStr"] else []

    conn.close()
    return {"orders": orders}


@router.post("/orders")
def create_new_order(
    req: CreateOrderRequest,
    current_user: Dict[str, Any] = Depends(waiter_guard)
):
    """
    Initializes a new order across one or more physical tables.
    Wrapped in ACID transaction.
    """
    waiter_id = current_user["EmployeeID"]
    items_payload = [{"MenuItemID": it.MenuItemID, "Quantity": it.Quantity} for it in req.items]

    try:
        res = create_order_with_tables_and_items(
            waiter_id=waiter_id,
            customer_count=req.customer_count,
            table_numbers=req.table_numbers,
            items=items_payload
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/orders/{order_id}/items")
def add_dish_to_order(
    order_id: int,
    req: AddItemRequest,
    current_user: Dict[str, Any] = Depends(waiter_guard)
):
    """Adds a dish to an existing active ticket without re-creating the order."""
    try:
        res = add_item_to_order(order_id, req.menu_item_id, req.quantity)
        return res
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/order-details/{detail_id}/cancel-request")
def request_dish_cancellation(
    detail_id: int,
    req: CancelRequest,
    current_user: Dict[str, Any] = Depends(waiter_guard)
):
    """
    Triggers Chef Deletion-Consent Flow:
    Waiters cannot hard-delete active dishes. Updates status to 'Cancel Requested'.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT od.OrderDetailID, od.ItemStatus, od.OrderID, m.ItemName
        FROM Order_Details od
        JOIN Menu_Items m ON od.MenuItemID = m.MenuItemID
        WHERE od.OrderDetailID = ?;
    """, (detail_id,))
    item = cursor.fetchone()

    if not item:
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order item not found.")

    if item["ItemStatus"] in ('Ready', 'Cancelled'):
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot request cancellation for item currently in '{item['ItemStatus']}' status."
        )

    cursor.execute("""
        UPDATE Order_Details
        SET ItemStatus = 'Cancel Requested', CancellationReason = ?
        WHERE OrderDetailID = ?;
    """, (req.reason.strip(), detail_id))
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "detail_id": detail_id,
        "message": f"Cancellation requested for {item['ItemName']}. Forwarded to Kitchen Display for Chef approval."
    }


@router.delete("/order-details/{detail_id}")
def delete_order_item(
    detail_id: int,
    current_user: Dict[str, Any] = Depends(waiter_guard)
):
    """
    Deletes an item from an active order.
    The Pre-Cooking Edit Block (Trigger) ensures this is physically blocked
    once the kitchen status moves past 'Pending'.
    """
    import sqlite3
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Order_Details WHERE OrderDetailID = ?;", (detail_id,))
        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order item not found.")
        conn.commit()
        conn.close()
        return {"status": "success", "message": "Item successfully deleted."}
    except (sqlite3.DatabaseError, Exception) as e:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pre-Cooking Edit Block Trigger: {str(e)}"
        )


@router.post("/orders/{order_id}/checkout")
def process_checkout(
    order_id: int,
    req: CheckoutRequest,
    current_user: Dict[str, Any] = Depends(waiter_guard)
):
    """
    Finalizes order billing, recording Cash and UPI splits,
    marking the order Completed and freeing tables back to Available.
    """
    try:
        res = checkout_order(order_id, req.cash_amount, req.upi_amount)
        return res
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/orders/{order_id}/feedback")
def submit_feedback(
    order_id: int,
    req: FeedbackRequest,
    current_user: Dict[str, Any] = Depends(waiter_guard)
):
    """
    Submits verified customer feedback.
    Enforces the Anti-Fraud Gatekeeper constraint physically preventing padded ratings.
    """
    try:
        res = submit_order_feedback(
            order_id=order_id,
            customer_name=req.customer_name,
            phone_number=req.phone_number,
            service_rating=req.service_rating,
            food_rating=req.food_rating,
            ambience_rating=req.ambience_rating,
            cleanliness_rating=req.cleanliness_rating,
            review_text=req.review_text
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/daily-summary")
def get_daily_collection_summary(current_user: Dict[str, Any] = Depends(waiter_guard)):
    """Returns today's collections and customers served by the active waiter."""
    waiter_id = current_user["EmployeeID"]
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            COALESCE(SUM(CustomerCount), 0) AS TodayCustomers,
            COALESCE(SUM(CashAmount), 0) AS TodayCash,
            COALESCE(SUM(UPIAmount), 0) AS TodayUPI,
            COALESCE(SUM(CashAmount + UPIAmount), 0) AS TodayTotal,
            COUNT(*) AS OrdersHandled
        FROM Orders
        WHERE WaiterID = ? AND DATE(OrderTimestamp) = DATE('now');
    """, (waiter_id,))
    summary = dict(cursor.fetchone())
    conn.close()
    return {"summary": summary}
