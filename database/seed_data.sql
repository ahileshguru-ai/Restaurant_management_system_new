-- =====================================================================
-- Restaurant Relational Database - Comprehensive Seed Data
-- =====================================================================

-- 1. Roles
INSERT INTO Roles (RoleID, RoleName) VALUES
(1, 'Shop Manager'),
(2, 'Kitchen Manager'),
(3, 'Chef'),
(4, 'Waiter');

-- 2. Staff
INSERT INTO Staff (EmployeeID, Name, RoleID, Role, Shift, IsActive, Salary) VALUES
(1, 'Ramesh Sharma', 1, 'Shop Manager', 'General Shift', 1, 65000.00),
(2, 'Ananya Deshmukh', 2, 'Kitchen Manager', 'Morning Shift', 1, 48000.00),
(3, 'Chef Vikram Roy', 3, 'Chef', 'Morning Shift', 1, 40000.00),
(4, 'Chef Meera Sen', 3, 'Chef', 'Evening Shift', 1, 42000.00),
(5, 'Rahul Varma', 4, 'Waiter', 'Morning Shift', 1, 24000.00),
(6, 'Priya Nair', 4, 'Waiter', 'Evening Shift', 1, 24000.00);

-- 3. Users (Passwords hashed via bcrypt: manager123, kitchen123, chef123, waiter123)
INSERT INTO Users (UserID, EmployeeID, Username, PasswordHash, RoleID) VALUES
(1, 1, 'shopmanager', '$2b$12$B7us46gZPWgZFd9rHFArQOpI2wEKk6cXrceEnwynFrhmyi.y0PwkC', 1),
(2, 2, 'kitchenmgr', '$2b$12$ODj.XlRzEtW.VShGaZyWluVBu00zDsD2QC/JSQFnegujlq02d9E8y', 2),
(3, 3, 'chef_vikram', '$2b$12$y6lAqQX1MgmGUzmdfKw4aOfOHH4E1tcco60h3z9ygmRZD84HvJ8Bi', 3),
(4, 4, 'chef_meera', '$2b$12$y6lAqQX1MgmGUzmdfKw4aOfOHH4E1tcco60h3z9ygmRZD84HvJ8Bi', 3),
(5, 5, 'waiter_rahul', '$2b$12$So4/biFFYVUbiXiXCdB9XOQ43owzI8alDP7E65Ni/Q9Z2vZcUNXku', 4),
(6, 6, 'waiter_priya', '$2b$12$So4/biFFYVUbiXiXCdB9XOQ43owzI8alDP7E65Ni/Q9Z2vZcUNXku', 4);

-- 4. Tables
INSERT INTO Tables (TableNumber, SeatingCapacity, CurrentStatus) VALUES
(1, 2, 'Available'),
(2, 4, 'Available'),
(3, 4, 'Occupied'),
(4, 6, 'Available'),
(5, 8, 'Occupied'),
(6, 4, 'Available'),
(7, 2, 'Reserved'),
(8, 6, 'Available');

-- 5. Menu Items (AssignedChefID links to specific chefs)
-- Chef 3 (Vikram) specializes in South Indian & Curries
-- Chef 4 (Meera) specializes in Biryani & Breads
INSERT INTO Menu_Items (MenuItemID, ItemName, Category, Price, StockQuantity, IsAvailable, AssignedChefID) VALUES
(1, 'Crispy Masala Dosa', 'South Indian', 130.00, 15, 1, 3),
(2, 'Ghee Roast Dosa', 'South Indian', 160.00, 12, 1, 3),
(3, 'Medu Vada (2 Pcs)', 'South Indian', 90.00, 10, 1, 3),
(4, 'Hyderabadi Chicken Biryani', 'Biryani', 290.00, 20, 1, 4),
(5, 'Royal Mutton Biryani', 'Biryani', 360.00, 15, 1, 4),
(6, 'Paneer Butter Masala', 'Curries', 240.00, 12, 1, 3),
(7, 'Dal Makhani Slow-Cooked', 'Curries', 210.00, 14, 1, 4),
(8, 'Butter Garlic Naan', 'Breads', 65.00, 25, 1, 4),
(9, 'Steamed Idly (2 Pcs)', 'South Indian', 70.00, 10, 1, 3);

-- 6. Inventory (AssignedChefID: 3 = Chef Vikram [South Indian/Curries], 4 = Chef Meera [Biryani/Breads])
INSERT INTO Inventory (IngredientID, IngredientName, NeedsRestock, AssignedChefID, ReportedBy_ChefID, LastUpdated) VALUES
(1, 'Fermented Dosa Batter (kg)', 0, 3, 3, CURRENT_TIMESTAMP),
(2, 'Aged Basmati Rice (kg)', 0, 4, 4, CURRENT_TIMESTAMP),
(3, 'Fresh Cottage Cheese / Paneer (kg)', 0, 3, 3, CURRENT_TIMESTAMP),
(4, 'Farm Fresh Chicken (kg)', 0, 4, 4, CURRENT_TIMESTAMP),
(5, 'Pure Desi Ghee (Litre)', 0, 3, 3, CURRENT_TIMESTAMP),
(6, 'Royal Biryani Whole Spices Pack', 0, 4, 4, CURRENT_TIMESTAMP),
(7, 'Organic Dairy Cooking Cream (kg)', 0, 4, 4, CURRENT_TIMESTAMP);

-- 7. Shortage Logs
INSERT INTO Shortage_Logs (LogID, MenuItemID, ChefID, Reason, LogTimestamp) VALUES
(1, 6, 3, 'Fresh dairy delivery delayed by supplier', '2026-10-10 11:30:00');

-- 8. Menu Requests
INSERT INTO Menu_Requests (RequestID, ChefID, DishName, RequestType, Reason, Status, CreatedAt) VALUES
(1, 3, 'Rava Onion Dosa', 'Add', 'High customer demand during morning breakfast peak hours', 'Approved', '2026-10-08 09:00:00'),
(2, 4, 'Prawn Dum Biryani', 'Add', 'Weekend coastal seafood special requested by diners', 'Pending', '2026-10-11 10:15:00'),
(3, 3, 'Plain Uttapam', 'Remove', 'Very low sales velocity over the past 45 days', 'Pending', '2026-10-11 11:00:00');

-- 9. Historical & Active Orders
INSERT INTO Orders (OrderID, WaiterID, CustomerCount, OrderTimestamp, CashAmount, UPIAmount, OrderStatus) VALUES
(1, 5, 4, '2026-10-09 13:15:00', 450.00, 230.00, 'Completed'),
(2, 5, 2, '2026-10-10 14:00:00', 0.00, 385.00, 'Completed'),
(3, 6, 6, '2026-10-10 20:30:00', 800.00, 755.00, 'Completed'),
(4, 6, 3, '2026-10-11 19:00:00', 300.00, 300.00, 'Completed'),
(5, 5, 4, '2026-10-11 21:00:00', 0.00, 0.00, 'In Progress'),
(6, 6, 8, '2026-10-11 21:30:00', 0.00, 0.00, 'In Progress');

-- 10. Order_Tables (Bridge Table resolving M:N table associations)
INSERT INTO Order_Tables (OrderID, TableNumber) VALUES
(1, 1),
(2, 2),
(3, 4),
(4, 6),
(5, 3),
(6, 5);

-- 11. Order_Details (Bridge Table resolving M:N Order-Dish associations)
INSERT INTO Order_Details (OrderDetailID, OrderID, MenuItemID, Quantity, UnitPrice, Subtotal, PreparedBy_EmployeeID, ItemStatus, CancellationReason) VALUES
(1, 1, 1, 2, 130.00, 260.00, 3, 'Ready', NULL),
(2, 1, 4, 1, 290.00, 290.00, 4, 'Ready', NULL),
(3, 1, 8, 2, 65.00, 130.00, 4, 'Ready', NULL),
(4, 2, 2, 2, 160.00, 320.00, 3, 'Ready', NULL),
(5, 2, 8, 1, 65.00, 65.00, 4, 'Cancelled', 'Customer allergy notification'),
(6, 3, 4, 3, 290.00, 870.00, 4, 'Ready', NULL),
(7, 3, 5, 1, 360.00, 360.00, 4, 'Ready', NULL),
(8, 3, 8, 5, 65.00, 325.00, 4, 'Ready', NULL),
(9, 4, 1, 3, 130.00, 390.00, 3, 'Ready', NULL),
(10, 4, 7, 1, 210.00, 210.00, 4, 'Ready', NULL),
(11, 5, 1, 2, 130.00, 260.00, 3, 'Pending', NULL),
(12, 5, 4, 1, 290.00, 290.00, 4, 'Cooking', NULL),
(13, 6, 4, 2, 290.00, 580.00, 4, 'Cancel Requested', NULL),
(14, 6, 2, 3, 160.00, 480.00, 3, 'Cooking', NULL);

-- 12. Feedback (Strictly follows chk_feedback_authenticity anti-fraud constraint)
INSERT INTO Feedback (FeedbackID, OrderID, CustomerName, PhoneNumber, ServiceRating, FoodRating, AmbienceRating, CleanlinessRating, ReviewText) VALUES
(1, 1, 'Aditya Gupta', '9876543210', 5, 5, 4, 5, 'Outstanding crispy dosa and warm, prompt service by Rahul!'),
(2, 2, 'Sunita Rao', '9811223344', 4, 4, 4, 4, 'Good quality food and clean ambiance. Appreciate the hygienic kitchen.'),
(3, 3, 'Karthik Raja', '9845012345', 5, 5, 5, 5, 'Biryani was royal and flavourful. Exceptional dining experience for family!'),
(4, 4, 'Divya Iyer', '9870098700', 4, 4, 4, 4, 'Quick evening dinner. Priya attended our table with great hospitality.');

-- 13. Purchase_Expenses
INSERT INTO Purchase_Expenses (ExpenseID, ExpenseDate, ExpenseAmount, ExpenseType, Description) VALUES
(1, '2026-09-05', 45000.00, 'Raw Materials', 'Bulk Grains, Dosa Batter & Dairy Procurement'),
(2, '2026-09-28', 120000.00, 'Payroll', 'September Month Staff Salary & Benefits Disbursement'),
(3, '2026-09-15', 15000.00, 'Other Investments', 'Commercial Induction Cooktops & Heavy Cookware'),
(4, '2026-10-02', 38000.00, 'Raw Materials', 'Fresh Vegetables & Whole Spices Delivery'),
(5, '2026-10-08', 22000.00, 'Raw Materials', 'Weekly Poultry & Dairy Farm Supplies'),
(6, '2026-10-10', 120000.00, 'Payroll', 'October Month Staff Salary & Benefits Disbursement');

-- 14. Waste_Log (Automatically triggers synchronized entry in Purchase_Expenses with description 'wastelog')
INSERT INTO Waste_Log (WasteID, OrderDetailID, IngredientCost, LogTimestamp) VALUES
(1, 5, 35.00, '2026-10-10 14:15:00');
