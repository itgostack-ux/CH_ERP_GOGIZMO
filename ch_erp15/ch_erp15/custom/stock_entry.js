frappe.ui.form.on("Stock Entry", {

    onload(frm) {
        apply_visibility(frm);
        apply_readonly(frm);
    },
    refresh(frm) {
        apply_visibility(frm);
        apply_readonly(frm);
        handle_buttons(frm);
        setTimeout(() => {
            $('.form-message, .help-box, .document-help').remove();
        }, 100);
        // shrink_system_columns(frm);
        
    },
    // onload_post_render(frm) {
    //     shrink_system_columns(frm);
    // },
    stock_entry_type(frm) {
        apply_visibility(frm);
        apply_readonly(frm);
    }

});

// function shrink_system_columns(frm) {
//     setTimeout(() => {
//         let grid = frm.fields_dict.items.grid.wrapper[1];
//         if (!grid) return;
//         grid.querySelectorAll('.grid-row-check').forEach(el => {
//             el.style.width = "48px";
//             el.style.maxWidth = "48px";
//         });

//         grid.querySelectorAll('.row-index').forEach(el => {
//             el.style.width = "55px";
//             el.style.maxWidth = "55px";
//             el.style.textAlign = "center";
//         });

//     }, 300);
// }

function apply_visibility(frm) {
    const is_mt = frm.doc.stock_entry_type === "Material Transfer";
    const style_id = "mt-hide-style";
    let css = "";

    if (!is_mt) {
        css = `
        [data-fieldname="custom_pending_qty"],
        [data-fieldname="custom_receive_qty"],
        [data-fieldname="custom_final_received_qty"] {
            display: none !important;
        }`;
    }

    let old = document.getElementById(style_id);
    if (old) old.remove();

    let style = document.createElement("style");
    style.id = style_id;
    style.innerHTML = css;
    document.head.appendChild(style);
    frm.refresh_field("items");
}

function handle_buttons(frm) {
    const is_mt = frm.doc.stock_entry_type === "Material Transfer";

    if (!is_mt) {
        frm.clear_custom_buttons();
        return;
    }

    frm.clear_custom_buttons();
    if (frm.doc.custom_status) {
        const statusColors = {
            "Draft": "gray",
            "Pending With Goods": "orange",
            "Ready For Pickup": "blue",
            "In Transit": "blue",
            "Ready For Receive": "yellow",
            "Receive At Transit": "yellow",
            "Partially Transferred": "purple",
            "Transferred": "green",
            "Force Closed": "black",
        };

        frm.page.set_indicator(
            frm.doc.custom_status,
            statusColors[frm.doc.custom_status] || "gray"
        );

        // Logistics status badge
        if (frm.doc.custom_logistics_status) {
            const lColors = {
                "Pending Pickup": "orange",
                "Picked Up": "blue",
                "In Transit": "blue",
                "Delivered": "green",
                "Revert Requested": "red",
                "Reverted": "darkgray",
            };
            frm.dashboard.set_headline(
                `<span class="indicator-pill ${lColors[frm.doc.custom_logistics_status] || 'gray'}">
                    <i class="fa fa-truck"></i> Logistics: ${frm.doc.custom_logistics_status}
                </span>
                ${frm.doc.custom_logistics_person ? ' &middot; ' + frm.doc.custom_logistics_person : ''}`
            );
        }
    }
    if (frm.doc.docstatus === 0) {
        frm.page.clear_primary_action();
    }

    if (!frm.is_new() && (!frm.doc.custom_status || frm.doc.custom_status === "Draft")) {
        frm.add_custom_button("Pending With Goods", () => {
            frappe.call({
                method: "ch_erp15.ch_erp15.custom.stock_entry.set_pending_qty",
                args: {
                    StockEntry: frm.doc.name,
                    status: "Pending With Goods"
                },
                callback: () => frm.reload_doc()
            });
        }).addClass("btn-primary");
    }

    if (frm.doc.custom_status === "Pending With Goods") {
        frm.add_custom_button("Scan & Send", () => {
            let barcode = prompt("Scan or Enter Barcode:");
            if (barcode) {
                frappe.call({
                    method: "ch_erp15.ch_erp15.custom.stock_entry.received_qty",
                    args: {
                        StockEntry: frm.doc.name,
                        barcode
                    },
                    callback: () => frm.reload_doc()
                });
            }
        }).addClass("btn-success");
        frm.add_custom_button("Ready For Pickup", () => {
            frappe.call({
                method: "ch_erp15.ch_erp15.custom.stock_entry.set_custom_status",
                args: {
                    StockEntry: frm.doc.name,
                    status: "Ready For Pickup"
                },
                callback: () => frm.reload_doc()
            });
        });

        frm.add_custom_button("Revert", () => {
            frappe.call({
                method: "ch_erp15.ch_erp15.custom.stock_entry.revert_goods",
                args: {
                    StockEntry: frm.doc.name
                },
                callback: () => {
                    frappe.msgprint("Stocks Reverted");
                    frm.reload_doc();
                }
            });
        }).addClass("btn-danger");
    }

    // Logistics: Ready For Pickup → logistics can pick up
    if (frm.doc.custom_status === "Ready For Pickup" && !frm.doc.custom_logistics_status) {
        frm.add_custom_button("Logistics Pickup", () => {
            let d = new frappe.ui.Dialog({
                title: __("Logistics Pickup"),
                fields: [
                    {fieldname: "logistics_person", fieldtype: "Data", label: "Logistics Person", reqd: 1},
                    {fieldname: "pickup_photo", fieldtype: "Attach Image", label: "Pickup Photo"},
                ],
                primary_action_label: __("Confirm Pickup"),
                primary_action: (values) => {
                    d.hide();
                    frappe.call({
                        method: "ch_erp15.ch_erp15.custom.stock_entry.logistics_pickup",
                        args: {
                            stock_entry: frm.doc.name,
                            logistics_person: values.logistics_person,
                            pickup_photo: values.pickup_photo,
                        },
                        callback: () => frm.reload_doc()
                    });
                }
            });
            d.show();
        }).addClass("btn-primary");
    }

    // Logistics: In Transit → can deliver
    if (frm.doc.custom_logistics_status === "In Transit") {
        frm.add_custom_button("Deliver to Store", () => {
            let d = new frappe.ui.Dialog({
                title: __("Deliver to Store"),
                fields: [
                    {fieldname: "delivery_photo", fieldtype: "Attach Image", label: "Delivery Photo"},
                ],
                primary_action_label: __("Confirm Delivery"),
                primary_action: (values) => {
                    d.hide();
                    frappe.call({
                        method: "ch_erp15.ch_erp15.custom.stock_entry.logistics_deliver",
                        args: {
                            stock_entry: frm.doc.name,
                            delivery_photo: values.delivery_photo,
                        },
                        callback: () => frm.reload_doc()
                    });
                }
            });
            d.show();
        }).addClass("btn-success");

        // Revert request while in transit
        frm.add_custom_button("Request Revert", () => {
            let reason = prompt("Reason for revert:");
            if (reason) {
                frappe.call({
                    method: "ch_erp15.ch_erp15.custom.stock_entry.logistics_revert_request",
                    args: { stock_entry: frm.doc.name, reason },
                    callback: () => frm.reload_doc()
                });
            }
        }).addClass("btn-danger");
    }

    // Revert requested → complete revert
    if (frm.doc.custom_logistics_status === "Revert Requested") {
        frm.add_custom_button("Complete Revert", () => {
            frappe.call({
                method: "ch_erp15.ch_erp15.custom.stock_entry.logistics_revert_complete",
                args: { stock_entry: frm.doc.name },
                callback: () => {
                    frappe.msgprint("Goods reverted to source warehouse");
                    frm.reload_doc();
                }
            });
        }).addClass("btn-danger");
    }

    if (frm.doc.custom_status === "Ready For Receive" || frm.doc.custom_status === "Receive At Transit") {
        // Block receive if revert requested
        if (frm.doc.custom_logistics_status === "Revert Requested") {
            frm.dashboard.set_headline(
                '<span class="indicator-pill red"><i class="fa fa-ban"></i> Revert Requested — receiving blocked</span>'
            );
        } else {
            frm.add_custom_button("Scan & Receive", () => {
                let barcode = prompt("Scan IMEI / Barcode:");
                if (barcode) {
                    frappe.call({
                        method: "ch_erp15.ch_erp15.custom.stock_entry.pos_scan_receive",
                        args: {
                            stock_entry: frm.doc.name,
                            barcode
                        },
                        callback: () => frm.reload_doc()
                    });
                }
            }).addClass("btn-success");
            frm.add_custom_button("Confirm Received", () => {
                frappe.call({
                    method: "ch_erp15.ch_erp15.custom.stock_entry.pos_confirm_receive",
                    args: {
                        stock_entry: frm.doc.name
                    },
                    callback: () => frm.reload_doc()
                });
            }).addClass("btn-primary");
        }
    }

    if (frm.doc.custom_status === "Partially Transferred" && frm.doc.docstatus === 1) {
        frm.add_custom_button("Goods Transfer To Pending", () => {
            frappe.call({
                method: "ch_erp15.ch_erp15.custom.stock_entry.goods_to_pending",
                args: {
                    StockEntry: frm.doc.name
                },
                callback: () => frm.reload_doc()
            });
        }).addClass("btn-success");
    }

    // if (frm.doc.custom_status === "Partially Transferred" && frm.doc.docstatus === 1) {
    //     frm.add_custom_button("Force Close", () => {
    //         frappe.call({
    //             method: "ch_erp15.ch_erp15.custom.stock_entry.force_closed",
    //             args: {
    //                 StockEntry: frm.doc.name
    //             },
    //             callback: () => frm.reload_doc()
    //         });
    //     }).addClass("btn-success");
    // }

    if (frm.doc.docstatus === 2) {
        frm.page.clear_primary_action();
        frm.remove_custom_button("Amend");
    }
}

function apply_readonly(frm) {
    if (frm.doc.stock_entry_type !== "Material Transfer") return;
    let status = frm.doc.custom_status || "Draft";
    let is_new = frm.is_new();
    let allow = {
        item_code: false,
        s_warehouse: false,
        t_warehouse: false,
        qty: false,
        custom_pending_qty: false,
        custom_receive_qty: false,
        custom_final_received_qty: false,
        basic_rate: false
    };

    if (is_new || status === "Draft") {
        allow.item_code = true;
        allow.s_warehouse = true;
        allow.t_warehouse = true;
        allow.qty = true;
    }
    if (status === "Pending With Goods") {
        allow.custom_receive_qty = true;
    }
    if (status === "Receive At Transit") {
        allow.custom_final_received_qty = true;
    }

    let grid = frm.fields_dict.items.grid;
    Object.keys(allow).forEach(field => {
        grid.update_docfield_property(field, "read_only", allow[field] ? 0 : 1);
        (grid.grid_rows || []).forEach(row => {
            row.toggle_editable(field, allow[field]);
        });
    });

    frm.refresh_field("items");
    setTimeout(() => {
        Object.keys(allow).forEach(field => {
            grid.update_docfield_property(field, "read_only", allow[field] ? 0 : 1);
        });
        frm.refresh_field("items");
    }, 300);
}