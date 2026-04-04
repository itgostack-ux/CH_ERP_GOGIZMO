/**
 * Operations Hub — Receiving Workspace
 *
 * Incoming stock: transfers arriving at user's warehouses
 * and purchase receipts pending GRN processing.
 */
import { OpsState, EventBus } from "../../state.js";

const RECEIVING_TABS = [
	{ key: "pending",   label: __("Pending Receipt") },
	{ key: "received",  label: __("Recently Received") },
];

export class ReceivingWorkspace {
	constructor() {
		this._panel = null;
		this._active_tab = "pending";
		this._items = [];
		EventBus.on("workspace:render", (ctx) => {
			if (ctx.module !== "receiving") return;
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

		this._panel.on("click", ".ops-recv-row", function () {
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
				warehouse: OpsState.active_warehouse || "",
			},
			callback: (r) => {
				this._items = r.message || [];
				this._render_list();
			},
		});
	}

	_render_list() {
		const $list = this._panel.find("#ops-receiving-list");

		if (!this._items.length) {
			$list.html(`<div class="ops-empty-state">
				<i class="fa fa-inbox"></i>
				<p>${this._active_tab === "pending"
					? __("No pending receipts")
					: __("No recent receipts")}</p>
			</div>`);
			return;
		}

		let html = "";
		for (const item of this._items) {
			const icon = item.doctype === "Purchase Receipt" ? "fa-shopping-bag" : "fa-truck";
			const time_ago = frappe.datetime.prettyDate(item.creation);
			const from_label = item.from_warehouse
				? `<span class="ops-recv-from">${__("From")}: ${frappe.utils.escape_html(item.from_warehouse)}</span>`
				: item.supplier
				? `<span class="ops-recv-from">${__("Supplier")}: ${frappe.utils.escape_html(item.supplier)}</span>`
				: "";

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
}
