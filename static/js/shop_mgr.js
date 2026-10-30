/**
 * Shop Manager Desktop Controller (1280px+ Wide Desktop Viewport Target)
 * Executive KPI cards, the 4 Automated SQL Business Intelligence Views,
 * Personnel directory with salary adjustments, and the Single-Seat Handover Protocol.
 */

const ShopMgrModule = {
  kpi: {},
  waiterLeaderboard: [],
  chefLeaderboard: [],
  dailyCollections: [],
  monthlyProfitLoss: [],
  staffList: [],

  async init() {
    await this.refresh();
  },

  async refresh() {
    await Promise.all([
      this.fetchOverview(),
      this.fetchWaiterLeaderboard(),
      this.fetchChefLeaderboard(),
      this.fetchDailyCollections(),
      this.fetchMonthlyProfitLoss(),
      this.fetchStaff(),
      this.fetchExpenses(),
      this.fetchFeedbacks()
    ]);
  },

  async fetchOverview() {
    try {
      const data = await App.apiFetch("/api/manager/overview");
      this.kpi = data.kpi || {};
      this.renderKPIs();
    } catch (e) {
      console.error("Error fetching overview", e);
    }
  },

  async fetchWaiterLeaderboard() {
    try {
      const data = await App.apiFetch("/api/manager/views/waiter-performance");
      this.waiterLeaderboard = data.view_data || [];
      this.renderWaiterLeaderboard();
    } catch (e) {
      console.error("Error fetching waiter view", e);
    }
  },

  async fetchChefLeaderboard() {
    try {
      const data = await App.apiFetch("/api/manager/views/chef-performance");
      this.chefLeaderboard = data.view_data || [];
      this.renderChefLeaderboard();
    } catch (e) {
      console.error("Error fetching chef view", e);
    }
  },

  async fetchDailyCollections() {
    try {
      const data = await App.apiFetch("/api/manager/views/daily-collections");
      this.dailyCollections = data.view_data || [];
      this.renderDailyCollections();
    } catch (e) {
      console.error("Error fetching collections view", e);
    }
  },

  async fetchMonthlyProfitLoss() {
    try {
      const data = await App.apiFetch("/api/manager/views/monthly-profit-loss");
      this.monthlyProfitLoss = data.view_data || [];
      this.renderMonthlyProfitLoss();
    } catch (e) {
      console.error("Error fetching P&L view", e);
    }
  },

  async fetchStaff() {
    try {
      const data = await App.apiFetch("/api/manager/staff");
      this.staffList = data.staff || [];
      this.renderStaffList();
    } catch (e) {
      console.error("Error fetching staff", e);
    }
  },

  async fetchExpenses() {
    try {
      const data = await App.apiFetch("/api/manager/expenses");
      this.renderExpenses(data.expenses || []);
    } catch (e) {
      console.error("Error fetching expenses", e);
    }
  },

  async fetchFeedbacks() {
    try {
      const data = await App.apiFetch("/api/manager/feedbacks");
      this.renderFeedbacks(data.feedbacks || []);
    } catch (e) {
      console.error("Error fetching feedbacks", e);
    }
  },

  renderKPIs() {
    const k = this.kpi;
    const revEl = document.getElementById("kpiTotalRevenue");
    const expEl = document.getElementById("kpiTotalExpenses");
    const netEl = document.getElementById("kpiNetProfit");
    const occEl = document.getElementById("kpiTableOccupancy");

    if (revEl) revEl.textContent = `Rs.${(k.total_revenue || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
    if (expEl) expEl.textContent = `Rs.${(k.total_expenses || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
    if (netEl) {
      const net = k.net_profit_loss || 0;
      netEl.textContent = `Rs.${net.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
      netEl.style.color = net >= 0 ? "var(--brand-green-dark)" : "#B91C1C";
    }
    if (occEl) {
      const tot = k.total_tables || 1;
      const occ = k.occupied_tables || 0;
      occEl.textContent = `${occ} / ${tot} (${Math.round((occ/tot)*100)}%)`;
    }
  },

  renderWaiterLeaderboard() {
    const tableBody = document.querySelector("#viewWaiterPerformanceTable tbody");
    if (!tableBody) return;

    if (this.waiterLeaderboard.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">No waiter orders yet.</td></tr>`;
      return;
    }

    tableBody.innerHTML = this.waiterLeaderboard.map((w, idx) => `
      <tr>
        <td><strong>#${idx + 1}</strong></td>
        <td><strong>${w.WaiterName}</strong></td>
        <td>${w.TotalCustomersHandled}</td>
        <td>⭐ ${w.AvgServiceRating ? w.AvgServiceRating.toFixed(2) : 'N/A'}</td>
        <td><strong style="color:var(--brand-green-dark);">${w.TotalPerformancePoints} pts</strong></td>
      </tr>
    `).join("");
  },

  renderChefLeaderboard() {
    const tableBody = document.querySelector("#viewChefPerformanceTable tbody");
    if (!tableBody) return;

    if (this.chefLeaderboard.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">No completed chef dishes yet.</td></tr>`;
      return;
    }

    tableBody.innerHTML = this.chefLeaderboard.map((c, idx) => {
      return `
        <tr>
          <td><strong>#${idx + 1}</strong></td>
          <td><strong>${c.ChefName}</strong></td>
          <td>${c.TotalDishesPrepared}</td>
          <td>⭐ ${c.AvgFoodRating ? c.AvgFoodRating.toFixed(2) : 'N/A'}</td>
          <td><strong style="color:var(--brand-green-dark);">${c.CulinaryPerformancePoints} pts</strong></td>
        </tr>
      `;
    }).join("");
  },

  renderDailyCollections() {
    const tableBody = document.querySelector("#viewDailyCollectionsTable tbody");
    if (!tableBody) return;

    if (this.dailyCollections.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--text-muted);">No shifts finalized.</td></tr>`;
      return;
    }

    tableBody.innerHTML = this.dailyCollections.map(row => `
      <tr>
        <td>${row.CollectionDate}</td>
        <td><strong>${row.WaiterName}</strong></td>
        <td>Rs.${row.TotalCashCollected.toFixed(2)}</td>
        <td>Rs.${row.TotalUPICollected.toFixed(2)}</td>
        <td><strong>Rs.${row.TotalShiftCollection.toFixed(2)}</strong></td>
      </tr>
    `).join("");
  },

  renderMonthlyProfitLoss() {
    const tableBody = document.querySelector("#viewMonthlyProfitLossTable tbody");
    if (!tableBody) return;

    if (this.monthlyProfitLoss.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">No monthly periods aggregated.</td></tr>`;
      return;
    }

    tableBody.innerHTML = this.monthlyProfitLoss.map(m => {
      const net = m.NetProfitLoss || 0;
      const pct = m.ProfitPercentage !== null ? m.ProfitPercentage : 0;
      return `
        <tr>
          <td><strong>${m.ReportingMonth}</strong></td>
          <td>Rs.${m.TotalIncomingRevenue.toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>
          <td>Rs.${m.TotalOutgoingExpenses.toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>
          <td style="color:${net >= 0 ? 'var(--brand-green-dark)' : '#B91C1C'}; font-weight:700;">
            Rs.${net.toLocaleString('en-IN', {minimumFractionDigits: 2})}
          </td>
          <td><span class="bubble-badge ${net >= 0 ? 'badge-green' : 'badge-red'}">${pct > 0 ? '+' : ''}${pct.toFixed(2)}%</span></td>
        </tr>
      `;
    }).join("");
  },

  renderStaffList() {
    const tableBody = document.querySelector("#staffManagementTable tbody");
    if (!tableBody) return;

    tableBody.innerHTML = this.staffList.map(emp => `
      <tr style="opacity:${emp.IsActive ? 1 : 0.6};">
        <td><strong>${emp.Name}</strong></td>
        <td><span class="bubble-badge badge-blue">${emp.Role}</span></td>
        <td><strong style="color:var(--brand-green-dark);">${emp.Username || '—'}</strong></td>
        <td>${emp.Shift || 'Standard'}</td>
        <td>
          <span class="bubble-badge ${emp.IsActive ? 'badge-green' : 'badge-gray'}">
            ${emp.IsActive ? 'Active' : 'Retired'}
          </span>
        </td>
        <td><strong>Rs.${emp.Salary.toLocaleString('en-IN', {minimumFractionDigits: 2})}</strong></td>
        <td>
          ${emp.IsActive ? `
            <div style="display:flex; gap:6px;">
              <button class="btn-bubble btn-bubble-secondary btn-bubble-sm" onclick="ShopMgrModule.promptAdjustSalary(${emp.EmployeeID}, '${emp.Name}', ${emp.Salary})">
                Adjust Salary
              </button>
              ${emp.UserID ? `
                <button class="btn-bubble btn-bubble-primary btn-bubble-sm" onclick="App.openUpdateCredentialsModal(${emp.UserID}, '${emp.Name}', '${emp.Username}')">
                  ✏️ Edit Login
                </button>
              ` : ''}
              ${emp.EmployeeID !== App.currentUser?.employee_id ? `
                <button class="btn-bubble btn-bubble-danger btn-bubble-sm" onclick="ShopMgrModule.promptDeleteStaff(${emp.EmployeeID}, '${emp.Name.replace(/'/g, "\\'")}', '${emp.Role}')" title="Remove employee and revoke login credentials">
                  🗑️ Remove
                </button>
              ` : ''}
            </div>
          ` : '<span style="font-size:11px; color:var(--text-muted);">Audited Record (Retired)</span>'}
        </td>
      </tr>
    `).join("");
  },

  async promptDeleteStaff(employeeId, name, role) {
    if (!confirm(`Are you sure you want to remove ${role} "${name}"?\n\nThis will revoke their login credentials and deactivate them from active duty.`)) {
      return;
    }

    try {
      const res = await App.apiFetch(`/api/manager/staff/${employeeId}`, {
        method: "DELETE"
      });
      App.showToast(res.message, "success");
      await this.fetchStaff();
    } catch (e) {
      App.showToast("Failed to remove staff: " + e.message, "error");
    }
  },

  promptAdjustSalary(employeeId, name, currentSalary) {
    const newVal = prompt(`Enter new salary (Rs.) for ${name}:`, currentSalary);
    if (newVal === null) return;
    const salary = parseFloat(newVal);
    if (isNaN(salary) || salary < 0) {
      App.showToast("Invalid salary value", "error");
      return;
    }

    App.apiFetch(`/api/manager/staff/${employeeId}/salary`, {
      method: "PUT",
      body: { new_salary: salary }
    }).then(res => {
      App.showToast(res.message, "success");
      this.fetchStaff();
    }).catch(err => {
      App.showToast("Salary update failed: " + err.message, "error");
    });
  },

  renderExpenses(expenses) {
    const container = document.getElementById("mgrExpensesList");
    if (!container) return;

    if (expenses.length === 0) {
      container.innerHTML = `<div style="text-align:center; padding:15px; color:var(--text-muted); font-size:12px;">No expenses logged.</div>`;
      return;
    }

    container.innerHTML = expenses.map(e => {
      const isWastelog = (e.Description && e.Description.toLowerCase() === 'wastelog');
      return `
      <div style="display:flex; justify-content:space-between; align-items:flex-start; padding:10px 0; border-bottom:1px solid #F1F5F9; font-size:12px;">
        <div style="flex:1; padding-right:12px;">
          <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-weight:700;">${e.ExpenseType}</span>
            <span class="bubble-badge badge-gray" style="font-size:10px; padding:2px 8px;">${e.ExpenseDate}</span>
            ${isWastelog ? '<span class="bubble-badge badge-red" style="font-size:9px; padding:1px 6px;">WASTE LOG</span>' : ''}
          </div>
          ${e.Description ? `
            <div style="font-size:11px; color:var(--text-secondary); margin-top:3px; line-height:1.4;">
              ${isWastelog ? '🗑️' : '📝'} ${e.Description}
            </div>
          ` : ''}
        </div>
        <strong style="color:#B91C1C; white-space:nowrap; font-size:13px;">-Rs.${e.ExpenseAmount.toLocaleString('en-IN', {minimumFractionDigits: 2})}</strong>
      </div>
    `;
    }).join("");
  },

  renderFeedbacks(feedbacks) {
    const container = document.getElementById("mgrFeedbacksList");
    if (!container) return;

    if (feedbacks.length === 0) {
      container.innerHTML = `<div style="text-align:center; padding:15px; color:var(--text-muted); font-size:12px;">No customer feedbacks.</div>`;
      return;
    }

    container.innerHTML = feedbacks.map(f => `
      <div class="bubble-card" style="padding:14px; margin-bottom:10px;">
        <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
          <span style="font-weight:700; font-size:13px;">${f.CustomerName} (${f.PhoneNumber})</span>
          <span>⭐ ${f.ServiceRating}/5</span>
        </div>
        <div style="font-size:12px; color:var(--text-secondary); margin-bottom:4px;">
          "${f.ReviewText || 'No review description'}"
        </div>
        <div style="font-size:10px; color:var(--text-muted);">
          Attended by Waiter: ${f.WaiterName} • Order #${f.OrderID}
        </div>
      </div>
    `).join("");
  },

  openHandoverModal() {
    document.getElementById("handoverModal").classList.add("open");
  },

  async submitHandover() {
    const role = document.getElementById("handoverRoleSelect").value;
    const name = document.getElementById("handoverNewName").value.trim();
    const username = document.getElementById("handoverNewUsername").value.trim();
    const password = document.getElementById("handoverNewPassword").value;
    const salary = parseFloat(document.getElementById("handoverSalary").value || 50000);

    if (!name || !username || !password) {
      App.showToast("All fields are mandatory for administrative handover", "error");
      return;
    }

    try {
      const res = await App.apiFetch("/api/auth/handover", {
        method: "POST",
        body: {
          admin_role_name: role,
          new_employee_name: name,
          new_username: username,
          new_password: password,
          salary: salary
        }
      });

      App.showToast(res.message, "success");
      document.getElementById("handoverModal").classList.remove("open");
      await this.fetchStaff();
      if (App.loadDemoProfiles) await App.loadDemoProfiles();
    } catch (e) {
      App.showToast("Handover Protocol failed: " + e.message, "error");
    }
  },

  openLogExpenseModal() {
    const today = new Date().toISOString().split("T")[0];
    document.getElementById("logExpDate").value = today;
    const descInput = document.getElementById("logExpDescription");
    if (descInput) descInput.value = "";
    document.getElementById("logExpenseModal").classList.add("open");
  },

  async submitLogExpense() {
    const date = document.getElementById("logExpDate").value;
    const amount = parseFloat(document.getElementById("logExpAmount").value || 0);
    const type = document.getElementById("logExpType").value;
    const descInput = document.getElementById("logExpDescription");
    const desc = descInput ? descInput.value.trim() : "";

    if (!date || amount <= 0) {
      App.showToast("Valid date and positive amount required", "error");
      return;
    }

    try {
      const res = await App.apiFetch("/api/manager/expenses", {
        method: "POST",
        body: {
          expense_date: date,
          expense_amount: amount,
          expense_type: type,
          description: desc || null
        }
      });
      App.showToast(res.message, "success");
      document.getElementById("logExpenseModal").classList.remove("open");
      if (descInput) descInput.value = "";
      document.getElementById("logExpAmount").value = "";
      await this.refresh();
    } catch (e) {
      App.showToast("Failed to log expense: " + e.message, "error");
    }
  }
};
