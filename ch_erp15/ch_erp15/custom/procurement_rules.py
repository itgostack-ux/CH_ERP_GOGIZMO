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

    # if purchase_type == "Marginal":
    #     frappe.throw(
    #         _(
    #             "Marginal purchase mode is not yet supported by the server-side procurement posting flow. "
    #             "Use Taxable or Unregistered until backend accounting support is implemented."
    #         )
    #     )

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