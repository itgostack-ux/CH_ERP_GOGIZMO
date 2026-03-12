app_name = "ch_erp15"
app_title = "Gogizmo ERP"
app_publisher = "Admin"
app_description = "Gogizmo ERP Customization Suite"
app_email = "manonraj@gostack.in"
app_license = "mit"


override_doctype_class = {
    # "Purchase Order": "ch_erp15.ch_erp15.custom.purchase_order.CustomPurchaseOrder",
    "Purchase Receipt": "ch_erp15.ch_erp15.custom.purchase_receipt.CustomPurchaseReceipt",
    # "Purchase Invoice": "ch_erp15.ch_erp15.custom.purchase_invoice.CustomPurchaseInvoice",
}

doctype_js = {
    "Purchase Order": "ch_erp15/custom/purchase_order.js",
    "Purchase Receipt": "ch_erp15/custom/purchase_receipt.js",
    "Purchase Invoice": "ch_erp15/custom/purchase_invoice.js",
    "Sales Order": "ch_erp15/custom/sales_order.js",
}

doc_events = {
    "Stock Entry": {
        "validate": "ch_erp15.ch_erp15.doctype.warehouse_capacity.warehouse_capacity.validate_warehouse_capacity"
    },
    "Purchase Receipt": {
        "validate": "ch_erp15.ch_erp15.doctype.warehouse_capacity.warehouse_capacity.validate_warehouse_capacity"
    },
    "Purchase Invoice": {
        "validate": "ch_erp15.ch_erp15.doctype.warehouse_capacity.warehouse_capacity.validate_warehouse_capacity"
    },
    "Delivery Note": {
        "validate": "ch_erp15.ch_erp15.doctype.warehouse_capacity.warehouse_capacity.validate_warehouse_capacity"
    }
}

fixtures = [
    "Client Script"
]