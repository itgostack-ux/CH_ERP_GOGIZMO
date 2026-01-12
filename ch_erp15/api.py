import frappe

# ---------------------------------------------------
# COMPANY → CITY
# ---------------------------------------------------
@frappe.whitelist()
def get_company_cities(doctype, txt, searchfield, start, page_len, filters):
    company_name = filters.get("company_name") if filters else None

    if not company_name:
        return []

    rows = frappe.get_all(
        "City Master",
        filters={
            "parenttype": "Company",
            "parentfield": "custom_company_city",
            "parent": company_name
        },
        fields=["city_master"]
    )

    return [
        (row.city_master,)
        for row in rows
        if row.city_master and txt.lower() in row.city_master.lower()
    ]


# ---------------------------------------------------
# COMPANY → ZONE  ✅ NEW METHOD
# ---------------------------------------------------
@frappe.whitelist()
def get_company_zones(doctype, txt, searchfield, start, page_len, filters):
    company_name = filters.get("company_name") if filters else None

    if not company_name:
        return []

    rows = frappe.get_all(
        "Zone Master",
        filters={
            "parenttype": "Company",
            "parentfield": "custom_company_zone",
            "parent": company_name
        },
        fields=["zone_master"]
    )

    return [
        (row.zone_master,)
        for row in rows
        if row.zone_master and txt.lower() in row.zone_master.lower()
    ]
