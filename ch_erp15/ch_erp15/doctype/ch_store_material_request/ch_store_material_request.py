import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, flt, now_datetime, nowdate


STORE_EDITABLE_STATUSES = {"Draft", "Pending Approval", "Rejected"}
CLOSED_STATUSES = {"Closed With Reason", "Cancelled", "Fulfilled"}

# SLA hours by priority
SLA_HOURS = {"Urgent": 4, "Standard": 24, "Low": 72}


class CHStoreMaterialRequest(Document):
    def before_insert(self):
        if not self.requested_by:
            self.requested_by = frappe.session.user
        if not self.status:
            self.status = "Draft"
        self._resolve_destination_warehouse()

    def validate(self):
        self._validate_items()
        self._validate_edit_lock()
        self._resolve_destination_warehouse()
        self._recompute_totals()

    def on_trash(self):
        if self.status not in STORE_EDITABLE_STATUSES:
            frappe.throw(_("Request can only be deleted while in Draft/Pending Approval status."))

    # ─── Resolution helpers ───────────────────────────────────────────

    def _resolve_destination_warehouse(self):
        if self.destination_warehouse:
            return
        wh = None
        if self.pos_profile:
            wh = frappe.db.get_value("POS Profile", self.pos_profile, "warehouse")
        if not wh and self.store:
            wh = frappe.db.get_value("CH Store", self.store, "warehouse")
        self.destination_warehouse = wh

    # ─── Validation ───────────────────────────────────────────────────

    def _validate_items(self):
        if not self.items:
            frappe.throw(_("At least one item is required."))

        for row in self.items:
            if flt(row.requested_qty) <= 0:
                frappe.throw(_("Requested qty must be greater than 0 for item {0}.").format(row.item_code))
            if not row.item_name:
                row.item_name = frappe.db.get_value("Item", row.item_code, "item_name") or row.item_code
            if not row.uom:
                row.uom = frappe.db.get_value("Item", row.item_code, "stock_uom") or "Nos"

    def _validate_edit_lock(self):
        if getattr(self.flags, "ignore_store_lock", False):
            return

        if self.is_new():
            return

        prev = self.get_doc_before_save()
        if not prev:
            return

        if prev.status not in STORE_EDITABLE_STATUSES:
            if frappe.session.user == self.requested_by:
                frappe.throw(_("Store can edit/delete this request only before stock team starts processing."))
            if frappe.has_role("System Manager") or frappe.has_role("Stock Manager") or frappe.has_role("Purchase Manager"):
                return
            frappe.throw(_("Only stock/purchase team can update this request after processing starts."))

    # ─── Approval workflow ────────────────────────────────────────────

    def submit_for_approval(self):
        if self.status not in ("Draft", "Rejected"):
            frappe.throw(_("Only Draft or Rejected requests can be submitted for approval."))
        self.status = "Pending Approval"

    def approve(self):
        if self.status != "Pending Approval":
            frappe.throw(_("Only Pending Approval requests can be approved."))
        self.status = "Approved"
        self.approved_by = frappe.session.user
        self.approved_on = now_datetime()
        for row in self.items:
            if not flt(row.approved_qty):
                row.approved_qty = flt(row.requested_qty)

    def reject(self, reason):
        if self.status != "Pending Approval":
            frappe.throw(_("Only Pending Approval requests can be rejected."))
        self.status = "Rejected"
        self.rejection_reason = reason
        for row in self.items:
            row.line_status = "Rejected"

    # ─── Totals & status ─────────────────────────────────────────────

    def _recompute_totals(self):
        requested = 0.0
        planned_internal = 0.0
        planned_purchase = 0.0
        received = 0.0
        shortage = 0.0

        per_item_internal = {}
        per_item_purchase = {}
        for plan in self.fulfillment_plan or []:
            qty = flt(plan.planned_qty)
            if qty <= 0:
                continue
            if plan.source_type in ("Store", "Warehouse"):
                per_item_internal[plan.item_code] = flt(per_item_internal.get(plan.item_code)) + qty
                planned_internal += qty
            elif plan.source_type == "Supplier":
                per_item_purchase[plan.item_code] = flt(per_item_purchase.get(plan.item_code)) + qty
                planned_purchase += qty

            # Compute pending on plan row
            plan.pending_qty = max(flt(plan.planned_qty) - flt(plan.received_qty), 0)

        per_item_received = {}
        for rec in self.receipts or []:
            qty = flt(rec.received_qty)
            if qty <= 0:
                continue
            # Auto-compute accepted_qty = received - damaged - short
            rec.accepted_qty = max(qty - flt(rec.damaged_qty) - flt(rec.short_qty), 0)
            per_item_received[rec.item_code] = flt(per_item_received.get(rec.item_code)) + flt(rec.accepted_qty)
            received += flt(rec.accepted_qty)

        for row in self.items:
            row.planned_internal_qty = flt(per_item_internal.get(row.item_code))
            row.planned_purchase_qty = flt(per_item_purchase.get(row.item_code))
            row.received_qty = flt(per_item_received.get(row.item_code))
            row.pending_qty = max(flt(row.requested_qty) - flt(row.received_qty), 0)
            total_planned = flt(row.planned_internal_qty) + flt(row.planned_purchase_qty)
            row.shortage_qty = max(flt(row.requested_qty) - total_planned, 0)
            shortage += flt(row.shortage_qty)

            requested += flt(row.requested_qty)
            row.line_status = self._compute_line_status(row)

        self.total_requested_qty = requested
        self.total_planned_internal_qty = planned_internal
        self.total_planned_purchase_qty = planned_purchase
        self.total_received_qty = received
        self.total_shortage_qty = shortage
        self.percent_fulfilled = (received / requested * 100.0) if requested else 0

        self._derive_status()
        self._check_sla()

    def _compute_line_status(self, row):
        if self.status in ("Rejected",):
            return "Rejected"
        if flt(row.received_qty) >= flt(row.requested_qty) and flt(row.requested_qty) > 0:
            return "Fulfilled"
        if flt(row.received_qty) > 0:
            return "Partially Received"
        if self.status in CLOSED_STATUSES:
            return "Short Closed" if flt(row.pending_qty) > 0 else "Closed"
        total_planned = flt(row.planned_internal_qty) + flt(row.planned_purchase_qty)
        if total_planned > 0:
            # Check if any plan row for this item is In Transit
            for plan in self.fulfillment_plan or []:
                if plan.item_code == row.item_code and plan.status == "In Transit":
                    return "In Transit"
            return "Allocated"
        if self.status == "Approved":
            return "Approved"
        return "Pending"

    def _derive_status(self):
        if self.status in ("Closed With Reason", "Cancelled", "Pending Approval", "Rejected"):
            return

        if self.total_requested_qty and self.total_received_qty >= self.total_requested_qty:
            self.status = "Fulfilled"
            return

        if self.total_received_qty > 0:
            self.status = "Partially Received"
            return

        # Check if any plan row is In Transit
        has_in_transit = any(
            plan.status == "In Transit" for plan in (self.fulfillment_plan or [])
        )
        if has_in_transit:
            self.status = "In Transit"
            return

        planned_total = flt(self.total_planned_internal_qty) + flt(self.total_planned_purchase_qty)

        if not self.processed_by_stock_team:
            if self.status not in ("Approved",):
                self.status = "Draft"
            return

        if planned_total <= 0:
            self.status = "Under Review"
        elif planned_total < flt(self.total_requested_qty):
            if flt(self.total_planned_purchase_qty) > 0:
                self.status = "Procurement Initiated"
            else:
                self.status = "Partially Allocated"
        elif flt(self.total_planned_purchase_qty) > 0 and flt(self.total_planned_internal_qty) <= 0:
            self.status = "Procurement Initiated"
        elif flt(self.total_planned_internal_qty) > 0:
            self.status = "Allocation Planned"
        else:
            self.status = "Under Review"

    def _check_sla(self):
        if self.status in CLOSED_STATUSES or not self.processing_started_on:
            return
        hours = SLA_HOURS.get(self.priority, 24)
        import datetime
        breach_dt = self.processing_started_on + datetime.timedelta(hours=hours)
        self.sla_breach_date = breach_dt
        if now_datetime() > breach_dt and self.status not in CLOSED_STATUSES:
            self.sla_breached = 1

    # ─── Stock team actions ──────────────────────────────────────────

    def start_processing(self):
        if self.status not in ("Draft", "Approved"):
            frappe.throw(_("Only Draft or Approved requests can be moved to processing."))
        self.processed_by_stock_team = 1
        self.processing_started_by = frappe.session.user
        self.processing_started_on = now_datetime()
        self.status = "Under Review"

    def apply_fulfillment_plan(self, plan_rows):
        if self.status == "Draft":
            frappe.throw(_("Start processing before setting fulfillment plan."))
        if self.status in ("Closed With Reason", "Cancelled", "Fulfilled"):
            frappe.throw(_("Cannot change fulfillment plan for closed/fulfilled request."))

        self.set("fulfillment_plan", [])
        item_qty_map = {row.item_code: flt(row.requested_qty) for row in self.items}

        # Over-allocation check: aggregate planned qty per item
        per_item_planned = {}
        for raw in plan_rows:
            item_code = raw.get("item_code")
            if item_code not in item_qty_map:
                frappe.throw(_("Plan item {0} is not present in request lines.").format(item_code))

            planned_qty = flt(raw.get("planned_qty"))
            if planned_qty <= 0:
                frappe.throw(_("Planned qty must be greater than 0 for {0}.").format(item_code))

            per_item_planned[item_code] = flt(per_item_planned.get(item_code)) + planned_qty

            self.append("fulfillment_plan", {
                "item_code": item_code,
                "source_type": raw.get("source_type") or "Warehouse",
                "source_location": raw.get("source_location"),
                "source_warehouse": raw.get("source_warehouse"),
                "source_store": raw.get("source_store"),
                "planned_qty": planned_qty,
                "route_type": raw.get("route_type") or "Via Warehouse",
                "expected_date": raw.get("expected_date"),
                "notes": raw.get("notes"),
                "status": "Planned",
            })

        # Warn (not block) if total planned > requested for an item
        for item_code, total_planned in per_item_planned.items():
            if total_planned > item_qty_map.get(item_code, 0):
                frappe.msgprint(
                    _("Warning: Total planned qty ({0}) exceeds requested qty ({1}) for {2}.").format(
                        total_planned, item_qty_map[item_code], item_code
                    ),
                    indicator="orange",
                )

    def add_receipts(self, receipt_rows):
        if self.status in ("Closed With Reason", "Cancelled"):
            frappe.throw(_("Cannot add receipts to a closed/cancelled request."))

        for raw in receipt_rows:
            received_qty = flt(raw.get("received_qty"))
            if received_qty <= 0:
                frappe.throw(_("Received qty must be greater than 0."))
            self.append("receipts", {
                "item_code": raw.get("item_code"),
                "received_qty": received_qty,
                "damaged_qty": flt(raw.get("damaged_qty")),
                "short_qty": flt(raw.get("short_qty")),
                "receipt_date": raw.get("receipt_date") or nowdate(),
                "location": raw.get("location"),
                "receipt_mode": raw.get("receipt_mode") or "Internal Transfer",
                "reference_doctype": raw.get("reference_doctype"),
                "reference_docname": raw.get("reference_docname"),
                "received_by": raw.get("received_by") or frappe.session.user,
                "fulfillment_plan_row": raw.get("fulfillment_plan_row"),
                "remarks": raw.get("remarks"),
            })

    def close_with_reason(self, reason_code, reason_detail=None, action="Closed"):
        if not reason_code:
            frappe.throw(_("Closure reason is mandatory."))

        self.closure_reason_code = reason_code
        self.closure_reason_detail = reason_detail
        self.closed_by = frappe.session.user
        self.closed_on = now_datetime()

        if action == "Cancelled":
            self.status = "Cancelled"
        else:
            self.status = "Closed With Reason"

        self.append("closure_log", {
            "action": "Cancelled" if action == "Cancelled" else "Closed",
            "reason_code": reason_code,
            "reason_detail": reason_detail,
            "actor": frappe.session.user,
            "action_time": now_datetime(),
        })


# ─── Stock availability check (used by API) ─────────────────────────

def check_stock_availability(items, company, destination_warehouse):
    """Check stock across all warehouses for the given items.

    Returns a dict keyed by item_code with availability per warehouse:
    {
        "ITEM-001": {
            "requested_qty": 10,
            "availability": [
                {"warehouse": "Central - G", "available_qty": 5, "is_destination": False},
                {"warehouse": "Anna Nagar - G", "available_qty": 3, "is_destination": False},
            ],
            "total_available": 8,
            "shortage": 2,
        }
    }
    """
    from erpnext.stock.utils import get_stock_balance

    result = {}
    item_codes = [r.get("item_code") for r in items if r.get("item_code")]
    if not item_codes:
        return result

    # Get all warehouses for this company (leaf warehouses only)
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

        # Sort: destination warehouse excluded, then central/main warehouses first, then by qty desc
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
    """Auto-generate a fulfillment plan using source prioritization.

    Priority order:
    1. Central/main warehouse (largest stock first)
    2. Other store warehouses (largest stock first)
    3. Supplier (for shortage)
    """
    stock_data = check_stock_availability(items, company, destination_warehouse)
    plan_rows = []

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

            # Determine if this is the central warehouse or a store
            store = frappe.db.get_value("CH Store", {"warehouse": source["warehouse"]}, "name")
            source_type = "Store" if store else "Warehouse"

            plan_rows.append({
                "item_code": item_code,
                "source_type": source_type,
                "source_location": source["warehouse"],
                "source_warehouse": source["warehouse"],
                "source_store": store or "",
                "planned_qty": alloc_qty,
                "route_type": "Via Warehouse" if source_type == "Warehouse" else "Direct To Store",
            })
            remaining -= alloc_qty

        # Remaining goes to purchase
        if remaining > 0:
            plan_rows.append({
                "item_code": item_code,
                "source_type": "Supplier",
                "source_location": "",
                "planned_qty": remaining,
                "route_type": "Via Warehouse",
            })

    return plan_rows, stock_data
