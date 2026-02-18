import frappe
from frappe.model.document import Document
from frappe.utils import flt


class WarehouseCapacity(Document):
    pass


def validate_warehouse_capacity(doc, method=None):

    if not doc.get("items"):
        return

    checked = set()

    for row in doc.items:

        warehouse = row.get("t_warehouse") or row.get("warehouse")
        item_code = row.get("item_code")

        if not warehouse or not item_code:
            continue

        key = (warehouse, item_code)

        if key in checked:
            continue

        checked.add(key)

        # Get Item Group
        item_group = frappe.db.get_value("Item", item_code, "item_group")

        # Get Capacity Rule
        capacity = frappe.db.sql("""
            SELECT max_qty, max_amount
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
            LIMIT 1
        """, (warehouse, item_code, item_group, item_code, item_group),
           as_dict=True)

        if not capacity:
            continue

        rule = capacity[0]
        max_qty = flt(rule.get("max_qty"))
        max_amount = flt(rule.get("max_amount"))

        # Current Stock
        stock = frappe.db.get_value(
            "Bin",
            {"warehouse": warehouse, "item_code": item_code},
            ["actual_qty", "stock_value"],
            as_dict=True
        )

        current_qty = flt(stock.get("actual_qty")) if stock else 0
        current_value = flt(stock.get("stock_value")) if stock else 0

        incoming_qty = 0
        incoming_value = 0

        for r in doc.items:
            w = r.get("t_warehouse") or r.get("warehouse")

            if w == warehouse and r.get("item_code") == item_code:
                qty = flt(r.get("qty"))
                rate = flt(r.get("valuation_rate") or r.get("basic_rate") or r.get("rate"))

                if qty > 0:
                    incoming_qty += qty
                    incoming_value += qty * rate

        final_qty = current_qty + incoming_qty
        final_value = current_value + incoming_value

        # Quantity Check
        if max_qty and final_qty > max_qty:
            frappe.throw(
                f"""Quantity capacity exceeded

Warehouse : {warehouse}
Item      : {item_code}

Max Qty   : {max_qty}
Current   : {current_qty}
Incoming  : {incoming_qty}
After     : {final_qty}
"""
            )

        # Amount Check
        if max_amount and final_value > max_amount:
            frappe.throw(
                f"""Amount capacity exceeded

Warehouse : {warehouse}
Item      : {item_code}

Max Value : ₹{max_amount:,.2f}
Current   : ₹{current_value:,.2f}
Incoming  : ₹{incoming_value:,.2f}
After     : ₹{final_value:,.2f}
"""
            )
