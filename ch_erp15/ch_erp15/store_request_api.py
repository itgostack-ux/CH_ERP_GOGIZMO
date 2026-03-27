"""Store Material Request API — extends standard Material Request.

All store replenishment requests use the standard Material Request doctype
with custom fields for store context, priority, and SLA tracking.

Flow:
  POS Store -> creates Material Request (type=Material Transfer) -> Submit
  Stock team processes via standard ERPNext:
    - MR -> Stock Entry (for internal transfers)
    - MR -> Purchase Order (when type=Purchase)
  Status auto-updates: Pending -> Ordered/Transferred -> Received
"""

import datetime
import json

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, nowdate


# -- SLA configuration --

SLA_HOURS = {"Urgent": 4, "Standard": 24, "Low": 72}


# -- Helpers --

def _load_rows(payload):
    if isinstance(payload, str):
        return json.loads(payload)
    return payload or []


def _get_store_from_profile(pos_profile):
    """Resolve CH Store from POS Profile."""
    store = frappe.db.get_value("POS Profile Extension", {"pos_profile": pos_profile}, "store")
    if store:
        return store
    warehouse = frappe.db.get_value("POS Profile", pos_profile, "warehouse")
    if warehouse:
        store = frappe.db.get_value("CH Store", {"warehouse": warehouse}, "name")
    return store


def _get_warehouse_from_profile(pos_profile):
    """Get the warehouse linked to a POS Profile."""
    return frappe.db.get_value("POS Profile", pos_profile, "warehouse")


# -- Create Material Request from Store --

@frappe.whitelist()
def create_store_material_request(pos_profile, items, priority="Standard",
                                  notes=None, required_by_date=None):
    """Create a standard Material Request from a POS store.

    Creates a Material Transfer type request with the store's warehouse
    as the target (set_warehouse). Automatically submits it so it appears
    in the stock team's queue.
    """
    frappe.has_permission("Material Request", "create", throw=True)
    rows = _load_rows(items)
    if not rows:
        frappe.throw(_("At least one item is required."))

    profile = frappe.get_cached_doc("POS Profile", pos_profile)
    store = _get_store_from_profile(pos_profile)
    warehouse = profile.warehouse

    if not warehouse:
        frappe.throw(_("Warehouse not configured for POS Profile {0}.").format(pos_profile))

    schedule_date = required_by_date or nowdate()

    mr = frappe.new_doc("Material Request")
    mr.material_request_type = "Material Transfer"
    mr.company = profile.company
    mr.transaction_date = nowdate()
    mr.schedule_date = schedule_date
    mr.set_warehouse = warehouse  # target warehouse (store's warehouse)

    # Custom fields for store context
    mr.custom_store = store
    mr.custom_pos_profile = pos_profile
    mr.custom_priority = priority or "Standard"
    mr.custom_request_notes = notes

    for row in rows:
        qty = flt(row.get("qty") or row.get("requested_qty") or 0)
        if qty <= 0:
            frappe.throw(_("Requested qty must be greater than 0."))
        item_code = row.get("item_code")
        if not item_code:
            frappe.throw(_("Item code is required."))

        mr.append("items", {
            "item_code": item_code,
            "qty": qty,
            "uom": row.get("uom") or frappe.db.get_value("Item", item_code, "stock_uom") or "Nos",
            "warehouse": warehouse,
            "schedule_date": schedule_date,
        })

    mr.insert()
    mr.submit()

    # Set SLA after submit
    _set_sla(mr)

    return mr.name


# -- Get pending requests for a store --

@frappe.whitelist()
def get_store_material_requests(pos_profile, include_closed=0):
    """Get recent Material Requests for a POS store."""
    frappe.has_permission("Material Request", "read", throw=True)
    store = _get_store_from_profile(pos_profile)
    if not store:
        return []

    filters = {
        "custom_store": store,
        "docstatus": 1,
    }

    if not frappe.utils.cint(include_closed):
        filters["status"] = ("not in", ["Stopped", "Cancelled"])

    return frappe.get_all(
        "Material Request",
        filters=filters,
        fields=[
            "name", "company", "custom_store as store", "custom_priority as priority",
            "status", "schedule_date as required_by_date", "creation",
            "per_ordered", "per_received", "transfer_status",
            "custom_sla_breached as sla_breached",
            "material_request_type",
        ],
        order_by="creation desc",
        limit=30,
    )


# -- Stock availability check --

@frappe.whitelist()
def check_stock_for_request(request_name):
    """Return stock availability across all warehouses for items in this request."""
    frappe.has_permission("Material Request", "read", throw=True)
    doc = frappe.get_doc("Material Request", request_name)

    destination_warehouse = doc.set_warehouse
    if not destination_warehouse and doc.items:
        destination_warehouse = doc.items[0].warehouse

    items = [{"item_code": r.item_code, "requested_qty": r.qty} for r in doc.items]
    return check_stock_availability(items, doc.company, destination_warehouse)


# -- SLA tracking --

def _set_sla(doc):
    """Set SLA breach date based on priority after submission."""
    priority = doc.custom_priority or "Standard"
    hours = SLA_HOURS.get(priority, 24)
    breach_dt = now_datetime() + datetime.timedelta(hours=hours)

    frappe.db.set_value("Material Request", doc.name, {
        "custom_sla_breach_date": breach_dt,
        "custom_sla_breached": 0,
    }, update_modified=False)


def check_sla_breach():
    """Scheduled job: mark overdue store requests as SLA breached.

    Add to hooks.py scheduler_events to run hourly.
    """
    overdue = frappe.get_all(
        "Material Request",
        filters={
            "custom_store": ("is", "set"),
            "custom_sla_breached": 0,
            "custom_sla_breach_date": ("<", now_datetime()),
            "docstatus": 1,
            "status": ("not in", ["Received", "Transferred", "Stopped", "Cancelled"]),
        },
        pluck="name",
    )
    for name in overdue:
        frappe.db.set_value("Material Request", name, "custom_sla_breached", 1, update_modified=False)
    if overdue:
        frappe.db.commit()


# -- Stock availability utility --

def check_stock_availability(items, company, destination_warehouse):
    """Check stock across all company warehouses for the given items.

    Returns:
        {
            "ITEM-001": {
                "requested_qty": 10,
                "availability": [
                    {"warehouse": "Central - G", "available_qty": 5, "is_destination": False},
                ],
                "total_available": 8,
                "shortage": 2,
            }
        }
    """
    from erpnext.stock.utils import get_stock_balance

    result = {}
    if not items:
        return result

    warehouses = frappe.get_all(
        "Warehouse",
        filters={"company": company, "is_group": 0, "disabled": 0},
        pluck="name",
    )

    for item in items:
        item_code = item.get("item_code")
        requested_qty = flt(item.get("requested_qty") or item.get("qty"))
        availability = []

        for wh in warehouses:
            bal = flt(get_stock_balance(item_code, wh))
            if bal > 0:
                availability.append({
                    "warehouse": wh,
                    "available_qty": bal,
                    "is_destination": (wh == destination_warehouse),
                })

        # Sort: non-destination first, then by qty descending
        availability.sort(key=lambda x: (x["is_destination"], -x["available_qty"]))
        total_available = sum(a["available_qty"] for a in availability if not a["is_destination"])

        result[item_code] = {
            "requested_qty": requested_qty,
            "availability": availability,
            "total_available": total_available,
            "shortage": max(requested_qty - total_available, 0),
        }

    return result


def auto_allocate_sources(items, company, destination_warehouse):
    """Auto-generate a fulfillment suggestion using source prioritization.

    Priority: Central warehouses (largest stock) -> Store warehouses -> Supplier.
    Returns list of dicts with source info for display/reference.
    """
    stock_data = check_stock_availability(items, company, destination_warehouse)
    suggestions = []

    for item in items:
        item_code = item.get("item_code")
        requested_qty = flt(item.get("requested_qty") or item.get("qty"))
        remaining = requested_qty
        data = stock_data.get(item_code, {})

        for source in data.get("availability", []):
            if remaining <= 0:
                break
            if source["is_destination"]:
                continue

            alloc_qty = min(source["available_qty"], remaining)
            if alloc_qty <= 0:
                continue

            store = frappe.db.get_value("CH Store", {"warehouse": source["warehouse"]}, "name")
            suggestions.append({
                "item_code": item_code,
                "source_type": "Store" if store else "Warehouse",
                "source_warehouse": source["warehouse"],
                "source_store": store or "",
                "suggested_qty": alloc_qty,
            })
            remaining -= alloc_qty

        if remaining > 0:
            suggestions.append({
                "item_code": item_code,
                "source_type": "Supplier",
                "source_warehouse": "",
                "suggested_qty": remaining,
            })

    return suggestions, stock_data


# -- Raise Purchase Request for shortage --

@frappe.whitelist()
def raise_purchase_request(source_mr_name):
    """Create a Purchase-type Material Request for items with stock shortage.

    Checks stock availability for all items in the source (Material Transfer) MR,
    identifies shortages, and creates a new MR (type=Purchase) for the deficit qty.
    Links back to the source MR via custom_request_notes.
    """
    frappe.has_permission("Material Request", "create", throw=True)
    source = frappe.get_doc("Material Request", source_mr_name)

    if source.material_request_type != "Material Transfer":
        frappe.throw(_("Purchase requests can only be raised from Material Transfer requests."))

    destination_warehouse = source.set_warehouse
    if not destination_warehouse and source.items:
        destination_warehouse = source.items[0].warehouse

    items = [{"item_code": r.item_code, "requested_qty": r.qty} for r in source.items]
    stock_data = check_stock_availability(items, source.company, destination_warehouse)

    purchase_items = []
    for item in source.items:
        data = stock_data.get(item.item_code, {})
        shortage = flt(data.get("shortage", 0))
        if shortage > 0:
            purchase_items.append({
                "item_code": item.item_code,
                "qty": shortage,
                "uom": item.uom,
                "warehouse": destination_warehouse,
                "schedule_date": source.schedule_date or nowdate(),
            })

    if not purchase_items:
        frappe.throw(_("No shortage found. All items have sufficient stock for transfer."))

    mr = frappe.new_doc("Material Request")
    mr.material_request_type = "Purchase"
    mr.company = source.company
    mr.transaction_date = nowdate()
    mr.schedule_date = source.schedule_date or nowdate()
    mr.set_warehouse = destination_warehouse
    mr.custom_store = source.custom_store
    mr.custom_pos_profile = source.custom_pos_profile
    mr.custom_priority = source.custom_priority
    mr.custom_request_notes = _("Auto-raised from {0} for stock shortage").format(source_mr_name)

    for item in purchase_items:
        mr.append("items", item)

    mr.insert()
    mr.submit()
    _set_sla(mr)

    # Add a comment on the source MR linking to the purchase request
    source.add_comment("Info",
        _("Purchase Request {0} raised for {1} shortage items").format(
            f'<a href="/app/material-request/{mr.name}">{mr.name}</a>',
            len(purchase_items),
        )
    )

    return {
        "name": mr.name,
        "items": len(purchase_items),
        "stock_data": stock_data,
    }
