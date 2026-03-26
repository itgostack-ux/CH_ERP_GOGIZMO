# import frappe


# def update_exempted_values(doc, method):

#     print("\n🚀 Updating Exempted Values for:", doc.name)

#     for row in doc.items:

#         print("\n🔹 Row:", row.idx)

#         if not row.custom_serial_noimei_no:
#             row.custom_exempted_value = 0
#             continue

#         # First serial only
#         serial = row.custom_serial_noimei_no.split("\n")[0].strip()

#         if not serial:
#             row.custom_exempted_value = 0
#             continue

#         print("🔎 Serial:", serial)

#         # =========================================
#         # SQL MATCH FOR YOUR DATABASE
#         # =========================================

#         result = frappe.db.sql("""
#             SELECT tpri.custom_exempted_value
#             FROM `tabSerial No` sr
#             JOIN `tabPurchase Receipt` pr
#                 ON sr.purchase_document_no = pr.name
#             JOIN `tabPurchase Receipt Item` tpri
#                 ON pr.name = tpri.parent
#                AND sr.item_code = tpri.item_code
#             WHERE sr.name = %s
#             LIMIT 1
#         """, (serial,), as_dict=True)

#         print("📦 Result:", result)

#         if result:
#             value = result[0].custom_exempted_value or 0
#             row.custom_exempted_value = value
#             print("💰 Value Set:", value)
#         else:
#             row.custom_exempted_value = 0
#             print("❌ No value found")
# import frappe


# # =====================================================
# # ⭐ DOC EVENT — RUN ON VALIDATE (SAVE + SUBMIT SAFE)
# # =====================================================

# def update_exempted_values(doc, method=None):

#     for row in doc.items:

#         # 🔹 No serial → reset values
#         if not row.custom_serial_noimei_no:
#             row.custom_exempted_value = 0
#             row.taxable_value = row.rate or 0
#             row.amount = (row.rate or 0) * (row.qty or 1)
#             continue

#         serial = row.custom_serial_noimei_no.split("\n")[0].strip()

#         if not serial:
#             row.custom_exempted_value = 0
#             continue

#         # 🔹 Get exempt value
#         exempt = get_exempted_value_from_serial(serial)

#         row.custom_exempted_value = exempt

#         # =====================================================
#         # ⭐ APPLY SAME CALCULATION AS CLIENT SCRIPT
#         # =====================================================

#         rate = row.rate or 0
#         qty = row.qty or 1

#         taxable_value = rate - exempt
#         if taxable_value < 0:
#             taxable_value = 0


#         row.taxable_value = taxable_value


# # =====================================================
# # ⭐ SERVER METHOD — CALLED FROM JS
# # =====================================================

# @frappe.whitelist()
# def get_exempted_value_from_serial(serial):

#     if not serial:
#         return 0

#     result = frappe.db.sql("""
#         SELECT tpri.custom_exempted_value
#         FROM `tabSerial No` sr
#         JOIN `tabPurchase Receipt` pr
#             ON sr.purchase_document_no = pr.name
#         JOIN `tabPurchase Receipt Item` tpri
#             ON pr.name = tpri.parent
#            AND sr.item_code = tpri.item_code
#         WHERE sr.name = %s
#         LIMIT 1
#     """, (serial,), as_dict=True)

#     if result:
#         return result[0].custom_exempted_value or 0

#     return 0