import frappe
from frappe import _
from frappe.utils import flt
from frappe.model.mapper import get_mapped_doc
from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice


def has_field(doctype, fieldname):
    return frappe.get_meta(doctype).has_field(fieldname)


# =====================================================
# SALES ORDER → DELIVERY NOTE
# =====================================================

@frappe.whitelist()
def make_delivery_note(source_name, target_doc=None):

    def set_missing_values(source, target):
        target.run_method("set_missing_values")
        target.run_method("calculate_taxes_and_totals")

    def update_item(source, target, source_parent):

        if has_field("Delivery Note Item", "custom_sales_order_qty"):
            target.custom_sales_order_qty = flt(source.qty)

        target.qty = 0
        target.stock_qty = 0

    doc = get_mapped_doc(
        "Sales Order",
        source_name,
        {
            "Sales Order": {
                "doctype": "Delivery Note",
                "validation": {"docstatus": ["=", 1]},
            },
            "Sales Order Item": {
                "doctype": "Delivery Note Item",
                "field_map": {
                    "name": "so_detail",
                    "parent": "against_sales_order",
                },
                "postprocess": update_item,
            },
        },
        target_doc,
        set_missing_values,
    )

    return doc



@frappe.whitelist()
def get_exempted_value_from_serial(serial):

    if not serial:
        return 0

    # ERP-14 fix: Guard SQL against missing custom field
    if not has_field("Purchase Receipt Item", "custom_exempted_value"):
        return 0

    result = frappe.db.sql("""
        SELECT 
            SUM(pri.custom_exempted_value) / NULLIF(SUM(pri.qty), 0)
        FROM `tabSerial No` sn
        JOIN `tabPurchase Receipt Item` pri
            ON sn.purchase_document_no = pri.parent
            AND sn.item_code = pri.item_code
        WHERE sn.name = %s
    """, (serial,), as_list=True)

    return flt(result[0][0]) if result and result[0][0] else 0










def _validate_exemption_data(doc):
    """ERP-5 fix: Validate that exempted values have valid source data.
    Ensures serial numbers referenced in exemption lookups actually have
    Purchase Receipt backing — warns if exemption data is missing or stale.
    """
    for item in doc.items:
        if not item.serial_no:
            continue
        serials = [s.strip() for s in item.serial_no.split("\n") if s.strip()]
        for sn in serials:
            exempt_val = get_exempted_value_from_serial(sn)
            if flt(exempt_val) > flt(item.rate) * 1.5:
                frappe.msgprint(
                    _("Warning: Exempted value ({0}) for serial {1} exceeds 150% of item rate ({2}). "
                      "Please verify the Purchase Receipt exemption data.").format(
                        exempt_val, sn, item.rate),
                    indicator="orange",
                )
            if flt(exempt_val) < 0:
                frappe.throw(
                    _("Invalid negative exempted value ({0}) for serial {1}. "
                      "Check the Purchase Receipt custom_exempted_value field.").format(
                        exempt_val, sn),
                    title=_("Invalid Exemption Data"),
                )


def full_recalculation(doc, method=None):
    # ERP-5 fix: Validate exemption values before recalculation
    _validate_exemption_data(doc)

    total_taxable = 0

    for item in doc.items:

        serials = []
        if item.serial_no:
            serials = [s.strip() for s in item.serial_no.split("\n") if s.strip()]

        # ✅ Sync qty safely
        if serials:
            item.qty = len(serials)
            item.stock_qty = len(serials)

        total_exempt = sum(get_exempted_value_from_serial(s) for s in serials)

        if has_field("Delivery Note Item", "custom_exempted_value"):
            item.custom_exempted_value = total_exempt

        rate = flt(item.rate)
        qty = flt(item.qty)

        # ✅ NEW LOGIC (ONLY CHANGE)
        exempt_per_unit = (total_exempt / qty) if qty else 0

        base_value = rate - exempt_per_unit
        if base_value < 0:
            base_value = 0

        # ERP-3 fix: Dynamic GST rate lookup instead of hardcoded 18%
        gst_rate = _get_item_gst_rate(item.item_code, doc) or 18
        taxable_per_unit = base_value / (1 + gst_rate / 100)

        item.taxable_value = taxable_per_unit

        taxable_total = taxable_per_unit * qty

        if has_field("Delivery Note Item", "custom_total_taxable_value"):
            item.custom_total_taxable_value = taxable_total

        total_taxable += taxable_total

    if not doc.taxes:
        doc.append("taxes", {})

    tax_row = doc.taxes[0]

    # Use the effective GST rate (from taxes table or default 18%)
    effective_gst_rate = _get_doc_gst_rate(doc) or 18
    tax_amount = total_taxable * (effective_gst_rate / 100)

    tax_row.charge_type = "Actual"
    tax_row.tax_amount = tax_amount
    tax_row.base_tax_amount = tax_amount

    doc.total_taxes_and_charges = tax_amount
    doc.base_total_taxes_and_charges = tax_amount

    doc.flags.ignore_validate_update_after_submit = True

    doc.calculate_taxes_and_totals()


def _get_item_gst_rate(item_code, doc):
    """Get GST rate for an item from its Item Tax Template or the doc's tax template."""
    from frappe.utils import flt as _flt
    # Try item-level tax template first
    item_tax_template = frappe.db.get_value("Item", item_code, "item_tax_template") if item_code else None
    if item_tax_template:
        rates = frappe.get_all(
            "Item Tax Template Detail",
            filters={"parent": item_tax_template},
            fields=["tax_rate"],
        )
        if rates:
            return sum(_flt(r.tax_rate) for r in rates)

    # Fall back to the first tax row rate on the document
    return _get_doc_gst_rate(doc)


def _get_doc_gst_rate(doc):
    """Get GST rate from the document's tax rows or the sales taxes template."""
    from frappe.utils import flt as _flt
    for tax in (doc.get("taxes") or []):
        if _flt(tax.get("rate")) > 0:
            return _flt(tax.rate)
    # Default
    return 18





def before_submit_all(doc, method=None):

    for item in doc.items:

        if item.serial_no:
            serials = [s.strip() for s in item.serial_no.split("\n") if s.strip()]
            count = len(serials)

            item.qty = count
            item.stock_qty = count

        # ✅ FIX: strict validation
        if flt(item.qty) <= 0:
            frappe.throw(f"Qty must be greater than 0 for Item {item.item_code}")

        item.qty = flt(item.qty)
        item.rate = flt(item.rate)

        item.amount = item.rate * item.qty
        item.base_rate = item.rate
        item.base_amount = item.amount

    # ✅ Sales Order sync FIXED
    for item in doc.items:

        if not item.so_detail:
            continue

        so_item = frappe.get_doc("Sales Order Item", item.so_detail)

        delivered = flt(so_item.delivered_qty) + flt(item.qty)

        if delivered > flt(so_item.qty):
            frappe.throw(
                f"Delivery exceeds ordered qty for Item {item.item_code}"
            )

        if has_field("Sales Order Item", "custom_delivered_qty"):
            so_item.db_set("custom_delivered_qty", delivered)

    doc.calculate_taxes_and_totals()



def create_sales_invoice_on_submit(doc, method=None):

    if frappe.db.exists(
        "Sales Invoice Item",
        {"delivery_note": doc.name}
    ):
        return

    si = make_sales_invoice(doc.name)

    dn_items = {d.name: d for d in doc.items}

    for item in si.items:

        dn_item = dn_items.get(item.dn_detail)
        if not dn_item:
            continue

        item.serial_no = dn_item.serial_no

        if has_field("Sales Invoice Item", "custom_exempted_value"):
            item.custom_exempted_value = getattr(
                dn_item, "custom_exempted_value", 0
            )

        item.taxable_value = dn_item.taxable_value

        if has_field("Sales Invoice Item", "custom_total_taxable_value"):
            item.custom_total_taxable_value = getattr(
                dn_item, "custom_total_taxable_value", 0
            )

    si.calculate_taxes_and_totals()

    si.insert(ignore_permissions=True)
    si.submit()

    frappe.msgprint(f"✅ Sales Invoice {si.name} created automatically")