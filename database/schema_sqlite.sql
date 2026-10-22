-- =====================================================================
-- Restaurant Relational Database Management System (3NF)
-- Dialect: SQLite 3 (Standard Local Embedded Engine)
-- Theoretical Foundations:
--   - 3NF Relational Normalization (Edgar F. Codd)
--   - Role-Based Access Control (David Ferraiolo & Richard Kuhn)
--   - ACID Transactions & Concurrency Control (Jim Gray)
-- =====================================================================

PRAGMA foreign_keys = ON;

-- =====================================================================
-- SECTION A: Personnel & Security (RBAC)
-- =====================================================================

CREATE TABLE IF NOT EXISTS Roles (
    RoleID INTEGER PRIMARY KEY AUTOINCREMENT,
    RoleName TEXT NOT NULL UNIQUE CHECK (RoleName IN ('Shop Manager', 'Kitchen Manager', 'Chef', 'Waiter'))
);

CREATE TABLE IF NOT EXISTS Staff (
    EmployeeID INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL,
    RoleID INTEGER NOT NULL,
    Role TEXT NOT NULL,
    Shift TEXT,
    IsActive INTEGER DEFAULT 1 NOT NULL CHECK (IsActive IN (0, 1)),
    Salary REAL DEFAULT 30000.00 NOT NULL CHECK (Salary >= 0),
    FOREIGN KEY (RoleID) REFERENCES Roles(RoleID) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS Users (
    UserID INTEGER PRIMARY KEY AUTOINCREMENT,
    EmployeeID INTEGER NOT NULL UNIQUE,
    Username TEXT NOT NULL UNIQUE,
    PasswordHash TEXT NOT NULL,
    RoleID INTEGER NOT NULL,
    FOREIGN KEY (EmployeeID) REFERENCES Staff(EmployeeID) ON DELETE CASCADE,
    FOREIGN KEY (RoleID) REFERENCES Roles(RoleID) ON DELETE RESTRICT
);

-- =====================================================================
-- SECTION B: Menu, Kitchen & Inventory
-- =====================================================================

CREATE TABLE IF NOT EXISTS Menu_Items (
    MenuItemID INTEGER PRIMARY KEY AUTOINCREMENT,
    ItemName TEXT NOT NULL,
    Category TEXT NOT NULL,
    Price REAL NOT NULL CHECK (Price > 0),
    IsAvailable INTEGER DEFAULT 1 NOT NULL CHECK (IsAvailable IN (0, 1)),
    AssignedChefID INTEGER NOT NULL,
    IsActive INTEGER DEFAULT 1 NOT NULL CHECK (IsActive IN (0, 1)),
    FOREIGN KEY (AssignedChefID) REFERENCES Staff(EmployeeID)
);

CREATE TABLE IF NOT EXISTS Inventory (
    IngredientID INTEGER PRIMARY KEY AUTOINCREMENT,
    IngredientName TEXT NOT NULL,
    NeedsRestock INTEGER DEFAULT 0 NOT NULL CHECK (NeedsRestock IN (0, 1)),
    AssignedChefID INTEGER NULL,
    ReportedBy_ChefID INTEGER NULL,
    LastUpdated DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (AssignedChefID) REFERENCES Staff(EmployeeID) ON DELETE SET NULL,
    FOREIGN KEY (ReportedBy_ChefID) REFERENCES Staff(EmployeeID) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS Shortage_Logs (
    LogID INTEGER PRIMARY KEY AUTOINCREMENT,
    MenuItemID INTEGER NOT NULL,
    ChefID INTEGER NOT NULL,
    Reason TEXT NOT NULL,
    LogTimestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (MenuItemID) REFERENCES Menu_Items(MenuItemID) ON DELETE CASCADE,
    FOREIGN KEY (ChefID) REFERENCES Staff(EmployeeID)
);

CREATE TABLE IF NOT EXISTS Menu_Requests (
    RequestID INTEGER PRIMARY KEY AUTOINCREMENT,
    ChefID INTEGER NOT NULL,
    DishName TEXT NOT NULL,
    RequestType TEXT NOT NULL CHECK (RequestType IN ('Add', 'Remove')),
    Reason TEXT NOT NULL,
    Status TEXT DEFAULT 'Pending' NOT NULL CHECK (Status IN ('Pending', 'Approved', 'Rejected')),
    CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ChefID) REFERENCES Staff(EmployeeID)
);

-- =====================================================================
-- SECTION C: Floor Operations & Ordering
-- =====================================================================

CREATE TABLE IF NOT EXISTS Tables (
    TableNumber INTEGER PRIMARY KEY,
    SeatingCapacity INTEGER NOT NULL CHECK (SeatingCapacity > 0),
    CurrentStatus TEXT DEFAULT 'Available' NOT NULL CHECK (CurrentStatus IN ('Available', 'Occupied', 'Reserved'))
);

CREATE TABLE IF NOT EXISTS Orders (
    OrderID INTEGER PRIMARY KEY AUTOINCREMENT,
    WaiterID INTEGER NOT NULL,
    CustomerCount INTEGER NOT NULL CHECK (CustomerCount > 0),
    OrderTimestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    CashAmount REAL DEFAULT 0.00 NOT NULL CHECK (CashAmount >= 0),
    UPIAmount REAL DEFAULT 0.00 NOT NULL CHECK (UPIAmount >= 0),
    OrderStatus TEXT DEFAULT 'In Progress' NOT NULL CHECK (OrderStatus IN ('In Progress', 'Completed', 'Cancelled')),
    FOREIGN KEY (WaiterID) REFERENCES Staff(EmployeeID)
);

CREATE TABLE IF NOT EXISTS Order_Tables (
    OrderID INTEGER NOT NULL,
    TableNumber INTEGER NOT NULL,
    PRIMARY KEY (OrderID, TableNumber),
    FOREIGN KEY (OrderID) REFERENCES Orders(OrderID) ON DELETE CASCADE,
    FOREIGN KEY (TableNumber) REFERENCES Tables(TableNumber) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS Order_Details (
    OrderDetailID INTEGER PRIMARY KEY AUTOINCREMENT,
    OrderID INTEGER NOT NULL,
    MenuItemID INTEGER NOT NULL,
    Quantity INTEGER NOT NULL CHECK (Quantity > 0),
    UnitPrice REAL NOT NULL CHECK (UnitPrice >= 0),
    Subtotal REAL NOT NULL CHECK (Subtotal >= 0),
    PreparedBy_EmployeeID INTEGER NOT NULL,
    ItemStatus TEXT DEFAULT 'Pending' NOT NULL CHECK (ItemStatus IN ('Pending', 'Cooking', 'Ready', 'Cancel Requested', 'Cancelled')),
    CancellationReason TEXT NULL,
    FOREIGN KEY (OrderID) REFERENCES Orders(OrderID) ON DELETE CASCADE,
    FOREIGN KEY (MenuItemID) REFERENCES Menu_Items(MenuItemID),
    FOREIGN KEY (PreparedBy_EmployeeID) REFERENCES Staff(EmployeeID)
);

-- =====================================================================
-- SECTION D: Analytics, Waste & Feedback
-- =====================================================================

CREATE TABLE IF NOT EXISTS Feedback (
    FeedbackID INTEGER PRIMARY KEY AUTOINCREMENT,
    OrderID INTEGER NOT NULL UNIQUE,
    CustomerName TEXT NULL,
    PhoneNumber TEXT NULL,
    ServiceRating INTEGER NULL CHECK (ServiceRating BETWEEN 1 AND 5),
    FoodRating INTEGER NULL CHECK (FoodRating BETWEEN 1 AND 5),
    AmbienceRating INTEGER NULL CHECK (AmbienceRating BETWEEN 1 AND 5),
    CleanlinessRating INTEGER NULL CHECK (CleanlinessRating BETWEEN 1 AND 5),
    ReviewText TEXT NULL,
    CONSTRAINT chk_feedback_authenticity CHECK (
        (ServiceRating IS NULL AND CustomerName IS NULL AND PhoneNumber IS NULL)
        OR
        (ServiceRating IS NOT NULL AND CustomerName IS NOT NULL AND PhoneNumber IS NOT NULL)
    ),
    FOREIGN KEY (OrderID) REFERENCES Orders(OrderID) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Waste_Log (
    WasteID INTEGER PRIMARY KEY AUTOINCREMENT,
    OrderDetailID INTEGER NULL,
    IngredientCost REAL NOT NULL CHECK (IngredientCost >= 0),
    LogTimestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (OrderDetailID) REFERENCES Order_Details(OrderDetailID) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS Purchase_Expenses (
    ExpenseID INTEGER PRIMARY KEY AUTOINCREMENT,
    ExpenseDate DATE NOT NULL,
    ExpenseAmount REAL NOT NULL CHECK (ExpenseAmount > 0),
    ExpenseType TEXT NOT NULL CHECK (ExpenseType IN ('Raw Materials', 'Other Investments', 'Payroll')),
    Description TEXT NULL
);

-- =====================================================================
-- SECTION E: Automated Business Intelligence Views
-- =====================================================================

-- 5.1 Waiter Performance Leaderboard
DROP VIEW IF EXISTS View_Waiter_Performance;
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

-- 5.2 Chef Culinary Production & Quality Leaderboard
DROP VIEW IF EXISTS View_Chef_Performance;
CREATE VIEW View_Chef_Performance AS
SELECT
    s.EmployeeID AS ChefID,
    s.Name AS ChefName,
    COALESCE(SUM(od.Quantity), 0) AS TotalDishesPrepared,
    ROUND(AVG(f.FoodRating), 2) AS AvgFoodRating,
    ROUND(COALESCE(SUM(od.Quantity), 0) * COALESCE(AVG(f.FoodRating), 0), 2) AS CulinaryPerformancePoints
FROM Staff s
JOIN Order_Details od ON s.EmployeeID = od.PreparedBy_EmployeeID
JOIN Orders o ON od.OrderID = o.OrderID
LEFT JOIN Feedback f ON o.OrderID = f.OrderID
WHERE s.Role = 'Chef' AND s.IsActive = 1 AND od.ItemStatus = 'Ready'
GROUP BY s.EmployeeID, s.Name;

-- 5.3 Daily Financial Reconciliation (Per Waiter)
DROP VIEW IF EXISTS View_Daily_Waiter_Collections;
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

-- 5.4 Monthly Profit, Loss & Waste Trend Analytics
DROP VIEW IF EXISTS View_Monthly_Profit_Loss;
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

-- =====================================================================
-- SECTION F: Pre-Cooking Edit Block Triggers
-- =====================================================================

CREATE TRIGGER IF NOT EXISTS trg_block_order_detail_delete
BEFORE DELETE ON Order_Details
FOR EACH ROW
WHEN OLD.ItemStatus != 'Pending'
BEGIN
    SELECT RAISE(ABORT, 'Pre-Cooking Edit Block: Cannot delete order item once status moves past Pending. Initiate Cancellation-Consent flow instead.');
END;

CREATE TRIGGER IF NOT EXISTS trg_block_order_detail_update
BEFORE UPDATE ON Order_Details
FOR EACH ROW
WHEN OLD.ItemStatus != 'Pending' AND (OLD.MenuItemID != NEW.MenuItemID OR OLD.Quantity != NEW.Quantity OR OLD.UnitPrice != NEW.UnitPrice)
BEGIN
    SELECT RAISE(ABORT, 'Pre-Cooking Edit Block: Cannot modify dish, quantity, or unit price once status moves past Pending.');
END;
