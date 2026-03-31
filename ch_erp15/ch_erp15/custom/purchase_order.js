// =====================================================
// ⭐ PURCHASE ORDER EVENTS (ONLY ONE BLOCK)
// =====================================================

frappe.ui.form.on("Purchase Order", {

    onload(frm) {
        disable_erp_calculation(frm);
        run_all(frm);
    },

    refresh(frm) {
        run_all(frm);
    },

    validate(frm) {
        run_all(frm);
    },

    custom_purchase_type(frm) {
        run_all(frm);
    }
});


// =====================================================
// ⭐ DISABLE ERP DEFAULT CALCULATION
// =====================================================

function disable_erp_calculation(frm) {
    frm.cscript = frm.cscript || {};

    if (!frm._calculation_disabled) {
        frm._calculation_disabled = true;

        frm.cscript.calculate_taxes_and_totals = function () {
            return;
        };
    }
}


// =====================================================
// ⭐ MASTER CONTROLLER
// =====================================================

function run_all(frm) {

    let type = frm.doc.custom_purchase_type;

    if (type === "Unregistered") {
        apply_zero_tax(frm);
    }
    else if (type === "Marginal") {
        apply_marginal_scheme(frm);
    }
    else if (type === "Taxable") {
        apply_taxable_scheme(frm);
    }
}


// =====================================================
// ⭐ ITEM EVENTS (ONLY ONE BLOCK)
// =====================================================

frappe.ui.form.on("Purchase Order Item", {

    qty(frm) {
        run_all(frm);
    },

    rate(frm) {
        run_all(frm);
    },

    custom_unit_taxable_value(frm) {
        run_all(frm);
    }
});


// =====================================================
// ⭐ TAX EVENTS
// =====================================================

frappe.ui.form.on("Purchase Taxes and Charges", {

    rate(frm) {
        run_all(frm);
    }
});


// =====================================================
// ⭐ ZERO TAX (UNREGISTERED)
// =====================================================

function apply_zero_tax(frm) {

    (frm.doc.taxes || []).forEach(row => {
        row.rate = 0;
        row.tax_amount = 0;
        row.base_tax_amount = 0;
        row.total = 0;
        row.base_total = 0;
    });

    frm.doc.net_total = 0;
    frm.doc.taxes_and_charges_added = 0;
    frm.doc.grand_total = 0;
    frm.doc.rounded_total = 0;

    frm.refresh_fields(["taxes", "net_total", "grand_total"]);
}


// =====================================================
// ⭐ MARGINAL SCHEME (UNCHANGED - CLEAN)
// =====================================================

function apply_marginal_scheme(frm) {

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

    (frm.doc.taxes || []).forEach(tax => {

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

    (frm.doc.items || []).forEach(item => {

        let qty = flt(item.qty);
        let margin_unit = flt(item.custom_unit_taxable_value);

        if (qty <= 0 || flt(item.amount) <= 0) return;

        let margin_taxable = qty * margin_unit;

        let item_gst = total_margin_taxable
            ? (margin_taxable / total_margin_taxable) * total_gst
            : 0;

        let exempted = flt(item.amount) - margin_taxable - item_gst;

        item.custom_exempted_value = Math.max(0, exempted);

        total_exempted += item.custom_exempted_value;
    });

    frm.doc.net_total = total_margin_taxable;
    frm.doc.taxes_and_charges_added = total_gst;

    let grand_total = total_margin_taxable + total_gst + total_exempted;

    frm.doc.grand_total = grand_total;
    frm.doc.rounded_total = Math.round(grand_total);

    frm.refresh_fields(["items", "taxes", "grand_total"]);
}


// =====================================================
// ⭐ TAXABLE SCHEME (FINAL FIXED)
// =====================================================
function apply_taxable_scheme(frm) {

    let total_taxable = 0;

    (frm.doc.items || []).forEach(item => {

        let qty = flt(item.qty);
        let unit_taxable = flt(item.custom_unit_taxable_value);

        if (qty <= 0 || unit_taxable <= 0) {
            item.rate = 0;
            item.amount = 0;
            item.taxable_value = 0;
            return;
        }

        // ✅ RATE (GST Inclusive)
        let rate = unit_taxable * 1.18;
        item.rate = rate;

        // ✅ AMOUNT
        let amount = qty * rate;
        item.amount = amount;
        item.base_amount = amount;

        // ✅ TAXABLE VALUE
        let taxable_value = qty * unit_taxable;
        item.taxable_value = taxable_value;

        total_taxable += taxable_value;
    });

    // ✅ GST
    let total_gst = total_taxable * 0.18;

    (frm.doc.taxes || []).forEach(tax => {

        tax.tax_amount = total_gst;
        tax.amount = total_gst;
        tax.total = total_gst;

        tax.base_tax_amount = total_gst;
        tax.base_amount = total_gst;
    });

    // ✅ BEFORE DISCOUNT TOTAL
    let grand_total = total_taxable + total_gst;

    // ✅ GET DISCOUNT
    let discount = flt(frm.doc.discount_amount);

    // ✅ FINAL GRAND TOTAL AFTER DISCOUNT
    let final_total = grand_total - discount;

    // 🛑 Safety (avoid negative total)
    if (final_total < 0) {
        final_total = 0;
    }

    // ✅ SET TOTALS
    frm.doc.net_total = total_taxable;
    frm.doc.total_taxes_and_charges = total_gst;
    frm.doc.taxes_and_charges_added = total_gst;

    frm.doc.grand_total = final_total;
    frm.doc.rounded_total = Math.round(final_total);

    // Optional (ERPNext consistency fields)
    frm.doc.base_grand_total = final_total;
    frm.doc.base_rounded_total = Math.round(final_total);

    frm.refresh_fields([
        "items",
        "taxes",
        "net_total",
        "grand_total",
        "rounded_total",
        "discount_amount"
    ]);
}