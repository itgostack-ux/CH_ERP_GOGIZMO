// // =====================================================
// // SALES ORDER ITEM — SERIAL → AUTO ITEM + EXEMPT VALUE
// // =====================================================

// // =====================================================
// // ⭐ SALES ORDER — RUN ON LOAD / REFRESH
// // =====================================================

// frappe.ui.form.on("Sales Order", {
//     onload: function(frm) {
//         update_all_rows(frm);
//     },

//     refresh: function(frm) {
//         update_all_rows(frm);
//     }
// });

// // =====================================================
// // ⭐ SERIAL FIELD HANDLER
// // =====================================================

// frappe.ui.form.on("Sales Order Item", {

//     custom_serial_noimei_no: function (frm, cdt, cdn) {

//         let row = locals[cdt][cdn];

//         if (!row.custom_serial_noimei_no) {
//             clear_fields(cdt, cdn);
//             return;
//         }

//         let serial = row.custom_serial_noimei_no.split("\n")[0].trim();
//         if (!serial) return;

//         frappe.db.get_doc("Serial No", serial).then(sn => {

//             if (!sn) {
//                 frappe.msgprint("❌ Serial not found");
//                 clear_fields(cdt, cdn);
//                 return;
//             }

//             if (sn.status !== "Active") {
//                 frappe.msgprint("❌ Serial not Active");
//                 clear_fields(cdt, cdn);
//                 return;
//             }

//             if (!sn.warehouse) {
//                 frappe.msgprint("❌ Serial not in warehouse");
//                 clear_fields(cdt, cdn);
//                 return;
//             }

//             // AUTO FILL
//             frappe.model.set_value(cdt, cdn, "item_code", sn.item_code);
//             frappe.model.set_value(cdt, cdn, "warehouse", sn.warehouse);
//             frappe.model.set_value(cdt, cdn, "qty", 1);
//             frappe.model.set_value(cdt, cdn, "serial_no", serial);

//             // FETCH EXEMPT VALUE
//             frappe.call({
//                 method: "ch_erp15.ch_erp15.custom.sales_order.get_exempted_value_from_serial",
//                 args: { serial: serial },
//                 callback: function (r) {

//                     let value = r.message || 0;

//                     frappe.model.set_value(cdt, cdn, "custom_exempted_value", value);

//                     // ⭐ RECALCULATE TAXABLE VALUE
//                     update_row(frm, cdt, cdn);

//                     // Show alert
//                     frappe.show_alert({
//                         message: "✅ Serial + Exempted value updated",
//                         indicator: "green"
//                     });
//                 }
//             });

//         }).catch(() => {
//             frappe.msgprint("❌ Invalid Serial");
//             clear_fields(cdt, cdn);
//         });
//     },

//     // Recalculate on change
//     rate: function(frm, cdt, cdn) {
//         // Keep old rate visible, but recalc taxable value
//         update_row(frm, cdt, cdn);
//     },
//     qty: update_row,
//     custom_exempted_value: update_row
// });

// // =====================================================
// // ⭐ UPDATE SINGLE ROW (TAXABLE CALC)
// // =====================================================

// function update_row(frm, cdt, cdn) {
//     let row = locals[cdt][cdn];

//     let rate = row.rate || 0;
//     let exempt = row.custom_exempted_value || 0;
//     let qty = row.qty || 1;

//     // TAXABLE VALUE CALCULATION
//     let taxable_value = rate - exempt;
//     if (taxable_value < 0) taxable_value = 0;

//     let amount = taxable_value * qty;

//     frappe.model.set_value(cdt, cdn, "amount", amount);
//     frappe.model.set_value(cdt, cdn, "taxable_value", taxable_value);

//     // Trigger amount for totals update
//     frm.script_manager.trigger("amount", cdt, cdn);
// }

// // =====================================================
// // ⭐ UPDATE ALL ROWS (ON LOAD / REFRESH)
// // =====================================================

// function update_all_rows(frm) {
//     (frm.doc.items || []).forEach(row => {
//         update_row(frm, row.doctype, row.name);
//     });
// }

// // =====================================================
// // ⭐ CLEAR HELPER
// // =====================================================

// function clear_fields(cdt, cdn) {
//     frappe.model.set_value(cdt, cdn, "serial_no", "");
//     frappe.model.set_value(cdt, cdn, "item_code", "");
//     frappe.model.set_value(cdt, cdn, "qty", 0);
//     frappe.model.set_value(cdt, cdn, "custom_exempted_value", 0);
//     frappe.model.set_value(cdt, cdn, "taxable_value", 0);
//     frappe.model.set_value(cdt, cdn, "amount", 0);
// }
// =====================================================
// ⭐ CHECKBOX → OPEN SERIAL SCANNER
// =====================================================

frappe.ui.form.on("Sales Order Item", {
    custom_imei__serial_no(frm, cdt, cdn) {

        let row = locals[cdt][cdn];
        if (!row.custom_imei__serial_no) return;

        open_serial_scanner(frm, cdt, cdn);
    }
});

// =====================================================
// ⭐ MAIN SCANNER FUNCTION
// =====================================================

function open_serial_scanner(frm, cdt, cdn) {

    let scanned_serials = [];
    let item_groups = {};  // item_code → { item_name, serials }

    let d = new frappe.ui.Dialog({
        title: "Scan Serial / IMEI",

        fields: [
            {
                label: "Scan Serial No",
                fieldname: "scanner",
                fieldtype: "Data"
            },
            {
                fieldname: "preview",
                fieldtype: "HTML"
            }
        ],

        primary_action_label: "Add to Sales Order",

        primary_action() {

            if (!Object.keys(item_groups).length) {
                frappe.msgprint("No serials scanned");
                return;
            }

            apply_to_sales_order(frm, cdt, cdn, item_groups);

            d.hide();
        }
    });

    d.show();

    let input = d.fields_dict.scanner.$input;
    setTimeout(() => input.focus(), 300);

    // =================================================
    // 🔥 SCAN HANDLER
    // =================================================

    input.on("change", function () {

        let serial = input.val().trim();
        if (!serial) return;

        input.val("");

        if (scanned_serials.includes(serial)) {
            frappe.show_alert("Duplicate Serial");
            return;
        }

        // 🔥 FETCH SERIAL NO DOCUMENT
        frappe.db.get_doc("Serial No", serial).then(sn => {

            if (!sn) {
                frappe.msgprint("Serial not found: " + serial);
                return;
            }

            if (sn.status !== "Active") {
                frappe.msgprint("Serial not Active: " + serial);
                return;
            }

            let item_code = sn.item_code;
            let item_name = sn.item_name || item_code;

            scanned_serials.push(serial);

            // GROUP BY ITEM
            if (!item_groups[item_code]) {
                item_groups[item_code] = {
                    item_name: item_name,
                    serials: []
                };
            }

            item_groups[item_code].serials.push(sn.name);  // Serial No Doc Name

            render_preview(d, item_groups);

        }).catch(() => {
            frappe.msgprint("Invalid Serial: " + serial);
        });
    });
}

// =====================================================
// ⭐ SHOW GROUPED PREVIEW
// =====================================================

function render_preview(dialog, groups) {

    let html = `<div style="max-height:300px;overflow:auto;">`;

    for (let item_code in groups) {

        let g = groups[item_code];

        html += `
            <div style="margin-bottom:14px;">
                <b>${g.item_name}</b> → Qty: ${g.serials.length}<br>
                ${g.serials.map(sn =>
                    `<div style="padding-left:15px;">${sn}</div>`
                ).join("")}
            </div>
        `;
    }

    html += `</div>`;

    dialog.fields_dict.preview.$wrapper.html(html);
}

// =====================================================
// ⭐ APPLY DATA TO SALES ORDER
// =====================================================

function apply_to_sales_order(frm, cdt, cdn, groups) {

    let first = true;

    for (let item_code in groups) {

        let g = groups[item_code];

        let target_row;

        // Use current row for first item
        if (first) {
            target_row = locals[cdt][cdn];
            first = false;
        }
        else {
            target_row = frm.add_child("items");
        }

        // AUTO FILL ITEM
        frappe.model.set_value(
            target_row.doctype,
            target_row.name,
            "item_code",
            item_code
        );

        frappe.model.set_value(
            target_row.doctype,
            target_row.name,
            "qty",
            g.serials.length
        );

        // SERIAL NO FIELD (ERPNext standard)
        frappe.model.set_value(
            target_row.doctype,
            target_row.name,
            "serial_no",
            g.serials.join("\n")
        );

        // OPTIONAL CUSTOM FIELD
        frappe.model.set_value(
            target_row.doctype,
            target_row.name,
            "serial_imei_nos",
            g.serials.join("\n")
        );
    }

    frm.refresh_field("items");

    frappe.show_alert({
        message: "✅ Items added using Serial No",
        indicator: "green"
    });
}

