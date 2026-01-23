// =======================================================
// PURCHASE ORDER – MARGINAL LOGIC (ERPNext 15)
// CLIENT SIDE (PREVIEW ONLY)
// =======================================================

frappe.ui.form.on("Purchase Order", {

    refresh(frm) {
        console.log("✅ Marginal Purchase JS Loaded");
    },

    supplier(frm) {
        if (frm.doc.custom_purchase_type === "Marginal") {
            frm.trigger("apply_marginal_tax_logic");
        }
    },

    custom_purchase_type(frm) {
        if (frm.doc.custom_purchase_type === "Marginal") {
            frm.trigger("apply_marginal_tax_logic");
        }
    },

    apply_marginal_tax_logic(frm) {

        if (frm.doc.custom_purchase_type !== "Marginal") return;

        console.log("🔥 Applying Marginal Tax Logic (JS)");

        let total_margin_taxable = 0;

        (frm.doc.items || []).forEach(row => {
            total_margin_taxable += flt(row.taxable_value || 0);
        });

        let running_total = total_margin_taxable;
        let total_tax = 0;

        (frm.doc.taxes || []).forEach(tax => {

            let tax_amount = 0;

            if (tax.charge_type === "On Net Total") {
                tax_amount = (total_margin_taxable * flt(tax.rate)) / 100;
                running_total += tax_amount;
                total_tax += tax_amount;
            }

            frappe.model.set_value(
                tax.doctype,
                tax.name,
                "tax_amount",
                tax_amount
            );

            frappe.model.set_value(
                tax.doctype,
                tax.name,
                "amount",
                tax_amount
            );

            frappe.model.set_value(
                tax.doctype,
                tax.name,
                "total",
                running_total
            );
        });

        let grand_total = total_margin_taxable + total_tax;

        frm.set_value("net_total", total_margin_taxable);
        frm.set_value("grand_total", grand_total);
        frm.set_value("rounded_total", Math.round(grand_total));
    }
});


// =======================================================
// ITEM LEVEL EVENTS
// =======================================================

frappe.ui.form.on("Purchase Order Item", {

    custom_unit_taxable_value(frm, cdt, cdn) {
        apply_margin_item_logic(frm, cdt, cdn);
    },

    qty(frm, cdt, cdn) {
        apply_margin_item_logic(frm, cdt, cdn);
    },

    rate(frm, cdt, cdn) {
        apply_margin_item_logic(frm, cdt, cdn);
    }
});


// =======================================================
// ITEM LEVEL LOGIC
// =======================================================

function apply_margin_item_logic(frm, cdt, cdn) {

    if (frm.doc.custom_purchase_type !== "Marginal") return;

    let row = locals[cdt][cdn];

    if (!row.qty || !row.rate || !row.custom_unit_taxable_value) return;

    let amount = flt(row.qty) * flt(row.rate);
    let taxable_value = flt(row.custom_unit_taxable_value) * flt(row.qty);

    frappe.model.set_value(cdt, cdn, "amount", amount);
    frappe.model.set_value(cdt, cdn, "base_amount", amount);
    frappe.model.set_value(cdt, cdn, "taxable_value", taxable_value);

    frm.trigger("apply_marginal_tax_logic");
}
