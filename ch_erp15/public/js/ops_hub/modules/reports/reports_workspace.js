/**
 * Operations Hub — Reports Workspace
 *
 * Quick access to operational reports: SLA, shortage, transfer tracking.
 */
import { OpsState, EventBus } from "../../state.js";

const REPORTS = [
	{
		key: "sla",
		title: __("Material Request SLA"),
		description: __("Track SLA compliance for store material requests"),
		icon: "fa-clock-o",
		route: "query-report/Store Material Request SLA",
		color: "#4f46e5",
	},
	{
		key: "shortage",
		title: __("Stock Shortage by Store"),
		description: __("Identify stock gaps across stores"),
		icon: "fa-exclamation-triangle",
		route: "query-report/Stock Shortage By Store",
		color: "#dc2626",
	},
	{
		key: "transfer_sla",
		title: __("Transfer SLA Report"),
		description: __("Monitor transfer timelines and delays"),
		icon: "fa-truck",
		route: "query-report/Transfer SLA Report",
		color: "#059669",
	},
	{
		key: "purchase_receipt",
		title: __("Purchase Receipt Report"),
		description: __("Track purchase receipts and supplier delivery"),
		icon: "fa-shopping-bag",
		route: "query-report/Purchase Receipt Report",
		color: "#d97706",
	},
];

export class ReportsWorkspace {
	constructor() {
		this._panel = null;
		EventBus.on("workspace:render", (ctx) => {
			if (ctx.module !== "reports") return;
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

		this._panel.on("click", ".ops-report-card", function () {
			const route = $(this).data("route");
			frappe.set_route(route);
		});
	}
}
