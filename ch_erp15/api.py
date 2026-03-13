import frappe
from frappe import _


@frappe.whitelist()
def set_login_context(company, territory, **kwargs):
    """Store company + territory selection as user defaults for the session."""
    if not company or not frappe.db.exists("Company", company):
        frappe.throw(_("Invalid or missing Company."))
    if not territory or not frappe.db.exists("Territory", territory):
        frappe.throw(_("Invalid or missing Territory."))

    frappe.defaults.set_user_default("company", company)
    frappe.defaults.set_user_default("territory", territory)
