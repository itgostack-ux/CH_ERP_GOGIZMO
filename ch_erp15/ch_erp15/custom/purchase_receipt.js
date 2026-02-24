frappe.ui.form.on("Purchase Receipt", {

    onload_post_render(frm) {
        zero_tax_if_unregistered(frm);
    },

    refresh(frm) {
        zero_tax_if_unregistered(frm);
    },

    custom_purchase_type(frm) {
        zero_tax_if_unregistered(frm);
    },

    supplier(frm) {
        zero_tax_if_unregistered(frm);
    },

    items_add(frm) {
        zero_tax_if_unregistered(frm);
    },

    validate(frm) {
        zero_tax_if_unregistered(frm);
    }

});


function zero_tax_if_unregistered(frm) {

    if (frm.doc.custom_purchase_type !== "Unregistered") return;

    // ⭐ Keep fetched rows — only neutralize them

    (frm.doc.taxes || []).forEach(row => {

        frappe.model.set_value(row.doctype, row.name, "rate", 0);

        // Reset calculated values
        frappe.model.set_value(row.doctype, row.name, "tax_amount", 0);
        frappe.model.set_value(row.doctype, row.name, "base_tax_amount", 0);

    });

    // ⭐ Force totals to zero (without breaking links)
    frm.set_value("total_taxes_and_charges", 0);
    frm.set_value("base_total_taxes_and_charges", 0);

    // ⭐ Recalculate document totals
    frm.trigger("calculate_taxes_and_totals");

    frm.refresh_field("taxes");
}