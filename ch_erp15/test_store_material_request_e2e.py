"""
Store Material Request end-to-end executable test.

Run:
bench --site erpnext.local execute ch_erp15.test_store_material_request_e2e.test_all
"""

import traceback

import frappe
from frappe.utils import flt, nowdate

from ch_erp15.ch_erp15 import store_request_api


results = []


def ok(name, detail=""):
    results.append({"scenario": name, "status": "PASS", "detail": detail})
    print(f"PASS  {name}{' - ' + detail if detail else ''}")


def fail(name, detail=""):
    results.append({"scenario": name, "status": "FAIL", "detail": detail})
    print(f"FAIL  {name}{' - ' + detail if detail else ''}")


def _find_context():
    pos_profiles = frappe.get_all(
        "POS Profile",
        filters={"disabled": 0},
        fields=["name", "company", "warehouse"],
        order_by="name asc",
        limit=20,
    )
    if not pos_profiles:
        return None

    for p in pos_profiles:
        store = frappe.db.get_value("POS Profile Extension", {"pos_profile": p.name}, "store")
        if not store and p.warehouse:
            store = frappe.db.get_value("CH Store", {"warehouse": p.warehouse}, "name")
        if not store:
            continue

        source_wh = frappe.db.get_value(
            "Warehouse",
            {"company": p.company, "name": ("!=", p.warehouse), "disabled": 0},
            "name",
        )

        item = frappe.db.sql(
            """SELECT b.item_code
               FROM `tabBin` b
               JOIN `tabItem` i ON i.name = b.item_code
               WHERE b.warehouse = %s
                 AND b.actual_qty > 0
                 AND i.is_stock_item = 1
                 AND i.disabled = 0
               ORDER BY b.actual_qty DESC
               LIMIT 1""",
            (p.warehouse,),
            as_dict=True,
        )
        if not item:
            continue

        return {
            "pos_profile": p.name,
            "company": p.company,
            "store": store,
            "destination_wh": p.warehouse,
            "source_wh": source_wh,
            "item_code": item[0].item_code,
        }

    return None


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


def test_all():
    frappe.set_user("Administrator")
    ctx = _find_context()
    if not ctx:
        raise Exception("No suitable POS profile/store/item context found for E2E test")

    print("Context:", ctx)

    created_docs = []

    try:
        scenario = "S1 create store material request"
        req_name = store_request_api.create_store_material_request(
            pos_profile=ctx["pos_profile"],
            items=[{"item_code": ctx["item_code"], "qty": 10}],
            priority="Standard",
            notes="E2E orchestration test",
            required_by_date=nowdate(),
        )
        created_docs.append(("CH Store Material Request", req_name))
        req = frappe.get_doc("CH Store Material Request", req_name)
        _assert(req.status == "Draft", "Request should be Draft on creation")
        _assert(req.destination_warehouse, "Destination warehouse should be auto-resolved")
        ok(scenario, req_name)

        scenario = "S2 store edit allowed before processing"
        req.items[0].requested_qty = 12
        req.save()
        _assert(flt(req.items[0].requested_qty) == 12, "Edit before processing should be allowed")
        ok(scenario)

        scenario = "S2a approval workflow"
        store_request_api.submit_for_approval(req_name)
        req.reload()
        _assert(req.status == "Pending Approval", "Status must be Pending Approval")

        store_request_api.approve_store_material_request(req_name)
        req.reload()
        _assert(req.status == "Approved", "Status must be Approved")
        _assert(req.approved_by, "Approved by must be set")
        ok(scenario)

        scenario = "S2b rejection workflow"
        req3_name = store_request_api.create_store_material_request(
            pos_profile=ctx["pos_profile"],
            items=[{"item_code": ctx["item_code"], "qty": 3}],
            priority="Low",
        )
        created_docs.append(("CH Store Material Request", req3_name))
        store_request_api.submit_for_approval(req3_name)
        store_request_api.reject_store_material_request(req3_name, "Budget constraint")
        req3 = frappe.get_doc("CH Store Material Request", req3_name)
        _assert(req3.status == "Rejected", "Status must be Rejected")
        _assert(req3.rejection_reason == "Budget constraint", "Rejection reason must be stored")
        ok(scenario)

        scenario = "S3 start processing locks store edit"
        store_request_api.start_store_material_request_processing(req_name)
        req.reload()
        _assert(req.status == "Under Review", "Status must move to Under Review")

        frappe.set_user(req.requested_by)
        edit_blocked = False
        try:
            locked = frappe.get_doc("CH Store Material Request", req_name)
            locked.request_notes = "Store edit after lock"
            locked.save()
        except Exception:
            edit_blocked = True
        finally:
            frappe.set_user("Administrator")

        _assert(edit_blocked, "Store edit must be blocked after processing starts")
        ok(scenario)

        scenario = "S3a stock availability check"
        stock_result = store_request_api.check_stock_for_request(req_name)
        _assert(isinstance(stock_result, dict), "Stock check must return dict")
        _assert(ctx["item_code"] in stock_result, "Item must be present in stock check result")
        ok(scenario, f"total_available={stock_result[ctx['item_code']].get('total_available', 0)}")

        scenario = "S3b auto-allocate sources"
        auto_result = store_request_api.auto_allocate_for_request(req_name)
        _assert(auto_result.get("plan_rows", 0) > 0, "Auto-allocate must create plan rows")
        req.reload()
        _assert(len(req.fulfillment_plan) > 0, "Fulfillment plan must have rows")
        ok(scenario, f"{auto_result['plan_rows']} plan rows")

        scenario = "S4 split allocation internal plus purchase"
        allocations = []
        if ctx.get("source_wh"):
            allocations.append({
                "item_code": ctx["item_code"],
                "source_type": "Warehouse",
                "source_location": ctx["source_wh"],
                "source_warehouse": ctx["source_wh"],
                "planned_qty": 5,
                "route_type": "Via Warehouse",
            })
        allocations.append({
            "item_code": ctx["item_code"],
            "source_type": "Supplier",
            "source_location": "Preferred Vendor",
            "planned_qty": 7 if ctx.get("source_wh") else 12,
            "route_type": "Direct To Store",
        })

        alloc_result = store_request_api.set_store_material_request_allocations(req_name, allocations)
        _assert(
            flt(alloc_result.get("total_planned_internal_qty")) + flt(alloc_result.get("total_planned_purchase_qty")) >= 12,
            "Planned qty must cover requested quantity",
        )
        ok(scenario)

        scenario = "S5 execution docs created"
        exec_result = store_request_api.create_store_material_request_execution_docs(req_name)
        created = exec_result.get("created") or []
        _assert(created, "Execution documents should be generated")
        for row in created:
            created_docs.append((row["doctype"], row["name"]))
        ok(scenario, f"{len(created)} docs")

        scenario = "S6 partial then full receipt with damage tracking"
        store_request_api.record_store_material_receipt(
            req_name,
            [{"item_code": ctx["item_code"], "received_qty": 5, "damaged_qty": 1, "short_qty": 0, "location": ctx["store"], "receipt_mode": "Internal Transfer"}],
        )
        req.reload()
        _assert(req.status == "Partially Received", "Status should be Partially Received after partial receipt")
        # Accepted = 5 - 1 damage = 4
        _assert(flt(req.total_received_qty) == 4, f"Total received should count accepted only (4), got {req.total_received_qty}")

        remaining = max(flt(req.total_requested_qty) - flt(req.total_received_qty), 0)
        if remaining > 0:
            store_request_api.record_store_material_receipt(
                req_name,
                [{"item_code": ctx["item_code"], "received_qty": remaining, "location": ctx["store"], "receipt_mode": "Direct To Store"}],
            )

        req.reload()
        _assert(req.status == "Fulfilled", "Request should auto-close to Fulfilled when all qty received")
        _assert(flt(req.percent_fulfilled) >= 99.99, "Fulfillment percent should be 100")
        ok(scenario)

        scenario = "S6a shortage qty computed"
        req4_name = store_request_api.create_store_material_request(
            pos_profile=ctx["pos_profile"],
            items=[{"item_code": ctx["item_code"], "qty": 100}],
            priority="Standard",
        )
        created_docs.append(("CH Store Material Request", req4_name))
        store_request_api.start_store_material_request_processing(req4_name)
        store_request_api.set_store_material_request_allocations(req4_name, [
            {"item_code": ctx["item_code"], "source_type": "Warehouse", "source_location": ctx.get("source_wh") or ctx["destination_wh"], "planned_qty": 10}
        ])
        req4 = frappe.get_doc("CH Store Material Request", req4_name)
        _assert(flt(req4.total_shortage_qty) == 90, f"Shortage should be 90, got {req4.total_shortage_qty}")
        ok(scenario)

        scenario = "S7 close by reason enforced"
        req2 = store_request_api.create_store_material_request(
            pos_profile=ctx["pos_profile"],
            items=[{"item_code": ctx["item_code"], "qty": 2}],
            priority="Low",
            notes="Closure reason validation",
            required_by_date=nowdate(),
        )
        created_docs.append(("CH Store Material Request", req2))
        store_request_api.start_store_material_request_processing(req2)

        reason_blocked = False
        try:
            store_request_api.close_store_material_request(req2, reason_code=None, reason_detail="no reason")
        except Exception:
            reason_blocked = True

        _assert(reason_blocked, "Closure must require reason code")

        close_res = store_request_api.close_store_material_request(
            req2,
            reason_code="Not Required",
            reason_detail="Store cancelled requirement",
            action="Closed",
        )
        _assert(close_res.get("status") == "Closed With Reason", "Status should be Closed With Reason")
        ok(scenario)

        scenario = "S8 SLA breach detection"
        req5_name = store_request_api.create_store_material_request(
            pos_profile=ctx["pos_profile"],
            items=[{"item_code": ctx["item_code"], "qty": 1}],
            priority="Urgent",
        )
        created_docs.append(("CH Store Material Request", req5_name))
        store_request_api.start_store_material_request_processing(req5_name)
        req5 = frappe.get_doc("CH Store Material Request", req5_name)
        _assert(req5.sla_breach_date, "SLA breach date should be set")
        ok(scenario)

    except Exception as exc:
        traceback.print_exc()
        fail("E2E failure", str(exc))

    finally:
        # Keep docs for auditability in QA by default; only roll back if explicit failure cleanup needed.
        frappe.db.commit()

    total = len(results)
    passed = len([r for r in results if r["status"] == "PASS"])
    failed = len([r for r in results if r["status"] == "FAIL"])
    print("\nSummary:")
    print(f"  Total : {total}")
    print(f"  PASS  : {passed}")
    print(f"  FAIL  : {failed}")

    if failed:
        raise Exception(f"Store material request E2E failed: {failed} scenarios")

    return {"total": total, "passed": passed, "failed": failed}
