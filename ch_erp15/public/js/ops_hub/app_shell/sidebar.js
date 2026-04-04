/**
 * Operations Hub — Sidebar
 *
 * Module navigation with role-based filtering.
 * Stock Manager / System Manager → all modules
 * Purchase User / Purchase Manager → Dashboard, Requests
 * Stock User → Dashboard, Requests, Transfers, Receiving
 */
import { OpsState, EventBus } from "../state.js";

const ROLE_MODULE_MAP = {
	"Stock Manager":    ["dashboard", "requests", "transfers", "receiving", "reports"],
	"System Manager":   ["dashboard", "requests", "transfers", "receiving", "reports"],
	"Stock User":       ["dashboard", "requests", "transfers", "receiving"],
	"Purchase User":    ["dashboard", "requests"],
	"Purchase Manager": ["dashboard", "requests", "reports"],
};

const MODULE_SECTIONS = [
	{
		label: __("Overview"),
		modules: [
			{ key: "dashboard", icon: "fa-tachometer", label: __("Dashboard") },
		],
	},
	{
		label: __("Procurement"),
		modules: [
			{ key: "requests", icon: "fa-clipboard", label: __("Material Requests") },
		],
	},
	{
		label: __("Stock"),
		modules: [
			{ key: "transfers", icon: "fa-truck",   label: __("Transfers") },
			{ key: "receiving", icon: "fa-download", label: __("Receiving") },
		],
	},
	{
		label: __("Insights"),
		modules: [
			{ key: "reports", icon: "fa-bar-chart", label: __("Reports") },
		],
	},
];

export class Sidebar {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.collapsed = localStorage.getItem("ops_hub_sidebar_collapsed") === "1";
		this._allowed_modules = null;
		this.render();
		this._bind();
		this._auto_responsive();
		if (this.collapsed) this._apply_collapsed(true);
	}

	/** Auto-collapse sidebar on narrow screens, auto-expand on wide */
	_auto_responsive() {
		if (!window.matchMedia) return;
		const mql = window.matchMedia("(max-width: 1024px)");
		const handler = (e) => {
			if (e.matches && !this.collapsed) {
				this.collapsed = true;
				this._apply_collapsed(true);
			} else if (!e.matches && this.collapsed &&
				localStorage.getItem("ops_hub_sidebar_collapsed") !== "1") {
				this.collapsed = false;
				this._apply_collapsed(false);
			}
		};
		mql.addEventListener("change", handler);
		// Apply immediately
		if (mql.matches && !this.collapsed) {
			this.collapsed = true;
			this._apply_collapsed(true);
		}
	}

	_compute_allowed_modules() {
		const roles = OpsState.roles || [];
		if (!roles.length) {
			this._allowed_modules = null; // show all (admin fallback)
			return;
		}

		const allowed = new Set();
		for (const role of roles) {
			const mods = ROLE_MODULE_MAP[role];
			if (mods) mods.forEach((m) => allowed.add(m));
		}
		this._allowed_modules = allowed.size ? allowed : null;
	}

	_is_module_allowed(key) {
		if (!this._allowed_modules) return true;
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
			if (!visible.length) continue;

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

		// Bottom: user identity
		const user = OpsState.user_fullname || frappe.session.user_fullname || "User";
		const initials = user.split(" ").map(w => w[0]).join("").substring(0, 2).toUpperCase();
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
					<span class="ops-online-dot${navigator.onLine ? '' : ' offline'}"></span>
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

		sidebar.on("click", ".ops-sidebar-item", function () {
			const mod = $(this).data("module");
			if (mod === OpsState.active_module) return;
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
			if (this.collapsed) this._apply_collapsed(true);
		});
	}

	_apply_collapsed(collapsed) {
		const container = this.wrapper.closest(".ops-hub-container");
		if (collapsed) {
			this.wrapper.addClass("collapsed");
			container.addClass("sidebar-collapsed");
			this.wrapper.find(".ops-sidebar-toggle i")
				.removeClass("fa-chevron-left").addClass("fa-chevron-right");
		} else {
			this.wrapper.removeClass("collapsed");
			container.removeClass("sidebar-collapsed");
			this.wrapper.find(".ops-sidebar-toggle i")
				.removeClass("fa-chevron-right").addClass("fa-chevron-left");
		}
	}
}
