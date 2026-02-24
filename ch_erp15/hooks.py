app_name = "ch_erp15"
app_title = "Ch Erp15"
app_publisher = "Admin"
app_description = "Ch Erp15"
app_email = "manonraj@gostack.in"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "ch_erp15",
# 		"logo": "/assets/ch_erp15/logo.png",
# 		"title": "Ch Erp15",
# 		"route": "/ch_erp15",
# 		"has_permission": "ch_erp15.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/ch_erp15/css/ch_erp15.css"
# app_include_js = "/assets/ch_erp15/js/ch_erp15.js"

# include js, css files in header of web template
# web_include_css = "/assets/ch_erp15/css/ch_erp15.css"
# web_include_js = "/assets/ch_erp15/js/ch_erp15.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "ch_erp15/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "ch_erp15/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "ch_erp15.utils.jinja_methods",
# 	"filters": "ch_erp15.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "ch_erp15.install.before_install"
# after_install = "ch_erp15.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "ch_erp15.uninstall.before_uninstall"
# after_uninstall = "ch_erp15.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "ch_erp15.utils.before_app_install"
# after_app_install = "ch_erp15.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "ch_erp15.utils.before_app_uninstall"
# after_app_uninstall = "ch_erp15.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "ch_erp15.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"ch_erp15.tasks.all"
# 	],
# 	"daily": [
# 		"ch_erp15.tasks.daily"
# 	],
# 	"hourly": [
# 		"ch_erp15.tasks.hourly"
# 	],
# 	"weekly": [
# 		"ch_erp15.tasks.weekly"
# 	],
# 	"monthly": [
# 		"ch_erp15.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "ch_erp15.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "ch_erp15.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "ch_erp15.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["ch_erp15.utils.before_request"]
# after_request = ["ch_erp15.utils.after_request"]

# Job Events
# ----------
# before_job = ["ch_erp15.utils.before_job"]
# after_job = ["ch_erp15.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"ch_erp15.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

# before_request = [
#     "ch_erp15.utils.login_guard.enforce_company_selection"
# ]

# app_include_js = [
#     "/assets/ch_erp15/js/company_selector.js"
# ]

# app_include_css = [
#     "/assets/ch_erp15/css/company_selector.css"
# ]
# permission_query_conditions = {
#     "*": "ch_erp15.permission_query_conditions.get_conditions"
# }
# override_doctype_class = {
#     "Purchase Order": "ch_erp15.ch_erp15.custom.purchase_order.CustomPurchaseOrder"
# }
# doctype_js = {
#     "Purchase Order": "custom/purchase_order.js"
# }
override_doctype_class = {
    "Purchase Order": "ch_erp15.ch_erp15.custom.purchase_order.CustomPurchaseOrder",
    "Purchase Receipt": "ch_erp15.ch_erp15.custom.purchase_receipt.CustomPurchaseReceipt",
    # "Purchase Invoice": "ch_erp15.ch_erp15.custom.purchase_invoice.CustomPurchaseInvoice",
}


doctype_js = {
    "Purchase Order": "ch_erp15/custom/purchase_order.js",
    "Purchase Receipt": "ch_erp15/custom/purchase_receipt.js",
    # "Purchase Inovice": "ch_erp15/custom/purchase_invoice.js"

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
# app_include_css = "/assets/ch_erp15/css/custom_theme.css"
# app_include_js = "/assets/ch_erp15/js/custom_theme.js"