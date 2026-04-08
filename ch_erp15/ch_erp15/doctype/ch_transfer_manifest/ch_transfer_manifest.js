frappe.ui.form.on("CH Transfer Manifest", {
    refresh(frm) {
        render_status_badge(frm);
        add_action_buttons(frm);
    },

    source_store(frm) {
        if (frm.doc.source_store) {
            frappe.db.get_value("CH Store", frm.doc.source_store, "warehouse", (r) => {
                if (r && r.warehouse) frm.set_value("source_warehouse", r.warehouse);
            });
        }
    },

    destination_store(frm) {
        if (frm.doc.destination_store) {
            frappe.db.get_value("CH Store", frm.doc.destination_store, "warehouse", (r) => {
                if (r && r.warehouse) frm.set_value("destination_warehouse", r.warehouse);
            });
        }
    },
});

frappe.ui.form.on("CH Transfer Manifest Item", {
    stock_entry(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.stock_entry) return;
        frappe.call({
            method: "frappe.client.get",
            args: { doctype: "Stock Entry", name: row.stock_entry },
            callback(r) {
                if (!r.message) return;
                let se = r.message;
                frappe.model.set_value(cdt, cdn, "from_warehouse", se.from_warehouse);
                frappe.model.set_value(cdt, cdn, "to_warehouse", se.to_warehouse);
                frappe.model.set_value(cdt, cdn, "material_request", se.material_request);
                frappe.model.set_value(cdt, cdn, "transfer_status", se.custom_status || "Draft");
                let item_count = (se.items || []).length;
                let total_qty = (se.items || []).reduce((s, i) => s + (i.qty || 0), 0);
                frappe.model.set_value(cdt, cdn, "item_count", item_count);
                frappe.model.set_value(cdt, cdn, "total_qty", total_qty);
            }
        });
    }
});

function render_status_badge(frm) {
    if (!frm.doc.status) return;
    const colors = {
        "Draft": "gray", "Packed": "blue", "Assigned": "orange",
        "Pickup Started": "yellow", "In Transit": "blue",
        "Delivered": "purple", "Received": "green", "Closed": "darkgray",
        "Cancelled": "red",
    };
    frm.page.set_indicator(frm.doc.status, colors[frm.doc.status] || "gray");

    if (frm.doc.driver_name) {
        frm.dashboard.set_headline(
            `<span class="indicator-pill ${colors[frm.doc.status] || "gray"}">
                <i class="fa fa-truck"></i> ${frm.doc.driver_name}
                ${frm.doc.driver_phone ? " &middot; " + frm.doc.driver_phone : ""}
            </span>`
        );
    }
}

function add_action_buttons(frm) {
    if (frm.doc.docstatus !== 1) return;
    const api = "ch_erp15.ch_erp15.transfer_manifest_api.";

    if (frm.doc.status === "Packed") {
        frm.add_custom_button(__("Assign Driver"), () => show_assign_driver_dialog(frm, api));
    }

    if (frm.doc.status === "Assigned") {
        frm.add_custom_button(__("Start Pickup"), () => show_pickup_dialog(frm, api));
    }

    if (frm.doc.status === "In Transit") {
        frm.add_custom_button(__("Complete Delivery"), () => show_delivery_dialog(frm, api));
    }

    if (frm.doc.status === "Delivered") {
        frm.add_custom_button(__("Accept Delivery"), () => show_accept_dialog(frm, api));
    }

    if (frm.doc.status === "Received") {
        frm.add_custom_button(__("Close Manifest"), () => {
            frappe.confirm(__("Close this manifest?"), () => {
                frappe.call({
                    method: api + "close_manifest",
                    args: { manifest: frm.doc.name },
                    callback: () => frm.reload_doc()
                });
            });
        });
    }

    // Resend OTP for Delivered status
    if (frm.doc.status === "Assigned" || frm.doc.status === "In Transit") {
        frm.add_custom_button(__("Resend OTP"), () => {
            frappe.call({
                method: api + "resend_otp",
                args: { manifest: frm.doc.name },
                callback: (r) => {
                    frappe.msgprint(__("OTP sent to destination store."));
                    frm.reload_doc();
                }
            });
        }, __("Actions"));
    }
}

function show_assign_driver_dialog(frm, api) {
    let d = new frappe.ui.Dialog({
        title: __("Assign Driver"),
        fields: [
            { fieldname: "driver", fieldtype: "Link", options: "Driver", label: __("Driver"), reqd: 1 },
            { fieldname: "courier_partner", fieldtype: "Link", options: "Courier Partner", label: __("Courier Partner") },
            { fieldname: "vehicle_number", fieldtype: "Data", label: __("Vehicle Number") },
            { fieldname: "tracking_number", fieldtype: "Data", label: __("Tracking Number") },
            { fieldname: "estimated_delivery_date", fieldtype: "Date", label: __("Estimated Delivery Date") },
        ],
        primary_action_label: __("Assign"),
        primary_action(values) {
            d.hide();
            frappe.call({
                method: api + "assign_driver",
                args: { manifest: frm.doc.name, ...values },
                callback: () => frm.reload_doc()
            });
        }
    });
    d.show();
}

function show_pickup_dialog(frm, api) {
    let d = new frappe.ui.Dialog({
        title: __("Start Pickup"),
        fields: [
            { fieldname: "pickup_photo", fieldtype: "Attach Image", label: __("Pickup Photo"), reqd: 1 },
            { fieldname: "notes", fieldtype: "Small Text", label: __("Notes") },
        ],
        primary_action_label: __("Confirm Pickup"),
        primary_action(values) {
            d.hide();
            // Get GPS
            capture_gps((lat, lng) => {
                frappe.call({
                    method: api + "start_pickup",
                    args: {
                        manifest: frm.doc.name,
                        pickup_photo: values.pickup_photo,
                        lat, lng,
                        notes: values.notes,
                    },
                    callback: () => frm.reload_doc()
                });
            });
        }
    });
    d.show();
}

function show_delivery_dialog(frm, api) {
    let d = new frappe.ui.Dialog({
        title: __("Complete Delivery"),
        fields: [
            { fieldname: "delivery_photo", fieldtype: "Attach Image", label: __("Delivery Photo"), reqd: 1 },
            { fieldname: "receiver_name", fieldtype: "Data", label: __("Receiver Name"), reqd: 1 },
            { fieldname: "otp", fieldtype: "Data", label: __("Delivery OTP"), reqd: 1 },
        ],
        primary_action_label: __("Confirm Delivery"),
        primary_action(values) {
            d.hide();
            capture_gps((lat, lng) => {
                frappe.call({
                    method: api + "complete_delivery",
                    args: {
                        manifest: frm.doc.name,
                        delivery_photo: values.delivery_photo,
                        receiver_name: values.receiver_name,
                        otp: values.otp,
                        lat, lng,
                    },
                    callback: () => frm.reload_doc()
                });
            });
        }
    });
    d.show();
}

function show_accept_dialog(frm, api) {
    let d = new frappe.ui.Dialog({
        title: __("Accept Delivery"),
        fields: [
            { fieldname: "damage_reported", fieldtype: "Check", label: __("Damage Reported") },
            { fieldname: "damage_notes", fieldtype: "Small Text", label: __("Damage Notes"), depends_on: "damage_reported" },
            { fieldname: "damage_photo", fieldtype: "Attach Image", label: __("Damage Photo"), depends_on: "damage_reported" },
        ],
        primary_action_label: __("Accept"),
        primary_action(values) {
            d.hide();
            frappe.call({
                method: api + "accept_delivery",
                args: {
                    manifest: frm.doc.name,
                    damage_reported: values.damage_reported,
                    damage_notes: values.damage_notes,
                    damage_photo: values.damage_photo,
                },
                callback: () => frm.reload_doc()
            });
        }
    });
    d.show();
}

function capture_gps(callback) {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (pos) => callback(pos.coords.latitude, pos.coords.longitude),
            () => callback(0, 0),
            { timeout: 5000 }
        );
    } else {
        callback(0, 0);
    }
}
