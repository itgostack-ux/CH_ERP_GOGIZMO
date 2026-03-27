import frappe
from frappe.utils import flt


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"fieldname": "custom_store", "label": "Store", "fieldtype": "Link",
         "options": "CH Store", "width": 140},
        {"fieldname": "mr_name", "label": "Material Request", "fieldtype": "Link",
         "options": "Material Request", "width": 150},
        {"fieldname": "item_code", "label": "Item", "fieldtype": "Link",
         "options": "Item", "width": 180},
        {"fieldname": "item_name", "label": "Item Name", "fieldtype": "Data",
         "width": 180},
        {"fieldname": "requested_qty", "label": "Requested Qty", "fieldtype": "Float",
         "width": 110},
        {"fieldname": "received_qty", "label": "Received Qty", "fieldtype": "Float",
         "width": 110},
        {"fieldname": "pending_qty", "label": "Pending Qty", "fieldtype": "Float",
         "width": 110},
        {"fieldname": "status", "label": "MR Status", "fieldtype": "Data",
         "width": 110},
        {"fieldname": "custom_priority", "label": "Priority", "fieldtype": "Data",
         "width": 90},
        {"fieldname": "schedule_date", "label": "Required By", "fieldtype": "Date",
         "width": 110},
        {"fieldname": "purchase_mr", "label": "Purchase MR", "fieldtype": "Link",
         "options": "Material Request", "width": 150},
    ]


def get_data(filters):
    conditions = {
        "mr.custom_store": ("is", "set"),
        "mr.docstatus": 1,
        "mr.status": ("not in", ["Received", "Transferred", "Stopped", "Cancelled"]),
    }

    if filters.get("company"):
        conditions["mr.company"] = filters["company"]
    if filters.get("store"):
        conditions["mr.custom_store"] = filters["store"]

    rows = frappe.db.sql(
        """SELECT
              mr.custom_store, mr.name AS mr_name,
              mri.item_code, mri.item_name,
              mri.qty AS requested_qty,
              IFNULL(mri.received_qty, 0) AS received_qty,
              (mri.qty - IFNULL(mri.received_qty, 0)) AS pending_qty,
              mr.status, mr.custom_priority, mr.schedule_date
           FROM `tabMaterial Request Item` mri
           JOIN `tabMaterial Request` mr ON mr.name = mri.parent
           WHERE mr.custom_store IS NOT NULL AND mr.custom_store != ''
             AND mr.docstatus = 1
             AND mr.status NOT IN ('Received','Transferred','Stopped','Cancelled')
             AND (mri.qty - IFNULL(mri.received_qty, 0)) > 0
             {company_filter}
             {store_filter}
           ORDER BY mr.custom_store, mr.custom_priority DESC, mr.creation ASC""".format(
            company_filter="AND mr.company = %(company)s" if filters.get("company") else "",
            store_filter="AND mr.custom_store = %(store)s" if filters.get("store") else "",
        ),
        {
            "company": filters.get("company"),
            "store": filters.get("store"),
        },
        as_dict=True,
    )

    # Lookup linked purchase MRs
    if rows:
        mr_names = list(set(r["mr_name"] for r in rows))
        purchase_links = frappe.get_all(
            "Material Request",
            filters={
                "custom_source_material_request": ("in", mr_names),
                "material_request_type": "Purchase",
                "docstatus": ("in", [0, 1]),
            },
            fields=["name", "custom_source_material_request"],
        )
        pm_map = {p.custom_source_material_request: p.name for p in purchase_links}
        for row in rows:
            row["purchase_mr"] = pm_map.get(row["mr_name"], "")

    return rows
