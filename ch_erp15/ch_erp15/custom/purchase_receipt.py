import frappe
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt
from ch_erp15.ch_erp15.custom.procurement_rules import enforce_procurement_rules

class CustomPurchaseReceipt(PurchaseReceipt):
    def validate(self):
        enforce_procurement_rules(self)
        super().validate()
        enforce_procurement_rules(self)

   