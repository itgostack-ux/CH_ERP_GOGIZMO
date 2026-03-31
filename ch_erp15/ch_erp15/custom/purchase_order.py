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

        self.set_custom_tax_breakup()


   
   
   
   
    def set_custom_tax_breakup(self):
        try:
            headers = ["HSN/SAC", "Taxable Amount"] + [
                tax.description or tax.account_head or "Tax" for tax in self.taxes]
 
            total_taxable = sum(flt(item.qty) * flt(item.get("custom_unit_taxable_value"))
                for item in self.items)
 
            # group hsn
            hsn_map = {}
            for item in self.items:
                taxable_value = flt(item.qty) * flt(item.get("custom_unit_taxable_value"))
                amount = flt(item.amount) or flt(item.base_amount)
                if taxable_value <= 0:
                    continue
 
                hsn = item.get("gst_hsn_code") or ""
                if hsn not in hsn_map:
                    hsn_map[hsn] = {"amount": 0, "taxable_value": 0}
                hsn_map[hsn]["amount"] += amount
                hsn_map[hsn]["taxable_value"] += taxable_value
 
            rows = ""
            for hsn, data in hsn_map.items():
                proportion = data["taxable_value"] / total_taxable if total_taxable else 0
 
                cells = f"<td>{hsn}</td>"
                cells += f"<td style='text-align:right'>{fmt_money(data['amount'], currency='INR')}</td>"
                for tax in self.taxes:
                    item_tax = flt(flt(tax.tax_amount) * proportion)
                    cells += (
                        f"<td style='text-align:right'>"
                        f"({flt(tax.rate)}%) {fmt_money(item_tax, currency='INR')}"
                        f"</td>"
                    )
                rows += f"<tr>{cells}</tr>"
 
            if not rows:
                rows = f"<tr><td colspan='{len(headers)}' style='text-align:center'>No tax data</td></tr>"
 
            header_html = f"<th>{headers[0]}</th>"
            header_html += "".join(f"<th style='text-align:right'>{h}</th>" for h in headers[1:])
            self.other_charges_calculation = f"""
            <table class="table table-bordered">
                <thead><tr>{header_html}</tr></thead>
                <tbody>{rows}</tbody>
            </table>
            """
 
        except Exception:
            import frappe
            frappe.log_error(title="Tax Breakup Error", message=frappe.get_traceback())
            self.other_charges_calculation = ""