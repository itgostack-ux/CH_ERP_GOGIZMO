
frappe.ui.form.on("Purchase Invoice", {

    onload(frm) {
        frm.cscript = frm.cscript || {};
        if (!frm._original_calculation) {
            frm._original_calculation = frm.cscript.calculate_taxes_and_totals;
        }
        frm.cscript.calculate_taxes_and_totals = function() {
            if (frm.doc.custom_purchase_type === "Marginal") {
                apply_zero_tax(frm);
                apply_marginal_scheme(frm);
                apply_on_marginal(frm);
                apply_taxable_scheme(frm);

                return;
            }
            if (frm._original_calculation) {
                frm._original_calculation.call(frm);
            }
        };
    },
    refresh(frm) {
        apply_zero_tax(frm);
        apply_marginal_scheme(frm);
        apply_on_marginal(frm);
        apply_taxable_scheme(frm);

    },

    custom_purchase_type(frm) {
        apply_zero_tax(frm);
        apply_marginal_scheme(frm);
        apply_on_marginal(frm)
        apply_taxable_scheme(frm)

    },

    validate(frm) {
        apply_marginal_scheme(frm);
        apply_on_marginal(frm);
        apply_zero_tax(frm);
        apply_taxable_scheme(frm)

        
        
    }
});

function apply_on_marginal(frm) {
    const is_m = frm.doc.custom_purchase_type === "Marginal";
    const style_id = "mt-hide-style";
    let css = "";
 

 
    let old = document.getElementById(style_id);
    if (old) old.remove();
 
    let style = document.createElement("style");
    style.id = style_id;
    style.innerHTML = css;
    document.head.appendChild(style);
 
    frm.refresh_field("items");
}
 





frappe.ui.form.on("Purchase Invoice Item", {

    qty(frm) {
        apply_marginal_scheme(frm);
        apply_zero_tax(frm);
        apply_taxable_scheme(frm)


        
    },

    rate(frm) {
        apply_marginal_scheme(frm);
        apply_zero_tax(frm);
        apply_taxable_scheme(frm)


    },

    custom_unit_taxable_value(frm) {
        apply_marginal_scheme(frm);
        apply_zero_tax(frm);
        apply_taxable_scheme(frm)

        

    }
});

frappe.ui.form.on("Purchase Taxes and Charges", {

    rate(frm) {
        apply_marginal_scheme(frm);
        apply_zero_tax(frm);
        apply_taxable_scheme(frm)

    }
});










function apply_zero_tax(frm) {

    if (frm.doc.custom_purchase_type !== "Unregistered") return;

    let total_amount = 0;


    
    (frm.doc.items || []).forEach(item => {

        let qty = flt(item.qty);
        let rate = flt(item.rate);

        let amount = qty * rate;

        item.amount = amount;
        item.base_amount = amount;

        total_amount += amount;
    });

    (frm.doc.taxes || []).forEach(row => {

        // row.rate = 0;

        row.tax_amount = 0;
        row.base_tax_amount = 0;

        row.total = total_amount;
        row.base_total = total_amount;
    });

    frm.doc.net_total = total_amount;
    frm.doc.base_net_total = total_amount;

    frm.doc.total = total_amount;
    frm.doc.base_total = total_amount;

    frm.doc.total_taxes_and_charges = 0;
    frm.doc.base_total_taxes_and_charges = 0;

    frm.doc.taxes_and_charges_added = 0;
    frm.doc.base_taxes_and_charges_added = 0;

    frm.doc.grand_total = total_amount;
    frm.doc.outstanding_amount= total_amount;
    frm.doc.base_grand_total = total_amount;

    frm.doc.rounded_total = Math.round(total_amount);
    frm.doc.base_rounded_total = Math.round(total_amount);

    frm.refresh_fields([
        "items",
        "taxes",
        "net_total",
        "grand_total",
        "rounded_total"
    ]);
}













function apply_marginal_scheme(frm) {

    if (frm.doc.custom_purchase_type !== "Marginal") return;

    let total_margin_taxable = 0;
    let total_gst = 0;
    let total_exempted = 0;

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

    (frm.doc.items || []).forEach(item => {

        let qty = flt(item.qty);
        let margin_unit = flt(item.custom_unit_taxable_value);

        if (qty <= 0 || flt(item.amount) <= 0) return;

        let margin_taxable = qty * margin_unit;

        let item_gst = 0;
        if (total_margin_taxable > 0) {
            item_gst = (margin_taxable / total_margin_taxable) * total_gst;
        }

        let exempted_value = flt(item.amount) - margin_taxable - item_gst;

        if (exempted_value < 0) {
            exempted_value = 0;
        }

        item.custom_exempted_value = exempted_value;

        total_exempted += exempted_value;
    });

    frm.refresh_field("items");


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
    frm.doc.outstanding_amount = custom_grand_total;

    frm.refresh_fields();
}



function apply_taxable_scheme(frm) {

    if (frm.doc.custom_purchase_type !== "Taxable") return;

    let total_taxable = 0;
    let total_gst = 0;

    
    (frm.doc.items || []).forEach(item => {

        let qty = flt(item.qty);
        let unit_taxable = flt(item.custom_unit_taxable_value);

        if (qty <= 0 || unit_taxable <= 0) {
            item.rate = 0;
            item.amount = 0;
            item.base_amount = 0;
            item.taxable_value = 0;
            return;
        }

        let rate = unit_taxable * 1.18;
        let amount = qty * rate;
        let taxable_value = qty * unit_taxable;

        item.rate = rate;
        item.amount = amount;
        item.base_amount = amount;
        item.taxable_value = taxable_value;

        total_taxable += taxable_value;
    });

    frm.refresh_field("items");

    
    total_gst = total_taxable * 0.18;

    (frm.doc.taxes || []).forEach(tax => {

        tax.tax_amount = total_gst;
        tax.amount = total_gst;
        tax.total = total_gst;

        tax.base_tax_amount = total_gst;
        tax.base_amount = total_gst;
    });

    frm.refresh_field("taxes");
    let gross_total = total_taxable + total_gst;
    let discount = flt(frm.doc.discount_amount);

    let final_total = gross_total - discount;

    if (final_total < 0) final_total = 0;

    frm.doc.net_total = total_taxable;
    frm.doc.base_net_total = total_taxable;

    frm.doc.total_taxes_and_charges = total_gst;
    frm.doc.base_total_taxes_and_charges = total_gst;

    frm.doc.taxes_and_charges_added = total_gst;
    frm.doc.base_taxes_and_charges_added = total_gst;

    frm.doc.grand_total = final_total;
    frm.doc.base_grand_total = final_total;

    frm.doc.rounded_total = Math.round(final_total);
    frm.doc.base_rounded_total = Math.round(final_total);
    frm.doc.outstanding_amount = final_total;

    frm.refresh_fields([
        "net_total",
        "total_taxes_and_charges",
        "grand_total",
        "rounded_total",
        "discount_amount"
    ]);
}