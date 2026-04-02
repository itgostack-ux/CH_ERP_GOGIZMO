/**
 * Material Request — List View customization for store requests.
 *
 * Shows a unified status combining docstatus, custom_approval_status,
 * and standard status into a single indicator.
 */
frappe.listview_settings["Material Request"] = frappe.listview_settings["Material Request"] || {};

const orig_get_indicator = frappe.listview_settings["Material Request"].get_indicator;

frappe.listview_settings["Material Request"].get_indicator = function (doc) {
    // Only custom handling for store requests
    if (doc.custom_store) {
        // Pre-submission states
        if (doc.docstatus === 0) {
            if (doc.custom_approval_status === "Pending Approval") {
                return [__("Pending Approval"), "orange", "custom_approval_status,=,Pending Approval"];
            }
            if (doc.custom_approval_status === "Rejected") {
                return [__("Rejected"), "red", "custom_approval_status,=,Rejected"];
            }
        }
        // Post-submission: use standard status with SLA override
        if (doc.docstatus === 1) {
            if (doc.custom_sla_breached) {
                return [__("SLA Breached — ") + doc.status, "red",
                    "custom_sla_breached,=,1"];
            }
        }
    }
    // Fall back to standard ERPNext indicator
    if (orig_get_indicator) {
        return orig_get_indicator(doc);
    }
};

// Add custom_approval_status to the fields fetched in list view
frappe.listview_settings["Material Request"].add_fields = [
    "custom_store", "custom_approval_status", "custom_priority",
    "custom_sla_breached", "material_request_type",
];
