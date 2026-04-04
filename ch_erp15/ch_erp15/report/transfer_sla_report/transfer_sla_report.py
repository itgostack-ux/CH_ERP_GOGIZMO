import frappe
from frappe.utils import flt, now_datetime, time_diff_in_hours, getdate


# Default SLA targets (hours) for inter-store material transfers
TRANSFER_SLA_HOURS = {"Urgent": 8, "Standard": 24, "Low": 72}


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"fieldname": "name", "label": "Stock Entry", "fieldtype": "Link",
         "options": "Stock Entry", "width": 160},
        {"fieldname": "material_request", "label": "Material Request", "fieldtype": "Link",
         "options": "Material Request", "width": 150},
        {"fieldname": "from_warehouse", "label": "From Store", "fieldtype": "Link",
         "options": "Warehouse", "width": 140},
        {"fieldname": "to_warehouse", "label": "To Store", "fieldtype": "Link",
         "options": "Warehouse", "width": 140},
        {"fieldname": "posting_date", "label": "Transfer Date", "fieldtype": "Date",
         "width": 110},
        {"fieldname": "items_count", "label": "Items", "fieldtype": "Int", "width": 60},
        {"fieldname": "total_qty", "label": "Total Qty", "fieldtype": "Float",
         "width": 80},
        {"fieldname": "total_value", "label": "Value", "fieldtype": "Currency",
         "width": 110},
        {"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 100},
        {"fieldname": "per_received", "label": "% Received", "fieldtype": "Percent",
         "width": 90},
        {"fieldname": "age_hours", "label": "Age (Hours)", "fieldtype": "Float",
         "width": 100},
        {"fieldname": "sla_target_hours", "label": "SLA (Hours)", "fieldtype": "Float",
         "width": 90},
        {"fieldname": "sla_breached", "label": "Breached", "fieldtype": "Check",
         "width": 80},
    ]


def get_data(filters):
    conditions = ["se.docstatus = 1", "se.stock_entry_type = 'Material Transfer'"]
    params = {}

    if filters.get("company"):
        conditions.append("se.company = %(company)s")
        params["company"] = filters["company"]
    if filters.get("from_warehouse"):
        conditions.append("sed.s_warehouse = %(from_warehouse)s")
        params["from_warehouse"] = filters["from_warehouse"]
    if filters.get("to_warehouse"):
        conditions.append("sed.t_warehouse = %(to_warehouse)s")
        params["to_warehouse"] = filters["to_warehouse"]
    if filters.get("from_date"):
        conditions.append("se.posting_date >= %(from_date)s")
        params["from_date"] = filters["from_date"]
    if filters.get("to_date"):
        conditions.append("se.posting_date <= %(to_date)s")
        params["to_date"] = filters["to_date"]

    where = " AND ".join(conditions)

    data = frappe.db.sql("""
        SELECT
            se.name,
            GROUP_CONCAT(DISTINCT sed.s_warehouse) AS from_warehouse,
            GROUP_CONCAT(DISTINCT sed.t_warehouse) AS to_warehouse,
            se.posting_date,
            COUNT(sed.name) AS items_count,
            SUM(sed.qty) AS total_qty,
            SUM(sed.amount) AS total_value,
            se.per_transferred AS per_received,
            se.creation,
            (SELECT mr.name FROM `tabStock Entry Detail` sed2
             LEFT JOIN `tabMaterial Request Item` mri
               ON sed2.material_request_item = mri.name
             LEFT JOIN `tabMaterial Request` mr ON mri.parent = mr.name
             WHERE sed2.parent = se.name AND mr.name IS NOT NULL LIMIT 1
            ) AS material_request,
            (SELECT mr2.custom_priority FROM `tabStock Entry Detail` sed3
             LEFT JOIN `tabMaterial Request Item` mri2
               ON sed3.material_request_item = mri2.name
             LEFT JOIN `tabMaterial Request` mr2 ON mri2.parent = mr2.name
             WHERE sed3.parent = se.name AND mr2.name IS NOT NULL LIMIT 1
            ) AS priority
        FROM `tabStock Entry` se
        JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
        WHERE {where}
        GROUP BY se.name
        ORDER BY se.posting_date DESC, se.creation DESC
        LIMIT 500
    """.format(where=where), params, as_dict=True)  # noqa: UP032

    now = now_datetime()
    for row in data:
        row["age_hours"] = round(time_diff_in_hours(now, row["creation"]), 1)
        priority = row.pop("priority", None) or "Standard"
        row["sla_target_hours"] = TRANSFER_SLA_HOURS.get(priority, 24)
        row["sla_breached"] = 1 if row["age_hours"] > row["sla_target_hours"] else 0
        row["status"] = "Completed" if flt(row.get("per_received")) >= 100 else "In Transit"

    if filters.get("sla_breached"):
        data = [r for r in data if r["sla_breached"]]

    return data
