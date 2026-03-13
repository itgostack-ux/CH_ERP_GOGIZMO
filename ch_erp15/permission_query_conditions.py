import frappe

def get_conditions(user, doctype=None):
    """
    Permission query conditions based on company + territory user defaults.
    Applied automatically during list, link search, reports.
    """

    # System Manager → no restriction
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return ""

    # Get values from User Defaults
    company = frappe.defaults.get_user_default("company")
    territory = frappe.defaults.get_user_default("territory")

    # Territory permission
    if doctype == "Territory" and territory:
        return f"`tabTerritory`.`name` = {frappe.db.escape(territory)}"

    # No condition
    return ""
