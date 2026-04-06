app_name = "ch_erp15"
app_title = "Gogizmo ERP"
app_publisher = "Admin"
app_description = "Gogizmo ERP Customization Suite"
app_email = "manonraj@gostack.in"
app_license = "mit"
required_apps = ["frappe/erpnext", "AbirJ1/ch_item_master", "gofix"]

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [
	{
		"name": "ch_erp15",
		"logo": "/assets/ch_erp15/icon.svg",
		"title": "Gogizmo ERP",
		"route": "/desk/gogizmo-erp",
	}
]

after_install = "ch_erp15.setup.after_install"
after_migrate = "ch_erp15.setup.after_migrate"
before_uninstall = "ch_erp15.setup.before_uninstall"

app_include_css = "/assets/ch_erp15/css/ops_hub.css"



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
    "Material Request": "ch_erp15/custom/material_request.js",
}

doctype_list_js = {
    "Material Request": "ch_erp15/custom/material_request_list.js",
}



doc_events = {
    "Delivery Note": {
        "validate":
            "ch_erp15.ch_erp15.custom.delivery_note.full_recalculation",

        "before_submit":
            "ch_erp15.ch_erp15.custom.delivery_note.before_submit_all",

        "on_submit":
            "ch_erp15.ch_erp15.custom.delivery_note.create_sales_invoice_on_submit"
    },


    "Stock Entry": {
        "validate": [
            "ch_erp15.ch_erp15.doctype.warehouse_capacity.warehouse_capacity.validate_warehouse_capacity",
            "ch_erp15.ch_erp15.store_request_api.validate_transfer_qty",
        ],
        "on_submit":
            "ch_erp15.ch_erp15.store_request_api.notify_store_on_transfer",
    },

    "Material Request": {
        "on_update":
            "ch_erp15.ch_erp15.store_request_api.notify_on_mr_update",
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


scheduler_events = {
    "cron": {
        "*/15 * * * *": [
            "ch_erp15.ch_erp15.store_request_api.check_sla_breach",
        ],
    },
}