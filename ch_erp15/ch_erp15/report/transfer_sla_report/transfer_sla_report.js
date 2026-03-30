frappe.query_reports["Transfer SLA Report"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            default: frappe.defaults.get_user_default("Company"),
        },
        {
            fieldname: "from_warehouse",
            label: __("From Warehouse"),
            fieldtype: "Link",
            options: "Warehouse",
        },
        {
            fieldname: "to_warehouse",
            label: __("To Warehouse"),
            fieldtype: "Link",
            options: "Warehouse",
        },
        {
            fieldname: "sla_breached",
            label: __("SLA Breached Only"),
            fieldtype: "Check",
        },
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
        },
    ],
};
