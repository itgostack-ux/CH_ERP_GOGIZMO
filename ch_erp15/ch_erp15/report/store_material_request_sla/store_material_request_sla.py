import frappe
from frappe.utils import flt, now_datetime, time_diff_in_hours


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"fieldname": "name", "label": "Material Request", "fieldtype": "Link",
         "options": "Material Request", "width": 150},
        {"fieldname": "custom_store", "label": "Store", "fieldtype": "Link",
         "options": "CH Store", "width": 140},
        {"fieldname": "custom_priority", "label": "Priority", "fieldtype": "Data",
         "width": 90},
        {"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 120},
        {"fieldname": "custom_approval_status", "label": "Approval",
         "fieldtype": "Data", "width": 120},
        {"fieldname": "creation", "label": "Created", "fieldtype": "Datetime",
         "width": 160},
        {"fieldname": "custom_sla_breach_date", "label": "SLA Deadline",
         "fieldtype": "Datetime", "width": 160},
        {"fieldname": "custom_sla_breached", "label": "Breached", "fieldtype": "Check",
         "width": 80},
        {"fieldname": "age_hours", "label": "Age (Hours)", "fieldtype": "Float",
         "width": 100},
        {"fieldname": "per_received", "label": "% Received", "fieldtype": "Percent",
         "width": 100},
        {"fieldname": "owner", "label": "Requested By", "fieldtype": "Link",
         "options": "User", "width": 150},
    ]


def get_data(filters):
    conditions = {"custom_store": ("is", "set"), "docstatus": ("in", [0, 1])}

    if filters.get("company"):
        conditions["company"] = filters["company"]
    if filters.get("store"):
        conditions["custom_store"] = filters["store"]
    if filters.get("priority"):
        conditions["custom_priority"] = filters["priority"]
    if filters.get("sla_breached"):
        conditions["custom_sla_breached"] = 1
    if filters.get("from_date"):
        conditions["creation"] = (">=", filters["from_date"])
    if filters.get("to_date"):
        conditions["creation"] = ("<=", filters["to_date"] + " 23:59:59")

    data = frappe.get_all(
        "Material Request",
        filters=conditions,
        fields=[
            "name", "custom_store", "custom_priority", "status",
            "custom_approval_status", "creation", "custom_sla_breach_date",
            "custom_sla_breached", "per_received", "owner",
        ],
        order_by="custom_sla_breached desc, creation asc",
        limit=200,
    )

    now = now_datetime()
    for row in data:
        row["age_hours"] = round(time_diff_in_hours(now, row["creation"]), 1)

    return data
