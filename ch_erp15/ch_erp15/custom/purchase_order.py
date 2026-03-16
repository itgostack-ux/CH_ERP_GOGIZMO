# import frappe
# from erpnext.buying.doctype.purchase_order.purchase_order import PurchaseOrder

# class CustomPurchaseOrder(PurchaseOrder):
#     def validate(self):
#         super().validate()

#         doc = self.custom_purchase_type
#         print(doc,"mmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmm")
#         custom_type = getattr(self, "custom_purchase_type", None)
#         print(custom_type,"mmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmm")
#         if custom_type == "Marginal":
#             frappe.log_error(f"Marginal PO detected: {self.name}", "CustomPurchaseOrder")

#             for item in self.items:
#                 max_book_value = getattr(item, "max_book_value", None) or (item.rate * item.qty)
#                 taxable_value = float(getattr(item, "custom_unit_taxable_value", 0) or 0)
#                 exempted_value = float(getattr(item, "custom_exempted_value", 0) or 0)
#                 gst_value = float(getattr(item, "custom_gst_value", 0) or 0)

#                 # Safety check
#                 total_value = taxable_value + exempted_value + gst_value
#                 if total_value > max_book_value:
#                     frappe.throw(
#                         f"Total of Taxable + Exempted + GST exceeds Max Book Value for {item.item_code}"
#                     )

#                 # Marginal tax calculation
#                 item_taxable_amount = min(taxable_value, max_book_value)
#                 item_gst_amount = gst_value

#                 # Update item amount
#                 item.amount = item_taxable_amount + exempted_value + item_gst_amount

#                 # Update custom fields
#                 item.custom_unit_taxable_value = item_taxable_amount
#                 item.custom_exempted_value = exempted_value
#                 item.custom_gst_value = item_gst_amount
import frappe
from frappe.utils import flt, rounded
from erpnext.buying.doctype.purchase_order.purchase_order import PurchaseOrder
from frappe.utils import getdate,nowdate

class CustomPurchaseOrder(PurchaseOrder):
    pass

    # def validate(self):
    #     super().validate()




    #     print(self.custom_purchase_type,"mmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmm")

    #     if self.get("custom_purchase_type") != "Marginal":
    #         return

    #     total_margin_taxable = 0
    #     total_gst = 0
    #     total_exempted = 0

    #     # ------------------------------------------------
    #     # ITEM LEVEL
    #     # ------------------------------------------------
    #     for item in self.items:

    #         qty = flt(item.qty)
    #         rate = flt(item.rate)
    #         margin_unit = flt(item.custom_unit_taxable_value)

    #         if qty <= 0 or rate <= 0 or margin_unit <= 0:
    #             continue

    #         item_amount = rate * qty
    #         item.amount = item_amount
    #         item.base_amount = item_amount

    #         margin_taxable = margin_unit * qty
    #         item.taxable_value = margin_taxable
    #         total_margin_taxable += margin_taxable

    #     # ------------------------------------------------
    #     # TAX TABLE
    #     # ------------------------------------------------
    #     for tax in self.taxes:

    #         tax.tax_amount = 0
    #         tax.tax_amount_after_discount_amount = 0
    #         tax.amount = 0
    #         tax.total = 0

    #         tax.base_tax_amount = 0
    #         tax.base_tax_amount_after_discount_amount = 0
    #         tax.base_amount = 0
    #         tax.base_total = 0

    #         if tax.charge_type == "On Net Total":
    #             tax_amount = (total_margin_taxable * flt(tax.rate)) / 100

    #             tax.tax_amount = tax_amount
    #             tax.tax_amount_after_discount_amount = tax_amount
    #             tax.amount = tax_amount
    #             tax.total = tax_amount

    #             tax.base_tax_amount = tax_amount
    #             tax.base_tax_amount_after_discount_amount = tax_amount
    #             tax.base_amount = tax_amount
    #             tax.base_total = tax_amount

    #             total_gst += tax_amount

    #     # ------------------------------------------------
    #     # EXEMPTED VALUE
    #     # ------------------------------------------------
    #     for item in self.items:

    #         qty = flt(item.qty)
    #         margin_unit = flt(item.custom_unit_taxable_value)

    #         if qty <= 0 or flt(item.amount) <= 0:
    #             continue

    #         margin_taxable = margin_unit * qty

    #         exempted_value = (
    #             flt(item.amount)
    #             - margin_taxable
    #             - total_gst
    #         )

    #         if exempted_value < 0:
    #             frappe.throw(
    #                 f"Exempted value cannot be negative for item {item.item_code}"
    #             )

    #         item.custom_exempted_value = exempted_value
    #         total_exempted += exempted_value

    #     # ------------------------------------------------
    #     # HEADER TOTALS
    #     # ------------------------------------------------
    #     self.net_total = total_margin_taxable
    #     self.base_net_total = total_margin_taxable

    #     self.taxes_and_charges_added = total_gst
    #     self.base_taxes_and_charges_added = total_gst
    #     self.total_taxes_and_charges = total_gst
    #     self.base_total_taxes_and_charges = total_gst

    #     custom_grand_total = (
    #         item.taxable_value
    #         + self.taxes_and_charges_added
    #         + item.custom_exempted_value
    #     )

    #     self.grand_total = custom_grand_total
    #     self.base_grand_total = custom_grand_total

    #     self.rounded_total = rounded(custom_grand_total)
    #     self.in_words = frappe.utils.money_in_words(custom_grand_total, self.currency)

        
