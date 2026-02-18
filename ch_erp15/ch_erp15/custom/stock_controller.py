# import frappe
# from frappe.utils import flt


# def validate_group_stock_limit(doc, method=None):

#     TARGET_WAREHOUSE = "Kellys - GD"
#     MAX_ALLOWED_TOTAL_QTY = 3
#     TARGET_ITEM_GROUP = "Mobiles"

#     if not getattr(doc, "items", None):
#         return


#     current_total = frappe.db.sql("""
#         SELECT SUM(b.actual_qty)
#         FROM `tabBin` b
#         JOIN `tabItem` i ON b.item_code = i.name
#         WHERE b.warehouse = %s
#         AND i.item_group = %s
#     """, (TARGET_WAREHOUSE, TARGET_ITEM_GROUP))[0][0] or 0

#     current_total = flt(current_total)

#     frappe.logger().info(f"{current_total} current mobile stock")


#     incoming_total = 0

#     for item in doc.items:

#         warehouse = item.get("t_warehouse") or item.get("warehouse")

#         if warehouse != TARGET_WAREHOUSE:
#             continue

#         item_group = frappe.db.get_value("Item", item.item_code, "item_group")

#         if item_group != TARGET_ITEM_GROUP:
#             continue

#         qty = flt(item.get("qty"))

#         if qty > 0:
#             incoming_total += qty

#     frappe.logger().info(f"{incoming_total} incoming mobile qty")

  
#     final_total = current_total + incoming_total

#     frappe.logger().info(
#         f"Warehouse: {TARGET_WAREHOUSE} | "
#         f"Current Mobiles: {current_total} | "
#         f"Incoming: {incoming_total} | "
#         f"Final: {final_total}"
#     )


#     if final_total > MAX_ALLOWED_TOTAL_QTY:

#         frappe.throw(
#             f"❌ Mobile capacity exceeded for '{TARGET_WAREHOUSE}'.\n\n"
#             f"Item Group        : {TARGET_ITEM_GROUP}\n"
#             f"Maximum Allowed   : {MAX_ALLOWED_TOTAL_QTY}\n"
#             f"Current Stock     : {current_total}\n"
#             f"Incoming Qty      : {incoming_total}\n"
#             f"Stock After Entry : {final_total}\n\n"
#             f"👉 Reduce quantity or use another warehouse."
#         )
