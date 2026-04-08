"""CH Transfer Manifest controller.

Lifecycle:
    Draft → Packed → Assigned → Pickup Started → In Transit → Delivered → Received → Closed
"""

import frappe
import random
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, cint, flt


class CHTransferManifest(Document):

    def validate(self):
        if not self.status:
            self.status = "Draft"
        self._populate_transfer_details()
        self._compute_totals()
        self._validate_transfers()

    def before_submit(self):
        if not self.transfers:
            frappe.throw(_("Add at least one Stock Entry to the manifest."))
        if self.status in ("Draft", None, ""):
            self.status = "Packed"

    def on_submit(self):
        self._update_stock_entries_manifest()

    def on_cancel(self):
        self.db_set("status", "Cancelled")
        self._clear_stock_entries_manifest()

    # ── Helpers ─────────────────────────────────────────────────────────

    def _populate_transfer_details(self):
        """Auto-fill warehouse, item count, MR link from each Stock Entry."""
        for row in self.transfers:
            if not row.stock_entry:
                continue
            se = frappe.db.get_value(
                "Stock Entry", row.stock_entry,
                ["from_warehouse", "to_warehouse",
                 "docstatus", "stock_entry_type"],
                as_dict=True,
            )
            if not se:
                frappe.throw(_("Stock Entry {0} not found.").format(row.stock_entry))
            if se.docstatus == 2:
                frappe.throw(_("Stock Entry {0} is cancelled.").format(row.stock_entry))
            if se.stock_entry_type != "Material Transfer":
                frappe.throw(
                    _("Stock Entry {0} is not a Material Transfer (type: {1}).").format(
                        row.stock_entry, se.stock_entry_type
                    )
                )
            row.from_warehouse = se.from_warehouse
            row.to_warehouse = se.to_warehouse
            # Get material_request from items (it's on the child table)
            row.material_request = frappe.db.get_value(
                "Stock Entry Detail",
                {"parent": row.stock_entry, "material_request": ("is", "set")},
                "material_request",
            ) or ""
            row.transfer_status = frappe.db.get_value(
                "Stock Entry", row.stock_entry, "custom_status"
            ) or "Draft"

            items = frappe.db.sql(
                """SELECT COUNT(*) as cnt, SUM(IFNULL(qty,0)) as total_qty
                   FROM `tabStock Entry Detail` WHERE parent=%s""",
                row.stock_entry, as_dict=True,
            )
            row.item_count = cint(items[0].cnt) if items else 0
            row.total_qty = flt(items[0].total_qty) if items else 0

    def _compute_totals(self):
        self.total_stock_entries = len(self.transfers)
        self.total_items = sum(cint(r.item_count) for r in self.transfers)
        self.total_qty = sum(flt(r.total_qty) for r in self.transfers)

    def _validate_transfers(self):
        """Ensure no Stock Entry is already on another active manifest."""
        seen = set()
        for row in self.transfers:
            if row.stock_entry in seen:
                frappe.throw(_("Duplicate Stock Entry {0} in manifest.").format(row.stock_entry))
            seen.add(row.stock_entry)

            existing = frappe.db.get_value(
                "CH Transfer Manifest Item",
                {
                    "stock_entry": row.stock_entry,
                    "parent": ("!=", self.name or ""),
                    "parenttype": "CH Transfer Manifest",
                },
                ["parent"],
            )
            if existing:
                parent_status = frappe.db.get_value("CH Transfer Manifest", existing, "docstatus")
                if parent_status == 1:
                    frappe.throw(
                        _("Stock Entry {0} is already in active manifest {1}.").format(
                            row.stock_entry, existing
                        )
                    )

    def _update_stock_entries_manifest(self):
        """Link Stock Entries back to this manifest via custom field."""
        for row in self.transfers:
            frappe.db.set_value(
                "Stock Entry", row.stock_entry,
                "custom_transfer_manifest", self.name,
                update_modified=False,
            )

    def _clear_stock_entries_manifest(self):
        for row in self.transfers:
            frappe.db.set_value(
                "Stock Entry", row.stock_entry,
                "custom_transfer_manifest", "",
                update_modified=False,
            )

    # ── Status Transitions (called from API) ───────────────────────────

    def assign_driver(self, driver, courier_partner=None, vehicle_number=None,
                      tracking_number=None, estimated_delivery_date=None):
        if self.status not in ("Packed",):
            frappe.throw(_("Can only assign driver when status is Packed."))
        self.driver = driver
        self.driver_name = frappe.db.get_value("Driver", driver, "full_name")
        self.driver_phone = frappe.db.get_value("Driver", driver, "cell_number")
        self.courier_partner = courier_partner or self.courier_partner
        self.vehicle_number = vehicle_number or self.vehicle_number
        self.tracking_number = tracking_number or self.tracking_number
        self.estimated_delivery_date = estimated_delivery_date
        self.status = "Assigned"
        self._generate_delivery_otp()
        self.flags.ignore_validate_update_after_submit = True
        self.save()

    def start_pickup(self, pickup_photo, lat=None, lng=None, notes=None):
        if self.status not in ("Assigned",):
            frappe.throw(_("Can only start pickup when status is Assigned."))
        if not pickup_photo:
            frappe.throw(_("Pickup photo is mandatory."))
        self.pickup_photo = pickup_photo
        self.pickup_datetime = now_datetime()
        self.pickup_lat = flt(lat)
        self.pickup_lng = flt(lng)
        self.pickup_notes = notes
        self.status = "In Transit"
        self.flags.ignore_validate_update_after_submit = True
        self.save()
        self._sync_logistics_status_to_entries("In Transit")

    def complete_delivery(self, delivery_photo, receiver_name, otp=None,
                          lat=None, lng=None):
        if self.status not in ("In Transit",):
            frappe.throw(_("Can only deliver when status is In Transit."))
        if not delivery_photo:
            frappe.throw(_("Delivery photo is mandatory."))
        if not receiver_name:
            frappe.throw(_("Receiver name is mandatory."))
        # OTP verification
        if self.delivery_otp:
            if not otp:
                frappe.throw(_("Delivery OTP is required."))
            if str(otp).strip() != str(self.delivery_otp).strip():
                frappe.throw(_("Invalid OTP. Please check and try again."))
            self.delivery_otp_verified = 1

        self.delivery_photo = delivery_photo
        self.delivery_datetime = now_datetime()
        self.delivery_lat = flt(lat)
        self.delivery_lng = flt(lng)
        self.receiver_name = receiver_name
        self.status = "Delivered"
        self.flags.ignore_validate_update_after_submit = True
        self.save()
        self._sync_logistics_status_to_entries("Delivered")

    def accept_delivery(self, received_by=None, damage_reported=False,
                        damage_notes=None, damage_photo=None):
        if self.status not in ("Delivered",):
            frappe.throw(_("Can only accept when status is Delivered."))
        self.received_by = received_by or frappe.session.user
        self.received_datetime = now_datetime()
        self.damage_reported = cint(damage_reported)
        self.damage_notes = damage_notes
        self.damage_photo = damage_photo
        self.status = "Received"
        self.flags.ignore_validate_update_after_submit = True
        self.save()

    def close_manifest(self):
        if self.status not in ("Received",):
            frappe.throw(_("Can only close when status is Received."))
        self.status = "Closed"
        self.flags.ignore_validate_update_after_submit = True
        self.save()

    # ── Private ─────────────────────────────────────────────────────────

    def _generate_delivery_otp(self):
        self.delivery_otp = str(random.randint(100000, 999999))

    def _sync_logistics_status_to_entries(self, logistics_status):
        """Push logistics status change to all child Stock Entries."""
        for row in self.transfers:
            frappe.db.set_value(
                "Stock Entry", row.stock_entry,
                "custom_logistics_status", logistics_status,
                update_modified=False,
            )
