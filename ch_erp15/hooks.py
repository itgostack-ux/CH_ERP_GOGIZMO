app_name = "ch_erp15"
app_title = "Gogizmo ERP"
app_publisher = "Admin"
app_description = "Gogizmo ERP Customization Suite"
app_email = "manonraj@gostack.in"
app_license = "mit"



override_doctype_class = {
    "Purchase Order": "ch_erp15.ch_erp15.custom.purchase_order.CustomPurchaseOrder",
    "Purchase Receipt": "ch_erp15.ch_erp15.custom.purchase_receipt.CustomPurchaseReceipt",
    "Purchase Invoice": "ch_erp15.ch_erp15.custom.purchase_invoice.CustomPurchaseInvoice",
    "Stock Entry": "ch_erp15.ch_erp15.custom.stock_entry.CustomStockEntry",
}



override_whitelisted_methods = {
    "erpnext.selling.doctype.sales_order.sales_order.make_delivery_note":
        "ch_erp15.ch_erp15.custom.delivery_note.make_delivery_note"
}



doctype_js = {
    "Purchase Order": "ch_erp15/custom/purchase_order.js",
    "Purchase Receipt": "ch_erp15/custom/purchase_receipt.js",
    "Purchase Invoice": "ch_erp15/custom/purchase_invoice.js",
    "Stock Entry": "ch_erp15/custom/stock_entry.js",
    "Delivery Note": "ch_erp15/custom/delivery_note.js",
}



doc_events = {

    "Delivery Note": {
        "validate": "ch_erp15.ch_erp15.custom.delivery_note.full_recalculation",
        "before_save": "ch_erp15.ch_erp15.custom.delivery_note.full_recalculation",
        "on_submit": "ch_erp15.ch_erp15.custom.delivery_note.create_sales_invoice_on_submit"
    },

    "Stock Entry": {
        "validate":
            "ch_erp15.ch_erp15.doctype.warehouse_capacity.warehouse_capacity.validate_warehouse_capacity"
    },

    "Purchase Receipt": {
        "validate":
            "ch_erp15.ch_erp15.doctype.warehouse_capacity.warehouse_capacity.validate_warehouse_capacity"
    },

    "Purchase Invoice": {
        "validate":
            "ch_erp15.ch_erp15.doctype.warehouse_capacity.warehouse_capacity.validate_warehouse_capacity"
    },
}



fixtures = [
    "Client Script",
]