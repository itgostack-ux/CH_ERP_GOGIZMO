import frappe
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry
from erpnext.stock.stock_ledger import make_sl_entries
from frappe.utils import get_datetime, now_datetime, flt

class CustomStockEntry(StockEntry):

    def update_stock_ledger(self):
        # Transit workflow entries handle SLEs manually via move_stock
        if self.custom_status:
            return
        super().update_stock_ledger()

    def validate(self):
        super().validate()

        if self.stock_entry_type == "Material Transfer":
            self.calculate_totals()
        else:
            return
        for item in self.items:
            if not item.custom_quantity:
                item.custom_quantity = item.qty
            if item.qty < 0 or (item.custom_pending_qty or 0) < 0:
                frappe.throw("Negative Qty not allowed")
            if self.custom_status == "Pending With Goods":
                if not item.s_warehouse:
                    frappe.throw(f"Source Warehouse missing for {item.item_code}")
                if not item.t_warehouse:
                    frappe.throw(f"Target Warehouse missing for {item.item_code}")
            if self.custom_status in ["Transferred", "Partially Transferred"]:
                if not item.t_warehouse:
                    frappe.throw(f"Target Warehouse missing for {item.item_code}")
            if self.custom_status == "Receive At Transit" and not item.custom_receive_qty:
                frappe.throw(f"{item.item_code}: Receive qty cannot be 0")

            if self.custom_status == "Transferred" and  not item.custom_final_received_qty:
                frappe.throw(f"{item.item_code}: Transfer qty cannot be 0")

            if (item.custom_receive_qty or 0) > (item.custom_quantity or 0):
                frappe.throw(f"{item.item_code}: Receive qty cannot exceed original qty ({item.custom_quantity}).")
            if (item.custom_final_received_qty or 0) > (item.custom_quantity or 0):
                frappe.throw(f"{item.item_code}: Final receive qty cannot exceed original qty ({item.custom_quantity}).")
            if (item.custom_final_received_qty or 0) > (item.custom_receive_qty or 0):
                frappe.throw(f"{item.item_code}: Final receive qty cannot exceed received qty ({item.custom_receive_qty}).")
    
    def calculate_totals(self):
        if self.stock_entry_type != "Material Transfer":
            return
        total_outgoing = 0
        total_incoming = 0
        for item in self.items:
            qty = (item.custom_final_received_qty or item.custom_receive_qty or item.custom_pending_qty)
            rate = item.basic_rate
            qty = qty or 0
            rate = rate or 0 
            amount = qty * rate

            if item.s_warehouse:
                total_outgoing += amount
            if item.t_warehouse:
                total_incoming += amount
        self.total_outgoing_value = total_outgoing
        self.total_incoming_value = total_incoming
        self.total_amount = total_outgoing
        self.base_total = total_outgoing
        self.grand_total = total_outgoing
          
@frappe.whitelist()
def set_custom_status(StockEntry, status):
    doc = frappe.get_doc("Stock Entry", StockEntry)
    if doc.stock_entry_type != "Material Transfer":
        return
    frappe.db.sql("SELECT name FROM `tabStock Entry` WHERE name=%s FOR UPDATE",doc.name)
    doc.custom_status = status
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    return {"custom_status": status}

@frappe.whitelist()
def set_pending_qty(StockEntry):
    doc = frappe.get_doc("Stock Entry", StockEntry)
    if doc.stock_entry_type != "Material Transfer":
        return
    frappe.db.sql("SELECT name FROM `tabStock Entry` WHERE name=%s FOR UPDATE",doc.name)
    if doc.custom_status == "Pending With Goods":
        frappe.throw("Stock already moved to Transit Warehouse")
    for item in doc.items:
        item.custom_pending_qty = item.custom_quantity
    insert_transit_entry(doc)    
    doc.custom_status = "Pending With Goods"
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    return {"status": doc.custom_status}

@frappe.whitelist()
def received_qty(StockEntry, barcode):
    doc = frappe.get_doc("Stock Entry", StockEntry)
    if doc.stock_entry_type != "Material Transfer":
        return
    frappe.db.sql("SELECT name FROM `tabStock Entry` WHERE name=%s FOR UPDATE",doc.name)
    
    if doc.custom_status != "Pending With Goods":               
        frappe.throw("Scanning allowed only in Pending With Goods")
    item_code = frappe.db.get_value("Item Barcode", {"barcode": barcode}, "parent")
    if not item_code:
        frappe.throw(f"Barcode not found: {barcode}")
    found = False
    for item in doc.items:
        if item.item_code == item_code:
            found = True
            if item.custom_receive_qty >= item.custom_quantity:
                frappe.throw(f"All Quantity scanned from Pending Quantity {item.item_code}")
            item.custom_receive_qty += 1
            # item.custom_pending_qty = item.custom_quantity - item.custom_receive_qty #temp hide
            break
    if not found:
        frappe.throw(f"{item_code} not in this Stock Entry")
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    doc.reload()
    return {"items": [i.as_dict() for i in doc.items]}

@frappe.whitelist()
def final_received(StockEntry, barcode):
    doc = frappe.get_doc("Stock Entry", StockEntry)
    if doc.stock_entry_type != "Material Transfer":
        return
    frappe.db.sql("SELECT name FROM `tabStock Entry` WHERE name=%s FOR UPDATE",doc.name)
    if doc.custom_status != "Receive At Transit":
        frappe.throw("Transfer allowed only in 'Receive At Transit' status.")
    item_code = frappe.db.get_value("Item Barcode", {"barcode": barcode}, "parent")
    if not item_code:
        frappe.throw(f"No item found for barcode {barcode}")

    found = False
    for item in doc.items:
        if item.custom_final_received_qty > item.qty:
            frappe.throw("Received qty cannot exceed original qty")
        if item.item_code == item_code:
            found = True
            if item.custom_final_received_qty >= item.custom_receive_qty:
                frappe.throw(f"All Quantity Received from Transit for {item.item_code}")
            item.custom_final_received_qty += 1
            frappe.msgprint(f"{item.item_code} | Transferred: {item.custom_final_received_qty} | Pending: {item.custom_pending_qty}")
    if not found:
        frappe.throw(f"{item_code} not in this Stock Entry")
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    doc.reload()
    return {"items": [i.as_dict() for i in doc.items]}

@frappe.whitelist()
def revert_goods(StockEntry):
    doc = frappe.get_doc("Stock Entry", StockEntry)
    if doc.stock_entry_type != "Material Transfer":
        return
    revert_transit_entry(doc)
    doc.custom_status = "Draft"
    for item in doc.items:
        item.custom_pending_qty =0
        item.custom_receive_qty= 0
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    return "Reverted Successfully"

@frappe.whitelist()
def transfer_custom_status(StockEntry):
    doc = frappe.get_doc("Stock Entry", StockEntry)
    if doc.stock_entry_type != "Material Transfer":
        return
    if doc.custom_status != "Receive At Transit":
        frappe.throw("Not allowed in this status")
    if not any(i.custom_final_received_qty for i in doc.items):
        frappe.throw("No quantity received from transit")
    transit_target_entry(doc)
    fully_done = all((i.custom_final_received_qty ) == (i.custom_quantity) for i in doc.items)
    if fully_done:
        doc.custom_status = "Transferred"
    else:
        doc.custom_status = "Partially Transferred"
        if doc.custom_status == "Partially Transferred":
            for item in doc.items:
                remaining = item.custom_quantity - item.custom_final_received_qty
                item.custom_quantity = remaining
                item.custom_pending_qty= remaining
                item.custom_receive_qty =0
                item.custom_final_received_qty= 0
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    if doc.docstatus == 0:
        doc.submit()
    return doc.custom_status

@frappe.whitelist()
def goods_to_pending(StockEntry):
    doc = frappe.get_doc("Stock Entry", StockEntry)
    if doc.stock_entry_type != "Material Transfer":
        return
    if doc.custom_status!= "Partially Transferred":
        frappe.throw("Not a partially transferred document")

    doc.db_set("docstatus", 0)
    doc.custom_status = "Pending With Goods"

    for item in doc.items:
        remaining = item.custom_quantity - item.custom_final_received_qty
        if remaining > 0:            
            item.custom_quantity = remaining
            item.custom_pending_qty= remaining
            item.custom_receive_qty =0
            item.custom_final_received_qty= 0
    doc.save(ignore_permissions=True)
    return "Flow restarted"

# @frappe.whitelist()
# def force_closed(StockEntry):
#     doc = frappe.get_doc("Stock Entry", StockEntry)
#     if doc.stock_entry_type != "Material Transfer":
#         return
#     if doc.custom_status!= "Partially Transferred":
#         frappe.throw("Not a partially transferred document")
#     doc.db_set("docstatus", 0)       
#     doc.custom_status = "Force Closed"
#     transit_source(doc)
#     doc.save()
#     doc.submit()
#     return "Stock Returned to Source Warehouse and Force Closed"

def _get_transit_warehouse(company):
    abbr = frappe.get_cached_value("Company", company, "abbr")
    return f"Goods In Transit - {abbr}"

def _get_serial_nos_from_item(item):
    """Extract serial numbers from a Stock Entry Detail row."""
    from erpnext.stock.doctype.serial_no.serial_no import get_serial_nos
    if item.serial_no:
        return get_serial_nos(item.serial_no)
    if item.serial_and_batch_bundle:
        entries = frappe.get_all(
            "Serial and Batch Entry",
            filters={"parent": item.serial_and_batch_bundle},
            pluck="serial_no",
        )
        return [sn for sn in entries if sn]
    return []

def _update_serial_warehouse(serial_nos, warehouse, company):
    """Update Serial No warehouse and status after transit stock movement."""
    if not serial_nos:
        return
    sn_table = frappe.qb.DocType("Serial No")
    (
        frappe.qb.update(sn_table)
        .set(sn_table.warehouse, warehouse)
        .set(sn_table.status, "Active" if warehouse else "Inactive")
        .set(sn_table.company, company)
        .where(sn_table.name.isin(serial_nos))
    ).run()

def move_stock(doc, item, qty, from_wh, to_wh):
    if doc.stock_entry_type != "Material Transfer":
        return
    if qty <= 0 or from_wh == to_wh:
        return
    posting_datetime = get_datetime(f"{doc.posting_date} {doc.posting_time}")
    sle = []
    sle.append(frappe._dict({
        "item_code": item.item_code,
        "warehouse": from_wh,
        "actual_qty": -qty,
        "posting_date": doc.posting_date,
        "posting_time": doc.posting_time,
        "posting_datetime": posting_datetime,
        "creation": posting_datetime,
        "modified": posting_datetime,
        "voucher_type": "Stock Entry",
        "voucher_no": doc.name,
        "voucher_detail_no": item.name,
        "dependant_sle_voucher_detail_no": item.name,
        "company": doc.company,
        "stock_uom": item.uom,
        "is_cancelled": 0,
        "recalculate_rate": 0,
    }))
    sle.append(frappe._dict({
        "item_code": item.item_code,
        "warehouse": to_wh,
        "actual_qty": qty,
        "posting_date": doc.posting_date,
        "posting_time": doc.posting_time,
        "posting_datetime": posting_datetime,
        "creation": posting_datetime,
        "modified": posting_datetime,
        "voucher_type": "Stock Entry",
        "voucher_no": doc.name,
        "voucher_detail_no": item.name,
        "company": doc.company,
        "stock_uom": item.uom,
        "is_cancelled": 0,
        "recalculate_rate": 1,
    }))
    make_sl_entries(sle, allow_negative_stock=False)

    # Update Serial No warehouse for serialized items
    if frappe.get_cached_value("Item", item.item_code, "has_serial_no"):
        serial_nos = _get_serial_nos_from_item(item)
        if serial_nos:
            _update_serial_warehouse(serial_nos, to_wh, doc.company)

def insert_transit_entry(doc):
    for item in doc.items:
        if not item.custom_quantity:
            continue
        move_stock(doc, item, item.custom_quantity, item.s_warehouse, _get_transit_warehouse(doc.company))

def revert_transit_entry(doc):
    for item in doc.items:
        if not item.custom_quantity:
            continue
        move_stock(doc, item, item.custom_quantity, _get_transit_warehouse(doc.company), item.s_warehouse)

def transit_target_entry(doc):

    for item in doc.items:
        final_qty = item.custom_final_received_qty
        if final_qty > 0:
            move_stock(doc,item,final_qty,_get_transit_warehouse(doc.company),item.t_warehouse)

# ERP-2 fix: Uncommented transit_source function
def transit_source(doc):
    for item in doc.items:
        if not item.custom_pending_qty:
            continue
        move_stock(doc, item, item.custom_pending_qty, _get_transit_warehouse(doc.company), item.s_warehouse)


# ─── Logistics Flow APIs ────────────────────────────────────────────────────

@frappe.whitelist()
def logistics_pickup(stock_entry, logistics_person, pickup_photo=None):
    """Logistics team picks up goods from warehouse. Status: Ready For Pickup → In Transit."""
    doc = frappe.get_doc("Stock Entry", stock_entry)
    if doc.stock_entry_type != "Material Transfer":
        frappe.throw("Not a Material Transfer")

    allowed = ("Pending With Goods", "Ready For Pickup")
    if doc.custom_status not in allowed:
        frappe.throw(f"Pickup only allowed when status is {' or '.join(allowed)}, current: {doc.custom_status}")

    frappe.db.sql("SELECT name FROM `tabStock Entry` WHERE name=%s FOR UPDATE", doc.name)
    doc.custom_status = "In Transit"
    doc.custom_logistics_status = "In Transit"
    doc.custom_logistics_person = logistics_person
    doc.custom_pickup_datetime = now_datetime()
    if pickup_photo:
        doc.custom_pickup_photo = pickup_photo
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()

    # Auto-generate e-way bill if India Compliance is installed & enabled
    _auto_generate_ewaybill(doc)

    return {"status": doc.custom_status, "logistics_status": doc.custom_logistics_status}


@frappe.whitelist()
def logistics_deliver(stock_entry, delivery_photo=None):
    """Logistics delivers goods to store. Status: In Transit → Ready For Receive."""
    doc = frappe.get_doc("Stock Entry", stock_entry)
    if doc.stock_entry_type != "Material Transfer":
        frappe.throw("Not a Material Transfer")
    if doc.custom_logistics_status != "In Transit":
        frappe.throw(f"Delivery only allowed when logistics status is 'In Transit', current: {doc.custom_logistics_status}")

    frappe.db.sql("SELECT name FROM `tabStock Entry` WHERE name=%s FOR UPDATE", doc.name)
    doc.custom_status = "Ready For Receive"
    doc.custom_logistics_status = "Delivered"
    doc.custom_delivery_datetime = now_datetime()
    if delivery_photo:
        doc.custom_delivery_photo = delivery_photo
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    return {"status": doc.custom_status, "logistics_status": doc.custom_logistics_status}


@frappe.whitelist()
def logistics_revert_request(stock_entry, reason):
    """Request revert while goods are in movement. Blocks store from receiving."""
    doc = frappe.get_doc("Stock Entry", stock_entry)
    if doc.stock_entry_type != "Material Transfer":
        frappe.throw("Not a Material Transfer")
    if doc.custom_logistics_status not in ("In Transit", "Delivered"):
        frappe.throw("Revert only allowed when goods are in movement")
    if not reason:
        frappe.throw("Revert reason is required")

    frappe.db.sql("SELECT name FROM `tabStock Entry` WHERE name=%s FOR UPDATE", doc.name)
    doc.custom_logistics_status = "Revert Requested"
    doc.custom_revert_reason = reason
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    return {"logistics_status": doc.custom_logistics_status}


@frappe.whitelist()
def logistics_revert_complete(stock_entry):
    """Complete revert: move goods back from transit to source warehouse."""
    doc = frappe.get_doc("Stock Entry", stock_entry)
    if doc.stock_entry_type != "Material Transfer":
        frappe.throw("Not a Material Transfer")
    if doc.custom_logistics_status != "Revert Requested":
        frappe.throw("Revert completion only allowed after revert is requested")

    frappe.db.sql("SELECT name FROM `tabStock Entry` WHERE name=%s FOR UPDATE", doc.name)
    revert_transit_entry(doc)
    doc.custom_status = "Draft"
    doc.custom_logistics_status = "Reverted"
    for item in doc.items:
        item.custom_pending_qty = 0
        item.custom_receive_qty = 0
        item.custom_final_received_qty = 0
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    return {"status": doc.custom_status, "logistics_status": doc.custom_logistics_status}


@frappe.whitelist()
def get_logistics_entries(status_filter=None):
    """List Stock Entries relevant to logistics team."""
    filters = {
        "stock_entry_type": "Material Transfer",
        "docstatus": ["<", 2],
        "custom_status": ["in", [
            "Pending With Goods", "Ready For Pickup", "In Transit",
            "Ready For Receive", "Receive At Transit",
        ]],
    }
    if status_filter:
        filters["custom_logistics_status"] = status_filter

    entries = frappe.get_all(
        "Stock Entry",
        filters=filters,
        fields=[
            "name", "posting_date", "custom_status", "custom_logistics_status",
            "custom_logistics_person", "custom_pickup_datetime",
            "custom_delivery_datetime", "from_warehouse", "to_warehouse",
            "remarks", "company",
        ],
        order_by="creation desc",
        limit=50,
    )
    for e in entries:
        e["item_count"] = frappe.db.count("Stock Entry Detail", {"parent": e["name"]})
    return entries


# ─── POS Scan-and-Receive (uses same transit workflow) ───────────────────────

@frappe.whitelist()
def pos_scan_receive(stock_entry, barcode):
    """POS store executive scans IMEI/barcode to receive items.

    Uses the same transit workflow as the Stock Entry form:
    increments custom_final_received_qty per scanned item.
    Only allowed when status is 'Ready For Receive' or 'Receive At Transit'.
    """
    doc = frappe.get_doc("Stock Entry", stock_entry)
    if doc.stock_entry_type != "Material Transfer":
        frappe.throw("Not a Material Transfer")

    # Block receive if logistics revert is requested
    if doc.custom_logistics_status == "Revert Requested":
        frappe.throw("Cannot receive — revert has been requested for this shipment")

    allowed = ("Ready For Receive", "Receive At Transit")
    if doc.custom_status not in allowed:
        frappe.throw(f"Scan-receive only allowed when status is {' or '.join(allowed)}, current: {doc.custom_status}")

    frappe.db.sql("SELECT name FROM `tabStock Entry` WHERE name=%s FOR UPDATE", doc.name)

    # Resolve barcode to item_code (supports IMEI/serial via Item Barcode or Serial No)
    item_code = _resolve_barcode(barcode)

    found = False
    for item in doc.items:
        if item.item_code == item_code:
            found = True
            max_qty = item.custom_receive_qty or item.custom_quantity or item.qty
            if (item.custom_final_received_qty or 0) >= max_qty:
                frappe.throw(f"All quantity already received for {item.item_code}")
            item.custom_final_received_qty = (item.custom_final_received_qty or 0) + 1
            break

    if not found:
        frappe.throw(f"{item_code} (barcode: {barcode}) not in this Stock Entry")

    # Move to Receive At Transit if not already
    if doc.custom_status == "Ready For Receive":
        doc.custom_status = "Receive At Transit"

    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    doc.reload()

    return {
        "item_code": item_code,
        "items": [
            {
                "item_code": i.item_code,
                "item_name": i.item_name,
                "qty": i.custom_quantity or i.qty,
                "received_qty": i.custom_final_received_qty or 0,
                "pending": (i.custom_quantity or i.qty) - (i.custom_final_received_qty or 0),
            }
            for i in doc.items
        ],
    }


@frappe.whitelist()
def pos_confirm_receive(stock_entry):
    """POS store executive confirms all scanned items — triggers final transfer.

    Calls the same transit_target_entry as the Stock Entry form "Final Received" button.
    """
    doc = frappe.get_doc("Stock Entry", stock_entry)
    if doc.stock_entry_type != "Material Transfer":
        frappe.throw("Not a Material Transfer")
    if doc.custom_status != "Receive At Transit":
        frappe.throw(f"Confirm receive only allowed at 'Receive At Transit', current: {doc.custom_status}")
    if doc.custom_logistics_status == "Revert Requested":
        frappe.throw("Cannot confirm — revert has been requested for this shipment")

    if not any(i.custom_final_received_qty for i in doc.items):
        frappe.throw("No items have been scanned. Scan at least one item first.")

    frappe.db.sql("SELECT name FROM `tabStock Entry` WHERE name=%s FOR UPDATE", doc.name)

    # Move stock from transit → target warehouse (same as stock_entry.js "Final Received")
    transit_target_entry(doc)

    fully_done = all(
        (i.custom_final_received_qty or 0) == (i.custom_quantity or i.qty)
        for i in doc.items
    )

    if fully_done:
        doc.custom_status = "Transferred"
    else:
        doc.custom_status = "Partially Transferred"
        for item in doc.items:
            remaining = (item.custom_quantity or item.qty) - (item.custom_final_received_qty or 0)
            item.custom_quantity = remaining
            item.custom_pending_qty = remaining
            item.custom_receive_qty = 0
            item.custom_final_received_qty = 0

    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    if doc.docstatus == 0:
        doc.submit()

    return {
        "status": doc.custom_status,
        "partial": doc.custom_status == "Partially Transferred",
    }


def _resolve_barcode(barcode):
    """Resolve barcode/IMEI/serial to item_code."""
    # Try Item Barcode first
    item_code = frappe.db.get_value("Item Barcode", {"barcode": barcode}, "parent")
    if item_code:
        return item_code

    # Try Serial No (IMEI is stored as serial number)
    item_code = frappe.db.get_value("Serial No", barcode, "item_code")
    if item_code:
        return item_code

    frappe.throw(f"Barcode/IMEI not found: {barcode}")


def _auto_generate_ewaybill(doc):
    """Auto-generate e-way bill for material transfer if India Compliance is enabled.

    Triggered on logistics pickup. Checks:
    - India Compliance is installed
    - E-way bill is enabled for Stock Entry (enable_e_waybill + enable_e_waybill_for_sc)
    - Stock entry has bill_from_address / bill_to_address set
    """
    try:
        from india_compliance.gst_india.utils.e_waybill import generate_e_waybill
    except ImportError:
        return  # India Compliance not installed

    gst_settings = frappe.get_cached_doc("GST Settings")
    if not (gst_settings.enable_e_waybill and gst_settings.enable_e_waybill_for_sc and gst_settings.enable_api):
        return

    # Only proceed if addresses are set (required for e-way bill)
    if not (doc.get("bill_from_address") and doc.get("bill_to_address")):
        frappe.msgprint(
            frappe._("E-Way Bill could not be auto-generated: Bill From / Bill To addresses are not set on {0}").format(doc.name),
            indicator="orange",
            alert=True,
        )
        return

    frappe.enqueue(
        "india_compliance.gst_india.utils.e_waybill.generate_e_waybill",
        enqueue_after_commit=True,
        queue="short",
        doctype="Stock Entry",
        docname=doc.name,
    )