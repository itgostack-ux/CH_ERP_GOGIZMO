frappe.provide("ops_hub");

frappe.pages["operations-hub"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Operations Hub"),
		single_column: true,
	});

	frappe.require("operations_hub.bundle.js", function () {
		wrapper.ops_hub = new ops_hub.OpsHubApp(wrapper);
		window.cur_ops_hub = wrapper.ops_hub;
	});
};

frappe.pages["operations-hub"].refresh = function (wrapper) {
	// handled inside OpsHubApp
};
