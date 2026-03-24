import frappe
from frappe import _
from frappe.utils import cint, cstr, flt


ALLOWED_PURCHASE_TYPES = {"Taxable", "Unregistered", "Marginal"}


def enforce_procurement_rules(doc):
    purchase_type = cstr(doc.get("custom_purchase_type")).strip()

    if purchase_type and purchase_type not in ALLOWED_PURCHASE_TYPES:
        frappe.throw(
            _("Invalid purchase type {0} on {1}.").format(
                frappe.bold(purchase_type), frappe.bold(doc.doctype)
            )
        )

    if purchase_type == "Marginal":
        _apply_marginal_scheme(doc)

    if purchase_type == "Unregistered":
        _apply_zero_tax(doc)

    if doc.doctype == "Purchase Receipt":
        _validate_purchase_receipt_imeis(doc)


def _apply_zero_tax(doc):
    for tax in doc.get("taxes") or []:
        for fieldname in (
            "rate",
            "tax_amount",
            "base_tax_amount",
            "total",
            "base_total",
            "amount",
            "base_amount",
        ):
            if hasattr(tax, fieldname):
                setattr(tax, fieldname, 0)

    for fieldname in (
        "taxes_and_charges_added",
        "base_taxes_and_charges_added",
        "total_taxes_and_charges",
        "base_total_taxes_and_charges",
        "custom_margin_taxable",
        "custom_margin_gst",
    ):
        if hasattr(doc, fieldname):
            setattr(doc, fieldname, 0)


def _apply_marginal_scheme(doc):
    """Mirror the JS apply_marginal_scheme logic server-side.

    Tax is calculated only on the marginal (taxable) value per item
    (custom_unit_taxable_value × qty), not on the full invoice amount.
    The remainder is recorded as the exempted value.
    """
    total_margin_taxable = 0.0
    total_gst = 0.0
    total_exempted = 0.0

    # --- Item level: compute amounts and margin taxable ---
    for item in doc.get("items") or []:
        qty = flt(item.get("qty"))
        rate = flt(item.get("rate"))
        margin_unit = flt(item.get("custom_unit_taxable_value"))

        if qty <= 0 or rate <= 0 or margin_unit <= 0:
            continue

        item_amount = qty * rate
        margin_taxable = qty * margin_unit

        item.amount = item_amount
        item.base_amount = item_amount
        item.taxable_value = margin_taxable

        total_margin_taxable += margin_taxable

    # --- Tax level: apply tax only on total margin taxable ---
    for tax in doc.get("taxes") or []:
        tax.tax_amount = 0
        tax.base_tax_amount = 0
        tax.total = 0
        tax.base_total = 0

        if cstr(tax.get("charge_type")) == "On Net Total" and total_margin_taxable > 0:
            tax_amount = (total_margin_taxable * flt(tax.get("rate"))) / 100
            tax.tax_amount = tax_amount
            tax.base_tax_amount = tax_amount
            tax.total = tax_amount
            tax.base_total = tax_amount
            total_gst += tax_amount

    # --- Item level: compute exempted value ---
    for item in doc.get("items") or []:
        qty = flt(item.get("qty"))
        margin_unit = flt(item.get("custom_unit_taxable_value"))
        item_amount = flt(item.get("amount"))

        if qty <= 0 or item_amount <= 0:
            continue

        margin_taxable = qty * margin_unit
        item_gst = 0.0
        if total_margin_taxable > 0:
            item_gst = (margin_taxable / total_margin_taxable) * total_gst

        exempted_value = item_amount - margin_taxable - item_gst
        if exempted_value < 0:
            exempted_value = 0.0

        item.custom_exempted_value = exempted_value
        total_exempted += exempted_value

    # --- Document totals ---
    doc.net_total = total_margin_taxable
    doc.base_net_total = total_margin_taxable

    for fieldname in (
        "taxes_and_charges_added",
        "base_taxes_and_charges_added",
        "total_taxes_and_charges",
        "base_total_taxes_and_charges",
    ):
        if hasattr(doc, fieldname):
            setattr(doc, fieldname, total_gst)

    grand_total = total_margin_taxable + total_gst + total_exempted
    doc.grand_total = grand_total
    doc.base_grand_total = grand_total
    doc.rounded_total = flt(round(grand_total))


def _validate_purchase_receipt_imeis(doc):
    tracked_rows = {}
    for item in doc.get("items") or []:
        if not cint(item.get("custom_imei_track")):
            continue

        qty = flt(item.qty)
        if qty <= 0:
            frappe.throw(_("Row #{0}: Qty must be greater than zero for IMEI-tracked items.").format(item.idx))
        if qty != cint(qty):
            frappe.throw(_("Row #{0}: IMEI-tracked items must use whole-number quantities.").format(item.idx))

        tracked_rows[item.name] = {"qty": cint(qty), "item_code": item.item_code}

    imei_rows = doc.get("custom_track") or []
    if not tracked_rows and not imei_rows:
        return

    seen_imeis = set()
    row_counts = {item_name: 0 for item_name in tracked_rows}

    for row in imei_rows:
        imei_number = cstr(row.get("imei_number")).strip()
        if not imei_number:
            frappe.throw(_("All IMEI tracking rows must include an IMEI number."))
        if imei_number in seen_imeis:
            frappe.throw(_("Duplicate IMEI number found: {0}").format(frappe.bold(imei_number)))

        purchase_receipt_item = row.get("purchase_receipt_item")
        if purchase_receipt_item not in tracked_rows:
            frappe.throw(
                _("IMEI {0} is linked to a Purchase Receipt row that is not marked for IMEI tracking.").format(
                    frappe.bold(imei_number)
                )
            )

        seen_imeis.add(imei_number)
        row_counts[purchase_receipt_item] += 1

    for item_name, meta in tracked_rows.items():
        if row_counts.get(item_name, 0) != meta["qty"]:
            frappe.throw(
                _("Item {0} requires {1} IMEI entries, but found {2}.").format(
                    frappe.bold(meta["item_code"]), meta["qty"], row_counts.get(item_name, 0)
                )
            )