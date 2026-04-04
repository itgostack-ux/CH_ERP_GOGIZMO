/**
 * Operations Hub — Dashboard Workspace
 *
 * Overview KPIs: pending requests, SLA breaches, active transfers,
 * pending receipts, and quick action buttons.
 */
import { OpsState, EventBus } from "../../state.js";

export class DashboardWorkspace {
	constructor() {
		this._panel = null;
		EventBus.on("workspace:render", (ctx) => {
			if (ctx.module !== "dashboard") return;
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
						<div class="ops-kpi-value" id="kpi-pending-requests">—</div>
						<div class="ops-kpi-label">${__("Pending Requests")}</div>
						<div class="ops-kpi-sub" id="kpi-pending-approval">—</div>
					</div>
					<div class="ops-kpi-card ops-kpi-danger" data-navigate="requests">
						<div class="ops-kpi-value" id="kpi-sla-breached">—</div>
						<div class="ops-kpi-label">${__("SLA Breached")}</div>
						<div class="ops-kpi-sub">${__("Overdue requests")}</div>
					</div>
					<div class="ops-kpi-card" data-navigate="transfers">
						<div class="ops-kpi-value" id="kpi-active-transfers">—</div>
						<div class="ops-kpi-label">${__("Active Transfers")}</div>
						<div class="ops-kpi-sub" id="kpi-in-transit">—</div>
					</div>
					<div class="ops-kpi-card" data-navigate="receiving">
						<div class="ops-kpi-value" id="kpi-pending-receipt">—</div>
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
		this._panel.on("click", ".ops-kpi-card[data-navigate]", function () {
			const mod = $(this).data("navigate");
			EventBus.emit("module:set", mod);
			EventBus.emit("module:switch", mod);
		});

		this._panel.on("click", ".ops-action-btn", function () {
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
				if (!r.message) return;
				const s = r.message;
				OpsState.stats = s;
				this._panel.find("#kpi-pending-requests").text(s.pending_requests || 0);
				this._panel.find("#kpi-pending-approval").text(
					__("{0} awaiting approval", [s.pending_approval || 0])
				);
				this._panel.find("#kpi-sla-breached").text(s.sla_breached || 0);
				this._panel.find("#kpi-active-transfers").text(s.active_transfers || 0);
				this._panel.find("#kpi-in-transit").text(
					__("{0} in transit", [s.in_transit || 0])
				);
				this._panel.find("#kpi-pending-receipt").text(s.pending_receipt || 0);
				this._render_recent(s.recent_activity || []);
			},
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
			const icon = act.type === "Material Request" ? "fa-clipboard"
				: act.type === "Stock Entry" ? "fa-truck"
				: "fa-file-text-o";
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

		$list.on("click", ".ops-recent-item", function () {
			frappe.set_route("Form", $(this).data("doctype"), $(this).data("name"));
		});
	}
}
