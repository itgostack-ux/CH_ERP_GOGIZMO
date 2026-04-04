/**
 * Operations Hub — Material Requests Workspace
 *
 * Queue view of all Material Requests with status tabs,
 * SLA indicators, and approval/allocation actions.
 */
import { OpsState, EventBus } from "../../state.js";

const STATUS_TABS = [
	{ key: "pending_approval", label: __("Pending Approval"), filter: { custom_approval_status: "Pending Approval", docstatus: 0 } },
	{ key: "approved",         label: __("Approved"),          filter: { custom_approval_status: "Approved", docstatus: 1, status: ["not in", ["Stopped", "Cancelled", "Received", "Transferred"]] } },
	{ key: "in_progress",      label: __("In Progress"),       filter: { docstatus: 1, status: ["in", ["Ordered", "Partially Ordered", "Partially Received"]], custom_approval_status: "Approved" } },
	{ key: "completed",        label: __("Completed"),         filter: { docstatus: 1, status: ["in", ["Received", "Transferred"]] } },
	{ key: "all",              label: __("All"),               filter: { docstatus: ["in", [0, 1]] } },
];

const PRIORITY_COLORS = {
	Urgent: "#dc2626",
	Standard: "#2563eb",
	Low: "#6b7280",
};

export class RequestsWorkspace {
	constructor() {
		this._panel = null;
		this._active_tab = "pending_approval";
		this._requests = [];
		EventBus.on("workspace:render", (ctx) => {
			if (ctx.module !== "requests") return;
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

		this._panel.on("click", ".ops-req-row", function () {
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
			},
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
				priority: priority,
				store: store,
				warehouse: OpsState.active_warehouse || "",
			},
			callback: (r) => {
				this._requests = r.message || [];
				this._render_list();
				this._load_tab_counts();
			},
		});
	}

	_load_tab_counts() {
		frappe.call({
			method: "ch_erp15.ch_erp15.operations_hub_api.get_request_tab_counts",
			args: {
				warehouse: OpsState.active_warehouse || "",
			},
			callback: (r) => {
				const counts = r.message || {};
				for (const [key, count] of Object.entries(counts)) {
					this._panel.find(`#tab-count-${key}`).text(count || "");
				}
			},
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

			const approval_btns = req.approval_status === "Pending Approval"
				? `<button class="btn btn-xs btn-success ops-btn-approve" data-name="${frappe.utils.escape_html(req.name)}">
					<i class="fa fa-check"></i> ${__("Approve")}
				   </button>
				   <button class="btn btn-xs btn-danger ops-btn-reject" data-name="${frappe.utils.escape_html(req.name)}">
					<i class="fa fa-times"></i> ${__("Reject")}
				   </button>`
				: "";

			const allocate_btn = req.approval_status === "Approved" && req.status === "Pending"
				? `<button class="btn btn-xs btn-primary ops-btn-allocate" data-name="${frappe.utils.escape_html(req.name)}">
					<i class="fa fa-magic"></i> ${__("Allocate")}
				   </button>`
				: "";

			const sla_label = req.sla_due_by
				? `<span class="ops-req-sla ${sla_class}">
					${sla_icon} ${__("Due")}: ${frappe.datetime.str_to_user(req.sla_due_by)}
				   </span>`
				: "";

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
					},
				});
			}
		);
	}

	_reject_request(name) {
		const d = new frappe.ui.Dialog({
			title: __("Reject Request"),
			fields: [
				{ label: __("Reason"), fieldname: "reason", fieldtype: "Small Text", reqd: 1 },
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
					},
				});
			},
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
			},
		});
	}
}
