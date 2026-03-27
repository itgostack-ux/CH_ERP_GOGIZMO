from frappe.utils import flt, rounded, money_in_words
from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import PurchaseInvoice
from ch_erp15.ch_erp15.custom.procurement_rules import enforce_procurement_rules


class CustomPurchaseInvoice(PurchaseInvoice):
    def validate(self):
        # enforce_procurement_rules(self)
        super().validate()

        if self.custom_purchase_type != "Marginal":
            return

        total_margin_taxable = 0
        total_gst = 0
        total_amount = 0
        for item in self.items:
            qty = flt(item.qty)
            rate = flt(item.rate)
            margin_unit = flt(item.custom_unit_taxable_value)

            item_amount = qty * rate
            margin_taxable = qty * margin_unit

            item.amount = item_amount
            item.base_amount = item_amount

            total_amount += item_amount
            total_margin_taxable += margin_taxable

        for tax in self.taxes:
            tax.included_in_print_rate = 1
            tax.tax_amount = 0

            if tax.charge_type == "On Net Total":
                tax.tax_amount = (total_margin_taxable * flt(tax.rate)) / 100
                total_gst += tax.tax_amount
            tax.base_total = tax.tax_amount
            tax.total = tax.tax_amount
            tax.base_tax_amount = tax.tax_amount

        net_total = total_amount - total_gst

        self.total = total_amount
        self.net_total = total_amount - total_gst
        self.base_net_total = net_total

        self.total_taxes_and_charges = total_gst
        self.base_total_taxes_and_charges = total_gst
        self.taxes_and_charges_added =total_gst

        self.grand_total = total_amount
        self.base_grand_total = total_amount

        self.rounded_total = total_amount
        self.outstanding_amount = total_amount
        self.in_words = money_in_words(self.rounded_total, self.currency)