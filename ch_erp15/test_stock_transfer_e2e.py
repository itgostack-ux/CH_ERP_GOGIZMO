"""
Stock Transfer (Material Transfer) end-to-end executable test.

Covers the full transit workflow including:
  - SE creation, submission, set_pending_qty (stock → transit)
  - Scan & Send (received_qty barcode scan)
  - Logistics pickup, deliver, revert
  - POS scan-receive (IMEI/barcode) & confirm receive (transit → store)
  - Partial transfer handling

Run:
  bench --site erpnext.local execute ch_erp15.test_stock_transfer_e2e.test_all
"""

import traceback

import frappe
from frappe.utils import flt, nowdate, nowtime

from ch_erp15.ch_erp15.custom import stock_entry as se_api

results = []


def ok(name, detail=""):
    results.append({"scenario": name, "status": "PASS", "detail": detail})
    print(f"PASS  {name}{' - ' + detail if detail else ''}")


def fail(name, detail=""):
    results.append({"scenario": name, "status": "FAIL", "detail": detail})
    print(f"FAIL  {name}{' - ' + detail if detail else ''}")


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


def _find_context():
    """Find a company, source warehouse, target warehouse, and items with stock + barcodes."""
    companies = frappe.get_all("Company", filters={"is_group": 0}, pluck="name", limit=20)
    for company in companies:
        abbr = frappe.get_cached_value("Company", company, "abbr")
        transit_wh = f"Goods In Transit - {abbr}"
        if not frappe.db.exists("Warehouse", transit_wh):
            continue

        # Find two different non-group warehouses with stock
        warehouses = frappe.get_all(
            "Warehouse",
            filters={"company": company, "disabled": 0, "is_group": 0,
                      "name": ("not like", "Goods In Transit%")},
            pluck="name",
            limit=100,
        )
        if len(warehouses) < 2:
            continue

        # Find an item with stock >= 8 in any warehouse (we need qty for multiple test SEs)
        for s_wh in warehouses:
            items_with_stock = frappe.db.sql(
                """SELECT b.item_code, b.actual_qty
                   FROM `tabBin` b
                   JOIN `tabItem` i ON i.name = b.item_code
                   WHERE b.warehouse = %s
                     AND b.actual_qty >= 8
                     AND i.is_stock_item = 1
                     AND i.disabled = 0
                   ORDER BY b.actual_qty DESC
                   LIMIT 10""",
                (s_wh,),
                as_dict=True,
            )
            for item_row in items_with_stock:
                barcode = frappe.db.get_value(
                    "Item Barcode", {"parent": item_row.item_code}, "barcode"
                )
                created_barcode = False
                if not barcode:
                    # Create a test barcode for this item
                    barcode = f"TEST-E2E-{item_row.item_code[:20]}"
                    item_doc = frappe.get_doc("Item", item_row.item_code)
                    item_doc.append("barcodes", {"barcode": barcode})
                    item_doc.flags.ignore_validate = True
                    item_doc.save(ignore_permissions=True)
                    frappe.db.commit()
                    created_barcode = True

                # Find a different warehouse as target
                t_wh = next((w for w in warehouses if w != s_wh), None)
                if not t_wh:
                    continue

                return {
                    "company": company,
                    "s_warehouse": s_wh,
                    "t_warehouse": t_wh,
                    "transit_warehouse": transit_wh,
                    "item_code": item_row.item_code,
                    "available_qty": item_row.available_qty if hasattr(item_row, 'available_qty') else item_row.actual_qty,
                    "barcode": barcode,
                    "created_barcode": created_barcode,
                }

    return None


def _create_se(ctx, qty=2):
    """Create and submit a Material Transfer Stock Entry."""
    se = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Transfer",
        "company": ctx["company"],
        "from_warehouse": ctx["s_warehouse"],
        "to_warehouse": ctx["t_warehouse"],
        "posting_date": nowdate(),
        "posting_time": nowtime(),
        "items": [{
            "item_code": ctx["item_code"],
            "qty": qty,
            "s_warehouse": ctx["s_warehouse"],
            "t_warehouse": ctx["t_warehouse"],
            "custom_quantity": qty,
        }],
    })
    se.insert(ignore_permissions=True)
    se.submit()
    return se.name


def _cleanup(created_docs, ctx=None):
    """Best-effort cleanup of test documents."""
    for dt, dn in reversed(created_docs):
        try:
            doc = frappe.get_doc(dt, dn)
            if doc.docstatus == 1:
                # For SEs with custom_status, revert transit stock first if needed
                if dt == "Stock Entry" and doc.custom_status in (
                    "Pending With Goods", "Ready For Pickup", "In Transit",
                    "Ready For Receive", "Receive At Transit",
                ):
                    try:
                        se_api.revert_goods(dn)
                    except Exception:
                        pass
                    doc.reload()
                if doc.docstatus == 1:
                    doc.flags.ignore_permissions = True
                    doc.cancel()
            frappe.delete_doc(dt, dn, force=True, ignore_permissions=True)
            print(f"  Cleaned: {dt} {dn}")
        except Exception:
            pass

    # Remove test barcode if we created one
    if ctx and ctx.get("created_barcode"):
        try:
            frappe.db.sql(
                "DELETE FROM `tabItem Barcode` WHERE parent=%s AND barcode=%s",
                (ctx["item_code"], ctx["barcode"]),
            )
            print(f"  Cleaned barcode: {ctx['barcode']}")
        except Exception:
            pass

    frappe.db.commit()


def _get_bin_qty(item_code, warehouse):
    return flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty"))


def test_all():
    frappe.set_user("Administrator")
    global results
    results = []
    ctx = _find_context()
    if not ctx:
        raise Exception(
            "No suitable context found. Need: company with transit warehouse, "
            "2 warehouses, item with stock ≥3 and a barcode."
        )

    print(f"\nContext:")
    print(f"  Company        : {ctx['company']}")
    print(f"  Source WH      : {ctx['s_warehouse']}")
    print(f"  Target WH      : {ctx['t_warehouse']}")
    print(f"  Transit WH     : {ctx['transit_warehouse']}")
    print(f"  Item           : {ctx['item_code']}")
    print(f"  Available Qty  : {ctx['available_qty']}")
    print(f"  Barcode        : {ctx['barcode']}")
    print()

    created_docs = []
    transfer_qty = 2

    try:
        # ── S1: Create & submit Stock Entry ─────────────────
        scenario = "S1 create material transfer SE"
        initial_src = _get_bin_qty(ctx["item_code"], ctx["s_warehouse"])
        se_name = _create_se(ctx, qty=transfer_qty)
        created_docs.append(("Stock Entry", se_name))
        se = frappe.get_doc("Stock Entry", se_name)
        _assert(se.docstatus == 1, "SE should be submitted")
        _assert(se.stock_entry_type == "Material Transfer", "Should be Material Transfer")
        _assert(not se.custom_status, f"custom_status should be empty after submit, got '{se.custom_status}'")
        ok(scenario, se_name)

        # ── S2: set_pending_qty (source → transit) ──────────
        scenario = "S2 set_pending_qty moves stock to transit"
        res = se_api.set_pending_qty(se_name)
        _assert(res["status"] == "Pending With Goods", f"Expected Pending With Goods, got {res['status']}")
        se.reload()
        _assert(se.custom_status == "Pending With Goods", "custom_status should be Pending With Goods")
        for item in se.items:
            _assert(flt(item.custom_pending_qty) == transfer_qty,
                    f"custom_pending_qty should be {transfer_qty}, got {item.custom_pending_qty}")

        # Verify stock moved: source reduced, transit increased
        src_after = _get_bin_qty(ctx["item_code"], ctx["s_warehouse"])
        transit_qty = _get_bin_qty(ctx["item_code"], ctx["transit_warehouse"])
        _assert(src_after < initial_src, "Source warehouse stock should decrease")
        _assert(transit_qty > 0, "Transit warehouse should have stock")
        ok(scenario, f"src: {initial_src}→{src_after}, transit: {transit_qty}")

        # ── S3: Scan & Send (received_qty barcode scan) ─────
        scenario = "S3 scan and send (barcode scan at warehouse)"
        for i in range(transfer_qty):
            res = se_api.received_qty(se_name, ctx["barcode"])
        se.reload()
        for item in se.items:
            _assert(flt(item.custom_receive_qty) == transfer_qty,
                    f"custom_receive_qty should be {transfer_qty}, got {item.custom_receive_qty}")
        ok(scenario, f"scanned {transfer_qty} items")

        # ── S4: Set status to Ready For Pickup ───────────────
        scenario = "S4 set status Ready For Pickup"
        se_api.set_custom_status(se_name, "Ready For Pickup")
        se.reload()
        _assert(se.custom_status == "Ready For Pickup", f"Expected Ready For Pickup, got {se.custom_status}")
        ok(scenario)

        # ── S5: Logistics pickup ─────────────────────────────
        scenario = "S5 logistics pickup"
        res = se_api.logistics_pickup(se_name, "Test Driver", pickup_photo=None)
        _assert(res["status"] == "In Transit", f"Expected In Transit, got {res['status']}")
        _assert(res["logistics_status"] == "In Transit", f"Expected logistics In Transit, got {res['logistics_status']}")
        se.reload()
        _assert(se.custom_logistics_person == "Test Driver", "Logistics person should be set")
        _assert(se.custom_pickup_datetime, "Pickup datetime should be set")
        ok(scenario)

        # ── S6: Logistics deliver ────────────────────────────
        scenario = "S6 logistics deliver"
        res = se_api.logistics_deliver(se_name, delivery_photo=None)
        _assert(res["status"] == "Ready For Receive", f"Expected Ready For Receive, got {res['status']}")
        _assert(res["logistics_status"] == "Delivered", f"Expected Delivered, got {res['logistics_status']}")
        se.reload()
        _assert(se.custom_delivery_datetime, "Delivery datetime should be set")
        ok(scenario)

        # ── S7: POS scan receive (IMEI/barcode) ─────────────
        scenario = "S7 POS scan receive"
        for i in range(transfer_qty):
            res = se_api.pos_scan_receive(se_name, ctx["barcode"])
            _assert(res.get("item_code") == ctx["item_code"],
                    f"Scanned item should be {ctx['item_code']}, got {res.get('item_code')}")
        se.reload()
        _assert(se.custom_status == "Receive At Transit",
                f"Status should be Receive At Transit, got {se.custom_status}")
        for item in se.items:
            _assert(flt(item.custom_final_received_qty) == transfer_qty,
                    f"custom_final_received_qty should be {transfer_qty}, got {item.custom_final_received_qty}")
        ok(scenario, f"scanned {transfer_qty} items")

        # ── S8: POS confirm receive (transit → target) ──────
        scenario = "S8 POS confirm receive"
        transit_before = _get_bin_qty(ctx["item_code"], ctx["transit_warehouse"])
        tgt_before = _get_bin_qty(ctx["item_code"], ctx["t_warehouse"])
        res = se_api.pos_confirm_receive(se_name)
        _assert(res["status"] == "Transferred", f"Expected Transferred, got {res['status']}")
        _assert(res["partial"] is False, "Should not be partial")

        # Verify stock moved: transit reduced, target increased
        transit_after = _get_bin_qty(ctx["item_code"], ctx["transit_warehouse"])
        tgt_after = _get_bin_qty(ctx["item_code"], ctx["t_warehouse"])
        _assert(tgt_after > tgt_before, "Target warehouse stock should increase")
        ok(scenario, f"transit: {transit_before}→{transit_after}, target: {tgt_before}→{tgt_after}")

        # ── S9: Revert flow ──────────────────────────────────
        # Create a new SE for revert testing
        scenario = "S9 revert request blocks receive"
        se2_name = _create_se(ctx, qty=2)
        created_docs.append(("Stock Entry", se2_name))
        se_api.set_pending_qty(se2_name)

        # Scan & send
        for i in range(2):
            se_api.received_qty(se2_name, ctx["barcode"])
        se_api.set_custom_status(se2_name, "Ready For Pickup")
        se_api.logistics_pickup(se2_name, "Revert Driver")

        # Request revert while in transit
        res = se_api.logistics_revert_request(se2_name, reason="Wrong shipment")
        _assert(res["logistics_status"] == "Revert Requested",
                f"Expected Revert Requested, got {res['logistics_status']}")

        # Try to receive — should be blocked
        blocked = False
        try:
            # Deliver first to get to Ready For Receive
            se_api.logistics_deliver(se2_name)
        except Exception as e:
            # Delivery should also be blocked if revert is requested
            # Actually logistics_deliver checks logistics_status == "In Transit" but it's now "Revert Requested"
            blocked = True

        if not blocked:
            # The deliver went through despite revert, let's try receive
            try:
                se_api.pos_scan_receive(se2_name, ctx["barcode"])
            except Exception as e:
                if "revert" in str(e).lower():
                    blocked = True
                else:
                    raise

        _assert(blocked, "Receive should be blocked when revert is requested")
        ok(scenario)

        # ── S10: Complete revert ─────────────────────────────
        scenario = "S10 complete revert returns stock to source"
        src_before_revert = _get_bin_qty(ctx["item_code"], ctx["s_warehouse"])
        se2 = frappe.get_doc("Stock Entry", se2_name)
        # If logistics_deliver failed (expected), status is still Revert Requested
        if se2.custom_logistics_status != "Revert Requested":
            se_api.logistics_revert_request(se2_name, reason="Wrong shipment again")

        res = se_api.logistics_revert_complete(se2_name)
        _assert(res["status"] == "Draft", f"Expected Draft, got {res['status']}")
        _assert(res["logistics_status"] == "Reverted", f"Expected Reverted, got {res['logistics_status']}")

        src_after_revert = _get_bin_qty(ctx["item_code"], ctx["s_warehouse"])
        _assert(src_after_revert > src_before_revert, "Source warehouse stock should increase after revert")
        se2.reload()
        for item in se2.items:
            _assert(flt(item.custom_pending_qty) == 0, "Pending qty should be reset to 0")
            _assert(flt(item.custom_receive_qty) == 0, "Receive qty should be reset to 0")
        ok(scenario, f"source: {src_before_revert}→{src_after_revert}")

        # ── S11: Partial transfer ────────────────────────────
        scenario = "S11 partial transfer"
        se3_name = _create_se(ctx, qty=2)
        created_docs.append(("Stock Entry", se3_name))
        se_api.set_pending_qty(se3_name)

        # Scan & send both
        for i in range(2):
            se_api.received_qty(se3_name, ctx["barcode"])

        se_api.set_custom_status(se3_name, "Ready For Pickup")
        se_api.logistics_pickup(se3_name, "Partial Driver")
        se_api.logistics_deliver(se3_name)

        # Only scan-receive 1 of 2
        se_api.pos_scan_receive(se3_name, ctx["barcode"])

        res = se_api.pos_confirm_receive(se3_name)
        _assert(res["status"] == "Partially Transferred",
                f"Expected Partially Transferred, got {res['status']}")
        _assert(res["partial"] is True, "Should be partial")

        se3 = frappe.get_doc("Stock Entry", se3_name)
        for item in se3.items:
            _assert(flt(item.custom_quantity) == 1,
                    f"Remaining qty should be 1, got {item.custom_quantity}")
            _assert(flt(item.custom_pending_qty) == 1,
                    f"Pending qty should be 1, got {item.custom_pending_qty}")
            _assert(flt(item.custom_receive_qty) == 0,
                    f"Receive qty should be reset to 0, got {item.custom_receive_qty}")
            _assert(flt(item.custom_final_received_qty) == 0,
                    f"Final received qty should be reset to 0, got {item.custom_final_received_qty}")
        ok(scenario)

        # ── S12: Scan over-qty blocked ───────────────────────
        scenario = "S12 scan over-qty blocked"
        se4_name = _create_se(ctx, qty=1)
        created_docs.append(("Stock Entry", se4_name))
        se_api.set_pending_qty(se4_name)
        se_api.received_qty(se4_name, ctx["barcode"])
        se_api.set_custom_status(se4_name, "Ready For Pickup")
        se_api.logistics_pickup(se4_name, "Over Driver")
        se_api.logistics_deliver(se4_name)
        se_api.pos_scan_receive(se4_name, ctx["barcode"])

        over_blocked = False
        try:
            se_api.pos_scan_receive(se4_name, ctx["barcode"])
        except Exception as e:
            if "already received" in str(e).lower():
                over_blocked = True
            else:
                raise
        _assert(over_blocked, "Over-qty scan should be blocked")
        ok(scenario)

        # ── S13: get_logistics_entries ────────────────────────
        scenario = "S13 get_logistics_entries"
        entries = se_api.get_logistics_entries()
        _assert(isinstance(entries, list), "Should return list")
        ok(scenario, f"{len(entries)} entries")

    except Exception as exc:
        traceback.print_exc()
        fail("E2E failure", str(exc))

    finally:
        _cleanup(created_docs, ctx)

    total = len(results)
    passed = len([r for r in results if r["status"] == "PASS"])
    failed = len([r for r in results if r["status"] == "FAIL"])
    print(f"\n{'='*60}")
    print(f"Stock Transfer E2E Summary:")
    print(f"  Total : {total}")
    print(f"  PASS  : {passed}")
    print(f"  FAIL  : {failed}")
    print(f"{'='*60}")

    if failed:
        raise Exception(f"Stock Transfer E2E failed: {failed} scenarios")

    return {"total": total, "passed": passed, "failed": failed}
