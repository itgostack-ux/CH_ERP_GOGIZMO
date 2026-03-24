import frappe
from frappe import _
from frappe.utils import flt, rounded
from erpnext.buying.doctype.purchase_order.purchase_order import PurchaseOrder
from ch_erp15.ch_erp15.custom.procurement_rules import enforce_procurement_rules


class CustomPurchaseOrder(PurchaseOrder):
    def validate(self):
        enforce_procurement_rules(self)
        super().validate()
        enforce_procurement_rules(self)

        self.rounded_total
