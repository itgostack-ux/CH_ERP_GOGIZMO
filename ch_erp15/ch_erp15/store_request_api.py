"""Store Material Request API — extends standard Material Request.

All store replenishment requests use the standard Material Request doctype
with custom fields for store context, priority, SLA tracking, and approval.

Flow:
  POS Store -> creates Material Request (type=Material Transfer, Draft)
  Store Manager approves -> MR submitted -> SLA starts
  Stock team processes via standard ERPNext + custom buttons:
    - Check Stock Availability across all warehouses
    - Suggest Allocation (auto-prioritize sources)
    - Execute Allocation (create Stock Entries per source)
    - Raise Purchase Request (for shortage items)
    - Short Close (partial fulfillment acceptance)
  Status auto-updates via standard ERPNext: Pending -> Ordered/Transferred -> Received
  Notifications sent at key lifecycle events.
"""

import datetime
import json

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime, nowdate


# ─── SLA configuration ───────────────────────────────────────────────────────

SLA_HOURS = {"Urgent": 4, "Standard": 24, "Low": 72}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _load_rows(payload):
    if isinstance(payload, str):
        return json.loads(payload)
    return payload or []


def _get_store_from_profile(pos_profile):
    """Resolve CH Store from POS Profile."""
    store = frappe.db.get_value(
        "POS Profile Extension", {"pos_profile": pos_profile}, "store"
    )
    if store:
        return store
    warehouse = frappe.db.get_value("POS Profile", pos_profile, "warehouse")
    if warehouse:
        store = frappe.db.get_value("CH Store", {"warehouse": warehouse}, "name")
    return store


def _get_warehouse_from_profile(pos_profile):
    """Get the warehouse linked to a POS Profile."""
    return frappe.db.get_value("POS Profile", pos_profile, "warehouse")


def _get_zone_source_warehouse(store):
    """Resolve the source warehouse from the store's zone.

    Returns the zone's source_warehouse or None if zone is not set.
    """
    if not store:
        return None
    zone = frappe.db.get_value("CH Store", store, "zone")
    if not zone:
        return None
    return frappe.db.get_value("CH Store Zone", zone, "source_warehouse")


def _validate_store_permission(store):
    """Ensure current user is allowed to act on this store."""
    if frappe.session.user == "Administrator":
        return
    if "Stock Manager" in frappe.get_roles():
        return
    if "System Manager" in frappe.get_roles():
        return
    if not store:
        return
    # Check if User Permission links this user to the store
    has_perm = frappe.db.exists(
        "User Permission",
        {"user": frappe.session.user, "allow": "CH Store", "for_value": store},
    )
    if has_perm:
        return
    # Also allow if user is listed in CH Store users
    is_store_user = frappe.db.exists(
        "CH Store User",
        {"parent": store, "parenttype": "CH Store", "user": frappe.session.user},
    )
    if is_store_user:
        return
    frappe.throw(
        _("You do not have permission to act on store {0}.").format(store),
        frappe.PermissionError,
    )


def _send_notification(recipients, subject, message, reference_doctype=None,
                       reference_name=None):
    """Send system notification and email to recipients (best-effort)."""
    if not recipients:
        return
    if isinstance(recipients, str):
        recipients = [recipients]
    try:
        for user in recipients:
            doc = frappe.new_doc("Notification Log")
            doc.for_user = user
            doc.from_user = frappe.session.user
            doc.subject = subject
            doc.type = "Alert"
            doc.document_type = reference_doctype
            doc.document_name = reference_name
            doc.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Store MR Notification Error")

    try:
        # Only attempt email if an outgoing email account is configured
        default_outgoing = frappe.db.get_value(
            "Email Account",
            {"default_outgoing": 1, "enable_outgoing": 1},
            "name",
        )
        if default_outgoing:
            frappe.sendmail(
                recipients=recipients,
                subject=subject,
                message=message,
                reference_doctype=reference_doctype,
                reference_name=reference_name,
                now=True,
            )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Store MR Email Error")


def _get_stock_team_users():
    """Return list of users with Stock Manager or Stock User role."""
    users = frappe.get_all(
        "Has Role",
        filters={"role": ("in", ["Stock Manager", "Stock User"]), "parenttype": "User"},
        pluck="parent",
    )
    return list(set(u for u in users if u and u != "Administrator"))


def _get_store_managers(store):
    """Return users who can approve MRs for this store."""
    managers = []
    if store:
        managers = frappe.get_all(
            "CH Store User",
            filters={"parent": store, "parenttype": "CH Store"},
            pluck="user",
        )
    if not managers:
        managers = frappe.get_all(
            "Has Role",
            filters={"role": "Stock Manager", "parenttype": "User"},
            pluck="parent",
        )
    return list(set(m for m in managers if m and m != "Administrator"))


# ─── Create Material Request from Store ───────────────────────────────────────

@frappe.whitelist()
def create_store_material_request(pos_profile, items, priority="Standard",
                                  notes=None, required_by_date=None,
                                  preferred_source_warehouse=None):
    """Create a standard Material Request from a POS store.

    Creates a Material Transfer type request with the store's warehouse
    as the target (set_warehouse). Saved as Draft for manager approval.
    """
    frappe.has_permission("Material Request", "create", throw=True)
    rows = _load_rows(items)
    if not rows:
        frappe.throw(_("At least one item is required."))

    profile = frappe.get_cached_doc("POS Profile", pos_profile)
    store = _get_store_from_profile(pos_profile)
    warehouse = profile.warehouse

    if not warehouse:
        frappe.throw(
            _("Warehouse not configured for POS Profile {0}.").format(pos_profile)
        )

    # Store-level permission check
    _validate_store_permission(store)

    # Duplicate prevention: open MR with same store + overlapping items in 24h
    item_codes = [r.get("item_code") for r in rows if r.get("item_code")]
    if item_codes and store:
        existing = frappe.db.sql(
            """SELECT mr.name
               FROM `tabMaterial Request` mr
               JOIN `tabMaterial Request Item` mri ON mri.parent = mr.name
               WHERE mr.custom_store = %(store)s
                 AND mr.docstatus < 2
                 AND mr.status NOT IN ('Stopped', 'Cancelled', 'Received', 'Transferred')
                 AND mr.creation >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
                 AND mri.item_code IN %(items)s
               LIMIT 1""",
            {"store": store, "items": tuple(item_codes)},
            as_dict=True,
        )
        if existing:
            frappe.throw(
                _("An open Material Request {0} already exists for some of these items. "
                  "Please check before creating a duplicate.").format(existing[0].name)
            )

    schedule_date = required_by_date or nowdate()

    # Auto-resolve source warehouse from zone if not explicitly given
    if not preferred_source_warehouse:
        preferred_source_warehouse = _get_zone_source_warehouse(store)

    mr = frappe.new_doc("Material Request")
    mr.material_request_type = "Material Transfer"
    mr.company = profile.company
    mr.transaction_date = nowdate()
    mr.schedule_date = schedule_date
    mr.set_warehouse = warehouse

    # Custom fields
    mr.custom_store = store
    mr.custom_pos_profile = pos_profile
    mr.custom_priority = priority or "Standard"
    mr.custom_request_notes = notes
    mr.custom_approval_status = "Pending Approval"
    mr.custom_request_datetime = now_datetime()
    if preferred_source_warehouse:
        mr.custom_preferred_source_warehouse = preferred_source_warehouse

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
            "uom": row.get("uom") or frappe.db.get_value(
                "Item", item_code, "stock_uom"
            ) or "Nos",
            "warehouse": warehouse,
            "schedule_date": schedule_date,
        })

    mr.insert()
    # Stays as Draft until store manager approves

    # Notify store managers
    managers = _get_store_managers(store)
    if managers:
        _send_notification(
            recipients=managers,
            subject=_("Store Material Request {0} needs approval").format(mr.name),
            message=_("A new material request {0} from store {1} with {2} priority "
                      "requires your approval.").format(mr.name, store, priority),
            reference_doctype="Material Request",
            reference_name=mr.name,
        )

    return mr.name


# ─── Approval workflow ────────────────────────────────────────────────────────

@frappe.whitelist()
def approve_store_request(request_name):
    """Store Manager approves a pending store MR — submits it and starts SLA."""
    frappe.has_permission("Material Request", "submit", throw=True)
    doc = frappe.get_doc("Material Request", request_name)

    if doc.custom_approval_status != "Pending Approval":
        frappe.throw(_("Only requests with 'Pending Approval' status can be approved."))
    if doc.docstatus != 0:
        frappe.throw(_("Only Draft requests can be approved."))

    _validate_store_permission(doc.custom_store)

    doc.custom_approval_status = "Approved"
    doc.save()
    doc.submit()

    # Set SLA from approval time
    _set_sla(doc)

    # Notify stock team
    stock_users = _get_stock_team_users()
    if stock_users:
        _send_notification(
            recipients=stock_users,
            subject=_("New Store Material Request {0} — {1}").format(
                doc.name, doc.custom_priority
            ),
            message=_("Store {0} has submitted {1} ({2} priority, {3} items). "
                      "Please process.").format(
                doc.custom_store, doc.name, doc.custom_priority,
                len(doc.items),
            ),
            reference_doctype="Material Request",
            reference_name=doc.name,
        )

    # Notify requester
    _send_notification(
        recipients=[doc.owner],
        subject=_("Your Material Request {0} has been approved").format(doc.name),
        message=_("Material Request {0} has been approved and sent to the stock team.").format(
            doc.name
        ),
        reference_doctype="Material Request",
        reference_name=doc.name,
    )

    return {"status": "Approved", "name": doc.name}


@frappe.whitelist()
def reject_store_request(request_name, reason=None):
    """Store Manager rejects a pending store MR."""
    frappe.has_permission("Material Request", "write", throw=True)
    doc = frappe.get_doc("Material Request", request_name)

    if doc.custom_approval_status != "Pending Approval":
        frappe.throw(_("Only requests with 'Pending Approval' status can be rejected."))
    if doc.docstatus != 0:
        frappe.throw(_("Only Draft requests can be rejected."))

    _validate_store_permission(doc.custom_store)

    doc.custom_approval_status = "Rejected"
    doc.save()
    doc.add_comment("Info", _("Rejected by {0}. Reason: {1}").format(
        frappe.session.user, reason or "No reason provided"
    ))

    # Notify requester
    _send_notification(
        recipients=[doc.owner],
        subject=_("Your Material Request {0} has been rejected").format(doc.name),
        message=_("Material Request {0} was rejected. Reason: {1}").format(
            doc.name, reason or "No reason provided"
        ),
        reference_doctype="Material Request",
        reference_name=doc.name,
    )

    return {"status": "Rejected", "name": doc.name}


# ─── Get pending requests for a store ─────────────────────────────────────────

@frappe.whitelist()
def get_store_material_requests(pos_profile, include_closed=0):
    """Get recent Material Requests for a POS store with unified tracking."""
    frappe.has_permission("Material Request", "read", throw=True)
    store = _get_store_from_profile(pos_profile)
    if not store:
        return []

    filters = {
        "custom_store": store,
        "docstatus": ("in", [0, 1]),
    }

    if not cint(include_closed):
        filters["status"] = ("not in", ["Stopped", "Cancelled"])

    requests = frappe.get_all(
        "Material Request",
        filters=filters,
        fields=[
            "name", "company", "custom_store as store",
            "custom_priority as priority",
            "custom_approval_status as approval_status",
            "status", "schedule_date as required_by_date", "creation",
            "per_ordered", "per_received", "transfer_status",
            "custom_sla_breached as sla_breached",
            "material_request_type", "docstatus",
        ],
        order_by="creation desc",
        limit=50,
    )

    if not requests:
        return requests

    # Enrich with linked purchase MRs and Stock Entries
    mr_names = [r["name"] for r in requests]

    # Linked purchase MRs (via custom_source_material_request)
    purchase_mrs = frappe.get_all(
        "Material Request",
        filters={
            "custom_source_material_request": ("in", mr_names),
            "docstatus": ("in", [0, 1]),
        },
        fields=["name", "status", "custom_source_material_request as source_mr",
                "per_ordered"],
    )
    purchase_map = {}
    for pm in purchase_mrs:
        purchase_map.setdefault(pm.source_mr, []).append(pm)

    # Linked Stock Entries (via Material Request Item back-reference)
    se_data = frappe.db.sql(
        """SELECT DISTINCT sed.material_request, se.name, se.docstatus,
                  se.custom_status
           FROM `tabStock Entry Detail` sed
           JOIN `tabStock Entry` se ON se.name = sed.parent
           WHERE sed.material_request IN %(names)s
             AND se.docstatus = 1""",
        {"names": tuple(mr_names)},
        as_dict=True,
    )
    se_map = {}
    for se in se_data:
        se_map.setdefault(se.material_request, []).append(se)

    for req in requests:
        req["purchase_requests"] = purchase_map.get(req["name"], [])
        req["stock_entries"] = se_map.get(req["name"], [])

    return requests


# ─── Detailed request tracking ────────────────────────────────────────────────

@frappe.whitelist()
def get_request_tracking(request_name):
    """Unified tracking view: source MR + linked purchase MRs + Stock Entries."""
    frappe.has_permission("Material Request", "read", throw=True)
    doc = frappe.get_doc("Material Request", request_name)

    tracking = {
        "name": doc.name,
        "status": doc.status,
        "approval_status": doc.custom_approval_status,
        "priority": doc.custom_priority,
        "store": doc.custom_store,
        "sla_breached": cint(doc.custom_sla_breached),
        "sla_breach_date": str(doc.custom_sla_breach_date or ""),
        "per_ordered": flt(doc.per_ordered),
        "per_received": flt(doc.per_received),
        "transfer_status": doc.transfer_status,
        "items": [],
        "purchase_requests": [],
        "stock_entries": [],
        "closure": None,
    }

    # Items detail
    for item in doc.items:
        tracking["items"].append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "qty": item.qty,
            "ordered_qty": flt(item.ordered_qty),
            "received_qty": flt(item.received_qty),
            "warehouse": item.warehouse,
        })

    # Linked purchase MRs
    purchase_mrs = frappe.get_all(
        "Material Request",
        filters={
            "custom_source_material_request": doc.name,
            "docstatus": ("in", [0, 1]),
        },
        fields=["name", "status", "material_request_type", "per_ordered",
                "schedule_date", "creation"],
    )
    tracking["purchase_requests"] = purchase_mrs

    # Linked Stock Entries
    stock_entries = frappe.db.sql(
        """SELECT DISTINCT se.name, se.stock_entry_type, se.docstatus,
                  se.posting_date, se.custom_status, se.from_warehouse, se.to_warehouse
           FROM `tabStock Entry Detail` sed
           JOIN `tabStock Entry` se ON se.name = sed.parent
           WHERE sed.material_request = %(mr)s AND se.docstatus = 1""",
        {"mr": doc.name},
        as_dict=True,
    )
    for se in stock_entries:
        # Get damage info from items
        damage_items = frappe.db.sql(
            """SELECT item_code, custom_damaged_qty, custom_damage_notes
               FROM `tabStock Entry Detail`
               WHERE parent = %(se)s AND IFNULL(custom_damaged_qty, 0) > 0""",
            {"se": se.name},
            as_dict=True,
        )
        se["damage_items"] = damage_items
    tracking["stock_entries"] = stock_entries

    # Closure info
    if doc.custom_closure_reason:
        tracking["closure"] = {
            "reason": doc.custom_closure_reason,
            "closed_by": doc.custom_closed_by,
            "closure_date": str(doc.custom_closure_date or ""),
        }

    return tracking


# ─── Stock availability check ─────────────────────────────────────────────────

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


# ─── SLA tracking ─────────────────────────────────────────────────────────────

def _set_sla(doc):
    """Set SLA breach date based on priority after approval/submission."""
    priority = doc.custom_priority or "Standard"
    hours = SLA_HOURS.get(priority, 24)
    breach_dt = now_datetime() + datetime.timedelta(hours=hours)

    frappe.db.set_value("Material Request", doc.name, {
        "custom_sla_breach_date": breach_dt,
        "custom_sla_breached": 0,
    }, update_modified=False)


def check_sla_breach():
    """Scheduled job: mark overdue store requests as SLA breached.

    Runs every 15 minutes via cron. Sends escalation notification on breach.
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
        fields=["name", "custom_store", "custom_priority", "owner"],
    )
    for mr in overdue:
        frappe.db.set_value(
            "Material Request", mr.name, "custom_sla_breached", 1,
            update_modified=False,
        )

        # Escalation notification
        stock_users = _get_stock_team_users()
        recipients = list(set(stock_users + [mr.owner]))
        _send_notification(
            recipients=recipients,
            subject=_("SLA BREACHED: Material Request {0}").format(mr.name),
            message=_("Material Request {0} for store {1} ({2} priority) has "
                      "breached its SLA. Please action immediately.").format(
                mr.name, mr.custom_store, mr.custom_priority
            ),
            reference_doctype="Material Request",
            reference_name=mr.name,
        )

    if overdue:
        frappe.db.commit()


# ─── Stock availability utility ───────────────────────────────────────────────

def check_stock_availability(items, company, destination_warehouse):
    """Check stock across all company warehouses for the given items.

    Deducts quantities already reserved by other open Material Requests
    to prevent double-allocation.

    Returns:
        {
            "ITEM-001": {
                "requested_qty": 10,
                "availability": [
                    {"warehouse": "Central - G", "available_qty": 5,
                     "is_destination": False},
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

    # Calculate reserved qty per item per warehouse from open MRs
    item_codes = [i.get("item_code") for i in items if i.get("item_code")]
    reserved = {}
    if item_codes:
        reserved_rows = frappe.db.sql(
            """SELECT mri.item_code, mri.warehouse,
                      SUM(mri.qty - IFNULL(mri.received_qty, 0)) AS reserved_qty
               FROM `tabMaterial Request Item` mri
               JOIN `tabMaterial Request` mr ON mr.name = mri.parent
               WHERE mr.docstatus = 1
                 AND mr.status NOT IN ('Received','Transferred','Stopped','Cancelled')
                 AND mri.item_code IN %(items)s
               GROUP BY mri.item_code, mri.warehouse""",
            {"items": tuple(item_codes)},
            as_dict=True,
        )
        for r in reserved_rows:
            reserved.setdefault(r.item_code, {})
            reserved[r.item_code][r.warehouse] = flt(r.reserved_qty)

    for item in items:
        item_code = item.get("item_code")
        requested_qty = flt(item.get("requested_qty") or item.get("qty"))
        availability = []

        for wh in warehouses:
            bal = flt(get_stock_balance(item_code, wh))
            # Deduct reserved qty from other open MRs
            wh_reserved = reserved.get(item_code, {}).get(wh, 0)
            effective = max(bal - wh_reserved, 0)
            if effective > 0:
                availability.append({
                    "warehouse": wh,
                    "available_qty": effective,
                    "actual_qty": bal,
                    "reserved_qty": wh_reserved,
                    "is_destination": (wh == destination_warehouse),
                })

        # Sort: non-destination first, then by qty descending
        availability.sort(
            key=lambda x: (x["is_destination"], -x["available_qty"])
        )
        total_available = sum(
            a["available_qty"] for a in availability if not a["is_destination"]
        )

        result[item_code] = {
            "requested_qty": requested_qty,
            "availability": availability,
            "total_available": total_available,
            "shortage": max(requested_qty - total_available, 0),
        }

    return result


# ─── Auto-allocate sources ────────────────────────────────────────────────────

@frappe.whitelist()
def auto_allocate_sources(request_name):
    """Suggest fulfillment sources for a Material Request.

    Priority: Central warehouses (largest stock) -> Store warehouses -> Supplier.
    Stores the allocation plan on the MR and returns the suggestions.
    """
    frappe.has_permission("Material Request", "read", throw=True)
    doc = frappe.get_doc("Material Request", request_name)

    destination_warehouse = doc.set_warehouse
    if not destination_warehouse and doc.items:
        destination_warehouse = doc.items[0].warehouse

    items = [{"item_code": r.item_code, "requested_qty": r.qty} for r in doc.items]
    stock_data = check_stock_availability(items, doc.company, destination_warehouse)
    suggestions = []

    for item in items:
        item_code = item.get("item_code")
        requested_qty = flt(item.get("requested_qty"))
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

            store = frappe.db.get_value(
                "CH Store", {"warehouse": source["warehouse"]}, "name"
            )
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

    # Persist allocation plan on the MR
    plan_json = json.dumps(suggestions, default=str)
    frappe.db.set_value(
        "Material Request", doc.name,
        "custom_allocation_plan", plan_json,
        update_modified=False,
    )

    return {"suggestions": suggestions, "stock_data": stock_data}


# ─── Execute allocation (split Stock Entries) ─────────────────────────────────

@frappe.whitelist()
def execute_allocation(request_name):
    """Create Stock Entries from the saved allocation plan.

    Groups allocation suggestions by source warehouse and creates one
    Material Transfer Stock Entry per source. Returns list of created SEs.
    """
    frappe.has_permission("Stock Entry", "create", throw=True)
    doc = frappe.get_doc("Material Request", request_name)

    if doc.docstatus != 1:
        frappe.throw(_("Material Request must be submitted before execution."))

    plan_raw = doc.custom_allocation_plan
    if not plan_raw:
        frappe.throw(
            _("No allocation plan found. Run 'Suggest Allocation' first.")
        )

    plan = json.loads(plan_raw) if isinstance(plan_raw, str) else plan_raw
    if not plan:
        frappe.throw(_("Allocation plan is empty."))

    destination = doc.set_warehouse
    if not destination and doc.items:
        destination = doc.items[0].warehouse

    # Group by source warehouse (skip Supplier rows)
    from collections import defaultdict
    wh_groups = defaultdict(list)
    for row in plan:
        if row.get("source_type") == "Supplier":
            continue
        wh = row.get("source_warehouse")
        if wh:
            wh_groups[wh].append(row)

    created = []
    for source_wh, alloc_items in wh_groups.items():
        se = frappe.new_doc("Stock Entry")
        se.stock_entry_type = "Material Transfer"
        se.company = doc.company
        se.posting_date = nowdate()

        for ai in alloc_items:
            # Find the MR item row for back-reference
            mr_item_name = None
            for mri in doc.items:
                if mri.item_code == ai["item_code"]:
                    mr_item_name = mri.name
                    break

            se.append("items", {
                "item_code": ai["item_code"],
                "qty": flt(ai["suggested_qty"]),
                "s_warehouse": source_wh,
                "t_warehouse": destination,
                "material_request": doc.name,
                "material_request_item": mr_item_name,
            })

        se.insert()
        # Save as Draft — stock team must review serial/batch selection
        # and submit manually. ERPNext auto-picks serial/batch on submit
        # if auto_create_serial_and_batch_bundle_for_outward is enabled.
        created.append({"name": se.name, "source": source_wh, "items": len(se.items)})

    # Notify stock team that draft SEs are ready for review
    if created:
        stock_users = _get_stock_team_users()
        if stock_users:
            _send_notification(
                recipients=stock_users,
                subject=_("Stock Entries ready for review — {0}").format(doc.name),
                message=_("{0} draft Stock Entries created for Material Request {1}. "
                          "Please review serial/batch selection and submit.").format(
                    len(created), doc.name,
                ),
                reference_doctype="Material Request",
                reference_name=doc.name,
        )

    return {"created": created}


# ─── Raise Purchase Request for shortage ──────────────────────────────────────

@frappe.whitelist()
def raise_purchase_request(source_mr_name):
    """Create a Purchase-type Material Request for items with stock shortage.

    Checks stock availability, identifies shortages, creates a new MR
    (type=Purchase) for the deficit qty. Links via custom_source_material_request.
    Guards against duplicate purchase requests.
    """
    frappe.has_permission("Material Request", "create", throw=True)
    source = frappe.get_doc("Material Request", source_mr_name)

    if source.material_request_type != "Material Transfer":
        frappe.throw(
            _("Purchase requests can only be raised from Material Transfer requests.")
        )

    # Duplicate guard: check for existing purchase MR linked to this source
    existing_pr = frappe.db.get_value(
        "Material Request",
        {
            "custom_source_material_request": source_mr_name,
            "material_request_type": "Purchase",
            "docstatus": ("in", [0, 1]),
        },
        "name",
    )
    if existing_pr:
        frappe.throw(
            _("A purchase request {0} already exists for {1}.").format(
                existing_pr, source_mr_name
            )
        )

    destination_warehouse = source.set_warehouse
    if not destination_warehouse and source.items:
        destination_warehouse = source.items[0].warehouse

    items = [{"item_code": r.item_code, "requested_qty": r.qty}
             for r in source.items]
    stock_data = check_stock_availability(items, source.company,
                                          destination_warehouse)

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
        frappe.throw(
            _("No shortage found. All items have sufficient stock for transfer.")
        )

    mr = frappe.new_doc("Material Request")
    mr.material_request_type = "Purchase"
    mr.company = source.company
    mr.transaction_date = nowdate()
    mr.schedule_date = source.schedule_date or nowdate()
    mr.set_warehouse = destination_warehouse
    mr.custom_store = source.custom_store
    mr.custom_pos_profile = source.custom_pos_profile
    mr.custom_priority = source.custom_priority
    mr.custom_source_material_request = source.name
    mr.custom_request_notes = _(
        "Auto-raised from {0} for stock shortage"
    ).format(source.name)

    for item in purchase_items:
        mr.append("items", item)

    mr.insert()
    mr.submit()
    _set_sla(mr)

    # Comment on the source MR
    source.add_comment(
        "Info",
        _("Purchase Request {0} raised for {1} shortage items").format(
            f'<a href="/app/material-request/{mr.name}">{mr.name}</a>',
            len(purchase_items),
        ),
    )

    # Notify purchase team
    purchase_users = frappe.get_all(
        "Has Role",
        filters={"role": "Purchase User", "parenttype": "User"},
        pluck="parent",
    )
    purchase_users = list(set(u for u in purchase_users
                              if u and u != "Administrator"))
    if purchase_users:
        _send_notification(
            recipients=purchase_users,
            subject=_("Purchase Request {0} for store shortage").format(mr.name),
            message=_("Purchase request {0} raised for {1} items with stock shortage "
                      "(source: {2}, store: {3}).").format(
                mr.name, len(purchase_items), source.name, source.custom_store
            ),
            reference_doctype="Material Request",
            reference_name=mr.name,
        )

    return {
        "name": mr.name,
        "items": len(purchase_items),
        "stock_data": stock_data,
    }


# ─── Short-close request ─────────────────────────────────────────────────────

@frappe.whitelist()
def short_close_request(request_name, reason):
    """Short-close a Material Request with a reason.

    Stops the MR, records closure details, and notifies the store.
    """
    frappe.has_permission("Material Request", "write", throw=True)
    if not reason or not reason.strip():
        frappe.throw(_("A closure reason is required."))

    doc = frappe.get_doc("Material Request", request_name)
    if doc.docstatus != 1:
        frappe.throw(_("Only submitted requests can be short-closed."))
    if doc.status in ("Stopped", "Cancelled"):
        frappe.throw(_("Request is already stopped or cancelled."))

    # Record closure details
    frappe.db.set_value("Material Request", doc.name, {
        "custom_closure_reason": reason.strip(),
        "custom_closed_by": frappe.session.user,
        "custom_closure_date": now_datetime(),
    }, update_modified=False)

    # Stop the MR (standard ERPNext action)
    doc.update_status("Stopped")

    doc.add_comment(
        "Info",
        _("Short-closed by {0}. Reason: {1}").format(
            frappe.utils.get_fullname(frappe.session.user), reason.strip()
        ),
    )

    # Notify store
    if doc.custom_store:
        _send_notification(
            recipients=[doc.owner],
            subject=_("Material Request {0} has been short-closed").format(doc.name),
            message=_("Your Material Request {0} has been short-closed. "
                      "Reason: {1}").format(doc.name, reason.strip()),
            reference_doctype="Material Request",
            reference_name=doc.name,
        )

    return {"status": "Stopped", "name": doc.name}


# ─── Over-transfer validation (called from Stock Entry hook) ──────────────────

def validate_transfer_qty(doc, method=None):
    """Prevent over-transfer: ensure Stock Entry qty doesn't exceed MR requested qty.

    Called from doc_events on Stock Entry validate.
    """
    if doc.stock_entry_type != "Material Transfer":
        return

    for item in doc.items:
        mr_name = item.get("material_request")
        mr_item_name = item.get("material_request_item")
        if not mr_name or not mr_item_name:
            continue

        mr_item = frappe.db.get_value(
            "Material Request Item", mr_item_name,
            ["qty", "received_qty"],
            as_dict=True,
        )
        if not mr_item:
            continue

        remaining = flt(mr_item.qty) - flt(mr_item.received_qty)
        if flt(item.qty) > remaining + 0.01:
            frappe.throw(
                _("Row {0}: Transfer qty {1} for {2} exceeds remaining "
                  "Material Request qty {3} (requested {4}, already received {5}).").format(
                    item.idx, item.qty, item.item_code,
                    remaining, mr_item.qty, mr_item.received_qty,
                )
            )


# ─── Stock Entry submit notification ─────────────────────────────────────────

def notify_store_on_transfer(doc, method=None):
    """Notify store when a Stock Entry is submitted against their MR.

    Called from doc_events on Stock Entry on_submit.
    """
    if doc.stock_entry_type != "Material Transfer":
        return

    # Collect unique MR names from items
    mr_names = set()
    for item in doc.items:
        if item.get("material_request"):
            mr_names.add(item.material_request)

    for mr_name in mr_names:
        mr = frappe.db.get_value(
            "Material Request", mr_name,
            ["custom_store", "owner"],
            as_dict=True,
        )
        if mr and mr.custom_store:
            _send_notification(
                recipients=[mr.owner],
                subject=_("Stock Transfer {0} dispatched for {1}").format(
                    doc.name, mr_name
                ),
                message=_("Stock Entry {0} has been submitted as a transfer "
                          "for your Material Request {1}.").format(
                    doc.name, mr_name
                ),
                reference_doctype="Stock Entry",
                reference_name=doc.name,
            )


# ─── Material Request status change notification ─────────────────────────────

def notify_on_mr_update(doc, method=None):
    """Notify store when MR status changes (e.g. Ordered, Partially Received).

    Called from doc_events on Material Request on_update.
    """
    if not doc.custom_store:
        return
    if doc.docstatus != 1:
        return

    old_status = doc.get_doc_before_save()
    if old_status and old_status.status != doc.status:
        _send_notification(
            recipients=[doc.owner],
            subject=_("Material Request {0} status: {1}").format(
                doc.name, doc.status
            ),
            message=_("Your Material Request {0} status changed from {1} to "
                      "{2}.").format(
                doc.name, old_status.status, doc.status
            ),
            reference_doctype="Material Request",
            reference_name=doc.name,
        )


# ─── Draft requests: list + append items ──────────────────────────────────────

@frappe.whitelist()
def get_draft_requests(pos_profile):
    """Return Draft store MRs that the store exec can still append items to."""
    frappe.has_permission("Material Request", "read", throw=True)
    store = _get_store_from_profile(pos_profile)
    if not store:
        return []

    drafts = frappe.get_all(
        "Material Request",
        filters={
            "custom_store": store,
            "docstatus": 0,
            "custom_approval_status": "Pending Approval",
        },
        fields=[
            "name", "custom_priority as priority",
            "custom_request_notes as notes",
            "schedule_date as required_by_date",
            "custom_request_datetime as request_datetime",
            "creation",
        ],
        order_by="creation desc",
        limit=10,
    )

    if not drafts:
        return drafts

    # Enrich with items
    names = [d["name"] for d in drafts]
    items = frappe.db.sql(
        """SELECT parent, item_code, item_name, qty, uom
           FROM `tabMaterial Request Item`
           WHERE parent IN %(names)s
           ORDER BY idx""",
        {"names": tuple(names)},
        as_dict=True,
    )
    items_map = {}
    for i in items:
        items_map.setdefault(i.parent, []).append(i)

    for d in drafts:
        d["items"] = items_map.get(d["name"], [])
        d["item_count"] = len(d["items"])

    return drafts


@frappe.whitelist()
def add_items_to_draft(request_name, items):
    """Add items to an existing Draft Material Request.

    If an item already exists in the MR, its qty is incremented.
    Otherwise a new row is appended.
    """
    frappe.has_permission("Material Request", "write", throw=True)
    doc = frappe.get_doc("Material Request", request_name)

    if doc.docstatus != 0:
        frappe.throw(_("Can only add items to Draft requests."))
    if doc.custom_approval_status not in ("Pending Approval", ""):
        frappe.throw(_("This request has already been {0}.").format(
            doc.custom_approval_status
        ))

    _validate_store_permission(doc.custom_store)
    rows = _load_rows(items)
    if not rows:
        frappe.throw(_("At least one item is required."))

    warehouse = doc.set_warehouse or (doc.items[0].warehouse if doc.items else None)
    schedule_date = doc.schedule_date or nowdate()

    for row in rows:
        item_code = row.get("item_code")
        qty = flt(row.get("qty") or row.get("requested_qty") or 0)
        if not item_code or qty <= 0:
            continue

        # Check if item already exists — increment qty
        existing = None
        for mri in doc.items:
            if mri.item_code == item_code:
                existing = mri
                break

        if existing:
            existing.qty = flt(existing.qty) + qty
        else:
            doc.append("items", {
                "item_code": item_code,
                "qty": qty,
                "uom": row.get("uom") or frappe.db.get_value(
                    "Item", item_code, "stock_uom"
                ) or "Nos",
                "warehouse": warehouse,
                "schedule_date": schedule_date,
            })

    doc.save()

    return {
        "name": doc.name,
        "item_count": len(doc.items),
        "items": [
            {"item_code": i.item_code, "item_name": i.item_name,
             "qty": i.qty, "uom": i.uom}
            for i in doc.items
        ],
    }


# ─── Capacity / allowed-stock check for POS ──────────────────────────────────

@frappe.whitelist()
def check_request_capacity(pos_profile, items):
    """Validate requested quantities against Warehouse Capacity rules.

    Returns per-item capacity info: max_qty, current_qty, headroom,
    and whether the requested qty would exceed capacity.
    """
    frappe.has_permission("Material Request", "read", throw=True)
    rows = _load_rows(items)
    if not rows:
        return {}

    warehouse = _get_warehouse_from_profile(pos_profile)
    if not warehouse:
        return {}

    result = {}

    for row in rows:
        item_code = row.get("item_code")
        requested_qty = flt(row.get("qty") or 0)
        if not item_code:
            continue

        item_group = frappe.db.get_value("Item", item_code, "item_group")

        # Fetch capacity rule (item-specific → item-group → catch-all)
        capacity = frappe.db.sql(
            """SELECT max_qty
               FROM `tabWarehouse Capacity`
               WHERE warehouse = %s
                 AND (
                     item = %s
                     OR (item IS NULL AND item_group = %s)
                     OR (item IS NULL AND item_group IS NULL)
                 )
               ORDER BY
                   CASE
                       WHEN item = %s THEN 1
                       WHEN item_group = %s THEN 2
                       ELSE 3
                   END
               LIMIT 1""",
            (warehouse, item_code, item_group, item_code, item_group),
            as_dict=True,
        )

        max_qty = flt(capacity[0].max_qty) if capacity else 0
        current_qty = flt(frappe.db.get_value(
            "Bin", {"warehouse": warehouse, "item_code": item_code}, "actual_qty"
        ))

        # Pending incoming from open MRs
        pending_qty = flt(frappe.db.sql(
            """SELECT SUM(mri.qty - IFNULL(mri.received_qty, 0))
               FROM `tabMaterial Request Item` mri
               JOIN `tabMaterial Request` mr ON mr.name = mri.parent
               WHERE mr.docstatus = 1
                 AND mr.status NOT IN ('Received','Transferred','Stopped','Cancelled')
                 AND mri.item_code = %s AND mri.warehouse = %s""",
            (item_code, warehouse),
        )[0][0] or 0)

        headroom = max(max_qty - current_qty - pending_qty, 0) if max_qty else 0

        info = {
            "item_code": item_code,
            "max_qty": max_qty,
            "current_qty": current_qty,
            "pending_qty": pending_qty,
            "headroom": headroom,
            "requested_qty": requested_qty,
            "has_capacity_rule": bool(capacity),
        }

        if max_qty and (current_qty + pending_qty + requested_qty) > max_qty:
            info["exceeds"] = True
            info["message"] = _(
                "{0}: Requesting {1} would exceed capacity. "
                "Max: {2}, Current stock: {3}, Pending: {4}, Headroom: {5}"
            ).format(item_code, requested_qty, max_qty, current_qty,
                     pending_qty, headroom)
        else:
            info["exceeds"] = False

        result[item_code] = info

    return result


@frappe.whitelist()
def get_zone_source_warehouse(pos_profile):
    """Return the zone source warehouse for a POS Profile's store."""
    store = _get_store_from_profile(pos_profile)
    source_wh = _get_zone_source_warehouse(store)
    zone = frappe.db.get_value("CH Store", store, "zone") if store else None
    return {
        "store": store,
        "zone": zone,
        "source_warehouse": source_wh,
    }
