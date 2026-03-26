# import frappe
# from frappe.utils import flt, money_in_words
# from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice


# # =====================================================
# # ⭐ GET EXEMPTED VALUE FROM SERIAL
# # =====================================================

# @frappe.whitelist()
# def get_exempted_value_from_serial(serial):

#     if not serial:
#         return 0

#     result = frappe.db.sql("""
#         SELECT 
#             SUM(pri.custom_exempted_value) / NULLIF(SUM(pri.qty), 0) AS value_per_qty
#         FROM `tabSerial No` sn
#         JOIN `tabPurchase Receipt Item` pri
#             ON sn.purchase_document_no = pri.parent
#             AND sn.item_code = pri.item_code
#         WHERE sn.name = %s
#     """, (serial,), as_dict=True)

#     return flt(result[0].value_per_qty) if result else 0


# # =====================================================
# # ⭐ DELIVERY NOTE FULL RECALCULATION
# # =====================================================

# def full_recalculation(doc, method=None):

#     total_taxable = 0

#     for item in doc.items:

#         # SERIAL LIST
#         serials = []
#         if item.serial_no:
#             serials = [s.strip() for s in item.serial_no.split("\n") if s.strip()]

#         if serials:
#             item.qty = len(serials)

#         # TOTAL EXEMPTED VALUE
#         total_exempt = 0
#         for serial in serials:
#             total_exempt += get_exempted_value_from_serial(serial)

#         item.custom_exempted_value = total_exempt

#         rate = flt(item.rate)
#         qty = flt(item.qty)

#         total_value = rate * qty
#         taxable_total = total_value - total_exempt

#         if taxable_total < 0:
#             taxable_total = 0

#         # PER UNIT TAXABLE
#         item.taxable_value = taxable_total / qty if qty else 0

#         # TOTAL TAXABLE PER ROW
#         item.custom_total_taxable_value = taxable_total

#         total_taxable += taxable_total


#     # -------------------------------------------------
#     # ⭐ TAX CALCULATION (18%)
#     # -------------------------------------------------

#     tax_amount = total_taxable * 0.18


#     if doc.taxes:

#         tax_row = doc.taxes[0]

#         tax_row.charge_type = "Actual"
#         tax_row.tax_amount = tax_amount
#         tax_row.base_tax_amount = tax_amount

#         tax_row.total = tax_amount
#         tax_row.base_total = tax_amount


#     # -------------------------------------------------
#     # ⭐ UPDATE TOTALS
#     # -------------------------------------------------

#     doc.total_taxes_and_charges = tax_amount
#     doc.base_total_taxes_and_charges = tax_amount

#     doc.grand_total = doc.total + tax_amount
#     doc.base_grand_total = doc.base_total + tax_amount

#     rounded = round(doc.grand_total)

#     doc.rounded_total = rounded
#     doc.base_rounded_total = rounded

#     doc.in_words = money_in_words(rounded, doc.currency)


# # =====================================================
# # ⭐ AUTO CREATE SALES INVOICE ON DN SUBMIT
# # =====================================================

# def create_sales_invoice_on_submit(doc, method=None):

#     # Prevent duplicate invoice
#     existing = frappe.db.exists(
#         "Sales Invoice Item",
#         {"delivery_note": doc.name}
#     )

#     if existing:
#         return


#     # -------------------------------------------------
#     # ⭐ CREATE INVOICE USING ERPNext MAPPER
#     # -------------------------------------------------

#     si = make_sales_invoice(doc.name)


#     # -------------------------------------------------
#     # ⭐ COPY CUSTOM FIELDS FROM DN ITEMS
#     # -------------------------------------------------

#     dn_items = {d.name: d for d in doc.items}

#     for item in si.items:

#         dn_item = dn_items.get(item.dn_detail)
#         if not dn_item:
#             continue

#         item.serial_no = dn_item.serial_no
#         item.custom_exempted_value = dn_item.custom_exempted_value
#         item.taxable_value = dn_item.taxable_value
#         item.custom_total_taxable_value = dn_item.custom_total_taxable_value


#     # -------------------------------------------------
#     # ⭐ CALCULATE TAX AGAIN FOR INVOICE
#     # -------------------------------------------------

#     total_taxable = 0

#     for item in si.items:
#         total_taxable += flt(item.taxable_value) * flt(item.qty)

#     tax_amount = total_taxable * 0.18


#     # -------------------------------------------------
#     # ⭐ SET TAX ROW
#     # -------------------------------------------------

#     if si.taxes:
#         tax_row = si.taxes[0]
#     else:
#         tax_row = si.append("taxes", {})

#     tax_row.charge_type = "Actual"
#     tax_row.account_head = (
#         doc.taxes[0].account_head if doc.taxes else None
#     )

#     tax_row.tax_amount = tax_amount
#     tax_row.base_tax_amount = tax_amount


#     # -------------------------------------------------
#     # ⭐ FINALIZE INVOICE
#     # -------------------------------------------------

#     si.calculate_taxes_and_totals()

#     si.insert(ignore_permissions=True)
#     si.submit()

#     frappe.msgprint(f"✅ Sales Invoice {si.name} created automatically")

import frappe
from frappe.utils import flt, money_in_words
from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice


# =====================================================
# ⭐ SAFE FIELD CHECK (CORRECT)
# =====================================================

def has_field(doctype, fieldname):
    return frappe.get_meta(doctype).has_field(fieldname)


# =====================================================
# ⭐ GET EXEMPTED VALUE FROM SERIAL
# =====================================================

@frappe.whitelist()
def get_exempted_value_from_serial(serial):

    if not serial:
        return 0

    result = frappe.db.sql("""
        SELECT 
            SUM(pri.custom_exempted_value) / NULLIF(SUM(pri.qty), 0) AS value_per_qty
        FROM `tabSerial No` sn
        JOIN `tabPurchase Receipt Item` pri
            ON sn.purchase_document_no = pri.parent
            AND sn.item_code = pri.item_code
        WHERE sn.name = %s
    """, (serial,), as_dict=True)

    return flt(result[0].value_per_qty) if result else 0


# =====================================================
# ⭐ DELIVERY NOTE FULL RECALCULATION
# =====================================================

def full_recalculation(doc, method=None):

    total_taxable = 0

    for item in doc.items:

        # SERIAL LIST
        serials = []
        if item.serial_no:
            serials = [s.strip() for s in item.serial_no.split("\n") if s.strip()]

        if serials:
            item.qty = len(serials)

        # TOTAL EXEMPTED
        total_exempt = 0
        for serial in serials:
            total_exempt += get_exempted_value_from_serial(serial)

        if has_field("Delivery Note Item", "custom_exempted_value"):
            item.custom_exempted_value = total_exempt

        rate = flt(item.rate)
        qty = flt(item.qty)

        total_value = rate * qty
        taxable_total = total_value - total_exempt

        if taxable_total < 0:
            taxable_total = 0

        # PER UNIT TAXABLE
        item.taxable_value = taxable_total / qty if qty else 0

        # TOTAL TAXABLE PER ROW
        if has_field("Delivery Note Item", "custom_total_taxable_value"):
            item.custom_total_taxable_value = taxable_total

        total_taxable += taxable_total


    # -------------------------------------------------
    # ⭐ TAX CALCULATION
    # -------------------------------------------------

    tax_amount = total_taxable * 0.18

    if doc.taxes:

        tax_row = doc.taxes[0]

        tax_row.charge_type = "Actual"
        tax_row.tax_amount = tax_amount
        tax_row.base_tax_amount = tax_amount

        tax_row.total = tax_amount
        tax_row.base_total = tax_amount


    # -------------------------------------------------
    # ⭐ UPDATE TOTALS
    # -------------------------------------------------

    doc.total_taxes_and_charges = tax_amount
    doc.base_total_taxes_and_charges = tax_amount

    doc.grand_total = doc.total + tax_amount
    doc.base_grand_total = doc.base_total + tax_amount

    rounded = round(doc.grand_total)

    doc.rounded_total = rounded
    doc.base_rounded_total = rounded

    doc.in_words = money_in_words(rounded, doc.currency)


def create_sales_invoice_on_submit(doc, method=None):

    existing = frappe.db.exists(
        "Sales Invoice Item",
        {"delivery_note": doc.name}
    )

    if existing:
        return

    si = make_sales_invoice(doc.name)

    dn_items = {d.name: d for d in doc.items}

    for item in si.items:

        dn_item = dn_items.get(item.dn_detail)
        if not dn_item:
            continue

        item.serial_no = dn_item.serial_no

        if has_field("Sales Invoice Item", "custom_exempted_value"):
            item.custom_exempted_value = getattr(dn_item, "custom_exempted_value", 0)

        item.taxable_value = dn_item.taxable_value

        if has_field("Sales Invoice Item", "custom_total_taxable_value"):
            item.custom_total_taxable_value = getattr(dn_item, "custom_total_taxable_value", 0)


    # TAX CALCULATION
    total_taxable = sum(
        flt(item.taxable_value) * flt(item.qty)
        for item in si.items
    )

    tax_amount = total_taxable * 0.18

    if si.taxes:
        tax_row = si.taxes[0]
    else:
        tax_row = si.append("taxes", {})

    tax_row.charge_type = "Actual"
    tax_row.account_head = (
        doc.taxes[0].account_head if doc.taxes else None
    )
    si.outstanding_amount = si.grand_total
    si.base_outstanding_amount = si.base_grand_total

    tax_row.tax_amount = tax_amount
    tax_row.base_tax_amount = tax_amount

    si.calculate_taxes_and_totals()

    si.insert(ignore_permissions=True)
    si.submit()

    frappe.msgprint(f"✅ Sales Invoice {si.name} created automatically")