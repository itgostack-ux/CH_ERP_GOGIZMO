from frappe.utils import flt, rounded, money_in_words, fmt_money
from erpnext.buying.doctype.purchase_order.purchase_order import PurchaseOrder
import json


class CustomPurchaseOrder(PurchaseOrder):

    def validate(self):
        # super().validate()

        if self.custom_purchase_type != "Marginal":
            super().validate()
            return

        total_margin_taxable = 0
        total_gst = 0
        total_exempted = 0
        total_amount = 0
        total_qty = 0
        for item in self.items:
            qty = flt(item.qty)
            rate = flt(item.rate)
            margin_unit = flt(item.custom_unit_taxable_value)

            if qty <= 0 or rate <= 0:
                continue

            item_amount = qty * rate
            margin_taxable = qty * margin_unit

            item.amount = item_amount
            item.base_amount = item_amount
            item.net_amount = margin_taxable
            item.base_net_amount = margin_taxable
            item.taxable_value = margin_taxable
            total_margin_taxable += margin_taxable
            total_amount += item_amount
            total_qty += qty

        self.total_qty = total_qty
        self.total = total_amount

        # for tax in self.taxes:
        #     tax.tax_amount = 0
        #     tax.tax_amount_after_discount_amount = 0
        #     item_tax_map = {}
        #     if tax.charge_type == "On Net Total":
        #         tax.tax_amount = (total_margin_taxable * flt(tax.rate)) / 100
        #         tax.tax_amount_after_discount_amount = tax.tax_amount
        #         total_gst += tax.tax_amount

        #     tax.base_tax_amount = tax.tax_amount
        #     tax.base_tax_amount_after_discount_amount = tax.tax_amount

        #     for item in self.items:
        #         if total_margin_taxable:
        #             item_share = (flt(item.taxable_value) / total_margin_taxable) * tax.tax_amount
        #         else:
        #             item_share = 0

        #         item_tax_map[item.name] = [
        #             flt(tax.rate),
        #             item_share
        #         ]
        #     tax.item_wise_tax_detail = json.dumps(item_tax_map)

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

        self.total_taxes_and_charges = total_gst
        self.base_total_taxes_and_charges = total_gst

        self.grand_total = custom_total
        self.base_grand_total = custom_total

        self.rounded_total = rounded(custom_total)
        self.base_rounded_total = rounded(custom_total)

        self.in_words = money_in_words(self.rounded_total, self.currency)
        self.base_in_words = money_in_words(self.rounded_total, self.currency)

        # self.set_custom_tax_breakup()

    # def set_custom_tax_breakup(self):
    #     rows = ""

    #     if self.tax_category == "In State":
    #         headers = ["HSN/SAC", "Taxable Amount", "CGST", "SGST"]
    #     if self.tax_category == "Out State":
    #         headers = ["HSN/SAC", "Taxable Amount", "IGST"]

    #     hsn_data = {}
    #     for item in self.items:
    #         qty = flt(item.qty)
    #         margin_unit = flt(item.custom_unit_taxable_value)

    #         if qty <= 0 or margin_unit <= 0:
    #             continue
    #         hsn = item.gst_hsn_code or ""
    #         taxable_value = qty * margin_unit

    #         cgst = sgst = igst = 0
    #         for tax in self.taxes:
    #             rate = flt(tax.rate)
    #             acc = tax.account_head or ""
    #             if "CGST" in acc:
    #                 cgst += (taxable_value * rate) / 100
    #             elif "SGST" in acc:
    #                 sgst += (taxable_value * rate) / 100
    #             elif "IGST" in acc:
    #                 igst += (taxable_value * rate) / 100

    #         if hsn not in hsn_data:
    #             hsn_data[hsn] = {
    #                 "taxable_amount": 0,
    #                 "cgst": 0,
    #                 "sgst": 0,
    #                 "igst": 0
    #             }

    #         hsn_data[hsn]["taxable_amount"] += item.base_amount
    #         hsn_data[hsn]["cgst"] += cgst
    #         hsn_data[hsn]["sgst"] += sgst
    #         hsn_data[hsn]["igst"] += igst

    #     for hsn, data in hsn_data.items():
    #         row = f"<td>{hsn}</td>"
    #         row += f"<td>{fmt_money(data['taxable_amount'], currency='INR')}</td>"

    #         if self.tax_category == "In State":
    #             row += f"<td>{fmt_money(data['cgst'], currency='INR')}</td>"
    #             row += f"<td>{fmt_money(data['sgst'], currency='INR')}</td>"
    #         if self.tax_category == "Out State":
    #             row += f"<td>{fmt_money(data['igst'], currency='INR')}</td>"
    #         rows += f"<tr>{row}</tr>"

    #     header_html = "".join([f"<th>{h}</th>" for h in headers])
    #     html = f"""
    #     <table class="table table-bordered">
    #         <thead>
    #             <tr>{header_html}</tr>
    #         </thead>
    #         <tbody>
    #             {rows}
    #         </tbody>
    #     </table>
    #     """
    #     self.other_charges_calculation = html