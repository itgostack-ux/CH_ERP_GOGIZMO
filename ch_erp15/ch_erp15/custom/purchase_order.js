frappe.ui.form.on("Purchase Order", {

    refresh(frm) {
        apply_zero_tax(frm);
        apply_marginal_scheme(frm);
        apply_on_marginal(frm);
    },

    onload(frm) {
        apply_zero_tax(frm);
        apply_marginal_scheme(frm);
        apply_on_marginal(frm);
    },

    custom_purchase_type(frm) {
        apply_zero_tax(frm);
        apply_on_marginal(frm);
    },

    validate(frm) {
        apply_marginal_scheme(frm);
        apply_on_marginal(frm);
    }

});

function apply_on_marginal(frm) {
    const is_m = frm.doc.custom_purchase_type === "Marginal";
    const style_id = "mt-hide-style";
    let css = "";

    if (!is_m) {
        css = `
        [data-fieldname="taxable_value"],
        [data-fieldname="custom_unit_taxable_value"],
        [data-fieldname="custom_exempted_value"] {
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

function apply_zero_tax(frm) {
    const is_unregistered = frm.doc.custom_purchase_type === "Unregistered";

    if (is_unregistered) {
        // Update all tax rows
        (frm.doc.taxes || []).forEach(row => {
            row.rate = 0;
            row.tax_amount = 0;
            row.base_tax_amount = 0;
            row.total = 0;
            row.base_total = 0;
        });

        // Refresh the child table to reflect changes
        frm.refresh_field("taxes");

        // Set total tax fields to 0
        frm.set_value("total_taxes_and_charges", 0);
        frm.set_value("base_total_taxes_and_charges", 0);

        // Recalculate totals
        frm.trigger("calculate_taxes_and_totals");
    }
}



frappe.ui.form.on("Purchase Order Item", {

    qty(frm) {
        apply_marginal_scheme(frm);
    },

    rate(frm) {
        apply_marginal_scheme(frm);
    },

    custom_unit_taxable_value(frm) {
        apply_marginal_scheme(frm);
    }

});


frappe.ui.form.on("Purchase Taxes and Charges", {

    rate(frm) {
        apply_marginal_scheme(frm);
    }

});


function apply_marginal_scheme(frm) {

    if (frm.doc.custom_purchase_type !== "Marginal") {
        return;
    }

    let total_margin_taxable = 0;
    let total_gst = 0;
    let total_exempted = 0;

    //--------------------------------------------------
    // ITEM LEVEL
    //--------------------------------------------------

    (frm.doc.items || []).forEach(item => {

        let qty = flt(item.qty);
        let rate = flt(item.rate);
        let margin_unit = flt(item.custom_unit_taxable_value);

        if (qty <= 0 || rate <= 0 || margin_unit <= 0) return;

        let item_amount = qty * rate;
        let margin_taxable = qty * margin_unit;

        item.amount = item_amount;
        item.base_amount = item_amount;
        item.taxable_value = margin_taxable;

        total_margin_taxable += margin_taxable;

    });

    frm.refresh_field("items");

    //--------------------------------------------------
    // TAX
    //--------------------------------------------------

    (frm.doc.taxes || []).forEach(tax => {

        tax.tax_amount = 0;
        tax.amount = 0;
        tax.total = 0;

        if (tax.charge_type === "On Net Total") {

            let tax_amount = (total_margin_taxable * flt(tax.rate)) / 100;

            tax.tax_amount = tax_amount;
            tax.amount = tax_amount;
            tax.total = tax_amount;

            tax.base_tax_amount = tax_amount;
            tax.base_amount = tax_amount;

            total_gst += tax_amount;
        }

    });

    frm.refresh_field("taxes");

    //--------------------------------------------------
    // EXEMPTED
    //--------------------------------------------------

    (frm.doc.items || []).forEach(item => {

        let qty = flt(item.qty);
        let margin_unit = flt(item.custom_unit_taxable_value);

        if (qty <= 0 || flt(item.amount) <= 0) return;

        let margin_taxable = qty * margin_unit;

        let exempted_value = flt(item.amount) - margin_taxable - total_gst;

        if (exempted_value < 0) {
            exempted_value = 0;
        }

        item.custom_exempted_value = exempted_value;

        total_exempted += exempted_value;

    });

    frm.refresh_field("items");

    //--------------------------------------------------
    // TOTALS
    //--------------------------------------------------

    frm.doc.net_total = total_margin_taxable;
    frm.doc.base_net_total = total_margin_taxable;

    frm.doc.taxes_and_charges_added = total_gst;
    frm.doc.base_taxes_and_charges_added = total_gst;

    frm.doc.total_taxes_and_charges = total_gst;
    frm.doc.base_total_taxes_and_charges = total_gst;

    let custom_grand_total = total_margin_taxable + total_gst + total_exempted;

    frm.doc.grand_total = custom_grand_total;
    frm.doc.base_grand_total = custom_grand_total;
    frm.doc.rounded_total = Math.round(custom_grand_total);

    frm.refresh_fields([
        "net_total",
        "taxes_and_charges_added",
        "grand_total",
        "rounded_total"
    ]);
}