frappe.ui.form.on("Material Request", {
    refresh(frm) {
        // ── Combined status indicator ────────────────────────────────────
        if (frm.doc.custom_store) {
            let status_html = "";
            if (frm.doc.docstatus === 0 && frm.doc.custom_approval_status === "Pending Approval") {
                status_html = '<span class="indicator-pill orange">Pending Approval</span>';
            } else if (frm.doc.docstatus === 0 && frm.doc.custom_approval_status === "Rejected") {
                status_html = '<span class="indicator-pill red">Rejected</span>';
            } else if (frm.doc.custom_sla_breached) {
                status_html = '<span class="indicator-pill red">SLA Breached</span>';
            } else if (frm.doc.custom_priority === "Urgent") {
                status_html = '<span class="indicator-pill orange">Urgent</span>';
            }
            if (status_html) {
                let parts = [status_html];
                if (frm.doc.custom_store) parts.push("Store: " + frm.doc.custom_store);
                if (frm.doc.custom_priority) parts.push("Priority: " + frm.doc.custom_priority);
                frm.dashboard.set_headline(parts.join(" &nbsp;|&nbsp; "));
            }

            // ── Target warehouse info ─────────────────────────────────────
            if (frm.doc.set_warehouse && frm.doc.material_request_type === "Material Transfer") {
                frm.dashboard.add_comment(
                    __("Target Warehouse (Store): <strong>{0}</strong>", [frm.doc.set_warehouse]),
                    "blue", true
                );
            }
            if (frm.doc.custom_preferred_source_warehouse) {
                frm.dashboard.add_comment(
                    __("Source Warehouse (Zone): <strong>{0}</strong>", [frm.doc.custom_preferred_source_warehouse]),
                    "blue", true
                );
            }
            if (frm.doc.custom_request_datetime) {
                frm.dashboard.add_comment(
                    __("Requested: {0}", [frappe.datetime.str_to_user(frm.doc.custom_request_datetime)]),
                    "blue", true
                );
            }
        }

        // Show linked purchase requests in dashboard
        if (frm.doc.docstatus === 1 && frm.doc.custom_store) {
            show_tracking_dashboard(frm);
        }

        if (!frm.doc.custom_store) return;

        // ── Approval buttons (Draft, Pending Approval) ───────────────────
        if (frm.doc.docstatus === 0
            && frm.doc.custom_approval_status === "Pending Approval") {
            frm.add_custom_button(
                __("Approve"),
                () => approve_request(frm),
                __("Store Actions")
            );
            frm.add_custom_button(
                __("Reject"),
                () => reject_request(frm),
                __("Store Actions")
            );
        }

        // ── Stock team buttons (submitted MRs) ──────────────────────────
        if (frm.doc.docstatus !== 1) return;

        if (frm.doc.material_request_type === "Material Transfer") {
            frm.add_custom_button(
                __("Check Stock Availability"),
                () => check_stock(frm),
                __("Store Actions")
            );

            frm.add_custom_button(
                __("Suggest Allocation"),
                () => suggest_allocation(frm),
                __("Store Actions")
            );

            if (frm.doc.custom_allocation_plan) {
                frm.add_custom_button(
                    __("Execute Allocation"),
                    () => execute_allocation(frm),
                    __("Store Actions")
                );
            }

            if (["Pending", "Partially Ordered"].includes(frm.doc.status)) {
                frm.add_custom_button(
                    __("Raise Purchase Request"),
                    () => raise_purchase_request(frm),
                    __("Store Actions")
                );
            }

            if (!["Stopped", "Cancelled", "Received", "Transferred"].includes(frm.doc.status)) {
                frm.add_custom_button(
                    __("Short Close"),
                    () => short_close(frm),
                    __("Store Actions")
                );
            }

            frm.add_custom_button(
                __("View Full Tracking"),
                () => view_tracking(frm),
                __("Store Actions")
            );
        }
    },
});


// ── Approval ─────────────────────────────────────────────────────────────────

function approve_request(frm) {
    frappe.confirm(
        __("Approve this Material Request and send it to the stock team?"),
        () => {
            frappe.call({
                method: "ch_erp15.ch_erp15.store_request_api.approve_store_request",
                args: { request_name: frm.doc.name },
                freeze: true,
                freeze_message: __("Approving..."),
                callback(r) {
                    if (r.message) {
                        frappe.show_alert({
                            message: __("Approved — sent to stock team"),
                            indicator: "green",
                        });
                        frm.reload_doc();
                    }
                },
            });
        }
    );
}


function reject_request(frm) {
    frappe.prompt(
        { fieldname: "reason", fieldtype: "Small Text", label: __("Rejection Reason"),
          reqd: 1 },
        (values) => {
            frappe.call({
                method: "ch_erp15.ch_erp15.store_request_api.reject_store_request",
                args: { request_name: frm.doc.name, reason: values.reason },
                freeze: true,
                callback(r) {
                    if (r.message) {
                        frappe.show_alert({
                            message: __("Rejected"),
                            indicator: "orange",
                        });
                        frm.reload_doc();
                    }
                },
            });
        },
        __("Reject Material Request"),
        __("Reject")
    );
}


// ── Stock Check ──────────────────────────────────────────────────────────────

function check_stock(frm) {
    frappe.call({
        method: "ch_erp15.ch_erp15.store_request_api.check_stock_for_request",
        args: { request_name: frm.doc.name },
        freeze: true,
        freeze_message: __("Checking stock across warehouses..."),
        callback(r) {
            if (!r.message) return;
            show_stock_dialog(frm, r.message);
        },
    });
}


function show_stock_dialog(frm, stock_data) {
    let rows = "";
    for (let [item_code, data] of Object.entries(stock_data)) {
        let avail_html = "";
        if (data.availability && data.availability.length) {
            for (let a of data.availability) {
                let badge = a.is_destination
                    ? ' <span class="badge badge-info">Destination</span>'
                    : "";
                let reserved = a.reserved_qty
                    ? ` <span style="color:#636e72">(${a.reserved_qty} reserved)</span>`
                    : "";
                avail_html += `<div style="margin-left:20px;">
                    ${a.warehouse}: <strong>${a.available_qty}</strong>${badge}${reserved}
                </div>`;
            }
        } else {
            avail_html = '<div style="margin-left:20px; color:#d63031;">No stock found</div>';
        }

        let shortage_html = data.shortage > 0
            ? `<span style="color:#d63031; font-weight:bold;">Shortage: ${data.shortage}</span>`
            : '<span style="color:#00b894; font-weight:bold;">Sufficient</span>';

        rows += `
            <div style="border-bottom:1px solid #eee; padding:10px 0;">
                <strong>${item_code}</strong> — Requested: ${data.requested_qty}
                &nbsp; | &nbsp; Available: ${data.total_available}
                &nbsp; | &nbsp; ${shortage_html}
                ${avail_html}
            </div>`;
    }

    let d = new frappe.ui.Dialog({
        title: __("Stock Availability for {0}", [frm.doc.name]),
        size: "large",
    });
    d.$body.html(
        `<div style="padding:15px; max-height:400px; overflow-y:auto;">${rows}</div>`
    );
    d.show();
}


// ── Suggest Allocation ───────────────────────────────────────────────────────

function suggest_allocation(frm) {
    frappe.call({
        method: "ch_erp15.ch_erp15.store_request_api.auto_allocate_sources",
        args: { request_name: frm.doc.name },
        freeze: true,
        freeze_message: __("Calculating allocation plan..."),
        callback(r) {
            if (!r.message) return;
            show_allocation_dialog(frm, r.message.suggestions, r.message.stock_data);
        },
    });
}


function show_allocation_dialog(frm, suggestions, stock_data) {
    if (!suggestions || !suggestions.length) {
        frappe.msgprint(__("No allocation suggestions available."));
        return;
    }

    let rows = "";
    for (let s of suggestions) {
        let type_badge = "";
        if (s.source_type === "Warehouse") {
            type_badge = '<span class="badge badge-primary">Warehouse</span>';
        } else if (s.source_type === "Store") {
            type_badge = '<span class="badge badge-warning">Store</span>';
        } else {
            type_badge = '<span class="badge badge-danger">Supplier</span>';
        }

        rows += `<tr>
            <td>${s.item_code}</td>
            <td>${type_badge} ${s.source_warehouse || "N/A"}</td>
            <td>${s.source_store || "—"}</td>
            <td style="text-align:right"><strong>${s.suggested_qty}</strong></td>
        </tr>`;
    }

    let html = `
        <div style="padding:10px;">
            <p>Allocation plan has been saved. You can now <b>Execute Allocation</b>
            to create Stock Entries, or <b>Raise Purchase Request</b> for supplier items.</p>
            <table class="table table-bordered table-sm" style="margin-top:10px;">
                <thead>
                    <tr>
                        <th>Item</th><th>Source</th><th>Store</th><th style="text-align:right">Qty</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;

    let d = new frappe.ui.Dialog({
        title: __("Allocation Plan for {0}", [frm.doc.name]),
        size: "large",
    });
    d.$body.html(html);
    d.show();
    frm.reload_doc();
}


// ── Execute Allocation ───────────────────────────────────────────────────────

function execute_allocation(frm) {
    frappe.confirm(
        __("This will create Stock Entries from the allocation plan. "
           + "Supplier items will be skipped (use 'Raise Purchase Request' for those). Continue?"),
        () => {
            frappe.call({
                method: "ch_erp15.ch_erp15.store_request_api.execute_allocation",
                args: { request_name: frm.doc.name },
                freeze: true,
                freeze_message: __("Creating Stock Entries..."),
                callback(r) {
                    if (!r.message || !r.message.created) return;
                    let created = r.message.created;
                    let links = created.map(
                        (c) => `<a href="/desk/stock-entry/${c.name}">${c.name}</a> (${c.source}, ${c.items} items)`
                    ).join("<br>");
                    frappe.msgprint({
                        title: __("Stock Entries Created"),
                        message: links,
                        indicator: "green",
                    });
                    frm.reload_doc();
                },
            });
        }
    );
}


// ── Raise Purchase Request ───────────────────────────────────────────────────

function raise_purchase_request(frm) {
    frappe.confirm(
        __("This will create a <b>Purchase</b> type Material Request for items "
           + "with stock shortage. Continue?"),
        () => {
            frappe.call({
                method: "ch_erp15.ch_erp15.store_request_api.raise_purchase_request",
                args: { source_mr_name: frm.doc.name },
                freeze: true,
                freeze_message: __("Checking stock & creating purchase request..."),
                callback(r) {
                    if (!r.message) return;
                    let result = r.message;
                    frappe.msgprint({
                        title: __("Purchase Request Created"),
                        message: __(
                            "Created {0} with {1} items.<br><br>"
                            + '<a href="/desk/material-request/{2}">{2}</a>',
                            [result.name, result.items, result.name]
                        ),
                        indicator: "green",
                    });
                    frm.reload_doc();
                },
            });
        }
    );
}


// ── Short Close ──────────────────────────────────────────────────────────────

function short_close(frm) {
    frappe.prompt(
        { fieldname: "reason", fieldtype: "Small Text", label: __("Closure Reason"),
          reqd: 1, description: __("Explain why this request is being short-closed") },
        (values) => {
            frappe.call({
                method: "ch_erp15.ch_erp15.store_request_api.short_close_request",
                args: { request_name: frm.doc.name, reason: values.reason },
                freeze: true,
                callback(r) {
                    if (r.message) {
                        frappe.show_alert({
                            message: __("Request short-closed"),
                            indicator: "orange",
                        });
                        frm.reload_doc();
                    }
                },
            });
        },
        __("Short Close Material Request"),
        __("Short Close")
    );
}


// ── View Full Tracking ───────────────────────────────────────────────────────

function view_tracking(frm) {
    frappe.call({
        method: "ch_erp15.ch_erp15.store_request_api.get_request_tracking",
        args: { request_name: frm.doc.name },
        freeze: true,
        callback(r) {
            if (!r.message) return;
            show_tracking_dialog(frm, r.message);
        },
    });
}


function show_tracking_dialog(frm, t) {
    let html = '<div style="padding:10px;">';

    // Summary
    html += `<div class="row" style="margin-bottom:15px;">
        <div class="col-4"><strong>Status:</strong> ${t.status}</div>
        <div class="col-4"><strong>Approval:</strong> ${t.approval_status || "N/A"}</div>
        <div class="col-4"><strong>SLA:</strong> ${t.sla_breached ? '<span class="text-danger">Breached</span>' : '<span class="text-success">OK</span>'}</div>
    </div>
    <div class="row" style="margin-bottom:15px;">
        <div class="col-4"><strong>Ordered:</strong> ${t.per_ordered}%</div>
        <div class="col-4"><strong>Received:</strong> ${t.per_received}%</div>
        <div class="col-4"><strong>Transfer:</strong> ${t.transfer_status || "—"}</div>
    </div>`;

    // Items
    html += '<h6 style="margin-top:15px;">Items</h6><table class="table table-bordered table-sm"><thead><tr><th>Item</th><th>Qty</th><th>Ordered</th><th>Received</th></tr></thead><tbody>';
    for (let item of (t.items || [])) {
        html += `<tr><td>${item.item_code}</td><td>${item.qty}</td><td>${item.ordered_qty}</td><td>${item.received_qty}</td></tr>`;
    }
    html += '</tbody></table>';

    // Purchase Requests
    if (t.purchase_requests && t.purchase_requests.length) {
        html += '<h6>Linked Purchase Requests</h6><ul>';
        for (let pr of t.purchase_requests) {
            html += `<li><a href="/desk/material-request/${pr.name}">${pr.name}</a> — ${pr.status} (${pr.per_ordered}% ordered)</li>`;
        }
        html += '</ul>';
    }

    // Stock Entries
    if (t.stock_entries && t.stock_entries.length) {
        html += '<h6>Stock Entries</h6><ul>';
        for (let se of t.stock_entries) {
            let damage_html = "";
            if (se.damage_items && se.damage_items.length) {
                damage_html = ' <span class="text-danger">[Damage reported]</span>';
            }
            html += `<li><a href="/desk/stock-entry/${se.name}">${se.name}</a> — ${se.custom_status || "Submitted"} (${se.posting_date})${damage_html}</li>`;
        }
        html += '</ul>';
    }

    // Closure
    if (t.closure) {
        html += `<h6>Closure</h6><p>Closed by ${t.closure.closed_by} on ${t.closure.closure_date}.<br>Reason: ${t.closure.reason}</p>`;
    }

    html += '</div>';

    let d = new frappe.ui.Dialog({
        title: __("Tracking: {0}", [frm.doc.name]),
        size: "extra-large",
    });
    d.$body.html(html);
    d.show();
}


// ── Dashboard: linked purchase requests & stock entries ──────────────────────

function show_tracking_dashboard(frm) {
    // Show linked purchase MRs in the form dashboard
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Material Request",
            filters: {
                custom_source_material_request: frm.doc.name,
                docstatus: ["in", [0, 1]],
            },
            fields: ["name", "status", "material_request_type"],
            limit_page_length: 10,
        },
        async: true,
        callback(r) {
            if (r.message && r.message.length) {
                let items = r.message.map(
                    (pr) => `<a href="/desk/material-request/${pr.name}">${pr.name}</a> (${pr.status})`
                ).join(", ");
                frm.dashboard.add_comment(
                    __("Linked Purchase Requests: ") + items, "blue", true
                );
            }
        },
    });

    // Show linked Stock Entries
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Stock Entry",
            filters: [
                ["Stock Entry Detail", "material_request", "=", frm.doc.name],
                ["docstatus", "=", 1],
            ],
            fields: ["name", "custom_status", "posting_date"],
            limit_page_length: 10,
        },
        async: true,
        callback(r) {
            if (r.message && r.message.length) {
                let items = r.message.map(
                    (se) => `<a href="/desk/stock-entry/${se.name}">${se.name}</a> (${se.custom_status || se.posting_date})`
                ).join(", ");
                frm.dashboard.add_comment(
                    __("Stock Entries: ") + items, "green", true
                );
            }
        },
    });
}
