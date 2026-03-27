frappe.ui.form.on("Material Request", {
    refresh(frm) {
        // Only show custom buttons for submitted store Material Transfer requests
        if (frm.doc.docstatus !== 1) return;
        if (!frm.doc.custom_store) return;

        if (frm.doc.material_request_type === "Material Transfer") {
            frm.add_custom_button(
                __("Check Stock Availability"),
                () => check_stock(frm),
                __("Store Actions")
            );

            if (["Pending", "Partially Ordered"].includes(frm.doc.status)) {
                frm.add_custom_button(
                    __("Raise Purchase Request"),
                    () => raise_purchase_request(frm),
                    __("Store Actions")
                );
            }
        }

        // Show SLA breach indicator
        if (frm.doc.custom_sla_breached) {
            frm.dashboard.set_headline(
                __('<span class="indicator-pill red">SLA Breached</span> Priority: {0}', [frm.doc.custom_priority])
            );
        } else if (frm.doc.custom_priority === "Urgent") {
            frm.dashboard.set_headline(
                __('<span class="indicator-pill orange">Urgent</span> Store: {0}', [frm.doc.custom_store])
            );
        }
    },
});


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
                    ? '<span class="badge badge-info">Destination</span>'
                    : "";
                avail_html += `<div style="margin-left:20px;">
                    ${a.warehouse}: <strong>${a.available_qty}</strong> ${badge}
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
    d.$body.html(`<div style="padding:15px; max-height:400px; overflow-y:auto;">${rows}</div>`);
    d.show();
}


function raise_purchase_request(frm) {
    frappe.confirm(
        __("This will create a <b>Purchase</b> type Material Request for items with stock shortage. Continue?"),
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
                            "Created {0} with {1} items.<br><br>" +
                            '<a href="/app/material-request/{2}">{2}</a>',
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
