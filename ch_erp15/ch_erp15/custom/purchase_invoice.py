from frappe.utils import flt, rounded, money_in_words, fmt_money
from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import PurchaseInvoice


class CustomPurchaseInvoice(PurchaseInvoice):
    def validate(self):
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
                tax.tax_amount = flt(
                    (total_margin_taxable * flt(tax.rate)) / 100,
                    tax.precision("tax_amount"),
                )
                total_gst += tax.tax_amount

            tax.base_tax_amount = tax.tax_amount
            tax.tax_amount_after_discount_amount = tax.tax_amount
            tax.base_tax_amount_after_discount_amount = tax.tax_amount
            tax.base_total = tax.tax_amount
            tax.total = tax.tax_amount

        net_total = total_amount - total_gst

        self.total = total_amount
        self.base_total = total_amount
        self.net_total = net_total
        self.base_net_total = net_total

        self.total_taxes_and_charges = total_gst
        self.base_total_taxes_and_charges = total_gst
        self.taxes_and_charges_added = total_gst

        self.grand_total = total_amount
        self.base_grand_total = total_amount
        self.rounded_total = total_amount
        self.base_rounded_total = total_amount
        self.outstanding_amount = total_amount

        self.rounding_adjustment = 0
        self.base_rounding_adjustment = 0

        self.in_words = money_in_words(self.rounded_total, self.currency)
        self.base_in_words = money_in_words(self.rounded_total, self.currency)

        self.set_custom_tax_breakup()

    def get_gl_entries(self, warehouse_account=None):
        """Build custom GL entries for Marginal purchase type"""

        if self.custom_purchase_type != "Marginal":
            return super().get_gl_entries(warehouse_account)

        gl_entries = []

        total_margin_taxable = sum(
            flt(item.qty) * flt(item.custom_unit_taxable_value)
            for item in self.items
        )

        grand_total = flt(self.grand_total)

        total_tax = 0
        tax_entries = []
        for tax in self.taxes:
            tax_amt = 0
            if tax.charge_type == "On Net Total" and flt(tax.rate) > 0:
                tax_amt = flt(
                    (total_margin_taxable * flt(tax.rate)) / 100,
                    tax.precision("tax_amount"),
                )
            total_tax += tax_amt
            if tax_amt:
                tax_entries.append({
                    "account": tax.account_head,
                    "amount": tax_amt,
                    "cost_center": tax.cost_center or self.cost_center,
                })

        expense_total = flt(grand_total - total_tax)

        # Against accounts string
        against_accounts = list(set(
            [item.expense_account for item in self.items]
            + [t["account"] for t in tax_entries]
        ))

        gl_entries.append(
            self.get_gl_dict(
                {
                    "account": self.credit_to,
                    "party_type": "Supplier",
                    "party": self.supplier,
                    "against": ", ".join(against_accounts),
                    "credit": grand_total,
                    "credit_in_account_currency": grand_total,
                    "against_voucher": (
                        self.return_against
                        if self.get("is_return") and self.return_against
                        else self.name
                    ),
                    "against_voucher_type": self.doctype,
                    "cost_center": self.cost_center,
                    "project": self.project,
                },
                self.party_account_currency,
                item=self,
            )
        )

        total_full = sum(flt(item.qty) * flt(item.rate) for item in self.items)
        running_debit = 0

        for idx, item in enumerate(self.items):
            item_full = flt(item.qty) * flt(item.rate)

            # Last item absorbs any rounding difference
            if idx == len(self.items) - 1:
                item_debit = flt(expense_total - running_debit)
            else:
                proportion = item_full / total_full if total_full else 0
                item_debit = flt(
                    expense_total * proportion,
                    item.precision("base_net_amount"),
                )

            running_debit += item_debit

            gl_entries.append(
                self.get_gl_dict(
                    {
                        "account": item.expense_account,
                        "against": self.credit_to,
                        "debit": item_debit,
                        "debit_in_account_currency": item_debit,
                        "cost_center": item.cost_center or self.cost_center,
                        "project": item.project or self.project,
                    },
                    item=item,
                )
            )

        for t in tax_entries:
            gl_entries.append(
                self.get_gl_dict({
                    "account": t["account"],
                    "against": self.credit_to,
                    "debit": t["amount"],
                    "debit_in_account_currency": t["amount"],
                    "cost_center": t["cost_center"],
                })
            )

        return gl_entries


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