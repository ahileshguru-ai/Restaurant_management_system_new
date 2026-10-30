-- =====================================================================
-- Restaurant Relational Database Management System (3NF)
-- Dialect: MySQL 8.0+
-- Theoretical Foundations:
--   - 3NF Relational Normalization (Edgar F. Codd)
--   - Role-Based Access Control (David Ferraiolo & Richard Kuhn)
--   - ACID Transactions & Row-Level Locking (Jim Gray)
-- =====================================================================

DROP DATABASE IF EXISTS restaurant_db;
CREATE DATABASE restaurant_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE restaurant_db;

-- =====================================================================
-- SECTION A: Personnel & Security (RBAC)
-- =====================================================================

CREATE TABLE Roles (
    RoleID INT AUTO_INCREMENT PRIMARY KEY,
    RoleName VARCHAR(50) NOT NULL UNIQUE,
    CONSTRAINT chk_valid_role CHECK (RoleName IN ('Shop Manager', 'Kitchen Manager', 'Chef', 'Waiter'))
) ENGINE=InnoDB;

CREATE TABLE Staff (
    EmployeeID INT AUTO_INCREMENT PRIMARY KEY,
    Name VARCHAR(100) NOT NULL,
    RoleID INT NOT NULL,
    Role VARCHAR(50) NOT NULL,
    Shift VARCHAR(30) NULL,
    IsActive BOOLEAN DEFAULT TRUE NOT NULL,
    Salary DECIMAL(10,2) DEFAULT 30000.00 NOT NULL CHECK (Salary >= 0),
    CONSTRAINT fk_staff_role FOREIGN KEY (RoleID) REFERENCES Roles(RoleID) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE Users (
    UserID INT AUTO_INCREMENT PRIMARY KEY,
    EmployeeID INT NOT NULL UNIQUE,
    Username VARCHAR(50) NOT NULL UNIQUE,
    PasswordHash VARCHAR(255) NOT NULL,
    RoleID INT NOT NULL,
    CONSTRAINT fk_users_staff FOREIGN KEY (EmployeeID) REFERENCES Staff(EmployeeID) ON DELETE CASCADE,
    CONSTRAINT fk_users_role FOREIGN KEY (RoleID) REFERENCES Roles(RoleID) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- =====================================================================
-- SECTION B: Menu, Kitchen & Inventory
-- =====================================================================

CREATE TABLE Menu_Items (
    MenuItemID INT AUTO_INCREMENT PRIMARY KEY,
    ItemName VARCHAR(100) NOT NULL,
    Category VARCHAR(50) NOT NULL,
    Price DECIMAL(10,2) NOT NULL,
    StockQuantity INT NOT NULL DEFAULT 10,
    IsAvailable BOOLEAN DEFAULT TRUE NOT NULL,
    AssignedChefID INT NOT NULL,
    IsActive BOOLEAN DEFAULT TRUE NOT NULL,
    CONSTRAINT chk_menu_price CHECK (Price > 0),
    CONSTRAINT chk_menu_stock CHECK (StockQuantity >= 0),
    CONSTRAINT fk_menu_chef FOREIGN KEY (AssignedChefID) REFERENCES Staff(EmployeeID)
) ENGINE=InnoDB;

CREATE TABLE Inventory (
    IngredientID INT AUTO_INCREMENT PRIMARY KEY,
    IngredientName VARCHAR(100) NOT NULL,
    NeedsRestock BOOLEAN DEFAULT FALSE NOT NULL,
    ReportedBy_ChefID INT NULL,
    LastUpdated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_inventory_chef FOREIGN KEY (ReportedBy_ChefID) REFERENCES Staff(EmployeeID) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE Shortage_Logs (
    LogID INT AUTO_INCREMENT PRIMARY KEY,
    MenuItemID INT NOT NULL,
    ChefID INT NOT NULL,
    Reason VARCHAR(255) NOT NULL,
    LogTimestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_shortage_menu FOREIGN KEY (MenuItemID) REFERENCES Menu_Items(MenuItemID) ON DELETE CASCADE,
    CONSTRAINT fk_shortage_chef FOREIGN KEY (ChefID) REFERENCES Staff(EmployeeID)
) ENGINE=InnoDB;

CREATE TABLE Menu_Requests (
    RequestID INT AUTO_INCREMENT PRIMARY KEY,
    ChefID INT NOT NULL,
    DishName VARCHAR(100) NOT NULL,
    RequestType VARCHAR(10) NOT NULL,
    Reason TEXT NOT NULL,
    Status VARCHAR(20) DEFAULT 'Pending' NOT NULL,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_request_type CHECK (RequestType IN ('Add', 'Remove')),
    CONSTRAINT chk_request_status CHECK (Status IN ('Pending', 'Approved', 'Rejected')),
    CONSTRAINT fk_request_chef FOREIGN KEY (ChefID) REFERENCES Staff(EmployeeID)
) ENGINE=InnoDB;

-- =====================================================================
-- SECTION C: Floor Operations & Ordering
-- =====================================================================

CREATE TABLE Tables (
    TableNumber INT PRIMARY KEY,
    SeatingCapacity INT NOT NULL,
    CurrentStatus VARCHAR(20) DEFAULT 'Available' NOT NULL,
    CONSTRAINT chk_table_capacity CHECK (SeatingCapacity > 0),
    CONSTRAINT chk_table_status CHECK (CurrentStatus IN ('Available', 'Occupied', 'Reserved'))
) ENGINE=InnoDB;

CREATE TABLE Orders (
    OrderID INT AUTO_INCREMENT PRIMARY KEY,
    WaiterID INT NOT NULL,
    CustomerCount INT NOT NULL,
    OrderTimestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CashAmount DECIMAL(10,2) DEFAULT 0.00 NOT NULL,
    UPIAmount DECIMAL(10,2) DEFAULT 0.00 NOT NULL,
    OrderStatus VARCHAR(20) DEFAULT 'In Progress' NOT NULL,
    CONSTRAINT chk_customer_count CHECK (CustomerCount > 0),
    CONSTRAINT chk_cash_amount CHECK (CashAmount >= 0),
    CONSTRAINT chk_upi_amount CHECK (UPIAmount >= 0),
    CONSTRAINT chk_order_status CHECK (OrderStatus IN ('In Progress', 'Completed', 'Cancelled')),
    CONSTRAINT fk_order_waiter FOREIGN KEY (WaiterID) REFERENCES Staff(EmployeeID)
) ENGINE=InnoDB;

CREATE TABLE Order_Tables (
    OrderID INT NOT NULL,
    TableNumber INT NOT NULL,
    PRIMARY KEY (OrderID, TableNumber),
    CONSTRAINT fk_ordertables_order FOREIGN KEY (OrderID) REFERENCES Orders(OrderID) ON DELETE CASCADE,
    CONSTRAINT fk_ordertables_table FOREIGN KEY (TableNumber) REFERENCES Tables(TableNumber) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE Order_Details (
    OrderDetailID INT AUTO_INCREMENT PRIMARY KEY,
    OrderID INT NOT NULL,
    MenuItemID INT NOT NULL,
    Quantity INT NOT NULL,
    UnitPrice DECIMAL(10,2) NOT NULL,
    Subtotal DECIMAL(10,2) NOT NULL,
    PreparedBy_EmployeeID INT NOT NULL,
    ItemStatus VARCHAR(20) DEFAULT 'Pending' NOT NULL,
    CancellationReason VARCHAR(255) NULL,
    CONSTRAINT chk_detail_quantity CHECK (Quantity > 0),
    CONSTRAINT chk_detail_unitprice CHECK (UnitPrice >= 0),
    CONSTRAINT chk_detail_subtotal CHECK (Subtotal >= 0),
    CONSTRAINT chk_detail_itemstatus CHECK (ItemStatus IN ('Pending', 'Cooking', 'Ready', 'Cancel Requested', 'Cancelled')),
    CONSTRAINT fk_details_order FOREIGN KEY (OrderID) REFERENCES Orders(OrderID) ON DELETE CASCADE,
    CONSTRAINT fk_details_menu FOREIGN KEY (MenuItemID) REFERENCES Menu_Items(MenuItemID),
    CONSTRAINT fk_details_chef FOREIGN KEY (PreparedBy_EmployeeID) REFERENCES Staff(EmployeeID)
) ENGINE=InnoDB;

-- =====================================================================
-- SECTION D: Analytics, Waste & Feedback
-- =====================================================================

CREATE TABLE Feedback (
    FeedbackID INT AUTO_INCREMENT PRIMARY KEY,
    OrderID INT NOT NULL UNIQUE,
    CustomerName VARCHAR(100) NULL,
    PhoneNumber VARCHAR(20) NULL,
    ServiceRating INT NULL,
    FoodRating INT NULL,
    AmbienceRating INT NULL,
    CleanlinessRating INT NULL,
    ReviewText TEXT NULL,
    CONSTRAINT chk_service_rating CHECK (ServiceRating BETWEEN 1 AND 5),
    CONSTRAINT chk_food_rating CHECK (FoodRating BETWEEN 1 AND 5),
    CONSTRAINT chk_ambience_rating CHECK (AmbienceRating BETWEEN 1 AND 5),
    CONSTRAINT chk_cleanliness_rating CHECK (CleanlinessRating BETWEEN 1 AND 5),
    CONSTRAINT chk_feedback_authenticity CHECK (
        (ServiceRating IS NULL AND CustomerName IS NULL AND PhoneNumber IS NULL)
        OR
        (ServiceRating IS NOT NULL AND CustomerName IS NOT NULL AND PhoneNumber IS NOT NULL)
    ),
    CONSTRAINT fk_feedback_order FOREIGN KEY (OrderID) REFERENCES Orders(OrderID) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE Waste_Log (
    WasteID INT AUTO_INCREMENT PRIMARY KEY,
    OrderDetailID INT NULL,
    IngredientCost DECIMAL(10,2) NOT NULL,
    LogTimestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_waste_cost CHECK (IngredientCost >= 0),
    CONSTRAINT fk_waste_orderdetail FOREIGN KEY (OrderDetailID) REFERENCES Order_Details(OrderDetailID) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE Purchase_Expenses (
    ExpenseID INT AUTO_INCREMENT PRIMARY KEY,
    ExpenseDate DATE NOT NULL,
    ExpenseAmount DECIMAL(10,2) NOT NULL,
    ExpenseType VARCHAR(50) NOT NULL,
    CONSTRAINT chk_expense_amount CHECK (ExpenseAmount > 0),
    CONSTRAINT chk_expense_type CHECK (ExpenseType IN ('Raw Materials', 'Other Investments', 'Payroll'))
) ENGINE=InnoDB;

-- =====================================================================
-- SECTION E: Automated Business Intelligence Views
-- =====================================================================

-- 5.1 Waiter Performance Leaderboard
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

-- 5.2 Chef Culinary Production & Quality Leaderboard
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

-- 5.3 Daily Financial Reconciliation (Per Waiter)
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

-- 5.4 Monthly Profit, Loss & Waste Trend Analytics
CREATE VIEW View_Monthly_Profit_Loss AS
SELECT
    DATE_FORMAT(o.OrderTimestamp, '%Y-%m') AS ReportingMonth,
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
        DATE_FORMAT(ExpenseDate, '%Y-%m') AS ExpenseMonth,
        SUM(ExpenseAmount) AS TotalOutgoingExpenses
    FROM Purchase_Expenses
    GROUP BY DATE_FORMAT(ExpenseDate, '%Y-%m')
) e ON DATE_FORMAT(o.OrderTimestamp, '%Y-%m') = e.ExpenseMonth
GROUP BY DATE_FORMAT(o.OrderTimestamp, '%Y-%m'), e.TotalOutgoingExpenses;

-- =====================================================================
-- SECTION F: Pre-Cooking Edit Block Database Triggers
-- =====================================================================

DELIMITER $$

CREATE TRIGGER trg_block_order_detail_delete
BEFORE DELETE ON Order_Details
FOR EACH ROW
BEGIN
    IF OLD.ItemStatus != 'Pending' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Pre-Cooking Edit Block: Cannot delete order item once status moves past Pending. Initiate Cancellation-Consent flow instead.';
    END IF;
END$$

CREATE TRIGGER trg_block_order_detail_update
BEFORE UPDATE ON Order_Details
FOR EACH ROW
BEGIN
    IF OLD.ItemStatus != 'Pending' AND (OLD.MenuItemID != NEW.MenuItemID OR OLD.UnitPrice != NEW.UnitPrice OR NEW.Quantity > OLD.Quantity) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Pre-Cooking Edit Block: Cannot modify dish, unit price, or increase quantity once status moves past Pending.';
    END IF;
END$$

-- =====================================================================
-- SECTION G: Automated Waste Log to Expenses Synchronization Trigger
-- =====================================================================

CREATE TRIGGER trg_sync_wastelog_to_expenses
AFTER INSERT ON Waste_Log
FOR EACH ROW
BEGIN
    IF NEW.IngredientCost > 0 THEN
        INSERT INTO Purchase_Expenses (ExpenseDate, ExpenseAmount, ExpenseType, Description)
        VALUES (CURDATE(), NEW.IngredientCost, 'Raw Materials', 'wastelog');
    END IF;
END$$

DELIMITER ;
