# Role-Based Relational Database Management System for Multi-Station Restaurant Operations
## Official Comprehensive Project Review & Viva Submission Document

---

### Executive Summary

- **Project Title:** Role-Based Relational Database Management System for Multi-Station Restaurant Operations
- **Domain:** Database Management Systems (DBMS), Enterprise Systems Architecture, Relational Schema Design
- **Core Focus:** 3NF Normalization, ACID Transactional Integrity, Role-Based Access Control (RBAC), Automated SQL Business Intelligence, and Dynamic Inventory & Waste Tracking
- **Tech Stack:**
  - **Database Engine:** SQLite (3NF Embedded) / PostgreSQL / MySQL
  - **Application / Middleware Layer:** Python (FastAPI), Pydantic v2, Python-Jose (JWT), Passlib / Bcrypt
  - **Presentation Layer (Frontend):** Modern HTML5, Responsive Vanilla CSS (White-and-Green Bubble UI Design System), Modular ES6 JavaScript
  - **Security & Integrity:** Ferraiolo-Kuhn Role-Based Access Control, Bcrypt Password Hashing, Anti-Fraud SQL Gatekeepers, Pre-Cooking Edit Block Triggers

---

## 1. Problem Statement & Motivation

Traditional restaurant point-of-sale (POS) and billing systems suffer from fundamental relational design flaws:
1. **Denormalized "God Tables":** Storing orders, line items, customer info, and table numbers in single unnormalized tables leads to severe data redundancy, string-parsing hacks (e.g. storing tables as `"1, 2"`), and update anomalies.
2. **Historical Billing Skew:** Computing past bills dynamically using live menu prices distorts financial audits whenever the restaurant raises prices.
3. **No Separation of Concerns:** Credential records coupled with personnel records cause deletion anomalies during staff turnover.
4. **Kitchen & Waste Blindness:** Uncooked versus cooked food cancellations are either untracked or wiped out completely, leading to unaccounted raw material inventory losses.
5. **Concurrency Conflicts:** Simultaneous table assignments and order updates result in race conditions and dirty reads.

This project delivers an enterprise-grade, mathematically normalized 3rd Normal Form (3NF) relational database solution that enforces data isolation, transactional ACID boundaries, role segregation, automated fiscal auditing, and real-time portion-level inventory tracking.

---

## 2. Theoretical Computer Science Pillars

```
+---------------------------------------------------------------------------------------------------+
|                                  THEORETICAL ARCHITECTURAL PILLARS                                |
+---------------------------------+---------------------------------+-------------------------------+
|     1. Edgar F. Codd (3NF)      |  2. Ferraiolo-Kuhn (NIST RBAC)  |      3. Jim Gray (Turing)     |
|   Relational Normalization      |   Role-Based Access Control     |   ACID Transaction Guarantees |
| - Zero redundancy               | - Decoupled auth credentials    | - BEGIN IMMEDIATE boundaries  |
| - 1NF atomic domain values      | - 4 isolated operational roles  | - Row-level locking & commits |
| - 2NF no partial dependencies   | - Single-seat handover protocol | - Atomic multi-table checkouts|
| - 3NF direct key dependency     | - Token-based session guards    | - Automatic rollback on error |
+---------------------------------+---------------------------------+-------------------------------+
```

1. **Edgar F. Codd (3rd Normal Form Decomposition):**
   Every non-key attribute is non-transitively dependent directly on the primary key ($X \to A$ where $X$ is a candidate key). Decomposed into 14 normalized tables connected via foreign key constraints with strict `ON DELETE` rules.
2. **David Ferraiolo & Richard Kuhn (Role-Based Access Control):**
   Authentication credentials (`Users`) are strictly separated from operational personnel data (`Staff`). Four discrete roles (**Waiter**, **Chef**, **Kitchen Manager**, **Shop Manager**) access dedicated hardware viewport clients protected by cryptographically signed JWT tokens.
3. **Jim Gray (ACID Transactions & Concurrency Control):**
   Multi-step database updates (multi-table order dispatch, partial cancellations, out-of-stock toggling, and executive credential handovers) execute inside atomic transaction boundaries (`BEGIN IMMEDIATE ... COMMIT`), rolling back completely if any sub-operation fails.

---

## 3. The Normalization Journey: Before vs. After 3NF

### 3.1 The Flawed State Before 3NF (Flat / Denormalized Representation)
Before normalization, typical implementations use a single flat relation or poorly split tables:

```
Orders_Denormalized (
    OrderID, TableNumbers, CustomerCount, WaiterName, WaiterShift, 
    ItemsOrdered, Quantities, CatalogPrice, TotalBill, ChefName, OrderStatus
)
```

**Anomalies Present in the Denormalized State:**
- **1NF Violation (Repeating Groups & Delimited Lists):** Storing `TableNumbers` as `"1, 2"` and `ItemsOrdered` as `"Biryani, Dosa"` violates atomicity. SQL queries cannot index or filter by table or dish without expensive full-table string searches.
- **2NF Violation (Partial Dependencies):** In a composite key `(OrderID, MenuItemID)`, attributes like `ItemName` and `CatalogPrice` depend solely on `MenuItemID`, not on `OrderID`. A new dish cannot be added to the catalog without creating a dummy order (Insertion Anomaly).
- **3NF Violation (Transitive Dependencies):** `OrderID` $\to$ `WaiterID` $\to$ `WaiterName`, `Shift`. Updating an employee's shift requires updating thousands of historical order records (Update Anomaly).
- **Historical Price Corruption:** Without snapshotting price at order time, any price adjustment on the menu immediately retroactively corrupts past receipts and revenue history.
- **Personnel Deletion Anomaly:** Deleting an ex-employee's user credentials deletes their associated sales history or requires orphan `NULL` values.

### 3.2 The State After 3NF (Strict Relational Decomposition)

In 3NF, the data is partitioned across **14 relational entities**:
- `Roles (RoleID, RoleName)`: Isolates role metadata.
- `Staff (EmployeeID, Name, RoleID, Shift, IsActive)`: HR personnel tracking.
- `Users (UserID, EmployeeID, Username, PasswordHash)`: Decoupled authentication.
- `Tables (TableNumber, SeatingCapacity, CurrentStatus)`: Dining floor state.
- `Menu_Items (MenuItemID, ItemName, Category, Price, StockQuantity, IsAvailable, AssignedChefID)`: Dish catalog.
- `Orders (OrderID, WaiterID, CustomerCount, CashAmount, UPIAmount, OrderStatus, OrderTimestamp)`: Master order header.
- `Order_Tables (OrderID, TableNumber)`: Composite M:N bridge table resolving multi-table group seating.
- `Order_Details (OrderDetailID, OrderID, MenuItemID, Quantity, UnitPrice, Subtotal, PreparedBy_EmployeeID, ItemStatus, CancellationReason)`: 1:N line items with price snapshotting.
- `Waste_Log (WasteID, OrderDetailID, IngredientCost, LogTimestamp)`: Cooked food discard loss auditing.
- `Purchase_Expenses (ExpenseID, ExpenseDate, ExpenseAmount, ExpenseType, Description)`: Operating expense register.
- `Feedback (FeedbackID, OrderID, CustomerName, PhoneNumber, ServiceRating, FoodRating, AmbienceRating, CleanlinessRating, ReviewText)`: Authenticated customer feedback.
- `Inventory (IngredientID, IngredientName, AssignedChefID, NeedsRestock)`: Kitchen ingredients inventory.
- `Shortage_Logs (LogID, MenuItemID, ChefID, Reason, LoggedAt)`: Menu outage audit logs.
- `Menu_Requests (RequestID, ChefID, RequestType, ItemName, Category, ProposedPrice, Reason, RequestStatus)`: Chef culinary proposals.

### 3.3 Normalization Comparative Matrix

| Database Dimension | Before Normalization | After 3NF Normalization |
|---|---|---|
| **Data Redundancy** | High; dish names, prices, staff titles repeated across rows | Zero redundancy; canonical source for all entities |
| **Historical Pricing** | Dynamic lookup; price changes corrupted past receipts | `UnitPrice` snapshot in `Order_Details` permanently preserves financial integrity |
| **Multi-Table Parties** | Impossible or delimited strings (`"1,2"`) | Resolved via `Order_Tables` composite primary key bridge table |
| **Credential Lifecycle** | Coupled with staff; deleting user wiped sales history | Decoupled `Users` $\leftrightarrow$ `Staff` enables Single-Seat Handover with zero data loss |
| **Food Waste Tracking** | Untracked; cancellations erased order lines | Cooked discards routed to `Waste_Log` and auto-synchronized to expenses |

---

## 4. Entity-Relationship Architecture (Schema Diagram)

```
+------------------+         1:N        +-------------------+
|      Roles       |------------------->|       Users       |
+------------------+                    +-------------------+
  RoleID (PK)                             UserID (PK)
  RoleName (UNIQUE)                       EmployeeID (UNIQUE FK)
         |                                Username (UNIQUE)
         | 1:N                            PasswordHash (bcrypt)
         v
+------------------+
|      Staff       |
+------------------+
  EmployeeID (PK)
  Name, RoleID (FK), Shift, IsActive (BOOL)
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
| StockQuantity    | | UPIAmount   | | UnitPrice (Price Snapshot)    |
| IsAvailable      | | OrderStatus | | Subtotal                      |
+------------------+ +-------------+ | PreparedBy_EmployeeID (FK)    |
         ^                 |         | ItemStatus ('Pending', etc.)  |
         |                 | 1:N     | CancellationReason (TEXT)     |
         |                 v         +-------------------------------+
+------------------+ +-----------------+             |
|  Shortage_Logs   | |  Order_Tables   |             | 1:1
+------------------+ +-----------------+             v
| LogID (PK)       | | OrderID (FK)    |     +-------------------+
| MenuItemID (FK)  | | TableNumber(FK) |     |     Waste_Log     |
| ChefID (FK)      | +-----------------+     +-------------------+
| Reason           |                         | WasteID (PK)      |
+------------------+                         | OrderDetailID(FK) |
                                             | IngredientCost    |
                                             +-------------------+
                                                       |
                                                       | Trigger trg_sync_wastelog_to_expenses
                                                       v
                                             +---------------------+
                                             |  Purchase_Expenses  |
                                             +---------------------+
                                             | ExpenseID (PK)      |
                                             | ExpenseAmount       |
                                             | ExpenseType         |
                                             | Description         |
                                             +---------------------+
```

---

## 5. Advanced Relational Constraints & Database Triggers

### 5.1 Pre-Cooking Edit Block Triggers
Protects kitchen operations by preventing client applications or waitstaff from directly deleting or modifying order quantities once items have moved into active preparation:

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
WHEN OLD.ItemStatus != 'Pending' 
  AND (
    OLD.MenuItemID != NEW.MenuItemID 
    OR OLD.UnitPrice != NEW.UnitPrice 
    OR NEW.Quantity > OLD.Quantity
  )
BEGIN
    SELECT RAISE(ABORT, 'Pre-Cooking Edit Block: Cannot modify dish, unit price, or increase quantity once status moves past Pending.');
END;
```

### 5.2 Automated Waste Log to Operating Expenses Synchronization Trigger
Whenever spoiled or cancelled cooked food is logged into `Waste_Log`, a database trigger immediately inserts an atomic debit into `Purchase_Expenses`:

```sql
CREATE TRIGGER trg_sync_wastelog_to_expenses
AFTER INSERT ON Waste_Log
FOR EACH ROW
WHEN NEW.IngredientCost > 0
BEGIN
    INSERT INTO Purchase_Expenses (ExpenseDate, ExpenseAmount, ExpenseType, Description)
    VALUES (DATE(COALESCE(NEW.LogTimestamp, 'now')), NEW.IngredientCost, 'Raw Materials', 'wastelog');
END;
```

### 5.3 Anti-Fraud Feedback Gatekeeper Check Constraint
Prevents malicious staff from padding reviews or inflating leaderboard ratings without authentic customer details:

```sql
CONSTRAINT chk_feedback_authenticity CHECK (
    (ServiceRating IS NULL AND CustomerName IS NULL AND PhoneNumber IS NULL)
    OR
    (ServiceRating IS NOT NULL AND CustomerName IS NOT NULL AND PhoneNumber IS NOT NULL)
)
```

---

## 6. Waiter Cancellation Architecture & 80% Waste Logging

The system implements selective, portion-level cancellation controls:

```
                                  Waitstaff Cancels Dish
                                            |
                         +------------------+------------------+
                         |                                     |
               Before Cooking ('Pending')            During/After Cooking ('Cooking'/'Ready')
                         |                                     |
            +------------+------------+           +------------+------------+
            |                         |           |                         |
      Full Item Qty             Partial Qty  Full Item Qty             Partial Qty
      (e.g. 5 of 5)             (e.g. 1 of 5) (e.g. 15 of 15)           (e.g. 1 of 15)
            |                         |           |                         |
       Restores 5 to             Restores 1  Calculates 80% Cost       Splits Row:
       Stock Inventory           to Stock;   Logs 80% to Waste_Log;    - 14 continue Cooking
            |                    4 remain    Item -> 'Cancelled';      - 1 marked Cancelled
      Zero Waste Log             Pending     Zero stock recovery       - 80% Cost of 1 portion
                                                                         sent to Waste_Log
```

### Partial Quantity Cancellation Math
If an order contains **15 Biriyanis** at ₹290.00 each ($\text{Subtotal} = ₹4,350.00$) and the customer cancels **1 Biryani** during cooking:
1. The active order line is updated:
   $$\text{Quantity}_{\text{remaining}} = 14, \quad \text{Subtotal}_{\text{remaining}} = 14 \times ₹290.00 = ₹4,060.00$$
2. A new cancelled row is atomically inserted:
   $$\text{Quantity}_{\text{cancelled}} = 1, \quad \text{Subtotal}_{\text{cancelled}} = ₹290.00, \quad \text{ItemStatus} = \text{'Cancelled'}$$
3. Raw ingredient loss is calculated at **80%** of the cancelled portion:
   $$\text{IngredientCost} = \text{round}(₹290.00 \times 0.80, 2) = ₹232.00$$
4. Exactly ₹232.00 is logged to `Waste_Log` and automatically debited into `Purchase_Expenses`. The remaining 14 portions continue cooking undisturbed.

---

## 7. Automated Business Intelligence SQL Views

The system runs 4 real-time analytical views without data duplication:

### 1. View 5.1: `View_Waiter_Performance` (Shift Efficiency Leaderboard)
Evaluates waitstaff productivity based on total guest throughput and verified customer service ratings:
$$\text{TotalPerformancePoints} = \text{TotalCustomersHandled} \times \text{AvgServiceRating}$$

### 2. View 5.2: `View_Chef_Performance` (Culinary Output Leaderboard)
Ranks kitchen culinary volume weighted by customer satisfaction:
$$\text{CulinaryPerformancePoints} = \text{TotalDishesPrepared} \times \text{AvgFoodRating}$$

### 3. View 5.3: `View_Daily_Waiter_Collections` (Fiscal Cash Reconciliation)
Provides zero-leakage financial reconciliation by aggregating cash versus digital UPI collections per waiter per day:
$$\text{TotalShiftCollection} = \sum(\text{CashAmount}) + \sum(\text{UPIAmount})$$

### 4. View 5.4: `View_Monthly_Profit_Loss` (Enterprise Fiscal Reporting)
Reconciles gross restaurant revenue against incoming purchases, operational investments, payroll, and spoiled food wastelog losses:
$$\text{NetProfitLoss} = \sum(\text{IncomingRevenue}) - \sum(\text{OutgoingExpenses})$$
$$\text{ProfitMarginPercentage} = \frac{\text{NetProfitLoss}}{\text{IncomingRevenue}} \times 100$$

---

## 8. Role-Based Access Control (4 Operating Personas)

```
+-------------------+-----------------------------------------------------------------------------------+
| Role Persona      | Permitted Operations & UI Capabilities                                            |
+-------------------+-----------------------------------------------------------------------------------+
| 1. Waiter         | - Dining floor table occupancy map & multi-table reservation merging              |
|                   | - Order dispatch & dynamic portion availability enforcement                       |
|                   | - Authoritative partial & full dish cancellation with portion quantity selector   |
|                   | - Bill settlement with cash & UPI payment split calculator                        |
|                   | - Authenticated customer feedback submission with phone verification              |
+-------------------+-----------------------------------------------------------------------------------+
| 2. Chef           | - Kitchen Display System (KDS) live order queue filtered by assigned station      |
|                   | - Preparation status progression: 'Cooking' -> 'Ready' -> 'Plated'                |
|                   | - Direct advance portion stock replenishment (+5 / portions batch saver)          |
|                   | - Out-of-Stock (OOS) shortage declaration with atomic ingredient logging          |
|                   | - Culinary menu modification proposals (Add/Remove dishes)                        |
+-------------------+-----------------------------------------------------------------------------------+
| 3. Kitchen Mgr    | - Comprehensive kitchen floor oversight and multi-chef dispatch queue             |
|                   | - Discarded food & Waste Log register audit (with 80% cost valuation)            |
|                   | - Station ingredient restock monitoring & replenishment approvals                 |
|                   | - Chef culinary performance analytics & dish approval pipeline                   |
+-------------------+-----------------------------------------------------------------------------------+
| 4. Shop Mgr       | - Executive overview dashboard: Real-time Revenue, Expenses, and Net Profit/Loss  |
|                   | - Daily waiter cash/UPI shift reconciliation register                             |
|                   | - Operating Expense Register (Procurements, Payroll, Investments, and Wastelog)   |
|                   | - Single-Seat Handover Protocol execution (safe administrative credential rotation)|
|                   | - Staff credential management and account security administration                 |
+-------------------+-----------------------------------------------------------------------------------+
```

---

## 9. Single-Seat Administrative Handover Protocol

To satisfy security audit standards, administrative executive seats (**Kitchen Manager** and **Shop Manager**) permit strictly **one active account**:
1. When an executive manager departs, an atomic transaction executes:
   - Hard `DELETE` of the outgoing manager's credentials from `Users`.
   - Soft-retire the outgoing manager in `Staff` by setting `IsActive = 0`.
   - `INSERT` the successor into `Staff` with the appropriate `RoleID`.
   - `INSERT` new bcrypt credentials into `Users` referencing the successor's `EmployeeID`.
2. **Audit Preservation:** All historical orders, approvals, cash collections, and cooking logs remain permanently linked to the retired `EmployeeID`, guaranteeing zero audit trail corruption.

---

## 10. Verification & Test Suite Evidence

The codebase includes automated test suites covering relational integrity, triggers, views, and workflows:

| Test Identifier | Test Scope & Objective | Result |
|---|---|---|
| **TEST 1** | Schema DDL creation, 3NF foreign key cascades, column checks across 14 tables | **PASSED (100%)** |
| **TEST 2** | Verification of all 4 Business Intelligence Views (`View_Waiter_Performance`, etc.) | **PASSED (100%)** |
| **TEST 3** | Anti-Fraud check constraint (`chk_feedback_authenticity`) blocks padded reviews | **PASSED (100%)** |
| **TEST 4** | Multi-table M:N bridge table (`Order_Tables`) joins and frees tables upon payment | **PASSED (100%)** |
| **TEST 5** | Chef cancellation-consent flow and waste logging at 80% cost valuation | **PASSED (100%)** |
| **TEST 5B** | Partial dish cancellation (1 of 15 Biriyanis cancelled during cooking; 14 cooking; 80% waste logged) | **PASSED (100%)** |
| **TEST 5C** | Waiter cancellation options: before cooking (restores stock, 0 waste) vs during cooking (80% waste) | **PASSED (100%)** |
| **TEST 5D** | Automated trigger `trg_sync_wastelog_to_expenses` pushes wastelog debits into expenses | **PASSED (100%)** |
| **TEST 6** | Pre-cooking edit block triggers (`trg_block_order_detail_*`) block illegal modifications | **PASSED (100%)** |
| **TEST 7** | Out-of-stock atomic ACID transaction updates availability and logs shortage reason | **PASSED (100%)** |
| **TEST 7B** | Portion inventory auto-OOS transitions at 0 portions; recovers portions on pre-cook cancellation | **PASSED (100%)** |
| **TEST 8** | Single-Seat Handover Protocol deletes old credentials, soft-retires employee, enrolls successor | **PASSED (100%)** |
| **TEST 9** | Order checkout, payment splits (Cash + UPI), bill finalization, and table release | **PASSED (100%)** |
| **Overall Result** | **All 13 ACID, relational, and business workflow test suites pass with 100% success.** |

---

## 11. Project Presentation Checklist for Viva & Review

When presenting this project to an evaluator or review panel, highlight these 5 core engineering achievements:
1. **Show the 3NF Relational Schema:** Demonstrate how `Order_Tables` and `Order_Details` eliminate repeating groups and partial dependencies, and explain why snapshotting `UnitPrice` prevents historical price distortion.
2. **Demonstrate Partial Quantity Cancellation:** Order 15 Biriyanis, cancel 1 Biryani from the Waiter portal, show how 14 continue cooking on the Chef KDS, and show the exact 80% raw ingredient loss appearing in the Kitchen Manager Waste Log and Shop Manager Expense Register.
3. **Trigger Enforcements:** Show that direct SQL `DELETE` or `UPDATE` attempts on active dishes are physically rejected by database engine triggers (`Pre-Cooking Edit Block`).
4. **Single-Seat Handover:** Rotate the Kitchen Manager credentials live, showing that the old account is terminated, the successor is registered, and historical analytics remain completely intact.
5. **Real-Time SQL Views:** Open the Shop Manager Financial Overview to show real-time Net Profit/Loss and shift collection calculations executing dynamically through SQL views.

---

## 12. Formal Academic & Technical References

The architectural, relational, security, and algorithmic paradigms implemented in this project are grounded in the following seminal literature and engineering standards:

### 12.1 Relational Database Theory & Normalization (Edgar F. Codd)
1. **Codd, E. F. (1970).** "A Relational Model of Data for Large Shared Data Banks." *Communications of the ACM*, 13(6), 377–387.  
   - *Application in Project:* Establishes the mathematical foundation for relational algebra, candidate keys, foreign key constraints, and multi-relation table decomposition.
2. **Codd, E. F. (1972).** "Further Normalization of the Data Base Relational Model." In *Data Base Systems* (Courant Computer Science Symposia Series 6), Prentice-Hall, 33–64.  
   - *Application in Project:* Defines First (1NF), Second (2NF), and Third Normal Form (3NF), eliminating partial dependencies on composite keys (`Order_Tables`) and transitive dependencies (`Roles`, `Staff`, `Users`, and `Order_Details`).
3. **Fagin, R. (1977).** "Multivalued Dependencies and a New Normal Form for Relational Databases." *ACM Transactions on Database Systems (TODS)*, 2(3), 262–278.  
   - *Application in Project:* Underpins the isolation of independent multi-table relationships (`Order_Tables`) and line-item allocations (`Order_Details`).

### 12.2 Transaction Processing, Concurrency & ACID Boundaries (Jim Gray)
4. **Gray, J. (1981).** "The Transaction Concept: Virtues and Limitations." In *Proceedings of the 7th International Conference on Very Large Data Bases (VLDB)*, 144–154.  
   - *Application in Project:* Defines ACID properties (Atomicity, Consistency, Isolation, Durability) used in multi-table order dispatch, checkout bill settlements, and out-of-stock shortage declarations.
5. **Gray, J., & Reuter, A. (1993).** *Transaction Processing: Concepts and Techniques*. Morgan Kaufmann Publishers, San Francisco, CA.  
   - *Application in Project:* Informs the locking hierarchy, rollback protocols, and atomic boundaries (`BEGIN IMMEDIATE ... COMMIT`) implemented in `database/db.py`.
6. **Eswaran, K. P., Gray, J. N., Lorie, R. A., & Traiger, I. L. (1976).** "The Notions of Consistency and Predicate Locks in a Database System." *Communications of the ACM*, 19(11), 624–633.  
   - *Application in Project:* Guarantees serializability and row-level isolation preventing dirty reads or concurrent table collision during rush hours.

### 12.3 Role-Based Access Control & Security Architecture (Ferraiolo & Kuhn)
7. **Ferraiolo, D. F., & Kuhn, D. R. (1992).** "Role-Based Access Controls." In *Proceedings of the 15th National Computer Security Conference*, 554–563.  
   - *Application in Project:* Formulates the core RBAC model decoupling user identities from operational privileges across Waiters, Chefs, Kitchen Managers, and Shop Managers.
8. **Ferraiolo, D. F., Sandhu, R., Gavrila, S., Kuhn, D. R., & Chandramouli, R. (2001).** "Proposed NIST Standard for Role-Based Access Control." *ACM Transactions on Information and System Security (TISSEC)*, 4(3), 224–274.  
   - *Application in Project:* Direct foundation for the Single-Seat Handover Protocol, credential isolation (`Users` vs `Staff`), and permission matrices.
9. **Provos, N., & Mazières, D. (1999).** "A Future-Adaptable Password Scheme." In *Proceedings of the FREENIX Track: 1999 USENIX Annual Technical Conference*, 81–91.  
   - *Application in Project:* Implements the `bcrypt` adaptive hashing algorithm for salted cryptographic protection of `Users.PasswordHash`.

### 12.4 Standard Database System Design Textbooks
10. **Silberschatz, A., Korth, H. F., & Sudarshan, S. (2019).** *Database System Concepts* (7th ed.). McGraw-Hill Education, New York, NY.  
    - *Reference Chapters:* Chapter 7 (Relational Database Design & 3NF), Chapter 14 (Transactions), Chapter 15 (Concurrency Control).
11. **Ramakrishnan, R., & Gehrke, J. (2003).** *Database Management Systems* (3rd ed.). McGraw-Hill Education, Boston, MA.  
    - *Reference Chapters:* Functional dependency closure, lossy vs. lossless join decomposition, and database integrity triggers.
12. **Elmasri, R., & Navathe, S. B. (2016).** *Fundamentals of Database Systems* (7th ed.). Pearson Education, Hoboken, NJ.  
    - *Reference Chapters:* Relational constraints, SQL DDL/DML, and database view materialized aggregation.

### 12.5 Modern Web, API & Protocol Standards
13. **Jones, M., Bradley, J., & Sakimura, N. (2015).** "JSON Web Token (JWT)." *RFC 7519*, Internet Engineering Task Force (IETF). DOI: 10.17487/RFC7519.  
    - *Application in Project:* Secures stateless cross-origin REST communication between FastAPI routes and client UI viewports.
14. **Hipp, D. R., Kennedy, D., et al. (2024).** "SQLite: An Embeddable, ACID-Compliant Relational Database Engine." *SQLite Consortium Document Repository*.  
    - *Application in Project:* Governs the execution environment for zero-latency relational joins, foreign key cascades, and trigger raising (`RAISE(ABORT)`).
15. **Ramírez, S. (2018–2024).** "FastAPI: High-Performance Python Web Framework based on Starlette and Pydantic." *FastAPI Documentation*, https://fastapi.tiangolo.com.  
    - *Application in Project:* Framework for declarative request schema validation (`Pydantic v2`), dependency-injected JWT security guards, and atomic connection routing.
