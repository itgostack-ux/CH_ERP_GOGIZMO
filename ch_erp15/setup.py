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
            "fieldname": "custom_request_notes",
            "fieldtype": "Small Text",
            "label": "Request Notes",
            "insert_after": "custom_priority",
        },
        # ── SLA fields ──
        {
            "fieldname": "custom_sla_section",
            "fieldtype": "Section Break",
            "label": "SLA Tracking",
            "insert_after": "custom_request_notes",
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
    ],
}


def after_install():
    _ensure_module_def()
    create_custom_fields(CUSTOM_FIELDS, update=True)


def after_migrate():
    create_custom_fields(CUSTOM_FIELDS, update=True)


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
