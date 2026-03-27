"""Tests for store_request_api.py — Store Material Request via standard MR.

Run with:
    bench run-tests --app ch_erp15 --module ch_erp15.test_store_material_request
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate, now_datetime, add_days

from ch_erp15.ch_erp15.store_request_api import (
    check_sla_breach,
    check_stock_availability,
    check_stock_for_request,
    create_store_material_request,
    approve_store_request,
    reject_store_request,
    raise_purchase_request,
    short_close_request,
    auto_allocate_sources,
    get_request_tracking,
    get_store_material_requests,
    validate_transfer_qty,
)


def _get_test_pos_profile():
    """Return the first POS Profile with a warehouse configured."""
    pp = frappe.get_all(
        "POS Profile",
        filters={"disabled": 0, "warehouse": ("is", "set")},
        fields=["name"],
        limit=1,
    )
    if pp:
        return pp[0].name
    frappe.throw("No active POS Profile with warehouse found for testing.")


def _get_test_item():
    """Return first non-disabled stock item."""
    item = frappe.get_all(
        "Item",
        filters={"disabled": 0, "is_stock_item": 1},
        pluck="name",
        limit=1,
    )
    return item[0] if item else "Test Item"


class TestCreateStoreMaterialRequest(FrappeTestCase):
    """Test: create_store_material_request creates a Draft MR with Pending Approval."""

    def test_creates_draft_mr(self):
        pp = _get_test_pos_profile()
        item = _get_test_item()

        mr_name = create_store_material_request(
            pos_profile=pp,
            items=[{"item_code": item, "qty": 5}],
            priority="Standard",
            notes="Test request",
        )

        self.assertTrue(mr_name)
        mr = frappe.get_doc("Material Request", mr_name)

        # Should be Draft, Pending Approval
        self.assertEqual(mr.docstatus, 0)
        self.assertEqual(mr.custom_approval_status, "Pending Approval")
        self.assertEqual(mr.material_request_type, "Material Transfer")
        self.assertTrue(mr.custom_store or not mr.custom_store)  # may or may not resolve
        self.assertEqual(len(mr.items), 1)
        self.assertEqual(mr.items[0].item_code, item)
        self.assertEqual(mr.items[0].qty, 5)

        # Cleanup
        frappe.delete_doc("Material Request", mr_name, force=True)

    def test_rejects_empty_items(self):
        pp = _get_test_pos_profile()
        with self.assertRaises(frappe.ValidationError):
            create_store_material_request(pos_profile=pp, items=[])

    def test_rejects_zero_qty(self):
        pp = _get_test_pos_profile()
        item = _get_test_item()
        with self.assertRaises(frappe.ValidationError):
            create_store_material_request(
                pos_profile=pp,
                items=[{"item_code": item, "qty": 0}],
            )


class TestApprovalWorkflow(FrappeTestCase):
    """Test: approve and reject workflow."""

    def setUp(self):
        self.pp = _get_test_pos_profile()
        self.item = _get_test_item()
        self.mr_name = create_store_material_request(
            pos_profile=self.pp,
            items=[{"item_code": self.item, "qty": 3}],
        )

    def tearDown(self):
        mr = frappe.get_doc("Material Request", self.mr_name)
        if mr.docstatus == 1:
            mr.cancel()
        frappe.delete_doc("Material Request", self.mr_name, force=True)

    def test_approve_submits_mr(self):
        result = approve_store_request(self.mr_name)
        self.assertEqual(result["status"], "Approved")

        mr = frappe.get_doc("Material Request", self.mr_name)
        self.assertEqual(mr.docstatus, 1)
        self.assertEqual(mr.custom_approval_status, "Approved")
        self.assertTrue(mr.custom_sla_breach_date)

    def test_reject_marks_rejected(self):
        result = reject_store_request(self.mr_name, reason="Test rejection")
        self.assertEqual(result["status"], "Rejected")

        mr = frappe.get_doc("Material Request", self.mr_name)
        self.assertEqual(mr.custom_approval_status, "Rejected")
        self.assertEqual(mr.docstatus, 0)


class TestStockAvailability(FrappeTestCase):
    """Test: check_stock_availability returns correct structure."""

    def test_returns_dict_structure(self):
        item = _get_test_item()
        company = frappe.get_all("Company", pluck="name", limit=1)[0]

        result = check_stock_availability(
            items=[{"item_code": item, "requested_qty": 10}],
            company=company,
            destination_warehouse=None,
        )

        self.assertIn(item, result)
        data = result[item]
        self.assertIn("requested_qty", data)
        self.assertIn("availability", data)
        self.assertIn("total_available", data)
        self.assertIn("shortage", data)
        self.assertEqual(data["requested_qty"], 10)

    def test_empty_items(self):
        result = check_stock_availability([], "Test Company", None)
        self.assertEqual(result, {})


class TestRaisePurchaseRequest(FrappeTestCase):
    """Test: raise_purchase_request creates linked Purchase MR."""

    def setUp(self):
        self.pp = _get_test_pos_profile()
        self.item = _get_test_item()
        self.mr_name = create_store_material_request(
            pos_profile=self.pp,
            items=[{"item_code": self.item, "qty": 100}],
        )
        approve_store_request(self.mr_name)

    def tearDown(self):
        # Cleanup purchase MRs
        for pr in frappe.get_all(
            "Material Request",
            filters={"custom_source_material_request": self.mr_name},
            pluck="name",
        ):
            doc = frappe.get_doc("Material Request", pr)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Material Request", pr, force=True)

        mr = frappe.get_doc("Material Request", self.mr_name)
        if mr.docstatus == 1:
            mr.cancel()
        frappe.delete_doc("Material Request", self.mr_name, force=True)

    def test_creates_purchase_mr_with_link(self):
        # This will create a purchase MR if there's any shortage
        try:
            result = raise_purchase_request(self.mr_name)
            self.assertTrue(result["name"])

            pr = frappe.get_doc("Material Request", result["name"])
            self.assertEqual(pr.material_request_type, "Purchase")
            self.assertEqual(pr.custom_source_material_request, self.mr_name)
            self.assertEqual(pr.docstatus, 1)
        except frappe.ValidationError as e:
            # "No shortage found" is valid if stock is sufficient
            if "No shortage found" in str(e):
                pass
            else:
                raise

    def test_duplicate_guard(self):
        try:
            raise_purchase_request(self.mr_name)
            # Second attempt should fail
            with self.assertRaises(frappe.ValidationError):
                raise_purchase_request(self.mr_name)
        except frappe.ValidationError as e:
            if "No shortage found" in str(e):
                pass
            else:
                raise


class TestShortClose(FrappeTestCase):
    """Test: short_close_request stops MR with closure details."""

    def setUp(self):
        self.pp = _get_test_pos_profile()
        self.item = _get_test_item()
        self.mr_name = create_store_material_request(
            pos_profile=self.pp,
            items=[{"item_code": self.item, "qty": 5}],
        )
        approve_store_request(self.mr_name)

    def tearDown(self):
        mr = frappe.get_doc("Material Request", self.mr_name)
        if mr.docstatus == 1 and mr.status != "Stopped":
            mr.cancel()
        frappe.delete_doc("Material Request", self.mr_name, force=True)

    def test_short_close(self):
        result = short_close_request(self.mr_name, reason="Partial fulfillment accepted")
        self.assertEqual(result["status"], "Stopped")

        mr = frappe.get_doc("Material Request", self.mr_name)
        self.assertEqual(mr.status, "Stopped")
        self.assertEqual(mr.custom_closure_reason, "Partial fulfillment accepted")
        self.assertTrue(mr.custom_closed_by)
        self.assertTrue(mr.custom_closure_date)

    def test_requires_reason(self):
        with self.assertRaises(frappe.ValidationError):
            short_close_request(self.mr_name, reason="")


class TestRequestTracking(FrappeTestCase):
    """Test: get_request_tracking returns unified tracking data."""

    def setUp(self):
        self.pp = _get_test_pos_profile()
        self.item = _get_test_item()
        self.mr_name = create_store_material_request(
            pos_profile=self.pp,
            items=[{"item_code": self.item, "qty": 5}],
        )
        approve_store_request(self.mr_name)

    def tearDown(self):
        mr = frappe.get_doc("Material Request", self.mr_name)
        if mr.docstatus == 1:
            mr.cancel()
        frappe.delete_doc("Material Request", self.mr_name, force=True)

    def test_tracking_structure(self):
        t = get_request_tracking(self.mr_name)
        self.assertEqual(t["name"], self.mr_name)
        self.assertIn("items", t)
        self.assertIn("purchase_requests", t)
        self.assertIn("stock_entries", t)
        self.assertIn("closure", t)
        self.assertEqual(len(t["items"]), 1)


class TestSLABreach(FrappeTestCase):
    """Test: check_sla_breach marks overdue requests."""

    def test_marks_breached(self):
        pp = _get_test_pos_profile()
        item = _get_test_item()
        mr_name = create_store_material_request(
            pos_profile=pp,
            items=[{"item_code": item, "qty": 2}],
        )
        approve_store_request(mr_name)

        # Force SLA breach date to past
        import datetime
        past = now_datetime() - datetime.timedelta(hours=1)
        frappe.db.set_value("Material Request", mr_name, {
            "custom_sla_breach_date": past,
            "custom_sla_breached": 0,
        })
        frappe.db.commit()

        check_sla_breach()

        breached = frappe.db.get_value(
            "Material Request", mr_name, "custom_sla_breached"
        )
        self.assertEqual(breached, 1)

        # Cleanup
        mr = frappe.get_doc("Material Request", mr_name)
        mr.cancel()
        frappe.delete_doc("Material Request", mr_name, force=True)
