import frappe
from frappe.utils import flt, rounded
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt


class CustomPurchaseReceipt(PurchaseReceipt):

    def validate(self):
        super().validate()

        # Run only for Marginal purchase
        if self.get("custom_purchase_type") != "Marginal":
            return

        total_taxable_value = 0
        total_gst = 0
        total_exempted = 0

        # -----------------------------------
        # ITEM CALCULATION
        # -----------------------------------
        for item in self.items:

            qty = flt(item.qty)
            rate = flt(item.rate)
            margin_unit = flt(item.custom_unit_taxable_value)

            if qty <= 0:
                continue

            # Item amount
            item_amount = rate * qty
            item.amount = item_amount
            item.base_amount = item_amount

            # Margin taxable
            taxable_value = margin_unit * qty
            item.taxable_value = taxable_value

            total_taxable_value += taxable_value

        # -----------------------------------
        # TAX CALCULATION
        # -----------------------------------
        for tax in self.taxes:

            if tax.charge_type == "On Net Total":

                gst_amount = (total_taxable_value * flt(tax.rate)) / 100

                tax.tax_amount = gst_amount
                tax.tax_amount_after_discount_amount = gst_amount
                tax.amount = gst_amount
                tax.total = gst_amount

                tax.base_tax_amount = gst_amount
                tax.base_tax_amount_after_discount_amount = gst_amount
                tax.base_amount = gst_amount
                tax.base_total = gst_amount

                total_gst += gst_amount

        # -----------------------------------
        # HEADER TAX TOTALS
        # -----------------------------------
        self.total_taxes_and_charges = total_gst
        self.base_total_taxes_and_charges = total_gst

        self.taxes_and_charges_added = total_gst
        self.base_taxes_and_charges_added = total_gst

        # -----------------------------------
        # EXEMPTED VALUE
        # -----------------------------------
        for item in self.items:

            margin = flt(item.taxable_value)

            gst_share = 0
            if total_taxable_value > 0:
                gst_share = (margin / total_taxable_value) * total_gst

            exempted_value = flt(item.amount) - margin - gst_share

            item.custom_exempted_value = exempted_value

            total_exempted += exempted_value

        # -----------------------------------
        # FINAL TOTALS
        # -----------------------------------
        custom_grand_total = total_taxable_value + total_gst + total_exempted

        self.net_total = total_taxable_value
        self.base_net_total = total_taxable_value

        self.grand_total = custom_grand_total
        self.base_grand_total = custom_grand_total

        self.rounded_total = rounded(custom_grand_total)

        # -----------------------------------
        # STORE CUSTOM HEADER FIELDS
        # -----------------------------------
        self.custom_margin_taxable = total_taxable_value
        self.custom_margin_gst = total_gst
        self.custom_exempted_value = total_exempted