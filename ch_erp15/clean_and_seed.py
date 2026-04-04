"""
Clean all test/transaction data and seed fresh masters for end-to-end testing.

Run with:
    bench --site erpnext.local execute ch_erp15.clean_and_seed.audit
    bench --site erpnext.local execute ch_erp15.clean_and_seed.clean
    bench --site erpnext.local execute ch_erp15.clean_and_seed.seed
    bench --site erpnext.local execute ch_erp15.clean_and_seed.run_all
"""
import frappe
from frappe.utils import flt

_ALLOWED_TABLES = frozenset({
	"tabBuyback Order Item", "tabBuyback Order Payment",
	"tabBuyback Inspection Test Result", "tabBuyback Inspection",
	"tabBuyback Order", "tabBuyback Assessment Diagnostic Test",
	"tabBuyback Assessment", "tabCH OTP Log",
	"tabPOS Opening Entry Detail", "tabPOS Opening Entry",
	"tabPOS Closing Entry Detail", "tabPOS Closing Entry",
	"tabSales Invoice Payment", "tabSales Invoice Item",
	"tabSales Invoice", "tabPayment Entry Reference",
	"tabPayment Entry", "tabGL Entry",
	"tabDynamic Link", "tabCustomer Credit Limit",
	"tabContact Phone", "tabContact Email",
	"tabContact", "tabCustomer",
	"tabSerial No", "tabItem", "tabItem Price",
	"tabGrade Master", "tabMode of Payment", "tabPOS Profile",
})


def _del(table, label=None, where="1=1"):
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"Table '{table}' not in allowed whitelist")
    try:
        frappe.db.sql("DELETE FROM `{table}` WHERE {where}".format(table=table, where=where))  # noqa: UP032
        cnt = frappe.db.sql("SELECT ROW_COUNT()")[0][0]
        print(f"  OK  {label or table:<42} : {cnt} deleted")
    except Exception as e:
        print(f"  ERR {label or table:<42} : {e}")


def _count(table):
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"Table '{table}' not in allowed whitelist")
    try:
        return frappe.db.sql("SELECT COUNT(*) FROM `{table}`".format(table=table))[0][0]  # noqa: UP032
    except Exception:
        return "?"


# ── AUDIT ─────────────────────────────────────────────────────────────────────

def audit():
    print("\n=== DATABASE AUDIT ===")
    for label, tbl in [
        ("Sales Invoice",       "tabSales Invoice"),
        ("Payment Entry",       "tabPayment Entry"),
        ("GL Entry",            "tabGL Entry"),
        ("POS Opening Entry",   "tabPOS Opening Entry"),
        ("Buyback Assessment",  "tabBuyback Assessment"),
        ("Buyback Inspection",  "tabBuyback Inspection"),
        ("Buyback Order",       "tabBuyback Order"),
        ("CH OTP Log",          "tabCH OTP Log"),
        ("Customer",            "tabCustomer"),
        ("Serial No",           "tabSerial No"),
        ("Item",                "tabItem"),
        ("Item Price",          "tabItem Price"),
        ("Grade Master",        "tabGrade Master"),
        ("Mode of Payment",     "tabMode of Payment"),
        ("POS Profile",         "tabPOS Profile"),
    ]:
        print(f"  {label:<30} {_count(tbl):>6}")

    print("\n=== CUSTOMERS ===")
    for c in frappe.db.sql("SELECT name, customer_name, mobile_no FROM `tabCustomer` ORDER BY creation", as_dict=True):
        print(f"  {c.name:<30} {(c.mobile_no or '')}")

    print("\n=== GRADE MASTERS ===")
    for g in frappe.db.sql("SELECT name, grade_name FROM `tabGrade Master` ORDER BY display_order", as_dict=True):
        print(f"  {g.name}  grade_name={g.grade_name}")

    print("\n=== PRICES (serial items) ===")
    rows = frappe.db.sql(
        "SELECT i.name, i.item_name, i.standard_rate, COALESCE(ip.price_list_rate,0) sp"
        " FROM `tabItem` i"
        " LEFT JOIN `tabItem Price` ip ON ip.item_code=i.name AND ip.price_list='Standard Selling'"
        " WHERE i.has_serial_no=1 AND i.disabled=0 ORDER BY i.name",
        as_dict=True,
    )
    for r in rows:
        print(f"  {r.name:<25} std=Rs{r.standard_rate:,.0f}  sell=Rs{r.sp:,.0f}  {r.item_name}")

    frappe.db.commit()


# ── CLEAN ─────────────────────────────────────────────────────────────────────

def clean():
    print("\n=== CLEAN: deleting all transaction/customer data ===")

    for tbl, label in [
        ("tabBuyback Order Item",               "Buyback Order Items"),
        ("tabBuyback Order Payment",            "Buyback Order Payments"),
        ("tabBuyback Inspection Test Result",   "Buyback Inspection Test Results"),
        ("tabBuyback Inspection",               "Buyback Inspections"),
        ("tabBuyback Order",                    "Buyback Orders"),
        ("tabBuyback Assessment Diagnostic Test","Buyback Assessment Diagnostics"),
        ("tabBuyback Assessment",               "Buyback Assessments"),
        ("tabCH OTP Log",                       "CH OTP Logs"),
        ("tabPOS Opening Entry Detail",         "POS Opening Entry Details"),
        ("tabPOS Opening Entry",                "POS Opening Entries"),
        ("tabPOS Closing Entry Detail",         "POS Closing Entry Details"),
        ("tabPOS Closing Entry",                "POS Closing Entries"),
        ("tabSales Invoice Payment",            "SI Payments"),
        ("tabSales Invoice Item",               "SI Items"),
        ("tabSales Invoice",                    "Sales Invoices"),
        ("tabPayment Entry Reference",          "Payment Entry Refs"),
        ("tabPayment Entry",                    "Payment Entries"),
    ]:
        _del(tbl, label)

    _del("tabGL Entry", "GL Entries (transactional)",
         "voucher_type IN ('Sales Invoice','Payment Entry','POS Opening Entry','POS Closing Entry')")

    # Reset serial nos
    try:
        frappe.db.sql(
            "UPDATE `tabSerial No` SET status='Active', customer=NULL, customer_name=NULL,"
            " sales_invoice=NULL, warranty_expiry_date=NULL, delivery_date=NULL"
        )
        n = frappe.db.sql("SELECT COUNT(*) FROM `tabSerial No` WHERE status='Active'")[0][0]
        print(f"  OK  {'Serial Nos reset to Active':<42} : {n} active")
    except Exception as e:
        print(f"  ERR Serial No reset: {e}")

    # Remove customers
    _del("tabDynamic Link", "Customer Dynamic Links", "link_doctype='Customer'")
    _del("tabCustomer Credit Limit", "Customer Credit Limits")
    _del("tabContact Phone", "Contact Phones")
    _del("tabContact Email", "Contact Emails")
    _del("tabContact", "Contacts")
    _del("tabCustomer", "Customers")

    frappe.db.commit()
    print("\n=== POST-CLEAN ===")
    for label, tbl in [
        ("Buyback Assessment", "tabBuyback Assessment"),
        ("Buyback Order",      "tabBuyback Order"),
        ("Customer",           "tabCustomer"),
        ("Sales Invoice",      "tabSales Invoice"),
        ("GL Entry",           "tabGL Entry"),
        ("Serial No (Active)", "tabSerial No"),
    ]:
        print(f"  {label:<30} {_count(tbl)}")
    print("  Clean done.")


# ── SEED ──────────────────────────────────────────────────────────────────────

def seed():
    print("\n=== SEED: ensuring all masters are ready ===")

    company = frappe.db.get_single_value("Global Defaults", "default_company") or "GoGizmo Retail Pvt Ltd"
    pos_name = frappe.db.sql("SELECT name FROM `tabPOS Profile` LIMIT 1")[0][0]
    pos = frappe.get_doc("POS Profile", pos_name)
    warehouse = pos.warehouse
    print(f"  Company={company}  POS={pos_name}  Warehouse={warehouse}")

    # 1. Walk-in Customer
    if not frappe.db.exists("Customer", "Walk-in Customer"):
        cg  = frappe.db.sql("SELECT name FROM `tabCustomer Group` WHERE is_group=0 ORDER BY name LIMIT 1")[0][0]
        terr = frappe.db.sql("SELECT name FROM `tabTerritory` WHERE is_group=0 ORDER BY name LIMIT 1")[0][0]
        c = frappe.new_doc("Customer")
        c.customer_name = "Walk-in Customer"
        c.customer_type = "Company"
        c.customer_group = cg
        c.territory = terr
        c.flags.ignore_permissions = True
        c.insert()
        frappe.db.commit()
        print("  Walk-in Customer created")
    else:
        print("  Walk-in Customer OK")

    # 2. Grade Masters (columns: grade_name, grade_id, display_order)
    grade_cols = [r[0] for r in frappe.db.sql("DESCRIBE `tabGrade Master`")]
    grades = [
        dict(grade_name="A", grade_id=1, display_order=1, price_factor=0.85, min_score=85),
        dict(grade_name="B", grade_id=2, display_order=2, price_factor=0.65, min_score=65),
        dict(grade_name="C", grade_id=3, display_order=3, price_factor=0.45, min_score=40),
        dict(grade_name="D", grade_id=4, display_order=4, price_factor=0.20, min_score=0),
    ]
    for g in grades:
        row = frappe.db.sql("SELECT name FROM `tabGrade Master` WHERE grade_name=%s", g["grade_name"])
        if not row:
            doc = frappe.new_doc("Grade Master")
            doc.grade_name  = g["grade_name"]
            doc.grade_id    = g["grade_id"]
            doc.display_order = g["display_order"]
            if "price_factor" in grade_cols:
                doc.price_factor = g["price_factor"]
            if "min_score" in grade_cols:
                doc.min_score = g["min_score"]
            doc.flags.ignore_permissions = True
            doc.insert()
            frappe.db.commit()
            print(f"  Grade {g['grade_name']} created")
        else:
            if "price_factor" in grade_cols:
                frappe.db.set_value("Grade Master", row[0][0], "price_factor", g["price_factor"])
            print(f"  Grade {g['grade_name']} OK ({row[0][0]})")

    # 3. Item Prices in Standard Selling for serial-tracked items
    price_map = {
        # Phones
        "DEVICE-SAMSUNG-S23":  74999,
        "QAP000001":           69999,   # iPhone 15
        "QAP000001-R":         55000,   # iPhone 15 Refurbished
        "QAP000002":           59999,   # iPhone 14
        "QAP000003":           49999,   # iPhone 13
        "QAP000004":           65999,   # Samsung S24
        "QAP000004-R":         42000,   # Samsung S24 Refurbished
        "QAP000005":           54999,   # Samsung S23
        "QAP000006":           24999,   # Samsung A34
        "QAP000007":           55999,   # Google Pixel 8
        "QAP000007-R":         28000,   # Google Pixel 8 Pre-Owned
        "QAP000008":           52999,   # OnePlus 12
        "QAP000009":           29999,   # Oppo Reno 12
        "QAP000010":           44999,   # Xiaomi 14
        # Tablets
        "QAT000001":           65999,   # iPad Air
        "QAT000001-R":         38000,   # iPad Air Refurbished
        "QAT000002":           99999,   # iPad Pro
        "QAT000003":           74999,   # Samsung Tab S9
        "QAT000004":           29999,   # Lenovo Tab P12
        "QAT000005":           24999,   # Xiaomi Pad 6
        # Laptops
        "QAL000001":          124999,   # MacBook Pro M3
        "QAL000002":           89999,   # MacBook Air M2
        "QAL000003":           84999,   # Dell XPS 15
        "QAL000004":           79999,   # HP Spectre
        "QAL000005":           74999,   # Lenovo ThinkPad
    }
    for item_code, rate in price_map.items():
        if not frappe.db.exists("Item", item_code):
            continue
        existing = frappe.db.sql(
            "SELECT name FROM `tabItem Price` WHERE item_code=%s AND price_list='Standard Selling'",
            item_code,
        )
        if not existing:
            ip = frappe.new_doc("Item Price")
            ip.item_code = item_code
            ip.price_list = "Standard Selling"
            ip.price_list_rate = rate
            ip.currency = "INR"
            ip.flags.ignore_permissions = True
            ip.insert()
            frappe.db.commit()
            print(f"  Item Price created: {item_code} = Rs{rate:,}")
        else:
            frappe.db.set_value("Item Price", existing[0][0], "price_list_rate", rate)
            print(f"  Item Price OK     : {item_code} = Rs{rate:,}")

    # 4. POS Profile payment modes
    pos = frappe.get_doc("POS Profile", pos_name)
    existing_modes = {p.mode_of_payment for p in (pos.payments or [])}
    changed = False
    for mode, default in [("Cash", 1), ("UPI", 0), ("Credit Card", 0)]:
        if mode not in existing_modes and frappe.db.exists("Mode of Payment", mode):
            acct = frappe.db.sql(
                "SELECT default_account FROM `tabMode of Payment Account`"
                " WHERE parent=%s AND company=%s LIMIT 1",
                (mode, company),
            )
            pos.append("payments", {
                "mode_of_payment": mode,
                "account": acct[0][0] if acct else None,
                "default": default,
            })
            changed = True
            print(f"  Added {mode} to POS Profile")
    if changed:
        pos.flags.ignore_permissions = True
        pos.save()
        frappe.db.commit()
    else:
        print(f"  POS payments OK: {', '.join(sorted(existing_modes))}")

    # 5. Put serial nos in POS warehouse if none are there
    in_wh = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabSerial No` WHERE warehouse=%s AND status='Active'",
        warehouse,
    )[0][0]
    total_active = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabSerial No` WHERE status='Active'"
    )[0][0]

    if in_wh == 0 and total_active > 0:
        frappe.db.sql("UPDATE `tabSerial No` SET warehouse=%s WHERE status='Active'", warehouse)
        frappe.db.commit()
        print(f"  Moved {total_active} serial nos to {warehouse}")
    else:
        print(f"  Serial Nos: {total_active} active, {in_wh} in {warehouse}")

    # 6. Summary
    ip_count = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabItem Price` WHERE price_list='Standard Selling'"
    )[0][0]
    serial_in_wh = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabSerial No` WHERE status='Active' AND warehouse=%s", warehouse
    )[0][0]

    print("\n=== READY FOR TESTING ===")
    print(f"  Walk-in Customer : {'YES' if frappe.db.exists('Customer','Walk-in Customer') else 'MISSING'}")
    print(f"  Grade Masters    : {_count('tabGrade Master')}")
    print(f"  Item Prices (SP) : {ip_count}")
    print(f"  Serial Nos in WH : {serial_in_wh} (in {warehouse})")
    print()
    print("  FLOW: Create Customer -> Open POS -> Sell device -> complete")
    print("        Then Buyback panel -> find customer -> New Assessment -> Inspect -> Approve -> Settle")


def run_all():
    audit()
    print("\n" + "=" * 60)
    clean()
    print("\n" + "=" * 60)
    seed()
