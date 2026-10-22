/**
 * Kitchen Manager Tablet Controller (768px - 1024px Viewport Target)
 * Dual-pane layout splitting Raw Inventory Alerts on the left,
 * and Menu Alteration Approvals & Waste Tracking on the right.
 */

const KitchenMgrModule = {
  inventory: [],
  shortages: [],
  menuRequests: [],
  wasteLogs: [],
  totalWasteLoss: 0,

  async init() {
    await this.refresh();
  },

  async refresh() {
    await Promise.all([
      this.fetchInventory(),
      this.fetchMenuRequests(),
      this.fetchWasteLogs(),
      this.fetchChefRatings()
    ]);
  },

  async fetchInventory() {
    try {
      const data = await App.apiFetch("/api/kitchen/inventory");
      this.inventory = data.inventory || [];
      this.shortages = data.shortages || [];
      this.renderInventory();
    } catch (e) {
      console.error("Error fetching inventory", e);
    }
  },

  async fetchMenuRequests() {
    try {
      const data = await App.apiFetch("/api/kitchen/menu-requests");
      this.menuRequests = data.requests || [];
      this.renderMenuRequests();
    } catch (e) {
      console.error("Error fetching menu requests", e);
    }
  },

  async fetchWasteLogs() {
    try {
      const data = await App.apiFetch("/api/kitchen/waste-log");
      this.wasteLogs = data.waste_logs || [];
      this.totalWasteLoss = data.total_waste_loss || 0;
      this.renderWasteLogs();
    } catch (e) {
      console.error("Error fetching waste logs", e);
    }
  },

  async fetchChefRatings() {
    try {
      const data = await App.apiFetch("/api/kitchen/chef-ratings");
      this.renderChefRatings(data.chef_ratings || []);
    } catch (e) {
      console.error("Error fetching chef ratings", e);
    }
  },

  renderInventory() {
    const list = document.getElementById("kmInventoryList");
    const countBadge = document.getElementById("kmShortageCountBadge");
    if (!list) return;

    if (countBadge) {
      countBadge.textContent = `${this.shortages.length} Shortages Alerted`;
    }

    list.innerHTML = "";
    this.inventory.forEach(item => {
      const isShortage = Boolean(item.NeedsRestock);
      const row = document.createElement("div");
      row.style.cssText = "display:flex; align-items:center; justify-content:space-between; padding:12px; margin-bottom:8px; border-radius:16px; background:" + (isShortage ? "#FEF2F2" : "#FFFFFF") + "; border:1px solid " + (isShortage ? "#FECACA" : "#E2E8F0") + ";";

      const chefBadge = item.AssignedChefName 
        ? `<span class="bubble-badge badge-blue" style="margin-left:6px; font-size:10px;">👨‍🍳 ${item.AssignedChefName}</span>`
        : `<span class="bubble-badge badge-gray" style="margin-left:6px; font-size:10px;">🌐 Shared Kitchen</span>`;

      row.innerHTML = `
        <div style="flex:1; padding-right:12px;">
          <div style="font-weight:700; font-size:14px; color:${isShortage ? '#B91C1C' : 'var(--text-primary)'}; display:flex; align-items:center; flex-wrap:wrap; gap:4px;">
            <span>${item.IngredientName}</span>
            ${isShortage ? '<span class="bubble-badge badge-red" style="font-size:10px;">SHORTAGE ACTIVE</span>' : ''}
            ${chefBadge}
          </div>
          <div style="font-size:11px; color:var(--text-muted); margin-top:3px;">
            ${item.ReporterChefName ? `Flagged by: ${item.ReporterChefName} • ` : ''}Last Updated: ${item.LastUpdated}
          </div>
        </div>
        <div style="display:flex; align-items:center; gap:8px;">
          ${isShortage ? `
            <button class="btn-bubble btn-bubble-primary btn-bubble-sm" onclick="KitchenMgrModule.resolveRestock(${item.IngredientID})">
              ✓ Restock Resolved
            </button>
          ` : `
            <span class="bubble-badge badge-green" style="font-size:11px;">In Stock</span>
          `}
          <button class="btn-bubble btn-bubble-danger btn-bubble-sm" style="padding:5px 12px; font-size:11px; font-weight:700;" title="Remove this raw ingredient from inventory" onclick="KitchenMgrModule.removeIngredient(${item.IngredientID}, '${this.escapeStr(item.IngredientName)}')">
            🗑️ Remove
          </button>
        </div>
      `;
      list.appendChild(row);
    });
  },

  async resolveRestock(ingredientId) {
    try {
      await App.apiFetch(`/api/kitchen/inventory/${ingredientId}/restock`, {
        method: "PUT",
        body: { needs_restock: false }
      });
      App.showToast("Shortage resolved! Restock updated in database.", "success");
      await this.fetchInventory();
    } catch (e) {
      App.showToast("Failed to resolve shortage: " + e.message, "error");
    }
  },

  async openAddIngredientModal() {
    const nameInput = document.getElementById("newIngName");
    if (nameInput) nameInput.value = "";
    
    const chefSelect = document.getElementById("newIngChef");
    if (chefSelect) {
      chefSelect.innerHTML = '<option value="">🌐 All Chefs / Shared Kitchen</option>';
      try {
        const data = await App.apiFetch("/api/kitchen/chefs");
        (data.chefs || []).forEach(chef => {
          const opt = document.createElement("option");
          opt.value = chef.EmployeeID;
          opt.textContent = `👨‍🍳 ${chef.Name} (${chef.Shift})`;
          chefSelect.appendChild(opt);
        });
      } catch (e) {
        console.error("Failed to load chefs list", e);
      }
    }
    document.getElementById("addIngredientModal").classList.add("open");
  },

  async submitAddIngredient() {
    const name = document.getElementById("newIngName").value.trim();
    if (!name) {
      App.showToast("Ingredient name is required", "error");
      return;
    }

    const chefVal = document.getElementById("newIngChef").value;
    const assignedChefId = chefVal ? parseInt(chefVal) : null;

    try {
      await App.apiFetch("/api/kitchen/inventory", {
        method: "POST",
        body: { ingredient_name: name, needs_restock: false, assigned_chef_id: assignedChefId }
      });
      App.showToast(`Ingredient '${name}' registered in inventory!`, "success");
      document.getElementById("addIngredientModal").classList.remove("open");
      document.getElementById("newIngName").value = "";
      await this.fetchInventory();
    } catch (e) {
      App.showToast("Failed to add ingredient: " + (e.message || e), "error");
    }
  },

  async removeIngredient(ingredientId, ingredientName) {
    if (!confirm(`Are you sure you want to remove '${ingredientName}' from raw material inventory?\n\nThis will remove it from all chef station lists immediately.`)) {
      return;
    }

    try {
      const res = await App.apiFetch(`/api/kitchen/inventory/${ingredientId}`, {
        method: "DELETE"
      });
      App.showToast(res.message, "info");
      await this.fetchInventory();
    } catch (e) {
      App.showToast("Failed to remove ingredient: " + (e.message || e), "error");
    }
  },

  escapeStr(str) {
    if (!str) return "";
    return str.replace(/'/g, "\\'").replace(/"/g, "&quot;");
  },

  openLogProcurementModal() {
    const today = new Date().toISOString().split("T")[0];
    document.getElementById("procureDate").value = today;
    const descInput = document.getElementById("procureDescription");
    if (descInput) descInput.value = "";
    document.getElementById("logProcurementModal").classList.add("open");
  },

  async submitLogProcurement() {
    const date = document.getElementById("procureDate").value;
    const amount = parseFloat(document.getElementById("procureAmount").value || 0);
    const descInput = document.getElementById("procureDescription");
    const desc = descInput ? descInput.value.trim() : "";

    if (!date || amount <= 0) {
      App.showToast("Valid date and procurement amount are required", "error");
      return;
    }

    try {
      const res = await App.apiFetch("/api/kitchen/expenses", {
        method: "POST",
        body: {
          expense_date: date,
          expense_amount: amount,
          notes: "Raw Material Restock",
          description: desc || null
        }
      });
      App.showToast(res.message, "success");
      document.getElementById("logProcurementModal").classList.remove("open");
      document.getElementById("procureAmount").value = "";
      if (descInput) descInput.value = "";
    } catch (e) {
      App.showToast("Failed to log expense: " + e.message, "error");
    }
  },

  renderMenuRequests() {
    const list = document.getElementById("kmMenuRequestsList");
    if (!list) return;

    if (this.menuRequests.length === 0) {
      list.innerHTML = `<div style="text-align:center; padding:20px; color:var(--text-muted); font-size:12px;">No pending menu alteration requests.</div>`;
      return;
    }

    list.innerHTML = "";
    this.menuRequests.forEach(req => {
      const isPending = req.Status === "Pending";
      const card = document.createElement("div");
      card.className = "bubble-card";
      card.style.cssText = "padding:16px; margin-bottom:12px;";

      let badgeClass = req.Status === "Approved" ? "badge-green" : req.Status === "Rejected" ? "badge-red" : "badge-amber";

      card.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
          <div>
            <span style="font-weight:800; font-size:14px;">${req.DishName}</span>
            <span class="bubble-badge ${req.RequestType === 'Add' ? 'badge-blue' : 'badge-amber'}" style="margin-left:6px;">${req.RequestType}</span>
          </div>
          <span class="bubble-badge ${badgeClass}">${req.Status}</span>
        </div>
        <div style="font-size:12px; color:var(--text-secondary); margin-bottom:8px;">
          "${req.Reason}"
        </div>
        <div style="font-size:11px; color:var(--text-muted); display:flex; justify-content:space-between; align-items:center;">
          <span>Chef: ${req.ChefName}</span>
          <span>${req.CreatedAt}</span>
        </div>
        ${isPending ? `
          <div style="display:flex; gap:8px; margin-top:10px;">
            <button class="btn-bubble btn-bubble-primary btn-bubble-sm" style="flex:1;" onclick="KitchenMgrModule.actionMenuRequest(${req.RequestID}, 'Approved')">
              ${req.RequestType === 'Remove' ? '✓ Approve Removal' : '✓ Approve & Add to Menu'}
            </button>
            <button class="btn-bubble btn-bubble-danger btn-bubble-sm" style="flex:1;" onclick="KitchenMgrModule.actionMenuRequest(${req.RequestID}, 'Rejected')">
              ✕ Reject
            </button>
          </div>
        ` : ''}
      `;
      list.appendChild(card);
    });
  },

  async actionMenuRequest(requestId, action) {
    const req = this.menuRequests.find(r => r.RequestID == requestId);
    let category = "Main Course";
    let price = 180.00;

    if (action === "Approved") {
      if (req && req.RequestType === "Remove") {
        const confirmed = confirm(`Are you sure you want to approve removing '${req.DishName}' from the active menu?`);
        if (!confirmed) return;
      } else {
        const dishLabel = req ? req.DishName : 'new dish';
        const priceStr = prompt(`Enter menu price (Rs.) for approved dish '${dishLabel}':`, "180.00");
        if (priceStr === null) return;
        price = parseFloat(priceStr) || 180.00;

        const catStr = prompt(`Enter category for '${dishLabel}':`, "Main Course");
        if (catStr) category = catStr;
      }
    }

    try {
      const res = await App.apiFetch(`/api/kitchen/menu-requests/${requestId}/action`, {
        method: "POST",
        body: { action: action, category: category, price: price }
      });
      App.showToast(res.message, "success");
      await this.fetchMenuRequests();
    } catch (e) {
      App.showToast("Action failed: " + (e.message || e), "error");
    }
  },

  renderWasteLogs() {
    const list = document.getElementById("kmWasteLogsList");
    const totalLabel = document.getElementById("kmTotalWasteLossLabel");
    if (!list) return;

    if (totalLabel) {
      totalLabel.textContent = `Total Financial Loss: Rs.${this.totalWasteLoss.toFixed(2)}`;
    }

    if (this.wasteLogs.length === 0) {
      list.innerHTML = `<div style="text-align:center; padding:20px; color:var(--text-muted); font-size:12px;">No food discards logged. Kitchen waste is optimal!</div>`;
      return;
    }

    list.innerHTML = "";
    this.wasteLogs.forEach(w => {
      const row = document.createElement("div");
      row.style.cssText = "display:flex; align-items:center; justify-content:space-between; padding:10px 0; border-bottom:1px solid #F1F5F9; font-size:13px;";

      row.innerHTML = `
        <div>
          <span style="font-weight:700;">${w.ItemName || 'Discarded Dish'}</span>
          <div style="font-size:11px; color:var(--text-muted);">
            Reason: "${w.CancellationReason || 'Customer Allergy'}" • Chef: ${w.ChefName || 'Station'}
          </div>
        </div>
        <div style="text-align:right;">
          <span style="font-weight:800; color:#B91C1C;">-Rs.${w.IngredientCost.toFixed(2)}</span>
          <div style="font-size:10px; color:var(--text-muted);">${w.LogTimestamp}</div>
        </div>
      `;
      list.appendChild(row);
    });
  },

  renderChefRatings(ratings) {
    const container = document.getElementById("kmChefRatingsContainer");
    if (!container) return;

    if (ratings.length === 0) {
      container.innerHTML = `<div style="font-size:12px; color:var(--text-muted);">No ratings recorded yet.</div>`;
      return;
    }

    container.innerHTML = ratings.map(c => `
      <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #F1F5F9; font-size:13px;">
        <span style="font-weight:700;">${c.ChefName}</span>
        <span>
          ⭐ ${c.AvgFoodRating ? c.AvgFoodRating.toFixed(1) : 'N/A'} / 5.0 
          <span style="color:var(--brand-green-dark); font-weight:700; margin-left:6px;">(${c.CulinaryPerformancePoints || 0} pts)</span>
        </span>
      </div>
    `).join("");
  }
};
