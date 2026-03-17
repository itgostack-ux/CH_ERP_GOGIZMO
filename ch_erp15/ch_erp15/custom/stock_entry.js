frappe.ui.form.on("Stock Entry", {
    refresh(frm) {
        setInterval(() => {
            $('.form-message').remove();
            $('.help-box').remove();
            $('.document-help').remove();
        }, 1000);
        frm.page.btn_secondary.hide();
        
        frm.clear_custom_buttons();
        if (frm.doc.custom_status) {
            const statusColors = {
                "Draft": "gray",
                "Pending With Goods": "orange",
                "Dispatch": "blue",
                "Receive At Transit": "yellow",
                "Partially Transferred": "purple",
                "Transferred": "green",
                "Force Closed":"black",
            };
            const color = statusColors[frm.doc.custom_status] || "gray";
            frm.page.set_indicator(frm.doc.custom_status, color);
        }
        setTimeout(() => {
            $('.primary-action').attr("title", "Confirm Transfer");
        }, 200);

        if (frm.doc.docstatus === 0) {
            frm.page.clear_primary_action();
        }
        if (!frm.is_new() && (!frm.doc.custom_status || frm.doc.custom_status === "Draft")) {
            frm.add_custom_button("Pending With Goods", function () {
                frappe.call({
                    method: "ch_erp15.ch_erp15.custom.stock_entry.set_pending_qty",
                    args: { StockEntry: frm.doc.name, status: "Pending With Goods" },
                    callback: function () { frm.reload_doc(); }
                });
            }).addClass("btn-primary");
        }

        if (frm.doc.custom_status === "Pending With Goods") {
            frm.add_custom_button("Scan & Receive", function () {
                let barcode = prompt("Scan or Enter Barcode:");
                if (barcode) {
                    frappe.call({
                        method: "ch_erp15.ch_erp15.custom.stock_entry.received_qty",
                        args: { StockEntry: frm.doc.name, barcode: barcode },
                        callback: function () { frm.reload_doc(); }
                    });
                }
            }).addClass("btn-success");
            frm.add_custom_button("Received At Transit", function () {
                frappe.call({
                    method: "ch_erp15.ch_erp15.custom.stock_entry.set_custom_status",
                    args: { StockEntry: frm.doc.name, status: "Receive At Transit" },
                    callback: function () { frm.reload_doc(); }
                });
            });
        }

        if (frm.doc.custom_status === "Receive At Transit") {
            frm.add_custom_button("Scan & Transfer", function () {
                let barcode = prompt("Scan or Enter Barcode:");
                if (barcode) {
                    frappe.call({
                        method: "ch_erp15.ch_erp15.custom.stock_entry.final_received",
                        args: {
                            StockEntry: frm.doc.name,
                            barcode: barcode
                        },
                        callback: function () {
                            frm.reload_doc();
                        }
                    });
                }
            }).addClass("btn-success");
            frm.add_custom_button("Final Received", function () {
                frappe.call({
                    method: "ch_erp15.ch_erp15.custom.stock_entry.transfer_custom_status",
                    args: {
                        StockEntry: frm.doc.name
                    },
                    callback: function (r) {
                        frm.reload_doc();
                    }
                });
            }).addClass("btn-primary");
            }
        const revertableStates = ["Pending With Goods",];
        if (revertableStates.includes(frm.doc.custom_status)) {
            frm.add_custom_button("Revert", function () {
                frappe.call({
                    method: "ch_erp15.ch_erp15.custom.stock_entry.revert_goods",
                    args: { StockEntry: frm.doc.name },
                    callback: function () {
                        frappe.msgprint("Stocks Reverted");
                        frm.reload_doc();
                    }
                });
            }).addClass("btn-danger");
        }

        if (frm.doc.custom_status === "Partially Transferred" && frm.doc.docstatus === 1) {
            frm.add_custom_button("Goods Transfer To Pending", function () {
                    frappe.call({
                        method: "ch_erp15.ch_erp15.custom.stock_entry.goods_to_pending",
                        args: { StockEntry: frm.doc.name},
                    callback: function(r) {
                        if(!r.exc){
                            frm.reload_doc();
                        }
                    }
                    });
            }).addClass("btn-success");
        }

        if (frm.doc.custom_status === "Partially Transferred" && frm.doc.docstatus === 1) {
            frm.add_custom_button("Goods Transfer To Pending", function () {
                    frappe.call({
                        method: "ch_erp15.ch_erp15.custom.stock_entry.goods_to_pending",
                        args: { StockEntry: frm.doc.name},
                    callback: function(r) {
                        if(!r.exc){
                            frm.reload_doc();
                        }
                    }
                    });
            }).addClass("btn-success");
        }
        
        // if (frm.doc.custom_status === "Partially Transferred" && frm.doc.docstatus === 1) {
        //     frm.add_custom_button("Force Close", function () {

        //     if (!frm.doc.custom_description) {
        //         frm.set_df_property("custom_description", "hidden", 0);
        //         frm.set_df_property("custom_description", "read_only", 0);
        //         frm.set_df_property("custom_description", "reqd", 1);
        //         frm.refresh_field("custom_description");
        //         frm.scroll_to_field("custom_description");
        //         frappe.msgprint("Enter Force Close Reason and click Force Close again");
        //         return;
        //     }
        //         frappe.call({
        //             method: "ch_erp15.ch_erp15.custom.stock_entry.force_closed",
        //             args: {StockEntry: frm.doc.name},
        //             callback: function (r) {
        //                 if (!r.exc) {
        //                     frm.reload_doc();
        //                 }
        //             }
        //         });

        //     }).addClass("btn-danger");
        // }

        if (frm.doc.docstatus === 2) {
            frm.page.clear_primary_action();
            frm.remove_custom_button("Amend");
        }
        control_item_fields(frm);
    }
});

function control_item_fields(frm) {
    let status = frm.doc.custom_status || "Draft";
    let is_new = frm.is_new();
    let allow = {
        item_code: false,
        s_warehouse: false,
        t_warehouse: false,
        qty: false,
        custom_pending_qty:false,
        custom_receive_qty: false,
        custom_final_received_qty: false,
        basic_rate:false,
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

    const grid = frm.fields_dict.items.grid;
    Object.keys(allow).forEach(field => {
        grid.update_docfield_property(
            field,
            "read_only",
            allow[field] ? 0 : 1
        );
        grid.grid_rows.forEach(row => {
            row.toggle_editable(field, allow[field]);
        });

    });
    frm.refresh_field("items");
}