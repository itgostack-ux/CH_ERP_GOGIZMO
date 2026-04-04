/**
 * Operations Hub — Header Bar
 *
 * Top bar showing operator identity, company, warehouse selector,
 * and connection status.
 */
import { OpsState, EventBus } from "../state.js";

export class HeaderBar {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.render();
		this._bind();
	}

	render() {
		const user = OpsState.user_fullname || frappe.session.user_fullname || frappe.session.user;
		const company = OpsState.company || "";
		const roles = (OpsState.roles || []).filter(r =>
			["Stock Manager", "Stock User", "Purchase User", "Purchase Manager", "System Manager"].includes(r)
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
					<div class="ops-warehouse-selector" style="display:${OpsState.warehouses.length > 1 ? 'block' : 'none'}">
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
					<span class="ops-online-dot${navigator.onLine ? '' : ' offline'}"></span>
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
}
