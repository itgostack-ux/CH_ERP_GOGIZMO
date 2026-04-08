"""
Transfer Manifest API — Whitelisted endpoints.

Used by both the CH Transfer Manifest form buttons and the Delivery App page.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime, cint, flt


# ── Manifest CRUD ────────────────────────────────────────────────────────────

@frappe.whitelist()
def create_manifest(stock_entries, source_warehouse=None, destination_warehouse=None,
                    source_store=None, destination_store=None):
    """Create a manifest from a list of Stock Entry names (comma-separated or list)."""
    if isinstance(stock_entries, str):
        stock_entries = [s.strip() for s in stock_entries.split(",") if s.strip()]

    if not stock_entries:
        frappe.throw(_("No Stock Entries provided."))

    # Infer warehouses from first Stock Entry if not supplied
    if not source_warehouse or not destination_warehouse:
        se = frappe.get_doc("Stock Entry", stock_entries[0])
        source_warehouse = source_warehouse or se.from_warehouse
        destination_warehouse = destination_warehouse or se.to_warehouse

    doc = frappe.new_doc("CH Transfer Manifest")
    doc.source_warehouse = source_warehouse
    doc.destination_warehouse = destination_warehouse
    doc.source_store = source_store
    doc.destination_store = destination_store

    for se_name in stock_entries:
        doc.append("transfers", {"stock_entry": se_name})

    doc.insert()
    frappe.db.commit()
    return doc.name


@frappe.whitelist()
def get_manifest(manifest):
    """Return full manifest doc as dict."""
    doc = frappe.get_doc("CH Transfer Manifest", manifest)
    doc.check_permission("read")
    return doc.as_dict()


# ── Status Transitions ──────────────────────────────────────────────────────

@frappe.whitelist()
def assign_driver(manifest, driver, courier_partner=None, vehicle_number=None,
                  tracking_number=None, estimated_delivery_date=None):
    doc = frappe.get_doc("CH Transfer Manifest", manifest)
    doc.check_permission("write")
    doc.assign_driver(
        driver=driver,
        courier_partner=courier_partner,
        vehicle_number=vehicle_number,
        tracking_number=tracking_number,
        estimated_delivery_date=estimated_delivery_date,
    )
    frappe.db.commit()
    return {"status": doc.status, "delivery_otp": doc.delivery_otp}


@frappe.whitelist()
def start_pickup(manifest, pickup_photo, lat=None, lng=None, notes=None):
    doc = frappe.get_doc("CH Transfer Manifest", manifest)
    doc.check_permission("write")
    doc.start_pickup(pickup_photo=pickup_photo, lat=lat, lng=lng, notes=notes)
    frappe.db.commit()
    return {"status": doc.status}


@frappe.whitelist()
def complete_delivery(manifest, delivery_photo, receiver_name, otp=None,
                      lat=None, lng=None):
    doc = frappe.get_doc("CH Transfer Manifest", manifest)
    doc.check_permission("write")
    doc.complete_delivery(
        delivery_photo=delivery_photo,
        receiver_name=receiver_name,
        otp=otp, lat=lat, lng=lng,
    )
    frappe.db.commit()
    return {"status": doc.status}


@frappe.whitelist()
def accept_delivery(manifest, damage_reported=0, damage_notes=None, damage_photo=None):
    doc = frappe.get_doc("CH Transfer Manifest", manifest)
    doc.check_permission("write")
    doc.accept_delivery(
        damage_reported=cint(damage_reported),
        damage_notes=damage_notes,
        damage_photo=damage_photo,
    )
    frappe.db.commit()
    return {"status": doc.status}


@frappe.whitelist()
def close_manifest(manifest):
    doc = frappe.get_doc("CH Transfer Manifest", manifest)
    doc.check_permission("write")
    doc.close_manifest()
    frappe.db.commit()
    return {"status": doc.status}


@frappe.whitelist()
def resend_otp(manifest):
    """Regenerate and resend OTP to destination store contact."""
    doc = frappe.get_doc("CH Transfer Manifest", manifest)
    doc.check_permission("write")
    if doc.status not in ("Assigned", "In Transit"):
        frappe.throw(_("OTP can only be resent in Assigned/In Transit status."))
    doc._generate_delivery_otp()
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    frappe.db.commit()
    # TODO: Send OTP via SMS/notification to destination store
    return {"message": "OTP regenerated"}


# ── Delivery App Endpoints ───────────────────────────────────────────────────

@frappe.whitelist()
def get_driver_assignments():
    """Return manifests assigned to the logged-in user (as Driver)."""
    user = frappe.session.user
    # Find Driver record linked to this user
    driver = frappe.db.get_value("Driver", {"employee": user}, "name")
    if not driver:
        # Try matching by user email in Driver doctype
        driver = frappe.db.get_value("Driver", {"name": ["like", f"%{user}%"]}, "name")

    filters = {"docstatus": 1}
    if driver:
        filters["driver"] = driver
    else:
        # System Manager / Administrator can see all
        user_roles = frappe.get_roles(user)
        if "System Manager" not in user_roles and "Delivery User" not in user_roles and "Delivery Manager" not in user_roles:
            return []

    filters["status"] = ["in", ["Assigned", "In Transit"]]

    manifests = frappe.get_all(
        "CH Transfer Manifest",
        filters=filters,
        fields=[
            "name", "status", "source_warehouse", "destination_warehouse",
            "source_store", "destination_store",
            "driver_name", "driver_phone",
            "total_stock_entries", "total_items", "total_qty",
            "estimated_delivery_date", "creation",
        ],
        order_by="creation desc",
        limit=50,
    )

    # Enrichment: store addresses
    for m in manifests:
        if m.get("source_store"):
            addr = frappe.db.get_value("CH Store", m["source_store"], "address")
            m["source_address"] = addr or ""
        if m.get("destination_store"):
            addr = frappe.db.get_value("CH Store", m["destination_store"], "address")
            m["destination_address"] = addr or ""

    return manifests


@frappe.whitelist()
def get_delivery_history():
    """Return recently delivered/received manifests for current driver."""
    user = frappe.session.user
    driver = frappe.db.get_value("Driver", {"employee": user}, "name")

    filters = {
        "docstatus": 1,
        "status": ["in", ["Delivered", "Received", "Closed"]],
    }
    if driver:
        filters["driver"] = driver
    else:
        user_roles = frappe.get_roles(user)
        if "System Manager" not in user_roles and "Delivery User" not in user_roles and "Delivery Manager" not in user_roles:
            return []

    return frappe.get_all(
        "CH Transfer Manifest",
        filters=filters,
        fields=[
            "name", "status", "source_warehouse", "destination_warehouse",
            "source_store", "destination_store",
            "total_stock_entries", "total_items", "total_qty",
            "delivery_datetime", "received_datetime",
        ],
        order_by="modified desc",
        limit=20,
    )


@frappe.whitelist()
def get_manifest_detail(manifest):
    """Return manifest detail for the delivery app."""
    doc = frappe.get_doc("CH Transfer Manifest", manifest)
    doc.check_permission("read")

    result = doc.as_dict()
    # Add Stock Entry item details
    items = []
    for row in doc.transfers:
        se_items = frappe.get_all(
            "Stock Entry Detail",
            filters={"parent": row.stock_entry},
            fields=["item_code", "item_name", "qty", "serial_no", "batch_no"],
        )
        items.append({
            "stock_entry": row.stock_entry,
            "from_warehouse": row.from_warehouse,
            "to_warehouse": row.to_warehouse,
            "items": se_items,
        })
    result["transfer_items_detail"] = items

    # Store addresses
    if doc.source_store:
        result["source_address"] = frappe.db.get_value("CH Store", doc.source_store, "address") or ""
    if doc.destination_store:
        result["destination_address"] = frappe.db.get_value("CH Store", doc.destination_store, "address") or ""

    return result


# ── Operations Hub Integration ───────────────────────────────────────────────

@frappe.whitelist()
def get_manifest_queue(tab="active", warehouse=""):
    """Return manifest list for Ops Hub integration."""
    filters = {"docstatus": 1}

    if tab == "active":
        filters["status"] = ["in", ["Packed", "Assigned", "In Transit"]]
    elif tab == "delivered":
        filters["status"] = ["in", ["Delivered", "Received"]]
    elif tab == "closed":
        filters["status"] = "Closed"
    elif tab == "all":
        pass

    if warehouse:
        filters["source_warehouse"] = warehouse

    return frappe.get_all(
        "CH Transfer Manifest",
        filters=filters,
        fields=[
            "name", "status", "source_warehouse", "destination_warehouse",
            "source_store", "destination_store",
            "driver_name", "courier_partner",
            "total_stock_entries", "total_items", "total_qty",
            "estimated_delivery_date", "creation", "modified",
        ],
        order_by="creation desc",
        limit=100,
    )
