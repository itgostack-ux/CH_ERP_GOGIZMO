import frappe
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry
from erpnext.stock.stock_ledger import make_sl_entries
from frappe.utils import get_datetime

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

# def transit_source(doc):
#     for item in doc.items:
#         move_stock(doc,item,item.custom_pending_qty,TRANSIT_WAREHOUSE,item.s_warehouse)