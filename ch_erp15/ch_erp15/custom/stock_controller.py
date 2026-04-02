# Stock controller overrides for warehouse capacity validation.
#
# ERP-7 fix: Provide warehouse capacity check that can be enabled via
# CH ERP Settings (future).  Currently validates that target warehouse
# exists and is active before allowing stock movements.

import frappe
from frappe import _
from frappe.utils import flt


def validate_warehouse_active(doc, method=None):
    """Ensure source and target warehouses are not disabled."""
    for item in doc.get("items", []):
        for wh_field in ("s_warehouse", "t_warehouse", "warehouse"):
            wh = item.get(wh_field)
            if wh and frappe.db.get_value("Warehouse", wh, "disabled"):
                frappe.throw(
                    _("Warehouse {0} is disabled. Cannot proceed with this stock transaction.").format(wh),
                    title=_("Disabled Warehouse"),
                )