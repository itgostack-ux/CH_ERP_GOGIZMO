// frappe.ui.form.on("Purchase Receipt", {

//     onload_post_render(frm) {
//         zero_tax_if_unregistered(frm);
//     },

//     refresh(frm) {
//         zero_tax_if_unregistered(frm);
//     },

//     custom_purchase_type(frm) {
//         zero_tax_if_unregistered(frm);
//     },

//     supplier(frm) {
//         zero_tax_if_unregistered(frm);
//     },

//     items_add(frm) {
//         zero_tax_if_unregistered(frm);
//     },

//     validate(frm) {
//         zero_tax_if_unregistered(frm);
//     }

// });


// function zero_tax_if_unregistered(frm) {

//     if (frm.doc.custom_purchase_type !== "Unregistered") return;

//     // ⭐ Keep fetched rows — only neutralize them

//     (frm.doc.taxes || []).forEach(row => {

//         frappe.model.set_value(row.doctype, row.name, "rate", 0);

//         // Reset calculated values
//         frappe.model.set_value(row.doctype, row.name, "tax_amount", 0);
//         frappe.model.set_value(row.doctype, row.name, "base_tax_amount", 0);

//     });

//     // ⭐ Force totals to zero (without breaking links)
//     frm.set_value("total_taxes_and_charges", 0);
//     frm.set_value("base_total_taxes_and_charges", 0);

//     // ⭐ Recalculate document totals
//     frm.trigger("calculate_taxes_and_totals");

//     frm.refresh_field("taxes");
// }
frappe.ui.form.on("Purchase Receipt Item", {
    custom_imei_track: function(frm, cdt, cdn) {

        let row = locals[cdt][cdn];

        if (!row.custom_imei_track) {
            return;
        }

        if (!row.qty || row.qty <= 0) {
            frappe.msgprint("Please enter Qty first");
            frappe.model.set_value(cdt, cdn, "custom_imei_track", 0);
            return;
        }

        open_imei_dialog(frm, row);
    }
});


function open_imei_dialog(frm, row) {

    let table_data = [];
    let qty = parseInt(row.qty);

    for (let i = 0; i < qty; i++) {
        table_data.push({
            item_code: row.item_code,
            imei_no: ""
        });
    }

    let dialog = new frappe.ui.Dialog({
        title: "IMEI Entry",
        size: "large",

        fields: [
            {
                fieldname: "imei_table",
                fieldtype: "Table",
                label: "IMEI Numbers",
                in_place_edit: true,
                reqd: 1,
                data: table_data,

                fields: [
                    {
                        fieldtype: "Data",
                        fieldname: "item_code",
                        label: "Item Code",
                        read_only: 1,
                        in_list_view: 1
                    },
                    {
                        fieldtype: "Data",
                        fieldname: "imei_no",
                        label: "IMEI Number",
                        in_list_view: 1,
                        reqd: 1
                    }
                ]
            }
        ],

        primary_action_label: "Save",

        primary_action() {

            let imeis = dialog.fields_dict.imei_table.grid.get_data();

            if (!imeis || imeis.length === 0) {
                frappe.msgprint("Please enter IMEI numbers");
                return;
            }

            // Empty validation
            let empty = imeis.some(d => !d.imei_no);
            if (empty) {
                frappe.msgprint("All IMEI numbers are required");
                return;
            }

            // Duplicate validation
            let imei_list = imeis.map(d => d.imei_no);
            let unique = new Set(imei_list);

            if (unique.size !== imei_list.length) {
                frappe.msgprint("Duplicate IMEI numbers found");
                return;
            }

            // Remove existing IMEI rows for same item
            frm.doc.custom_track = (frm.doc.custom_track || []).filter(
                d => d.item_code !== row.item_code
            );

            // Add new rows
            imeis.forEach(function(d) {

                let child = frm.add_child("custom_track");

                child.item_code = d.item_code;
                child.imei_number = d.imei_no;

            });

            frm.refresh_field("custom_track");

            frappe.msgprint("IMEI Data Saved Successfully");

            dialog.hide();
        }
    });

    dialog.show();
    dialog.fields_dict.imei_table.grid.refresh();
}







