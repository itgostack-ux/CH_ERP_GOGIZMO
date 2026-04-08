/**
 * Operations Hub — Transfers Workspace
 *
 * Two-view workspace:
 *   1. Manifests — Transfer Manifest lifecycle (default)
 *   2. Stock Entries — Individual Material Transfer SEs
 */
import { OpsState, EventBus } from "../../state.js";

const MANIFEST_TABS = [
	{ key: "active",    label: __("Active") },
	{ key: "delivered", label: __("Delivered") },
	{ key: "closed",    label: __("Closed") },
	{ key: "all",       label: __("All") },
];

const SE_TABS = [
	{ key: "draft",      label: __("Draft") },
	{ key: "in_transit",  label: __("In Transit") },
	{ key: "completed",   label: __("Completed") },
	{ key: "all",         label: __("All") },
];

const STATUS_COLORS = {
	"draft": "gray", "packed": "blue", "assigned": "orange",
	"pickup-started": "yellow", "in-transit": "blue",
	"delivered": "purple", "received": "green", "closed": "darkgray",
	"cancelled": "red",
};

export class TransfersWorkspace {
	constructor() {
		this._panel = null;
		this._view = "manifests"; // "manifests" or "entries"
		this._active_tab = "active";
		this._data = [];
		EventBus.on("workspace:render", (ctx) => {
			if (ctx.module !== "transfers") return;
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
			if (view === this._view) return;
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

		// Row click — manifests or SEs
		this._panel.on("click", ".ops-transfer-row .ops-transfer-main", (e) => {
			const $row = $(e.currentTarget).closest(".ops-transfer-row");
			const dt = $row.data("doctype");
			const name = $row.data("name");
			frappe.set_route("Form", dt, name);
		});

		// Create Manifest from checked SEs
		this._panel.on("click", ".ops-create-manifest-from-se", () => {
			const checked = [];
			this._panel.find(".ops-transfer-check:checked").each(function () {
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

	// ── Manifests ────────────────────────────────────────────────

	_load_manifests() {
		frappe.call({
			method: "ch_erp15.ch_erp15.transfer_manifest_api.get_manifest_queue",
			args: {
				tab: this._active_tab,
				warehouse: OpsState.active_warehouse || "",
			},
			callback: (r) => {
				this._data = r.message || [];
				this._render_manifest_list();
			},
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
			const driver = m.driver_name
				? `<span class="ops-manifest-driver"><i class="fa fa-user"></i> ${frappe.utils.escape_html(m.driver_name)}</span>`
				: "";
			const courier = m.courier_partner
				? `<span class="ops-manifest-courier"><i class="fa fa-motorcycle"></i> ${frappe.utils.escape_html(m.courier_partner)}</span>`
				: "";

			html += `
				<div class="ops-transfer-row" data-name="${frappe.utils.escape_html(m.name)}" data-doctype="CH Transfer Manifest">
					<div class="ops-transfer-main">
						<div class="ops-transfer-top">
							<span class="ops-transfer-name">${frappe.utils.escape_html(m.name)}</span>
							<span class="ops-manifest-badge ops-badge-${status_cls}" style="color:${color}">${frappe.utils.escape_html(m.status)}</span>
						</div>
						<div class="ops-transfer-route">
							<span class="ops-wh-from">${frappe.utils.escape_html(m.source_store || m.source_warehouse || "—")}</span>
							<i class="fa fa-long-arrow-right"></i>
							<span class="ops-wh-to">${frappe.utils.escape_html(m.destination_store || m.destination_warehouse || "—")}</span>
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

	// ── Stock Entries ────────────────────────────────────────────

	_load_stock_entries() {
		frappe.call({
			method: "ch_erp15.ch_erp15.operations_hub_api.get_transfer_queue",
			args: {
				tab: this._active_tab,
				warehouse: OpsState.active_warehouse || "",
			},
			callback: (r) => {
				this._data = r.message || [];
				this._render_se_list();
			},
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
							<span class="ops-wh-from">${frappe.utils.escape_html(tr.from_warehouse || "—")}</span>
							<i class="fa fa-long-arrow-right"></i>
							<span class="ops-wh-to">${frappe.utils.escape_html(tr.to_warehouse || "—")}</span>
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
}
