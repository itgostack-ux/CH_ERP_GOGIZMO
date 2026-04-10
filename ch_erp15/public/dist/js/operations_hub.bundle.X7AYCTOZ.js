(() => {
  // ../ch_erp15/ch_erp15/public/js/ops_hub/state.js
  var OpsState = {
    user: null,
    user_fullname: null,
    roles: [],
    company: null,
    companies: [],
    warehouses: [],
    active_warehouse: null,
    active_module: "dashboard",
    is_online: navigator.onLine,
    stats: {},
    reset_filters() {
      this.active_warehouse = null;
      EventBus.emit("state:filters_reset");
    }
  };
  var EventBus = {
    _handlers: {},
    on(event, handler) {
      if (!this._handlers[event]) {
        this._handlers[event] = [];
      }
      this._handlers[event].push(handler);
    },
    off(event, handler) {
      if (!this._handlers[event])
        return;
      if (handler) {
        this._handlers[event] = this._handlers[event].filter((h) => h !== handler);
      } else {
        delete this._handlers[event];
      }
    },
    emit(event, data) {
      const handlers = this._handlers[event];
      if (!handlers)
        return;
      for (const handler of handlers) {
        try {
          handler(data);
        } catch (e) {
          console.error(`[OpsHub EventBus] Error in handler for "${event}":`, e);
        }
      }
    },
    clear() {
      this._handlers = {};
    }
  };

  // ../ch_erp15/ch_erp15/public/js/ops_hub/app_shell/sidebar.js
  var ROLE_MODULE_MAP = {
    "Stock Manager": ["dashboard", "requests", "transfers", "receiving", "reports"],
    "System Manager": ["dashboard", "requests", "transfers", "receiving", "reports"],
    "Stock User": ["dashboard", "requests", "transfers", "receiving"],
    "Purchase User": ["dashboard", "requests"],
    "Purchase Manager": ["dashboard", "requests", "reports"]
  };
  var MODULE_SECTIONS = [
    {
      label: __("Overview"),
      modules: [
        { key: "dashboard", icon: "fa-tachometer", label: __("Dashboard") }
      ]
    },
    {
      label: __("Procurement"),
      modules: [
        { key: "requests", icon: "fa-clipboard", label: __("Material Requests") }
      ]
    },
    {
      label: __("Stock"),
      modules: [
        { key: "transfers", icon: "fa-truck", label: __("Transfers") },
        { key: "receiving", icon: "fa-download", label: __("Receiving") }
      ]
    },
    {
      label: __("Insights"),
      modules: [
        { key: "reports", icon: "fa-bar-chart", label: __("Reports") }
      ]
    }
  ];
  var Sidebar = class {
    constructor(wrapper) {
      this.wrapper = wrapper;
      this.collapsed = localStorage.getItem("ops_hub_sidebar_collapsed") === "1";
      this._allowed_modules = null;
      this.render();
      this._bind();
      this._auto_responsive();
      if (this.collapsed)
        this._apply_collapsed(true);
    }
    _auto_responsive() {
      if (!window.matchMedia)
        return;
      const mql = window.matchMedia("(max-width: 1024px)");
      const handler = (e) => {
        if (e.matches && !this.collapsed) {
          this.collapsed = true;
          this._apply_collapsed(true);
        } else if (!e.matches && this.collapsed && localStorage.getItem("ops_hub_sidebar_collapsed") !== "1") {
          this.collapsed = false;
          this._apply_collapsed(false);
        }
      };
      mql.addEventListener("change", handler);
      if (mql.matches && !this.collapsed) {
        this.collapsed = true;
        this._apply_collapsed(true);
      }
    }
    _compute_allowed_modules() {
      const roles = OpsState.roles || [];
      if (!roles.length) {
        this._allowed_modules = null;
        return;
      }
      const allowed = /* @__PURE__ */ new Set();
      for (const role of roles) {
        const mods = ROLE_MODULE_MAP[role];
        if (mods)
          mods.forEach((m) => allowed.add(m));
      }
      this._allowed_modules = allowed.size ? allowed : null;
    }
    _is_module_allowed(key) {
      if (!this._allowed_modules)
        return true;
      return this._allowed_modules.has(key);
    }
    render() {
      this._compute_allowed_modules();
      let html = `
			<button class="ops-sidebar-toggle" title="${__("Toggle sidebar")}">
				<i class="fa fa-chevron-left"></i>
			</button>`;
      for (const section of MODULE_SECTIONS) {
        const visible = section.modules.filter((m) => this._is_module_allowed(m.key));
        if (!visible.length)
          continue;
        html += `<div class="ops-sidebar-section">${section.label}</div>`;
        for (const mod of visible) {
          const active = mod.key === OpsState.active_module ? " active" : "";
          html += `
					<button class="ops-sidebar-item${active}"
						data-module="${mod.key}"
						title="${mod.label}">
						<span class="sidebar-icon"><i class="fa ${mod.icon}"></i></span>
						<span class="sidebar-label">${mod.label}</span>
					</button>`;
        }
      }
      const user = OpsState.user_fullname || frappe.session.user_fullname || "User";
      const initials = user.split(" ").map((w) => w[0]).join("").substring(0, 2).toUpperCase();
      const company = OpsState.company || "";
      html += `
			<div class="ops-sidebar-bottom">
				<div class="ops-sidebar-identity">
					<div class="ops-sidebar-avatar">${frappe.utils.escape_html(initials)}</div>
					<div class="ops-sidebar-detail">
						<span class="ops-sidebar-name">${frappe.utils.escape_html(user)}</span>
						<span class="ops-sidebar-company">${frappe.utils.escape_html(company)}</span>
					</div>
				</div>
				<div class="ops-sidebar-status">
					<span class="ops-online-dot${navigator.onLine ? "" : " offline"}"></span>
					<span class="ops-online-label">${navigator.onLine ? __("Online") : __("Offline")}</span>
				</div>
			</div>`;
      this.wrapper.html(html);
    }
    _bind() {
      const sidebar = this.wrapper;
      sidebar.on("click", ".ops-sidebar-toggle", () => {
        this.collapsed = !this.collapsed;
        localStorage.setItem("ops_hub_sidebar_collapsed", this.collapsed ? "1" : "0");
        this._apply_collapsed(this.collapsed);
      });
      sidebar.on("click", ".ops-sidebar-item", function() {
        const mod = $(this).data("module");
        if (mod === OpsState.active_module)
          return;
        sidebar.find(".ops-sidebar-item").removeClass("active");
        $(this).addClass("active");
        OpsState.active_module = mod;
        EventBus.emit("module:switch", mod);
      });
      EventBus.on("module:set", (mod) => {
        sidebar.find(".ops-sidebar-item").removeClass("active");
        sidebar.find(`.ops-sidebar-item[data-module="${mod}"]`).addClass("active");
        OpsState.active_module = mod;
      });
      EventBus.on("context:loaded", () => {
        this.render();
        if (this.collapsed)
          this._apply_collapsed(true);
      });
    }
    _apply_collapsed(collapsed) {
      const container = this.wrapper.closest(".ops-hub-container");
      if (collapsed) {
        this.wrapper.addClass("collapsed");
        container.addClass("sidebar-collapsed");
        this.wrapper.find(".ops-sidebar-toggle i").removeClass("fa-chevron-left").addClass("fa-chevron-right");
      } else {
        this.wrapper.removeClass("collapsed");
        container.removeClass("sidebar-collapsed");
        this.wrapper.find(".ops-sidebar-toggle i").removeClass("fa-chevron-right").addClass("fa-chevron-left");
      }
    }
  };

  // ../ch_erp15/ch_erp15/public/js/ops_hub/app_shell/header_bar.js
  var HeaderBar = class {
    constructor(wrapper) {
      this.wrapper = wrapper;
      this.render();
      this._bind();
    }
    render() {
      const user = OpsState.user_fullname || frappe.session.user_fullname || frappe.session.user;
      const company = OpsState.company || "";
      const roles = (OpsState.roles || []).filter(
        (r) => ["Stock Manager", "Stock User", "Purchase User", "Purchase Manager", "System Manager"].includes(r)
      );
      const role_label = roles[0] || "User";
      this.wrapper.html(`
			<div class="ops-header-inner">
				<div class="ops-header-left">
					<span class="ops-header-title">
						<i class="fa fa-th-large"></i>
						${__("Operations Hub")}
					</span>
				</div>

				<div class="ops-header-center">
					<div class="ops-warehouse-selector" style="display:${OpsState.warehouses.length > 1 ? "block" : "none"}">
						<select class="ops-warehouse-filter">
							<option value="">${__("All Warehouses")}</option>
						</select>
					</div>
				</div>

				<div class="ops-header-right">
					<span class="ops-header-company">${frappe.utils.escape_html(company)}</span>
					<span class="ops-header-divider">|</span>
					<span class="ops-header-role">${frappe.utils.escape_html(role_label)}</span>
					<span class="ops-header-divider">|</span>
					<span class="ops-header-user">${frappe.utils.escape_html(user)}</span>
					<span class="ops-online-dot${navigator.onLine ? "" : " offline"}"></span>
				</div>
			</div>
		`);
      this._populate_warehouses();
    }
    _populate_warehouses() {
      const $select = this.wrapper.find(".ops-warehouse-filter");
      for (const wh of OpsState.warehouses) {
        $select.append(`<option value="${frappe.utils.escape_html(wh)}">${frappe.utils.escape_html(wh)}</option>`);
      }
      if (OpsState.active_warehouse) {
        $select.val(OpsState.active_warehouse);
      }
    }
    _bind() {
      this.wrapper.on("change", ".ops-warehouse-filter", (e) => {
        OpsState.active_warehouse = $(e.target).val() || null;
        EventBus.emit("warehouse:changed", OpsState.active_warehouse);
      });
      window.addEventListener("online", () => {
        this.wrapper.find(".ops-online-dot").removeClass("offline");
        OpsState.is_online = true;
      });
      window.addEventListener("offline", () => {
        this.wrapper.find(".ops-online-dot").addClass("offline");
        OpsState.is_online = false;
      });
      EventBus.on("context:loaded", () => this.render());
    }
  };

  // ../ch_erp15/ch_erp15/public/js/ops_hub/app_shell/layout_manager.js
  var LayoutManager = class {
    constructor(wrapper) {
      this.wrapper = $(wrapper);
      this.page = wrapper.page;
      this.sidebar = null;
      this.header_bar = null;
      this.$container = null;
      this.$content_panel = null;
    }
    init() {
      this._apply_fullscreen();
      this._render_shell();
      this._init_components();
      this._bind_module_switch();
    }
    _apply_fullscreen() {
      this.page.clear_actions();
      this.wrapper.find(".page-content").addClass("ops-hub-page");
      this.wrapper.find(".page-head").hide();
      $("header.navbar").hide();
      $("body").addClass("ops-hub-fullscreen");
      $(".main-section").css({ margin: 0, padding: 0, "max-width": "100%" });
      $(".page-container").css({ margin: 0, padding: 0, "max-width": "100%" });
    }
    _render_shell() {
      const content = this.wrapper.find(".layout-main-section");
      content.empty().append(`
			<div class="ops-hub-header-bar"></div>
			<div class="ops-hub-container">
				<div class="ops-hub-sidebar"></div>
				<div class="ops-hub-content-panel"></div>
			</div>
		`);
      this.$header_bar = content.find(".ops-hub-header-bar");
      this.$container = content.find(".ops-hub-container");
      this.$sidebar = content.find(".ops-hub-sidebar");
      this.$content_panel = content.find(".ops-hub-content-panel");
    }
    _init_components() {
      this.header_bar = new HeaderBar(this.$header_bar);
      this.sidebar = new Sidebar(this.$sidebar);
    }
    _bind_module_switch() {
      EventBus.on("module:switch", (module) => {
        this._switch_to(module);
      });
    }
    _switch_to(module) {
      this.$content_panel.off();
      this.$content_panel.empty();
      EventBus.emit("workspace:render", {
        module,
        panel: this.$content_panel
      });
    }
    get content_panel() {
      return this.$content_panel;
    }
    destroy() {
      $("body").removeClass("ops-hub-fullscreen");
      $("header.navbar").show();
      EventBus.clear();
    }
  };

  // ../ch_erp15/ch_erp15/public/js/ops_hub/modules/dashboard/dashboard_workspace.js
  var DashboardWorkspace = class {
    constructor() {
      this._panel = null;
      EventBus.on("workspace:render", (ctx) => {
        if (ctx.module !== "dashboard")
          return;
        this._panel = ctx.panel;
        this.render();
      });
    }
    render() {
      this._panel.html(`
			<div class="ops-module-panel ops-dashboard-root">
				<div class="ops-module-header">
					<h4>
						<span class="ops-module-icon" style="background:#eff6ff;color:#1d4ed8">
							<i class="fa fa-tachometer"></i>
						</span>
						${__("Operations Dashboard")}
					</h4>
					<span class="ops-module-hint">${__("Real-time overview of procurement, stock, and fulfillment")}</span>
				</div>

				<div class="ops-dashboard-kpis">
					<div class="ops-kpi-card" data-navigate="requests">
						<div class="ops-kpi-value" id="kpi-pending-requests">\u2014</div>
						<div class="ops-kpi-label">${__("Pending Requests")}</div>
						<div class="ops-kpi-sub" id="kpi-pending-approval">\u2014</div>
					</div>
					<div class="ops-kpi-card ops-kpi-danger" data-navigate="requests">
						<div class="ops-kpi-value" id="kpi-sla-breached">\u2014</div>
						<div class="ops-kpi-label">${__("SLA Breached")}</div>
						<div class="ops-kpi-sub">${__("Overdue requests")}</div>
					</div>
					<div class="ops-kpi-card" data-navigate="transfers">
						<div class="ops-kpi-value" id="kpi-active-manifests">\u2014</div>
						<div class="ops-kpi-label">${__("Active Manifests")}</div>
						<div class="ops-kpi-sub" id="kpi-manifests-in-transit">\u2014</div>
					</div>
					<div class="ops-kpi-card" data-navigate="transfers">
						<div class="ops-kpi-value" id="kpi-active-transfers">\u2014</div>
						<div class="ops-kpi-label">${__("Stock Entries")}</div>
						<div class="ops-kpi-sub" id="kpi-in-transit">\u2014</div>
					</div>
					<div class="ops-kpi-card" data-navigate="receiving">
						<div class="ops-kpi-value" id="kpi-pending-receipt">\u2014</div>
						<div class="ops-kpi-label">${__("Pending Receipt")}</div>
						<div class="ops-kpi-sub">${__("Awaiting GRN")}</div>
					</div>
				</div>

				<div class="ops-dashboard-actions">
					<h5>${__("Quick Actions")}</h5>
					<div class="ops-action-grid">
						<button class="ops-action-btn" data-action="new_request">
							<i class="fa fa-plus-circle"></i> ${__("New Material Request")}
						</button>
						<button class="ops-action-btn" data-action="check_stock">
							<i class="fa fa-search"></i> ${__("Check Stock Availability")}
						</button>
						<button class="ops-action-btn" data-action="sla_report">
							<i class="fa fa-clock-o"></i> ${__("SLA Report")}
						</button>
						<button class="ops-action-btn" data-action="shortage_report">
							<i class="fa fa-exclamation-triangle"></i> ${__("Stock Shortage Report")}
						</button>
					</div>
				</div>

				<div class="ops-dashboard-recent">
					<h5>${__("Recent Activity")}</h5>
					<div class="ops-recent-list" id="ops-recent-activity">
						<div class="ops-loading-skeleton">
							<div class="skeleton-line"></div>
							<div class="skeleton-line short"></div>
							<div class="skeleton-line"></div>
						</div>
					</div>
				</div>
			</div>
		`);
      this._bind_actions();
      this._load_stats();
    }
    _bind_actions() {
      this._panel.on("click", ".ops-kpi-card[data-navigate]", function() {
        const mod = $(this).data("navigate");
        EventBus.emit("module:set", mod);
        EventBus.emit("module:switch", mod);
      });
      this._panel.on("click", ".ops-action-btn", function() {
        const action = $(this).data("action");
        if (action === "new_request") {
          frappe.new_doc("Material Request", { material_request_type: "Material Transfer" });
        } else if (action === "check_stock") {
          EventBus.emit("module:set", "requests");
          EventBus.emit("module:switch", "requests");
        } else if (action === "sla_report") {
          frappe.set_route("query-report", "Store Material Request SLA");
        } else if (action === "shortage_report") {
          frappe.set_route("query-report", "Stock Shortage By Store");
        }
      });
    }
    _load_stats() {
      frappe.call({
        method: "ch_erp15.ch_erp15.operations_hub_api.get_dashboard_stats",
        args: { warehouse: OpsState.active_warehouse || "" },
        callback: (r) => {
          if (!r.message)
            return;
          const s = r.message;
          OpsState.stats = s;
          this._panel.find("#kpi-pending-requests").text(s.pending_requests || 0);
          this._panel.find("#kpi-pending-approval").text(
            __("{0} awaiting approval", [s.pending_approval || 0])
          );
          this._panel.find("#kpi-sla-breached").text(s.sla_breached || 0);
          this._panel.find("#kpi-active-manifests").text(s.active_manifests || 0);
          this._panel.find("#kpi-manifests-in-transit").text(
            __("{0} in transit", [s.manifests_in_transit || 0])
          );
          this._panel.find("#kpi-active-transfers").text(s.active_transfers || 0);
          this._panel.find("#kpi-in-transit").text(
            __("{0} in transit", [s.in_transit || 0])
          );
          this._panel.find("#kpi-pending-receipt").text(s.pending_receipt || 0);
          this._render_recent(s.recent_activity || []);
        }
      });
    }
    _render_recent(activities) {
      const $list = this._panel.find("#ops-recent-activity");
      if (!activities.length) {
        $list.html(`<div class="ops-empty-state">
				<i class="fa fa-inbox"></i>
				<p>${__("No recent activity")}</p>
			</div>`);
        return;
      }
      let html = "";
      for (const act of activities) {
        const icon = act.type === "Material Request" ? "fa-clipboard" : act.type === "Stock Entry" ? "fa-truck" : act.type === "CH Transfer Manifest" ? "fa-archive" : "fa-file-text-o";
        const time_ago = frappe.datetime.prettyDate(act.creation);
        html += `
				<div class="ops-recent-item" data-doctype="${frappe.utils.escape_html(act.type)}" data-name="${frappe.utils.escape_html(act.name)}">
					<span class="ops-recent-icon"><i class="fa ${icon}"></i></span>
					<div class="ops-recent-detail">
						<span class="ops-recent-name">${frappe.utils.escape_html(act.name)}</span>
						<span class="ops-recent-desc">${frappe.utils.escape_html(act.description || "")}</span>
					</div>
					<span class="ops-recent-meta">
						<span class="ops-recent-status ops-status-${(act.status || "").toLowerCase().replace(/\s+/g, "-")}">${frappe.utils.escape_html(act.status || "")}</span>
						<span class="ops-recent-time">${time_ago}</span>
					</span>
				</div>`;
      }
      $list.html(html);
      $list.on("click", ".ops-recent-item", function() {
        frappe.set_route("Form", $(this).data("doctype"), $(this).data("name"));
      });
    }
  };

  // ../ch_erp15/ch_erp15/public/js/ops_hub/modules/requests/requests_workspace.js
  var STATUS_TABS = [
    { key: "pending_approval", label: __("Pending Approval"), filter: { custom_approval_status: "Pending Approval", docstatus: 0 } },
    { key: "approved", label: __("Approved"), filter: { custom_approval_status: "Approved", docstatus: 1, status: ["not in", ["Stopped", "Cancelled", "Received", "Transferred"]] } },
    { key: "in_progress", label: __("In Progress"), filter: { docstatus: 1, status: ["in", ["Ordered", "Partially Ordered", "Partially Received"]], custom_approval_status: "Approved" } },
    { key: "completed", label: __("Completed"), filter: { docstatus: 1, status: ["in", ["Received", "Transferred"]] } },
    { key: "all", label: __("All"), filter: { docstatus: ["in", [0, 1]] } }
  ];
  var PRIORITY_COLORS = {
    Urgent: "#dc2626",
    Standard: "#2563eb",
    Low: "#6b7280"
  };
  var RequestsWorkspace = class {
    constructor() {
      this._panel = null;
      this._active_tab = "pending_approval";
      this._requests = [];
      EventBus.on("workspace:render", (ctx) => {
        if (ctx.module !== "requests")
          return;
        this._panel = ctx.panel;
        this.render();
      });
    }
    render() {
      const tab_html = STATUS_TABS.map((t) => {
        const active = t.key === this._active_tab ? " active" : "";
        return `<button class="ops-tab${active}" data-tab="${t.key}">${t.label}
				<span class="ops-tab-count" id="tab-count-${t.key}"></span></button>`;
      }).join("");
      this._panel.html(`
			<div class="ops-module-panel ops-requests-root">
				<div class="ops-module-header">
					<h4>
						<span class="ops-module-icon" style="background:#fef3c7;color:#92400e">
							<i class="fa fa-clipboard"></i>
						</span>
						${__("Material Requests")}
					</h4>
					<div class="ops-module-actions">
						<button class="btn btn-primary btn-sm ops-new-request">
							<i class="fa fa-plus"></i> ${__("New Request")}
						</button>
						<button class="btn btn-default btn-sm ops-refresh-requests">
							<i class="fa fa-refresh"></i>
						</button>
					</div>
				</div>

				<div class="ops-tab-bar">${tab_html}</div>

				<div class="ops-request-filters">
					<select class="ops-filter-priority">
						<option value="">${__("All Priorities")}</option>
						<option value="Urgent">${__("Urgent")}</option>
						<option value="Standard">${__("Standard")}</option>
						<option value="Low">${__("Low")}</option>
					</select>
					<select class="ops-filter-store">
						<option value="">${__("All Stores")}</option>
					</select>
				</div>

				<div class="ops-request-list" id="ops-request-list">
					<div class="ops-loading-skeleton">
						<div class="skeleton-line"></div>
						<div class="skeleton-line short"></div>
						<div class="skeleton-line"></div>
						<div class="skeleton-line short"></div>
					</div>
				</div>
			</div>
		`);
      this._bind();
      this._load_stores();
      this._load_requests();
    }
    _bind() {
      this._panel.on("click", ".ops-tab", (e) => {
        const tab = $(e.currentTarget).data("tab");
        this._active_tab = tab;
        this._panel.find(".ops-tab").removeClass("active");
        $(e.currentTarget).addClass("active");
        this._load_requests();
      });
      this._panel.on("click", ".ops-new-request", () => {
        frappe.new_doc("Material Request", { material_request_type: "Material Transfer" });
      });
      this._panel.on("click", ".ops-refresh-requests", () => {
        this._load_requests();
      });
      this._panel.on("change", ".ops-filter-priority, .ops-filter-store", () => {
        this._load_requests();
      });
      this._panel.on("click", ".ops-req-row", function() {
        frappe.set_route("Form", "Material Request", $(this).data("name"));
      });
      this._panel.on("click", ".ops-btn-approve", (e) => {
        e.stopPropagation();
        this._approve_request($(e.currentTarget).data("name"));
      });
      this._panel.on("click", ".ops-btn-reject", (e) => {
        e.stopPropagation();
        this._reject_request($(e.currentTarget).data("name"));
      });
      this._panel.on("click", ".ops-btn-allocate", (e) => {
        e.stopPropagation();
        this._auto_allocate($(e.currentTarget).data("name"));
      });
      EventBus.on("warehouse:changed", () => this._load_requests());
    }
    _load_stores() {
      frappe.call({
        method: "ch_erp15.ch_erp15.operations_hub_api.get_stores",
        callback: (r) => {
          const stores = r.message || [];
          const $select = this._panel.find(".ops-filter-store");
          for (const s of stores) {
            $select.append(`<option value="${frappe.utils.escape_html(s.name)}">${frappe.utils.escape_html(s.store_name || s.name)}</option>`);
          }
        }
      });
    }
    _load_requests() {
      const tab = STATUS_TABS.find((t) => t.key === this._active_tab);
      const priority = this._panel.find(".ops-filter-priority").val() || "";
      const store = this._panel.find(".ops-filter-store").val() || "";
      frappe.call({
        method: "ch_erp15.ch_erp15.operations_hub_api.get_request_queue",
        args: {
          tab: this._active_tab,
          priority,
          store,
          warehouse: OpsState.active_warehouse || ""
        },
        callback: (r) => {
          this._requests = r.message || [];
          this._render_list();
          this._load_tab_counts();
        }
      });
    }
    _load_tab_counts() {
      frappe.call({
        method: "ch_erp15.ch_erp15.operations_hub_api.get_request_tab_counts",
        args: {
          warehouse: OpsState.active_warehouse || ""
        },
        callback: (r) => {
          const counts = r.message || {};
          for (const [key, count] of Object.entries(counts)) {
            this._panel.find(`#tab-count-${key}`).text(count || "");
          }
        }
      });
    }
    _render_list() {
      const $list = this._panel.find("#ops-request-list");
      if (!this._requests.length) {
        $list.html(`<div class="ops-empty-state">
				<i class="fa fa-inbox"></i>
				<p>${__("No requests found")}</p>
			</div>`);
        return;
      }
      let html = "";
      for (const req of this._requests) {
        const priority_color = PRIORITY_COLORS[req.priority] || "#6b7280";
        const sla_class = req.sla_breached ? "ops-sla-breached" : "";
        const sla_icon = req.sla_breached ? `<span class="ops-sla-badge" title="${__("SLA Breached")}"><i class="fa fa-exclamation-circle"></i></span>` : "";
        const time_ago = frappe.datetime.prettyDate(req.creation);
        const items_count = req.item_count || 0;
        const approval_btns = req.approval_status === "Pending Approval" ? `<button class="btn btn-xs btn-success ops-btn-approve" data-name="${frappe.utils.escape_html(req.name)}">
					<i class="fa fa-check"></i> ${__("Approve")}
				   </button>
				   <button class="btn btn-xs btn-danger ops-btn-reject" data-name="${frappe.utils.escape_html(req.name)}">
					<i class="fa fa-times"></i> ${__("Reject")}
				   </button>` : "";
        const allocate_btn = req.approval_status === "Approved" && req.status === "Pending" ? `<button class="btn btn-xs btn-primary ops-btn-allocate" data-name="${frappe.utils.escape_html(req.name)}">
					<i class="fa fa-magic"></i> ${__("Allocate")}
				   </button>` : "";
        const sla_label = req.sla_due_by ? `<span class="ops-req-sla ${sla_class}">
					${sla_icon} ${__("Due")}: ${frappe.datetime.str_to_user(req.sla_due_by)}
				   </span>` : "";
        html += `
				<div class="ops-req-row ${sla_class}" data-name="${frappe.utils.escape_html(req.name)}">
					<div class="ops-req-priority" style="background:${priority_color}"></div>
					<div class="ops-req-main">
						<div class="ops-req-top">
							<span class="ops-req-name">${frappe.utils.escape_html(req.name)}</span>
							<span class="ops-req-store">${frappe.utils.escape_html(req.store || "")}</span>
							<span class="ops-req-priority-label" style="color:${priority_color}">${frappe.utils.escape_html(req.priority)}</span>
						</div>
						<div class="ops-req-bottom">
							<span class="ops-req-items">${items_count} ${__("items")}</span>
							<span class="ops-req-status ops-status-${(req.status || "").toLowerCase().replace(/\s+/g, "-")}">${frappe.utils.escape_html(req.status)}</span>
							${sla_label}
							<span class="ops-req-time">${time_ago}</span>
						</div>
					</div>
					<div class="ops-req-actions">
						${approval_btns}
						${allocate_btn}
					</div>
				</div>`;
      }
      $list.html(html);
    }
    _approve_request(name) {
      frappe.confirm(
        __("Approve Material Request {0}?", [name]),
        () => {
          frappe.call({
            method: "ch_erp15.ch_erp15.store_request_api.approve_store_request",
            args: { request_name: name },
            callback: (r) => {
              if (r.message) {
                frappe.show_alert({ message: __("Request {0} approved", [name]), indicator: "green" });
                this._load_requests();
              }
            }
          });
        }
      );
    }
    _reject_request(name) {
      const d = new frappe.ui.Dialog({
        title: __("Reject Request"),
        fields: [
          { label: __("Reason"), fieldname: "reason", fieldtype: "Small Text", reqd: 1 }
        ],
        primary_action_label: __("Reject"),
        primary_action: (values) => {
          d.hide();
          frappe.call({
            method: "ch_erp15.ch_erp15.store_request_api.reject_store_request",
            args: { request_name: name, reason: values.reason },
            callback: (r) => {
              if (r.message) {
                frappe.show_alert({ message: __("Request {0} rejected", [name]), indicator: "orange" });
                this._load_requests();
              }
            }
          });
        }
      });
      d.show();
    }
    _auto_allocate(name) {
      frappe.call({
        method: "ch_erp15.ch_erp15.store_request_api.auto_allocate_sources",
        args: { request_name: name },
        freeze: true,
        freeze_message: __("Checking stock availability..."),
        callback: (r) => {
          if (r.message) {
            frappe.show_alert({ message: __("Allocation suggested for {0}", [name]), indicator: "green" });
            frappe.set_route("Form", "Material Request", name);
          }
        }
      });
    }
  };

  // ../ch_erp15/ch_erp15/public/js/ops_hub/modules/transfers/transfers_workspace.js
  var MANIFEST_TABS = [
    { key: "active", label: __("Active") },
    { key: "delivered", label: __("Delivered") },
    { key: "closed", label: __("Closed") },
    { key: "all", label: __("All") }
  ];
  var SE_TABS = [
    { key: "draft", label: __("Draft") },
    { key: "in_transit", label: __("In Transit") },
    { key: "completed", label: __("Completed") },
    { key: "all", label: __("All") }
  ];
  var STATUS_COLORS = {
    "draft": "gray",
    "packed": "blue",
    "assigned": "orange",
    "pickup-started": "yellow",
    "in-transit": "blue",
    "delivered": "purple",
    "received": "green",
    "closed": "darkgray",
    "cancelled": "red"
  };
  var TransfersWorkspace = class {
    constructor() {
      this._panel = null;
      this._view = "manifests";
      this._active_tab = "active";
      this._data = [];
      EventBus.on("workspace:render", (ctx) => {
        if (ctx.module !== "transfers")
          return;
        this._panel = ctx.panel;
        this.render();
      });
    }
    render() {
      this._panel.html(`
			<div class="ops-module-panel ops-transfers-root">
				<div class="ops-module-header">
					<h4>
						<span class="ops-module-icon" style="background:#ecfdf5;color:#059669">
							<i class="fa fa-truck"></i>
						</span>
						${__("Stock Transfers")}
					</h4>
					<div class="ops-module-actions">
						<button class="btn btn-primary btn-sm ops-new-manifest">
							<i class="fa fa-archive"></i> ${__("New Manifest")}
						</button>
						<button class="btn btn-default btn-sm ops-new-transfer">
							<i class="fa fa-plus"></i> ${__("New SE")}
						</button>
						<button class="btn btn-default btn-sm ops-refresh-transfers">
							<i class="fa fa-refresh"></i>
						</button>
					</div>
				</div>

				<!-- View switcher -->
				<div class="ops-view-switcher">
					<button class="ops-view-btn active" data-view="manifests">
						<i class="fa fa-archive"></i> ${__("Manifests")}
					</button>
					<button class="ops-view-btn" data-view="entries">
						<i class="fa fa-exchange"></i> ${__("Stock Entries")}
					</button>
				</div>

				<div class="ops-tab-bar" id="ops-tab-bar"></div>

				<div class="ops-transfer-list" id="ops-transfer-list">
					<div class="ops-loading-skeleton">
						<div class="skeleton-line"></div>
						<div class="skeleton-line short"></div>
						<div class="skeleton-line"></div>
					</div>
				</div>
			</div>
		`);
      this._render_tabs();
      this._bind();
      this._load_data();
    }
    _render_tabs() {
      const tabs = this._view === "manifests" ? MANIFEST_TABS : SE_TABS;
      const html = tabs.map((t) => {
        const active = t.key === this._active_tab ? " active" : "";
        return `<button class="ops-tab${active}" data-tab="${t.key}">${t.label}</button>`;
      }).join("");
      this._panel.find("#ops-tab-bar").html(html);
    }
    _bind() {
      this._panel.on("click", ".ops-view-btn", (e) => {
        const view = $(e.currentTarget).data("view");
        if (view === this._view)
          return;
        this._view = view;
        this._active_tab = view === "manifests" ? "active" : "draft";
        this._panel.find(".ops-view-btn").removeClass("active");
        $(e.currentTarget).addClass("active");
        this._render_tabs();
        this._load_data();
      });
      this._panel.on("click", ".ops-tab", (e) => {
        const tab = $(e.currentTarget).data("tab");
        this._active_tab = tab;
        this._panel.find(".ops-tab").removeClass("active");
        $(e.currentTarget).addClass("active");
        this._load_data();
      });
      this._panel.on("click", ".ops-new-manifest", () => {
        frappe.new_doc("CH Transfer Manifest");
      });
      this._panel.on("click", ".ops-new-transfer", () => {
        frappe.new_doc("Stock Entry", { stock_entry_type: "Material Transfer" });
      });
      this._panel.on("click", ".ops-refresh-transfers", () => {
        this._load_data();
      });
      this._panel.on("click", ".ops-transfer-row .ops-transfer-main", (e) => {
        const $row = $(e.currentTarget).closest(".ops-transfer-row");
        const dt = $row.data("doctype");
        const name = $row.data("name");
        frappe.set_route("Form", dt, name);
      });
      this._panel.on("click", ".ops-create-manifest-from-se", () => {
        const checked = [];
        this._panel.find(".ops-transfer-check:checked").each(function() {
          checked.push($(this).data("name"));
        });
        if (!checked.length) {
          frappe.msgprint(__("Select at least one Stock Entry to create a manifest."));
          return;
        }
        frappe.call({
          method: "ch_erp15.ch_erp15.transfer_manifest_api.create_manifest",
          args: { stock_entries: checked },
          callback: (r) => {
            if (r.message) {
              frappe.set_route("Form", "CH Transfer Manifest", r.message);
            }
          }
        });
      });
      EventBus.on("warehouse:changed", () => this._load_data());
    }
    _load_data() {
      if (this._view === "manifests") {
        this._load_manifests();
      } else {
        this._load_stock_entries();
      }
    }
    _load_manifests() {
      frappe.call({
        method: "ch_erp15.ch_erp15.transfer_manifest_api.get_manifest_queue",
        args: {
          tab: this._active_tab,
          warehouse: OpsState.active_warehouse || ""
        },
        callback: (r) => {
          this._data = r.message || [];
          this._render_manifest_list();
        }
      });
    }
    _render_manifest_list() {
      const $list = this._panel.find("#ops-transfer-list");
      if (!this._data.length) {
        $list.html(`<div class="ops-empty-state">
				<i class="fa fa-archive"></i>
				<p>${__("No manifests found")}</p>
			</div>`);
        return;
      }
      let html = "";
      for (const m of this._data) {
        const status_cls = (m.status || "").toLowerCase().replace(/\s+/g, "-");
        const color = STATUS_COLORS[status_cls] || "gray";
        const time_ago = frappe.datetime.prettyDate(m.creation);
        const driver = m.driver_name ? `<span class="ops-manifest-driver"><i class="fa fa-user"></i> ${frappe.utils.escape_html(m.driver_name)}</span>` : "";
        const courier = m.courier_partner ? `<span class="ops-manifest-courier"><i class="fa fa-motorcycle"></i> ${frappe.utils.escape_html(m.courier_partner)}</span>` : "";
        html += `
				<div class="ops-transfer-row" data-name="${frappe.utils.escape_html(m.name)}" data-doctype="CH Transfer Manifest">
					<div class="ops-transfer-main">
						<div class="ops-transfer-top">
							<span class="ops-transfer-name">${frappe.utils.escape_html(m.name)}</span>
							<span class="ops-manifest-badge ops-badge-${status_cls}" style="color:${color}">${frappe.utils.escape_html(m.status)}</span>
						</div>
						<div class="ops-transfer-route">
							<span class="ops-wh-from">${frappe.utils.escape_html(m.source_store || m.source_warehouse || "\u2014")}</span>
							<i class="fa fa-long-arrow-right"></i>
							<span class="ops-wh-to">${frappe.utils.escape_html(m.destination_store || m.destination_warehouse || "\u2014")}</span>
						</div>
						<div class="ops-transfer-bottom">
							<span class="ops-transfer-items">
								${m.total_stock_entries || 0} ${__("SEs")} &middot;
								${m.total_items || 0} ${__("items")} &middot;
								${m.total_qty || 0} ${__("qty")}
							</span>
							${driver}${courier}
							<span class="ops-transfer-time">${time_ago}</span>
						</div>
					</div>
				</div>`;
      }
      $list.html(html);
    }
    _load_stock_entries() {
      frappe.call({
        method: "ch_erp15.ch_erp15.operations_hub_api.get_transfer_queue",
        args: {
          tab: this._active_tab,
          warehouse: OpsState.active_warehouse || ""
        },
        callback: (r) => {
          this._data = r.message || [];
          this._render_se_list();
        }
      });
    }
    _render_se_list() {
      const $list = this._panel.find("#ops-transfer-list");
      if (!this._data.length) {
        $list.html(`<div class="ops-empty-state">
				<i class="fa fa-inbox"></i>
				<p>${__("No stock entries found")}</p>
				<button class="btn btn-xs btn-default ops-create-manifest-from-se" style="margin-top:8px">
					${__("Create Manifest from Selected")}
				</button>
			</div>`);
        return;
      }
      let html = `<div style="margin-bottom:8px;text-align:right">
			<button class="btn btn-xs btn-warning ops-create-manifest-from-se">
				<i class="fa fa-archive"></i> ${__("Bundle into Manifest")}
			</button>
		</div>`;
      for (const tr of this._data) {
        const status_class = (tr.custom_status || "").toLowerCase().replace(/\s+/g, "-") || (tr.docstatus === 0 ? "draft" : "submitted");
        const time_ago = frappe.datetime.prettyDate(tr.creation);
        html += `
				<div class="ops-transfer-row" data-name="${frappe.utils.escape_html(tr.name)}" data-doctype="Stock Entry">
					<label class="ops-transfer-checkbox-label">
						<input type="checkbox" class="ops-transfer-check" data-name="${frappe.utils.escape_html(tr.name)}" />
					</label>
					<div class="ops-transfer-main">
						<div class="ops-transfer-top">
							<span class="ops-transfer-name">${frappe.utils.escape_html(tr.name)}</span>
							<span class="ops-transfer-type">${frappe.utils.escape_html(tr.stock_entry_type)}</span>
						</div>
						<div class="ops-transfer-route">
							<span class="ops-wh-from">${frappe.utils.escape_html(tr.from_warehouse || "\u2014")}</span>
							<i class="fa fa-long-arrow-right"></i>
							<span class="ops-wh-to">${frappe.utils.escape_html(tr.to_warehouse || "\u2014")}</span>
						</div>
						<div class="ops-transfer-bottom">
							<span class="ops-transfer-items">${tr.item_count || 0} ${__("items")}</span>
							<span class="ops-transfer-status ops-status-${status_class}">${frappe.utils.escape_html(tr.custom_status || (tr.docstatus === 0 ? "Draft" : "Submitted"))}</span>
							<span class="ops-transfer-time">${time_ago}</span>
						</div>
					</div>
				</div>`;
      }
      $list.html(html);
    }
  };

  // ../ch_erp15/ch_erp15/public/js/ops_hub/modules/receiving/receiving_workspace.js
  var RECEIVING_TABS = [
    { key: "pending", label: __("Pending Receipt") },
    { key: "received", label: __("Recently Received") }
  ];
  var ReceivingWorkspace = class {
    constructor() {
      this._panel = null;
      this._active_tab = "pending";
      this._items = [];
      EventBus.on("workspace:render", (ctx) => {
        if (ctx.module !== "receiving")
          return;
        this._panel = ctx.panel;
        this.render();
      });
    }
    render() {
      const tab_html = RECEIVING_TABS.map((t) => {
        const active = t.key === this._active_tab ? " active" : "";
        return `<button class="ops-tab${active}" data-tab="${t.key}">${t.label}
				<span class="ops-tab-count" id="recv-tab-${t.key}"></span></button>`;
      }).join("");
      this._panel.html(`
			<div class="ops-module-panel ops-receiving-root">
				<div class="ops-module-header">
					<h4>
						<span class="ops-module-icon" style="background:#f0fdf4;color:#16a34a">
							<i class="fa fa-download"></i>
						</span>
						${__("Stock Receiving")}
					</h4>
					<div class="ops-module-actions">
						<button class="btn btn-default btn-sm ops-refresh-receiving">
							<i class="fa fa-refresh"></i>
						</button>
					</div>
				</div>

				<div class="ops-tab-bar">${tab_html}</div>

				<div class="ops-receiving-list" id="ops-receiving-list">
					<div class="ops-loading-skeleton">
						<div class="skeleton-line"></div>
						<div class="skeleton-line short"></div>
						<div class="skeleton-line"></div>
					</div>
				</div>
			</div>
		`);
      this._bind();
      this._load_items();
    }
    _bind() {
      this._panel.on("click", ".ops-tab", (e) => {
        const tab = $(e.currentTarget).data("tab");
        this._active_tab = tab;
        this._panel.find(".ops-tab").removeClass("active");
        $(e.currentTarget).addClass("active");
        this._load_items();
      });
      this._panel.on("click", ".ops-refresh-receiving", () => {
        this._load_items();
      });
      this._panel.on("click", ".ops-recv-row", function() {
        const dt = $(this).data("doctype");
        const name = $(this).data("name");
        frappe.set_route("Form", dt, name);
      });
      EventBus.on("warehouse:changed", () => this._load_items());
    }
    _load_items() {
      frappe.call({
        method: "ch_erp15.ch_erp15.operations_hub_api.get_receiving_queue",
        args: {
          tab: this._active_tab,
          warehouse: OpsState.active_warehouse || ""
        },
        callback: (r) => {
          this._items = r.message || [];
          this._render_list();
        }
      });
    }
    _render_list() {
      const $list = this._panel.find("#ops-receiving-list");
      if (!this._items.length) {
        $list.html(`<div class="ops-empty-state">
				<i class="fa fa-inbox"></i>
				<p>${this._active_tab === "pending" ? __("No pending receipts") : __("No recent receipts")}</p>
			</div>`);
        return;
      }
      let html = "";
      for (const item of this._items) {
        const icon = item.doctype === "Purchase Receipt" ? "fa-shopping-bag" : "fa-truck";
        const time_ago = frappe.datetime.prettyDate(item.creation);
        const from_label = item.from_warehouse ? `<span class="ops-recv-from">${__("From")}: ${frappe.utils.escape_html(item.from_warehouse)}</span>` : item.supplier ? `<span class="ops-recv-from">${__("Supplier")}: ${frappe.utils.escape_html(item.supplier)}</span>` : "";
        html += `
				<div class="ops-recv-row" data-doctype="${frappe.utils.escape_html(item.doctype)}" data-name="${frappe.utils.escape_html(item.name)}">
					<span class="ops-recv-icon"><i class="fa ${icon}"></i></span>
					<div class="ops-recv-main">
						<div class="ops-recv-top">
							<span class="ops-recv-name">${frappe.utils.escape_html(item.name)}</span>
							<span class="ops-recv-type">${frappe.utils.escape_html(item.doctype)}</span>
						</div>
						<div class="ops-recv-bottom">
							${from_label}
							<span class="ops-recv-to">${__("To")}: ${frappe.utils.escape_html(item.to_warehouse || "")}</span>
							<span class="ops-recv-items">${item.item_count || 0} ${__("items")}</span>
							<span class="ops-recv-time">${time_ago}</span>
						</div>
					</div>
				</div>`;
      }
      $list.html(html);
    }
  };

  // ../ch_erp15/ch_erp15/public/js/ops_hub/modules/reports/reports_workspace.js
  var REPORTS = [
    {
      key: "sla",
      title: __("Material Request SLA"),
      description: __("Track SLA compliance for store material requests"),
      icon: "fa-clock-o",
      route: "query-report/Store Material Request SLA",
      color: "#4f46e5"
    },
    {
      key: "shortage",
      title: __("Stock Shortage by Store"),
      description: __("Identify stock gaps across stores"),
      icon: "fa-exclamation-triangle",
      route: "query-report/Stock Shortage By Store",
      color: "#dc2626"
    },
    {
      key: "transfer_sla",
      title: __("Transfer SLA Report"),
      description: __("Monitor transfer timelines and delays"),
      icon: "fa-truck",
      route: "query-report/Transfer SLA Report",
      color: "#059669"
    },
    {
      key: "purchase_receipt",
      title: __("Purchase Receipt Report"),
      description: __("Track purchase receipts and supplier delivery"),
      icon: "fa-shopping-bag",
      route: "query-report/Purchase Receipt Report",
      color: "#d97706"
    }
  ];
  var ReportsWorkspace = class {
    constructor() {
      this._panel = null;
      EventBus.on("workspace:render", (ctx) => {
        if (ctx.module !== "reports")
          return;
        this._panel = ctx.panel;
        this.render();
      });
    }
    render() {
      let cards = "";
      for (const rpt of REPORTS) {
        cards += `
				<div class="ops-report-card" data-route="${rpt.route}">
					<div class="ops-report-icon" style="background:${rpt.color}15;color:${rpt.color}">
						<i class="fa ${rpt.icon}"></i>
					</div>
					<div class="ops-report-detail">
						<h6>${rpt.title}</h6>
						<p>${rpt.description}</p>
					</div>
					<i class="fa fa-chevron-right ops-report-arrow"></i>
				</div>`;
      }
      this._panel.html(`
			<div class="ops-module-panel ops-reports-root">
				<div class="ops-module-header">
					<h4>
						<span class="ops-module-icon" style="background:#faf5ff;color:#7c3aed">
							<i class="fa fa-bar-chart"></i>
						</span>
						${__("Reports & Analytics")}
					</h4>
				</div>

				<div class="ops-report-grid">
					${cards}
				</div>
			</div>
		`);
      this._panel.on("click", ".ops-report-card", function() {
        const route = $(this).data("route");
        frappe.set_route(route);
      });
    }
  };

  // ../ch_erp15/ch_erp15/public/js/operations_hub.bundle.js
  frappe.provide("ops_hub");
  ops_hub.OpsHubApp = class OpsHubApp {
    constructor(wrapper) {
      this.wrapper = $(wrapper);
      this.page = wrapper.page;
      this.layout = new LayoutManager(wrapper);
      this.init();
    }
    init() {
      this.layout.init();
      this._init_modules();
      this._load_context();
    }
    _init_modules() {
      this.dashboard = new DashboardWorkspace();
      this.requests = new RequestsWorkspace();
      this.transfers = new TransfersWorkspace();
      this.receiving = new ReceivingWorkspace();
      this.reports = new ReportsWorkspace();
    }
    _load_context() {
      frappe.call({
        method: "ch_erp15.ch_erp15.operations_hub_api.get_ops_context",
        callback: (r) => {
          if (!r.message)
            return;
          const ctx = r.message;
          OpsState.user = ctx.user;
          OpsState.user_fullname = ctx.user_fullname;
          OpsState.roles = ctx.roles || [];
          OpsState.company = ctx.company;
          OpsState.companies = ctx.companies || [];
          OpsState.warehouses = ctx.warehouses || [];
          EventBus.emit("context:loaded", OpsState);
          EventBus.emit("module:switch", "dashboard");
        }
      });
    }
    destroy() {
      this.layout.destroy();
    }
  };
})();
//# sourceMappingURL=operations_hub.bundle.X7AYCTOZ.js.map
