import frappe

REQUIRED = ["company", "territory"]

def enforce_company_selection():
    if frappe.session.user == "Guest":
        return

    if "System Manager" in frappe.get_roles():
        return

    if not frappe.request.path.startswith("/app"):
        return

    missing = [
        f for f in REQUIRED
        if not frappe.defaults.get_user_default(f)
    ]

    if missing:
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/app"
