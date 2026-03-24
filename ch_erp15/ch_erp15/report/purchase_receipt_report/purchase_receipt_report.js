// Copyright (c) 2026, Admin and contributors
// For license information, please see license.txt

frappe.query_reports["Purchase Receipt Report"] = {
	"filters": [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			width: "80",
			options: "Company",
			default: frappe.defaults.get_default("company"),
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			width: "80",
			reqd: 1,
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			width: "80",
			reqd: 1,
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "current_status",
			label: __("Current Status"),
			fieldtype: "Select",
			width: "80",
			options: "\nDraft\nPartly Billed\nTo Bill\nCompleted\nReturn\nReturn Issued\nCancelled\nClosed",
			default: " ",
		},
		{
			fieldname: "available_in",
			label: __("Available In"),
			fieldtype: "Select",
			width: "80",
			options: "\nChennai\nThiruvananthapuram\nBengaluru",
			default: "",
		},	
		{
			fieldname: "state",
			label: __("State"),
			fieldtype: "Select",
			width: "80",
			options: "\nTamil Nadu\nKeralam\nKarnataka",
			default: "",
		},
		{
			fieldname: "purchase_category",
			label: __("Purchase Category"),
			fieldtype: "Select",
			width: "80",
			options: "\nTaxable\nMarginal\nUnregistered",
			default: "",
		},	
		{
			fieldname: "warehouse",
			label: __("Warehouses"),
			fieldtype: "MultiSelectList",
			width: "80",
			options: "Warehouse",
			get_data: (txt) => {
				let warehouse_type = frappe.query_report.get_filter_value("warehouse_type");
				let company = frappe.query_report.get_filter_value("company");

				let filters = {
					...(warehouse_type && { warehouse_type }),
					...(company && { company }),
				};
				return frappe.db.get_link_options("Warehouse", txt, filters);
			},
		},
		{
			fieldname: "category",
			label: __("CH Category"),
			fieldtype: "Link",
			width: "80",
			options: "CH Category",
		},
		{
			fieldname: "ch_sub_category",
			label: __("CH Sub Category"),
			fieldtype: "Link",
			width: "80",
			options: "CH Sub Category",
		},
		{
			fieldname: "brand",
			label: __("Brand"),
			fieldtype: "Link",
			width: "80",
			options: "Brand",
		},
		{
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			width: "80",
			options: "Supplier",
		},
	],

onload: function(report) {
    report.page.add_inner_button("Download Report", function() {
        let filters = report.get_values();
        let query = new URLSearchParams({
            filters: JSON.stringify(filters)
        }).toString();
        let url = `/api/method/ch_erp15.ch_erp15.report.purchase_receipt_report.purchase_receipt_report.download_report?${query}`;
        window.open(url);
    });
}
};

