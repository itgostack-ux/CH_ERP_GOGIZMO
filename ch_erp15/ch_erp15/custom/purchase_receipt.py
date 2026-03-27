import frappe
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt
from ch_erp15.ch_erp15.custom.procurement_rules import enforce_procurement_rules
from frappe.utils import flt, rounded,money_in_words

class CustomPurchaseReceipt(PurchaseReceipt):
    def validate(self):
        # enforce_procurement_rules(self)
        # super().validate()
        # enforce_procurement_rules(self)
        # pass

        if self.custom_purchase_type != "Marginal":
            super().validate()
            return

        total_margin_taxable = 0
        total_gst = 0
        total_exempted = 0

        total_qty = 0
        total_amount = 0
        for item in self.items:
            qty = flt(item.qty)
            rate = flt(item.rate)

            item.received_qty = qty
            item.billed_qty = 0
            margin_unit = flt(item.custom_unit_taxable_value)
            if qty <= 0 or rate <= 0 or margin_unit <= 0:
                continue
            item.amount = qty * rate
            item.base_amount = item.amount
            item.net_amount = item.amount
            item.base_net_amount = item.amount
            item.taxable_value = qty * margin_unit
            total_margin_taxable += item.taxable_value

            total_qty += qty
            total_amount += item.amount

        self.total_qty = total_qty
        self.total = total_amount

        for tax in self.taxes:
            tax.tax_amount = 0
            if tax.charge_type == "On Net Total":
                tax.tax_amount = (total_margin_taxable * flt(tax.rate)) / 100
                total_gst += tax.tax_amount
            tax.base_tax_amount_after_discount_amount = tax.tax_amount
            tax.base_tax_amount = tax.tax_amount
            tax.base_total = tax.tax_amount
            tax.total = tax.tax_amount

        for item in self.items:
            qty = flt(item.qty)
            margin_unit = flt(item.custom_unit_taxable_value)

            if qty <= 0:
                continue

            margin_taxable = qty * margin_unit

            item_gst = 0
            if total_margin_taxable:
                item_gst = (margin_taxable / total_margin_taxable) * total_gst
            exempted = flt(item.amount) - margin_taxable - item_gst
            item.custom_exempted_value = max(exempted, 0)
            total_exempted += item.custom_exempted_value

        custom_total = total_margin_taxable + total_gst + total_exempted

        self.net_total = total_margin_taxable
        self.base_net_total = total_margin_taxable
 
        self.grand_total = custom_total
        self.base_grand_total = custom_total

        self.total = total_amount
        self.total_taxes_and_charges = total_gst
        self.base_total_taxes_and_charges = total_gst

        self.rounded_total = rounded(custom_total)
        self.base_rounded_total = rounded(custom_total)

        self.outstanding_amount=custom_total
        
        self.in_words = money_in_words(self.rounded_total, self.currency)
        self.base_in_words = money_in_words(self.rounded_total, self.currency)