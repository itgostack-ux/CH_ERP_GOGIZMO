import frappe
from frappe.utils import flt, rounded, getdate, nowdate
from erpnext.buying.doctype.purchase_order.purchase_order import PurchaseOrder


class CustomPurchaseOrder(PurchaseOrder):

    def validate(self):
        super().validate()

        if self.get("custom_purchase_type") != "Marginal":
            return

        total_margin_taxable = 0
        total_gst = 0
        total_exempted = 0

        # ------------------------------------------------
        # ITEM LEVEL
        # ------------------------------------------------
        for item in self.items:

            qty = flt(item.qty)
            rate = flt(item.rate)
            margin_unit = flt(item.custom_unit_taxable_value)

            if qty <= 0 or rate <= 0 or margin_unit <= 0:
                continue

            item_amount = rate * qty
            item.amount = item_amount
            item.base_amount = item_amount

            margin_taxable = margin_unit * qty
            item.taxable_value = margin_taxable
            total_margin_taxable += margin_taxable

        # ------------------------------------------------
        # TAX TABLE
        # ------------------------------------------------
        for tax in self.taxes:

            tax.tax_amount = 0
            tax.tax_amount_after_discount_amount = 0
            tax.amount = 0
            tax.total = 0

            tax.base_tax_amount = 0
            tax.base_tax_amount_after_discount_amount = 0
            tax.base_amount = 0
            tax.base_total = 0

            if tax.charge_type == "On Net Total":
                tax_amount = (total_margin_taxable * flt(tax.rate)) / 100

                tax.tax_amount = tax_amount
                tax.tax_amount_after_discount_amount = tax_amount
                tax.amount = tax_amount
                tax.total = tax_amount

                tax.base_tax_amount = tax_amount
                tax.base_tax_amount_after_discount_amount = tax_amount
                tax.base_amount = tax_amount
                tax.base_total = tax_amount

                total_gst += tax_amount

        # ------------------------------------------------
        # EXEMPTED VALUE
        # ------------------------------------------------
        for item in self.items:

            qty = flt(item.qty)
            margin_unit = flt(item.custom_unit_taxable_value)

            if qty <= 0 or flt(item.amount) <= 0:
                continue

            margin_taxable = margin_unit * qty

            exempted_value = (
                flt(item.amount)
                - margin_taxable
                - total_gst
            )

            if exempted_value < 0:
                frappe.throw(
                    f"Exempted value cannot be negative for item {item.item_code}"
                )

            item.custom_exempted_value = exempted_value
            total_exempted += exempted_value

        # ------------------------------------------------
        # HEADER TOTALS
        # ------------------------------------------------
        self.net_total = total_margin_taxable
        self.base_net_total = total_margin_taxable

        self.taxes_and_charges_added = total_gst
        self.base_taxes_and_charges_added = total_gst
        self.total_taxes_and_charges = total_gst
        self.base_total_taxes_and_charges = total_gst

        custom_grand_total = (
            total_margin_taxable
            + total_gst
            + total_exempted
        )

        self.grand_total = custom_grand_total
        self.base_grand_total = custom_grand_total

        self.rounded_total = rounded(custom_grand_total)
        self.in_words = frappe.utils.money_in_words(custom_grand_total, self.currency)
