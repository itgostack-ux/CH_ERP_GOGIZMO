frappe.query_reports["Stock Shortage By Store"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            default: frappe.defaults.get_user_default("Company"),
        },
        {
            fieldname: "store",
            label: __("Store"),
            fieldtype: "Link",
            options: "CH Store",
        },
    ],
};
