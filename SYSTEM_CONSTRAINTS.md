# Master Implementation Document: Restaurant Relational DBMS

**Course Context:** Database System Design & Relational Architectures  
**Execution Environment & Tech Stack:**
- **Target Environment:** Google Antigravity Agentic IDE
- **Presentation Layer (Frontend):** HTML, Vanilla CSS, and JavaScript implementing a responsive, role-based white-and-green bubble UI client
- **Application Layer:** Strictly Python (FastAPI) to handle API routing, connection pooling, and ACID-compliant transactional wrappers (Node.js is formally excluded to enforce a standardized stack)
- **Backend Database:** PostgreSQL / SQLite, structurally designed in 3rd Normal Form (3NF)

---

## 1. Core Architectural Foundations

### 1.1 3NF Normalization (Edgar F. Codd)
The schema eliminates update, insertion, and deletion anomalies across complex multi-table and multi-chef relations:
- Every non-key attribute is non-transitively dependent directly on the primary key (X → A where X is a candidate key).
- Personnel designations are normalized via `Roles (RoleID, RoleName)` with `Staff.RoleID (FK)`.
- Line-item financial accounting snapshots `UnitPrice` at order time directly on `Order_Details`, preventing historical audit skew when central menu prices change.
- Multi-table coverage (one bill across multiple tables) is decoupled cleanly through the `Order_Tables (OrderID, TableNumber)` composite primary key bridge table.

### 1.2 Role-Based Access Control (David Ferraiolo & Richard Kuhn)
Data access is isolated at the application and database levels without shared credentials:
- Passwords must be hashed cryptographically (`PasswordHash` using bcrypt) in the `Users` table rather than stored as plaintext.
- The `Users` table decouples credential authentication from personnel HR records (`Staff`).
- Permissions matrix strictly isolates Waiters, Chefs, Kitchen Managers, and Shop Managers.

### 1.3 Concurrency Control & ACID Transactions (Jim Gray)
- The backend employs row-level locking (e.g., `SELECT ... FOR UPDATE` in PostgreSQL or `BEGIN IMMEDIATE` transaction wrappers in SQLite) to avoid race conditions and safely isolate data.
- All checkout, inventory depletion, order dispatch, and cancellation operations run in strict atomic transaction boundaries.

---

## 2. Authentication & Session Constraints

### 2.1 Concurrency Tiers
- **Waitstaff & Chefs:** Unlimited concurrent sessions are supported. Every initiated transaction is stamped with the user's explicit `EmployeeID` (e.g., `WaiterID` or `PreparedBy_EmployeeID`) to dynamically isolate their active dashboards.
- **Kitchen & Shop Managers:** The architecture enforces a strict **Single-Seat Administrative Constraint**, allowing exactly one active account per executive role to safeguard overarching read/write CRUD authority.

### 2.2 Single-Seat Handover Protocol
When an executive manager departs, execute an atomic transaction:
1. Hard `DELETE` of the specific credentials row in `Users` matching that administrative role.
2. Soft-retire the manager in the `Staff` table by toggling `IsActive = FALSE` (preserving historical audit footprints, approvals, dish dispatch logs, and analytics).
3. `INSERT` the incoming employee into `Staff` with their assigned `RoleID`.
4. `INSERT` new credentials into `Users` pointing to the incoming `EmployeeID` and administrative `RoleID`.

---

## 3. Database Schema & Gatekeeping (DDL)

```
+------------------+         1:N        +-------------------+
|      Roles       |------------------->|       Users       |
+------------------+                    +-------------------+
  RoleID (PK)                             UserID (PK)
  RoleName (UNIQUE)                       EmployeeID (UNIQUE FK)
         |                                Username (UNIQUE)
         | 1:N                            PasswordHash
         v
+------------------+
|      Staff       |
+------------------+
  EmployeeID (PK)
  Name
  RoleID (FK)
  Shift
  IsActive (BOOL)
         |
         +-----------------+-----------------+
         | 1:N             | 1:N             | 1:N
         v                 v                 v
+------------------+ +-------------+ +-------------------------------+
|    Menu_Items    | |   Orders    | |         Order_Details         |
+------------------+ +-------------+ +-------------------------------+
| MenuItemID (PK)  | | OrderID(PK) | | OrderDetailID (PK)            |
| ItemName         | | WaiterID(FK)| | OrderID (FK)                  |
| Category         | | CustCount   | | MenuItemID (FK)               |
| Price (CHECK>0)  | | CashAmount  | | Quantity (CHECK>0)            |
| IsAvailable      | | UPIAmount   | | UnitPrice (Snapshot)          |
| AssignedChefID   | | OrderStatus | | Subtotal                      |
+------------------+ +-------------+ | PreparedBy_EmployeeID (FK)    |
         ^                 |         | ItemStatus (CHECK IN (...))   |
         |                 | 1:N     +-------------------------------+
+------------------+       v                         ^
|  Shortage_Logs   | +-----------------+             |
+------------------+ |  Order_Tables   |             | 1:1
| LogID (PK)       | +-----------------+             v
| MenuItemID (FK)  | | OrderID (FK)    |     +-------------------+
| ChefID (FK)      | | TableNumber(FK) |     |     Waste_Log     |
| Reason           | +-----------------+     +-------------------+
+------------------+                         | WasteID (PK)      |
                                             | OrderDetailID(FK) |
                                             | IngredientCost    |
                                             +-------------------+
```

### 3.1 Authentication Hub
1. **Roles**
   - `RoleID` (INT, PK, AUTO_INCREMENT)
   - `RoleName` (VARCHAR(50), UNIQUE, NOT NULL): Seeded with `'Shop Manager'`, `'Kitchen Manager'`, `'Chef'`, `'Waiter'`.
2. **Staff**
   - `EmployeeID` (INT, PK, AUTO_INCREMENT)
   - `Name` (VARCHAR(100), NOT NULL)
   - `RoleID` (INT, NOT NULL, FK → `Roles.RoleID`)
   - `Role` (VARCHAR(50), NOT NULL)
   - `Shift` (VARCHAR(30))
   - `IsActive` (BOOLEAN, DEFAULT TRUE, NOT NULL)
   - `Salary` (DECIMAL(10,2), DEFAULT 30000.00, CHECK (Salary >= 0))
3. **Users**
   - `UserID` (INT, PK, AUTO_INCREMENT)
   - `EmployeeID` (INT, UNIQUE, NOT NULL, FK → `Staff.EmployeeID` ON DELETE CASCADE)
   - `Username` (VARCHAR(50), UNIQUE, NOT NULL)
   - `PasswordHash` (VARCHAR(255), NOT NULL)
   - `RoleID` (INT, NOT NULL, FK → `Roles.RoleID`)

### 3.2 Menu & Inventory
4. **Menu_Items**
   - `MenuItemID` (INT, PK, AUTO_INCREMENT)
   - `ItemName` (VARCHAR(100), NOT NULL)
   - `Category` (VARCHAR(50), NOT NULL)
   - `Price` (DECIMAL(10,2), NOT NULL, CHECK (Price > 0))
   - `StockQuantity` (INT, DEFAULT 10, NOT NULL, CHECK (StockQuantity >= 0))
   - `IsAvailable` (BOOLEAN, DEFAULT TRUE, NOT NULL)
   - `AssignedChefID` (INT, NOT NULL, FK → `Staff.EmployeeID`)
   - `IsActive` (BOOLEAN, DEFAULT TRUE, NOT NULL)
5. **Inventory**
   - `IngredientID` (INT, PK, AUTO_INCREMENT)
   - `IngredientName` (VARCHAR(100), NOT NULL)
   - `NeedsRestock` (BOOLEAN, DEFAULT FALSE, NOT NULL)
   - `ReportedBy_ChefID` (INT, NULL, FK → `Staff.EmployeeID` ON DELETE SET NULL)
   - `LastUpdated` (TIMESTAMP, DEFAULT CURRENT_TIMESTAMP)
6. **Shortage_Logs**
   - `LogID` (INT, PK, AUTO_INCREMENT)
   - `MenuItemID` (INT, NOT NULL, FK → `Menu_Items.MenuItemID` ON DELETE CASCADE)
   - `ChefID` (INT, NOT NULL, FK → `Staff.EmployeeID`)
   - `Reason` (VARCHAR(255), NOT NULL)
   - `LogTimestamp` (TIMESTAMP, DEFAULT CURRENT_TIMESTAMP)
7. **Menu_Requests**
   - `RequestID` (INT, PK, AUTO_INCREMENT)
   - `ChefID` (INT, NOT NULL, FK → `Staff.EmployeeID`)
   - `DishName` (VARCHAR(100), NOT NULL)
   - `RequestType` (VARCHAR(10), NOT NULL, CHECK (RequestType IN ('Add', 'Remove')))
   - `Reason` (TEXT, NOT NULL)
   - `Status` (VARCHAR(20), DEFAULT 'Pending', NOT NULL, CHECK (Status IN ('Pending', 'Approved', 'Rejected')))
   - `CreatedAt` (TIMESTAMP, DEFAULT CURRENT_TIMESTAMP)

### 3.3 Floor Operations (M:N Handling)
8. **Tables**
   - `TableNumber` (INT, PK)
   - `SeatingCapacity` (INT, NOT NULL, CHECK (SeatingCapacity > 0))
   - `CurrentStatus` (VARCHAR(20), DEFAULT 'Available', NOT NULL, CHECK (CurrentStatus IN ('Available', 'Occupied', 'Reserved')))
9. **Orders**
   - `OrderID` (INT, PK, AUTO_INCREMENT)
   - `WaiterID` (INT, NOT NULL, FK → `Staff.EmployeeID`)
   - `CustomerCount` (INT, NOT NULL, CHECK (CustomerCount > 0))
   - `OrderTimestamp` (TIMESTAMP, DEFAULT CURRENT_TIMESTAMP)
   - `CashAmount` (DECIMAL(10,2), DEFAULT 0.00, NOT NULL, CHECK (CashAmount >= 0))
   - `UPIAmount` (DECIMAL(10,2), DEFAULT 0.00, NOT NULL, CHECK (UPIAmount >= 0))
   - `OrderStatus` (VARCHAR(20), DEFAULT 'In Progress', NOT NULL, CHECK (OrderStatus IN ('In Progress', 'Completed', 'Cancelled')))
10. **Order_Tables** (Composite PK resolving multi-table dining)
    - `OrderID` (INT, NOT NULL, FK → `Orders.OrderID` ON DELETE CASCADE)
    - `TableNumber` (INT, NOT NULL, FK → `Tables.TableNumber` ON DELETE RESTRICT)
    - `PRIMARY KEY (OrderID, TableNumber)`
11. **Order_Details**
    - `OrderDetailID` (INT, PK, AUTO_INCREMENT)
    - `OrderID` (INT, NOT NULL, FK → `Orders.OrderID` ON DELETE CASCADE)
    - `MenuItemID` (INT, NOT NULL, FK → `Menu_Items.MenuItemID`)
    - `Quantity` (INT, NOT NULL, CHECK (Quantity > 0))
    - `UnitPrice` (DECIMAL(10,2), NOT NULL, CHECK (UnitPrice >= 0)) — *Historical Snapshot*
    - `Subtotal` (DECIMAL(10,2), NOT NULL, CHECK (Subtotal >= 0))
    - `PreparedBy_EmployeeID` (INT, NOT NULL, FK → `Staff.EmployeeID`)
    - `ItemStatus` (VARCHAR(20), DEFAULT 'Pending', NOT NULL, CHECK (ItemStatus IN ('Pending', 'Cooking', 'Ready', 'Cancel Requested', 'Cancelled')))
    - `CancellationReason` (VARCHAR(255), NULL)

### 3.4 Feedback & Anti-Fraud Integrity
12. **Feedback**
    - `FeedbackID` (INT, PK, AUTO_INCREMENT)
    - `OrderID` (INT, UNIQUE, NOT NULL, FK → `Orders.OrderID` ON DELETE CASCADE)
    - `CustomerName` (VARCHAR(100), NULL)
    - `PhoneNumber` (VARCHAR(20), NULL)
    - `ServiceRating` (INT, NULL, CHECK (ServiceRating BETWEEN 1 AND 5))
    - `FoodRating` (INT, NULL, CHECK (FoodRating BETWEEN 1 AND 5))
    - `AmbienceRating` (INT, NULL, CHECK (AmbienceRating BETWEEN 1 AND 5))
    - `CleanlinessRating` (INT, NULL, CHECK (CleanlinessRating BETWEEN 1 AND 5))
    - `ReviewText` (TEXT, NULL)
    - **Gatekeeper Constraint:**
      ```sql
      CONSTRAINT chk_feedback_authenticity CHECK (
        (ServiceRating IS NULL AND CustomerName IS NULL AND PhoneNumber IS NULL)
        OR
        (ServiceRating IS NOT NULL AND CustomerName IS NOT NULL AND PhoneNumber IS NOT NULL)
      )
      ```
13. **Waste_Log**
    - `WasteID` (INT, PK, AUTO_INCREMENT)
    - `OrderDetailID` (INT, NULL, FK → `Order_Details.OrderDetailID` ON DELETE SET NULL)
    - `IngredientCost` (DECIMAL(10,2), NOT NULL, CHECK (IngredientCost >= 0))
    - `LogTimestamp` (TIMESTAMP, DEFAULT CURRENT_TIMESTAMP)
14. **Purchase_Expenses**
    - `ExpenseID` (INT, PK, AUTO_INCREMENT)
    - `ExpenseDate` (DATE, NOT NULL)
    - `ExpenseAmount` (DECIMAL(10,2), NOT NULL, CHECK (ExpenseAmount > 0))
    - `ExpenseType` (VARCHAR(50), NOT NULL, CHECK (ExpenseType IN ('Raw Materials', 'Other Investments', 'Payroll')))

---

## 4. Operational Workflows (ACID Transactions & Triggers)

### 4.1 Pre-Cooking Edit Block (Database Trigger)
A `BEFORE UPDATE OR DELETE` database trigger on `Order_Details` physically blocks waiters or clients from modifying or removing a bill item once the kitchen's status moves past `'Pending'`:
- Direct `DELETE` attempts when `ItemStatus != 'Pending'` are aborted at the database engine level.
- Direct `UPDATE` attempts altering `MenuItemID`, `Quantity`, or `UnitPrice` when `ItemStatus != 'Pending'` are aborted.

```sql
CREATE TRIGGER trg_block_order_detail_delete
BEFORE DELETE ON Order_Details
FOR EACH ROW
WHEN OLD.ItemStatus != 'Pending'
BEGIN
    SELECT RAISE(ABORT, 'Pre-Cooking Edit Block: Cannot delete order item once status moves past Pending. Initiate Cancellation-Consent flow instead.');
END;

CREATE TRIGGER trg_block_order_detail_update
BEFORE UPDATE ON Order_Details
FOR EACH ROW
WHEN OLD.ItemStatus != 'Pending' AND (OLD.MenuItemID != NEW.MenuItemID OR OLD.Quantity != NEW.Quantity OR OLD.UnitPrice != NEW.UnitPrice)
BEGIN
    SELECT RAISE(ABORT, 'Pre-Cooking Edit Block: Cannot modify dish, quantity, or unit price once status moves past Pending.');
END;
```

### 4.2 Waiter Cancellation Architecture & Waste Log Rules
Waiters have authoritative cancellation controls for both individual dishes and entire orders:

1. **Individual Dish & Partial Quantity Cancellation**:
   - When a waiter cancels a dish, they specify the number of portions to cancel (e.g. cancelling 1 Biryani out of 15).
   - **Before Cooking** (`Pending` / `Cancel Requested`): The cancelled portions are restored to `Menu_Items.StockQuantity`. Does **NOT** go to `Waste_Log`.
   - **During or After Cooking** (`Cooking` / `Ready`): ONLY the cancelled portions are logged to `Waste_Log` with estimated raw ingredient cost (~80% of cancelled subtotal). Any uncancelled portions continue preparation normally.

2. **Entire Order Cancellation**:
   - Dishes in `Pending` status are cancelled without being sent to `Waste_Log`.
   - Dishes in `Cooking` or `Ready` status are cancelled and alone sent to `Waste_Log`.
   - `Orders.OrderStatus` transitions to `'Cancelled'`.
   - Assigned floor tables are released back to `'Available'`.

3. **Automated Synchronization into Expenses List**:
   - Every `Waste_Log` entry triggers an atomic insert into `Purchase_Expenses` via database trigger `trg_sync_wastelog_to_expenses`.
   - The expense is recorded with `ExpenseType = 'Raw Materials'`, `ExpenseDate = DATE(LogTimestamp)`, `ExpenseAmount = IngredientCost`, and `Description = 'wastelog'`.
   - In the Shop Manager's login, these wastelog entries appear in the Operating Expense Register and are included in total expenses for computing Net Profit / Loss and Monthly Fiscal Reports.

*Note: Chefs cannot cancel orders directly. Waiters handle customer cancellations, specifying exact portion quantities.*

### 4.3 Out-of-Stock Atomic Transaction
The FastAPI layer wraps menu outages in an atomic ACID transaction that simultaneously sets stock to zero, executes dish availability toggling, and records shortage logging:
```sql
BEGIN TRANSACTION;
UPDATE Menu_Items SET StockQuantity = 0, IsAvailable = FALSE WHERE MenuItemID = :item_id;
INSERT INTO Shortage_Logs (MenuItemID, ChefID, Reason) VALUES (:item_id, :chef_id, :reason);
COMMIT;
```

### 4.4 Dynamic Portion Stock Inventory & Auto-OOS Thresholds
Instead of a static binary available/out-of-stock toggle, every menu item maintains an explicit non-negative portion inventory (`Menu_Items.StockQuantity`):
1. **Advance Preparation Entry**:
   - The chef enters the exact number of portions prepared in advance (e.g., 10 idlys) via `PUT /api/chef/menu/{item_id}/stock`.
   - The chef can alter the stock quantity at any time, even while in stock (e.g. preparing 10 additional portions elevates stock from 8 to 18).
2. **Advance Waiter Visibility**:
   - The waiter's menu list dynamically presents the real-time number of portions remaining for each dish before taking guest orders.
   - Waiters are prevented at both UI and ACID transaction levels from dispatching orders that exceed available stock.
3. **Atomic Decrement & Auto Out-of-Stock**:
   - When an order is dispatched or a dish is added to an existing order, the stock decrements atomically:
     ```sql
     UPDATE Menu_Items
     SET StockQuantity = StockQuantity - :qty,
         IsAvailable = CASE WHEN StockQuantity - :qty <= 0 THEN 0 ELSE 1 END
     WHERE MenuItemID = :item_id;
     ```
   - When portion stock reaches 0, the dish automatically transitions to `IsAvailable = 0` (Out of Stock), immediately blocking further orders across all floor terminals.
4. **Replenishment & Availability Restoration**:
   - When the chef prepares a new batch of food, entering a newly available quantity (e.g., 15) automatically restores the dish to `IsAvailable = 1` (In Stock).
5. **Pre-Cooking Cancellation Restitution**:
   - If a waiter cancels a dish *before cooking* (`Pending` / `Cancel Requested`), the reserved portion count is automatically restored back to `Menu_Items.StockQuantity` and `IsAvailable` is reset to 1.
   - If cancelled *during or after cooking*, the food is discarded to `Waste_Log` and cannot be returned to ready stock.


---

## 5. Automated Business Intelligence (Views)

### 5.1 Waiter Performance Leaderboard
Calculates performance points via `SUM(CustomerCount) * AVG(ServiceRating)` grouped by `WaiterID`:
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
WHERE s.Role = 'Waiter' AND s.IsActive = 1
GROUP BY s.EmployeeID, s.Name;
```

### 5.2 Chef Performance Leaderboard
Ranks culinary output using `Dishes Prepared × Avg Food Rating` grouped by `PreparedBy_EmployeeID`:
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
WHERE s.Role = 'Chef' AND s.IsActive = 1 AND od.ItemStatus = 'Ready'
GROUP BY s.EmployeeID, s.Name;
```

### 5.3 Daily Financial Reconciliation (Per Waiter)
Aggregates `SUM(CashAmount)` and `SUM(UPIAmount)` per waiter per day:
```sql
CREATE VIEW View_Daily_Waiter_Collections AS
SELECT
    o.WaiterID,
    s.Name AS WaiterName,
    DATE(o.OrderTimestamp) AS CollectionDate,
    SUM(o.CashAmount) AS TotalCashCollected,
    SUM(o.UPIAmount) AS TotalUPICollected,
    SUM(o.CashAmount + o.UPIAmount) AS TotalShiftCollection
FROM Orders o
JOIN Staff s ON o.WaiterID = s.EmployeeID
GROUP BY o.WaiterID, s.Name, DATE(o.OrderTimestamp);
```

### 5.4 Monthly Profit/Loss Analytics
Joins `Purchase_Expenses` against finalized `Orders` revenue. It integrates a **`NULLIF(TotalIncomingRevenue, 0)`** guard during the profit margin calculation to safely prevent division-by-zero crashes when expenses exist but revenue is zero:
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

## 6. UI Design System & Hardware Viewports

### 6.1 Aesthetic Theme: White-and-Green Bubble UI
- **Backgrounds:** Clean white backgrounds (`#FFFFFF`, `#F8FAFC`) with subtle translucent bubble layers.
- **Accents:** Emerald / mint green primary interactive accents (`#10B981`, `#059669`).
- **Typography:** Soft dark gray high-contrast typography (`#1F2937`, `#374151`) to prevent eye fatigue during kitchen and floor shifts.
- **Components:** Pill-shaped circular action buttons, curved badge indicators, and glassmorphic rounded containers.

### 6.2 Hardware Viewport Presets
- **Waiter Viewport (360px - 480px Mobile):** Single-column layout optimized for rapid handheld table selection and checkout on the move.
- **Chef KDS (768px - 1024px+ Landscape Monitor):** High-contrast multi-column ticket grid readable from across a hot kitchen station.
- **Kitchen Manager (768px - 1024px Tablet):** Split view balancing raw inventory shortage queues with menu alteration approvals.
- **Shop Manager (1280px+ Wide Desktop):** Multi-column dashboard presenting financial reconciliations, leaderboards, and executive controls.


---

## 7. Academic & Technical References

1. **Codd, E. F. (1970).** "A Relational Model of Data for Large Shared Data Banks." *Communications of the ACM*, 13(6), 377–387.
2. **Codd, E. F. (1972).** "Further Normalization of the Data Base Relational Model." In *Data Base Systems*, Prentice-Hall, 33–64.
3. **Gray, J. (1981).** "The Transaction Concept: Virtues and Limitations." In *Proceedings of the 7th International Conference on Very Large Data Bases (VLDB)*, 144–154.
4. **Gray, J., & Reuter, A. (1993).** *Transaction Processing: Concepts and Techniques*. Morgan Kaufmann Publishers.
5. **Ferraiolo, D. F., & Kuhn, D. R. (1992).** "Role-Based Access Controls." In *Proceedings of the 15th National Computer Security Conference*, 554–563.
6. **Ferraiolo, D. F., Sandhu, R., Gavrila, S., Kuhn, D. R., & Chandramouli, R. (2001).** "Proposed NIST Standard for Role-Based Access Control." *ACM Transactions on Information and System Security (TISSEC)*, 4(3), 224–274.
7. **Silberschatz, A., Korth, H. F., & Sudarshan, S. (2019).** *Database System Concepts* (7th ed.). McGraw-Hill Education.
8. **Ramakrishnan, R., & Gehrke, J. (2003).** *Database Management Systems* (3rd ed.). McGraw-Hill Education.
9. **Provos, N., & Mazières, D. (1999).** "A Future-Adaptable Password Scheme." In *Proceedings of the USENIX Annual Technical Conference*, 81–91.
10. **Jones, M., Bradley, J., & Sakimura, N. (2015).** "JSON Web Token (JWT)." *RFC 7519*, Internet Engineering Task Force (IETF).
