/**
 * Chef Kitchen Display System (KDS) Controller (768px - 1024px+ Landscape Monitor)
 * Assigned dish queue filtering (AssignedChefID), dish cooking lifecycle (Pending -> Cooking -> Ready),
 * Chef Deletion-Consent Flow, Out-of-Stock Atomic Transactions, and Menu Proposals.
 */

const ChefModule = {
  queue: [],
  dishes: [],
  inventory: [],
  allMenuDishes: [],

  async init() {
    await this.refresh();
  },

  async refresh() {
    await Promise.all([
      this.fetchQueue(),
      this.fetchDishes(),
      this.fetchInventory(),
      this.fetchActiveMenuDishes()
    ]);
  },

  async fetchQueue() {
    try {
      const data = await App.apiFetch("/api/chef/queue");
      this.queue = data.queue || [];
      this.renderQueue();
    } catch (e) {
      console.error("Error fetching chef queue", e);
    }
  },

  async fetchDishes() {
    try {
      const data = await App.apiFetch("/api/chef/menu");
      this.dishes = data.dishes || [];
      this.renderDishesMenu();
    } catch (e) {
      console.error("Error fetching chef dishes", e);
    }
  },

  async fetchInventory() {
    try {
      const data = await App.apiFetch("/api/chef/inventory");
      this.inventory = data.inventory || [];
      this.renderInventory();
    } catch (e) {
      console.error("Error fetching chef inventory", e);
    }
  },

  renderQueue() {
    const grid = document.getElementById("kdsTicketGrid");
    const countBadge = document.getElementById("kdsActiveCountBadge");
    if (!grid) return;

    if (countBadge) countBadge.textContent = `${this.queue.length} Dishes`;

    if (this.queue.length === 0) {
      grid.innerHTML = `
        <div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-muted);">
          <div style="font-size:36px; margin-bottom:10px;">👨‍🍳</div>
          <div style="font-size:16px; font-weight:700;">Kitchen station queue is clear!</div>
          <div style="font-size:12px;">New orders placed by waitstaff will arrive here in real-time.</div>
        </div>
      `;
      return;
    }

    grid.innerHTML = "";
    this.queue.forEach(item => {
      const isCancelRequested = item.ItemStatus === "Cancel Requested";
      const ticket = document.createElement("div");
      ticket.className = `kds-ticket ${isCancelRequested ? 'urgent' : ''}`;

      let statusBadge = "badge-gray";
      if (item.ItemStatus === "Cooking") statusBadge = "badge-blue";
      else if (item.ItemStatus === "Ready") statusBadge = "badge-green";
      else if (isCancelRequested) statusBadge = "badge-red";

      let actionButtons = "";
      if (isCancelRequested) {
        actionButtons = `
          <div style="width:100%;">
            <div style="font-size:11px; color:#B91C1C; font-weight:700; margin-bottom:6px;">
              ⚠️ Cancel Requested: "${item.CancellationReason || 'Customer request'}"
            </div>
            <div style="display:flex; gap:6px;">
              <button class="btn-bubble btn-bubble-danger btn-bubble-sm" style="flex:1;" onclick="ChefModule.respondConsent(${item.OrderDetailID}, true)">
                ✓ Approve (Discard)
              </button>
              <button class="btn-bubble btn-bubble-secondary btn-bubble-sm" style="flex:1;" onclick="ChefModule.respondConsent(${item.OrderDetailID}, false)">
                ✕ Deny (Keep on Bill)
              </button>
            </div>
          </div>
        `;
      } else if (item.ItemStatus === "Pending") {
        actionButtons = `
          <div style="width:100%;">
            <button class="btn-bubble btn-bubble-primary btn-bubble-sm" style="width:100%;" onclick="ChefModule.updateDishStatus(${item.OrderDetailID}, 'Cooking')">
              🔥 Start Cooking
            </button>
          </div>
        `;
      } else if (item.ItemStatus === "Cooking") {
        actionButtons = `
          <div style="width:100%;">
            <button class="btn-bubble btn-bubble-primary btn-bubble-sm" style="width:100%; background:linear-gradient(135deg, #059669, #047857);" onclick="ChefModule.updateDishStatus(${item.OrderDetailID}, 'Ready')">
              ✓ Mark as Ready
            </button>
          </div>
        `;
      } else if (item.ItemStatus === "Ready") {
        actionButtons = `
          <div style="width:100%; text-align:center;">
            <span style="font-size:12px; font-weight:700; color:var(--brand-green-dark);">
              ✓ Plated & Ready
            </span>
          </div>
        `;
      } else {
        actionButtons = "";
      }

      ticket.innerHTML = `
        <div class="kds-ticket-head">
          <div>
            <span style="font-weight:800; font-size:14px;">Order #${item.OrderID}</span>
            <span class="bubble-badge badge-green" style="margin-left:4px;">Table ${item.tables.join(", ")}</span>
          </div>
          <span class="bubble-badge ${statusBadge}">${item.ItemStatus}</span>
        </div>
        <div class="kds-ticket-body">
          <div style="display:flex; justify-content:space-between; align-items:baseline;">
            <div class="kds-dish-title">${item.ItemName}</div>
            <div class="kds-dish-qty">${item.Quantity}x</div>
          </div>
          <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">
            Category: ${item.Category} • Waiter: ${item.WaiterName}
          </div>
        </div>
        <div class="kds-ticket-foot">
          ${actionButtons}
        </div>
      `;
      grid.appendChild(ticket);
    });
  },

  escapeStr(str) {
    if (!str) return "";
    return str.replace(/'/g, "\\'").replace(/"/g, "&quot;");
  },

  async updateDishStatus(detailId, newStatus) {
    try {
      const res = await App.apiFetch(`/api/chef/order-details/${detailId}/status`, {
        method: "PUT",
        body: { new_status: newStatus }
      });
      App.showToast(`Updated '${res.item_name}' to ${newStatus}`, "info");
      await this.fetchQueue();
    } catch (e) {
      App.showToast("Failed to update status: " + e.message, "error");
    }
  },

  async respondConsent(detailId, approved) {
    try {
      const res = await App.apiFetch(`/api/chef/order-details/${detailId}/consent`, {
        method: "POST",
        body: { approved: approved }
      });
      App.showToast(res.message, approved ? "info" : "success");
      await this.fetchQueue();
    } catch (e) {
      App.showToast("Consent response failed: " + e.message, "error");
    }
  },

  renderDishesMenu() {
    const list = document.getElementById("chefDishStockList");
    if (!list) return;

    list.innerHTML = "";
    this.dishes.forEach(dish => {
      const row = document.createElement("div");
      row.style.cssText = "display:flex; align-items:center; justify-content:space-between; padding:10px 0; border-bottom:1px solid #F1F5F9; font-size:13px; gap:12px; flex-wrap:wrap;";
      const stock = typeof dish.StockQuantity === "number" ? dish.StockQuantity : (dish.IsAvailable ? 10 : 0);
      const isAvail = stock > 0 && Boolean(dish.IsAvailable);

      row.innerHTML = `
        <div style="min-width:180px; flex:1;">
          <div style="display:flex; align-items:center; gap:6px;">
            <span style="font-weight:700; font-size:14px;">${dish.ItemName}</span>
            <span class="bubble-badge ${isAvail ? 'badge-green' : 'badge-red'}" style="font-size:10px; font-weight:800;">
              ${isAvail ? `🟢 ${stock} IN STOCK` : '🔴 OUT OF STOCK (0)'}
            </span>
          </div>
          <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">
            Rs.${dish.Price.toFixed(2)} • ${dish.Category}
          </div>
        </div>

        <div style="display:flex; align-items:center; gap:6px;">
          <span style="font-size:11px; color:var(--text-muted); font-weight:600;">Portions:</span>
          <input type="number" id="dishStockInput_${dish.MenuItemID}" min="0" max="999" value="${stock}" 
                 style="width:58px; text-align:center; padding:4px 6px; font-weight:700; font-size:13px; border:1.5px solid #CBD5E1; border-radius:6px; background:#F8FAFC;"
                 title="Enter portions prepared in advance">
          <button class="btn-bubble btn-bubble-primary btn-bubble-sm" style="padding:4px 9px; font-size:11px; font-weight:700;"
                  onclick="ChefModule.saveDishStock(${dish.MenuItemID}, '${ChefModule.escapeStr(dish.ItemName)}')">
            Save
          </button>
          <button class="btn-bubble btn-bubble-secondary btn-bubble-sm" style="padding:4px 7px; font-size:10px; font-weight:700;"
                  title="Quickly add 5 portions prepared fresh"
                  onclick="ChefModule.quickAddStock(${dish.MenuItemID}, 5, '${ChefModule.escapeStr(dish.ItemName)}')">
            +5
          </button>
          <button class="btn-bubble btn-bubble-secondary btn-bubble-sm" style="padding:4px 7px; font-size:10px; font-weight:700;"
                  title="Quickly add 10 portions prepared fresh"
                  onclick="ChefModule.quickAddStock(${dish.MenuItemID}, 10, '${ChefModule.escapeStr(dish.ItemName)}')">
            +10
          </button>
          ${isAvail ? `
            <button class="btn-bubble btn-bubble-danger btn-bubble-sm" style="padding:4px 8px; font-size:10px;"
                    title="Log shortage cause and set to 0"
                    onclick="ChefModule.promptOutOfStock(${dish.MenuItemID}, '${ChefModule.escapeStr(dish.ItemName)}')">
              Shortage (0)
            </button>
          ` : ''}
        </div>
      `;
      list.appendChild(row);
    });
  },

  async saveDishStock(itemId, itemName) {
    const input = document.getElementById(`dishStockInput_${itemId}`);
    if (!input) return;
    const qty = parseInt(input.value);
    if (isNaN(qty) || qty < 0) {
      App.showToast("Stock quantity must be a non-negative number.", "error");
      return;
    }

    try {
      const res = await App.apiFetch(`/api/chef/menu/${itemId}/stock`, {
        method: "PUT",
        body: { stock_quantity: qty }
      });
      App.showToast(res.message || `Stock for '${itemName}' updated to ${qty} portion(s)!`, "success");
      await this.fetchDishes();
    } catch (e) {
      App.showToast("Failed to update stock: " + e.message, "error");
    }
  },

  async quickAddStock(itemId, delta, itemName) {
    const input = document.getElementById(`dishStockInput_${itemId}`);
    const currentQty = input ? parseInt(input.value) || 0 : 0;
    const newQty = Math.max(0, currentQty + delta);

    try {
      const res = await App.apiFetch(`/api/chef/menu/${itemId}/stock`, {
        method: "PUT",
        body: { stock_quantity: newQty }
      });
      App.showToast(`Prepared +${delta} portions of '${itemName}'. Total available: ${newQty}.`, "success");
      await this.fetchDishes();
    } catch (e) {
      App.showToast("Failed to update stock: " + e.message, "error");
    }
  },

  promptOutOfStock(itemId, itemName) {
    const reason = prompt(`Enter shortage cause for '${itemName}':\n(Executes ACID transaction writing to Shortage_Logs and sets stock to 0)`);
    if (!reason || !reason.trim()) return;

    App.apiFetch(`/api/chef/menu/${itemId}/out-of-stock`, {
      method: "POST",
      body: { reason: reason.trim() }
    }).then(res => {
      App.showToast(`Shortage transaction logged for '${res.item_name}' (Stock set to 0)!`, "info");
      this.fetchDishes();
    }).catch(err => {
      App.showToast("Failed to toggle stock: " + err.message, "error");
    });
  },

  async restoreStock(itemId) {
    try {
      await App.apiFetch(`/api/chef/menu/${itemId}/restore-stock`, { method: "POST" });
      App.showToast("Dish stock restored to 10 portions!", "success");
      await this.fetchDishes();
    } catch (e) {
      App.showToast("Restore failed: " + e.message, "error");
    }
  },

  renderInventory() {
    const list = document.getElementById("chefInventoryFlagsList");
    if (!list) return;

    list.innerHTML = "";
    if (this.inventory.length === 0) {
      list.innerHTML = `
        <div style="text-align:center; padding:24px 10px; color:var(--text-muted); font-size:12px;">
          No raw ingredients assigned to your culinary station.
        </div>
      `;
      return;
    }

    this.inventory.forEach(item => {
      const row = document.createElement("div");
      row.style.cssText = "display:flex; align-items:center; justify-content:space-between; padding:8px 0; border-bottom:1px solid #F1F5F9; font-size:13px;";
      const needsRestock = Boolean(item.NeedsRestock);

      row.innerHTML = `
        <div>
          <span style="font-weight:600;">${item.IngredientName}</span>
          ${needsRestock ? '<span class="bubble-badge badge-amber" style="margin-left:6px; font-size:9px;">NEEDS RESTOCK</span>' : ''}
          <div style="font-size:10px; color:var(--text-muted);">
            ${item.AssignedChefName ? `Station: ${item.AssignedChefName}` : '🌐 Shared Kitchen'}
          </div>
        </div>
        <button class="btn-bubble ${needsRestock ? 'btn-bubble-secondary' : 'btn-bubble-danger'} btn-bubble-sm" style="font-size:11px;"
                onclick="ChefModule.toggleRestockFlag(${item.IngredientID}, ${!needsRestock})">
          ${needsRestock ? 'Unflag Shortage' : 'Report Shortage'}
        </button>
      `;
      list.appendChild(row);
    });
  },

  async toggleRestockFlag(ingredientId, flag) {
    try {
      await App.apiFetch(`/api/chef/inventory/${ingredientId}/restock-flag`, {
        method: "PUT",
        body: { needs_restock: flag }
      });
      App.showToast("Inventory alert updated", "info");
      await this.fetchInventory();
    } catch (e) {
      App.showToast("Failed to update inventory flag: " + e.message, "error");
    }
  },

  async fetchActiveMenuDishes() {
    try {
      const data = await App.apiFetch("/api/chef/active-menu-dishes");
      this.allMenuDishes = data.dishes || [];
      this.populateMenuProposalDishes();
    } catch (e) {
      console.error("Error fetching active menu dishes", e);
    }
  },

  populateMenuProposalDishes() {
    const sel = document.getElementById("propDishSelect");
    if (!sel) return;
    const currentVal = sel.value;
    sel.innerHTML = '<option value="">-- Choose a dish from menu --</option>';

    // Group dishes by category
    const categories = {};
    (this.allMenuDishes || []).forEach(dish => {
      const cat = dish.Category || "Other";
      if (!categories[cat]) categories[cat] = [];
      categories[cat].push(dish);
    });

    Object.keys(categories).sort().forEach(cat => {
      const optGroup = document.createElement("optgroup");
      optGroup.label = cat;
      categories[cat].forEach(dish => {
        const opt = document.createElement("option");
        opt.value = dish.ItemName;
        const priceNum = Number(dish.Price || 0).toFixed(2);
        opt.textContent = `${dish.ItemName} (Rs.${priceNum}${dish.IsAvailable ? '' : ' - Out of Stock'})`;
        optGroup.appendChild(opt);
      });
      sel.appendChild(optGroup);
    });

    if (currentVal) {
      sel.value = currentVal;
    }
  },

  onProposalTypeChange() {
    const reqType = document.getElementById("propRequestType").value;
    const nameGroup = document.getElementById("propDishNameGroup");
    const selectGroup = document.getElementById("propDishSelectGroup");
    const reasonInput = document.getElementById("propReason");

    if (reqType === "Remove") {
      nameGroup.style.display = "none";
      selectGroup.style.display = "block";
      this.populateMenuProposalDishes();
      if (!reasonInput.value) {
        reasonInput.placeholder = "e.g. Low sales velocity, ingredients phased out, discontinued...";
      }
    } else {
      nameGroup.style.display = "block";
      selectGroup.style.display = "none";
      if (!reasonInput.value) {
        reasonInput.placeholder = "e.g. High customer demand, seasonal special, ingredient availability...";
      }
    }
  },

  async openMenuProposalModal() {
    const dishInput = document.getElementById("propDishName");
    if (dishInput) {
      dishInput.value = "";
      dishInput.setAttribute("autocomplete", "off");
      dishInput.name = "new_dish_name";
    }
    document.getElementById("propRequestType").value = "Add";
    document.getElementById("propDishSelect").value = "";
    document.getElementById("propReason").value = "";
    this.onProposalTypeChange();
    await this.fetchActiveMenuDishes();
    document.getElementById("menuProposalModal").classList.add("open");
  },

  async submitMenuProposal() {
    const reqType = document.getElementById("propRequestType").value;
    let dishName = "";

    if (reqType === "Remove") {
      dishName = document.getElementById("propDishSelect").value.trim();
      if (!dishName) {
        App.showToast("Please choose a dish from the menu to remove", "error");
        return;
      }
    } else {
      dishName = document.getElementById("propDishName").value.trim();
      if (!dishName) {
        App.showToast("Please enter a new dish name", "error");
        return;
      }
    }

    let reason = document.getElementById("propReason").value.trim();
    if (!reason) {
      reason = reqType === "Remove" ? "Discontinued from menu" : "Seasonal menu addition";
    }

    try {
      const res = await App.apiFetch("/api/chef/menu-requests", {
        method: "POST",
        body: { dish_name: dishName, request_type: reqType, reason: reason }
      });
      App.showToast(res.message, "success");
      document.getElementById("menuProposalModal").classList.remove("open");
      const dishInput = document.getElementById("propDishName");
      if (dishInput) {
        dishInput.value = "";
      }
      document.getElementById("propDishSelect").value = "";
      document.getElementById("propReason").value = "";
      await this.fetchActiveMenuDishes();
      await this.fetchDishes();
    } catch (e) {
      App.showToast("Proposal submission failed: " + (e.message || e), "error");
    }
  }
};
