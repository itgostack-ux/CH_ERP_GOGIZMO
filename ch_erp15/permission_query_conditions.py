import frappe

def get_conditions(user, doctype=None):
    """
    Permission query conditions for City / Zone
    Applied automatically during list, link search, reports
    """

    # System Manager → no restriction
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return ""

    # Get values from User Defaults / Session
    company = frappe.defaults.get_user_default("company")
    city = frappe.defaults.get_user_default("city")
    zone = frappe.defaults.get_user_default("zone")

    # City permission
    if doctype == "City" and city:
        return f"`tabCity`.`name` = {frappe.db.escape(city)}"

    # Zone permission
    if doctype == "Zone" and zone:
        return f"`tabZone`.`name` = {frappe.db.escape(zone)}"

    # No condition
    return ""
