"""
Operations Hub — Backend API

Provides context, dashboard stats, request queues, transfer queues,
and receiving queues for the Operations Hub frontend.
"""

import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, get_datetime, cint


# ── Context ──────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_ops_context():
	"""Return user context: roles, company, warehouses."""
	user = frappe.session.user
	roles = frappe.get_roles(user)
	companies = frappe.get_all("Company", pluck="name")

	# Pick default company from user defaults or first company
	company = (
		frappe.defaults.get_user_default("Company")
		or (companies[0] if companies else "")
	)

	# Warehouses the user can access (non-group, active, in company)
	warehouses = frappe.get_all(
		"Warehouse",
		filters={"company": company, "is_group": 0, "disabled": 0},
		pluck="name",
		order_by="name",
	)

	return {
		"user": user,
		"user_fullname": frappe.utils.get_fullname(user),
		"roles": roles,
		"company": company,
		"companies": companies,
		"warehouses": warehouses,
	}


# ── Dashboard Stats ──────────────────────────────────────────────────────────

@frappe.whitelist()
def get_dashboard_stats(warehouse=""):
	"""KPIs for the dashboard: pending requests, SLA breaches, active transfers, pending receipts."""
	company = frappe.defaults.get_user_default("Company") or ""
	wh_filter = {"set_warehouse": warehouse} if warehouse else {}
	company_filter = {"company": company} if company else {}

	# Pending Material Requests (draft or submitted, not completed)
	pending_requests = frappe.db.count("Material Request", filters={
		**company_filter,
		**wh_filter,
		"docstatus": ["in", [0, 1]],
		"status": ["not in", ["Stopped", "Cancelled", "Received", "Transferred"]],
		"material_request_type": "Material Transfer",
	})

	# Pending approval
	pending_approval = frappe.db.count("Material Request", filters={
		**company_filter,
		**wh_filter,
		"docstatus": 0,
		"custom_approval_status": "Pending Approval",
		"material_request_type": "Material Transfer",
	})

	# SLA breached
	sla_breached = frappe.db.count("Material Request", filters={
		**company_filter,
		**wh_filter,
		"docstatus": ["in", [0, 1]],
		"custom_sla_breached": 1,
		"status": ["not in", ["Stopped", "Cancelled", "Received", "Transferred"]],
		"material_request_type": "Material Transfer",
	})

	# Active transfers (Stock Entry - Material Transfer, submitted)
	transfer_filters = {
		**company_filter,
		"docstatus": 1,
		"stock_entry_type": "Material Transfer",
	}
	active_transfers = frappe.db.count("Stock Entry", filters=transfer_filters)

	# In transit (custom_status if exists, else just count submitted)
	in_transit = 0
	if frappe.db.has_column("Stock Entry", "custom_status"):
		in_transit = frappe.db.count("Stock Entry", filters={
			**transfer_filters,
			"custom_status": "In Transit",
		})

	# Pending receipt (Purchase Receipt in draft)
	pending_receipt = frappe.db.count("Purchase Receipt", filters={
		**company_filter,
		"docstatus": 0,
	})

	# ── Manifest KPIs ──
	active_manifests = 0
	manifests_in_transit = 0
	if frappe.db.exists("DocType", "CH Transfer Manifest"):
		active_manifests = frappe.db.count("CH Transfer Manifest", filters={
			"docstatus": 1,
			"status": ["in", ["Packed", "Assigned", "In Transit"]],
		})
		manifests_in_transit = frappe.db.count("CH Transfer Manifest", filters={
			"docstatus": 1,
			"status": "In Transit",
		})

	# Recent activity (last 20 items)
	recent_mrs = frappe.get_all("Material Request", filters={
		**company_filter,
		"material_request_type": "Material Transfer",
	}, fields=["name", "status", "creation", "custom_priority as priority"],
		order_by="creation desc", limit=10)

	recent_ses = frappe.get_all("Stock Entry", filters={
		**company_filter,
		"stock_entry_type": "Material Transfer",
	}, fields=["name", "docstatus", "creation"],
		order_by="creation desc", limit=10)

	recent_manifests = []
	if frappe.db.exists("DocType", "CH Transfer Manifest"):
		recent_manifests = frappe.get_all("CH Transfer Manifest", filters={
			"docstatus": ["in", [0, 1]],
		}, fields=["name", "status", "creation", "driver_name"],
			order_by="creation desc", limit=10)

	recent_activity = []
	for mr in recent_mrs:
		recent_activity.append({
			"type": "Material Request",
			"name": mr.name,
			"status": mr.status,
			"description": f"Priority: {mr.priority or 'Standard'}",
			"creation": str(mr.creation),
		})
	for se in recent_ses:
		recent_activity.append({
			"type": "Stock Entry",
			"name": se.name,
			"status": "Draft" if se.docstatus == 0 else "Submitted",
			"description": "Material Transfer",
			"creation": str(se.creation),
		})
	for m in recent_manifests:
		recent_activity.append({
			"type": "CH Transfer Manifest",
			"name": m.name,
			"status": m.status or "Draft",
			"description": f"Driver: {m.driver_name or '—'}",
			"creation": str(m.creation),
		})

	# Sort by creation desc, limit 15
	recent_activity.sort(key=lambda x: x["creation"], reverse=True)
	recent_activity = recent_activity[:15]

	return {
		"pending_requests": pending_requests,
		"pending_approval": pending_approval,
		"sla_breached": sla_breached,
		"active_transfers": active_transfers,
		"in_transit": in_transit,
		"active_manifests": active_manifests,
		"manifests_in_transit": manifests_in_transit,
		"pending_receipt": pending_receipt,
		"recent_activity": recent_activity,
	}


# ── Stores ───────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_stores():
	"""Return list of CH POS Profiles (stores) for filtering."""
	return frappe.get_all(
		"POS Profile",
		filters={"disabled": 0},
		fields=["name", "name as store_name"],
		order_by="name",
	)


# ── Request Queue ────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_request_queue(tab="pending_approval", priority="", store="", warehouse=""):
	"""Return Material Request queue rows for a given tab."""
	company = frappe.defaults.get_user_default("Company") or ""
	filters = {
		"material_request_type": "Material Transfer",
	}
	if company:
		filters["company"] = company
	if warehouse:
		filters["set_warehouse"] = warehouse

	if priority:
		filters["custom_priority"] = priority
	if store:
		filters["custom_store"] = store

	# Tab-specific filters
	if tab == "pending_approval":
		filters["custom_approval_status"] = "Pending Approval"
		filters["docstatus"] = 0
	elif tab == "approved":
		filters["custom_approval_status"] = "Approved"
		filters["docstatus"] = 1
		filters["status"] = ["not in", ["Stopped", "Cancelled", "Received", "Transferred"]]
	elif tab == "in_progress":
		filters["docstatus"] = 1
		filters["status"] = ["in", ["Ordered", "Partially Ordered", "Partially Received"]]
		filters["custom_approval_status"] = "Approved"
	elif tab == "completed":
		filters["docstatus"] = 1
		filters["status"] = ["in", ["Received", "Transferred"]]
	elif tab == "all":
		filters["docstatus"] = ["in", [0, 1]]

	requests = frappe.get_all("Material Request",
		filters=filters,
		fields=[
			"name", "status", "creation", "modified",
			"custom_priority as priority",
			"custom_approval_status as approval_status",
			"custom_store as store",
			"custom_sla_breach_date as sla_due_by",
			"custom_sla_breached as sla_breached",
			"set_warehouse",
		],
		order_by="creation desc",
		limit=100,
	)

	# Enrich with item count
	for req in requests:
		req["item_count"] = frappe.db.count("Material Request Item",
			filters={"parent": req["name"]})
		req["sla_breached"] = cint(req.get("sla_breached"))
		if req.get("sla_due_by"):
			req["sla_due_by"] = str(req["sla_due_by"])

	return requests


@frappe.whitelist()
def get_request_tab_counts(warehouse=""):
	"""Return counts per tab for the badge."""
	company = frappe.defaults.get_user_default("Company") or ""
	base = {"material_request_type": "Material Transfer"}
	if company:
		base["company"] = company
	if warehouse:
		base["set_warehouse"] = warehouse

	counts = {}

	counts["pending_approval"] = frappe.db.count("Material Request", filters={
		**base, "custom_approval_status": "Pending Approval", "docstatus": 0,
	})

	counts["approved"] = frappe.db.count("Material Request", filters={
		**base, "custom_approval_status": "Approved", "docstatus": 1,
		"status": ["not in", ["Stopped", "Cancelled", "Received", "Transferred"]],
	})

	counts["in_progress"] = frappe.db.count("Material Request", filters={
		**base, "docstatus": 1,
		"status": ["in", ["Ordered", "Partially Ordered", "Partially Received"]],
		"custom_approval_status": "Approved",
	})

	counts["completed"] = frappe.db.count("Material Request", filters={
		**base, "docstatus": 1, "status": ["in", ["Received", "Transferred"]],
	})

	counts["all"] = frappe.db.count("Material Request", filters={
		**base, "docstatus": ["in", [0, 1]],
	})

	return counts


# ── Transfer Queue ───────────────────────────────────────────────────────────

@frappe.whitelist()
def get_transfer_queue(tab="in_transit", warehouse=""):
	"""Return Stock Entry (Material Transfer) queue rows."""
	company = frappe.defaults.get_user_default("Company") or ""
	filters = {"stock_entry_type": "Material Transfer"}
	if company:
		filters["company"] = company

	has_custom_status = frappe.db.has_column("Stock Entry", "custom_status")

	if tab == "draft":
		filters["docstatus"] = 0
	elif tab == "in_transit" and has_custom_status:
		filters["docstatus"] = 1
		filters["custom_status"] = "In Transit"
	elif tab == "dispatched" and has_custom_status:
		filters["docstatus"] = 1
		filters["custom_status"] = "Dispatched"
	elif tab == "completed":
		filters["docstatus"] = 1
		if has_custom_status:
			filters["custom_status"] = ["in", ["Received", "Completed", ""]]
	elif tab == "all":
		filters["docstatus"] = ["in", [0, 1]]
	else:
		# Fallback: submitted
		filters["docstatus"] = 1

	fields = [
		"name", "stock_entry_type", "docstatus", "creation",
	]
	if has_custom_status:
		fields.append("custom_status")

	transfers = frappe.get_all("Stock Entry",
		filters=filters,
		fields=fields,
		order_by="creation desc",
		limit=100,
	)

	for tr in transfers:
		# Get first item's source/target warehouse and item count
		items = frappe.get_all("Stock Entry Detail",
			filters={"parent": tr["name"]},
			fields=["s_warehouse", "t_warehouse"],
			limit=1,
		)
		tr["from_warehouse"] = items[0]["s_warehouse"] if items else ""
		tr["to_warehouse"] = items[0]["t_warehouse"] if items else ""
		tr["item_count"] = frappe.db.count("Stock Entry Detail",
			filters={"parent": tr["name"]})
		if not has_custom_status:
			tr["custom_status"] = ""

		# Check linked Material Request
		tr["material_request"] = frappe.db.get_value("Stock Entry Detail",
			filters={"parent": tr["name"], "material_request": ["is", "set"]},
			fieldname="material_request",
		) or ""

	# Warehouse filter (source or target)
	if warehouse:
		transfers = [
			t for t in transfers
			if warehouse in (t.get("from_warehouse", ""), t.get("to_warehouse", ""))
		]

	return transfers


# ── Receiving Queue ──────────────────────────────────────────────────────────

@frappe.whitelist()
def get_receiving_queue(tab="pending", warehouse=""):
	"""Return incoming transfers and purchase receipts pending processing."""
	company = frappe.defaults.get_user_default("Company") or ""
	items = []

	if tab == "pending":
		# Pending transfers (submitted, not completed/received)
		se_filters = {
			"stock_entry_type": "Material Transfer",
			"docstatus": 1,
		}
		if company:
			se_filters["company"] = company

		has_custom_status = frappe.db.has_column("Stock Entry", "custom_status")
		if has_custom_status:
			se_filters["custom_status"] = ["in", ["In Transit", "Dispatched", ""]]

		transfers = frappe.get_all("Stock Entry",
			filters=se_filters,
			fields=["name", "creation"],
			order_by="creation desc",
			limit=50,
		)

		for tr in transfers:
			detail = frappe.get_all("Stock Entry Detail",
				filters={"parent": tr["name"]},
				fields=["s_warehouse", "t_warehouse"],
				limit=1,
			)
			from_wh = detail[0]["s_warehouse"] if detail else ""
			to_wh = detail[0]["t_warehouse"] if detail else ""

			if warehouse and to_wh != warehouse:
				continue

			items.append({
				"doctype": "Stock Entry",
				"name": tr["name"],
				"from_warehouse": from_wh,
				"to_warehouse": to_wh,
				"supplier": "",
				"item_count": frappe.db.count("Stock Entry Detail",
					filters={"parent": tr["name"]}),
				"creation": str(tr["creation"]),
			})

		# Pending Purchase Receipts (draft)
		pr_filters = {"docstatus": 0}
		if company:
			pr_filters["company"] = company

		prs = frappe.get_all("Purchase Receipt",
			filters=pr_filters,
			fields=["name", "supplier", "set_warehouse", "creation"],
			order_by="creation desc",
			limit=50,
		)

		for pr in prs:
			if warehouse and pr.get("set_warehouse") != warehouse:
				continue
			items.append({
				"doctype": "Purchase Receipt",
				"name": pr["name"],
				"from_warehouse": "",
				"to_warehouse": pr.get("set_warehouse") or "",
				"supplier": pr.get("supplier") or "",
				"item_count": frappe.db.count("Purchase Receipt Item",
					filters={"parent": pr["name"]}),
				"creation": str(pr["creation"]),
			})

	elif tab == "received":
		# Recently received transfers (last 7 days)
		se_filters = {
			"stock_entry_type": "Material Transfer",
			"docstatus": 1,
			"posting_date": [">=", frappe.utils.add_days(nowdate(), -7)],
		}
		if company:
			se_filters["company"] = company

		has_custom_status = frappe.db.has_column("Stock Entry", "custom_status")
		if has_custom_status:
			se_filters["custom_status"] = ["in", ["Received", "Completed"]]

		transfers = frappe.get_all("Stock Entry",
			filters=se_filters,
			fields=["name", "creation"],
			order_by="creation desc",
			limit=50,
		)

		for tr in transfers:
			detail = frappe.get_all("Stock Entry Detail",
				filters={"parent": tr["name"]},
				fields=["s_warehouse", "t_warehouse"],
				limit=1,
			)
			to_wh = detail[0]["t_warehouse"] if detail else ""
			if warehouse and to_wh != warehouse:
				continue
			items.append({
				"doctype": "Stock Entry",
				"name": tr["name"],
				"from_warehouse": detail[0]["s_warehouse"] if detail else "",
				"to_warehouse": to_wh,
				"supplier": "",
				"item_count": frappe.db.count("Stock Entry Detail",
					filters={"parent": tr["name"]}),
				"creation": str(tr["creation"]),
			})

		# Recently submitted Purchase Receipts
		pr_filters = {
			"docstatus": 1,
			"posting_date": [">=", frappe.utils.add_days(nowdate(), -7)],
		}
		if company:
			pr_filters["company"] = company

		prs = frappe.get_all("Purchase Receipt",
			filters=pr_filters,
			fields=["name", "supplier", "set_warehouse", "creation"],
			order_by="creation desc",
			limit=50,
		)

		for pr in prs:
			if warehouse and pr.get("set_warehouse") != warehouse:
				continue
			items.append({
				"doctype": "Purchase Receipt",
				"name": pr["name"],
				"from_warehouse": "",
				"to_warehouse": pr.get("set_warehouse") or "",
				"supplier": pr.get("supplier") or "",
				"item_count": frappe.db.count("Purchase Receipt Item",
					filters={"parent": pr["name"]}),
				"creation": str(pr["creation"]),
			})

	# Sort all by creation desc
	items.sort(key=lambda x: x["creation"], reverse=True)
	return items
