# Role-Based Relational Database Architecture for Modern Restaurant Management

> **Course Context:** Database System Design  
> **Theoretical Anchors:** Edgar F. Codd (3NF Normalization), David Ferraiolo & Richard Kuhn (RBAC Security), Jim Gray (ACID Transactions & Concurrency)  
> **Implementation Tool:** Google Antigravity Agentic IDE  
> **Aesthetic Theme:** The White-and-Green Bubble UI Design System  

---

## 1. System Architecture Overview

This project implements a complete **3-Tier Layered Architecture** strictly conforming to relational database principles, role-based security isolation, and transactional ACID boundaries:

```
+-----------------------------------------------------------------------------------+
|                            PRESENTATION LAYER (FRONTEND)                          |
|     Responsive White-and-Green Bubble UI with Hardware Viewport Presets:          |
|     - Waiter Mobile (360px - 480px)        - Kitchen Manager Tablet (768px-1024px)|
|     - Chef KDS Landscape (768px-1024px+)   - Shop Manager Desktop (1280px+)       |
+-----------------------------------------------------------------------------------+
                                        |  RESTful JSON API / JWT Bearer Auth
                                        v
+-----------------------------------------------------------------------------------+
|                           APPLICATION LOGIC LAYER (API)                           |
|     Python FastAPI Middle-Tier:                                                   |
|     - Connection Pooling & SQLite/MySQL/PostgreSQL Dialect Engines                |
|     - Ferraiolo-Kuhn JWT RBAC Verification & Dependency Guards                    |
|     - Jim Gray ACID Transaction Blocks (BEGIN IMMEDIATE / COMMIT / ROLLBACK)      |
+-----------------------------------------------------------------------------------+
                                        |  SQL DDL / DML / Views / Foreign Keys
                                        v
+-----------------------------------------------------------------------------------+
|                             DATA LAYER (RELATIONAL DBMS)                          |
|     Strictly Normalized 3rd Normal Form (3NF) Database:                           |
|     - 14 Core & Bridge Tables with CHECK & UNIQUE Gatekeepers                     |
|     - Anti-Fraud Feedback Gatekeeper Constraint                                   |
|     - 4 Automated SQL Business Intelligence Views (Views 5.1 - 5.4)               |
+-----------------------------------------------------------------------------------+
```

---

## 2. Theoretical Computer Science Anchors

1. **Relational Normalization (Edgar F. Codd):**
   - The entire relational schema is strictly organized in **3rd Normal Form (3NF)**.
   - All non-key attributes are fully functionally dependent on primary keys (1NF & 2NF satisfied) with zero transitive dependencies (3NF satisfied).
   - Eliminates update, insertion, and deletion anomalies across multi-table (`Order_Tables`) and multi-chef (`Order_Details`) operations.

2. **Role-Based Access Control (David Ferraiolo & Richard Kuhn):**
   - Authentication credentials (`Users`) are strictly decoupled from operational personnel records (`Staff`).
   - Cryptographic password hashing (`bcrypt`) protects all credentials.
   - Roles matrix isolates data access at both database and application levels without credential sharing.

3. **Concurrency & ACID Guarantees (Jim Gray):**
   - Multi-step operations (multi-table order creation, chef cancellation consent, out-of-stock toggling, and single-seat handover) are wrapped in atomic transaction boundaries (`BEGIN IMMEDIATE ... COMMIT`).
   - Row-level isolation ensures waitstaff can spin up overlapping tickets concurrently without seeing or corrupting peer records (`Orders.WaiterID = :current_user_id`).

---

## 3. Relational Schema & 14 Core/Bridge Tables

```
+------------------+         1:N        +-------------------+
|      Roles       |------------------->|       Users       |
+------------------+                    +-------------------+
                                                  |
                                                  | 1:1
                                                  v
+-----------------------+               +-------------------+
|       Inventory       |               |       Staff       |
+-----------------------+               +-------------------+
| IngredientID (PK)     |                         ^
| IngredientName        |                         | 1:N
| NeedsRestock (BOOL)   |       +-----------------+-----------------+
| ReportedBy_ChefID(FK) |       | (AssignedChefID)| (WaiterID)      |
+-----------------------+       v                 v                 v
          ^               +------------+    +------------+    +---------------+
          |               | Menu_Items |    |   Orders   |    | Order_Details |
          |               +------------+    +------------+    +---------------+
+-----------------------+       ^                 | 1:N             |
|     Shortage_Logs     |       |                 |                 |
+-----------------------+       |                 v                 v
| LogID (PK)            |       |           +-------------------------------+
| MenuItemID (FK)       |-------+           |         Order_Tables          |
| ChefID (FK)           |                   +-------------------------------+
+-----------------------+
```

### Table DDL Summary:
| # | Table Name | Type | Key Constraints | Purpose & Schema Integrity |
|---|------------|------|-----------------|----------------------------|
| 1 | `Roles` | Core | `RoleID` (PK), `RoleName` (UNIQUE) | Ferraiolo-Kuhn role definitions |
| 2 | `Staff` | Core | `EmployeeID` (PK), `RoleID` (FK), `Salary` (CHECK >= 0) | Personnel records and active/retired status |
| 3 | `Users` | Core | `UserID` (PK), `EmployeeID` (FK, UNIQUE), `Username` (UNIQUE) | Decoupled bcrypt credentials |
| 4 | `Menu_Items` | Core | `MenuItemID` (PK), `AssignedChefID` (FK), `Price` (CHECK > 0), `StockQuantity` (CHECK >= 0) | Dish catalog, numerical stock, and chef routing |
| 5 | `Inventory` | Core | `IngredientID` (PK), `ReportedBy_ChefID` (FK) | Raw material restock monitoring |
| 6 | `Shortage_Logs` | Core | `LogID` (PK), `MenuItemID` (FK), `ChefID` (FK) | Out-of-stock atomic incident audits |
| 7 | `Menu_Requests` | Bridge | `RequestID` (PK), `ChefID` (FK), `RequestType` (CHECK) | Chef proposals for add/remove dishes |
| 8 | `Tables` | Core | `TableNumber` (PK), `SeatingCapacity` (CHECK > 0) | Dining floor table allocation & status |
| 9 | `Orders` | Core | `OrderID` (PK), `WaiterID` (FK), `CashAmount`, `UPIAmount` | Customer tickets and payment splits |
| 10 | `Order_Tables` | M:N Bridge | Composite PK `(OrderID, TableNumber)` | Resolves 1-to-many physical table splitting |
| 11 | `Order_Details` | M:N Bridge | `OrderDetailID` (PK), `OrderID` (FK), `UnitPrice` (Snapshot) | Tracks quantity, unit price snapshot, chef output, and dish status |
| 12 | `Feedback` | Core | `FeedbackID` (PK), `OrderID` (FK, UNIQUE) | **Anti-Fraud Gatekeeper Constraint** |
| 13 | `Waste_Log` | Core | `WasteID` (PK), `OrderDetailID` (FK) | Tracks discarded dishes and financial loss |
| 14 | `Purchase_Expenses` | Core | `ExpenseID` (PK), `ExpenseType` (CHECK) | Raw materials, payroll, and investments |

### Anti-Fraud Feedback Gatekeeper Constraint:
```sql
CONSTRAINT chk_feedback_authenticity CHECK (
    (ServiceRating IS NULL AND CustomerName IS NULL AND PhoneNumber IS NULL)
    OR
    (ServiceRating IS NOT NULL AND CustomerName IS NOT NULL AND PhoneNumber IS NOT NULL)
)
```
*Physically rejects data padding: customer ratings cannot be submitted without verified contact identity.*

---

## 4. The 4 Automated SQL Business Intelligence Views

### 5.1 Waiter Performance Leaderboard
Calculates: `Total Customers Handled × Average Service Rating`
```sql
CREATE VIEW View_Waiter_Performance AS
SELECT
    s.EmployeeID AS WaiterID,
    s.Name AS WaiterName,
    COALESCE(SUM(o.CustomerCount), 0) AS TotalCustomersHandled,
    ROUND(AVG(f.ServiceRating), 2) AS AvgServiceRating,
    ROUND(COALESCE(SUM(o.CustomerCount), 0) * COALESCE(AVG(f.ServiceRating), 0), 2) AS TotalPerformancePoints
FROM Staff s
JOIN Orders o ON s.EmployeeID = o.WaiterID
LEFT JOIN Feedback f ON o.OrderID = f.OrderID
WHERE s.Role = 'Waiter' AND s.IsActive = TRUE
GROUP BY s.EmployeeID, s.Name;
```

### 5.2 Chef Culinary Production & Quality Leaderboard
Calculates: `Total Dishes Prepared × Average Food Rating`
```sql
CREATE VIEW View_Chef_Performance AS
SELECT
    s.EmployeeID AS ChefID,
    s.Name AS ChefName,
    COALESCE(SUM(od.Quantity), 0) AS TotalDishesPrepared,
    ROUND(AVG(f.FoodRating), 2) AS AvgFoodRating,
    ROUND(
        COALESCE(SUM(od.Quantity), 0) * COALESCE(AVG(f.FoodRating), 0), 2
    ) AS CulinaryPerformancePoints
FROM Staff s
JOIN Order_Details od ON s.EmployeeID = od.PreparedBy_EmployeeID
JOIN Orders o ON od.OrderID = o.OrderID
LEFT JOIN Feedback f ON o.OrderID = f.OrderID
WHERE s.Role = 'Chef' AND s.IsActive = TRUE AND od.ItemStatus = 'Ready'
GROUP BY s.EmployeeID, s.Name;
```

### 5.3 Daily Financial Reconciliation (Per Waiter)
Tracks cash and digital currency allocations:
```sql
CREATE VIEW View_Daily_Waiter_Collections AS
SELECT
    o.WaiterID,
    s.Name AS WaiterName,
    CAST(o.OrderTimestamp AS DATE) AS CollectionDate,
    SUM(o.CashAmount) AS TotalCashCollected,
    SUM(o.UPIAmount) AS TotalUPICollected,
    SUM(o.CashAmount + o.UPIAmount) AS TotalShiftCollection
FROM Orders o
JOIN Staff s ON o.WaiterID = s.EmployeeID
GROUP BY o.WaiterID, s.Name, CAST(o.OrderTimestamp AS DATE);
```

### 5.4 Monthly Profit, Loss & Waste Trend Analytics
Aggregates incoming revenue vs purchase expenses. Incorporates a `NULLIF(TotalIncomingRevenue, 0)` guard during the profit margin calculation to safely prevent division-by-zero crashes when expenses exist but revenue is zero:
```sql
CREATE VIEW View_Monthly_Profit_Loss AS
SELECT
    strftime('%Y-%m', o.OrderTimestamp) AS ReportingMonth,
    SUM(o.CashAmount + o.UPIAmount) AS TotalIncomingRevenue,
    COALESCE(e.TotalOutgoingExpenses, 0) AS TotalOutgoingExpenses,
    (SUM(o.CashAmount + o.UPIAmount) - COALESCE(e.TotalOutgoingExpenses, 0)) AS NetProfitLoss,
    ROUND(((SUM(o.CashAmount + o.UPIAmount) - COALESCE(e.TotalOutgoingExpenses, 0)) /
        NULLIF(SUM(o.CashAmount + o.UPIAmount), 0)) * 100, 2) AS ProfitMarginPercentage,
    ROUND(((SUM(o.CashAmount + o.UPIAmount) - COALESCE(e.TotalOutgoingExpenses, 0)) /
        NULLIF(COALESCE(e.TotalOutgoingExpenses, 0), 0)) * 100, 2) AS ProfitPercentage
FROM Orders o
LEFT JOIN (
    SELECT
        strftime('%Y-%m', ExpenseDate) AS ExpenseMonth,
        SUM(ExpenseAmount) AS TotalOutgoingExpenses
    FROM Purchase_Expenses
    GROUP BY strftime('%Y-%m', ExpenseDate)
) e ON strftime('%Y-%m', o.OrderTimestamp) = e.ExpenseMonth
GROUP BY strftime('%Y-%m', o.OrderTimestamp), e.TotalOutgoingExpenses;
```

---

## 5. Pre-Cooking Edit Block Database Trigger

A `BEFORE UPDATE OR DELETE` database trigger on `Order_Details` physically blocks waiters from modifying or removing a bill item once the kitchen's status moves past `'Pending'`:
- Blocks direct `DELETE` once food enters `'Cooking'` or `'Ready'` status.
- Blocks direct alterations to `Quantity`, `MenuItemID`, or `UnitPrice` past `'Pending'`.
- Forces staff to follow the **Cancellation-Consent Flow**, where chefs review cancellations and discard costs are pushed into `Waste_Log`.

---

## 5. Dynamic Portion Stock Inventory & Auto-OOS Thresholds

Instead of static binary available/out-of-stock flags:
- **Chef Advance Stock Entry:** Chefs enter the quantity of dishes prepared in advance (e.g. 10 idlys) and can alter/increase the quantity at any time.
- **Waiter Real-Time Visibility:** Waiters view the exact number of portions remaining for each dish before taking guest orders.
- **Atomic Stock Decrement:** When an order is placed, stock decrements atomically (e.g., 10 -> 9).
- **Auto Out-of-Stock:** When stock reaches 0, the dish automatically transitions to `IsAvailable = 0` (Out of Stock), disabling ordering on floor terminals.
- **Replenishment:** Entering a new batch quantity restores `IsAvailable = 1` immediately.
- **Pre-Cooking Recovery:** Cancelling an item before cooking (`Pending`) automatically restores the reserved portions to stock.

---

## 6. Single-Seat Administrative Handover Protocol

When a Shop Manager or Kitchen Manager departs:
1. **Hard DELETE** of the departing user's credentials from `Users`.
2. **Soft-retire** the manager in `Staff` by setting `IsActive = 0` (preserving historical audit footprints, approvals, and logs).
3. **INSERT** incoming employee into `Staff`.
4. **INSERT** new credentials into `Users` pointing to incoming `EmployeeID` and administrative `RoleID`.
*All four operations execute within a single atomic ACID transaction block.*

---

## 6. Frontend: The White-and-Green Bubble UI Design System

- **Aesthetic Theme:**
  - Crisp white backgrounds (`#FFFFFF`) with vibrant emerald/mint green accents (`#10B981` / `#059669`).
  - Typography: Modern Plus Jakarta Sans / Inter in soft dark grays (`#1F2937` / `#374151`).
  - Organic soft-radius pill buttons (`border-radius: 9999px`) and bubble containers (`border-radius: 24px` / `32px`).
- **Hardware Viewport Presets:**
  - **Waiter Viewport (360px–480px Mobile):** Single-column layout with high-contrast bubble buttons for table assignment, ordering, and checkout.
  - **Chef KDS (768px–1024px+ Landscape Monitor):** Multi-column ticket grid with status badges readable from a distance, filtering dishes strictly to the logged-in chef.
  - **Kitchen Manager (768px–1024px Tablet):** Dual-pane layout splitting raw inventory alerts on the left, and menu alteration approvals on the right.
  - **Shop Manager (1280px+ Wide Desktop):** Multi-column analytics grid presenting side-by-side performance leaderboards and fiscal charts.

---

## 7. How to Run and Evaluate the Project

### Prerequisites:
- Python 3.10+ (Standard library includes SQLite).
- Virtual environment with dependencies from `requirements.txt`.

### Step 1: Start the Application Server
```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Step 2: Open the Web Application
Open your browser and navigate to:
```
http://127.0.0.1:8000
```

### Step 3: Run the Automated Constraint Verification Test Suite
```powershell
.\.venv\Scripts\python.exe database\test_constraints.py
```
*Validates all 14 tables, 4 views, anti-fraud gatekeepers, multi-table orders, chef consent flows, and the handover protocol.*

### Step 4: Run the Live HTTP Integration Suite
```powershell
.\.venv\Scripts\python.exe test_e2e_api.py
```
*Executes full live workflows over HTTP against the running server.*

---

## 8. Pre-Configured Evaluation Accounts

| Role | Username | Password | Specialization / Context |
| :--- | :--- | :--- | :--- |
| **Shop Manager** | `shopmanager` | `manager123` | Executive BI, 4 Views, Staff Salaries, Handover Protocol |
| **Kitchen Manager** | `kitchenmgr` | `kitchen123` | Raw Material Inventory, Shortages, Menu Approvals |
| **Chef** | `chef_vikram` | `chef123` | Station: South Indian & Curries (Dosa, Vada, Paneer) |
| **Chef** | `chef_meera` | `chef123` | Station: Biryanis & Tandoor (Dum Biryani, Naan) |
| **Waiter** | `waiter_rahul` | `waiter123` | Floor: Morning Shift, Multi-Table Tickets |
| **Waiter** | `waiter_priya` | `waiter123` | Floor: Evening Shift, Multi-Table Tickets |

---

## 9. Top Academic & Technical References

1. **E. F. Codd (1972).** *"Further Normalization of the Data Base Relational Model,"* in *Data Base Systems*, Prentice-Hall, pp. 33–64.  
   *(Foundational theory for 3NF normalization, eliminating transitive dependencies, and update/deletion anomalies).*
2. **A. Silberschatz, H. F. Korth, and S. Sudarshan (2019).** *Database System Concepts*, 7th ed. McGraw-Hill Education.  
   *(Standard curriculum reference for relational schema design, SQL triggers, views, and ACID transaction boundaries).*
3. **J. Gray (1981).** *"The Transaction Concept: Virtues and Limitations,"* in *Proceedings of the 7th International Conference on Very Large Data Bases (VLDB)*, pp. 144–154.  
   *(Theoretical basis for atomic order checkout, inventory reservation, and synchronized financial ledgers).*
4. **D. F. Ferraiolo, R. Sandhu, S. Gavrila, D. R. Kuhn, and R. Chandramouli (2001).** *"Proposed NIST Standard for Role-Based Access Control,"* *ACM Transactions on Information and System Security (TISSEC)*, 4(3), pp. 224–274.  
   *(Architecture for multi-tiered RBAC across Waiter, Chef, Kitchen Manager, and Shop Manager).*
5. **N. Provos and D. Mazières (1999).** *"A Future-Adaptable Password Scheme,"* in *Proceedings of the USENIX Annual Technical Conference*, pp. 81–91.  
   *(Implementation foundation for salted bcrypt password hashing protecting credential records).*

> **Detailed Project Submission Document:** See [PROJECT_REVIEW_SUBMISSION.md](file:///c:/Users/Ahilesh%20Guru%20S/OneDrive/Desktop/DBMS%20vs%20project/project%20code/PROJECT_REVIEW_SUBMISSION.md) for the complete comprehensive review submission, full ER mapping, and viva defense guide.
