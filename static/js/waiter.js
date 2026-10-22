/**
 * Waiter Mobile Dashboard Controller (360px - 480px Viewport Target)
 * Floor table assignment, order execution, cancellation requests,
 * Cash/UPI checkout splits, and Anti-Fraud verified feedback.
 */

const WaiterModule = {
  menu: [],
  tables: [],
  activeOrders: [],
  selectedTables: [],
  orderItems: {}, // menuItemId -> qty
  currentCheckoutOrder: null,

  async init() {
    this.selectedTables = [];
    this.orderItems = {};
    await this.refresh();
  },

  async refresh() {
    await Promise.all([
      this.fetchTables(),
      this.fetchMenu(),
      this.fetchOrders(),
      this.fetchDailySummary()
    ]);
  },

  async fetchTables() {
    try {
      const data = await App.apiFetch("/api/waiter/tables");
      this.tables = data.tables || [];
      this.renderTables();
    } catch (e) {
      console.error("Error fetching tables", e);
    }
  },

  async fetchMenu() {
    try {
      const data = await App.apiFetch("/api/waiter/menu");
      this.menu = data.menu || [];
      this.renderMenuPicker();
    } catch (e) {
      console.error("Error fetching menu", e);
    }
  },

  async fetchOrders() {
    try {
      const data = await App.apiFetch("/api/waiter/orders");
      this.activeOrders = data.orders || [];
      this.renderOrders();
    } catch (e) {
      console.error("Error fetching orders", e);
    }
  },

  async fetchDailySummary() {
    try {
      const data = await App.apiFetch("/api/waiter/daily-summary");
      const s = data.summary || {};
      const el = document.getElementById("waiterDailyStats");
      if (el) {
        el.innerHTML = `
          <div style="display:flex; justify-content:space-between; font-size:12px; font-weight:700;">
            <span>Customers Served: <strong>${s.TodayCustomers || 0}</strong></span>
            <span>Total Collected: <strong>Rs.${(s.TodayTotal || 0).toFixed(2)}</strong></span>
            <span>Cash: Rs.${(s.TodayCash || 0).toFixed(0)} | UPI: Rs.${(s.TodayUPI || 0).toFixed(0)}</span>
          </div>
        `;
      }
    } catch (e) {
      console.error("Error fetching daily stats", e);
    }
  },

  renderTables() {
    const grid = document.getElementById("waiterTableGrid");
    if (!grid) return;

    grid.innerHTML = "";
    this.tables.forEach(t => {
      const tile = document.createElement("div");
      const isSelected = this.selectedTables.includes(t.TableNumber);
      tile.className = `table-bubble-tile ${t.CurrentStatus.toLowerCase()} ${isSelected ? 'selected' : ''}`;
      tile.innerHTML = `
        <div class="table-tile-num">T-${t.TableNumber}</div>
        <div class="table-tile-meta">${t.SeatingCapacity} seats</div>
        <div class="table-tile-meta">${t.CurrentStatus}</div>
      `;
      tile.addEventListener("click", () => this.toggleTableSelect(t.TableNumber));
      grid.appendChild(tile);
    });

    const label = document.getElementById("selectedTablesLabel");
    if (label) {
      label.textContent = this.selectedTables.length > 0 
        ? `Selected: Table ${this.selectedTables.join(", ")}` 
        : "Tap table(s) above to assign";
    }
  },

  toggleTableSelect(tableNum) {
    if (this.selectedTables.includes(tableNum)) {
      this.selectedTables = this.selectedTables.filter(n => n !== tableNum);
    } else {
      this.selectedTables.push(tableNum);
    }
    this.renderTables();
  },

  renderMenuPicker() {
    const list = document.getElementById("waiterMenuPickerList");
    if (!list) return;

    list.innerHTML = "";
    this.menu.forEach(item => {
      const row = document.createElement("div");
      row.style.cssText = "display:flex; align-items:center; justify-content:space-between; padding:10px 0; border-bottom:1px solid #F1F5F9;";
      const isOos = !item.IsAvailable;
      const currentQty = this.orderItems[item.MenuItemID] || 0;

      row.innerHTML = `
        <div>
          <div style="font-weight:700; font-size:14px; color:${isOos ? '#9CA3AF' : 'var(--text-primary)'}">
            ${item.ItemName} ${isOos ? '<span class="bubble-badge badge-red" style="font-size:9px;">OUT OF STOCK</span>' : ''}
          </div>
          <div style="font-size:11px; color:var(--text-muted);">
            ${item.Category} • Rs.${item.Price.toFixed(2)} • Chef: ${item.AssignedChefName}
          </div>
        </div>
        <div style="display:flex; align-items:center; gap:8px;">
          <button class="btn-bubble btn-bubble-secondary btn-bubble-sm" style="width:28px; height:28px; padding:0;" 
                  ${isOos ? 'disabled' : ''} onclick="WaiterModule.adjustItemQty(${item.MenuItemID}, -1)">-</button>
          <span style="font-weight:800; min-width:18px; text-align:center;">${currentQty}</span>
          <button class="btn-bubble btn-bubble-primary btn-bubble-sm" style="width:28px; height:28px; padding:0;" 
                  ${isOos ? 'disabled' : ''} onclick="WaiterModule.adjustItemQty(${item.MenuItemID}, 1)">+</button>
        </div>
      `;
      list.appendChild(row);
    });

    this.updateOrderSummary();
  },

  adjustItemQty(menuItemId, delta) {
    const cur = this.orderItems[menuItemId] || 0;
    const next = Math.max(0, cur + delta);
    if (next === 0) delete this.orderItems[menuItemId];
    else this.orderItems[menuItemId] = next;
    this.renderMenuPicker();
  },

  updateOrderSummary() {
    let total = 0;
    let count = 0;
    for (const [id, qty] of Object.entries(this.orderItems)) {
      const dish = this.menu.find(m => m.MenuItemID === parseInt(id));
      if (dish) {
        total += dish.Price * qty;
        count += qty;
      }
    }

    const summaryEl = document.getElementById("orderBuilderTotal");
    if (summaryEl) {
      summaryEl.textContent = `Total: Rs.${total.toFixed(2)} (${count} items)`;
    }
  },

  async submitNewOrder() {
    const custInput = document.getElementById("orderCustomerCountInput");
    const custCount = parseInt(custInput ? custInput.value : 1);

    if (this.selectedTables.length === 0) {
      App.showToast("Please select at least one physical table.", "error");
      return;
    }
    if (!custCount || custCount <= 0) {
      App.showToast("Customer count must be at least 1.", "error");
      return;
    }

    const items = [];
    for (const [id, qty] of Object.entries(this.orderItems)) {
      items.push({ MenuItemID: parseInt(id), Quantity: qty });
    }

    if (items.length === 0) {
      App.showToast("Please add at least one dish to the order.", "error");
      return;
    }

    try {
      const res = await App.apiFetch("/api/waiter/orders", {
        method: "POST",
        body: {
          customer_count: custCount,
          table_numbers: this.selectedTables,
          items: items
        }
      });

      App.showToast(`Order #${res.order_id} created for Table(s) ${res.tables.join(", ")}!`, "success");
      this.selectedTables = [];
      this.orderItems = {};
      if (custInput) custInput.value = 2;
      this.renderTables();
      this.renderMenuPicker();
      await this.fetchOrders();
    } catch (e) {
      App.showToast("Failed to place order: " + e.message, "error");
    }
  },

  renderOrders() {
    const container = document.getElementById("waiterOrdersList");
    if (!container) return;

    if (this.activeOrders.length === 0) {
      container.innerHTML = `
        <div style="text-align:center; padding:30px 10px; color:var(--text-muted);">
          <div style="font-size:32px; margin-bottom:8px;">🍽️</div>
          <div style="font-weight:700;">No active tickets for your shift.</div>
          <div style="font-size:12px;">Create an order above to dispatch tickets to the kitchen.</div>
        </div>
      `;
      return;
    }

    container.innerHTML = "";
    this.activeOrders.forEach(ord => {
      const card = document.createElement("div");
      card.className = "bubble-card waiter-order-card";
      
      let itemsHtml = ord.items.map(it => {
        let statusBadge = "badge-gray";
        if (it.ItemStatus === "Ready") statusBadge = "badge-green";
        else if (it.ItemStatus === "Cooking") statusBadge = "badge-blue";
        else if (it.ItemStatus === "Cancel Requested") statusBadge = "badge-amber";
        else if (it.ItemStatus === "Cancelled") statusBadge = "badge-red";

        const canCancel = (it.ItemStatus === "Pending" || it.ItemStatus === "Cooking");

        return `
          <div style="display:flex; align-items:center; justify-content:space-between; padding:8px 0; border-bottom:1px dashed #F1F5F9; font-size:13px;">
            <div>
              <span style="font-weight:700;">${it.Quantity}x ${it.ItemName}</span>
              <div style="font-size:11px; color:var(--text-muted);">Chef: ${it.ChefName} • Rs.${it.Subtotal.toFixed(2)}</div>
            </div>
            <div style="display:flex; align-items:center; gap:8px;">
              <span class="bubble-badge ${statusBadge}">${it.ItemStatus}</span>
              ${canCancel ? `<button class="btn-bubble btn-bubble-danger btn-bubble-sm" style="padding:3px 8px; font-size:10px;" onclick="WaiterModule.promptCancelRequest(${it.OrderDetailID}, '${it.ItemName}')">Cancel</button>` : ''}
            </div>
          </div>
        `;
      }).join("");

      card.innerHTML = `
        <div class="bubble-card-header" style="margin-bottom:10px; padding-bottom:8px;">
          <div>
            <span style="font-weight:800; font-size:15px; color:var(--text-primary);">Order #${ord.OrderID}</span>
            <span class="bubble-badge badge-green" style="margin-left:6px;">Tables: ${ord.tables.join(", ")}</span>
          </div>
          <div style="font-size:12px; font-weight:700; color:var(--text-secondary);">
            ${ord.CustomerCount} Guests • <span style="color:var(--brand-green-dark);">Rs.${ord.BillTotal.toFixed(2)}</span>
          </div>
        </div>

        <div style="margin-bottom:14px;">
          ${itemsHtml}
        </div>

        <div style="display:flex; gap:8px;">
          <button class="btn-bubble btn-bubble-secondary btn-bubble-sm" style="flex:1;" onclick="WaiterModule.openAddDishModal(${ord.OrderID})">+ Add Dish</button>
          <button class="btn-bubble btn-bubble-primary btn-bubble-sm" style="flex:1;" onclick="WaiterModule.openCheckoutModal(${ord.OrderID}, ${ord.BillTotal})">Checkout Bill</button>
        </div>
      `;
      container.appendChild(card);
    });
  },

  promptCancelRequest(orderDetailId, dishName) {
    const reason = prompt(`Enter reason for customer requesting cancellation of '${dishName}':\n(Will be routed to Chef for preparation consent)`);
    if (!reason || !reason.trim()) return;

    App.apiFetch(`/api/waiter/order-details/${orderDetailId}/cancel-request`, {
      method: "PUT",
      body: { reason: reason.trim() }
    }).then(res => {
      App.showToast(res.message, "info");
      this.fetchOrders();
    }).catch(err => {
      App.showToast("Cancellation request failed: " + err.message, "error");
    });
  },

  openAddDishModal(orderId) {
    const sel = document.getElementById("addDishSelect");
    if (!sel) return;
    sel.innerHTML = "";
    this.menu.filter(m => m.IsAvailable).forEach(m => {
      const opt = document.createElement("option");
      opt.value = m.MenuItemID;
      opt.textContent = `${m.ItemName} (Rs.${m.Price.toFixed(2)})`;
      sel.appendChild(opt);
    });

    document.getElementById("addDishOrderId").value = orderId;
    document.getElementById("addDishModal").classList.add("open");
  },

  async submitAddDish() {
    const orderId = parseInt(document.getElementById("addDishOrderId").value);
    const menuId = parseInt(document.getElementById("addDishSelect").value);
    const qty = parseInt(document.getElementById("addDishQtyInput").value || 1);

    try {
      const res = await App.apiFetch(`/api/waiter/orders/${orderId}/items`, {
        method: "POST",
        body: { menu_item_id: menuId, quantity: qty }
      });
      App.showToast(`Added ${qty}x ${res.item_name} to Order #${orderId}!`, "success");
      document.getElementById("addDishModal").classList.remove("open");
      await this.fetchOrders();
    } catch (e) {
      App.showToast("Failed to add dish: " + e.message, "error");
    }
  },

  openCheckoutModal(orderId, billTotal) {
    this.currentCheckoutOrder = { orderId, billTotal };
    document.getElementById("checkoutOrderIdLabel").textContent = `Order #${orderId}`;
    document.getElementById("checkoutTotalBillLabel").textContent = `Rs.${billTotal.toFixed(2)}`;
    document.getElementById("checkoutCashInput").value = billTotal.toFixed(2);
    document.getElementById("checkoutUpiInput").value = "0.00";
    document.getElementById("checkoutModal").classList.add("open");
  },

  async submitCheckout() {
    if (!this.currentCheckoutOrder) return;
    const cash = parseFloat(document.getElementById("checkoutCashInput").value || 0);
    const upi = parseFloat(document.getElementById("checkoutUpiInput").value || 0);
    const orderId = this.currentCheckoutOrder.orderId;

    try {
      const res = await App.apiFetch(`/api/waiter/orders/${orderId}/checkout`, {
        method: "POST",
        body: { cash_amount: cash, upi_amount: upi }
      });

      App.showToast(res.message, "success");
      document.getElementById("checkoutModal").classList.remove("open");

      // Prompt verified feedback modal
      this.openFeedbackModal(orderId);
      await this.refresh();
    } catch (e) {
      App.showToast("Checkout failed: " + e.message, "error");
    }
  },

  openFeedbackModal(orderId) {
    document.getElementById("feedbackOrderId").value = orderId;
    document.getElementById("feedbackModal").classList.add("open");
  },

  async submitFeedback() {
    const orderId = parseInt(document.getElementById("feedbackOrderId").value);
    const name = document.getElementById("fbCustomerName").value.trim() || null;
    const phone = document.getElementById("fbPhoneNumber").value.trim() || null;
    const serviceRating = parseInt(document.getElementById("fbServiceRating").value) || null;
    const foodRating = parseInt(document.getElementById("fbFoodRating").value) || null;
    const ambienceRating = parseInt(document.getElementById("fbAmbienceRating").value) || null;
    const cleanlinessRating = parseInt(document.getElementById("fbCleanlinessRating").value) || null;
    const reviewText = document.getElementById("fbReviewText").value.trim() || null;

    try {
      const res = await App.apiFetch(`/api/waiter/orders/${orderId}/feedback`, {
        method: "POST",
        body: {
          customer_name: name,
          phone_number: phone,
          service_rating: serviceRating,
          food_rating: foodRating,
          ambience_rating: ambienceRating,
          cleanliness_rating: cleanlinessRating,
          review_text: reviewText
        }
      });
      App.showToast(res.message, "success");
      document.getElementById("feedbackModal").classList.remove("open");
    } catch (e) {
      App.showToast("Feedback submission rejected: " + e.message, "error");
    }
  }
};
