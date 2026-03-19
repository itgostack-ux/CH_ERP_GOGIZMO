from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import PurchaseInvoice
from ch_erp15.ch_erp15.custom.procurement_rules import enforce_procurement_rules


class CustomPurchaseInvoice(PurchaseInvoice):
    def validate(self):
        enforce_procurement_rules(self)
        super().validate()
        enforce_procurement_rules(self)

    #     return gl_entries