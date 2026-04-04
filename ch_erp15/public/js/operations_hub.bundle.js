/**
 * Operations Hub — Entry Point (Bundle)
 *
 * Modular operations application for Purchase / Stock / Transfer teams.
 * Architecture mirrors ch_pos shell patterns:
 *   state.js          — Central state + EventBus
 *   app_shell/        — Layout, sidebar, header bar
 *   modules/          — Dashboard, Requests, Transfers, Receiving, Reports
 */
import { OpsState, EventBus } from "./ops_hub/state.js";
import { LayoutManager } from "./ops_hub/app_shell/layout_manager.js";

// Module workspaces
import { DashboardWorkspace } from "./ops_hub/modules/dashboard/dashboard_workspace.js";
import { RequestsWorkspace } from "./ops_hub/modules/requests/requests_workspace.js";
import { TransfersWorkspace } from "./ops_hub/modules/transfers/transfers_workspace.js";
import { ReceivingWorkspace } from "./ops_hub/modules/receiving/receiving_workspace.js";
import { ReportsWorkspace } from "./ops_hub/modules/reports/reports_workspace.js";

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
				if (!r.message) return;
				const ctx = r.message;
				OpsState.user = ctx.user;
				OpsState.user_fullname = ctx.user_fullname;
				OpsState.roles = ctx.roles || [];
				OpsState.company = ctx.company;
				OpsState.companies = ctx.companies || [];
				OpsState.warehouses = ctx.warehouses || [];

				EventBus.emit("context:loaded", OpsState);
				EventBus.emit("module:switch", "dashboard");
			},
		});
	}

	destroy() {
		this.layout.destroy();
	}
};
