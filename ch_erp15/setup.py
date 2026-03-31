import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


CUSTOM_FIELDS = {
    "Material Request": [
        # ── Store context section ──
        {
            "fieldname": "custom_store_section",
            "fieldtype": "Section Break",
            "label": "Store Request Details",
            "insert_after": "material_request_type",
            "collapsible": 1,
            "depends_on": "eval:doc.custom_store || doc.custom_pos_profile",
        },
        {
            "fieldname": "custom_store",
            "fieldtype": "Link",
            "label": "Store",
            "options": "CH Store",
            "insert_after": "custom_store_section",
            "read_only": 1,
        },
        {
            "fieldname": "custom_pos_profile",
            "fieldtype": "Link",
            "label": "POS Profile",
            "options": "POS Profile",
            "insert_after": "custom_store",
            "read_only": 1,
        },
        {
            "fieldname": "custom_store_col_break",
            "fieldtype": "Column Break",
            "insert_after": "custom_pos_profile",
        },
        {
            "fieldname": "custom_priority",
            "fieldtype": "Select",
            "label": "Priority",
            "options": "\nUrgent\nStandard\nLow",
            "insert_after": "custom_store_col_break",
            "default": "Standard",
        },
        {
            "fieldname": "custom_approval_status",
            "fieldtype": "Select",
            "label": "Approval Status",
            "options": "\nPending Approval\nApproved\nRejected",
            "insert_after": "custom_priority",
            "read_only": 1,
            "depends_on": "eval:doc.custom_store",
            "in_list_view": 1,
            "in_standard_filter": 1,
        },
        {
            "fieldname": "custom_request_notes",
            "fieldtype": "Small Text",
            "label": "Request Notes",
            "insert_after": "custom_approval_status",
        },
        {
            "fieldname": "custom_source_material_request",
            "fieldtype": "Link",
            "label": "Source Material Request",
            "options": "Material Request",
            "insert_after": "custom_request_notes",
            "read_only": 1,
            "description": "Transfer MR this purchase request was raised from",
        },
        {
            "fieldname": "custom_preferred_source_warehouse",
            "fieldtype": "Link",
            "label": "Preferred Source Warehouse",
            "options": "Warehouse",
            "insert_after": "custom_source_material_request",
            "depends_on": "eval:doc.material_request_type=='Material Transfer'",
        },
        # ── SLA fields ──
        {
            "fieldname": "custom_sla_section",
            "fieldtype": "Section Break",
            "label": "SLA Tracking",
            "insert_after": "custom_preferred_source_warehouse",
            "collapsible": 1,
            "depends_on": "eval:doc.custom_store",
        },
        {
            "fieldname": "custom_sla_breach_date",
            "fieldtype": "Datetime",
            "label": "SLA Breach Date",
            "insert_after": "custom_sla_section",
            "read_only": 1,
        },
        {
            "fieldname": "custom_sla_breached",
            "fieldtype": "Check",
            "label": "SLA Breached",
            "insert_after": "custom_sla_breach_date",
            "read_only": 1,
        },
        # ── Allocation plan (hidden JSON) ──
        {
            "fieldname": "custom_allocation_plan",
            "fieldtype": "JSON",
            "label": "Allocation Plan",
            "insert_after": "custom_sla_breached",
            "read_only": 1,
            "hidden": 1,
        },
        # ── Closure details ──
        {
            "fieldname": "custom_closure_section",
            "fieldtype": "Section Break",
            "label": "Closure Details",
            "insert_after": "custom_allocation_plan",
            "collapsible": 1,
            "depends_on": "eval:doc.custom_closure_reason",
        },
        {
            "fieldname": "custom_closure_reason",
            "fieldtype": "Small Text",
            "label": "Closure Reason",
            "insert_after": "custom_closure_section",
            "read_only": 1,
        },
        {
            "fieldname": "custom_closure_col_break",
            "fieldtype": "Column Break",
            "insert_after": "custom_closure_reason",
        },
        {
            "fieldname": "custom_closed_by",
            "fieldtype": "Link",
            "label": "Closed By",
            "options": "User",
            "insert_after": "custom_closure_col_break",
            "read_only": 1,
        },
        {
            "fieldname": "custom_closure_date",
            "fieldtype": "Datetime",
            "label": "Closure Date",
            "insert_after": "custom_closed_by",
            "read_only": 1,
        },
    ],
    # ── Damage tracking on Stock Entry items ──
    "Stock Entry Detail": [
        {
            "fieldname": "custom_damaged_qty",
            "fieldtype": "Float",
            "label": "Damaged Qty",
            "insert_after": "qty",
            "depends_on": "eval:parent.stock_entry_type=='Material Transfer'",
        },
        {
            "fieldname": "custom_damage_notes",
            "fieldtype": "Small Text",
            "label": "Damage Notes",
            "insert_after": "custom_damaged_qty",
            "depends_on": "eval:doc.custom_damaged_qty > 0",
        },
    ],
}


def _filter_ready_fields(fields_dict):
    """Skip Link fields whose target DocType doesn't exist yet."""
    ready = {}
    for dt, field_list in fields_dict.items():
        filtered = []
        for f in field_list:
            if f.get("fieldtype") == "Link" and f.get("options"):
                if not frappe.db.exists("DocType", f["options"]):
                    continue
            filtered.append(f)
        if filtered:
            ready[dt] = filtered
    return ready


def after_install():
    _ensure_module_def()
    create_custom_fields(_filter_ready_fields(CUSTOM_FIELDS), update=False)


def after_migrate():
    create_custom_fields(_filter_ready_fields(CUSTOM_FIELDS), update=False)


def before_uninstall():
    for dt, fields in CUSTOM_FIELDS.items():
        for field in fields:
            frappe.db.delete(
                "Custom Field",
                {"dt": dt, "fieldname": field["fieldname"]},
            )
    frappe.db.commit()


def _ensure_module_def():
    if not frappe.db.exists("Module Def", "Ch Erp15"):
        m = frappe.new_doc("Module Def")
        m.module_name = "Ch Erp15"
        m.app_name = "ch_erp15"
        m.insert(ignore_permissions=True)
        frappe.db.commit()
