import frappe
from frappe.utils import flt, rounded
from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import PurchaseInvoice


class CustomPurchaseInvoice(PurchaseInvoice):
    pass

    # ---------------------------------------------------
    # TAX ENGINE
    # ---------------------------------------------------
    # def calculate_taxes_and_totals(self):

    #     if self.get("custom_purchase_type") == "Marginal":
    #         self.apply_marginal_tax()
    #     else:
    #         super().calculate_taxes_and_totals()

    # # ---------------------------------------------------
    # # MARGINAL GST CALCULATION
    # # ---------------------------------------------------
    # def apply_marginal_tax(self):

    #     total_taxable = 0
    #     total_exempted = 0
    #     total_gst = 0

    #     for item in self.items:

    #         qty = flt(item.qty)
    #         amount = flt(item.amount)
    #         margin_unit = flt(item.custom_unit_taxable_value)

    #         if qty <= 0:
    #             continue

    #         taxable_value = margin_unit * qty

    #         if taxable_value > amount:
    #             frappe.throw(
    #                 f"Taxable value cannot exceed item amount for item {item.item_code}"
    #             )

    #         exempted_value = amount - taxable_value

    #         item.custom_margin_taxable = taxable_value
    #         item.custom_exempted_value = exempted_value

    #         total_taxable += taxable_value
    #         total_exempted += exempted_value

    #     for tax in self.taxes:

    #         tax_amount = 0

    #         if tax.charge_type == "On Net Total":
    #             tax_amount = flt((total_taxable * flt(tax.rate)) / 100)

    #         tax.tax_amount = tax_amount
    #         tax.tax_amount_after_discount_amount = tax_amount
    #         tax.amount = tax_amount

    #         total_gst += tax_amount

    #     net_total = flt(total_taxable + total_exempted)

    #     self.net_total = net_total
    #     self.base_net_total = net_total

    #     self.total_taxes_and_charges = total_gst
    #     self.base_total_taxes_and_charges = total_gst

    #     self.taxes_and_charges_added = total_gst
    #     self.base_taxes_and_charges_added = total_gst

    #     grand_total = flt(total_taxable + total_exempted)

    #     grand_total = rounded(grand_total)

    #     self.grand_total = grand_total
    #     self.base_grand_total = grand_total

    #     self.total = grand_total
    #     self.base_total = grand_total

    #     self.rounded_total = grand_total

    #     advance_paid = flt(getattr(self, "advance_paid", 0)) or flt(
    #         getattr(self, "advance_amount", 0)
    #     )

    #     self.outstanding_amount = grand_total - advance_paid

    #     self.custom_margin_taxable = total_taxable
    #     self.custom_margin_gst = total_gst
    #     self.custom_exempted_value = total_exempted

    #     self.in_words = frappe.utils.money_in_words(grand_total, self.currency)

    # def get_gl_entries(self, warehouse_account=None):

    #     gl_entries = super().get_gl_entries(warehouse_account)

    #     if self.get("custom_purchase_type") == "Marginal":

    #         filtered_entries = []

    #         for gl in gl_entries:

    #             # remove GST GL entry
    #             if "gst" in (gl.account or "").lower():
    #                 continue

    #             filtered_entries.append(gl)

    #         return filtered_entries

    #     return gl_entries