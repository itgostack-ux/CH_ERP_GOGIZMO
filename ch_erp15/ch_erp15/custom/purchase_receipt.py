import frappe
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt
from ch_erp15.ch_erp15.custom.procurement_rules import enforce_procurement_rules
from frappe.utils import flt, rounded,money_in_words, fmt_money

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

        # self.set_custom_tax_breakup()

    # def set_custom_tax_breakup(self):
    #     rows = ""

    #     if self.tax_category == "In-State":
    #         headers = ["HSN/SAC", "Taxable Amount", "CGST", "SGST"]
    #     else:
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

    #         if self.tax_category == "In-State":
    #             row += f"<td>{fmt_money(data['cgst'], currency='INR')}</td>"
    #             row += f"<td>{fmt_money(data['sgst'], currency='INR')}</td>"
    #         else:
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

    def generate_auto_serials(self):
        for item in self.items:

            if getattr(item, "custom_imei", "No") != "No":
                continue

            if item.serial_no and item.serial_no.strip():
                continue

            prefix = (getattr(item, "serial_no_series", "") or item.item_code.upper()).split("#")[0]
            prefix = prefix.replace(".", "")

            serials = frappe.db.get_all(
                "Serial No",
                filters={"item_code": item.item_code},
                fields=["name", "status"]
            )

            last_number = 0
            reusable = []

            for s in serials:
                match = re.match(rf"^{re.escape(prefix)}(\d+)$", s.name)
                if match:
                    num = int(match.group(1))
                    last_number = max(last_number, num)

                    if s.status == "Delivered":
                        reusable.append((s.name, num))

            reusable.sort(key=lambda x: x[1])

            final_serials = []
            qty = int(item.qty)

            for sn, num in reusable:
                if len(final_serials) >= qty:
                    break
                final_serials.append(sn)

            remaining = qty - len(final_serials)

            for i in range(remaining):
                last_number += 1
                final_serials.append(f"{prefix}{str(last_number).zfill(5)}")

            item.serial_no = "\n".join(final_serials)
            