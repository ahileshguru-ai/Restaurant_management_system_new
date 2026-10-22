/**
 * Master Application Shell & State Controller
 * Manages Role-Based Authentication, 4-Role Login Portal, and Real-Time Dashboard Sync
 */

const App = {
  currentUser: null,
  token: localStorage.getItem("token") || null,
  selectedRole: null,
  currentViewport: "fluid",
  syncInterval: null,

  async init() {
    this.bindGlobalEvents();

    // Verify existing authentication token
    if (this.token) {
      try {
        const res = await this.apiFetch("/api/auth/me");
        if (res && res.user) {
          this.currentUser = res.user;
          this.onLoginSuccess(this.currentUser);
          return;
        }
      } catch (e) {
        // Token expired or invalid -> clear session
        this.token = null;
        localStorage.removeItem("token");
      }
    }

    // Initial startup: Present the 4-role login portal
    this.showLoginPortal();
  },

  showLoginPortal() {
    const portal = document.getElementById("loginPortal");
    const app = document.getElementById("authenticatedApp");
    if (portal) portal.style.display = "flex";
    if (app) app.style.display = "none";
    this.backToRoleSelection();
  },

  selectRoleForLogin(roleName) {
    this.selectedRole = roleName;
    const grid = document.getElementById("roleSelectionGrid");
    const box = document.getElementById("roleCredentialBox");
    if (grid) grid.style.display = "none";
    if (box) box.style.display = "block";

    const roleMeta = {
      "Shop Manager": {
        icon: "💻",
        title: "Shop Manager Login",
        instructions: "Enter your assigned Shop Manager executive credentials to access management administration.",
        placeholder: "e.g. shopmanager"
      },
      "Kitchen Manager": {
        icon: "📟",
        title: "Kitchen Manager Login",
        instructions: "Enter your Kitchen Manager credentials created by the Shop Manager to access kitchen operations.",
        placeholder: "e.g. kitchenmgr"
      },
      "Chef": {
        icon: "👨‍🍳",
        title: "Chef Login",
        instructions: "Enter your assigned Chef credentials created by the Shop Manager to access the live KDS cooking station.",
        placeholder: "e.g. chef_vikram"
      },
      "Waiter": {
        icon: "📱",
        title: "Waiter Login",
        instructions: "Enter your assigned Waiter credentials created by the Shop Manager to access floor tables & mobile ordering.",
        placeholder: "e.g. waiter_rahul"
      }
    };

    const meta = roleMeta[roleName] || {
      icon: "👤",
      title: `${roleName} Login`,
      instructions: `Enter your credentials created by the Shop Manager to sign in as ${roleName}.`,
      placeholder: "Enter username"
    };

    document.getElementById("selectedRoleIcon").textContent = meta.icon;
    document.getElementById("selectedRoleTitle").textContent = meta.title;
    document.getElementById("selectedRoleInstructions").textContent = meta.instructions;
    document.getElementById("portalUsername").placeholder = meta.placeholder;
    document.getElementById("portalLoginBtn").textContent = `🚀 Sign In as ${roleName}`;

    document.getElementById("portalUsername").value = "";
    document.getElementById("portalPassword").value = "";

    const alertBox = document.getElementById("portalLoginAlert");
    if (alertBox) {
      alertBox.style.display = "none";
      alertBox.textContent = "";
    }

    setTimeout(() => {
      const uInput = document.getElementById("portalUsername");
      if (uInput) uInput.focus();
    }, 100);
  },

  backToRoleSelection() {
    this.selectedRole = null;
    const grid = document.getElementById("roleSelectionGrid");
    const box = document.getElementById("roleCredentialBox");
    if (grid) grid.style.display = "grid";
    if (box) box.style.display = "none";

    const alertBox = document.getElementById("portalLoginAlert");
    if (alertBox) {
      alertBox.style.display = "none";
      alertBox.textContent = "";
    }
  },

  togglePasswordVisibility(inputId, toggleEl) {
    const input = document.getElementById(inputId);
    if (!input) return;
    if (input.type === "password") {
      input.type = "text";
      if (toggleEl) toggleEl.textContent = "Hide";
    } else {
      input.type = "password";
      if (toggleEl) toggleEl.textContent = "Show";
    }
  },

  async submitPortalLogin() {
    const username = document.getElementById("portalUsername").value.trim();
    const password = document.getElementById("portalPassword").value;
    const alertBox = document.getElementById("portalLoginAlert");

    if (!username || !password) {
      if (alertBox) {
        alertBox.textContent = "Please enter both username and password.";
        alertBox.style.display = "flex";
      }
      return;
    }

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: username,
          password: password,
          expected_role: this.selectedRole
        })
      });

      const data = await res.json();
      if (!res.ok) {
        const errorDetail = data.detail || "Authentication failed.";
        if (alertBox) {
          alertBox.textContent = errorDetail;
          alertBox.style.display = "flex";
        }
        this.showToast(errorDetail, "error");
        return;
      }

      this.token = data.access_token;
      localStorage.setItem("token", this.token);
      this.currentUser = data.user;

      this.showToast(`Logged in successfully as ${data.user.staff_name} (${data.user.role})`, "success");
      this.onLoginSuccess(data.user);
    } catch (e) {
      const msg = "Network/server error: " + e.message;
      if (alertBox) {
        alertBox.textContent = msg;
        alertBox.style.display = "flex";
      }
      this.showToast(msg, "error");
    }
  },

  logout() {
    this.token = null;
    this.currentUser = null;
    this.selectedRole = null;
    localStorage.removeItem("token");
    if (this.syncInterval) clearInterval(this.syncInterval);
    this.showToast("Signed out successfully", "info");
    this.showLoginPortal();
  },

  onLoginSuccess(user) {
    const portal = document.getElementById("loginPortal");
    const app = document.getElementById("authenticatedApp");
    if (portal) portal.style.display = "none";
    if (app) app.style.display = "block";

    // Update Topbar and User Session displays
    const topDisplayName = document.getElementById("topUserDisplayName");
    const topRoleBadge = document.getElementById("topUserRoleBadge");
    const topUserName = document.getElementById("topUserName");
    const topUserAvatar = document.getElementById("topUserAvatar");
    const viewportLabel = document.getElementById("deviceViewportLabel");

    if (topDisplayName) topDisplayName.textContent = user.staff_name;
    if (topRoleBadge) {
      topRoleBadge.textContent = user.role;
      topRoleBadge.className = "bubble-badge " + (
        user.role === "Shop Manager" ? "badge-purple" :
          user.role === "Kitchen Manager" ? "badge-blue" :
            user.role === "Chef" ? "badge-orange" : "badge-green"
      );
    }
    if (topUserName) topUserName.textContent = user.staff_name;
    if (topUserAvatar) topUserAvatar.textContent = user.staff_name.charAt(0);

    const stationDescriptors = {
      "Waiter": "📱 Waiter Mobile POS Station",
      "Chef": "🖥️ Chef Kitchen Display System (KDS)",
      "Kitchen Manager": "📟 Kitchen Operations & Inventory Hub",
      "Shop Manager": "💻 Shop Manager Executive Console"
    };
    if (viewportLabel) {
      viewportLabel.textContent = stationDescriptors[user.role] || `${user.role} Workspace`;
    }

    this.setViewportMode("fluid");
    this.renderCurrentRoleDashboard();
    this.startLiveSync();
  },

  setViewportMode(mode) {
    this.currentViewport = mode;
    const frame = document.getElementById("deviceFrame");
    if (!frame) return;
    frame.className = `viewport-device-frame viewport-mode-${mode}`;
  },

  renderCurrentRoleDashboard() {
    if (!this.currentUser) return;
    const role = this.currentUser.role;

    // Hide all dashboards first
    document.getElementById("waiterDashboard").style.display = "none";
    document.getElementById("chefDashboard").style.display = "none";
    document.getElementById("kitchenDashboard").style.display = "none";
    document.getElementById("managerDashboard").style.display = "none";

    if (role === "Waiter") {
      document.getElementById("waiterDashboard").style.display = "block";
      WaiterModule.init();
    } else if (role === "Chef") {
      document.getElementById("chefDashboard").style.display = "block";
      ChefModule.init();
    } else if (role === "Kitchen Manager") {
      document.getElementById("kitchenDashboard").style.display = "block";
      KitchenMgrModule.init();
    } else if (role === "Shop Manager") {
      document.getElementById("managerDashboard").style.display = "block";
      ShopMgrModule.init();
    }
  },

  startLiveSync() {
    if (this.syncInterval) clearInterval(this.syncInterval);
    // Background polling every 5 seconds for seamless reactivity across active stations
    this.syncInterval = setInterval(() => {
      if (!this.currentUser) return;
      const role = this.currentUser.role;
      if (role === "Waiter") WaiterModule.refresh();
      else if (role === "Chef") ChefModule.refresh();
      else if (role === "Kitchen Manager") KitchenMgrModule.refresh();
      else if (role === "Shop Manager") ShopMgrModule.refresh();
    }, 5000);
  },

  async apiFetch(url, options = {}) {
    options.headers = options.headers || {};
    if (this.token) {
      options.headers["Authorization"] = `Bearer ${this.token}`;
    }
    if (options.body && typeof options.body === "object" && !(options.body instanceof FormData)) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(options.body);
    }

    const res = await fetch(url, options);
    let data;
    try {
      data = await res.json();
    } catch (_) {
      data = null;
    }

    if (!res.ok) {
      let errMsg = `Request failed (${res.status})`;
      if (data && data.detail) {
        if (typeof data.detail === "string") {
          errMsg = data.detail;
        } else if (Array.isArray(data.detail)) {
          errMsg = data.detail
            .map(d => (d && d.msg) ? d.msg : (typeof d === "string" ? d : JSON.stringify(d)))
            .join("; ");
        } else if (typeof data.detail === "object") {
          errMsg = data.detail.msg || data.detail.message || JSON.stringify(data.detail);
        }
      } else if (data && data.message) {
        errMsg = typeof data.message === "string" ? data.message : JSON.stringify(data.message);
      }
      throw new Error(errMsg);
    }
    return data;
  },

  showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    if (!container) return;

    let displayMsg = message;
    if (displayMsg instanceof Error) {
      displayMsg = displayMsg.message;
    } else if (typeof displayMsg === "object" && displayMsg !== null) {
      if (Array.isArray(displayMsg)) {
        displayMsg = displayMsg.map(d => (d && d.msg) ? d.msg : JSON.stringify(d)).join("; ");
      } else {
        displayMsg = displayMsg.message || displayMsg.detail || JSON.stringify(displayMsg);
      }
    }

    const toast = document.createElement("div");
    toast.className = `bubble-toast ${type}`;
    toast.innerHTML = `<span>${type === 'success' ? '✓' : type === 'error' ? '⚠' : 'ℹ'}</span> <span>${displayMsg}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  },

  bindGlobalEvents() {
    // Modal close triggers
    document.querySelectorAll(".btn-close-bubble, .modal-close-trigger").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".bubble-modal-backdrop").forEach(m => m.classList.remove("open"));
      });
    });

    // Close on backdrop click
    document.querySelectorAll(".bubble-modal-backdrop").forEach(backdrop => {
      backdrop.addEventListener("click", (e) => {
        if (e.target === backdrop) backdrop.classList.remove("open");
      });
    });
  },

  openRegisterUserModal() {
    document.getElementById("regFullName").value = "";
    document.getElementById("regRoleSelect").value = "Waiter";
    document.getElementById("regShiftSelect").value = "Morning Shift";
    document.getElementById("regSalary").value = "30000";
    document.getElementById("regUsername").value = "";
    document.getElementById("regPassword").value = "";
    document.getElementById("registerUserModal").classList.add("open");
  },

  async submitRegisterUser() {
    const name = document.getElementById("regFullName").value.trim();
    const role = document.getElementById("regRoleSelect").value;
    const shift = document.getElementById("regShiftSelect").value;
    const salary = parseFloat(document.getElementById("regSalary").value || 30000);
    const username = document.getElementById("regUsername").value.trim();
    const password = document.getElementById("regPassword").value;

    if (!name || !username || !password) {
      this.showToast("Full Name, Username, and Password are required.", "error");
      return;
    }

    try {
      const res = await this.apiFetch("/api/auth/register-staff", {
        method: "POST",
        body: {
          name: name,
          role: role,
          shift: shift,
          salary: salary,
          username: username,
          password: password
        }
      });

      this.showToast(res.message, "success");
      document.getElementById("registerUserModal").classList.remove("open");

      // Shop Manager remains logged in as Shop Manager; refresh personnel table
      if (typeof ShopMgrModule !== "undefined" && ShopMgrModule.fetchStaff) {
        ShopMgrModule.fetchStaff();
      }
    } catch (e) {
      this.showToast("Registration failed: " + e.message, "error");
    }
  },

  openUpdateCredentialsModal(userId, staffName, currentUsername) {
    document.getElementById("editUserId").value = userId;
    document.getElementById("editStaffNameLabel").textContent = staffName;
    document.getElementById("editCurrentUsernameLabel").textContent = currentUsername || "no login ID";
    document.getElementById("editNewUsername").value = currentUsername || "";
    document.getElementById("editNewPassword").value = "";
    document.getElementById("updateCredentialsModal").classList.add("open");
  },

  async submitUpdateCredentials() {
    const userId = parseInt(document.getElementById("editUserId").value);
    const newUsername = document.getElementById("editNewUsername").value.trim() || null;
    const newPassword = document.getElementById("editNewPassword").value || null;

    if (!newUsername && !newPassword) {
      this.showToast("Please provide a new username or a new password.", "error");
      return;
    }

    try {
      const res = await this.apiFetch("/api/auth/update-credentials", {
        method: "PUT",
        body: {
          user_id: userId,
          new_username: newUsername,
          new_password: newPassword
        }
      });

      this.showToast(res.message, "success");
      document.getElementById("updateCredentialsModal").classList.remove("open");

      // Refresh personnel table
      if (typeof ShopMgrModule !== "undefined" && ShopMgrModule.fetchStaff) {
        ShopMgrModule.fetchStaff();
      }
    } catch (e) {
      this.showToast("Failed to update credentials: " + e.message, "error");
    }
  }
};

window.addEventListener("DOMContentLoaded", () => App.init());
