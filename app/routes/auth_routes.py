"""
Authentication & Single-Seat Handover Routes
=============================================
Handles credentials, JWT session token generation, demo profile loading,
and single-seat administrative transitions.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from database.db import get_connection, execute_handover_protocol
from app.auth import (
    verify_password, hash_password, create_access_token,
    get_current_user, require_roles
)

router = APIRouter(prefix="/api/auth", tags=["Authentication & Handover"])


class LoginRequest(BaseModel):
    username: str
    password: str
    expected_role: Optional[str] = None


class HandoverRequest(BaseModel):
    admin_role_name: str = Field(..., description="'Shop Manager' or 'Kitchen Manager'")
    new_employee_name: str
    new_username: str
    new_password: str
    shift: str = "Morning Shift"
    salary: float = 50000.00


@router.post("/login")
def login(req: LoginRequest):
    """Authenticates credentials against cryptographic password hashes."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.UserID, u.Username, u.PasswordHash, u.EmployeeID, u.RoleID,
               r.RoleName, s.Name AS StaffName, s.IsActive
        FROM Users u
        JOIN Roles r ON u.RoleID = r.RoleID
        JOIN Staff s ON u.EmployeeID = s.EmployeeID
        WHERE u.Username = ?;
    """, (req.username.strip(),))
    user = cursor.fetchone()
    conn.close()

    if not user or not verify_password(req.password, user["PasswordHash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password."
        )

    if not user["IsActive"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is associated with a retired staff member."
        )

    if req.expected_role:
        expected = req.expected_role.strip().lower()
        actual = user["RoleName"].strip().lower()
        if expected != actual:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied: Account '{user['Username']}' is registered as '{user['RoleName']}', not '{req.expected_role}'. Please select the {user['RoleName']} login option."
            )

    token_data = {
        "user_id": user["UserID"],
        "employee_id": user["EmployeeID"],
        "username": user["Username"],
        "role": user["RoleName"],
        "staff_name": user["StaffName"]
    }
    access_token = create_access_token(token_data)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": token_data
    }


@router.get("/me")
def get_my_profile(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Returns current active authenticated identity and permissions."""
    return {"user": current_user}


@router.get("/demo-profiles")
def get_demo_profiles():
    """Lists all active personnel accounts for instant role-switching or custom login."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.UserID, u.Username, r.RoleName, s.Name AS StaffName, s.EmployeeID,
               CASE 
                   WHEN u.Username = 'shopmanager' THEN 'manager123'
                   WHEN u.Username = 'kitchenmgr' THEN 'kitchen123'
                   WHEN u.Username = 'chef_vikram' THEN 'chef123'
                   WHEN u.Username = 'chef_meera' THEN 'chef123'
                   WHEN u.Username = 'waiter_rahul' THEN 'waiter123'
                   WHEN u.Username = 'waiter_priya' THEN 'waiter123'
                   ELSE ''
               END AS DemoPassword
        FROM Users u
        JOIN Roles r ON u.RoleID = r.RoleID
        JOIN Staff s ON u.EmployeeID = s.EmployeeID
        WHERE s.IsActive = 1
        ORDER BY r.RoleID, s.EmployeeID;
    """)
    profiles = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"profiles": profiles}


@router.post("/handover")
def execute_single_seat_handover(
    req: HandoverRequest,
    current_user: Dict[str, Any] = Depends(require_roles(["Shop Manager"]))
):
    """
    Executes the transactional Single-Seat Handover Protocol.
    Strictly isolated to Shop Manager authorization.
    """
    if req.admin_role_name not in ('Shop Manager', 'Kitchen Manager'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Handover protocol only applies to Single-Seat administrative roles ('Shop Manager', 'Kitchen Manager')."
        )

    new_hash = hash_password(req.new_password)
    try:
        result = execute_handover_protocol(
            admin_role_name=req.admin_role_name,
            new_employee_name=req.new_employee_name,
            new_username=req.new_username,
            new_password_hash=new_hash,
            shift=req.shift,
            salary=req.salary
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


class RegisterStaffRequest(BaseModel):
    name: str = Field(..., min_length=2)
    role: str = Field(..., description="'Shop Manager', 'Kitchen Manager', 'Chef', 'Waiter'")
    shift: str = "Morning Shift"
    salary: float = Field(30000.00, ge=0)
    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=4)


@router.post("/register-staff")
def register_new_staff_and_user(
    req: RegisterStaffRequest,
    current_user: Dict[str, Any] = Depends(require_roles(["Shop Manager"]))
):
    """
    Registers a new staff member and creates their login credentials.
    STRICT SECURITY: Exclusively permitted to the Shop Manager.
    - For Waiter / Chef (unlimited concurrency): directly inserts Staff & Users records.
    - For Kitchen Manager / Shop Manager (Single-Seat constraint): executes Single-Seat Handover.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Verify role exists
    cursor.execute("SELECT RoleID FROM Roles WHERE RoleName = ?;", (req.role,))
    role_row = cursor.fetchone()
    if not role_row:
        conn.close()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid role '{req.role}'. Must be Shop Manager, Kitchen Manager, Chef, or Waiter.")

    role_id = role_row["RoleID"]

    # Check username uniqueness
    cursor.execute("SELECT UserID FROM Users WHERE Username = ?;", (req.username.strip(),))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Username '{req.username}' is already taken.")

    conn.close()

    new_hash = hash_password(req.password)

    # If Single-Seat role (Shop Manager or Kitchen Manager), perform handover if one already exists
    if req.role in ('Shop Manager', 'Kitchen Manager'):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT UserID FROM Users WHERE RoleID = ?;", (role_id,))
        existing_mgr = cursor.fetchone()
        conn.close()

        if existing_mgr:
            # Single-seat handover protocol
            try:
                res = execute_handover_protocol(
                    admin_role_name=req.role,
                    new_employee_name=req.name.strip(),
                    new_username=req.username.strip(),
                    new_password_hash=new_hash,
                    shift=req.shift,
                    salary=req.salary
                )
                return {
                    "status": "success",
                    "message": f"Single-seat {req.role} handover completed. New user '{req.username}' is now active.",
                    "details": res
                }
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    # Standard creation for Waiter / Chef or initial manager
    from database.db import transaction
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Staff (Name, RoleID, Role, Shift, IsActive, Salary)
            VALUES (?, ?, ?, ?, 1, ?);
        """, (req.name.strip(), role_id, req.role, req.shift, req.salary))
        emp_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO Users (EmployeeID, Username, PasswordHash, RoleID)
            VALUES (?, ?, ?, ?);
        """, (emp_id, req.username.strip(), new_hash, role_id))
        user_id = cursor.lastrowid

    return {
        "status": "success",
        "message": f"Successfully created {req.role} account for {req.name} with username '{req.username}'.",
        "user_id": user_id,
        "employee_id": emp_id,
        "username": req.username,
        "role": req.role
    }


class UpdateCredentialsRequest(BaseModel):
    user_id: int
    new_username: Optional[str] = None
    new_password: Optional[str] = None


@router.put("/update-credentials")
def update_user_credentials(
    req: UpdateCredentialsRequest,
    current_user: Dict[str, Any] = Depends(require_roles(["Shop Manager"]))
):
    """
    Updates the username and/or password for any registered user.
    STRICT SECURITY: Exclusively permitted to the Shop Manager.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT UserID, Username FROM Users WHERE UserID = ?;", (req.user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    if req.new_username and req.new_username.strip() != user["Username"]:
        # Check uniqueness
        cursor.execute("SELECT UserID FROM Users WHERE Username = ? AND UserID != ?;", (req.new_username.strip(), req.user_id))
        if cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Username '{req.new_username}' is already in use.")

    conn.close()

    from database.db import transaction
    with transaction() as conn:
        cursor = conn.cursor()
        if req.new_username and req.new_username.strip():
            cursor.execute("UPDATE Users SET Username = ? WHERE UserID = ?;", (req.new_username.strip(), req.user_id))
        if req.new_password and req.new_password.strip():
            new_hash = hash_password(req.new_password.strip())
            cursor.execute("UPDATE Users SET PasswordHash = ? WHERE UserID = ?;", (new_hash, req.user_id))

    return {
        "status": "success",
        "message": f"Credentials updated successfully for User #{req.user_id}."
    }


@router.post("/reset-database")
def reset_database_to_seed():
    """Resets the database to pristine 3NF schema and default seed data."""
    from database.db import init_db
    try:
        init_db(force_reset=True)
        return {
            "status": "success",
            "message": "Database successfully reset to initial schema and seed data! All default logins are restored."
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

