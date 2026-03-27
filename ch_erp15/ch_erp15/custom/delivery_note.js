// =====================================================
// ⭐ DELIVERY NOTE — FINAL TAX LOGIC
// item.taxable_value × 0.18 = tax.tax_amount
// =====================================================

let scan_in_progress = false;


// =====================================================
// ⭐ DELIVERY NOTE EVENTS (ONLY ONE BLOCK)
// =====================================================

frappe.ui.form.on("Delivery Note", {

    // onload(frm) {
    //     update_document_tax_amount(frm);
    // },

    // refresh(frm) {
    //     update_document_tax_amount(frm);
    // },

    custom_scan_imei__serial_no(frm) {

        const serial = (frm.doc.custom_scan_imei__serial_no || "").trim();
        if (!serial) return;

        if (scan_in_progress) return;
        scan_in_progress = true;

        process_serial_scan(frm, serial);
    }
});


// =====================================================
// ⭐ SERIAL SCAN LOGIC
// =====================================================

function process_serial_scan(frm, serial) {

    if (is_serial_already_used(frm, serial)) {
        frappe.msgprint(`⚠️ Serial ${serial} already scanned`);
        finish_scan(frm);
        return;
    }

    frappe.db.get_doc("Serial No", serial)

        .then(sn => {

            if (!sn.item_code) {
                frappe.msgprint("❌ Serial has no Item Code");
                finish_scan(frm);
                return;
            }

            let row =
                frm.doc.items.find(d => !d.item_code) ||
                frm.doc.items.find(d => d.item_code === sn.item_code) ||
                frm.add_child("items");


            // FIRST SERIAL
            if (!row.item_code) {

                frappe.model.set_value(row.doctype, row.name, "item_code", sn.item_code);

                if (sn.warehouse) {
                    frappe.model.set_value(row.doctype, row.name, "warehouse", sn.warehouse);
                }

                frappe.model.set_value(row.doctype, row.name, "qty", 1);
                frappe.model.set_value(row.doctype, row.name, "serial_no", serial);
            }

            // ADD SERIAL
            else {

                let serials = (row.serial_no || "")
                    .split("\n")
                    .map(s => s.trim())
                    .filter(Boolean);

                serials.push(serial);

                frappe.model.set_value(row.doctype, row.name, "serial_no", serials.join("\n"));
                frappe.model.set_value(row.doctype, row.name, "qty", serials.length);
            }


            // GET EXEMPTED VALUE
            frappe.call({
                method: "ch_erp15.ch_erp15.custom.delivery_note.get_exempted_value_from_serial",
                args: { serial: serial },

                callback: function(r) {

                    const value = r.message || 0;
                    const new_value = (row.custom_exempted_value || 0) + value;

                    frappe.model.set_value(
                        row.doctype,
                        row.name,
                        "custom_exempted_value",
                        new_value
                    );

                    update_row_taxable_value(row);
                    update_document_tax_amount(frm);
                }
            });

            update_row_taxable_value(row);
            update_document_tax_amount(frm);

            frm.refresh_field("items");

            frappe.show_alert({
                message: `✅ Added: ${sn.item_code} — ${serial}`,
                indicator: "green"
            });

            finish_scan(frm);
        })

        .catch(() => {
            frappe.msgprint("❌ Invalid Serial Number");
            finish_scan(frm);
        });
}


// =====================================================
// ⭐ DELIVERY NOTE ITEM EVENTS
// =====================================================

frappe.ui.form.on("Delivery Note Item", {

    rate(frm, cdt, cdn) {
        recalc_row(frm, cdt, cdn);
    },

    custom_exempted_value(frm, cdt, cdn) {
        recalc_row(frm, cdt, cdn);
    },

    qty(frm, cdt, cdn) {
        recalc_row(frm, cdt, cdn);
    }
});


// =====================================================
// ⭐ COMMON RECALC
// =====================================================

function recalc_row(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    update_row_taxable_value(row);
    update_document_tax_amount(frm);
}


// =====================================================
// ⭐ TAXABLE VALUE PER ITEM
// =====================================================

function update_row_taxable_value(row) {

    const rate = flt(row.rate);
    const exempt = flt(row.custom_exempted_value);
    const qty = flt(row.qty);

    let taxable = rate - exempt;
    if (taxable < 0) taxable = 0;

    frappe.model.set_value(row.doctype, row.name, "taxable_value", taxable);
    frappe.model.set_value(
        row.doctype,
        row.name,
        "custom_total_taxable_value",
        taxable * qty
    );
}


// =====================================================
// ⭐ FINAL TAX CALCULATION (USED EVERYWHERE)
// =====================================================

function update_document_tax_amount(frm) {

    if (!frm.doc.items || !frm.doc.taxes) return;

    let total_taxable = 0;

    (frm.doc.items || []).forEach(row => {
        total_taxable += flt(row.taxable_value) * flt(row.qty);
    });

    const tax_amount = total_taxable * 0.18;

    const tax_row = frm.doc.taxes[0];
    if (!tax_row) return;


    // ⭐ IMPORTANT — FORCE MANUAL TAX
    frappe.model.set_value(
        tax_row.doctype,
        tax_row.name,
        "charge_type",
        "Actual"
    );

    frappe.model.set_value(
        tax_row.doctype,
        tax_row.name,
        "tax_amount",
        tax_amount
    );


    // FORCE TOTAL RECALC
    frm.trigger("calculate_taxes_and_totals");

    frm.refresh_field("taxes");
}


// =====================================================
// ⭐ UTILITIES
// =====================================================

function is_serial_already_used(frm, serial) {

    for (let row of frm.doc.items || []) {

        let serials = (row.serial_no || "")
            .split("\n")
            .map(s => s.trim());

        if (serials.includes(serial)) return true;
    }

    return false;
}


function finish_scan(frm) {

    frm.set_value("custom_scan_imei__serial_no", "");

    setTimeout(() => {
        scan_in_progress = false;
    }, 150);
}