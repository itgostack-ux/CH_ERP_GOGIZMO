import frappe
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt

class CustomPurchaseReceipt(PurchaseReceipt):

    def on_submit(self):
        # Run original on_submit logic first
        super().on_submit()

        if not self.custom_track:
            return

        imei_list = []
        duplicates_in_doc = []

        # Collect all IMEI numbers and detect duplicates within this document
        for row in self.custom_track:
            imei_number = row.imei_number.strip()
            if imei_number in imei_list:
                duplicates_in_doc.append(imei_number)
            imei_list.append(imei_number)

        if duplicates_in_doc:
            frappe.throw(f"Duplicate IMEI(s) found in this Purchase Receipt: {', '.join(duplicates_in_doc)}")

        # Batch check for existing IMEIs in the master "IMEI Track" doctype
        existing_imeis = frappe.get_all(
            "IMEI Track",
            filters={"imei_no": ("in", imei_list)},
            fields=["imei_no"]
        )
        if existing_imeis:
            existing_list = [d.imei_no for d in existing_imeis]
            frappe.throw(f"IMEI(s) already exist in IMEI Track: {', '.join(existing_list)}")

        # Insert IMEI Track records - no manual commit here!
        for row in self.custom_track:
            imei_doc = frappe.get_doc({
                "doctype": "IMEI Track",
                "item_code": row.item_code,
                "imei_no": row.imei_number,
                "purchase_receipt": self.name,
                "purchase_receipt_item": getattr(row, "purchase_receipt_item", "")
            })
            imei_doc.insert(ignore_permissions=True)