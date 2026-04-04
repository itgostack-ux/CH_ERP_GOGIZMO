/**
 * Operations Hub — Transfers Workspace
 *
 * Queue view of Stock Entry (Material Transfer) with status tracking.
 * Shows outgoing/incoming transfers, transit status, and fulfillment state.
 */
import { OpsState, EventBus } from "../../state.js";

const TRANSFER_TABS = [
	{ key: "draft",      label: __("Draft"),      filter: { docstatus: 0 } },
	{ key: "in_transit",  label: __("In Transit"),  filter: { docstatus: 1, custom_status: "In Transit" } },
	{ key: "dispatched",  label: __("Dispatched"),  filter: { docstatus: 1, custom_status: "Dispatched" } },
	{ key: "completed",   label: __("Completed"),   filter: { docstatus: 1, custom_status: ["in", ["Received", "Completed", ""]] } },
	{ key: "all",         label: __("All"),         filter: { docstatus: ["in", [0, 1]] } },
];

export class TransfersWorkspace {
	constructor() {
		this._panel = null;
		this._active_tab = "in_transit";
		this._transfers = [];
		EventBus.on("workspace:render", (ctx) => {
			if (ctx.module !== "transfers") return;
			this._panel = ctx.panel;
			this.render();
		});
	}

	render() {
		const tab_html = TRANSFER_TABS.map((t) => {
			const active = t.key === this._active_tab ? " active" : "";
			return `<button class="ops-tab${active}" data-tab="${t.key}">${t.label}
				<span class="ops-tab-count" id="transfer-tab-${t.key}"></span></button>`;
		}).join("");

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
						<button class="btn btn-primary btn-sm ops-new-transfer">
							<i class="fa fa-plus"></i> ${__("New Transfer")}
						</button>
						<button class="btn btn-default btn-sm ops-refresh-transfers">
							<i class="fa fa-refresh"></i>
						</button>
					</div>
				</div>

				<div class="ops-tab-bar">${tab_html}</div>

				<div class="ops-transfer-list" id="ops-transfer-list">
					<div class="ops-loading-skeleton">
						<div class="skeleton-line"></div>
						<div class="skeleton-line short"></div>
						<div class="skeleton-line"></div>
					</div>
				</div>
			</div>
		`);

		this._bind();
		this._load_transfers();
	}

	_bind() {
		this._panel.on("click", ".ops-tab", (e) => {
			const tab = $(e.currentTarget).data("tab");
			this._active_tab = tab;
			this._panel.find(".ops-tab").removeClass("active");
			$(e.currentTarget).addClass("active");
			this._load_transfers();
		});

		this._panel.on("click", ".ops-new-transfer", () => {
			frappe.new_doc("Stock Entry", { stock_entry_type: "Material Transfer" });
		});

		this._panel.on("click", ".ops-refresh-transfers", () => {
			this._load_transfers();
		});

		this._panel.on("click", ".ops-transfer-row", function () {
			frappe.set_route("Form", "Stock Entry", $(this).data("name"));
		});

		EventBus.on("warehouse:changed", () => this._load_transfers());
	}

	_load_transfers() {
		frappe.call({
			method: "ch_erp15.ch_erp15.operations_hub_api.get_transfer_queue",
			args: {
				tab: this._active_tab,
				warehouse: OpsState.active_warehouse || "",
			},
			callback: (r) => {
				this._transfers = r.message || [];
				this._render_list();
			},
		});
	}

	_render_list() {
		const $list = this._panel.find("#ops-transfer-list");

		if (!this._transfers.length) {
			$list.html(`<div class="ops-empty-state">
				<i class="fa fa-inbox"></i>
				<p>${__("No transfers found")}</p>
			</div>`);
			return;
		}

		let html = "";
		for (const tr of this._transfers) {
			const status_class = (tr.custom_status || tr.docstatus_label || "").toLowerCase().replace(/\s+/g, "-");
			const time_ago = frappe.datetime.prettyDate(tr.creation);
			const mr_link = tr.material_request
				? `<span class="ops-transfer-mr">${__("MR")}: ${frappe.utils.escape_html(tr.material_request)}</span>`
				: "";

			html += `
				<div class="ops-transfer-row" data-name="${frappe.utils.escape_html(tr.name)}">
					<div class="ops-transfer-main">
						<div class="ops-transfer-top">
							<span class="ops-transfer-name">${frappe.utils.escape_html(tr.name)}</span>
							<span class="ops-transfer-type">${frappe.utils.escape_html(tr.stock_entry_type)}</span>
							${mr_link}
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
