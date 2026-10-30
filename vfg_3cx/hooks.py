app_name = "vfg_3cx"
app_title = "VFG 3CX"
app_publisher = "Shahrukhar Sattar"
app_description = "3CX Integration"
app_email = "shahrukh@ventureforce.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "vfg_3cx",
# 		"logo": "/assets/vfg_3cx/logo.png",
# 		"title": "VFG 3CX",
# 		"route": "/vfg_3cx",
# 		"has_permission": "vfg_3cx.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/vfg_3cx/css/vfg_3cx.css"
# app_include_js = "/assets/vfg_3cx/js/vfg_3cx.js"

# include js, css files in header of web template
# web_include_css = "/assets/vfg_3cx/css/vfg_3cx.css"
# web_include_js = "/assets/vfg_3cx/js/vfg_3cx.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "vfg_3cx/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Purchase Order": "public/js/purchase_order.js",
	"Lead": "public/js/threecx_call.js",
	"Contact": "public/js/threecx_call.js",
	"Sales Invoice": "public/js/sales_invoice.js",
	"Employee I9 Verification": "public/js/employee_i9_verification.js",
	"Employee W4": "public/js/employee_w4.js",
}
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "vfg_3cx/public/icons.svg"

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

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "vfg_3cx.utils.jinja_methods",
# 	"filters": "vfg_3cx.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "vfg_3cx.install.before_install"
# after_install = "vfg_3cx.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "vfg_3cx.uninstall.before_uninstall"
# after_uninstall = "vfg_3cx.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "vfg_3cx.utils.before_app_install"
# after_app_install = "vfg_3cx.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "vfg_3cx.utils.before_app_uninstall"
# after_app_uninstall = "vfg_3cx.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "vfg_3cx.notifications.get_notification_config"

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

doc_events = {
	"Employee I9 Verification": {
		"before_save": "vfg_3cx.onboarding.autofill_i9_dates",
		"before_update_after_submit": "vfg_3cx.onboarding.autofill_i9_dates",
	},
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"vfg_3cx.tasks.all"
# 	],
# 	"daily": [
# 		"vfg_3cx.tasks.daily"
# 	],
# 	"hourly": [
# 		"vfg_3cx.tasks.hourly"
# 	],
# 	"weekly": [
# 		"vfg_3cx.tasks.weekly"
# 	],
# 	"monthly": [
# 		"vfg_3cx.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "vfg_3cx.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "vfg_3cx.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "vfg_3cx.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "vfg_3cx.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["vfg_3cx.utils.before_request"]
# after_request = ["vfg_3cx.utils.after_request"]

# Job Events
# ----------
# before_job = ["vfg_3cx.utils.before_job"]
# after_job = ["vfg_3cx.utils.after_job"]

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
# 	"vfg_3cx.auth.validate"
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

